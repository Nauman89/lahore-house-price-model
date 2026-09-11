"""Tests for discovery: URL construction, redaction, and walking the endpoint."""

from __future__ import annotations

import json

import pytest
from conftest import read_log

from lhp.scrape.discover import Discoverer, redact_personal_fields, slugify, write_refs
from lhp.scrape.fetch import FetchConfig, Fetcher

TOTAL = 7
PAGE_SIZE = 3


def api_config(base: str, page_size: int = PAGE_SIZE, max_pages: int = 50) -> dict:
    """Config shaped like config/scrape.yaml, pointed at a local server."""
    return {
        "source": {
            "api_base": f"{base}/api/v2",
            "listing_url_template": "https://example.test/house-for-sale/{slug}-pid{property_id}",
        },
        "query": {"cityId": 1, "type": "House", "status": "ForSale"},
        "discovery": {"page_size": page_size, "max_pages": max_pages},
    }


def record(i: int) -> dict:
    """One synthetic discovery row, including the personal fields that must be stripped."""
    return {
        "propertyId": 600000 + i,
        "heading": f"{5 + i} Marla House for Sale in Béta Block, Lahore!!",
        "price": 25000000 + i,
        "landArea": 5.0 + i,
        "areaUnitName": "marla",
        "agentName": "Someone",
        "agentPhone": "0300-1234567",
        "coverImage": {"agentPhone": "0300-7654321", "fullUrl": "https://x/y.jpg"},
    }


def paged(page: int, size: int, total: int = TOTAL) -> bytes:
    """An Ilaan-shaped envelope: data.data rows plus data.pagination."""
    start = (page - 1) * size
    rows = [record(i) for i in range(start, min(start + size, total))]
    more = start + size < total
    return json.dumps(
        {
            "success": True,
            "data": {
                "data": rows,
                "pagination": {
                    "page": page,
                    "pageSize": size,
                    "hasMore": more,
                    "nextPage": page + 1 if more else None,
                },
            },
        }
    ).encode()


@pytest.fixture
def api(server):
    """Serve the paged endpoint."""

    def route() -> tuple[int, bytes]:
        path = server.hits[-1]
        params = dict(p.split("=") for p in path.split("?", 1)[1].split("&"))
        return 200, paged(int(params["page"]), int(params["pageSize"]))

    server.routes["/api/v2"] = route
    return server


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("8.25 Marla House, Béta Road!!", "8-25-marla-house-beta-road"),
        ("", "house"),
        ("---", "house"),
    ],
)
def test_slugify(text: str, expected: str) -> None:
    """Slugs are lowercase, hyphenated, ASCII, and never empty."""
    assert slugify(text) == expected


def test_redaction_removes_contact_fields_at_any_depth() -> None:
    """Agent details are stripped wherever they appear in the payload."""
    cleaned = json.loads(redact_personal_fields(json.dumps({"data": {"data": [record(0)]}})))
    row = cleaned["data"]["data"][0]
    assert not {"agentName", "agentPhone", "agentWhatsApp", "agentEmail"} & set(row)
    assert "agentPhone" not in row["coverImage"]
    assert row["price"] == 25000000
    assert row["coverImage"]["fullUrl"]


def test_redaction_passes_non_json_through() -> None:
    """An HTML body is returned unchanged rather than raising."""
    assert redact_personal_fields("<html>hi</html>") == "<html>hi</html>"


def test_walk_finds_everything_and_stops_at_the_end(api, config) -> None:
    """Discovery follows hasMore and stops when the source says there is no more."""
    discoverer = Discoverer(api_config(api.base), Fetcher(config))
    refs = list(discoverer.run())
    assert len(refs) == TOTAL
    assert discoverer.stopped_reason == "exhausted"
    assert len({r.property_id for r in refs}) == TOTAL


def test_listing_url_is_built_from_the_property_id(api, config) -> None:
    """The id drives the URL; the slug is cosmetic."""
    refs = list(Discoverer(api_config(api.base), Fetcher(config)).run())
    assert refs[0].url.endswith("-pid600000")
    assert "/house-for-sale/" in refs[0].url


def test_hints_are_carried_for_cross_checking(api, config) -> None:
    """What the endpoint claimed is kept so the fetched page can be checked against it."""
    refs = list(Discoverer(api_config(api.base), Fetcher(config)).run())
    assert refs[0].price_hint == 25000000
    assert refs[0].area_unit_hint == "marla"


def test_max_pages_guard_marks_the_result_incomplete(api, config) -> None:
    """Hitting the guard is recorded, so no stopping rule is applied to a partial count."""
    discoverer = Discoverer(api_config(api.base, max_pages=1), Fetcher(config))
    refs = list(discoverer.run())
    assert len(refs) == PAGE_SIZE
    assert discoverer.stopped_reason == "guard"


def test_a_failed_page_stops_the_walk_without_losing_earlier_pages(api, config) -> None:
    """A gap in discovery is invisible later, so the walk stops rather than skipping."""
    original = api.routes["/api/v2"]

    def sometimes_down() -> tuple[int, bytes]:
        path = api.hits[-1]
        if "page=3" in path:
            return 502, b"host error"
        return original()

    api.routes["/api/v2"] = sometimes_down
    discoverer = Discoverer(api_config(api.base), Fetcher(config))
    refs = list(discoverer.run())
    assert len(refs) == 6
    assert discoverer.stopped_reason == "fetch_failed"
    assert discoverer.last_page == 2


def test_rerunning_after_an_outage_costs_only_the_missing_pages(api, config) -> None:
    """Cached pages are not re-requested, so resuming is nearly free."""
    original = api.routes["/api/v2"]
    down = {"on": True}

    def sometimes_down() -> tuple[int, bytes]:
        if down["on"] and "page=3" in api.hits[-1]:
            return 502, b"host error"
        return original()

    api.routes["/api/v2"] = sometimes_down
    fetcher = Fetcher(config)
    list(Discoverer(api_config(api.base), fetcher).run())
    before = api.hit_count

    down["on"] = False
    discoverer = Discoverer(api_config(api.base), fetcher)
    refs = list(discoverer.run())
    assert len(refs) == TOTAL
    assert discoverer.stopped_reason == "exhausted"
    assert api.hit_count - before == 1  # only page 3


def test_write_refs_round_trips(api, config, tmp_path) -> None:
    """References survive the trip to disk as one JSON object per line."""
    refs = list(Discoverer(api_config(api.base), Fetcher(config)).run())
    out = tmp_path / "discovery.jsonl"
    assert write_refs(iter(refs), out) == TOTAL
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == TOTAL
    assert json.loads(lines[0])["property_id"] == 600000


def test_no_personal_data_reaches_the_cache(api, config) -> None:
    """The redaction filter is wired in before anything is written."""
    import gzip

    redacting = FetchConfig(**{**config.__dict__, "body_filter": redact_personal_fields})
    list(Discoverer(api_config(api.base), Fetcher(redacting)).run())
    blob = "".join(
        gzip.open(p, "rt", encoding="utf-8").read() for p in redacting.cache_dir.rglob("*.gz")
    )
    assert "0300-1234567" not in blob
    assert "Someone" not in blob
    assert "25000000" in blob
    assert read_log(redacting)
