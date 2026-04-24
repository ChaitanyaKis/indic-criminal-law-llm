"""Retroactively re-apply the criminal-case filter to already-saved docs.

Does NOT re-fetch anything. Only reads the on-disk judgment JSONs and
re-computes ``is_criminal()`` against the current filter code. Used to
propagate filter-logic fixes (e.g. the JJ Act addition, the body-header
case-style check) back through previously-saved documents.

Safety
------
The scraper may be running concurrently. This script is designed to
co-exist:

- Judgment JSONs are read only (atomic writes from the scraper mean we
  always see a complete file or no file at all).
- When updating the state file (non-dry-run), we re-read it just before
  writing and merge our delta — so any docs the scraper added during
  rescore are preserved.

Usage
-----
::

    # Report the diff without touching anything
    python scripts/rescore_filter.py --dry-run

    # Apply the new confidence tiers to the state file
    python scripts/rescore_filter.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.scrapers.criminal_filter import is_criminal  # noqa: E402

DEFAULT_DATA_DIR = _PROJECT_ROOT / "data" / "raw" / "supreme_court"
DEFAULT_STATE_FILE = _PROJECT_ROOT / "data" / "raw" / "_state" / "scraped_sc.json"

log = logging.getLogger("rescore_filter")


# ---- State helpers (mirror the scraper's atomic write semantics) ------


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"docs": {}, "stats": {"by_year": {}}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state_atomic(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ---- Core rescore loop ------------------------------------------------


def _normalize_confidence(kept: bool, confidence: str) -> str:
    """Map the filter's (bool, tier) → the state-file confidence string."""
    return confidence if kept else "filtered"


def compute_transitions(
    data_dir: Path, state_docs: dict[str, Any],
) -> tuple[dict[str, list[str]], Counter[str]]:
    """Walk all JSONs under ``data_dir``, re-run the filter, and return
    ``(transitions, tier_totals)``.

    ``transitions`` keys are ``"old->new"`` strings; values are lists of
    doc_ids. ``unchanged`` is also a key (confidence preserved).
    ``tier_totals`` is a Counter of the NEW confidence across all docs.
    """
    transitions: dict[str, list[str]] = defaultdict(list)
    tier_totals: Counter[str] = Counter()

    files = sorted(Path(data_dir).rglob("*.json"))
    log.info("Scanning %d judgment files under %s", len(files), data_dir)

    for i, f in enumerate(files):
        if i and i % 1000 == 0:
            log.info("  %d / %d processed", i, len(files))
        doc_id = f.stem
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log.warning("Skipping unreadable %s: %s", f, e)
            continue
        kept, new_conf_tier = is_criminal(rec)
        new_conf = _normalize_confidence(kept, new_conf_tier)
        tier_totals[new_conf] += 1
        old_conf = (state_docs.get(doc_id) or {}).get("confidence", "unknown")
        if old_conf == new_conf:
            transitions["unchanged"].append(doc_id)
        else:
            transitions[f"{old_conf}->{new_conf}"].append(doc_id)
    return transitions, tier_totals


def apply_transitions(
    state_file: Path, transitions: dict[str, list[str]],
) -> int:
    """Re-read the state file (to catch any scraper writes during
    rescore), apply the confidence updates, and atomically save.

    Returns the number of docs whose confidence was actually changed."""
    current = load_state(state_file)
    docs = current.setdefault("docs", {})
    changed = 0
    for key, doc_ids in transitions.items():
        if key == "unchanged":
            continue
        try:
            old_conf, new_conf = key.split("->")
        except ValueError:
            continue
        for did in doc_ids:
            info = docs.get(did)
            if info is None:
                # Scraper may have newly added this; don't touch
                continue
            if info.get("confidence") != old_conf:
                # Scraper revised it during rescore; leave alone
                continue
            info["confidence"] = new_conf
            changed += 1

    # Recompute aggregate counts from the (possibly scraper-extended) docs
    stats = current.setdefault("stats", {})
    all_conf = Counter(
        (info or {}).get("confidence") for info in docs.values()
    )
    stats["criminal_high_conf"] = all_conf.get("high", 0)
    stats["criminal_medium_conf"] = all_conf.get("medium", 0)
    stats["filtered_out"] = all_conf.get("filtered", 0)

    save_state_atomic(state_file, current)
    return changed


# ---- CLI --------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Retroactively re-score saved judgments with the current filter.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    p.add_argument("--dry-run", action="store_true",
                   help="Report the diff without touching the state file.")
    return p.parse_args(argv)


def _print_report(
    transitions: dict[str, list[str]],
    tier_totals: Counter[str],
    dry_run: bool,
) -> None:
    unchanged = len(transitions.get("unchanged", []))
    total = sum(len(v) for v in transitions.values())
    changed = total - unchanged
    bar = "=" * 72
    print(bar)
    print(f"Rescore summary  (dry_run={dry_run})")
    print(bar)
    print(f"Total judgments scanned:     {total}")
    print(f"Unchanged:                   {unchanged}")
    print(f"Changed:                     {changed}")
    print()
    print("Transitions (old -> new):")
    for key in sorted(transitions):
        if key == "unchanged":
            continue
        ids = transitions[key]
        sample = ", ".join(ids[:3]) + (" ..." if len(ids) > 3 else "")
        print(f"  {key:<30} {len(ids):>6}   e.g. {sample}")
    print()
    print("Final tier distribution (after rescore):")
    for k, v in sorted(tier_totals.items()):
        print(f"  {k:<12} {v:>6}")
    print(bar)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    state = load_state(args.state_file)
    state_docs = state.get("docs", {}) or {}
    log.info("State file has %d doc entries", len(state_docs))

    transitions, tier_totals = compute_transitions(args.data_dir, state_docs)
    _print_report(transitions, tier_totals, args.dry_run)

    if args.dry_run:
        print("\n(Dry run — state file NOT modified. Re-run without --dry-run to apply.)")
        return 0

    changed = apply_transitions(args.state_file, transitions)
    print(f"\nState file updated: {changed} confidence fields re-scored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
