"""Run listing discovery and write the reference list.

Usage:
    uv run python scripts/run_discover.py                 # full walk
    uv run python scripts/run_discover.py --max-pages 3   # trial run
    uv run python scripts/run_discover.py --start-page 61 # resume after an outage
    uv run python scripts/run_discover.py --refresh       # fresh snapshot, ignore cache

References are streamed to the output file as they are found, so an outage partway
through does not discard the pages already fetched. Re-running is cheap: pages already
in the cache cost no network request, so a resume only pays for what it has not seen.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import asdict
from pathlib import Path

import yaml
from lhp.scrape.discover import Discoverer, redact_personal_fields
from lhp.scrape.fetch import FetchConfig, Fetcher, summarise_log

ROOT = Path(__file__).resolve().parents[1]


def build_fetcher(config: dict) -> Fetcher:
    """Construct a Fetcher from the scrape config, with redaction enabled."""
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
            # D-22: agent contact fields are stripped before anything is cached.
            body_filter=redact_personal_fields,
        )
    )


def main() -> None:
    """Discover listings, streaming them to the configured JSONL output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=ROOT / "config" / "scrape.yaml", type=Path)
    parser.add_argument("--max-pages", type=int, help="Override the config guard.")
    parser.add_argument("--page-size", type=int, help="Override the configured page size.")
    parser.add_argument("--start-page", type=int, default=1, help="Resume from this page.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Bypass the cache and re-request every page, for a fresh snapshot.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if args.max_pages is not None:
        config["discovery"]["max_pages"] = args.max_pages
    if args.page_size is not None:
        config["discovery"]["page_size"] = args.page_size

    fetcher = build_fetcher(config)
    discoverer = Discoverer(config, fetcher)
    output = ROOT / config["paths"]["discovery_output"]
    output.parent.mkdir(parents=True, exist_ok=True)

    # Streamed, not collected then written: an outage on page 60 must not discard the
    # fifty-nine pages already paid for.
    started = time.monotonic()
    written = 0
    mode = "a" if args.start_page > 1 else "w"
    with output.open(mode, encoding="utf-8") as handle:
        for ref in discoverer.run(start_page=args.start_page, refresh=args.refresh):
            handle.write(json.dumps(asdict(ref), sort_keys=True) + "\n")
            written += 1
    elapsed = time.monotonic() - started

    pages = max(discoverer.last_page - args.start_page + 1, 0)
    print(f"\ndiscovered : {written} listings across {pages} pages")
    if pages:
        print(f"elapsed    : {elapsed:.1f}s  ({elapsed / pages:.1f}s per page)")
    print(f"written to : {output.relative_to(ROOT)}  (mode: {mode})")
    print(f"stopped    : {discoverer.stopped_reason}")

    tally = summarise_log(ROOT / config["paths"]["log_path"])
    if tally:
        print("\nrequest log, by outcome:")
        for outcome, count in tally.items():
            print(f"  {outcome:<16} {count}")

    # Only a walk that ran to the end of the inventory may be judged against the
    # stopping rule. Any other stop reason makes the count a lower bound.
    if discoverer.stopped_reason != "exhausted":
        print(
            f"\nWalk did not complete ({discoverer.stopped_reason}), so {written} is a lower "
            f"bound, not the inventory. Re-run to resume — cached pages cost no requests."
        )
        return

    floor = config["stopping"]["floor"]
    target = config["stopping"]["target_listings"]
    if written < floor:
        print(f"\nBELOW FLOOR ({floor}). PLAN section 8: stop and reconsider the source.")
    elif written < target:
        print(
            f"\nAbove the {floor} floor, below the {target} target. "
            "Quality outranks quantity here."
        )
    else:
        print(f"\nAt or above the {target} target.")


if __name__ == "__main__":
    main()
