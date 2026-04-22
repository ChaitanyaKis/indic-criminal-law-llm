"""Fetch a single court judgment from Indian Kanoon and save as JSON.

Thin CLI wrapper over :class:`src.scrapers.indian_kanoon.IndianKanoonScraper`.
The bulk pipeline (``scripts/scrape_sc_criminal.py``) uses the same class
directly; this script exists for one-off manual fetches and as the original
"proof of life" entry point.

Usage
-----
Run from the project root with the project venv activated::

    python scripts/fetch_one_judgment.py
    python scripts/fetch_one_judgment.py https://indiankanoon.org/doc/1560742/
    python scripts/fetch_one_judgment.py 1560742

The default target is Arnesh Kumar v. State of Bihar (2014), the Supreme
Court's landmark decision on arrest and bail under IPC 498A / CrPC 41.

Policy
------
One request per invocation, 3-second politeness delay, identifying
User-Agent, no proxies, no header rotation. For more than a handful of
documents use ``scripts/scrape_sc_criminal.py`` which handles state,
retries, and robots.txt.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.scrapers.indian_kanoon import IndianKanoonScraper  # noqa: E402

DEFAULT_URL = "https://indiankanoon.org/doc/2982624/"
OUTPUT_DIR = _PROJECT_ROOT / "data" / "raw"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("fetch_one_judgment")


def normalize_to_url(arg: str) -> str:
    """Accept a full URL or a bare doc id and return a canonical URL."""
    arg = arg.strip()
    if arg.startswith("http://") or arg.startswith("https://"):
        return arg
    if arg.isdigit():
        return f"https://indiankanoon.org/doc/{arg}/"
    raise ValueError(f"Cannot interpret argument as URL or doc id: {arg!r}")


def save(record: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = record.get("doc_id") or "unknown"
    out = OUTPUT_DIR / f"{doc_id}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def print_summary(record: dict, out_path: Path) -> None:
    text = record.get("full_text") or ""
    word_count = len(text.split())
    print("=" * 60)
    print(f"Title:   {record.get('title')}")
    print(f"Court:   {record.get('court')}")
    print(f"Date:    {record.get('date')}")
    print(f"Bench:   {', '.join(record.get('bench') or []) or '(none parsed)'}")
    print(f"Text:    {len(text):,} chars / ~{word_count:,} words")
    print(f"Statutes cited: {len(record.get('statutes_cited') or [])}")
    print(f"Cases cited:    {len(record.get('cases_cited') or [])}")
    print(f"Output:  {out_path}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "target",
        nargs="?",
        default=DEFAULT_URL,
        help="Indian Kanoon URL or bare doc id (default: Arnesh Kumar v. State of Bihar)",
    )
    args = parser.parse_args(argv)

    url = normalize_to_url(args.target)
    scraper = IndianKanoonScraper()
    record = scraper.get_judgment(url)
    out_path = save(record)
    print_summary(record, out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
