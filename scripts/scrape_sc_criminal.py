"""Bulk-scrape Supreme Court criminal judgments from Indian Kanoon.

Systematic year-by-year traversal of the SC case list, filtered for
criminal matters. Designed to be resumable (atomic state file) and to
run unattended for 24-48 hours.

Usage
-----
::

    # Smoke test (takes ~2-4 min with default 3s rate limit):
    python scripts/scrape_sc_criminal.py \\
        --start-year 2023 --end-year 2023 --limit-per-year 20

    # Full run:
    python scripts/scrape_sc_criminal.py \\
        --start-year 2015 --end-year 2024 --limit-per-year 2000

State and logs
--------------
- State:  ``data/raw/_state/scraped_sc.json`` (atomic, flushed every 10 docs)
- Output: ``data/raw/supreme_court/{year}/{doc_id}.json``
- Log:    ``logs/scrape_sc.log`` (rotating, 10 MB × 3 backups)

Graceful shutdown
-----------------
SIGINT (Ctrl+C) flushes state and exits cleanly. On Windows, a ``taskkill``
without ``/F`` raises the same handler. A hard kill (``/F``) is also safe —
the state file is updated atomically every 10 docs and at year boundaries.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import signal
import sys
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from tqdm import tqdm

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.scrapers.criminal_filter import is_criminal  # noqa: E402
from src.scrapers.indian_kanoon import (  # noqa: E402
    IndianKanoonScraper,
    RateLimitedError,
    RobotsDisallowed,
    ScraperError,
)
from src.scrapers.state import (  # noqa: E402
    atomic_save_state,
    load_state as _load_state_locked,
)

DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "data" / "raw" / "supreme_court"
STATE_PATH = _PROJECT_ROOT / "data" / "raw" / "_state" / "scraped_sc.json"
LOG_DIR = _PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "scrape_sc.log"

STATE_FLUSH_EVERY_N_DOCS = 10
CONSECUTIVE_429_THRESHOLD = 3
COOLDOWN_AFTER_RATELIMIT_SECONDS = 600  # 10 min

_shutdown_requested = False
log = logging.getLogger("scrape_sc")


# ---- Signal handling ---------------------------------------------------


def _install_sigint_handler() -> None:
    def _handler(signum: int, frame: Any) -> None:  # noqa: ARG001
        global _shutdown_requested
        if _shutdown_requested:
            log.warning("Second interrupt — exiting immediately")
            sys.exit(130)
        _shutdown_requested = True
        log.warning("SIGINT received — will finish current doc, flush state, exit")

    signal.signal(signal.SIGINT, _handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handler)


# ---- State file --------------------------------------------------------


def _fresh_state() -> dict[str, Any]:
    return {
        "version": 1,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_seen": 0,
            "criminal_high_conf": 0,
            "criminal_medium_conf": 0,
            "filtered_out": 0,
            "errors": 0,
            "by_year": {},
        },
        "docs": {},
        "processed_search_pages": {},
    }


def load_state(path: Path) -> dict[str, Any]:
    """Locked one-shot read with the same logging this script has had."""
    if not path.exists():
        log.info("No prior state at %s — starting fresh", path)
        return _fresh_state()
    state = _load_state_locked(path, default=_fresh_state())
    log.info(
        "Resuming from state: %d docs tracked, last_updated=%s",
        len(state.get("docs", {})),
        state.get("last_updated"),
    )
    return state


def _check_no_stale_lock(state_path: Path) -> None:
    """Refuse to start if a lock file already exists at the corresponding
    ``.lock`` path. Guards against the 'two scrapers running' incident
    by either catching an actively-held lock from another process or a
    stale lock left behind by a crashed run. The user is directed to
    delete the lock file manually if certain nothing else is using it.
    """
    lock_file = state_path.with_suffix(".lock")
    if lock_file.exists():
        raise RuntimeError(
            f"Lock file exists at {lock_file}. Either:\n"
            " - Another scraper or rescore is already running "
            "(check Get-Process python),\n"
            " - Or a previous run crashed and left a stale lock "
            "(delete the lock file manually if certain nothing else is running)."
        )


# ---- Logging -----------------------------------------------------------


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Remove any handlers left over from a prior run in the same interpreter.
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console)


# ---- Per-doc pipeline --------------------------------------------------


def _save_judgment(record: dict[str, Any], out_dir: Path, doc_id: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{doc_id}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def _process_one(
    scraper: IndianKanoonScraper,
    doc_id: str,
    url: str,
    year: int,
    output_dir: Path,
    state: dict[str, Any],
) -> str:
    """Fetch, parse, filter, save. Returns confidence ('high'|'medium'|'filtered')."""
    record = scraper.get_judgment(url)
    kept, confidence = is_criminal(record)
    year_key = str(year)
    year_stats = state["stats"]["by_year"].setdefault(
        year_key, {"seen": 0, "saved": 0, "errors": 0, "filtered": 0},
    )

    if kept:
        out_dir = output_dir / year_key
        out_path = _save_judgment(record, out_dir, doc_id)
        if confidence == "high":
            state["stats"]["criminal_high_conf"] += 1
        else:
            state["stats"]["criminal_medium_conf"] += 1
        year_stats["saved"] += 1
        state["docs"][doc_id] = {
            "year": year,
            "confidence": confidence,
            "path": str(out_path.relative_to(_PROJECT_ROOT)).replace("\\", "/"),
            "title": record.get("title"),
        }
        return confidence

    state["stats"]["filtered_out"] += 1
    year_stats["filtered"] += 1
    state["docs"][doc_id] = {
        "year": year,
        "confidence": "filtered",
        "path": None,
        "title": record.get("title"),
    }
    return "filtered"


# ---- Main loop ---------------------------------------------------------


def run(
    scraper: IndianKanoonScraper,
    state: dict[str, Any],
    start_year: int,
    end_year: int,
    limit_per_year: int | None,
    output_dir: Path,
) -> int:
    pbar = tqdm(total=None, desc="scrape_sc", unit="doc", dynamic_ncols=True)
    docs_since_flush = 0
    consecutive_429 = 0

    try:
        for year in range(start_year, end_year + 1):
            if _shutdown_requested:
                break
            log.info("=== Year %d ===", year)
            year_stats = state["stats"]["by_year"].setdefault(
                str(year), {"seen": 0, "saved": 0, "errors": 0, "filtered": 0},
            )

            for doc_id, url in scraper.search_by_year(year):
                if _shutdown_requested:
                    break
                if limit_per_year is not None and year_stats["saved"] >= limit_per_year:
                    log.info(
                        "year=%d: hit limit_per_year=%d (saved)",
                        year, limit_per_year,
                    )
                    break
                if doc_id in state["docs"]:
                    continue

                state["stats"]["total_seen"] += 1
                year_stats["seen"] += 1

                try:
                    confidence = _process_one(
                        scraper, doc_id, url, year, output_dir, state,
                    )
                    consecutive_429 = 0
                except RateLimitedError as e:
                    consecutive_429 += 1
                    state["stats"]["errors"] += 1
                    year_stats["errors"] += 1
                    log.warning(
                        "RateLimited on %s (consecutive=%d): %s",
                        url, consecutive_429, e,
                    )
                    if consecutive_429 >= CONSECUTIVE_429_THRESHOLD:
                        log.error(
                            "%d consecutive 429s — flushing state, sleeping %ds, then one retry",
                            consecutive_429, COOLDOWN_AFTER_RATELIMIT_SECONDS,
                        )
                        atomic_save_state(state, STATE_PATH)
                        time.sleep(COOLDOWN_AFTER_RATELIMIT_SECONDS)
                        try:
                            _process_one(
                                scraper, doc_id, url, year, output_dir, state,
                            )
                            consecutive_429 = 0
                        except Exception as retry_exc:  # noqa: BLE001
                            log.error(
                                "Still rate-limited after cooldown; exiting: %s",
                                retry_exc,
                            )
                            atomic_save_state(state, STATE_PATH)
                            return 2
                    continue
                except ScraperError as e:
                    state["stats"]["errors"] += 1
                    year_stats["errors"] += 1
                    log.error("ScraperError on %s: %s", url, e)
                except Exception as e:  # noqa: BLE001
                    state["stats"]["errors"] += 1
                    year_stats["errors"] += 1
                    log.exception("Unexpected error on %s: %s", url, e)
                finally:
                    pbar.update(1)
                    pbar.set_postfix(
                        year=year,
                        saved=year_stats["saved"],
                        filt=state["stats"]["filtered_out"],
                        err=state["stats"]["errors"],
                    )
                    docs_since_flush += 1
                    if docs_since_flush >= STATE_FLUSH_EVERY_N_DOCS:
                        atomic_save_state(state, STATE_PATH)
                        docs_since_flush = 0

            atomic_save_state(state, STATE_PATH)

    finally:
        pbar.close()
        atomic_save_state(state, STATE_PATH)

    return 0


# ---- CLI ---------------------------------------------------------------


def print_banner(args: argparse.Namespace, state: dict[str, Any]) -> None:
    border = "=" * 72
    print(border)
    print("IndicCrimLawLLM — Supreme Court Criminal Judgment Scraper")
    print(border)
    print(f"Years:           {args.start_year}-{args.end_year}")
    print(f"Limit per year:  {args.limit_per_year}")
    print(f"Rate limit:      {args.rate_limit:.1f}s (min {2.0}s)")
    print(f"Output dir:      {args.output_dir}")
    print(f"State file:      {STATE_PATH}")
    print(f"Log file:        {LOG_FILE}")
    print(f"Docs in state:   {len(state['docs'])}")
    print(f"Started at:      {datetime.now(timezone.utc).isoformat()}")
    print(border)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Bulk-scrape SC criminal judgments from Indian Kanoon.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--start-year", type=int, default=2015)
    p.add_argument("--end-year", type=int, default=2024)
    p.add_argument(
        "--limit-per-year", type=int, default=None,
        help="Stop a year after saving this many criminal docs. None = no cap.",
    )
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument(
        "--rate-limit", type=float, default=3.0,
        help="Seconds between requests (hard minimum: 2.0).",
    )
    args = p.parse_args(argv)

    if args.rate_limit < 2.0:
        p.error("--rate-limit must be >= 2.0 (politeness floor)")
    if args.end_year < args.start_year:
        p.error("--end-year must be >= --start-year")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # Seed RNG so randomized spot-checks downstream are reproducible within a run.
    random.seed(0)

    setup_logging()
    _install_sigint_handler()

    # Refuse to start if another process holds the state lock (or left
    # a stale one behind). This is the protection against the
    # "two scrapers running" incident.
    try:
        _check_no_stale_lock(STATE_PATH)
    except RuntimeError as e:
        log.error(str(e))
        return 4

    state = load_state(STATE_PATH)
    print_banner(args, state)

    scraper = IndianKanoonScraper(rate_limit_seconds=args.rate_limit)
    try:
        scraper.check_robots()
    except RobotsDisallowed as e:
        log.error("Aborting: %s", e)
        return 3

    try:
        return run(
            scraper=scraper,
            state=state,
            start_year=args.start_year,
            end_year=args.end_year,
            limit_per_year=args.limit_per_year,
            output_dir=args.output_dir,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("Fatal error: %s", e)
        atomic_save_state(state, STATE_PATH)
        return 1
    finally:
        print()
        print("Final stats:")
        print(json.dumps(state["stats"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
