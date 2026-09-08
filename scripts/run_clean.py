"""Run stage 2 cleaning end to end and write every artefact it owns.

Usage, from the repository root::

    python scripts/run_clean.py

Reads ``data/interim/listings.jsonl`` and writes:

* ``data/processed/listings.parquet`` + ``.csv``           the analysis set
* ``data/processed/listings_excluded.parquet`` + ``.csv``  every dropped row, with a reason
* ``reports/stage2-reconciliation.md``                     the run's own counts
* ``data/sample/listings_sample.parquet`` + ``.csv``       synthetic rows, committed (D-23)

Nothing here writes to ``data/raw`` or ``data/interim``. The whole stage is reproducible
from the interim file, which is itself reproducible from the cache.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lhp.clean import (
    reconciliation,
    run_cleaning,
    synthesise_sample,
    write_processed,
    write_reconciliation,
)

DEFAULT_INTERIM = Path("data/interim/listings.jsonl")
DEFAULT_PROCESSED = Path("data/processed")
DEFAULT_REPORT = Path("reports/stage2-reconciliation.md")
DEFAULT_SAMPLE = Path("data/sample")


def main() -> None:
    """Run the pipeline and report what was written."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interim", type=Path, default=DEFAULT_INTERIM)
    parser.add_argument("--processed", type=Path, default=DEFAULT_PROCESSED)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--sample-dir", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--sample-rows", type=int, default=200)
    parser.add_argument(
        "--no-sample",
        action="store_true",
        help="Skip regenerating data/sample. The sample is committed and seeded, so a "
        "re-run should produce an identical file; use this when you want to be certain "
        "the working tree is untouched.",
    )
    args = parser.parse_args()

    if not args.interim.exists():
        raise SystemExit(
            f"{args.interim} not found. Stage 1 produces it: python scripts/run_parse.py"
        )

    frame, reports = run_cleaning(str(args.interim))
    print(reconciliation(reports))
    print()

    written = write_processed(frame, str(args.processed))
    for name, description in written.items():
        print(f"  {name:<20} {description}")

    report_path = write_reconciliation(reports, str(args.report))
    print(f"  {'reconciliation':<20} {report_path}")

    if not args.no_sample:
        sample = synthesise_sample(frame, n_rows=args.sample_rows)
        args.sample_dir.mkdir(parents=True, exist_ok=True)
        sample.to_parquet(args.sample_dir / "listings_sample.parquet", index=False)
        sample.to_csv(args.sample_dir / "listings_sample.csv", index=False)
        print(
            f"  {'synthetic sample':<20} {args.sample_dir / 'listings_sample.parquet'} "
            f"({len(sample):,} rows)"
        )


if __name__ == "__main__":
    main()
