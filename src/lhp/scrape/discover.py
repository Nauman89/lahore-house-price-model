"""Discover Lahore house-for-sale listings and turn them into fetchable page URLs.

Ilaan publishes no sitemap that identifies houses, and paginates its search entirely in
JavaScript, so the set of listing IDs is not reachable through any page URL. The only route
to it is the endpoint the site's own frontend calls.

Per `project-log/decisions/02-acquisition.md` D-21, that endpoint is used for **discovery
only**: listing IDs and a few values kept solely to cross-check the pages we then fetch.
Every field that reaches the model is parsed by `parse.py` from the public listing pages,
which robots.txt permits without qualification.

Two properties of the source shape this module:

* The API reports `hasMore` and `nextPage` but no total, so inventory size is learned by
  walking to the end rather than read off the first response.
* Listing URLs are built from `propertyId`. Ilaan's router resolves the segment after
  ``-pid``, and accepts the numeric id as well as the opaque code its own links use
  (verified 5 Sep 2026), so no slug lookup is needed.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlencode

from lhp.scrape.fetch import Fetcher, FetchFailed

logger = logging.getLogger(__name__)

#: Fields the discovery endpoint returns that carry personal data. Stripped by
#: :func:`redact_personal_fields` before any response is cached — see D-22.
PERSONAL_FIELDS = frozenset(
    {
        "agentName",
        "agentPhone",
        "agentWhatsApp",
        "agentEmail",
        "contactVisibility",
        "whatsappEnabled",
        "callEnabled",
    }
)

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def redact_personal_fields(body: str) -> str:
    """Strip agent contact fields from a JSON response body.

    Intended as a :attr:`~lhp.scrape.fetch.FetchConfig.body_filter`, so redaction happens
    before the response is cached and before this module ever sees it. Bodies that are not
    JSON objects — HTML listing pages, error documents — are returned unchanged.

    Args:
        body: Raw response body.

    Returns:
        The body with every :data:`PERSONAL_FIELDS` key removed at any depth, re-serialised;
        or the original string if it is not JSON.

    """
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return body

    def strip(node: object) -> object:
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k not in PERSONAL_FIELDS}
        if isinstance(node, list):
            return [strip(item) for item in node]
        return node

    return json.dumps(strip(payload))


def slugify(text: str, max_length: int = 80) -> str:
    """Turn a listing heading into a URL slug.

    The slug is cosmetic — Ilaan resolves on the ``-pid<id>`` suffix alone — but a
    descriptive one keeps our requests legible in the operator's logs and close in shape to
    the canonical URLs their own pages use.

    Args:
        text: Listing heading.
        max_length: Truncation limit, applied on a word boundary.

    Returns:
        A lowercase hyphenated slug, or ``"house"`` if nothing usable survives.

    """
    normalised = unicodedata.normalize("NFKD", text or "")
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii").lower()
    slug = _NON_SLUG.sub("-", ascii_only).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]
    return slug or "house"


@dataclass(frozen=True)
class ListingRef:
    """A discovered listing: its id, the URL we will fetch, and values to check it against.

    The three ``*_hint`` fields are not model inputs. They are what the discovery endpoint
    claimed, kept so `parse.py` can assert that the page it fetched is the listing the API
    pointed at, rather than silently accepting whatever the router returned.
    """

    property_id: int
    url: str
    heading: str
    price_hint: int | None
    land_area_hint: float | None
    area_unit_hint: str | None
    discovered_on_page: int


class Discoverer:
    """Walks the discovery endpoint and yields listing references."""

    def __init__(self, config: dict, fetcher: Fetcher) -> None:
        """Prepare a discoverer.

        Args:
            config: Parsed `config/scrape.yaml`.
            fetcher: Fetcher whose ``body_filter`` should be
                :func:`redact_personal_fields`.

        """
        self.config = config
        self.fetcher = fetcher
        self.source = config["source"]
        self.query = dict(config["query"])
        self.discovery = config["discovery"]
        #: Why the last :meth:`run` ended. ``exhausted`` is the only value that means the
        #: inventory was fully enumerated; every other value means the count is a lower
        #: bound and must not be judged against the stopping rule.
        self.stopped_reason: str | None = None
        #: The last page fetched successfully, for resuming.
        self.last_page: int = 0

    def page_url(self, page: int) -> str:
        """Return the discovery endpoint URL for one page of results."""
        params = {
            **self.query,
            "page": page,
            "pageSize": self.discovery["page_size"],
        }
        return f"{self.source['api_base']}?{urlencode(params)}"

    def listing_url(self, property_id: int, heading: str) -> str:
        """Return the public listing page URL for a discovered id."""
        return self.source["listing_url_template"].format(
            slug=slugify(heading), property_id=property_id
        )

    def _rows(self, payload: dict) -> tuple[list[dict], dict]:
        """Split a response envelope into its rows and its pagination block."""
        data = payload.get("data") or {}
        rows = data.get("data") or []
        pagination = data.get("pagination") or {}
        return rows, pagination

    def run(self, start_page: int = 1, refresh: bool = False) -> Iterator[ListingRef]:
        """Yield every listing reference the endpoint exposes, in page order.

        Stops at the first of: ``hasMore`` false, an empty page, a page that failed every
        retry, or the configured ``max_pages`` guard. :attr:`stopped_reason` records which,
        because only ``exhausted`` licenses a judgement against the stopping rule.

        A page that cannot be fetched ends the walk rather than being skipped: a silent gap
        of fifty listings would surface later as an unexplained coverage shortfall. Re-running
        is cheap — already-fetched pages come from cache without a network request — so
        resuming after an outage costs only the pages not yet seen.

        Args:
            start_page: Page to begin from. Defaults to the first.
            refresh: Bypass the cache and re-request every page, for a fresh snapshot.

        Yields:
            One :class:`ListingRef` per distinct listing.

        """
        seen: set[int] = set()
        page = start_page
        max_pages = self.discovery["max_pages"]

        while page <= max_pages:
            try:
                response = self.fetcher.get(self.page_url(page), refresh=refresh)
            except FetchFailed as exc:
                logger.error("page %s failed every retry: %s", page, exc)
                self.stopped_reason = "fetch_failed"
                return
            try:
                payload = json.loads(response.body)
            except json.JSONDecodeError:
                logger.error(
                    "page %s returned a non-JSON body (%s bytes)", page, len(response.body)
                )
                self.stopped_reason = "bad_payload"
                return
            if not payload.get("success", True):
                logger.warning("page %s returned success=false: %s", page, payload.get("error"))
                self.stopped_reason = "source_error"
                return

            rows, pagination = self._rows(payload)
            if not rows:
                logger.info("page %s empty; discovery complete", page)
                self.stopped_reason = "exhausted"
                return
            self.last_page = page

            for row in rows:
                property_id = row.get("propertyId")
                if property_id is None or property_id in seen:
                    continue
                seen.add(property_id)
                heading = row.get("heading") or ""
                yield ListingRef(
                    property_id=property_id,
                    url=self.listing_url(property_id, heading),
                    heading=heading,
                    price_hint=row.get("price"),
                    land_area_hint=row.get("landArea"),
                    area_unit_hint=row.get("areaUnitName"),
                    discovered_on_page=page,
                )

            if not pagination.get("hasMore"):
                logger.info("hasMore false at page %s; discovery complete", page)
                self.stopped_reason = "exhausted"
                return
            page = pagination.get("nextPage") or page + 1

        self.stopped_reason = "guard"
        logger.warning(
            "stopped at the max_pages guard (%s); inventory is incomplete", max_pages
        )


def write_refs(refs: Iterator[ListingRef], path: Path) -> int:
    """Write listing references to a JSONL file, one object per line.

    Args:
        refs: References to write.
        path: Destination. Parent directories are created.

    Returns:
        The number of references written.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for ref in refs:
            handle.write(json.dumps(asdict(ref), sort_keys=True) + "\n")
            count += 1
    return count
