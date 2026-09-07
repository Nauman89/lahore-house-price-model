"""Polite, cached HTTP fetching with robots.txt enforcement.

Reusable across projects. Nothing in this module knows about property listings: it
fetches URLs, obeys each host's robots.txt, writes every response to disk, and
appends one audit line per request.

Three commitments shape the design:

* A URL disallowed by robots.txt **raises**. It is never skipped quietly, because a
  silent skip resurfaces later as an unexplained gap in coverage with no cause
  attached to it.
* Every response is cached before it is returned, so a rerun costs no network
  traffic and an interrupted run resumes for free.
* The audit log records the robots decision and a hash of the robots.txt that
  produced it. "Zero requests to disallowed paths" is then verifiable from the log
  rather than merely asserted.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import requests
from protego import Protego

logger = logging.getLogger(__name__)

#: Sent when robots.txt is missing (4xx): an empty policy permits everything.
_PERMISSIVE = ""

#: Sent when robots.txt cannot be read (5xx or network failure): fail closed.
_RESTRICTIVE = "User-agent: *\nDisallow: /\n"


class FetchError(RuntimeError):
    """Base class for every failure raised by this module."""


class DisallowedByRobots(FetchError):
    """A URL was blocked by its host's robots.txt."""


class FetchFailed(FetchError):
    """A URL could not be retrieved within the configured retry budget."""


def summarise_log(path: Path) -> dict[str, int]:
    """Tally the audit log by outcome.

    Turns the request log into the evidence a coverage claim needs: how many requests
    succeeded, how many were client errors, how many were transient server failures the
    retry absorbed, and how many were refused by robots.

    Args:
        path: The JSONL audit log.

    Returns:
        Outcome counts, ordered most frequent first. Empty if the log does not exist.

    """
    if not path.exists():
        return {}
    counts: dict[str, int] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                outcome = json.loads(line).get("outcome", "unknown")
            except json.JSONDecodeError:
                outcome = "unparseable_log_line"
            counts[outcome] = counts.get(outcome, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def url_key(url: str) -> str:
    """Return the stable cache key for a URL.

    Args:
        url: Absolute URL.

    Returns:
        Hex SHA-256 of the URL. Used as both the cache filename and the log key, so a
        cached file can always be traced back to the request that produced it.

    """
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


class RobotsPolicy:
    """One host's robots.txt, together with the provenance needed to audit it."""

    def __init__(self, host: str, user_agent: str, content: str, origin: str) -> None:
        """Build a policy from robots.txt text.

        Args:
            host: Hostname the policy governs, e.g. ``www.example.com``.
            user_agent: The agent token we identify as, used for group matching.
            content: Verbatim robots.txt text, or a synthetic policy (see ``origin``).
            origin: How the content was obtained — ``fetched``, ``absent`` (4xx, so
                everything is permitted) or ``unavailable`` (5xx or network error, so
                everything is refused). Recorded in the log so a synthetic policy is
                never mistaken for something the host actually published.

        """
        self.host = host
        self.user_agent = user_agent
        self.content = content
        self.origin = origin
        self.sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        # Protego, not urllib.robotparser: the stdlib parser silently discards
        # duplicate "User-agent: *" groups and resolves conflicts by file order
        # rather than by longest match, both of which under-restrict us.
        self._rules = Protego.parse(content)

    @classmethod
    def for_host(
        cls,
        url: str,
        user_agent: str,
        session: requests.Session,
        timeout: float = 30.0,
    ) -> RobotsPolicy:
        """Retrieve and parse the robots.txt governing a URL's host.

        Follows RFC 9309 section 2.3.1.3 on unreachable files: a 4xx means no
        restrictions exist, while a 5xx or a network failure means we must assume the
        whole host is off limits rather than guess in our own favour.

        Args:
            url: Any URL on the host.
            user_agent: The agent token we identify as.
            session: Session used for the request.
            timeout: Per-request timeout in seconds.

        Returns:
            A policy for that host.

        """
        parts = urlsplit(url)
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        try:
            response = session.get(robots_url, timeout=timeout)
        except requests.RequestException as exc:
            logger.warning("robots.txt unreachable for %s (%s); refusing host", parts.netloc, exc)
            return cls(parts.netloc, user_agent, _RESTRICTIVE, "unavailable")

        if response.status_code >= 500:
            logger.warning(
                "robots.txt returned %s for %s; refusing host", response.status_code, parts.netloc
            )
            return cls(parts.netloc, user_agent, _RESTRICTIVE, "unavailable")
        if response.status_code >= 400:
            logger.info(
                "no robots.txt for %s (%s); no restrictions",
                parts.netloc,
                response.status_code,
            )
            return cls(parts.netloc, user_agent, _PERMISSIVE, "absent")
        return cls(parts.netloc, user_agent, response.text, "fetched")

    def allows(self, url: str) -> bool:
        """Return whether robots.txt permits us to fetch this URL."""
        return bool(self._rules.can_fetch(url, self.user_agent))

    def check(self, url: str) -> None:
        """Raise :class:`DisallowedByRobots` unless this URL is permitted.

        Raises:
            DisallowedByRobots: If the host's robots.txt disallows the URL.

        """
        if not self.allows(url):
            raise DisallowedByRobots(
                f"{url} is disallowed by {self.host}/robots.txt "
                f"(policy origin: {self.origin}, sha256: {self.sha256[:12]})"
            )

    @property
    def declared_delay(self) -> float | None:
        """The host's ``Crawl-delay`` for our agent, in seconds, if it declares one."""
        declared = self._rules.crawl_delay(self.user_agent)
        return None if declared is None else float(declared)

    @property
    def sitemaps(self) -> list[str]:
        """Sitemap URLs declared in robots.txt, in the order they appear."""
        return list(self._rules.sitemaps)


@dataclass(frozen=True)
class FetchConfig:
    """Settings for a :class:`Fetcher`.

    Attributes:
        user_agent: Identifies us to the host. Should name the project and give a way
            to make contact, so an operator who dislikes the traffic can say so.
        cache_dir: Root of the on-disk response cache.
        log_path: JSONL audit log, appended to, one line per request.
        min_delay: Lower bound on the pause between network requests, in seconds.
        max_delay: Upper bound. The actual pause is drawn uniformly from the range so
            the traffic does not arrive on a metronome.
        timeout: Per-request timeout in seconds.
        max_retries: Attempts after the first before giving up on a retryable status.
        backoff_base: Exponential backoff multiplier between retries.
        retry_statuses: Status codes worth retrying. Transient server and rate-limit
            responses only — a 404 means the listing is gone and retrying is noise.
        body_filter: Optional hook applied to every response body **before it is cached
            and before it is returned**. Use it to strip material that must never reach
            disk — personal data above all. A filter that cannot handle a given body
            should return it unchanged rather than raise.
        content_validator: Optional hook deciding whether a 2xx response actually carries
            the content it should. Returns a short reason when it does not, and None when
            it is fine. A status code is not evidence of content: sites serve "not found"
            and error templates with 200, and a pipeline that trusts the status caches them
            as successes. An invalid response is retried like a 5xx, is never cached, and an
            invalid **cached** entry is treated as a miss so a re-run repairs it.

    """

    user_agent: str
    cache_dir: Path
    log_path: Path
    min_delay: float = 1.0
    max_delay: float = 2.0
    timeout: float = 30.0
    max_retries: int = 3
    backoff_base: float = 2.0
    retry_statuses: frozenset[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )
    body_filter: Callable[[str], str] | None = None
    content_validator: Callable[[str, int], str | None] | None = None


@dataclass(frozen=True)
class FetchResult:
    """One retrieved page, from the network or from cache."""

    url: str
    status: int
    body: str
    headers: dict[str, str]
    fetched_at: str
    from_cache: bool

    @property
    def key(self) -> str:
        """The cache key for this result's URL."""
        return url_key(self.url)


class Fetcher:
    """Fetches URLs politely, caches them, and logs every decision.

    Example:
        >>> config = FetchConfig(
        ...     user_agent="lhp-scraper/0.1 (+https://github.com/Nauman89/...)",
        ...     cache_dir=Path("data/raw/cache"),
        ...     log_path=Path("data/raw/requests.jsonl"),
        ... )
        >>> fetcher = Fetcher(config)
        >>> page = fetcher.get("https://example.com/listing/1")
        >>> page.status
        200

    """

    def __init__(self, config: FetchConfig, session: requests.Session | None = None) -> None:
        """Prepare a fetcher.

        Args:
            config: Delays, paths and retry policy.
            session: Optional session, mainly so tests can supply a fake. A session
                with our User-Agent is created if none is given.

        """
        self.config = config
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = config.user_agent
        self._policies: dict[str, RobotsPolicy] = {}
        self._last_request_at: dict[str, float] = {}
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)
        self.config.log_path.parent.mkdir(parents=True, exist_ok=True)

    def policy_for(self, url: str) -> RobotsPolicy:
        """Return the robots policy for a URL's host, fetching it once per host."""
        host = urlsplit(url).netloc
        if host not in self._policies:
            self._policies[host] = RobotsPolicy.for_host(
                url, self.config.user_agent, self.session, self.config.timeout
            )
        return self._policies[host]

    def _cache_path(self, url: str) -> Path:
        """Return the cache file for a URL, sharded two levels deep by key prefix."""
        key = url_key(url)
        return self.config.cache_dir / key[:2] / key[2:4] / f"{key}.json.gz"

    def _read_cache(self, url: str) -> FetchResult | None:
        """Return the cached result for a URL, or None if it is not cached."""
        path = self._cache_path(url)
        if not path.exists():
            return None
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        return FetchResult(
            url=payload["url"],
            status=payload["status"],
            body=payload["body"],
            headers=payload["headers"],
            fetched_at=payload["fetched_at"],
            from_cache=True,
        )

    def _write_cache(self, result: FetchResult) -> None:
        """Persist a fetched result, writing the URL alongside it for traceability."""
        path = self._cache_path(result.url)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "url": result.url,
            "status": result.status,
            "headers": result.headers,
            "fetched_at": result.fetched_at,
            "body": result.body,
        }
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def _invalid_reason(self, body: str, status: int) -> str | None:
        """Return why a response is not usable content, or None if it is fine."""
        if self.config.content_validator is None or status >= 400:
            return None
        return self.config.content_validator(body, status)

    def _log(self, **row: object) -> None:
        """Append one JSON object to the audit log."""
        row.setdefault("logged_at", datetime.now(UTC).isoformat())
        with self.config.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    def _sleep(self, host: str, policy: RobotsPolicy) -> None:
        """Pause before hitting a host again, honouring the longer of the two policies."""
        floor = self.config.min_delay
        declared = policy.declared_delay
        if declared is not None and declared > floor:
            floor = declared
        wait = random.uniform(floor, max(floor, self.config.max_delay))
        since = time.monotonic() - self._last_request_at.get(host, float("-inf"))
        if since < wait:
            time.sleep(wait - since)

    def get(self, url: str, refresh: bool = False) -> FetchResult:
        """Fetch a URL, serving it from cache when possible.

        Args:
            url: Absolute URL to retrieve.
            refresh: Bypass the cache and re-fetch from the network.

        Returns:
            The response, whether from cache or from the network.

        Raises:
            DisallowedByRobots: If the host's robots.txt disallows the URL. Checked
                before the cache, so a URL that becomes disallowed is refused even if
                an earlier run cached it.
            FetchFailed: If every attempt failed or returned a retryable status.

        """
        policy = self.policy_for(url)
        allowed = policy.allows(url)
        if not allowed:
            self._log(
                url=url,
                key=url_key(url),
                robots_allowed=False,
                robots_origin=policy.origin,
                robots_sha256=policy.sha256,
                from_cache=False,
                status=None,
                outcome="disallowed",
            )
            policy.check(url)

        if not refresh:
            cached = self._read_cache(url)
            if cached is not None:
                stale = self._invalid_reason(cached.body, cached.status)
                self._log(
                    url=url,
                    key=cached.key,
                    robots_allowed=True,
                    robots_origin=policy.origin,
                    robots_sha256=policy.sha256,
                    from_cache=True,
                    status=cached.status,
                    outcome="cache_hit" if stale is None else "invalid_cache",
                    error=stale,
                )
                if stale is None:
                    return cached
                logger.info("cached copy of %s is invalid (%s); re-fetching", url, stale)

        host = urlsplit(url).netloc
        last_error: str | None = None
        for attempt in range(self.config.max_retries + 1):
            self._sleep(host, policy)
            self._last_request_at[host] = time.monotonic()
            try:
                response = self.session.get(url, timeout=self.config.timeout)
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                outcome, status = "network_error", None
            else:
                status = response.status_code
                if status in self.config.retry_statuses:
                    last_error = f"HTTP {status}"
                    outcome = "server_error" if status >= 500 else "rate_limited"
                else:
                    body = response.text
                    if self.config.body_filter is not None:
                        body = self.config.body_filter(body)
                    invalid = self._invalid_reason(body, status)
                    if invalid is not None:
                        # Never cached: a placeholder stored as a success is a silent
                        # corruption that only surfaces downstream, far from its cause.
                        last_error = f"invalid content: {invalid}"
                        outcome = "invalid_content"
                        self._log(
                            url=url,
                            key=url_key(url),
                            robots_allowed=True,
                            robots_origin=policy.origin,
                            robots_sha256=policy.sha256,
                            from_cache=False,
                            status=status,
                            attempt=attempt,
                            outcome=outcome,
                            error=last_error,
                        )
                        if attempt < self.config.max_retries:
                            time.sleep(self.config.backoff_base**attempt)
                        continue
                    result = FetchResult(
                        url=url,
                        status=status,
                        body=body,
                        headers=dict(response.headers),
                        fetched_at=datetime.now(UTC).isoformat(),
                        from_cache=False,
                    )
                    self._write_cache(result)
                    self._log(
                        url=url,
                        key=result.key,
                        robots_allowed=True,
                        robots_origin=policy.origin,
                        robots_sha256=policy.sha256,
                        from_cache=False,
                        status=status,
                        attempt=attempt,
                        outcome="ok" if status < 400 else "client_error",
                        bytes=len(response.content),
                    )
                    return result

            self._log(
                url=url,
                key=url_key(url),
                robots_allowed=True,
                robots_origin=policy.origin,
                robots_sha256=policy.sha256,
                from_cache=False,
                status=status,
                attempt=attempt,
                outcome=outcome,
                error=last_error,
            )
            if attempt < self.config.max_retries:
                time.sleep(self.config.backoff_base**attempt)

        raise FetchFailed(
            f"{url} failed after {self.config.max_retries + 1} attempts: {last_error}"
        )
