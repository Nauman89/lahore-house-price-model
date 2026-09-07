"""Fetch a stratified sample of listing pages, to size the full run before committing to it.

The discovery endpoint returns listings in strictly descending ``propertyId`` order, i.e.
newest first (verified 5 Sep 2026 across 400 pages). This script samples evenly through
that order, so the result answers four questions at once:

* how many older listings have been removed (the 404 rate, by age band);
* how far back a given number of listings actually reaches (the ``createdAt`` spread);
* what a page fetch really costs against a slow source;
* and it leaves cached pages for `parse.py` to be developed against.

Unlike discovery, a listing that cannot be fetched is **recorded and skipped**, not treated
as fatal. A gap in discovery is an invisible coverage hole; a failed listing here is a
countable outcome, which is what the stage 1 exit criteria ask for.

Usage:
    uv run python scripts/sample_listings.py            # 40 listings, 5 bands
    uv run python scripts/sample_listings.py --n 100
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import yaml
from lhp.scrape.discover import redact_personal_fields
from lhp.scrape.fetch import FetchConfig, Fetcher, FetchFailed
from lhp.scrape.parse import soft_404_reason

ROOT = Path(__file__).resolve().parents[1]


def build_fetcher(config: dict) -> Fetcher:
    """Construct a Fetcher from the scrape config."""
    settings = config["fetch"]
    paths = config["paths"]
    return Fetcher(
        FetchConfig(
            user_agent=settings["user_agent"],
            cache_dir=ROOT / paths["cache_dir"],
            log_path=ROOT / paths["log_path"],
            min_delay=settings["min_delay"],
            max_delay=settings["max_delay"],
            timeout=settings["timeout"],
            max_retries=settings["max_retries"],
            backoff_base=settings["backoff_base"],
            body_filter=redact_personal_fields,
            # L-18: a 200 is not evidence of content. Ilaan serves a
            # "Property Not Found" template with 200 under load; it is retried,
            # never cached, and an already-cached one is treated as a miss.
            content_validator=soft_404_reason,
        )
    )


def stratify(refs: list[dict], n: int, bands: int) -> list[tuple[int, dict]]:
    """Pick an even spread of listings across the recency ordering.

    Args:
        refs: Discovery references, any order.
        n: Total listings to sample.
        bands: Number of equal-sized age bands to spread them across.

    Returns:
        ``(band_index, ref)`` pairs, band 0 being the newest.

    """
    ordered = sorted(refs, key=lambda r: r["property_id"], reverse=True)
    per_band = max(n // bands, 1)
    size = len(ordered) / bands
    picked: list[tuple[int, dict]] = []
    for band in range(bands):
        start = int(band * size)
        stop = int((band + 1) * size)
        segment = ordered[start:stop]
        if not segment:
            continue
        step = max(len(segment) // per_band, 1)
        picked.extend((band, segment[i]) for i in range(0, len(segment), step)[:per_band])
    return picked


def main() -> None:
    """Fetch the sample and report what it cost and what came back."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=ROOT / "config" / "scrape.yaml", type=Path)
    parser.add_argument("--n", type=int, default=40, help="Listings to sample.")
    parser.add_argument("--bands", type=int, default=5, help="Age bands to spread across.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    fetcher = build_fetcher(config)

    refs = [
        json.loads(line)
        for line in (ROOT / config["paths"]["discovery_output"]).read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    sample = stratify(refs, args.n, args.bands)
    print(f"sampling {len(sample)} of {len(refs)} listings across {args.bands} age bands\n")

    results = []
    started = time.monotonic()
    for band, ref in sample:
        began = time.monotonic()
        try:
            response = fetcher.get(ref["url"])
            status, size, error = response.status, len(response.body), None
        except FetchFailed as exc:
            status, size, error = None, 0, str(exc)
        results.append(
            {
                "band": band,
                "property_id": ref["property_id"],
                "url": ref["url"],
                "status": status,
                "bytes": size,
                "seconds": round(time.monotonic() - began, 2),
                "error": error,
            }
        )
    elapsed = time.monotonic() - started

    out = ROOT / "data" / "raw" / "sample_pages.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    header = (
        f"{'band':<6}{'newest first':<16}{'ok':>5}{'404':>6}"
        f"{'other':>7}{'failed':>8}{'avg s':>8}"
    )
    print(header)
    for band in range(args.bands):
        rows = [r for r in results if r["band"] == band]
        if not rows:
            continue
        ok = sum(1 for r in rows if r["status"] == 200)
        gone = sum(1 for r in rows if r["status"] == 404)
        other = sum(1 for r in rows if r["status"] not in (200, 404, None))
        failed = sum(1 for r in rows if r["status"] is None)
        avg = sum(r["seconds"] for r in rows) / len(rows)
        ids = [r["property_id"] for r in rows]
        label = f"{max(ids)}-{min(ids)}"
        print(f"{band:<6}{label:<16}{ok:>5}{gone:>6}{other:>7}{failed:>8}{avg:>8.1f}")

    ok_rows = [r for r in results if r["status"] == 200]
    print(f"\ntotal {len(results)} pages in {elapsed:.0f}s  ({elapsed / len(results):.1f}s each)")
    if ok_rows:
        avg_kb = sum(r["bytes"] for r in ok_rows) / len(ok_rows) / 1024
        print(f"median page {avg_kb:.0f} KB")
        for target in (5000, 8000, 20000):
            hours = target * (elapsed / len(results)) / 3600
            print(f"  {target:>6} listings would take about {hours:.1f} hours")
    print(f"\nwritten to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
