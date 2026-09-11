"""Tests for the stage 2 cleaning pipeline.

Every fixture is invented (D-29). Nothing here reproduces an Ilaan listing: the titles,
addresses, coordinates and prices are fabricated to have the *shape* of the real thing —
a title stating an area, an address ordered from most specific to least, a bulk posting of
identically-titled rows — with values that belong to no property.

The suite is weighted towards the findings that cost the most to establish, because those
are the ones a later change is most likely to undo without anyone noticing:

* the payload wins on area quantity and the title wins on unit (D-32, reversed mid-stage)
* "Multan Road" is a Lahore road, not the city of Multan (D-34)
* zero-variance is measured over every row, not the analysis set (D-37)
* junk removal runs before the collapse, never after (D-44 / D-45)
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from lhp import clean

# --------------------------------------------------------------------------------------
# Fixtures — all invented
# --------------------------------------------------------------------------------------

#: Every column `run_cleaning` expects from the interim file, with harmless defaults.
_DEFAULTS: dict[str, object] = {
    "property_id": 900001,
    "source_url": "https://example.invalid/listing/900001",
    "discovered_on_page": 1,
    "id_matches_discovery": True,
    "price_matches_discovery": True,
    "in_scope": True,
    "scope_reason": None,
    "title": "5 Marla House for Sale in Test Block, Testville, Lahore",
    "address": "Test Block, Testville, Lahore, Punjab, Pakistan",
    "description": "",
    "price": 18_000_000.0,
    "area": 5.0,
    "area_unit": "marla",
    "bedrooms": 4,
    "bathrooms": 4,
    "locality": "Testville",
    "latitude": 31.45,
    "longitude": 74.35,
    "created_at": "2024-01-15T09:00:00.000Z",
    "views": 5,
    "image_count": 6,
    "is_featured": False,
    "has_video": False,
    "condition": "New",
    "year_built": 2026,
    "is_verified": False,
    "is_gold_verified": False,
    "is_sold": False,
    "market_status": "ForSale",
    "city": "Lahore",
    "province": "Punjab",
    "amenity_count": 0,
    "amenities": [],
    "property_type": "House",
}


def row(**overrides: object) -> dict[str, object]:
    """One synthetic interim row, with any field overridden."""
    return {**_DEFAULTS, **overrides}


def frame(*rows: dict[str, object]) -> pd.DataFrame:
    """A frame of synthetic rows, with distinct property ids."""
    records = []
    for index, record in enumerate(rows or (row(),)):
        records.append({**record, "property_id": record.get("property_id", 900001 + index)})
    return pd.DataFrame.from_records(records)


@pytest.fixture()
def interim_file(tmp_path):
    """Write synthetic rows to a JSONL file and return the path, for whole-pipeline tests."""

    def write(rows: list[dict[str, object]]) -> str:
        path = tmp_path / "listings.jsonl"
        with open(path, "w", encoding="utf-8") as handle:
            for record in rows:
                handle.write(json.dumps(record) + "\n")
        return str(path)

    return write


# --------------------------------------------------------------------------------------
# Unit vocabulary and title parsing
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("marla", "marla"),
        ("Marla", "marla"),
        ("KANAL", "kanal"),
        ("Sq.ft", "square feet"),
        ("sq ft", "square feet"),
        ("square feet", "square feet"),
        ("Sq. Yd.", "square yard"),
        ("acreage", "acreage"),
        ("furlong", None),
        (None, None),
        (7, None),
    ],
)
def test_canonical_unit(raw, expected):
    assert clean.canonical_unit(raw) == expected


@pytest.mark.parametrize(
    ("quantity", "unit", "expected"),
    [
        (5, "marla", 5.0),
        (1, "kanal", 20.0),
        (225, "square feet", 1.0),
        (25, "square yard", 1.0),
        (1, "acreage", 160.0),
    ],
)
def test_to_marla_conversions(quantity, unit, expected):
    assert clean.to_marla(quantity, unit) == pytest.approx(expected)


@pytest.mark.parametrize(
    "bad", [(None, "marla"), (5, None), (5, "furlong"), (float("nan"), "marla")]
)
def test_to_marla_returns_none_rather_than_zero(bad):
    """An unconvertible value must never look like zero area to a caller."""
    assert clean.to_marla(*bad) is None


def test_parse_title_area_reads_a_compound_title_in_order():
    assert clean.parse_title_area("1 Kanal 4 Marla House for Sale in Testville, Lahore") == [
        (1.0, "kanal"),
        (4.0, "marla"),
    ]


def test_parse_title_area_ignores_numbers_that_are_not_areas():
    """"Phase 2" and "Block 5" are not areas; only a number followed by a unit is."""
    assert clean.parse_title_area("House for Sale in Phase 2, Block 5, Testville") == []


def test_parse_title_area_on_a_title_with_no_area():
    assert clean.parse_title_area("House for Sale in Testville, Lahore") == []


# --------------------------------------------------------------------------------------
# Area reconciliation — D-32, including the direction that was reversed mid-stage
# --------------------------------------------------------------------------------------


def test_area_agreement_keeps_the_payload_and_flags_nothing():
    result = clean.resolve_area("5 Marla House for Sale in Testville", 5.0, "marla")
    assert (result.area_marla, result.source, result.flags) == (5.0, "payload", ())


def test_title_wins_when_the_unit_disagrees_payload_marla_title_kanal():
    """The B-15 defect: payload says marla, title says kanal. A 20x error."""
    result = clean.resolve_area("2 Kanal House for Sale in Testville", 2.0, "marla")
    assert result.area_marla == 40.0
    assert result.source == "title"
    assert "area_unit_corrected" in result.flags


def test_title_wins_when_the_unit_disagrees_the_other_way_too():
    """The direction B-15 did not record, and the more common one: 37 rows against 18."""
    result = clean.resolve_area("5 Marla House for Sale in Testville", 5.0, "kanal")
    assert result.area_marla == 5.0
    assert result.source == "title"
    assert "area_unit_corrected" in result.flags


def test_unit_correction_takes_the_title_quantity_as_well():
    """A payload whose unit field is broken has not earned trust in the number beside it."""
    result = clean.resolve_area("10 Marla House for Sale in Testville", 1.0, "kanal")
    assert result.area_marla == 10.0  # not 20.0, which is the payload's own reading


def test_compound_title_beats_a_mis_encoded_decimal():
    """"1 Kanal 2 Marla" stored as 1.2 kanal is 24 marla; the title says 22."""
    result = clean.resolve_area("1 Kanal 2 Marla House for Sale in Testville", 1.2, "kanal")
    assert result.area_marla == 22.0
    assert result.source == "title"
    assert "area_title_compound" in result.flags


def test_payload_wins_on_a_sub_marla_quantity_gap():
    """D-32 as reversed: the payload is measured, the title is rounded for the advert.

    This is the assertion that fails if anyone restores the original rule, which took the
    title here and destroyed the more precise figure on 17 rows.
    """
    result = clean.resolve_area("2.5 Marla House for Sale in Testville", 2.52, "marla")
    assert result.area_marla == pytest.approx(2.52)
    assert result.source == "payload"
    assert result.flags == ("area_title_rounded",)


def test_payload_wins_on_a_large_quantity_gap_but_the_row_is_flagged():
    result = clean.resolve_area("5 Marla House for Sale in Testville", 15.0, "marla")
    assert result.area_marla == 15.0
    assert result.source == "payload"
    assert result.flags == ("area_quantity_conflict",)


def test_the_rounding_boundary_is_one_marla():
    """Just under a marla is rounding; a marla or more cannot be."""
    rounded = clean.resolve_area("12 Marla House for Sale in Testville", 11.45, "marla")
    conflict = clean.resolve_area("12 Marla House for Sale in Testville", 11.0, "marla")
    assert rounded.flags == ("area_title_rounded",)
    assert conflict.flags == ("area_quantity_conflict",)


def test_area_recovered_from_the_title_when_the_payload_has_none():
    result = clean.resolve_area("3 Marla House for Sale in Testville", None, "kanal")
    assert result.area_marla == 3.0
    assert result.source == "title_recovered"


def test_no_title_evidence_leaves_the_payload_unchallenged_but_flagged():
    result = clean.resolve_area("House for Sale in Testville", 5.0, "marla")
    assert result.source == "payload"
    assert result.flags == ("area_no_title_evidence",)


def test_neither_source_has_an_area():
    result = clean.resolve_area("House for Sale in Testville", None, None)
    assert result.area_marla is None
    assert result.source == "unresolved"


def test_add_area_marla_never_touches_the_source_columns():
    """B-12: the conversion must stay auditable, so `area` and `area_unit` survive intact."""
    original = frame(row(title="2 Kanal House for Sale in Testville", area=2.0, area_unit="marla"))
    result, report = clean.add_area_marla(original)
    assert result["area"].iloc[0] == 2.0
    assert result["area_unit"].iloc[0] == "marla"
    assert result["area_marla"].iloc[0] == 40.0
    assert report.counts["  unit wrong at source (B-15)"] == 1


# --------------------------------------------------------------------------------------
# Manual corrections — D-46
# --------------------------------------------------------------------------------------


def test_manual_correction_sets_a_derived_column_and_flags_the_row(monkeypatch):
    monkeypatch.setattr(
        clean,
        "MANUAL_CORRECTIONS",
        (clean.ManualCorrection(900001, "area_marla", 42.0, "invented, for the test"),),
    )
    original = frame(row(property_id=900001))
    original["area_marla"] = 2.1
    original["clean_flags"] = ""
    result, report = clean.apply_manual_corrections(original)
    assert result["area_marla"].iloc[0] == 42.0
    assert result["area"].iloc[0] == 5.0  # the source column is untouched
    assert "manual_correction" in result["clean_flags"].iloc[0]
    assert report.counts["corrections applied"] == 1


def test_a_correction_for_a_missing_listing_is_reported_not_ignored(monkeypatch):
    """A stale entry must be visible. Silence here is how a correction rots unnoticed."""
    monkeypatch.setattr(
        clean,
        "MANUAL_CORRECTIONS",
        (clean.ManualCorrection(111111, "area_marla", 42.0, "invented, for the test"),),
    )
    original = frame(row(property_id=900001))
    original["area_marla"] = 5.0
    _, report = clean.apply_manual_corrections(original)
    assert report.counts["listing not found — REVIEW"] == 1
    assert report.counts["corrections applied"] == 0


def test_every_shipped_correction_carries_a_reason():
    for correction in clean.MANUAL_CORRECTIONS:
        assert correction.reason.strip(), f"{correction.property_id} has no reason"


# --------------------------------------------------------------------------------------
# Coordinates — D-33
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("lat", "lon", "expected"),
    [
        (31.45, 74.35, True),
        (24.86, 67.01, False),  # Karachi
        (33.62, 73.05, False),  # Islamabad
        (None, 74.35, None),
        (31.45, None, None),
        (float("nan"), 74.35, None),
    ],
)
def test_in_lahore(lat, lon, expected):
    assert clean.in_lahore(lat, lon) is expected


def test_outside_lahore_and_missing_are_distinguishable():
    """Both end up with a null coordinate, but they are not the same fact."""
    original = frame(
        row(latitude=31.45, longitude=74.35),
        row(latitude=24.86, longitude=67.01),
        row(latitude=None, longitude=None),
    )
    result, report = clean.add_clean_coordinates(original)
    assert list(result["coord_source"]) == ["source", "out_of_lahore_nulled", "missing"]
    assert result["latitude_clean"].isna().sum() == 2
    assert report.counts["outside Lahore — nulled"] == 1


def test_a_nulled_coordinate_leaves_the_source_columns_intact():
    original = frame(row(latitude=24.86, longitude=67.01))
    result, _ = clean.add_clean_coordinates(original)
    assert result["latitude"].iloc[0] == 24.86
    assert pd.isna(result["latitude_clean"].iloc[0])


def test_multan_road_is_a_lahore_road_not_the_city_of_multan():
    """The negative lookahead in the city regex. Without it, 26 real listings are excluded."""
    assert clean.names_other_city("5 Marla House for Sale on Multan Road, Lahore") is False
    assert clean.names_other_city("5 Marla House for Sale in Wapda Town, Multan") is True


@pytest.mark.parametrize(
    "text",
    ["House in Bahria Town, Karachi", "House in DHA Islamabad", "House in Wapda Town, Gujranwala"],
)
def test_other_cities_are_recognised(text):
    assert clean.names_other_city(text) is True


# --------------------------------------------------------------------------------------
# Exclusions — D-34, D-35
# --------------------------------------------------------------------------------------


def _exclusions(*rows: dict[str, object]) -> pd.DataFrame:
    """Run the pipeline up to and including the exclusion step."""
    result, _ = clean.add_area_marla(frame(*rows))
    result, _ = clean.add_clean_coordinates(result)
    result, _ = clean.apply_exclusions(result)
    return result


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"title": "1200 Sq.ft Penthouse for Sale in Testville"}, "excl_penthouse"),
        ({"title": "5 Marla House for Sale (First Floor) in Testville"}, "excl_floor_sale"),
        ({"title": "5 Marla House for Sale (Ground Floor) in Testville"}, "excl_floor_sale"),
        ({"price": None}, "excl_no_price"),
        ({"bedrooms": 0}, "excl_zero_rooms"),
        ({"bathrooms": 0}, "excl_zero_rooms"),
        ({"bedrooms": 41}, "excl_impossible_beds"),
    ],
)
def test_each_exclusion_rule_fires_with_its_own_reason(overrides, reason):
    result = _exclusions(row(**overrides))
    assert result["excluded"].iloc[0]
    assert reason in result["exclusion_reason"].iloc[0]


def test_a_row_in_another_city_needs_both_the_title_and_the_coordinates_to_agree():
    both = _exclusions(
        row(title="10 Marla House for Sale in Wapda Town, Multan", latitude=30.19, longitude=71.47)
    )
    title_only = _exclusions(
        row(title="1 Kanal House for Sale in DHA Karachi", latitude=31.47, longitude=74.44)
    )
    assert both["excluded"].iloc[0]
    assert not title_only["excluded"].iloc[0], "a title typo is not evidence the house moved"


def test_seven_bedrooms_on_ten_marla_is_normal_in_lahore():
    """Houses here go up, not out. A rule tied to floor area fired on 73 legitimate rows."""
    result = _exclusions(row(bedrooms=7, bathrooms=6, area=10.0, area_unit="marla"))
    assert not result["excluded"].iloc[0]


def test_a_row_can_carry_several_reasons_and_is_counted_once():
    result = _exclusions(row(title="1200 Sq.ft Penthouse for Sale in Testville", bedrooms=0))
    reasons = result["exclusion_reason"].iloc[0].split(";")
    assert set(reasons) == {"excl_penthouse", "excl_zero_rooms"}
    assert int(result["excluded"].sum()) == 1


def test_exclusions_flag_but_never_remove():
    """PLAN §6: the reconciliation must come from one table, not a difference between two."""
    original = frame(row(), row(bedrooms=0), row(price=None))
    result = _exclusions(row(), row(bedrooms=0), row(price=None))
    assert len(result) == len(original) == 3
    assert int(result["excluded"].sum()) == 2


# --------------------------------------------------------------------------------------
# Locality — D-40, D-41
# --------------------------------------------------------------------------------------


def test_address_decomposes_into_its_tiers():
    parsed = clean.parse_address_path(
        "Block EE, Phase 4, Testville, Lahore, Punjab, Pakistan", "Testville"
    )
    assert parsed["loc_society"] == "Testville"
    assert parsed["loc_phase"] == "Phase 4"
    assert parsed["loc_phase_num"] == 4
    assert parsed["loc_block"] == "Block EE"
    assert parsed["loc_path"] == "Testville > Phase 4 > Block EE"


def test_a_sector_tier_is_recognised_separately_from_a_block():
    parsed = clean.parse_address_path(
        "Jinnah Block, Sector C, Testville, Lahore, Pakistan", "Testville"
    )
    assert parsed["loc_sector"] == "Sector C"
    assert parsed["loc_block"] == "Jinnah Block"


def test_an_address_with_no_sub_tier():
    parsed = clean.parse_address_path("Testville,Lahore, Pakistan", "Testville")
    assert parsed["loc_phase"] is None
    assert parsed["loc_block"] is None
    assert parsed["loc_path"] == "Testville"


def test_a_named_sub_society_lands_in_loc_sub():
    parsed = clean.parse_address_path("Greenfields, Testville, Lahore, Pakistan", "Testville")
    assert parsed["loc_sub"] == "Greenfields"


def test_a_missing_locality_does_not_crash_the_path_builder():
    parsed = clean.parse_address_path("Lahore, Pakistan", None)
    assert parsed["loc_society"] is None
    assert parsed["loc_path"] is None


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Phase 6", 6),
        ("Phase XII (EME)", 12),
        ("Phase 9 - Town", 9),
        ("Rahbar - Phase 2", 2),
        (None, None),
        ("Block E", None),
    ],
)
def test_phase_number_reads_arabic_and_roman(label, expected):
    assert clean.phase_number(label) == expected


def test_locality_spelling_variants_collapse():
    assert clean.canonical_locality("Highcourt Society") == "High Court Society"
    assert clean.canonical_locality("Sabzazar") == "Sabzazar Scheme"


def test_an_unknown_locality_passes_through_untouched():
    assert clean.canonical_locality("Testville") == "Testville"


def test_separate_developments_are_not_merged():
    """"Al-Kabir Town" is not "Al-Kabir Orchard"; "Sher Shah Road" is not the Colony."""
    assert clean.canonical_locality("Al-Kabir Town") == "Al-Kabir Town"
    assert clean.canonical_locality("Sher Shah Road") == "Sher Shah Road"


# --------------------------------------------------------------------------------------
# Fingerprint, junk and collapse — D-43, D-44, D-45
# --------------------------------------------------------------------------------------


def _through_fingerprint(*rows: dict[str, object]) -> pd.DataFrame:
    result, _ = clean.add_area_marla(frame(*rows))
    result, _ = clean.add_clean_coordinates(result)
    result, _ = clean.apply_exclusions(result)
    result, _ = clean.add_locality_parts(result)
    result, _ = clean.add_fingerprint(result)
    return result


def test_identical_listings_share_a_fingerprint_and_distinct_ones_do_not():
    result = _through_fingerprint(
        row(price=20_000_000.0),
        row(price=21_000_000.0),
        row(price=30_000_000.0, bedrooms=6),
    )
    assert list(result["n_listings"]) == [2, 2, 1]


def test_an_excluded_row_never_joins_a_group():
    """It must not pull a group median it is about to be dropped from."""
    result = _through_fingerprint(
        row(price=20_000_000.0), row(price=21_000_000.0), row(price=1.0, bedrooms=0)
    )
    assert pd.isna(result["n_listings"].iloc[2])
    assert result["fp_price_median"].iloc[0] == 20_500_000.0


def test_junk_prices_are_excluded_at_both_ends():
    result = _through_fingerprint(
        row(price=18_000_000.0),
        row(price=40_000.0, property_id=900050),
        row(price=900_000_000.0, property_id=900051),
    )
    result, report = clean.flag_price_junk(result)
    assert report.counts["price per marla outside the band"] == 2
    assert not result["excluded"].iloc[0]
    assert result["excluded"].iloc[1] and result["excluded"].iloc[2]


def test_an_impossible_area_is_excluded():
    result = _through_fingerprint(row(area=0.2, area_unit="marla", price=11_500_000.0))
    result, report = clean.flag_price_junk(result)
    assert report.counts["area physically impossible"] == 1


def test_the_group_guard_catches_a_junk_price_inside_a_pair():
    """The n=2 median trap. Left in, [100k, 18.5M] collapses to 9.3M — a fabricated price."""
    result = _through_fingerprint(row(price=18_500_000.0), row(price=100_000.0))
    result, _ = clean.flag_price_junk(result)
    assert clean.has_flag(result["clean_flags"], "excl_price_group_outlier").iloc[1]
    assert not result["excluded"].iloc[0]


def test_junk_must_be_removed_before_the_collapse_not_after():
    """Ordering, asserted directly: run them the wrong way round and the median is poisoned."""
    result = _through_fingerprint(row(price=18_500_000.0), row(price=100_000.0))
    right_way, _ = clean.flag_price_junk(result)
    right_way, _ = clean.collapse_groups(right_way)
    survivor = right_way[~right_way["excluded"] & ~right_way["collapsed"]]
    assert len(survivor) == 1
    assert survivor["price"].iloc[0] == 18_500_000.0

    wrong_way, _ = clean.collapse_groups(result)
    poisoned = wrong_way[~wrong_way["excluded"] & ~wrong_way["collapsed"]]
    assert poisoned["price"].iloc[0] == 9_300_000.0, "this is the failure the ordering prevents"


def test_a_group_collapses_to_one_row_at_the_median_price():
    result = _through_fingerprint(
        row(price=20_000_000.0), row(price=21_000_000.0), row(price=25_000_000.0)
    )
    result, _ = clean.flag_price_junk(result)
    result, report = clean.collapse_groups(result)
    survivor = result[~result["excluded"] & ~result["collapsed"]]
    assert len(survivor) == 1
    assert survivor["price"].iloc[0] == 21_000_000.0  # median, not mean (22M)
    assert survivor["n_listings"].iloc[0] == 3
    assert report.counts["rows folded into a survivor"] == 2


def test_excluded_rows_are_never_collapsed():
    """The excluded file keeps every dropped listing individually, not a summary of them."""
    result = _through_fingerprint(
        row(price=20_000_000.0),
        row(bedrooms=0, price=1_000_000.0),
        row(bedrooms=0, price=2_000_000.0),
    )
    result, _ = clean.flag_price_junk(result)
    result, _ = clean.collapse_groups(result)
    assert int(result["excluded"].sum()) == 2


def test_dha_rahbar_resolves_to_phase_11_and_keeps_its_own_phase():
    """B-18: DHA Rahbar is DHA Phase 11 and numbers its own phases inside it."""
    parsed = clean.parse_address_path("Rahbar - Phase 2, DHA, Lahore, Punjab, Pakistan", "DHA")
    assert parsed["loc_phase"] == "Phase 11 - Rahbar"
    assert parsed["loc_phase_num"] == 11, "2 is Rahbar's own phase, not DHA's"
    assert parsed["loc_sub"] == "Phase 2", "the internal phase is kept, not discarded"
    assert parsed["loc_path"] == "DHA > Phase 11 - Rahbar"


def test_the_two_rahbar_spellings_land_on_one_place():
    a = clean.parse_address_path("Rahbar - Phase 1, DHA, Lahore", "DHA")
    b = clean.parse_address_path("Phase 11 - Rahbar, DHA, Lahore", "DHA")
    assert a["loc_phase"] == b["loc_phase"] == "Phase 11 - Rahbar"
    assert a["loc_phase_num"] == b["loc_phase_num"] == 11
    assert a["loc_sub"] == "Phase 1"
    assert b["loc_sub"] is None, "Phase 11 states DHA's phase, so there is no internal one"


def test_rahbar_written_without_the_word_phase_is_still_caught():
    """Not in the current corpus. The branch exists so a re-scrape cannot file it silently."""
    parsed = clean.parse_address_path("Rahbar, DHA, Lahore", "DHA")
    assert parsed["loc_phase"] == "Phase 11 - Rahbar"
    assert parsed["loc_sub"] is None


def test_an_ordinary_dha_phase_is_untouched():
    parsed = clean.parse_address_path("Block EE, Phase 6, DHA, Lahore", "DHA")
    assert parsed["loc_phase"] == "Phase 6"
    assert parsed["loc_phase_num"] == 6
    assert parsed["loc_block"] == "Block EE"
    assert parsed["loc_sub"] is None


def test_rahbar_outside_dha_is_not_rewritten():
    """The mapping is keyed on the parent society, not on the word alone."""
    parsed = clean.parse_address_path("Rahbar - Phase 2, Testville, Lahore", "Testville")
    assert parsed["loc_phase"] == "Rahbar - Phase 2"
    assert parsed["loc_phase_num"] == 2


# --------------------------------------------------------------------------------------
# Columns and schema — D-37, D-39
# --------------------------------------------------------------------------------------


def test_zero_variance_columns_are_dropped_and_varying_ones_are_not():
    original = frame(row(), row(is_featured=True))
    original["excluded"] = False
    result, report = clean.drop_zero_variance(original)
    assert "condition" not in result.columns
    assert "is_featured" in result.columns, "13 True out of 8,459 is variance, not noise"
    assert report.counts["listed but NOT single-valued — KEPT"] == 0


def test_a_listed_column_that_turns_out_to_vary_is_kept_and_reported():
    original = frame(row(condition="New"), row(condition="Renovated"))
    original["excluded"] = False
    result, report = clean.drop_zero_variance(original)
    assert "condition" in result.columns
    assert report.counts["listed but NOT single-valued — KEPT"] == 1


def test_an_unlisted_single_valued_column_is_reported_not_dropped():
    original = frame(row(), row())
    original["excluded"] = False
    original["surprise"] = "always the same"
    result, report = clean.drop_zero_variance(original)
    assert "surprise" in result.columns
    assert "  surprise is single-valued" in report.counts


def test_variance_is_measured_over_every_row_not_the_analysis_set():
    """On the analysis set `excluded` is constant by construction, and would be dropped."""
    original = frame(row(), row())
    original["excluded"] = [False, True]
    original["exclusion_reason"] = ["", "excl_zero_rooms"]
    result, report = clean.drop_zero_variance(original)
    assert "excluded" in result.columns
    assert "exclusion_reason" in result.columns
    assert "  excluded is single-valued" not in report.counts
    assert "  exclusion_reason is single-valued" not in report.counts


def test_the_schema_types_created_at_as_a_real_datetime():
    """B-03's recency holdout sorts on this. Left as text it sorts lexically and looks fine."""
    original = _schema_shaped_frame()
    original["created_at"] = "2024-01-15T09:00:00.000Z"
    result, _ = clean.apply_schema(original)
    assert str(result["created_at"].dtype) == "datetime64[ns, UTC]"


def _schema_shaped_frame() -> pd.DataFrame:
    """A frame carrying exactly the schema's columns, so nothing else counts as unknown."""
    original = frame(row())
    for column in clean.SCHEMA:
        if column not in original.columns:
            original[column] = None
    original["excluded"] = False
    original["collapsed"] = False
    return original[[c for c in clean.SCHEMA]]


def test_a_column_outside_the_schema_is_reported_rather_than_shipped_untyped():
    original = _schema_shaped_frame()
    original["undeclared"] = 1
    _, report = clean.apply_schema(original)
    assert report.counts["in frame but not in schema — REVIEW"] == 1
    assert "  untyped: undeclared" in report.counts


def test_a_schema_column_missing_from_the_frame_is_reported_too():
    original = _schema_shaped_frame().drop(columns=["views"])
    _, report = clean.apply_schema(original)
    assert report.counts["in schema but not in frame — REVIEW"] == 1


# --------------------------------------------------------------------------------------
# Flags
# --------------------------------------------------------------------------------------


def test_has_flag_matches_whole_flags_only():
    flags = pd.Series(["area_corrected_from_title;coord_missing", "area_corrected", ""])
    assert list(clean.has_flag(flags, "area_corrected")) == [False, True, False]


def test_flags_accumulate_across_steps_without_duplicating():
    original = frame(
        row(
            title="2 Kanal House for Sale in Testville",
            area=2.0,
            area_unit="marla",
            latitude=24.86,
            longitude=67.01,
        )
    )
    result, _ = clean.add_area_marla(original)
    result, _ = clean.add_clean_coordinates(result)
    flags = result["clean_flags"].iloc[0].split(";")
    assert "area_corrected_from_title" in flags
    assert "coord_out_of_lahore" in flags
    assert len(flags) == len(set(flags))


# --------------------------------------------------------------------------------------
# Whole pipeline and artefacts
# --------------------------------------------------------------------------------------


def test_the_pipeline_reconciles_end_to_end(interim_file):
    rows = [row(property_id=900001 + i, price=18_000_000.0 + i * 100_000) for i in range(6)]
    rows.append(row(property_id=900100, bedrooms=0))  # excluded
    rows.append(row(property_id=900101, title="1200 Sq.ft Penthouse in Testville"))  # excluded
    path = interim_file(rows)

    result, reports = clean.run_cleaning(path)
    analysis = result[~result["excluded"] & ~result["collapsed"]]
    folded = result[~result["excluded"] & result["collapsed"]]
    excluded = result[result["excluded"]]

    assert len(analysis) + len(folded) + len(excluded) == len(result)
    assert len(excluded) == 2
    assert len(analysis) == 1, "six identical listings collapse to one row"
    assert len(folded) == 5, "the other five are marked, not deleted (D-53)"
    assert analysis["n_listings"].iloc[0] == 6
    assert [r.step for r in reports][0].startswith("area")
    assert all(r.rows_in >= r.rows_out for r in reports)


def test_out_of_scope_rows_never_enter_the_pipeline(interim_file):
    """Stage 1's verdict is not re-litigated here."""
    path = interim_file(
        [row(property_id=900001), row(property_id=900002, in_scope=False, scope_reason="type=Land")]
    )
    result, _ = clean.run_cleaning(path)
    assert 900002 not in set(result["property_id"])


def test_write_processed_splits_without_losing_a_row(tmp_path, interim_file):
    path = interim_file(
        [
            row(property_id=900001),
            row(property_id=900002, bedrooms=0),
            row(property_id=900003, bedrooms=5),
        ]
    )
    result, _ = clean.run_cleaning(path)
    written = clean.write_processed(result, str(tmp_path))

    kept = pd.read_parquet(tmp_path / "listings.parquet")
    dropped = pd.read_parquet(tmp_path / "listings_excluded.parquet")
    folded = result[~result["excluded"] & result["collapsed"]]
    assert len(kept) + len(dropped) + len(folded) == len(result)
    assert not kept["excluded"].any()
    assert not kept["collapsed"].any()
    assert dropped["excluded"].all()
    assert dropped["exclusion_reason"].str.len().gt(0).all()
    assert set(written) == {"listings", "listings_excluded", "listings_members"}


def test_the_processed_table_round_trips_through_parquet_unchanged(tmp_path, interim_file):
    """The whole justification for D-36 is that parquet preserves what it is handed."""
    path = interim_file([row(property_id=900001 + i, bedrooms=3 + i) for i in range(4)])
    result, _ = clean.run_cleaning(path)
    clean.write_processed(result, str(tmp_path))
    kept = result[~result["excluded"] & ~result["collapsed"]].reset_index(drop=True)
    back = clean.read_processed(str(tmp_path / "listings.parquet"))
    assert (back.dtypes == kept.dtypes).all()
    assert back.equals(kept)


def test_an_all_null_category_survives_a_round_trip_through_read_processed(tmp_path, interim_file):
    """Parquet hands an all-null category back as `object`. `read_processed` re-types it.

    Reading with `pd.read_parquet` directly is what fails here, which is why the pipeline
    does not.
    """
    path = interim_file([row(property_id=900001 + i, bedrooms=3 + i) for i in range(4)])
    result, _ = clean.run_cleaning(path)
    assert result["loc_phase"].isna().all(), "fixture must produce an all-null category"
    clean.write_processed(result, str(tmp_path))

    naive = pd.read_parquet(tmp_path / "listings.parquet")
    assert str(naive["loc_phase"].dtype) == "object"

    typed = clean.read_processed(str(tmp_path / "listings.parquet"))
    assert str(typed["loc_phase"].dtype) == "category"


def test_a_folded_row_keeps_its_own_price_while_the_survivor_takes_the_median(interim_file):
    """D-48 scores against the price each poster actually set, so it must survive intact."""
    prices = [20_000_000.0, 21_000_000.0, 25_000_000.0]
    path = interim_file([row(property_id=900001 + i, price=p) for i, p in enumerate(prices)])
    result, _ = clean.run_cleaning(path)

    survivor = result[~result["excluded"] & ~result["collapsed"]]
    folded = result[~result["excluded"] & result["collapsed"]]
    assert len(survivor) == 1
    assert survivor["price"].iloc[0] == 21_000_000.0, "survivor carries the group median"
    assert survivor["price_listed"].iloc[0] == 20_000_000.0, "its own asking price survives"
    assert sorted(folded["price_listed"]) == [21_000_000.0, 25_000_000.0]
    assert set(folded["fp_group_id"]) == set(survivor["fp_group_id"])
    # The whole point of the artefact: all three posted prices are still recoverable.
    analysis = result[~result["excluded"]]
    assert sorted(analysis["price_listed"]) == prices


def test_the_members_artefact_expands_every_analysis_row_into_its_listings(tmp_path,
                                                                          interim_file):
    """The stage 6 join: one analysis row, one group, every listing it stood for."""
    rows = [row(property_id=900001 + i, price=20_000_000.0 + i * 500_000) for i in range(4)]
    rows.append(row(property_id=900100, bedrooms=6))          # its own group
    rows.append(row(property_id=900101, bedrooms=0))          # excluded, never a member
    path = interim_file(rows)

    result, _ = clean.run_cleaning(path)
    clean.write_processed(result, str(tmp_path))
    kept = pd.read_parquet(tmp_path / "listings.parquet")
    members = pd.read_parquet(tmp_path / "listings_members.parquet")

    assert list(members.columns) == list(clean.MEMBER_COLUMNS)
    assert sorted(members["price_listed"]) == [
        18_000_000.0,   # the lone bedrooms=6 listing, its own group of one
        20_000_000.0, 20_500_000.0, 21_000_000.0, 21_500_000.0,   # the group of four
    ]
    assert len(members) == 5, "every pre-collapse analysis listing, excluded rows aside"
    assert 900101 not in set(members["property_id"])
    assert members["fp_group_id"].nunique() == len(kept)
    assert set(kept["fp_group_id"]) == set(members["fp_group_id"])
    sizes = members.groupby("fp_group_id").size()
    assert sizes.to_dict() == kept.set_index("fp_group_id")["n_listings"].to_dict()


def test_analysis_rows_counts_neither_excluded_nor_collapsed(interim_file):
    path = interim_file([row(property_id=900001 + i) for i in range(3)])
    result, _ = clean.run_cleaning(path)
    assert clean.analysis_rows(result) == 1
    assert len(result) == 3, "the other two are still in the frame"


# --------------------------------------------------------------------------------------
# Synthetic sample — D-23
# --------------------------------------------------------------------------------------


def test_the_sample_matches_the_processed_schema(interim_file):
    path = interim_file([row(property_id=900001 + i, bedrooms=3 + i % 4) for i in range(30)])
    result, _ = clean.run_cleaning(path)
    sample = clean.synthesise_sample(result, n_rows=25)
    assert list(sample.columns) == list(clean.SCHEMA)
    assert len(sample) == 25


def test_the_sample_reproduces_no_real_listing(interim_file):
    """D-23: Ilaan publishes no licence, so nothing of theirs is republished."""
    path = interim_file([row(property_id=900001 + i, bedrooms=3 + i % 4) for i in range(30)])
    result, _ = clean.run_cleaning(path)
    sample = clean.synthesise_sample(result, n_rows=40)
    real = result[~result["excluded"]]
    real_keys = set(zip(real["title"].astype(str), real["price"], strict=True))
    assert not [k for k in zip(sample["title"].astype(str), sample["price"], strict=True)
                if k in real_keys]
    assert not set(sample["property_id"]) & set(result["property_id"])


def test_the_sample_is_reproducible_so_its_diff_is_empty_on_a_re_run(interim_file):
    path = interim_file([row(property_id=900001 + i, bedrooms=3 + i % 4) for i in range(30)])
    result, _ = clean.run_cleaning(path)
    assert clean.synthesise_sample(result, 20).equals(clean.synthesise_sample(result, 20))


def test_the_sample_carries_no_null_price_or_area(interim_file):
    path = interim_file([row(property_id=900001 + i, bedrooms=3 + i % 4) for i in range(30)])
    result, _ = clean.run_cleaning(path)
    sample = clean.synthesise_sample(result, n_rows=30)
    assert sample["price"].notna().all()
    assert sample["area_marla"].notna().all()
    assert (sample["area_marla"] > 0).all()


# --------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------


def test_the_report_carries_both_row_counts():
    report = clean.StepReport("test", 100, 100, 100, 90, {"something": 10})
    rendered = report.to_markdown()
    assert "rows 100 → 100" in rendered
    assert "analysis set 100 → 90" in rendered


def test_the_reconciliation_file_is_written_from_the_run(tmp_path, interim_file):
    path = interim_file([row(property_id=900001), row(property_id=900002, bedrooms=0)])
    _, reports = clean.run_cleaning(path)
    target = clean.write_reconciliation(reports, str(tmp_path / "reports" / "recon.md"))
    text = open(target, encoding="utf-8").read()
    assert "Stage 2 — cleaning reconciliation" in text
    assert "exclusions" in text


# --------------------------------------------------------------------------------------
# Constants that encode a decision
# --------------------------------------------------------------------------------------


def test_the_marla_conversion_table_is_internally_consistent_except_where_it_says_so():
    """225 sq ft to the marla, 20 marla to the kanal, 25 sq yd to the marla (D-31)."""
    assert clean.MARLA_PER_UNIT["kanal"] == 20.0
    assert clean.to_marla(4500, "square feet") == pytest.approx(20.0)  # 1 kanal
    assert clean.to_marla(500, "square yard") == pytest.approx(20.0)  # 1 kanal
    # The acre is the documented inconsistency: 160 marla by convention, 193.6 at 225 sq ft.
    assert clean.MARLA_PER_UNIT["acreage"] == 160.0
    assert 43560 / 225 == pytest.approx(193.6)


def test_the_lahore_box_contains_the_city_and_excludes_the_other_metros():
    lat_min, lat_max, lon_min, lon_max = clean.LAHORE_BBOX
    assert lat_min < 31.52 < lat_max and lon_min < 74.35 < lon_max  # central Lahore
    assert not (lat_min <= 24.86 <= lat_max)  # Karachi
    assert not (lat_min <= 33.68 <= lat_max)  # Islamabad
    assert not (lon_min <= 71.47 <= lon_max)  # Multan


def test_the_fingerprint_uses_the_cleaned_coordinate_not_the_raw_one():
    """A coordinate D-33 nulled must not come back in through the grouping key."""
    assert "latitude_clean" in clean.FINGERPRINT_COLUMNS
    assert "latitude" not in clean.FINGERPRINT_COLUMNS


def test_the_manual_corrections_table_stays_small():
    """D-46: past a handful of entries, a rule is missing rather than the table working."""
    assert len(clean.MANUAL_CORRECTIONS) <= 5


def test_the_fingerprint_report_counts_rows_not_the_sum_of_group_sizes():
    """`sizes` is a per-row transform; summing it returns the sum of squares, not a row count.

    The first version reported 18,905 rows in multi-listing groups out of an analysis set of
    8,358 — a number larger than the data, in a file that ships as a deliverable.
    """
    result = _through_fingerprint(
        row(price=20_000_000.0),
        row(price=21_000_000.0),
        row(price=22_000_000.0),
        row(price=30_000_000.0, bedrooms=6),
    )
    _, report = clean.add_fingerprint(result.drop(columns=[
        "fp_group_id", "n_listings", "fp_price_median", "fp_price_spread"
    ]))
    assert report.counts["rows in multi-listing groups"] == 3
    assert report.counts["  of which hold more than one listing"] == 1
    assert report.counts["rows in multi-listing groups"] <= report.analysis_out


def test_the_one_date_statistic_excludes_singletons():
    """A singleton group is posted on one date by definition; counting it says nothing."""
    result = _through_fingerprint(row(price=20_000_000.0), row(price=30_000_000.0, bedrooms=6))
    _, report = clean.add_fingerprint(result.drop(columns=[
        "fp_group_id", "n_listings", "fp_price_median", "fp_price_spread"
    ]))
    assert report.counts["multi-listing groups posted entirely on one date"] == 0
