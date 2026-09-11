"""Tests for parsing: record extraction, sentinel handling, and scope verification."""

from __future__ import annotations

import pytest
from conftest import SOFT_404, listing, rsc_page

from lhp.scrape.parse import parse_page, soft_404_reason


def test_record_is_reassembled_from_split_rsc_chunks() -> None:
    """The payload arrives in fragments; the record is only findable once rejoined."""
    result = parse_page(rsc_page(listing(), chunks=5))
    assert result.parsed and result.in_scope
    assert result.row["property_id"] == 600001
    assert result.row["price"] == 25000000
    assert result.row["bedrooms"] == 4


def test_undefined_markers_become_null() -> None:
    """React's serialised `undefined` is not a value."""
    row = parse_page(rsc_page(listing(latitude="$undefined", longitude="$undefined"))).row
    assert row["latitude"] is None
    assert row["longitude"] is None


def test_date_prefix_is_stripped() -> None:
    """`$D` marks a serialised Date and is not part of the timestamp."""
    row = parse_page(rsc_page(listing())).row
    assert row["created_at"] == "2024-05-01T10:00:00.000Z"


@pytest.mark.parametrize("bad", [-1, 0, -3.0])
def test_sentinel_prices_and_areas_become_null(bad: float) -> None:
    """A -1 price reaching a model produces no error, just a corrupted fit."""
    row = parse_page(rsc_page(listing(price=bad, area=bad))).row
    assert row["price"] is None
    assert row["area"] is None


def test_empty_locality_becomes_null() -> None:
    """An empty string is missing data, not a category."""
    assert parse_page(rsc_page(listing(locality=""))).row["locality"] is None


def test_coordinates_fall_back_to_json_ld() -> None:
    """Where the payload has no coordinates, JSON-LD may still carry them."""
    page = rsc_page(listing(latitude="$undefined", longitude="$undefined"), geo=(31.47, 74.32))
    row = parse_page(page).row
    assert row["latitude"] == 31.47
    assert row["longitude"] == 74.32


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"type": "Land"}, "type=Land"),
        ({"type": "Commercial"}, "type=Commercial"),
        ({"status": "ForRent"}, "status=ForRent"),
        ({"city": "Karachi"}, "city=Karachi"),
    ],
)
def test_out_of_scope_rows_are_flagged_not_dropped(overrides: dict, reason: str) -> None:
    """Scope comes from the payload, and an excluded row still carries its reason."""
    result = parse_page(rsc_page(listing(**overrides)))
    assert result.parsed
    assert not result.in_scope
    assert result.reason == reason
    assert result.row  # the row survives so the exclusion can be audited


def test_scope_is_taken_from_the_payload_not_the_url() -> None:
    """Ilaan's router serves any listing under any path prefix, so the URL proves nothing."""
    ref = {"property_id": 600001, "url": "https://example.test/house-for-sale/x-pid600001"}
    result = parse_page(rsc_page(listing(type="Land")), ref)
    assert not result.in_scope


def test_agent_contact_never_reaches_the_row() -> None:
    """D-22: contact fields are dropped at the parse boundary, not merely unpublished."""
    row = parse_page(rsc_page(listing())).row
    assert not any("agent" in key.lower() for key in row)
    assert "0300-0000000" not in str(row)


def test_discovery_hints_are_cross_checked() -> None:
    """"The page loaded" is not evidence we fetched the listing we asked for."""
    page = rsc_page(listing())
    matching = {"property_id": 600001, "price_hint": 25000000}
    assert parse_page(page, matching).row["id_matches_discovery"] is True
    assert parse_page(page, matching).row["price_matches_discovery"] is True

    mismatched = {"property_id": 600001, "price_hint": 999}
    assert parse_page(page, mismatched).row["price_matches_discovery"] is False


def test_a_page_without_a_record_fails_rather_than_returning_empty() -> None:
    """An unparseable page is a defect with a reason, not a blank row."""
    result = parse_page("<html><body>nothing here</body></html>")
    assert not result.parsed
    assert result.reason == "no_initial_property"


def test_soft_404_is_identified_as_removed_not_as_a_parse_failure() -> None:
    """The placeholder is a distinct outcome; calling it a parse failure blames the parser."""
    result = parse_page(SOFT_404)
    assert not result.parsed
    assert result.reason == "listing_removed"


@pytest.mark.parametrize(
    ("body", "status", "expected"),
    [
        (SOFT_404, 200, "soft_404"),
        ("<html><title>10 Marla House</title></html>", 200, None),
        (SOFT_404, 404, None),  # a real 404 is handled by status, not by content
    ],
)
def test_soft_404_validator(body: str, status: int, expected: str | None) -> None:
    """The validator fires only on a 2xx carrying the placeholder."""
    assert soft_404_reason(body, status) == expected
