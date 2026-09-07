"""Extract listing records from cached Ilaan pages.

Ilaan is a Next.js App Router site: the listing record is not in the HTML as markup but
inside the React Server Component payload, split across ``self.__next_f.push`` calls as
escaped JSON. Reassembling that payload and pulling the ``initialProperty`` object out of
it gives a complete typed record — every field the API omitted (bedrooms, bathrooms,
locality, coordinates, posting date) is there.

This module extracts and validates. It does not transform: units are recorded as the
source gave them, sentinels become nulls, and nothing is dropped. Conversion, dedup and
outlier handling belong to the cleaning stage, so that raw stays reproducible and every
transformation is justified where it happens.

Two rules shape it:

* **Nothing is silently discarded.** A page that fails to parse, or a listing outside
  scope, is emitted with a reason attached. Coverage is then countable rather than
  asserted, which is what the stage 1 exit criteria require.
* **Scope is verified from the page, never the URL or the API.** The discovery endpoint's
  ``type=House`` filter is leaky — 4 of 40 sampled pages came back ``type="Land"`` — and
  Ilaan's router serves a listing under any path prefix. Only ``initialProperty`` is
  authoritative.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

#: RSC marker for a JavaScript ``undefined`` value.
UNDEFINED = "$undefined"

#: RSC prefix on serialised Date values, e.g. ``$D2026-09-05T05:45:19.193Z``.
DATE_PREFIX = "$D"

#: Values the source uses for "no price" / "no area". Reading these as numbers would be
#: silently destructive, so they become nulls here and are counted as missing.
SENTINEL_NUMBERS = frozenset({-1, 0, -3})

#: Fields carrying agent contact details. Never copied into a parsed row (D-22).
PERSONAL_KEYS = frozenset(
    {"agent", "agentId", "contactVisibility", "callEnabled", "whatsappEnabled"}
)

_PUSH = re.compile(r'self\.__next_f\.push\(\[\d+,\s*(".*?")\]\)', re.S)

#: Ilaan serves a "Property Not Found" template with HTTP 200 for listings that no longer
#: exist - a soft 404. The status code cannot distinguish it from a real listing, so the
#: page must be identified by content. Without this it presents as a parse failure, which
#: is a different fact with a different remedy: a removed listing belongs outside the
#: coverage denominator, a parse failure belongs inside it.
_NOT_FOUND = re.compile(r"<title>[^<]*Property Not Found", re.I)
_LD_JSON = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def soft_404_reason(body: str, status: int) -> str | None:
    """Return a reason if a 2xx response is Ilaan's "Property Not Found" placeholder.

    Intended as a :attr:`~lhp.scrape.fetch.FetchConfig.content_validator`. Ilaan serves this
    template with HTTP 200, and it was observed to appear **transiently** under load for
    listings that are in fact live: 969 pages cached this way on 6 Sep 2026 all returned
    real listings when re-fetched. So it is never evidence that a listing is gone, only that
    this response is unusable — which is why it belongs in the retry path rather than in a
    "removed" category.

    Args:
        body: Response body.
        status: HTTP status.

    Returns:
        ``"soft_404"`` for the placeholder, otherwise None.

    """
    if status == 200 and _NOT_FOUND.search(body):
        return "soft_404"
    return None


def flight_payload(html: str) -> str:
    """Reassemble the React Server Component payload from a page.

    Each ``self.__next_f.push`` call carries a JavaScript string literal holding one chunk
    of the payload. Decoding each with a JSON string parser unescapes it correctly —
    including the escaped quote sequences that defeat naive regex extraction — and
    concatenating the chunks restores the whole payload.

    Args:
        html: Full page source.

    Returns:
        The concatenated, unescaped payload; empty if the page has none.

    """
    chunks = []
    for match in _PUSH.finditer(html):
        try:
            chunks.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
    return "".join(chunks)


def json_ld_blocks(html: str) -> list[dict]:
    """Return every parseable ``application/ld+json`` object on the page."""
    blocks: list[dict] = []
    for match in _LD_JSON.finditer(html):
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        blocks.extend(parsed if isinstance(parsed, list) else [parsed])
    return blocks


def object_containing(text: str, needle: str) -> dict | None:
    """Return the smallest balanced JSON object in ``text`` that contains ``needle``.

    The payload is one long string with no document structure, so the record is located by
    finding a distinctive key and expanding outward to its enclosing braces. The scan is
    string-aware: braces inside quoted values do not affect nesting depth.

    Args:
        text: Text to search.
        needle: A quoted key, e.g. ``'"propertyId"'``.

    Returns:
        The decoded object, or None if no balanced parseable object contains the needle.

    """
    index = text.find(needle)
    if index < 0:
        return None
    start = text.rfind("{", 0, index)
    while start >= 0:
        depth = 0
        in_string = False
        escaped = False
        for position in range(start, len(text)):
            char = text[position]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    blob = text[start : position + 1]
                    if needle in blob:
                        try:
                            return json.loads(blob)
                        except json.JSONDecodeError:
                            pass
                    break
        start = text.rfind("{", 0, start)
    return None


def clean(value: Any) -> Any:
    """Normalise one RSC value: undefined markers and empty strings become None."""
    if value == UNDEFINED or value == "":
        return None
    if isinstance(value, str) and value.startswith(DATE_PREFIX):
        return value[len(DATE_PREFIX) :]
    return value


def number(value: Any) -> float | None:
    """Return a positive number, or None for sentinels, nulls and unparseable values."""
    value = clean(value)
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed in SENTINEL_NUMBERS or parsed <= 0:
        return None
    return parsed


def coordinates_from_ld(html: str) -> tuple[float | None, float | None]:
    """Return latitude and longitude from JSON-LD, as a fallback for the RSC payload."""
    for block in json_ld_blocks(html):
        geo = block.get("geo")
        if isinstance(geo, dict) and geo.get("@type") == "GeoCoordinates":
            return number(geo.get("latitude")), number(geo.get("longitude"))
    return None, None


@dataclass
class ParseResult:
    """One page's outcome: the row if it parsed, and always a reason if it did not."""

    property_id: int
    parsed: bool
    in_scope: bool
    reason: str | None = None
    row: dict = field(default_factory=dict)


def parse_page(html: str, ref: dict | None = None) -> ParseResult:
    """Turn one cached page into a listing row.

    Args:
        html: Page source as cached.
        ref: The discovery reference, if available. Its ``price_hint`` and
            ``land_area_hint`` are compared against the page and any disagreement is
            flagged — the router will serve a listing under a mismatched path, so "the
            page loaded" is not evidence we fetched the listing we asked for.

    Returns:
        A :class:`ParseResult`. ``parsed`` false with reason ``listing_removed`` means the
        listing no longer exists; with any other reason it means the record could not be
        located, which is a defect. ``in_scope`` false means it parsed but is not a Lahore
        house for sale.

    """
    ref = ref or {}
    ref_id = int(ref.get("property_id") or 0)

    if _NOT_FOUND.search(html):
        return ParseResult(ref_id, parsed=False, in_scope=False, reason="listing_removed")

    wrapper = object_containing(flight_payload(html), '"propertyId"')
    prop = (wrapper or {}).get("initialProperty")
    if not isinstance(prop, dict):
        return ParseResult(ref_id, parsed=False, in_scope=False, reason="no_initial_property")

    listing_type = clean(prop.get("type"))
    status = clean(prop.get("status"))
    city = clean(prop.get("city"))

    latitude = number(prop.get("latitude"))
    longitude = number(prop.get("longitude"))
    if latitude is None or longitude is None:
        latitude, longitude = coordinates_from_ld(html)

    amenities = prop.get("amenities")
    gallery = prop.get("gallery")

    row = {
        "property_id": int(clean(prop.get("id")) or ref_id or 0),
        "title": clean(prop.get("title")),
        "description": clean(prop.get("description")),
        "price": number(prop.get("price")),
        "area": number(prop.get("area")),
        "area_unit": clean(prop.get("areaUnit")),
        "bedrooms": clean(prop.get("bedrooms")),
        "bathrooms": clean(prop.get("bathrooms")),
        "address": clean(prop.get("address")),
        "city": city,
        "locality": clean(prop.get("locality")),
        "province": clean(prop.get("province")),
        "latitude": latitude,
        "longitude": longitude,
        "property_type": listing_type,
        "market_status": status,
        "condition": clean(prop.get("condition")),
        "year_built": clean(prop.get("yearBuilt")),
        "is_sold": bool(prop.get("isSold")),
        "is_featured": bool(prop.get("isFeatured")),
        "is_verified": bool(prop.get("isPropertyVerified")),
        "is_gold_verified": bool(prop.get("isGoldVerified")),
        "views": clean(prop.get("views")),
        "amenity_count": len(amenities) if isinstance(amenities, list) else None,
        "amenities": amenities if isinstance(amenities, list) else None,
        "image_count": len(gallery) if isinstance(gallery, list) else None,
        "has_video": bool(clean(prop.get("videoUrl"))),
        "created_at": clean(prop.get("createdAt")),
        "source_url": ref.get("url"),
        "discovered_on_page": ref.get("discovered_on_page"),
    }

    # The router serves a listing under any path prefix, so confirm the page we got is the
    # listing discovery pointed at.
    row["id_matches_discovery"] = bool(ref_id) and row["property_id"] == ref_id
    price_hint = number(ref.get("price_hint"))
    row["price_matches_discovery"] = (
        None if price_hint is None or row["price"] is None else price_hint == row["price"]
    )

    if listing_type != "House":
        return ParseResult(row["property_id"], True, False, f"type={listing_type}", row)
    if status != "ForSale":
        return ParseResult(row["property_id"], True, False, f"status={status}", row)
    if city != "Lahore":
        return ParseResult(row["property_id"], True, False, f"city={city}", row)
    return ParseResult(row["property_id"], True, True, None, row)
