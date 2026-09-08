"""Stage 2 cleaning: turn parsed listings into an analysis-ready table.

Reads ``data/interim/listings.jsonl`` and applies the corrections agreed in
``project-log/decisions/03-cleaning.md``. Raw is never touched and every step is
rerunnable from interim.

Three rules govern everything in this module.

* **Nothing is overwritten.** A correction lands in a NEW column beside the source
  value, so a wrong conversion factor stays detectable after the fact (B-12).
* **Nothing is dropped silently.** Rows that fail a rule are flagged with a reason and
  counted; the caller decides whether to exclude them (PLAN §6).
* **Every transformation is countable.** Each step returns a :class:`StepReport` so the
  reconciliation in ``reports/`` is derived from the run, not written by hand.

The stage 2 pipeline, in order. ``run_cleaning`` runs all of it.

1.  B-15 / D-32 — reconcile ``area`` and ``area_unit`` against the listing title.
2.  B-12 / D-31 — convert the reconciled area to marla in a new ``area_marla`` column.
2b. D-46 — apply the hand-made corrections table, before anything groups or judges.
3.  D-33 — null coordinates that fall outside Lahore; never impute one.
4.  D-34, D-35 — flag rows that leave the analysis set, each with a reason.
5.  B-08 / B-10 — decompose the locality hierarchy; canonicalise locality spellings.
6.  B-07 / D-43 — build the dedup fingerprint.
7.  B-09 / D-44 — flag price junk. Before the collapse, never after.
8.  D-45 — collapse each fingerprint group to one row at the median price.
9.  D-37 — drop columns that hold one value, verifying each before it goes.
10. D-39 — cast every surviving column to a declared type.

``write_processed`` then splits the result into the analysis set and the excluded rows
(D-42), writing each as parquet and as a CSV view.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import pandas as pd

# --------------------------------------------------------------------------------------
# Unit vocabulary
# --------------------------------------------------------------------------------------

#: Marla per unit. 1 marla = 225 sq ft = 25 sq yd, the convention used by DHA and the
#: post-1970s societies that make up most of this sample (D-31).
#:
#: The acre factor is the one inconsistency in this table and it is deliberate. Pakistani
#: land convention puts 1 acre = 8 kanal = 160 marla, which implies a 272.25 sq ft marla.
#: At 225 sq ft an acre is 43,560 / 225 = 193.6 marla. Both cannot be true at once. 160 is
#: kept because it is what an acre means in a Pakistani listing, and the disagreement is
#: recorded here rather than hidden. In practice the factor never fires: the single row
#: carrying ``area_unit="acreage"`` is a title mismatch that resolves to marla.
MARLA_PER_UNIT: dict[str, float] = {
    "marla": 1.0,
    "kanal": 20.0,
    "square feet": 1.0 / 225.0,
    "square yard": 1.0 / 25.0,
    "acreage": 160.0,
}

#: Maps every spelling seen in a title or in Ilaan's payload onto a key of
#: :data:`MARLA_PER_UNIT`. Keyed on the lowercased, letters-only form of the token, so
#: "Sq.ft", "sq ft" and "SQFT" all collapse to one entry.
_UNIT_ALIASES: dict[str, str] = {
    "kanal": "kanal",
    "kanals": "kanal",
    "marla": "marla",
    "marlas": "marla",
    "sqft": "square feet",
    "squarefeet": "square feet",
    "squarefoot": "square feet",
    "sqyd": "square yard",
    "squareyard": "square yard",
    "squareyards": "square yard",
    "acre": "acreage",
    "acres": "acreage",
    "acreage": "acreage",
}

#: Finds every "<number> <unit>" pair in a title. Ordered alternation matters: the longer
#: spellings must precede the shorter ones or "square feet" matches as "square" + junk.
_TITLE_AREA_RE = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>kanals?|marlas?|square\s*feet|square\s*yards?|sq\.?\s*ft\.?|sq\.?\s*yd\.?"
    r"|acres?|acreage)",
    re.IGNORECASE,
)

#: Relative tolerance when comparing a title's area to the payload's. Absorbs float noise
#: from the sq ft and sq yd divisions only — it is far tighter than any real disagreement,
#: the smallest of which is 22 marla against 24.
_AREA_REL_TOL = 1e-6

#: Marla below which a title/payload quantity disagreement is treated as the title being
#: rounded rather than as a conflict.
#:
#: The direction here was wrong in the first version of this module and the correction is
#: the point. The payload is the MORE precise of the two on quantity: measured across the
#: rows where both state an area and disagree by under a marla, the payload carries more
#: decimal places on 16 of 17 and fewer on none (``area=2.52`` against a title of
#: "2.5 Marla", ``area=11.45`` against "12 Marla"). 8.8% of payload areas are fractional.
#: The title is the rounded marketing figure; the payload is the plot as measured. So a
#: sub-marla gap resolves to the PAYLOAD, and a gap of a marla or more — which rounding
#: cannot explain — resolves to the payload too but is flagged for review. See D-32.
_AREA_ROUNDING_MARLA = 1.0


def canonical_unit(raw: object) -> str | None:
    """Return the canonical unit name for ``raw``, or ``None`` if it is not a unit.

    Args:
        raw: A unit string from a title or from Ilaan's payload. Anything that is not a
            string, or is a string this project has never seen, returns ``None``.

    Returns:
        A key of :data:`MARLA_PER_UNIT`, or ``None``.
    """
    if not isinstance(raw, str):
        return None
    return _UNIT_ALIASES.get(re.sub(r"[^a-z]", "", raw.lower()))


def to_marla(quantity: object, unit: object) -> float | None:
    """Convert ``quantity`` of ``unit`` to marla.

    Returns ``None`` when either input is missing or the unit is unrecognised, so a
    caller can never mistake an unconvertible value for zero.
    """
    canonical = canonical_unit(unit)
    if canonical is None or quantity is None:
        return None
    try:
        value = float(quantity)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value * MARLA_PER_UNIT[canonical]


def parse_title_area(title: object) -> list[tuple[float, str]]:
    """Extract every "<number> <unit>" pair from a listing title, in order.

    Ilaan writes compound areas as two tokens — "1 Kanal 4 Marla" — so this returns a
    list rather than a single pair. Tokens whose unit is unrecognised are discarded.

    Args:
        title: The listing title. A non-string returns an empty list.

    Returns:
        A list of ``(quantity, canonical_unit)`` pairs. Empty when the title states no
        area, which is the case on 8 of the 8,459 in-scope rows.
    """
    if not isinstance(title, str):
        return []
    found: list[tuple[float, str]] = []
    for match in _TITLE_AREA_RE.finditer(title):
        canonical = canonical_unit(match.group("unit"))
        if canonical is not None:
            found.append((float(match.group("qty")), canonical))
    return found


# --------------------------------------------------------------------------------------
# Step 1 + 2 — area reconciliation (B-15) and conversion to marla (B-12)
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AreaResolution:
    """The outcome of reconciling one row's area against its title.

    Attributes:
        area_marla: The area in marla, or ``None`` when neither source could supply one.
        source: Which evidence won — ``"payload"``, ``"title"``, ``"title_recovered"``
            (payload had no area at all) or ``"unresolved"``.
        flags: Reason codes for this row, written to the ``clean_flags`` column.
    """

    area_marla: float | None
    source: str
    flags: tuple[str, ...] = ()


def resolve_area(title: object, area: object, area_unit: object) -> AreaResolution:
    """Reconcile a row's area against its title and return the result in marla.

    Which source wins depends on what they disagree about (D-32).

    * **Unit** — the title wins. Ilaan's ``area_unit`` is wrong at source on 57 rows, in
      both directions, and the stage 1 manual audit verified the title against live pages.
    * **Compound encoding** — the title wins. On 5 rows "1 Kanal 2 Marla" was stored as the
      decimal ``1.2 kanal``; the payload collapsed two tokens into one number.
    * **Quantity** — the *payload* wins. It is the measured plot area and the title is the
      rounded marketing figure: where the two disagree by under a marla, the payload carries
      more decimal places on 16 of 17 rows and fewer on none. A gap of a marla or more is
      flagged for review but still resolves to the payload.

    The first version of this function took the title on quantity as well, on the reasoning
    that the payload rounded every area to a whole number. That was false — 8.8% of payload
    areas are fractional — and it was believed because it was read off a printout that had
    been formatted to zero decimal places. See LESSONS L-25.

    Args:
        title: The listing title.
        area: The payload's numeric area.
        area_unit: The payload's unit string.

    Returns:
        An :class:`AreaResolution`. It never raises — an unresolvable row comes back with
        ``area_marla=None`` and the ``area_unresolved`` flag, for the caller to exclude
        and count.
    """
    payload_marla = to_marla(area, area_unit)
    tokens = parse_title_area(title)

    if not tokens:
        # No title evidence. The payload stands unchallenged, which is not the same as
        # the payload being confirmed — hence the flag.
        if payload_marla is None:
            return AreaResolution(None, "unresolved", ("area_unresolved",))
        return AreaResolution(payload_marla, "payload", ("area_no_title_evidence",))

    title_marla = sum(quantity * MARLA_PER_UNIT[unit] for quantity, unit in tokens)

    if payload_marla is None:
        # The title carries an area the payload lost. Recovers 7 of the 15 rows where
        # `area` is null, which would otherwise be dropped.
        return AreaResolution(title_marla, "title_recovered", ("area_recovered_from_title",))

    if math.isclose(title_marla, payload_marla, rel_tol=_AREA_REL_TOL):
        return AreaResolution(payload_marla, "payload", ())

    # Disagreement. Which source wins depends on WHAT they disagree about, because the
    # evidence differs by field: the payload's unit is demonstrably broken and its quantity
    # is demonstrably the more precise of the two.
    if len(tokens) > 1:
        # "1 Kanal 2 Marla" encoded as the decimal 1.2 kanal — the payload read a compound
        # area as a single number. Structurally broken; the title's two tokens reconstruct
        # what it mangled.
        return AreaResolution(
            title_marla, "title", ("area_corrected_from_title", "area_title_compound")
        )

    title_qty, title_unit = tokens[0]
    if title_unit != canonical_unit(area_unit):
        # The B-15 defect proper: payload unit wrong at source, a 20x error either way,
        # verified against live pages by the stage 1 manual audit. The title wins outright
        # here, quantity included — a payload whose unit field is broken has not earned
        # partial trust in the number beside it.
        return AreaResolution(
            title_marla, "title", ("area_corrected_from_title", "area_unit_corrected")
        )

    if abs(title_marla - payload_marla) < _AREA_ROUNDING_MARLA:
        # Same unit, sub-marla gap: the title is rounded, the payload is measured. Keep the
        # payload. Flagged rather than silent because it marks every row where the two
        # sources state different areas, which EDA may want to see.
        return AreaResolution(payload_marla, "payload", ("area_title_rounded",))

    # Same unit, a marla or more apart. Rounding cannot explain it and no third source
    # exists — the cached page renders the title string and the payload number and nothing
    # further. The payload keeps precedence as the measured field; the row is flagged so it
    # is adjudicated with the distribution in view at EDA, not guessed at here.
    return AreaResolution(payload_marla, "payload", ("area_quantity_conflict",))


def analysis_rows(frame: pd.DataFrame) -> int:
    """Rows that will survive into the analysis set — everything not yet flagged excluded."""
    if "excluded" not in frame.columns:
        return len(frame)
    return int((~frame["excluded"]).sum())


@dataclass
class StepReport:
    """Counts for one cleaning step, for the run's reconciliation report.

    Two row counts are carried, not one. ``rows_*`` is every row the frame holds, excluded
    rows included, which is what the no-silent-drops arithmetic reconciles against.
    ``analysis_*`` is the set that will be modelled. Reporting only the first makes every
    step read "8,459 → 8,459" and hides the number a reader actually wants.

    Attributes:
        step: Short name, e.g. ``"area"``.
        rows_in / rows_out: Rows entering and leaving the step.
        analysis_in / analysis_out: The same, counting only rows not flagged excluded.
        counts: Named tallies, rendered as the body of the report.
    """

    step: str
    rows_in: int
    rows_out: int
    analysis_in: int
    analysis_out: int
    counts: dict[str, int] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Render the step as a markdown fragment for ``reports/``."""
        header = (
            f"rows {self.rows_in:,} → {self.rows_out:,}"
            f"   ·   analysis set {self.analysis_in:,} → {self.analysis_out:,}"
        )
        lines = [f"### {self.step}", "", header, ""]
        width = max((len(k) for k in self.counts), default=0)
        lines += [f"    {k:<{width}}  {v:>6,}" for k, v in self.counts.items()]
        return "\n".join(lines)


def add_area_marla(frame: pd.DataFrame) -> tuple[pd.DataFrame, StepReport]:
    """Add ``area_marla``, ``area_source`` and area flags. Steps 1 and 2 of stage 2.

    ``area`` and ``area_unit`` are left exactly as parsed, so the conversion stays
    auditable and a wrong factor remains detectable (B-12).

    Args:
        frame: Rows from ``data/interim/listings.jsonl``. Must carry ``title``, ``area``
            and ``area_unit``.

    Returns:
        ``(frame, report)`` where ``frame`` is a copy with three columns added and
        ``report`` carries the counts for the reconciliation.
    """
    out = frame.copy()
    resolutions = [
        resolve_area(row.title, row.area, row.area_unit)
        for row in out[["title", "area", "area_unit"]].itertuples(index=False)
    ]

    out["area_marla"] = [
        None if r.area_marla is None else round(r.area_marla, 4) for r in resolutions
    ]
    out["area_source"] = [r.source for r in resolutions]
    out["clean_flags"] = _merge_flags(out, [r.flags for r in resolutions])

    def tally(flag: str) -> int:
        return sum(1 for r in resolutions if flag in r.flags)

    counts: dict[str, int] = {
        "payload and title agree": sum(
            1 for r in resolutions if r.source == "payload" and not r.flags
        ),
        "no area stated in title": tally("area_no_title_evidence"),
        "title preferred over payload": sum(1 for r in resolutions if r.source == "title"),
        "  unit wrong at source (B-15)": tally("area_unit_corrected"),
        "  compound title mis-encoded": tally("area_title_compound"),
        "payload kept over a disagreeing title": tally("area_title_rounded")
        + tally("area_quantity_conflict"),
        "  title rounded, payload measured": tally("area_title_rounded"),
        "  quantity conflict — REVIEW": tally("area_quantity_conflict"),
        "recovered from title (payload had none)": sum(
            1 for r in resolutions if r.source == "title_recovered"
        ),
        "unresolved (flagged for exclusion)": sum(
            1 for r in resolutions if r.source == "unresolved"
        ),
    }
    return out, StepReport(
        "area — B-15 reconciliation, B-12 conversion",
        len(frame), len(out), analysis_rows(frame), analysis_rows(out), counts,
    )


def _merge_flags(frame: pd.DataFrame, new_flags: list[tuple[str, ...]]) -> list[str]:
    """Append ``new_flags`` to any ``clean_flags`` already on the frame.

    Flags are stored as a ``;``-delimited string rather than a list so the column
    survives a CSV round-trip unchanged. Use :func:`has_flag` to filter on them.
    """
    existing = (
        frame["clean_flags"].fillna("").tolist()
        if "clean_flags" in frame.columns
        else [""] * len(frame)
    )
    merged = []
    for prior, added in zip(existing, new_flags, strict=True):
        parts = [p for p in str(prior).split(";") if p] + list(added)
        merged.append(";".join(dict.fromkeys(parts)))
    return merged


def has_flag(series: pd.Series, flag: str) -> pd.Series:
    """Return a boolean mask of rows whose ``clean_flags`` contain ``flag``.

    Matches whole flags only, so ``has_flag(df.clean_flags, "area_corrected_from_title")``
    cannot be satisfied by a longer flag that merely starts the same way.
    """
    return series.fillna("").str.split(";").apply(lambda parts: flag in parts)


def load_interim(path: str) -> pd.DataFrame:
    """Read ``listings.jsonl`` into a frame, preserving nulls as nulls.

    ``pandas.read_json`` is not used: it infers dtypes per chunk and will happily turn an
    all-integer column with one null into a float, or an empty string into NaN. Reading
    the JSON ourselves keeps the file's own distinction between "absent" and "empty",
    which several of the flags below depend on.
    """
    import json

    with open(path, encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    return pd.DataFrame.from_records(records)


# --------------------------------------------------------------------------------------
# Step 2b — manual corrections (D-46)
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ManualCorrection:
    """One hand-made correction to a derived column, with the evidence that justifies it.

    Attributes:
        property_id: The listing corrected.
        field: The DERIVED column to set. Never a source column — `area`, `area_unit`,
            `price` and the rest stay exactly as parsed, so the correction is a visible
            override rather than a rewriting of what Ilaan published.
        value: The corrected value.
        reason: Why, in enough detail that a later reader can disagree. Required.
    """

    property_id: int
    field: str
    value: object
    reason: str


#: Hand-made corrections. This table is a deliberate exception to LESSONS L-24, which says
#: cleaning effort goes on classifying defects and never on adjudicating individual rows.
#:
#: The exception is admissible only when there is a specific, statable piece of external
#: evidence that the data itself cannot contain — local knowledge, a comparable, a physical
#: impossibility — and it is recorded here with that evidence attached. It exists so such
#: corrections live in one auditable place instead of as special cases scattered through the
#: rules. If this table grows past a handful of entries, that is a signal a rule is missing,
#: not that the table is working.
MANUAL_CORRECTIONS: tuple[ManualCorrection, ...] = (
    ManualCorrection(
        property_id=684395,
        field="area_marla",
        value=42.0,
        reason=(
            "Title and payload both say '2.1 Marla' at PKR 250,000,000, which is "
            "119M per marla and impossible. Read as 2.1 kanal (42 marla) it is 5.95M per "
            "marla, against a Gulberg median of 5.53M and p75 of 7.03M in this dataset — "
            "the local comparables land on it almost exactly. No reading of the price as a "
            "typo works: 25,000,000 would still be 11.9M per marla. Against: bedrooms=2 and "
            "bathrooms=3 suit a small house rather than a 2.1 kanal one, though room counts "
            "on this source carry a demonstrated error rate (D-35). Nauman's call, 8 Sep, on "
            "knowledge of the road."
        ),
    ),
)


def apply_manual_corrections(frame: pd.DataFrame) -> tuple[pd.DataFrame, StepReport]:
    """Apply :data:`MANUAL_CORRECTIONS`, flagging each corrected row.

    Runs after the area rules and before the fingerprint, so a corrected row is grouped and
    judged on its corrected value. A correction whose listing is absent, or whose value is
    already in place, is reported rather than passed over — a stale entry should be visible.
    """
    out = frame.copy()
    applied, missing, redundant = 0, 0, 0
    flags: list[tuple[str, ...]] = [() for _ in range(len(out))]

    for correction in MANUAL_CORRECTIONS:
        match = out.index[out["property_id"] == correction.property_id]
        if len(match) == 0:
            missing += 1
            continue
        position = out.index.get_loc(match[0])
        if out.at[match[0], correction.field] == correction.value:
            redundant += 1
            continue
        out.at[match[0], correction.field] = correction.value
        flags[position] = flags[position] + ("manual_correction",)
        applied += 1

    out["clean_flags"] = _merge_flags(out, flags)
    counts = {
        "corrections applied": applied,
        "listing not found — REVIEW": missing,
        "already correct, no-op — REVIEW": redundant,
    }
    return out, StepReport(
        "manual corrections — D-46",
        len(frame), len(out), analysis_rows(frame), analysis_rows(out), counts,
    )


# --------------------------------------------------------------------------------------
# Step 3 — coordinates (D-33)
# --------------------------------------------------------------------------------------

#: Lahore bounding box as ``(lat_min, lat_max, lon_min, lon_max)``.
#:
#: Checked for sensitivity: widening or narrowing every edge by 0.05 degrees returns the
#: same 77 out-of-box rows, so nothing here depends on exactly where the box is drawn. The
#: wider box is used so a genuine fringe listing is not clipped for the sake of tidiness.
LAHORE_BBOX: tuple[float, float, float, float] = (31.15, 31.80, 73.95, 74.75)

#: Cities whose appearance in a title or address contradicts a Lahore listing.
#:
#: The negative lookahead is load-bearing. "Multan Road" is a major Lahore artery and 26
#: legitimate Lahore listings name it; without the lookahead every one of them reads as a
#: Multan property. A first pass at this rule made exactly that error.
_OTHER_CITY_RE = re.compile(
    r"\b(karachi|islamabad|rawalpindi|faisalabad|gujranwala|sialkot|peshawar|multan)\b"
    r"(?!\s*road)",
    re.IGNORECASE,
)


def in_lahore(latitude: object, longitude: object) -> bool | None:
    """Return whether a coordinate falls inside :data:`LAHORE_BBOX`.

    Returns ``None`` when either value is missing, so "outside Lahore" and "no coordinate"
    stay distinguishable — they get different treatment in :func:`add_clean_coordinates`.
    """
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    lat_min, lat_max, lon_min, lon_max = LAHORE_BBOX
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def names_other_city(*texts: object) -> bool:
    """Return whether any of ``texts`` names a Pakistani city other than Lahore."""
    return any(_OTHER_CITY_RE.search(t) for t in texts if isinstance(t, str))


def add_clean_coordinates(frame: pd.DataFrame) -> tuple[pd.DataFrame, StepReport]:
    """Add ``latitude_clean``, ``longitude_clean``, ``coord_in_lahore`` and ``coord_source``.

    A coordinate outside Lahore is nulled rather than repaired or imputed (D-33). Nulling
    is legible to every downstream step; a fabricated point is not, and nothing later can
    tell a real coordinate from an invented one.

    ``latitude`` and ``longitude`` are left exactly as parsed.
    """
    out = frame.copy()
    inside = [
        in_lahore(lat, lon) for lat, lon in zip(out["latitude"], out["longitude"], strict=True)
    ]
    out["coord_in_lahore"] = pd.array(inside, dtype="boolean")

    sources, lats, lons, flags = [], [], [], []
    for is_inside, lat, lon in zip(inside, out["latitude"], out["longitude"], strict=True):
        if is_inside is None:
            sources.append("missing")
            lats.append(None)
            lons.append(None)
            flags.append(("coord_missing",))
        elif is_inside:
            sources.append("source")
            lats.append(lat)
            lons.append(lon)
            flags.append(())
        else:
            sources.append("out_of_lahore_nulled")
            lats.append(None)
            lons.append(None)
            flags.append(("coord_out_of_lahore",))

    out["latitude_clean"] = lats
    out["longitude_clean"] = lons
    out["coord_source"] = sources
    out["clean_flags"] = _merge_flags(out, flags)

    counts = {
        "coordinate inside Lahore": sources.count("source"),
        "outside Lahore — nulled": sources.count("out_of_lahore_nulled"),
        "  of which also named another city": sum(
            1
            for src, title, address in zip(sources, out["title"], out["address"], strict=True)
            if src == "out_of_lahore_nulled" and names_other_city(title, address)
        ),
        "no coordinate at source": sources.count("missing"),
    }
    return out, StepReport(
        "coordinates — D-33",
        len(frame), len(out), analysis_rows(frame), analysis_rows(out), counts,
    )


# --------------------------------------------------------------------------------------
# Step 4 — scope and quality exclusions (D-34, D-35)
# --------------------------------------------------------------------------------------

#: Matches a title that sells one floor of a building — "(Ground Floor)", "(First Floor)".
#: A floor being *sold* is an apartment or a portion, both excluded by D-02. B-16 tested for
#: the word "portion" and did not catch any of these.
_FLOOR_SALE_RE = re.compile(
    r"\((?:ground|first|second|third|fourth|1st|2nd|3rd|4th|upper|lower)[^)]*floor",
    re.IGNORECASE,
)

#: Bedroom count above which a listing is physically impossible rather than merely large.
#: Deliberately blunt — see D-35. A rule tied to floor area fired on 73 rows because 7
#: bedrooms on a 10 marla house is normal in Lahore, where houses go up rather than out.
_IMPOSSIBLE_BEDROOMS = 20


@dataclass(frozen=True)
class ExclusionRule:
    """One reason a row leaves the analysis set.

    Attributes:
        flag: The reason code, written to ``exclusion_reason`` and ``clean_flags``.
        description: Human-readable line for the reconciliation report.
        predicate: Takes the frame, returns a boolean Series that is True to exclude.
    """

    flag: str
    description: str
    predicate: object


def _titles(frame: pd.DataFrame) -> pd.Series:
    """Return the title column as a string Series with nulls as empty strings."""
    return frame["title"].fillna("").astype(str)


#: Applied in order, but order does not affect the outcome — a row can match several rules
#: and every match is recorded, so the reconciliation can report both "rows excluded" and
#: "times each reason fired" without the two being confused.
EXCLUSION_RULES: list[ExclusionRule] = [
    ExclusionRule(
        "excl_penthouse",
        "penthouse — an apartment, D-02 (B-16)",
        lambda f: _titles(f).str.contains("penthouse", case=False, regex=False),
    ),
    ExclusionRule(
        "excl_floor_sale",
        "one floor of a building sold — apartment or portion, D-02",
        lambda f: _titles(f).str.contains(_FLOOR_SALE_RE, regex=True),
    ),
    ExclusionRule(
        "excl_other_city",
        "title and coordinates agree the property is not in Lahore",
        lambda f: (f["coord_in_lahore"] == False).fillna(False)  # noqa: E712 — nullable
        & pd.Series(
            [names_other_city(t, a) for t, a in zip(f["title"], f["address"], strict=True)],
            index=f.index,
        ),
    ),
    ExclusionRule(
        "excl_no_price",
        "no asking price — the target is absent",
        lambda f: f["price"].isna(),
    ),
    ExclusionRule(
        "excl_no_area",
        "no area recoverable from payload or title",
        lambda f: f["area_marla"].isna(),
    ),
    ExclusionRule(
        "excl_zero_rooms",
        "bedrooms or bathrooms zero — a missing-value sentinel, D-35",
        lambda f: (f["bedrooms"] == 0) | (f["bathrooms"] == 0),
    ),
    ExclusionRule(
        "excl_impossible_beds",
        f"bedrooms >= {_IMPOSSIBLE_BEDROOMS} — physically impossible, D-35",
        lambda f: f["bedrooms"] >= _IMPOSSIBLE_BEDROOMS,
    ),
]


def apply_exclusions(frame: pd.DataFrame) -> tuple[pd.DataFrame, StepReport]:
    """Mark rows that leave the analysis set, with a reason. Nothing is removed here.

    Adds ``excluded`` (bool) and ``exclusion_reason`` (every matching reason, ``;``-joined).
    The caller filters on ``excluded`` when it wants the analysis set; the excluded rows stay
    in the frame so the reconciliation is derived from one table rather than a difference
    between two (PLAN §6 — no silent drops).

    Requires :func:`add_area_marla` and :func:`add_clean_coordinates` to have run: two rules
    read ``area_marla`` and ``coord_in_lahore``.
    """
    out = frame.copy()
    masks = {rule.flag: pd.Series(rule.predicate(out), index=out.index).fillna(False).astype(bool)
             for rule in EXCLUSION_RULES}

    reasons = []
    for i in out.index:
        hit = [flag for flag, mask in masks.items() if mask[i]]
        reasons.append(";".join(hit))
    out["exclusion_reason"] = reasons
    out["excluded"] = [bool(r) for r in reasons]
    out["clean_flags"] = _merge_flags(out, [tuple(r.split(";")) if r else () for r in reasons])

    counts = {rule.description: int(masks[rule.flag].sum()) for rule in EXCLUSION_RULES}
    counts["rows excluded (distinct, overlaps removed)"] = int(out["excluded"].sum())
    counts["rows remaining"] = int((~out["excluded"]).sum())
    return out, StepReport(
        "exclusions — D-34, D-35",
        len(frame), len(out), analysis_rows(frame), analysis_rows(out), counts,
    )


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------


def run_cleaning(interim_path: str) -> tuple[pd.DataFrame, list[StepReport]]:
    """Run every cleaning step implemented so far and return the frame and its reports.

    Only rows stage 1 marked ``in_scope`` enter. The 532 out-of-scope rows stay in the
    interim file with their own ``scope_reason``; this module never touches them and never
    rewrites stage 1's verdict.

    Steps still to come: B-08 locality decomposition, B-07 dedup fingerprint, B-06 spread
    threshold, B-10 locality spelling, B-09 residual price junk, D-37 column drops.
    """
    frame = load_interim(interim_path)
    frame = frame[frame["in_scope"]].reset_index(drop=True)

    steps = (
        add_area_marla,          # 1 + 2 — B-15 / D-32, B-12 / D-31
        apply_manual_corrections,  # 2b — D-46, before anything groups or judges
        add_clean_coordinates,  # 3 — D-33
        apply_exclusions,       # 4 — D-34, D-35
        add_locality_parts,     # 5 — B-08, B-10
        add_fingerprint,        # 6 — B-07 / D-43
        flag_price_junk,        # 7 — B-09 / D-44, before the collapse, never after
        collapse_groups,        # 8 — D-45
        drop_zero_variance,     # 9 — D-37
        apply_schema,           # 10 — D-39, last so it types only surviving columns
    )
    reports: list[StepReport] = []
    for step in steps:
        frame, report = step(frame)
        reports.append(report)
    return frame, reports


def reconciliation(reports: list[StepReport]) -> str:
    """Render every step report as one markdown document for ``reports/``."""
    return "\n\n".join(r.to_markdown() for r in reports)


# --------------------------------------------------------------------------------------
# Step 5 — locality decomposition (B-08) and spelling canonicalisation (B-10)
# --------------------------------------------------------------------------------------

#: Address segments that carry no locality information and are stripped before parsing.
_ADDRESS_NOISE = {"pakistan", "punjab", "lahore", ""}

#: Locality spellings that denote one place, mapped onto the form used by the most rows.
#:
#: Found systematically rather than by eye: normalising every locality to lowercase
#: alphanumerics collapses exactly three pairs, and stripping the generic suffixes
#: ("Scheme", "Housing Scheme", "Society", ...) collapses two more. That is the whole
#: vocabulary problem in 383 values — B-10 listed three, of which one pair was not in fact
#: a variant.
#:
#: NOT merged, deliberately: "Sarwar Town" (3) and "Sarwar Colony" (2), which the suffix
#: pass collides but which are different naming conventions and may be different places;
#: "Al-Kabir Town" and "Al Kabir Orchard", which are separate developments; and
#: "Sher Shah Road" and "Sher Shah Colony", a road and a colony.
LOCALITY_CANONICAL: dict[str, str] = {
    "Highcourt Society": "High Court Society",
    "Sher Shah Colony": "Shershah Colony",
    "Al Kabir Orchard": "Al-Kabir Orchard",
    "Sabzazar": "Sabzazar Scheme",
    "Taj Bagh": "Taj Bagh Housing Scheme",
}

#: Roman numerals seen in DHA phase labels ("Phase XII (EME)"), for the numeric phase column.
_ROMAN = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9,
    "X": 10, "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
}

_PHASE_NUM_RE = re.compile(r"phase\s+(\d+|[ivx]+)\b", re.IGNORECASE)


def canonical_locality(name: object) -> str | None:
    """Map a locality spelling onto its canonical form (B-10). Unknown names pass through.

    Anything that is not a string — one in-scope row has no locality at all — returns
    ``None``, so a missing society never reaches the path builder as a float NaN.
    """
    if not isinstance(name, str):
        return None
    return LOCALITY_CANONICAL.get(name.strip(), name.strip())


def _segment_kind(segment: str) -> str:
    """Classify one address segment as a phase, sector, block, or something else."""
    lowered = segment.lower()
    if "phase" in lowered:
        return "phase"
    if "sector" in lowered:
        return "sector"
    if "block" in lowered:
        return "block"
    return "sub"


def phase_number(label: object) -> int | None:
    """Extract the numeric phase from a label, Arabic or Roman.

    "Phase 6" and "Phase XII (EME)" both yield a number; "Phase 9 - Town" yields 9, which is
    why the verbatim label is kept alongside it — Phase 9 Town and Phase 9 Prism are
    different places that share a number.
    """
    if not isinstance(label, str):
        return None
    match = _PHASE_NUM_RE.search(label)
    if not match:
        return None
    token = match.group(1)
    if token.isdigit():
        return int(token)
    return _ROMAN.get(token.upper())


def parse_address_path(address: object, locality: object) -> dict[str, object]:
    """Decompose an address into its locality hierarchy (B-08).

    Ilaan's ``address`` is an ordered path from most specific to least — "Block EE, Phase 4,
    DHA, Lahore, Punjab, Pakistan" — so the decomposition is general rather than a rule per
    society. Segments are stripped of the city, province and country, the final segment is
    the society (and matches ``locality`` on 8,322 of 8,358 rows), and everything before it
    is classified by keyword.

    Returns a dict of ``loc_society``, ``loc_phase``, ``loc_phase_num``, ``loc_block``,
    ``loc_sector``, ``loc_sub`` and ``loc_path``. Missing tiers are ``None``; no tier is
    invented and none is collapsed into another, because which granularity carries price
    signal is an EDA question, not a cleaning one.
    """
    society = canonical_locality(locality)
    segments = [s.strip() for s in str(address).split(",")]
    segments = [s for s in segments if s.lower() not in _ADDRESS_NOISE]

    # The trailing segment repeats the society when present; drop it so only sub-tiers remain.
    if segments and canonical_locality(segments[-1]) == society:
        segments = segments[:-1]

    found: dict[str, list[str]] = {"phase": [], "sector": [], "block": [], "sub": []}
    for segment in segments:
        found[_segment_kind(segment)].append(segment)

    phase = found["phase"][0] if found["phase"] else None
    path = [p for p in (society, phase, found["sector"][0] if found["sector"] else None,
                        found["block"][0] if found["block"] else None) if p]
    return {
        "loc_society": society,
        "loc_phase": phase,
        "loc_phase_num": phase_number(phase),
        "loc_sector": found["sector"][0] if found["sector"] else None,
        "loc_block": found["block"][0] if found["block"] else None,
        "loc_sub": " / ".join(found["sub"]) if found["sub"] else None,
        "loc_path": " > ".join(path) if path else None,
    }


def add_locality_parts(frame: pd.DataFrame) -> tuple[pd.DataFrame, StepReport]:
    """Add the decomposed locality columns. ``locality`` and ``address`` are left as parsed."""
    out = frame.copy()
    parsed = [
        parse_address_path(address, locality)
        for address, locality in zip(out["address"], out["locality"], strict=True)
    ]
    for column in ("loc_society", "loc_phase", "loc_phase_num", "loc_sector", "loc_block",
                   "loc_sub", "loc_path"):
        out[column] = [row[column] for row in parsed]

    renamed = int(
        sum(1 for original in out["locality"] if canonical_locality(original) != original)
    )
    analysis = out[~out["excluded"]] if "excluded" in out.columns else out
    counts = {
        "locality spellings merged (B-10)": renamed,
        "distinct societies": int(analysis["loc_society"].nunique()),
        "  with a phase parsed": int(analysis["loc_phase"].notna().sum()),
        "  with a sector parsed": int(analysis["loc_sector"].notna().sum()),
        "  with a block parsed": int(analysis["loc_block"].notna().sum()),
        "  with no sub-tier at all": int(analysis["loc_path"].fillna("").eq(
            analysis["loc_society"].fillna("")).sum()),
        "distinct society > phase/sector": int(
            analysis[["loc_society", "loc_phase", "loc_sector"]]
            .fillna("")
            .astype(str)
            .agg("|".join, axis=1)
            .nunique()
        ),
        "distinct full paths": int(analysis["loc_path"].nunique()),
    }
    return out, StepReport(
        "locality — B-08 decomposition, B-10 spelling",
        len(frame), len(out), analysis_rows(frame), analysis_rows(out), counts,
    )


# --------------------------------------------------------------------------------------
# Step 6 — zero-variance column drops (D-37)
# --------------------------------------------------------------------------------------

#: Columns dropped because they hold exactly one value across every in-scope row (D-37).
#: Checked at runtime rather than trusted: if one of these turns out to vary, or a column
#: outside the list turns out not to, the step reports it instead of proceeding quietly.
ZERO_VARIANCE_COLUMNS: tuple[str, ...] = (
    # Named in B-13.
    "condition", "year_built", "is_verified", "is_gold_verified", "is_sold",
    # Equally single-valued and missed by B-13.
    "market_status", "city", "province", "amenity_count", "amenities",
    # Constant because of a filter applied upstream rather than because the source is
    # uniform: `property_type` is "House" only because stage 1 selected houses, and
    # `in_scope` / `scope_reason` describe a partition this frame is already on one side
    # of. They carry no information here; the interim file keeps the full picture.
    "property_type", "in_scope", "scope_reason", "id_matches_discovery",
)

#: Columns that vary and are explicitly kept against B-13, which filed them as zero-variance.
#: They may proxy for how professionally a listing is marketed; the decision to use them or
#: not belongs to stage 4 (D-37).
KEPT_LOW_VARIANCE_COLUMNS: tuple[str, ...] = ("is_featured", "has_video", "views", "image_count")


def drop_zero_variance(frame: pd.DataFrame) -> tuple[pd.DataFrame, StepReport]:
    """Drop the columns of D-37, verifying each is single-valued before it goes.

    Variance is measured over every row the frame holds, excluded rows included, not over
    the analysis set. Measuring on the analysis set makes ``excluded`` and
    ``exclusion_reason`` look constant — they are constant there by construction, and they
    exist precisely to describe the rows outside it. The wider denominator is also the more
    conservative one: a column that varies only among excluded rows survives.
    """
    def distinct(column: str) -> int:
        values = frame[column]
        if values.map(type).eq(list).any():  # `amenities` holds lists, which are unhashable
            return values.map(repr).nunique(dropna=False)
        return values.nunique(dropna=False)

    present = [c for c in ZERO_VARIANCE_COLUMNS if c in frame.columns]
    varying = {c: distinct(c) for c in present if distinct(c) > 1}
    unlisted = {
        c: 1
        for c in frame.columns
        if c not in present and c not in KEPT_LOW_VARIANCE_COLUMNS and distinct(c) == 1
    }

    out = frame.drop(columns=[c for c in present if c not in varying])
    counts = {
        "columns dropped": len(present) - len(varying),
        "listed but NOT single-valued — KEPT": len(varying),
        "single-valued but not listed — REVIEW": len(unlisted),
        "columns remaining": len(out.columns),
    }
    for column, n in varying.items():
        counts[f"  {column} has {n} values"] = n
    for column in unlisted:
        counts[f"  {column} is single-valued"] = 1
    return out, StepReport(
        "columns — D-37",
        len(frame), len(out), analysis_rows(frame), analysis_rows(out), counts,
    )


# --------------------------------------------------------------------------------------
# Step 7 — explicit dtypes (D-39)
# --------------------------------------------------------------------------------------

#: The processed table's declared schema. Types are declared, never inferred.
#:
#: Inference is how a pipeline drifts: ``DataFrame.from_records`` types a string column as
#: ``object`` on pandas 2 and ``str`` on pandas 3, turns an integer column with one null into
#: a float, and leaves ``created_at`` as text that sorts lexically — which would let B-03's
#: recency holdout appear to work while splitting on nothing. Declaring the schema is also
#: what makes D-36's choice of parquet worth anything: the format preserves whatever types it
#: is handed, so handing it inferred ones preserves the drift.
SCHEMA: dict[str, str] = {
    # identity and provenance
    "property_id": "int64",
    "source_url": "string",
    "discovered_on_page": "int64",
    "price_matches_discovery": "boolean",
    # listing text
    "title": "string",
    "address": "string",
    "description": "string",
    # target
    "price": "float64",
    # area, source and cleaned
    "area": "float64",
    "area_unit": "category",
    "area_marla": "float64",
    "area_source": "category",
    # structure
    "bedrooms": "Int64",
    "bathrooms": "Int64",
    # location, source and cleaned
    "locality": "string",
    "latitude": "float64",
    "longitude": "float64",
    "latitude_clean": "float64",
    "longitude_clean": "float64",
    "coord_in_lahore": "boolean",
    "coord_source": "category",
    "loc_society": "category",
    "loc_phase": "category",
    "loc_phase_num": "Int64",
    "loc_sector": "category",
    "loc_block": "string",
    "loc_sub": "string",
    "loc_path": "string",
    # listing metadata kept for EDA (D-37)
    "views": "Int64",
    "image_count": "Int64",
    "is_featured": "bool",
    "has_video": "bool",
    # time — a control at modelling, PLAN §3, and the basis of B-03's recency holdout
    "created_at": "datetime64[ns, UTC]",
    # cleaning audit trail
    "clean_flags": "string",
    "exclusion_reason": "string",
    "excluded": "bool",
    # fingerprint (B-07 / D-43)
    "fp_group_id": "Int64",
    "n_listings": "Int64",
    "fp_price_median": "float64",
    "fp_price_spread": "float64",
}


def apply_schema(frame: pd.DataFrame) -> tuple[pd.DataFrame, StepReport]:
    """Cast every column to its declared type, reporting anything the schema does not cover.

    A column present in the frame but absent from :data:`SCHEMA` is left untouched and
    reported, so a new column added upstream cannot slip into the processed table untyped.
    A column in the schema but absent from the frame is reported the same way.
    """
    out = frame.copy()
    unknown = [c for c in out.columns if c not in SCHEMA]
    missing = [c for c in SCHEMA if c not in out.columns]

    for column, dtype in SCHEMA.items():
        if column not in out.columns:
            continue
        if dtype.startswith("datetime64"):
            # to_datetime infers its resolution from the data on pandas 3 and fixes it at
            # nanoseconds on pandas 2. Casting afterwards pins both to the declared type,
            # so the parquet file is byte-identical whichever version wrote it.
            out[column] = pd.to_datetime(out[column], utc=True, format="ISO8601").astype(dtype)
        else:
            out[column] = out[column].astype(dtype)

    out = out[[c for c in SCHEMA if c in out.columns] + unknown]

    counts = {
        "columns typed": len([c for c in SCHEMA if c in out.columns]),
        "in frame but not in schema — REVIEW": len(unknown),
        "in schema but not in frame — REVIEW": len(missing),
    }
    for column in unknown:
        counts[f"  untyped: {column}"] = 1
    for column in missing:
        counts[f"  absent: {column}"] = 1
    return out, StepReport(
        "dtypes — D-39",
        len(frame), len(out), analysis_rows(frame), analysis_rows(out), counts,
    )


def write_processed(frame: pd.DataFrame, out_dir: str = "data/processed") -> dict[str, str]:
    """Split the cleaned frame into the analysis set and the excluded rows, and write both.

    This is where the exclusions of D-34 and D-35 stop being a flag and become a drop (D-42).
    Everything upstream carries every row so the arithmetic reconciles against one table; the
    artefact splits so that no later stage can train on a penthouse by forgetting a filter.

    * ``listings.parquet`` — the analysis set. What stages 3 onward read.
    * ``listings_excluded.parquet`` — the dropped rows, each carrying ``exclusion_reason``.
      Never read by the pipeline; it exists so "why is this listing not in the model" has an
      answer that does not require re-running anything.

    A CSV of each is written beside it for eyeballing rows. CSV cannot carry the dtypes of
    D-39, so nothing reads it back.
    """
    from pathlib import Path

    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)

    kept = frame[~frame["excluded"]].reset_index(drop=True)
    dropped = frame[frame["excluded"]].reset_index(drop=True)
    if len(kept) + len(dropped) != len(frame):  # pragma: no cover — arithmetic guard
        raise AssertionError("split lost rows")

    written: dict[str, str] = {}
    for name, part in (("listings", kept), ("listings_excluded", dropped)):
        parquet_path = directory / f"{name}.parquet"
        csv_path = directory / f"{name}.csv"
        part.to_parquet(parquet_path, index=False)
        part.to_csv(csv_path, index=False)
        written[name] = f"{parquet_path} ({len(part):,} rows)"
    return written


# --------------------------------------------------------------------------------------
# Step 8 — dedup fingerprint (B-07)
# --------------------------------------------------------------------------------------

#: The columns that identify a listing's product. Amended from D-08, which fingerprinted on
#: locality + area + beds + baths and put 77.1% of rows into multi-listing groups because
#: `locality` is coarse. Coordinates and the decomposed locality path together bring that to
#: 33.0%. See D-43.
FINGERPRINT_COLUMNS: tuple[str, ...] = (
    "latitude_clean", "longitude_clean", "loc_path", "area_marla", "bedrooms", "bathrooms",
)


def _fingerprint_key(frame: pd.DataFrame) -> pd.Series:
    """Build the fingerprint as a single delimited string, nulls made explicit."""
    parts = []
    for column in FINGERPRINT_COLUMNS:
        values = frame[column]
        if column == "area_marla":
            values = values.round(2)
        parts.append(values.astype("object").fillna("~").astype(str))
    key = parts[0]
    for part in parts[1:]:
        key = key + "|" + part
    return key


def add_fingerprint(frame: pd.DataFrame) -> tuple[pd.DataFrame, StepReport]:
    """Add ``fp_group_id``, ``n_listings``, ``fp_price_median`` and ``fp_price_spread``.

    Groups are computed over the analysis set only — an excluded row must not join a group
    and pull its median.
    """
    out = frame.copy()
    analysis = out[~out["excluded"]]
    key = _fingerprint_key(analysis)

    grouped = analysis["price"].groupby(key)
    sizes, medians = grouped.transform("size"), grouped.transform("median")
    spread = grouped.transform(lambda p: (p.max() - p.min()) / p.median() if p.median() else 0.0)

    out["fp_group_id"] = pd.Series(pd.factorize(key)[0], index=analysis.index).reindex(out.index)
    out["n_listings"] = sizes.reindex(out.index)
    out["fp_price_median"] = medians.reindex(out.index)
    out["fp_price_spread"] = spread.reindex(out.index)

    multi = sizes > 1
    # `sizes` is a per-row transform, so summing it over the rows in multi-listing groups
    # counts each group's size once per member and returns the sum of squares. The count
    # wanted here is of rows, so count the mask.
    multi_keys = key[multi].unique()
    # `created_at` is still text here — the schema is applied last — so it is parsed
    # locally rather than relying on a dtype this step does not own.
    one_date = (
        pd.to_datetime(analysis["created_at"], utc=True, format="ISO8601")
        .dt.date.groupby(key)
        .nunique()
        .eq(1)
    )
    counts = {
        "groups": int(key.nunique()),
        "  of which hold more than one listing": len(multi_keys),
        "rows in multi-listing groups": int(multi.sum()),
        "largest group": int(sizes.max()),
        # Restricted to multi-listing groups: a singleton satisfies "one date" trivially,
        # so including them would report ~100% whatever the data looked like.
        "multi-listing groups posted entirely on one date": int(one_date[multi_keys].sum()),
    }
    return out, StepReport(
        "fingerprint — B-07 / D-43",
        len(frame), len(out), analysis_rows(frame), analysis_rows(out), counts,
    )


# --------------------------------------------------------------------------------------
# Step 9 — price junk (B-09)
# --------------------------------------------------------------------------------------

#: How far from the corpus median price-per-marla a listing may sit before it is not an
#: asking price at all. Deliberately generous: a factor of ten each way is 2.8x beyond the
#: 1st percentile and 4.2x beyond the 99th, so the rule catches rent figures and typos
#: rather than merely expensive houses. See D-44.
_PPM_FACTOR = 10.0

#: How far from its own group's median a listing may sit. This is a guard on the collapse,
#: not a detector: with a group of two the median is the mean, so a pair like
#: [100,000, 18,500,000] would collapse to 9,300,000 — a fabricated price, wrong by a factor
#: of two, and undetectable afterwards.
_GROUP_FACTOR = 4.0

#: Smallest physically possible house, in marla. One marla (225 sq ft) is a real category in
#: dense Lahore — Tajpura and Sabzazar have them, priced normally. 0.2 marla is 45 sq ft.
_MIN_AREA_MARLA = 0.5


def flag_price_junk(frame: pd.DataFrame) -> tuple[pd.DataFrame, StepReport]:
    """Flag listings whose price or area is not a plausible asking figure (B-09).

    Three rules, applied to the analysis set only. Excluded rows are already gone and must
    not be re-judged.
    """
    out = frame.copy()
    analysis = ~out["excluded"]
    ppm = out["price"] / out["area_marla"]
    corpus_median = ppm[analysis].median()

    rules = {
        "excl_price_implausible": analysis
        & ((ppm < corpus_median / _PPM_FACTOR) | (ppm > corpus_median * _PPM_FACTOR)),
        "excl_price_group_outlier": analysis
        & (out["n_listings"] > 1)
        & (
            (out["price"] < out["fp_price_median"] / _GROUP_FACTOR)
            | (out["price"] > out["fp_price_median"] * _GROUP_FACTOR)
        ),
        "excl_area_impossible": analysis & (out["area_marla"] < _MIN_AREA_MARLA),
    }
    masks = {name: mask.fillna(False).astype(bool) for name, mask in rules.items()}

    reasons = out["exclusion_reason"].fillna("").tolist()
    for position in range(len(out)):
        hit = [name for name, mask in masks.items() if mask.iloc[position]]
        if hit:
            existing = [r for r in reasons[position].split(";") if r]
            reasons[position] = ";".join(existing + hit)
    out["exclusion_reason"] = reasons
    out["excluded"] = [bool(r) for r in reasons]
    out["clean_flags"] = _merge_flags(
        out, [tuple(n for n, m in masks.items() if m.iloc[i]) for i in range(len(out))]
    )

    counts = {
        f"corpus median PKR/marla = {corpus_median:,.0f}; band "
        f"{corpus_median / _PPM_FACTOR:,.0f} to {corpus_median * _PPM_FACTOR:,.0f}": 0,
        "price per marla outside the band": int(masks["excl_price_implausible"].sum()),
        "price far from its own group's median": int(masks["excl_price_group_outlier"].sum()),
        "area physically impossible": int(masks["excl_area_impossible"].sum()),
        "rows newly excluded (distinct)": int(
            (masks["excl_price_implausible"] | masks["excl_price_group_outlier"]
             | masks["excl_area_impossible"]).sum()
        ),
    }
    return out, StepReport(
        "price junk — B-09 / D-44",
        len(frame), len(out), analysis_rows(frame), analysis_rows(out), counts,
    )


# --------------------------------------------------------------------------------------
# Step 10 — collapse fingerprint groups (D-45)
# --------------------------------------------------------------------------------------


def collapse_groups(frame: pd.DataFrame) -> tuple[pd.DataFrame, StepReport]:
    """Reduce each fingerprint group in the analysis set to one row at the median price.

    Rows sharing a fingerprint share every feature the model will see; they differ only in
    where the poster placed them in a price ladder. They carry one observation of signal
    between them, so the group becomes one row and ``n_listings`` records how many listings
    it stood for.

    Runs *after* :func:`flag_price_junk` and not before. With a group of two the median is
    the mean, so a junk price left in the group would be averaged into the survivor.

    Excluded rows are never collapsed — they pass through so the excluded file keeps every
    dropped listing individually.
    """
    out = frame.copy()
    analysis = out[~out["excluded"]]
    excluded = out[out["excluded"]]

    key = _fingerprint_key(analysis)
    grouped = analysis["price"].groupby(key)
    sizes, medians = grouped.transform("size"), grouped.transform("median")
    spread = grouped.transform(lambda p: (p.max() - p.min()) / p.median() if p.median() else 0.0)

    kept = analysis.copy()
    kept["n_listings"] = sizes
    kept["fp_price_median"] = medians
    kept["fp_price_spread"] = spread
    kept = kept.assign(_key=key.values).drop_duplicates("_key", keep="first").drop(columns="_key")
    kept["price"] = kept["fp_price_median"]

    out = pd.concat([kept, excluded], ignore_index=True)
    counts = {
        "analysis rows before collapse": len(analysis),
        "groups": len(kept),
        "rows removed by collapse": len(analysis) - len(kept),
        "largest group collapsed": int(sizes.max()),
        "rows whose price is now a group median": int((kept["n_listings"] > 1).sum()),
    }
    return out, StepReport(
        "collapse — D-45",
        len(frame), len(out), analysis_rows(frame), analysis_rows(out), counts,
    )


# --------------------------------------------------------------------------------------
# Synthetic sample (D-23)
# --------------------------------------------------------------------------------------

#: Property ids for synthetic rows start here. Ilaan's ids in this project run 556,159 to
#: 697,397, so a nine-million id is unmistakably invented — nobody can confuse a sample row
#: for a real listing, and a join against real data finds nothing.
_SYNTHETIC_ID_BASE = 9_000_000


def synthesise_sample(
    frame: pd.DataFrame, n_rows: int = 200, seed: int = 20260908
) -> pd.DataFrame:
    """Generate synthetic rows matching the processed schema (D-23).

    Ilaan publishes no terms, which means no clause prohibits redistribution and no licence
    permits it. So the committed sample reproduces the *shape* of the data and none of its
    content: every row is invented.

    What is drawn from the real data and why it is safe to: **distributions** (how price per
    marla varies by society, how areas and room counts are spread) and **Lahore place
    names**. A society's name is a fact about the city, not Ilaan's work, and keeping the
    real vocabulary is what lets a notebook group by locality and produce something
    meaningful rather than merely execute. What is never taken: any actual listing — no real
    title, price, coordinate or combination of them.

    Args:
        frame: The processed analysis set, used only for marginal distributions.
        n_rows: How many rows to generate.
        seed: Fixed so the committed file is reproducible and its diff is empty on a re-run.

    Returns:
        A frame carrying exactly the columns and dtypes of :data:`SCHEMA`.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    real = frame[~frame["excluded"]] if "excluded" in frame.columns else frame
    real = real[real["price"].notna() & real["area_marla"].notna()]

    # Sample the society (and its phase/block vocabulary) in proportion to real volume, so
    # the synthetic set has the same shape of concentration the real one does.
    societies = real["loc_society"].astype("object")
    picks = rng.choice(len(real), size=n_rows, replace=True)
    chosen = real.iloc[picks]

    price_per_marla = (real["price"] / real["area_marla"]).astype(float)
    by_society = price_per_marla.groupby(societies).median()
    global_median = float(price_per_marla.median())

    # Area, rooms and locality come from the SAME donor row, so their joint structure
    # survives — a notebook plotting bedrooms against area sees the real relationship rather
    # than three independent marginals, which would put 2 bedrooms in a 17 marla house.
    areas = chosen["area_marla"].astype(float).to_numpy()
    # Jitter so no synthetic row reproduces a real area at a real price, then round back to
    # the tenth of a marla that real listings are quoted in.
    areas = np.round(areas * rng.uniform(0.9, 1.1, n_rows), 1).clip(1.0, 200.0)
    beds = chosen["bedrooms"].astype(int).to_numpy()
    baths = chosen["bathrooms"].astype(int).to_numpy()

    society_names = chosen["loc_society"].astype("object").to_numpy()
    base = np.array([by_society.get(s, global_median) for s in society_names], dtype=float)
    # Lognormal noise around the society's own level: right-skewed, like the real thing.
    ppm = base * rng.lognormal(mean=0.0, sigma=0.22, size=n_rows)
    prices = np.round(areas * ppm, -5)
    lat_min, lat_max, lon_min, lon_max = LAHORE_BBOX
    latitudes = np.round(rng.uniform(lat_min, lat_max, n_rows), 6)
    longitudes = np.round(rng.uniform(lon_min, lon_max, n_rows), 6)

    start, end = real["created_at"].min(), real["created_at"].max()
    # `max(..., 1)` because a corpus posted in a single instant is a legitimate degenerate
    # input — a small test fixture, or a source that batch-loaded everything at once — and
    # `rng.integers(0, 0)` raises rather than returning zero.
    span = max(int((end - start).total_seconds()), 1)
    created = [start + pd.Timedelta(seconds=int(s)) for s in rng.integers(0, span, n_rows)]

    def marla_label(value: float) -> str:
        return f"{value / 20:g} Kanal" if value >= 20 and value % 20 == 0 else f"{value:g} Marla"

    phases = chosen["loc_phase"].astype("object").to_numpy()
    blocks = chosen["loc_block"].astype("object").to_numpy()

    rows = []
    for i in range(n_rows):
        tiers = [t for t in (blocks[i], phases[i], society_names[i]) if isinstance(t, str)]
        where = ", ".join(tiers) if tiers else "Lahore"
        rows.append(
            {
                "property_id": _SYNTHETIC_ID_BASE + i,
                "source_url": f"https://example.invalid/synthetic/{_SYNTHETIC_ID_BASE + i}",
                "discovered_on_page": int(i // 50) + 1,
                "price_matches_discovery": True,
                "title": f"{marla_label(areas[i])} House for Sale in {where}, Lahore",
                "address": f"{where}, Lahore, Punjab, Pakistan",
                "description": "",
                "price": float(prices[i]),
                "area": float(areas[i]),
                "area_unit": "marla",
                "area_marla": float(areas[i]),
                "area_source": "payload",
                "bedrooms": int(beds[i]),
                "bathrooms": int(baths[i]),
                "locality": society_names[i],
                "latitude": latitudes[i],
                "longitude": longitudes[i],
                "latitude_clean": latitudes[i],
                "longitude_clean": longitudes[i],
                "coord_in_lahore": True,
                "coord_source": "source",
                "loc_society": society_names[i],
                "loc_phase": phases[i],
                "loc_phase_num": phase_number(phases[i]),
                "loc_sector": chosen["loc_sector"].astype("object").to_numpy()[i],
                "loc_block": blocks[i],
                "loc_sub": None,
                "loc_path": " > ".join(reversed(tiers)) if tiers else None,
                "views": int(rng.integers(0, 60)),
                "image_count": int(rng.integers(0, 30)),
                "is_featured": False,
                "has_video": False,
                "created_at": created[i],
                "clean_flags": "synthetic",
                "exclusion_reason": "",
                "excluded": False,
                "fp_group_id": i,
                "n_listings": 1,
                "fp_price_median": float(prices[i]),
                "fp_price_spread": 0.0,
            }
        )

    sample = pd.DataFrame.from_records(rows)
    sample, _ = apply_schema(sample)

    # Guard, and it is not decoration — it fired on the first run. A title is built from an
    # area and a place, and prices are rounded to the nearest 100,000, so a synthetic row can
    # land on a real listing by coincidence. Any that does has its price stepped until it
    # does not, deterministically, so the committed file stays reproducible.
    real_keys = set(zip(real["title"].astype(str), real["price"], strict=True))

    def collisions_in(rows: pd.DataFrame) -> list[int]:
        pairs = zip(rows["title"].astype(str), rows["price"], strict=True)
        return [i for i, key in enumerate(pairs) if key in real_keys]

    for _ in range(20):
        hits = collisions_in(sample)
        if not hits:
            break
        for position in hits:
            sample.iloc[position, sample.columns.get_loc("price")] += 100_000.0
            sample.iloc[position, sample.columns.get_loc("fp_price_median")] = sample.iloc[
                position, sample.columns.get_loc("price")
            ]
    if collisions_in(sample):
        raise AssertionError("synthetic rows still reproduce a real listing after repair")
    if set(sample["property_id"]) & set(frame["property_id"]):  # pragma: no cover
        raise AssertionError("synthetic property_id collides with a real one")
    return sample


def read_processed(path: str) -> pd.DataFrame:
    """Read a processed parquet file and re-apply :data:`SCHEMA`. Use this, not `read_parquet`.

    Parquet preserves the types it is handed, with one exception this project has actually
    hit: a ``category`` column whose values are entirely null comes back as ``object``. On the
    full dataset every category column has values, so the round-trip is exact — but a future
    run, a filtered subset or a small fixture can produce an all-null category, and the
    failure is silent. Re-applying the schema on read makes the dtype contract hold whatever
    the file did with a degenerate column.
    """
    frame, _ = apply_schema(pd.read_parquet(path))
    return frame


def write_reconciliation(reports: list[StepReport], path: str) -> str:
    """Write the run's reconciliation to a markdown file, derived from the run itself."""
    from datetime import date
    from pathlib import Path

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Stage 2 — cleaning reconciliation\n\n"
        f"Generated by `lhp.clean.run_cleaning` on {date.today().isoformat()}. "
        "Every number below is produced by the run, not written by hand.\n"
    )
    target.write_text(header + "\n" + reconciliation(reports) + "\n", encoding="utf-8")
    return str(target)
