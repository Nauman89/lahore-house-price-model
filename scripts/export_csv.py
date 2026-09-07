"""Export the parsed listings to CSV for inspection in a spreadsheet.

`data/interim/listings.jsonl` is the pipeline's format — one JSON object per line, which
survives partial writes and streams cheaply. This produces the same rows as a CSV for
reading by eye. It is a convenience export, not a pipeline stage: nothing downstream reads
it, and it can be regenerated at any time.

Every parsed row is included, in scope or not, with `in_scope` and `scope_reason` as the
first columns. Filtering here would hide the excluded listings from the person most likely
to want to check the exclusions.

Written UTF-8 with a BOM, because Excel on Windows mis-reads plain UTF-8 CSVs.

Usage:
    uv run python scripts/export_csv.py
    uv run python scripts/export_csv.py --in-scope-only
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "interim" / "listings.jsonl"

#: Column order for reading, not for machines: identity, then the fields that decide
#: whether a row is usable, then provenance.
COLUMNS = (
    "property_id",
    "in_scope",
    "scope_reason",
    "price",
    "area",
    "area_unit",
    "bedrooms",
    "bathrooms",
    "locality",
    "address",
    "city",
    "province",
    "latitude",
    "longitude",
    "property_type",
    "market_status",
    "condition",
    "year_built",
    "created_at",
    "views",
    "is_verified",
    "is_gold_verified",
    "is_featured",
    "is_sold",
    "image_count",
    "amenity_count",
    "has_video",
    "title",
    "description",
    "source_url",
    "discovered_on_page",
    "id_matches_discovery",
    "price_matches_discovery",
)


def main() -> None:
    """Write the CSV."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-scope-only", action="store_true", help="Drop excluded rows.")
    parser.add_argument("--out", type=Path, help="Destination (default alongside the JSONL).")
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.in_scope_only:
        rows = [r for r in rows if r.get("in_scope")]
    rows.sort(key=lambda r: r.get("property_id") or 0, reverse=True)

    out = args.out or SOURCE.with_suffix(".csv")
    extra = sorted({k for r in rows for k in r} - set(COLUMNS))
    header = [*COLUMNS, *extra]

    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flat = {
                k: ("" if v is None else ",".join(map(str, v)) if isinstance(v, list) else v)
                for k, v in row.items()
            }
            writer.writerow(flat)

    in_scope = sum(1 for r in rows if r.get("in_scope"))
    print(f"wrote {out.relative_to(ROOT)}")
    print(f"  {len(rows):,} rows  ({in_scope:,} in scope, {len(rows) - in_scope:,} excluded)")
    print(f"  {len(header)} columns")
    if extra:
        print(f"  columns not in the preferred order, appended: {extra}")


if __name__ == "__main__":
    main()
