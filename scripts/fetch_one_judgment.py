"""Fetch a single court judgment from Indian Kanoon and save as structured JSON.

This script is the foundation of the IndicCrimLawLLM ingestion pipeline. It
fetches one judgment from indiankanoon.org, parses metadata (court, date,
bench, cited statutes and cases) and writes a structured record to
``data/raw/{doc_id}.json``. Later stages of the pipeline will scale this up
to tens of thousands of judgments.

Usage
-----
Run from the project root with the project venv activated::

    python scripts/fetch_one_judgment.py
    python scripts/fetch_one_judgment.py https://indiankanoon.org/doc/1560742/
    python scripts/fetch_one_judgment.py 1560742

The default target is Arnesh Kumar v. State of Bihar (2014), a landmark
Supreme Court decision on arrest and bail under Section 498A IPC / Section
41 CrPC.

Policy
------
One request per invocation, 2-second politeness delay, identifying
User-Agent, no proxies, no evasion. Do not use this script in a loop to
scrape in bulk; a dedicated rate-limited crawler will replace it.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.extractors.statutes import extract_statutes  # noqa: E402

DEFAULT_URL = "https://indiankanoon.org/doc/2982624/"
USER_AGENT = (
    "IndicCrimLawLLM Research Bot "
    "(github.com/ChaitanyaKis/indic-criminal-law-llm)"
)
REQUEST_DELAY_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 30

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"

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


def extract_doc_id(url: str) -> str | None:
    m = re.search(r"/doc/(\d+)", url)
    return m.group(1) if m else None


def fetch(url: str) -> str:
    log.info("Sleeping %.1fs before request (politeness delay)", REQUEST_DELAY_SECONDS)
    time.sleep(REQUEST_DELAY_SECONDS)
    log.info("GET %s", url)
    resp = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Fetch failed: HTTP {resp.status_code} for {url}\n"
            f"First 200 chars of body: {resp.text[:200]!r}"
        )
    return resp.text


def _clean_ws(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def parse_title(soup: BeautifulSoup) -> str | None:
    for sel in ("h2.doc_title", "h2", "title"):
        node = soup.select_one(sel)
        if node and node.get_text(strip=True):
            title = node.get_text(" ", strip=True)
            return re.sub(r"\s+-\s+Indian Kanoon\s*$", "", title).strip()
    log.warning("Could not extract title")
    return None


def parse_court(soup: BeautifulSoup) -> str | None:
    node = soup.select_one("h2.docsource_main, .docsource, .docsource_main")
    if node:
        return node.get_text(" ", strip=True)
    # Fallback: infer from title
    title_node = soup.select_one("title")
    if title_node:
        t = title_node.get_text(" ", strip=True)
        if "Supreme Court" in t:
            return "Supreme Court of India"
        m = re.search(r"([A-Z][A-Za-z ]*High Court)", t)
        if m:
            return m.group(1).strip()
    log.warning("Could not extract court")
    return None


MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def parse_date(soup: BeautifulSoup, raw_text: str) -> str | None:
    # Indian Kanoon often puts the date in the title line or in a docsource sibling.
    # Try a few common patterns.
    candidates: list[str] = []
    title_node = soup.select_one("title")
    if title_node:
        candidates.append(title_node.get_text(" ", strip=True))
    h2 = soup.select_one("h2.doc_title, h2")
    if h2:
        candidates.append(h2.get_text(" ", strip=True))
    # First ~2000 chars of body text sometimes contain the pronouncement date.
    candidates.append(raw_text[:2000])

    for text in candidates:
        m = re.search(
            r"\b(\d{1,2})\s+"
            r"(January|February|March|April|May|June|July|August|"
            r"September|October|November|December)[,]?\s+(\d{4})\b",
            text, flags=re.IGNORECASE,
        )
        if m:
            day = int(m.group(1))
            month = MONTHS[m.group(2).lower()]
            year = int(m.group(3))
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                continue
        m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date().isoformat()
            except ValueError:
                continue
    log.warning("Could not parse judgment date")
    return None


def parse_bench(soup: BeautifulSoup) -> list[str]:
    # Indian Kanoon sometimes labels bench as "Bench:" in a .doc_bench or near docsource.
    judges: list[str] = []
    for sel in (".doc_bench", ".docsource_main + p", ".docsource + p"):
        node = soup.select_one(sel)
        if node:
            txt = node.get_text(" ", strip=True)
            txt = re.sub(r"^Bench\s*:\s*", "", txt, flags=re.IGNORECASE)
            parts = [p.strip() for p in re.split(r",| and ", txt) if p.strip()]
            if parts:
                judges = parts
                break
    if not judges:
        log.warning("Could not extract bench")
    return judges


def parse_full_text(soup: BeautifulSoup) -> str:
    # Indian Kanoon wraps the judgment body in #doc_content / .judgments.
    container = (
        soup.select_one("div.judgments")
        or soup.select_one("#doc_content")
        or soup.select_one(".doc_content")
        or soup.body
    )
    if container is None:
        return ""
    for tag in container.select("script, style"):
        tag.decompose()
    text = container.get_text("\n", strip=True)
    return _clean_ws(text)


def parse_cases_cited(soup: BeautifulSoup, source_doc_id: str | None) -> list[str]:
    ids: set[str] = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        m = re.search(r"/doc/(\d+)", href)
        if m:
            did = m.group(1)
            if did != source_doc_id:
                ids.add(did)
    return sorted(ids)


def parse_judgment(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    doc_id = extract_doc_id(source_url)
    full_text = parse_full_text(soup)
    return {
        "doc_id": doc_id,
        "title": parse_title(soup),
        "court": parse_court(soup),
        "date": parse_date(soup, full_text),
        "bench": parse_bench(soup),
        "full_text": full_text,
        "statutes_cited": extract_statutes(full_text),
        "cases_cited": parse_cases_cited(soup, doc_id),
        "source_url": source_url,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


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
    html = fetch(url)
    record = parse_judgment(html, url)
    out_path = save(record)
    print_summary(record, out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
