"""Build and score the manual field-accuracy spot-check.

PLAN section 5.3 requires field-level accuracy of at least 98% on 30 randomly sampled
listings, checked field by field against the live page. That check is Nauman's — it needs a
human comparing our output to what the page actually shows — so this script does the two
mechanical halves: drawing a reproducible sample and scoring the filled sheet.

The sheet is deliberately wide rather than long. A long sheet would be 360 rows to fill;
this is 30, each showing every parsed value at once, and only *disagreements* are typed.
Comparing twelve values on a page and naming the wrong ones is a couple of minutes per
listing; typing 360 cells is an hour and invites fatigue errors in the audit itself.

Denominator, as agreed at intake: 30 listings x 12 fields = 360 comparisons. A field absent
from the page and null in our output counts correct. Present on the page but null in our
output counts wrong.

Usage:
    uv run python scripts/make_spotcheck.py            # draw the sample
    uv run python scripts/make_spotcheck.py --score    # score the filled sheet
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sheet_path(seed: int) -> Path:
    """Return the sheet for one draw. Named by seed so draws cannot overwrite each other."""
    return ROOT / "reports" / f"spotcheck-fields-{seed}.csv"


def meta_path(seed: int) -> Path:
    """Return the provenance sidecar for one draw."""
    return ROOT / "reports" / f"spotcheck-fields-{seed}.meta.json"

#: The fields the accuracy gate is measured over. Chosen because each varies between
#: listings and each matters downstream; city, property_type and market_status are excluded
#: because the scope filter fixes them by construction, so checking them would inflate the
#: score with twelve free correct answers per listing.
CHECK_FIELDS = (
    "price",
    "area",
    "area_unit",
    "bedrooms",
    "bathrooms",
    "locality",
    "address",
    "latitude",
    "longitude",
    "year_built",
    "condition",
    "created_at",
)


def load_in_scope() -> list[dict]:
    """Return the in-scope parsed listings."""
    path = ROOT / "data" / "interim" / "listings.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    return [r for r in rows if r.get("in_scope")]


def draw(seed: int, n: int, force: bool) -> None:
    """Write the spot-check sheet for a reproducible random sample.

    A draw is tied to the corpus it came from. If the data changes, the old sheet remains
    valid evidence about the old corpus and nothing else, so a new draw gets a new file
    rather than replacing it — and an existing sheet is never overwritten by accident,
    because filling one costs an hour of manual comparison.
    """
    sheet = sheet_path(seed)
    if sheet.exists() and not force:
        print(f"{sheet.relative_to(ROOT)} already exists.")
        print("Use a different --seed for a new draw, or --force to overwrite it.")
        return

    rows = load_in_scope()
    sample = random.Random(seed).sample(rows, min(n, len(rows)))
    sample.sort(key=lambda r: r["property_id"], reverse=True)

    sheet.parent.mkdir(parents=True, exist_ok=True)
    meta_path(seed).write_text(
        json.dumps(
            {
                "seed": seed,
                "drawn_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "corpus_rows_in_scope": len(rows),
                "sampled": len(sample),
                "fields_checked": list(CHECK_FIELDS),
                "denominator": len(sample) * len(CHECK_FIELDS),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # "checked" comes first and must be filled in. Without it a blank sheet is
    # indistinguishable from a perfect one — both have an empty mismatch column — and the
    # scorer would report 100% on work that was never done.
    header = ["n", "checked", "property_id", "url", *CHECK_FIELDS, "mismatched_fields", "notes"]
    with sheet.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for i, row in enumerate(sample, start=1):
            writer.writerow(
                [i, "", row["property_id"], row.get("source_url") or ""]
                + [("" if row.get(f) is None else row.get(f)) for f in CHECK_FIELDS]
                + ["", ""]
            )

    print(f"wrote {sheet.relative_to(ROOT)}")
    print(f"  seed {seed}, drawn from {len(rows):,} in-scope listings")
    print(f"denominator: {len(sample)} x {len(CHECK_FIELDS)} = {len(sample) * len(CHECK_FIELDS)}")
    print("\nHow to fill it in:")
    print("  1. Open each url. Compare the twelve values in that row to the page.")
    print("  2. Put y in the 'checked' column for every row you actually looked at.")
    print("  3. Leave mismatched_fields EMPTY if every value on that row is right.")
    print("  4. Otherwise list the wrong field names, comma separated, e.g. price,bedrooms")
    print("  5. Use notes for anything odd worth keeping (ambiguous units, a changed page).")
    print("\nRows without 'y' in 'checked' are not scored. The gate cannot pass until all")
    print("of them are marked, which is deliberate: an unfilled sheet must not read as 100%.")
    print("\nThen: uv run python scripts/make_spotcheck.py --score")


def score(seed: int) -> None:
    """Score the filled sheet against the 98% gate."""
    sheet = sheet_path(seed)
    if not sheet.exists():
        print(f"no sheet at {sheet.relative_to(ROOT)} — draw one first, or pass --seed.")
        return
    if meta_path(seed).exists():
        meta = json.loads(meta_path(seed).read_text(encoding="utf-8"))
        print(
            f"draw seed {meta['seed']}, {meta['drawn_at']}, "
            f"from {meta['corpus_rows_in_scope']:,} in-scope listings"
        )
    with sheet.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        print("sheet is empty.")
        return

    affirmed = {"y", "yes", "x", "1", "true", "done"}
    checked = [r for r in rows if (r.get("checked") or "").strip().lower() in affirmed]
    unchecked = len(rows) - len(checked)
    mismatches: dict[str, int] = {}
    total_wrong = 0
    for row in rows:
        raw = (row.get("mismatched_fields") or "").strip()
        if not raw:
            continue
        for name in (part.strip() for part in raw.split(",")):
            if not name:
                continue
            if name not in CHECK_FIELDS:
                print(f"  WARNING row {row['n']}: '{name}' is not a checked field name")
            mismatches[name] = mismatches.get(name, 0) + 1
            total_wrong += 1

    if not checked:
        print(f"\nNo rows are marked as checked ({len(rows)} in the sheet).")
        print("Nothing to score. Put y in the 'checked' column for each row you compared.")
        return

    denominator = len(checked) * len(CHECK_FIELDS)
    accuracy = 100 * (denominator - total_wrong) / denominator
    print(f"listings in sheet  {len(rows)}")
    print(f"listings checked   {len(checked)}")
    if unchecked:
        print(f"NOT CHECKED        {unchecked}   <- excluded from the score")
    print(f"comparisons        {denominator}")
    print(f"mismatches         {total_wrong}")
    print(f"FIELD ACCURACY     {accuracy:.2f}%   (on the rows actually checked)")
    if unchecked:
        print(f"GATE (>= 98%)      INCOMPLETE — {unchecked} of {len(rows)} rows unchecked")
    else:
        print(f"GATE (>= 98%)      {'PASS' if accuracy >= 98 else 'FAIL'}")
    if mismatches:
        print("\nmismatches by field (this is where to look first):")
        for name, count in sorted(mismatches.items(), key=lambda kv: -kv[1]):
            print(f"  {name:<14} {count}")


def main() -> None:
    """Draw the sample, or score the filled sheet."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score", action="store_true", help="Score the filled sheet.")
    parser.add_argument("--seed", type=int, default=20260906, help="Sampling seed.")
    parser.add_argument("--n", type=int, default=30, help="Listings to sample.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing sheet.")
    args = parser.parse_args()
    score(args.seed) if args.score else draw(args.seed, args.n, args.force)


if __name__ == "__main__":
    main()
