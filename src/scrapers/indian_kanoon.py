"""Indian Kanoon scraper — class-based, rate-limited, robots-aware.

This is the core building block used by:
  - ``scripts/fetch_one_judgment.py`` (CLI wrapper for a single URL)
  - ``scripts/scrape_sc_criminal.py`` (bulk year-by-year Supreme Court run)

Discovered search-URL pattern
-----------------------------
Indian Kanoon's search page accepts a single ``formInput`` parameter whose
value is a space-separated list of ``key:value`` filters (the ``:`` is
URL-encoded as ``%3A``, spaces as ``+``). Pagination is 0-indexed via
``pagenum``::

    https://indiankanoon.org/search/
        ?formInput=doctypes%3Asupremecourt+fromdate%3A1-1-2023+todate%3A31-12-2023
        &pagenum=0

Result links on each page are ``<a href="/doc/{doc_id}/">`` anchors inside
``div.result_title``. Typical results-per-page is 10. When a page returns
no new result links, iteration terminates.

Date format in ``fromdate``/``todate`` is ``d-m-yyyy`` (no zero-padding).

Politeness
----------
- Rate limit: floor of 2 seconds between requests (configurable above).
- User-Agent: identifying research bot (no spoofing).
- robots.txt: fetched once at startup; ``/doc/`` and ``/search/`` must
  be allowed for the configured UA or we abort.
- Retries on 429/503 via tenacity (exponential backoff 4s → 60s, 5 tries).
- No proxies. No header rotation.
"""

from __future__ import annotations

import logging
import re
import time
import urllib.robotparser
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.extractors.statutes import extract_statutes

log = logging.getLogger(__name__)

BASE_URL = "https://indiankanoon.org"
SEARCH_PATH = "/search/"
DEFAULT_USER_AGENT = (
    "IndicCrimLawLLM Research Bot "
    "(github.com/ChaitanyaKis/indic-criminal-law-llm; research use only)"
)

_MIN_RATE_LIMIT_SECONDS = 2.0


class ScraperError(Exception):
    """Base for scraper-specific failures."""


class RateLimitedError(ScraperError):
    """HTTP 429 — the remote asked us to slow down."""


class ServerError(ScraperError):
    """HTTP 5xx — transient server failure worth retrying."""


class RobotsDisallowed(ScraperError):
    """robots.txt forbids the path we need."""


# ---- Judgment-page parsing helpers (module-level so they stay testable)


MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def _clean_ws(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def _parse_title(soup: BeautifulSoup) -> str | None:
    for sel in ("h2.doc_title", "h2", "title"):
        node = soup.select_one(sel)
        if node and node.get_text(strip=True):
            title = node.get_text(" ", strip=True)
            return re.sub(r"\s+-\s+Indian Kanoon\s*$", "", title).strip()
    return None


def _parse_court(soup: BeautifulSoup) -> str | None:
    node = soup.select_one("h2.docsource_main, .docsource, .docsource_main")
    if node:
        return node.get_text(" ", strip=True)
    title_node = soup.select_one("title")
    if title_node:
        t = title_node.get_text(" ", strip=True)
        if "Supreme Court" in t:
            return "Supreme Court of India"
        m = re.search(r"([A-Z][A-Za-z ]*High Court)", t)
        if m:
            return m.group(1).strip()
    return None


def _parse_date(soup: BeautifulSoup, raw_text: str) -> str | None:
    candidates: list[str] = []
    title_node = soup.select_one("title")
    if title_node:
        candidates.append(title_node.get_text(" ", strip=True))
    h2 = soup.select_one("h2.doc_title, h2")
    if h2:
        candidates.append(h2.get_text(" ", strip=True))
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
    return None


def _parse_bench(soup: BeautifulSoup) -> list[str]:
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
    return judges


def _parse_full_text(soup: BeautifulSoup) -> str:
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


def _parse_cases_cited(soup: BeautifulSoup, source_doc_id: str | None) -> list[str]:
    ids: set[str] = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        m = re.search(r"/doc/(\d+)", href)
        if m:
            did = m.group(1)
            if did != source_doc_id:
                ids.add(did)
    return sorted(ids)


def extract_doc_id(url: str) -> str | None:
    m = re.search(r"/doc/(\d+)", url)
    return m.group(1) if m else None


# ---- Scraper class ------------------------------------------------------


class IndianKanoonScraper:
    """Stateful scraper: owns a session, rate-limiter, and retry policy.

    One instance per process is the normal pattern. ``check_robots()`` should
    be called exactly once before any ``fetch``/``get_judgment``/``search_by_year``.
    """

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        rate_limit_seconds: float = 3.0,
        timeout_seconds: int = 30,
        session: requests.Session | None = None,
    ):
        if rate_limit_seconds < _MIN_RATE_LIMIT_SECONDS:
            raise ValueError(
                f"rate_limit_seconds must be >= {_MIN_RATE_LIMIT_SECONDS} "
                f"(politeness floor), got {rate_limit_seconds}"
            )
        self.user_agent = user_agent
        self.rate_limit = rate_limit_seconds
        self.timeout = timeout_seconds
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_request_monotonic: float = 0.0
        self._robots_checked = False

    # ---- Rate limiting & raw fetch ------------------------------------

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_monotonic
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

    @retry(
        retry=retry_if_exception_type((RateLimitedError, ServerError, requests.ConnectionError, requests.Timeout)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        reraise=True,
    )
    def fetch(self, url: str) -> str:
        """Rate-limited GET; retries on 429 / 5xx / connection errors."""
        self._wait()
        try:
            resp = self.session.get(url, timeout=self.timeout)
        finally:
            self._last_request_monotonic = time.monotonic()

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "?")
            raise RateLimitedError(f"429 on {url} (Retry-After: {retry_after})")
        if 500 <= resp.status_code < 600:
            raise ServerError(f"HTTP {resp.status_code} on {url}")
        if resp.status_code != 200:
            raise ScraperError(
                f"HTTP {resp.status_code} on {url}; body[:200]={resp.text[:200]!r}"
            )
        return resp.text

    # ---- robots.txt ---------------------------------------------------

    def check_robots(self) -> None:
        """Fetch /robots.txt; abort if /doc/ or /search/ disallowed for us."""
        robots_url = BASE_URL + "/robots.txt"
        log.info("Fetching robots.txt: %s", robots_url)
        resp = self.session.get(robots_url, timeout=self.timeout)
        if resp.status_code == 404:
            # No robots.txt -> nothing is disallowed. Treat as permissive.
            log.info("robots.txt not present (404); proceeding")
            self._robots_checked = True
            return
        resp.raise_for_status()
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(resp.text.splitlines())
        for path in ("/doc/", "/search/"):
            url = BASE_URL + path
            if not rp.can_fetch(self.user_agent, url):
                raise RobotsDisallowed(
                    f"robots.txt disallows {path} for UA {self.user_agent!r}; aborting."
                )
        log.info("robots.txt: /doc/ and /search/ allowed for our UA")
        self._robots_checked = True

    # ---- Judgment page -------------------------------------------------

    def parse_judgment_html(self, html: str, url: str) -> dict[str, Any]:
        """Parse an Indian Kanoon /doc/N/ HTML into our record schema."""
        soup = BeautifulSoup(html, "lxml")
        doc_id = extract_doc_id(url)
        full_text = _parse_full_text(soup)
        return {
            "doc_id": doc_id,
            "title": _parse_title(soup),
            "court": _parse_court(soup),
            "date": _parse_date(soup, full_text),
            "bench": _parse_bench(soup),
            "full_text": full_text,
            "statutes_cited": extract_statutes(full_text),
            "cases_cited": _parse_cases_cited(soup, doc_id),
            "source_url": url,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_judgment(self, url: str) -> dict[str, Any]:
        html = self.fetch(url)
        return self.parse_judgment_html(html, url)

    # ---- Search -------------------------------------------------------

    def search_by_year(
        self,
        year: int,
        doctype: str = "supremecourt",
        max_pages: int = 500,
    ) -> Iterator[tuple[str, str]]:
        """Yield ``(doc_id, url)`` for every search result in ``year``.

        Stops when a page yields no new /doc/ links (end of results) or when
        ``max_pages`` is reached (hard safety cap).
        """
        form_input = f"doctypes:{doctype} fromdate:1-1-{year} todate:31-12-{year}"
        seen_ids: set[str] = set()
        for pagenum in range(max_pages):
            params = {"formInput": form_input, "pagenum": pagenum}
            url = f"{BASE_URL}{SEARCH_PATH}?{urlencode(params)}"
            log.info("search year=%d page=%d", year, pagenum)
            html = self.fetch(url)
            page_ids = self._extract_result_ids(html)
            new_ids = [did for did in page_ids if did not in seen_ids]
            if not new_ids:
                log.info(
                    "year=%d page=%d yielded no new results (total seen=%d); stopping",
                    year, pagenum, len(seen_ids),
                )
                return
            for did in new_ids:
                seen_ids.add(did)
                yield did, f"{BASE_URL}/doc/{did}/"

    @staticmethod
    def _extract_result_ids(html: str) -> list[str]:
        """Pull /doc/N/ ids from a search-results page, preserving order.

        Prefers anchors inside ``div.result_title`` if present, falls back
        to any /doc/ link on the page. Header/footer navigation on IK does
        not use /doc/N/ URLs, so the fallback is safe.
        """
        soup = BeautifulSoup(html, "lxml")
        out: list[str] = []
        seen: set[str] = set()

        result_anchors = soup.select("div.result_title a[href], .result a[href]")
        source_anchors = result_anchors if result_anchors else soup.select("a[href]")

        for a in source_anchors:
            href = a.get("href", "")
            m = re.match(r"^/doc/(\d+)/?", href)
            if not m:
                continue
            did = m.group(1)
            if did in seen:
                continue
            seen.add(did)
            out.append(did)
        return out
