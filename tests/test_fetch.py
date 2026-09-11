"""Tests for the fetch layer: robots enforcement, caching, retries and the audit log."""

from __future__ import annotations

import gzip
import json

import pytest
from conftest import SOFT_404, read_log

from lhp.scrape.fetch import (
    DisallowedByRobots,
    FetchConfig,
    Fetcher,
    FetchFailed,
    RobotsPolicy,
    summarise_log,
)

# Graana's real robots.txt shape, verified 5 Sep 2026: two separate "User-agent: *" groups.
# RFC 9309 says merge them; urllib.robotparser keeps only the first and silently discards
# the rest, which reports every disallowed path as permitted. This fixture is the reason
# protego is a dependency, so it must keep failing on a non-compliant parser.
TWO_STAR_GROUPS = """User-agent: *
Content-Signal: search=yes,ai-train=no
Allow: /

User-agent: *
Disallow: /*?
Disallow: /secret/
Sitemap: https://example.com/sitemap.xml
"""

# One well-formed group where a broad Allow precedes a narrower Disallow. RFC 9309 resolves
# by longest match; a first-match parser reports /secret/ as allowed.
LONGEST_MATCH = """User-agent: *
Allow: /
Disallow: /secret/
Crawl-delay: 7
"""


@pytest.mark.parametrize(
    ("robots", "url", "allowed"),
    [
        (TWO_STAR_GROUPS, "https://x.test/property/1/", True),
        (TWO_STAR_GROUPS, "https://x.test/secret/", False),
        (TWO_STAR_GROUPS, "https://x.test/a/?page=2", False),
        (LONGEST_MATCH, "https://x.test/property/1/", True),
        (LONGEST_MATCH, "https://x.test/secret/", False),
    ],
)
def test_robots_rules(robots: str, url: str, allowed: bool) -> None:
    """Duplicate groups are merged and the longest matching rule wins."""
    policy = RobotsPolicy("x.test", "lhp-tests/0.1", robots, "fetched")
    assert policy.allows(url) is allowed


def test_robots_reports_delay_and_sitemaps() -> None:
    """Crawl-delay and Sitemap lines are read from the file."""
    assert RobotsPolicy("x.test", "a", LONGEST_MATCH, "fetched").declared_delay == 7.0
    policy = RobotsPolicy("x.test", "a", TWO_STAR_GROUPS, "fetched")
    assert policy.sitemaps == ["https://example.com/sitemap.xml"]


def test_missing_robots_permits_everything(server, config) -> None:
    """A 4xx on robots.txt means no restrictions exist (RFC 9309 2.3.1.3)."""
    server.robots = None
    server.routes["/robots.txt"] = (404, b"nope")
    fetcher = Fetcher(config)
    policy = fetcher.policy_for(f"{server.base}/x")
    assert policy.origin == "absent"
    assert policy.allows(f"{server.base}/anything")


def test_unreadable_robots_refuses_everything(config) -> None:
    """A 5xx or network failure on robots.txt means the host is off limits, not open."""
    fetcher = Fetcher(config)
    policy = fetcher.policy_for("http://127.0.0.1:9/x")  # nothing listening
    assert policy.origin == "unavailable"
    assert not policy.allows("http://127.0.0.1:9/anything")


def test_disallowed_url_raises_and_is_logged(server, config) -> None:
    """A blocked URL fails loudly rather than being skipped, and the attempt is recorded."""
    server.robots = b"User-agent: *\nDisallow: /secret/\n"
    fetcher = Fetcher(config)
    with pytest.raises(DisallowedByRobots):
        fetcher.get(f"{server.base}/secret/")
    assert server.hit_count == 0
    assert [r["outcome"] for r in read_log(config)] == ["disallowed"]


def test_response_is_cached_and_reused(server, config) -> None:
    """The second call is served from disk without touching the network."""
    server.routes["/p/1"] = (200, b"<html>listing</html>")
    fetcher = Fetcher(config)
    first = fetcher.get(f"{server.base}/p/1")
    second = fetcher.get(f"{server.base}/p/1")
    assert first.from_cache is False
    assert second.from_cache is True
    assert second.body == first.body
    assert server.hit_count == 1


def test_cache_survives_a_new_fetcher(server, config) -> None:
    """Resume is free: a fresh instance reads the cache rather than re-requesting."""
    server.routes["/p/1"] = (200, b"<html>listing</html>")
    Fetcher(config).get(f"{server.base}/p/1")
    assert Fetcher(config).get(f"{server.base}/p/1").from_cache is True
    assert server.hit_count == 1


def test_cache_is_gzipped_and_records_its_url(server, config) -> None:
    """A cached file can be traced back to the request that produced it."""
    server.routes["/p/1"] = (200, b"<html>listing</html>")
    fetcher = Fetcher(config)
    fetcher.get(f"{server.base}/p/1")
    files = list(config.cache_dir.rglob("*.json.gz"))
    assert len(files) == 1
    with gzip.open(files[0], "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["url"] == f"{server.base}/p/1"


def test_server_errors_are_retried_then_succeed(server, config) -> None:
    """Transient 5xx responses are retried with backoff."""
    calls = {"n": 0}

    def flaky() -> tuple[int, bytes]:
        calls["n"] += 1
        return (502, b"host error") if calls["n"] < 3 else (200, b"recovered")

    server.routes["/flaky"] = flaky
    result = Fetcher(config).get(f"{server.base}/flaky")
    assert result.body == "recovered"
    assert calls["n"] == 3


def test_client_errors_are_not_retried(server, config) -> None:
    """A 404 is a fact about the listing, not a transient failure."""
    server.routes["/gone"] = (404, b"gone")
    result = Fetcher(config).get(f"{server.base}/gone")
    assert result.status == 404
    assert server.hit_count == 1


def test_outcomes_are_categorised_distinctly(server, config) -> None:
    """"The site was down" and "the listing was removed" never pool into one number."""
    server.routes["/ok"] = (200, b"fine")
    server.routes["/gone"] = (404, b"gone")
    server.routes["/down"] = (500, b"boom")
    fetcher = Fetcher(config)
    fetcher.get(f"{server.base}/ok")
    fetcher.get(f"{server.base}/gone")
    with pytest.raises(FetchFailed):
        fetcher.get(f"{server.base}/down")
    tally = summarise_log(config.log_path)
    assert tally["ok"] == 1
    assert tally["client_error"] == 1
    assert tally["server_error"] == config.max_retries + 1


def test_every_log_row_carries_the_robots_provenance(server, config) -> None:
    """Which robots.txt governed which request is recoverable after the fact."""
    server.routes["/p/1"] = (200, b"listing")
    fetcher = Fetcher(config)
    fetcher.get(f"{server.base}/p/1")
    fetcher.get(f"{server.base}/p/1")
    rows = read_log(config)
    assert rows and all(len(r["robots_sha256"]) == 64 for r in rows)
    assert {r["robots_origin"] for r in rows} == {"fetched"}


def test_body_filter_runs_before_the_cache_is_written(server, config, tmp_path) -> None:
    """Material stripped by the filter never reaches disk."""
    server.routes["/p/1"] = (200, b'{"agentPhone": "0300-1234567", "price": 1}')
    filtered = FetchConfig(
        **{**config.__dict__, "body_filter": lambda b: b.replace("0300-1234567", "")}
    )
    Fetcher(filtered).get(f"{server.base}/p/1")
    blob = "".join(
        gzip.open(p, "rt", encoding="utf-8").read() for p in filtered.cache_dir.rglob("*.gz")
    )
    assert "0300-1234567" not in blob
    assert "price" in blob


def test_invalid_content_is_retried_and_never_cached(server, config) -> None:
    """A 200 carrying a placeholder is treated as a failure, not as a success."""
    server.routes["/p/1"] = (200, SOFT_404.encode())
    validated = FetchConfig(
        **{
            **config.__dict__,
            "content_validator": lambda b, s: "soft_404" if "Not Found" in b else None,
        }
    )
    with pytest.raises(FetchFailed):
        Fetcher(validated).get(f"{server.base}/p/1")
    assert server.hit_count == validated.max_retries + 1
    assert not list(validated.cache_dir.rglob("*.gz"))


def test_an_invalid_cached_entry_repairs_itself(server, config) -> None:
    """A cache poisoned before validation existed is re-fetched, not trusted."""
    server.routes["/p/1"] = (200, SOFT_404.encode())
    Fetcher(config).get(f"{server.base}/p/1")  # no validator: the placeholder is cached

    server.routes["/p/1"] = (200, b"<html>the real listing</html>")
    validated = FetchConfig(
        **{
            **config.__dict__,
            "content_validator": lambda b, s: "soft_404" if "Not Found" in b else None,
        }
    )
    result = Fetcher(validated).get(f"{server.base}/p/1")
    assert "the real listing" in result.body
    assert summarise_log(config.log_path)["invalid_cache"] == 1
