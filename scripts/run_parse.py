"""Parse every cached listing page in the window into rows, and report coverage.

Reads from the cache rather than the network, so this is cheap to re-run and a parser
change never costs a re-fetch. Output is `data/interim/listings.jsonl`: one row per page
that parsed, carrying ``in_scope`` and ``scope_reason`` so the cleaning stage decides what
to keep. Nothing is dropped here — a row excluded silently is a row nobody can account for.

The summary is the evidence for the stage 1 exit criteria: coverage against discovered
URLs, and every failure categorised.

Usage:
    uv run python scripts/run_parse.py
    uv run python scripts/run_parse.py --limit 500   # quick check
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import time
from pathlib import Path

import yaml

from lhp.scrape.fetch import url_key
from lhp.scrape.parse import parse_page

ROOT = Path(__file__).resolve().parents[1]


def cached_body(cache_dir: Path, url: str) -> tuple[str | None, int | None]:
    """Return the cached body and status for a URL, or (None, None) if not cached."""
    key = url_key(url)
    path = cache_dir / key[:2] / key[2:4] / f"{key}.json.gz"
    if not path.exists():
        return None, None
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload.get("body"), payload.get("status")


def percentile(values: list[float], fraction: float) -> float:
    """Return the value at a fraction through a sorted copy of ``values``."""
    ordered = sorted(values)
    return ordered[int(fraction * (len(ordered) - 1))]


def main() -> None:
    """Parse the window and write rows plus a coverage summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=ROOT / "config" / "scrape.yaml", type=Path)
    parser.add_argument("--limit", type=int, help="Parse only this many, for a quick check.")
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    scope = config["scope"]
    cache_dir = ROOT / config["paths"]["cache_dir"]

    refs = [
        json.loads(line)
        for line in (ROOT / config["paths"]["discovery_output"])
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    window = sorted(
        (
            r
            for r in refs
            if scope["min_property_id"] <= r["property_id"] <= scope["max_property_id"]
        ),
        key=lambda r: r["property_id"],
        reverse=True,
    )
    if args.limit:
        window = window[: args.limit]

    out = ROOT / "data" / "interim" / "listings.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    not_cached = 0
    bad_status: collections.Counter[int] = collections.Counter()
    failures: collections.Counter[str] = collections.Counter()
    out_of_scope: collections.Counter[str] = collections.Counter()
    parsed = in_scope = removed = 0
    seen: set[int] = set()
    duplicates = 0

    with out.open("w", encoding="utf-8") as handle:
        for ref in window:
            body, status = cached_body(cache_dir, ref["url"])
            if body is None:
                not_cached += 1
                continue
            if status != 200:
                bad_status[status] += 1
                continue
            result = parse_page(body, ref)
            if not result.parsed:
                if result.reason == "listing_removed":
                    removed += 1
                else:
                    failures[result.reason or "unknown"] += 1
                continue
            parsed += 1
            if result.property_id in seen:
                duplicates += 1
            seen.add(result.property_id)
            if result.in_scope:
                in_scope += 1
            else:
                out_of_scope[result.reason or "unknown"] += 1
            row = dict(result.row)
            row["in_scope"] = result.in_scope
            row["scope_reason"] = result.reason
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    elapsed = time.monotonic() - started
    # Two coverage figures, and the strict one is the headline. Excluding anything from the
    # denominator requires knowing WHY a page is unusable, and a "Property Not Found"
    # template is not proof a listing was removed: 969 pages carrying it on 6 Sep 2026
    # returned real listings when re-fetched. Where the strict figure already clears the
    # gate, the exclusion is not needed and is not relied on. See LESSONS L-20.
    fetched_ok = len(window) - not_cached - sum(bad_status.values())
    live = fetched_ok - removed

    print(f"parsed {parsed:,} pages in {elapsed:.0f}s\n")
    print("COVERAGE (stage 1 exit criterion: >= 95% of discovered URLs parsed)")
    print(f"  discovered in window        {len(window):,}")
    print(f"  not cached                  {not_cached:,}")
    for status, count in sorted(bad_status.items()):
        print(f"  cached but HTTP {status}        {count:,}")
    print(f"  fetched successfully        {fetched_ok:,}   <- strict denominator")
    print(f"  parsed successfully         {parsed:,}")
    if fetched_ok:
        strict = 100 * parsed / fetched_ok
        print(f"  COVERAGE (strict)           {strict:.2f}%   {'PASS' if strict >= 95 else 'FAIL'}")
    print(f"\n  unrecoverable soft 404      {removed:,}")
    if live and removed:
        print(f"  coverage excluding those    {100 * parsed / live:.2f}%   (not relied upon)")
    print(f"  parse failures              {sum(failures.values()):,}  {dict(failures)}")
    print(f"  duplicate property ids      {duplicates:,}")
    if removed:
        share = 100 * removed / fetched_ok
        print(
            f"\n  {removed:,} listings ({share:.2f}%) still return Ilaan's "
            f'"Property Not Found" template after exhausting retries. Whether these are '
            f"genuinely delisted or persistently failing is NOT established — the same "
            f"template was served transiently for 969 live listings. Reported as an "
            f"unexplained gap, not as removals."
        )

    print("\nSCOPE (verified from the page, never the URL or the API)")
    print(f"  in scope                    {in_scope:,}")
    for reason, count in out_of_scope.most_common():
        print(f"  excluded: {reason:<18} {count:,}")

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    kept = [r for r in rows if r["in_scope"]]
    print(f"\nFIELD COMPLETENESS ON {len(kept):,} IN-SCOPE ROWS")
    for column in (
        "price", "area", "area_unit", "bedrooms", "bathrooms", "locality", "latitude",
        "longitude", "created_at", "year_built", "condition", "views", "address", "title",
    ):
        present = sum(1 for r in kept if r.get(column) not in (None, ""))
        print(f"  {column:<14} {100 * present / max(len(kept), 1):>6.1f}%")

    prices = [r["price"] for r in kept if r.get("price")]
    dates = sorted((r["created_at"] or "")[:10] for r in kept if r.get("created_at"))
    if prices:
        print("\nSANITY")
        print(
            f"  price   p1 {percentile(prices, 0.01):>14,.0f}"
            f"   median {percentile(prices, 0.5):>14,.0f}"
            f"   p99 {percentile(prices, 0.99):>16,.0f}"
        )
    if dates:
        print(f"  created {dates[0]} .. {dates[-1]}")
    print(f"\nwritten to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
