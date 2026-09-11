"""Fetch listing pages for the discovered references, newest first.

Discovery gives ids; this fetches the public listing page for each. Pages land in the
cache and are parsed separately by `parse.py`, so fetching and parsing can be re-run
independently and a parser change never costs a re-fetch.

Order matters. The source returns listings in strictly descending ``propertyId``, which is
descending recency, so fetching in that order means any stopping point yields a coherent
"most recent N" dataset rather than a ragged partial one.

Resumable by design: listings already recorded as fetched are skipped outright, and
anything else already in the cache costs no network request. Interrupting and re-running
is safe and cheap.

Usage:
    uv run python scripts/run_scrape.py                  # the configured window
    uv run python scripts/run_scrape.py --min-id 614378  # a tighter window
    uv run python scripts/run_scrape.py --limit 500      # a bounded trial
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import ctypes
import json
import logging
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import yaml

from lhp.scrape.discover import redact_personal_fields
from lhp.scrape.fetch import FetchConfig, Fetcher, FetchFailed, summarise_log
from lhp.scrape.parse import soft_404_reason

ROOT = Path(__file__).resolve().parents[1]

#: Windows power-request flags. ES_CONTINUOUS makes the state persist until cleared;
#: ES_SYSTEM_REQUIRED asks Windows not to idle the system out while we hold it.
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


@contextlib.contextmanager
def keep_awake(enabled: bool) -> Iterator[None]:
    """Ask Windows not to suspend the machine for the duration of the run.

    A multi-hour unattended fetch is exactly what Modern Standby (S0 low-power idle)
    interrupts: the "never sleep" timeouts and the lid-close action do not govern it, so a
    machine left alone suspends the process regardless of the power plan. A power request
    is the supported way to say "I am working"; Windows releases it when we exit, and
    nothing about the machine's configuration is changed.

    A no-op on every other platform, and on Windows if the request is refused — the run
    then behaves exactly as it did before, resuming from cache after any interruption.

    Args:
        enabled: Whether to hold the request.

    Yields:
        None, for the duration of the run.

    """
    if not enabled or sys.platform != "win32":
        yield
        return
    kernel32 = ctypes.windll.kernel32
    kernel32.SetThreadExecutionState.argtypes = [ctypes.c_uint32]
    kernel32.SetThreadExecutionState.restype = ctypes.c_uint32
    granted = kernel32.SetThreadExecutionState(_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
    if not granted:
        logging.warning("power request refused; the machine may still enter Modern Standby")
    else:
        print("holding a power request: the machine will not idle out while this runs")
    try:
        yield
    finally:
        kernel32.SetThreadExecutionState(_ES_CONTINUOUS)


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


def load_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into a list, tolerating a trailing partial line.

    A run interrupted mid-write can leave the last line incomplete. Dropping it is
    correct: that listing is simply re-fetched, and the cache makes that free.
    """
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            logging.warning("dropping an incomplete final line in %s", path.name)
    return rows


def main() -> None:
    """Fetch listing pages, newest first, recording one outcome row per listing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=ROOT / "config" / "scrape.yaml", type=Path)
    parser.add_argument("--min-id", type=int, help="Override the configured window floor.")
    parser.add_argument("--max-id", type=int, help="Override the configured window ceiling.")
    parser.add_argument("--limit", type=int, help="Stop after this many listings.")
    parser.add_argument("--every", type=int, default=100, help="Progress interval.")
    parser.add_argument(
        "--allow-sleep",
        action="store_true",
        help="Do not hold a power request; let the machine suspend as it normally would.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    scope = config["scope"]
    min_id = args.min_id if args.min_id is not None else scope["min_property_id"]
    max_id = args.max_id if args.max_id is not None else scope.get("max_property_id")

    # Completion is not tracked in a second file. The cache is the single source of truth:
    # a page already held returns in about 0.1s, and one that fails content validation is
    # re-fetched. A separate "done" marker is what let 969 invalid pages stay marked
    # complete on 6 Sep 2026 — the marker said HTTP 200 and nothing re-examined the content.
    refs = load_jsonl(ROOT / config["paths"]["discovery_output"])
    window = sorted(
        (
            r
            for r in refs
            if r["property_id"] >= min_id and (max_id is None or r["property_id"] <= max_id)
        ),
        key=lambda r: r["property_id"],
        reverse=True,
    )

    out = ROOT / "data" / "raw" / "pages.jsonl"
    todo = window[: args.limit] if args.limit else window

    ceiling = f" and <= {max_id}" if max_id is not None else ""
    print(f"window     : property_id >= {min_id}{ceiling}")
    print(f"in window  : {len(window):,} of {len(refs):,} discovered")
    print(f"to process : {len(todo):,}  (cached pages are revalidated, not re-requested)\n")
    if not todo:
        print("nothing to do.")
        return

    fetcher = build_fetcher(config)
    started = time.monotonic()
    counts: dict[str, int] = {}
    # A rolling window, not a cumulative average. A laptop that suspends mid-run resumes
    # correctly but leaves hours of wall-clock in the total, which would poison a
    # cumulative rate and produce an alarming, meaningless ETA.
    recent: collections.deque[float] = collections.deque(maxlen=200)

    with keep_awake(not args.allow_sleep), out.open("w", encoding="utf-8") as handle:
        for i, ref in enumerate(todo, start=1):
            began = time.monotonic()
            try:
                response = fetcher.get(ref["url"])
                status, size, error = response.status, len(response.body), None
            except FetchFailed as exc:
                status, size, error = None, 0, str(exc)
            recent.append(time.monotonic() - began)
            key = "ok" if status == 200 else (f"http_{status}" if status else "failed")
            counts[key] = counts.get(key, 0) + 1
            handle.write(
                json.dumps(
                    {
                        "property_id": ref["property_id"],
                        "url": ref["url"],
                        "status": status,
                        "bytes": size,
                        "error": error,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            if i % args.every == 0:
                handle.flush()
                # Median of the rolling window: robust to the occasional slow request and
                # to a suspend/resume, unlike a mean over total elapsed time.
                ordered = sorted(recent)
                rate = ordered[len(ordered) // 2] if ordered else 0.0
                left = (len(todo) - i) * rate / 60
                summary = "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
                print(
                    f"  {i:>6,}/{len(todo):,}  {rate:.2f}s each  "
                    f"~{left:.0f} min left   {summary}"
                )

    elapsed = time.monotonic() - started
    print(f"\nfetched {len(todo):,} listings in {elapsed / 60:.0f} min of wall clock")
    for key, value in sorted(counts.items()):
        print(f"  {key:<12} {value:,}")
    tally = summarise_log(ROOT / config["paths"]["log_path"])
    if tally:
        print("\nrequest log, by outcome (cumulative across all runs):")
        for outcome, count in tally.items():
            print(f"  {outcome:<16} {count:,}")
    print(f"\nwritten to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
