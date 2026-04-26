"""Read-only corpus inventory / quality snapshot over scraped judgments.

Produces a structured JSON report and a scannable stdout summary that
answer "what do we actually have?" — counts, length distributions,
statute citation frequencies, citation-network metrics, bench data,
language mix, near-duplicate detection, and a ``quality_flags`` list
surfacing concrete issues.

Safe to run against a live scraper's output directory: the script only
reads. It can be re-run idempotently as the scrape progresses.

Usage
-----
::

    python scripts/inventory_corpus.py
    python scripts/inventory_corpus.py --sample-size 500          # quick iteration
    python scripts/inventory_corpus.py --data-dir data/raw/supreme_court

Performance
-----------
Streams JSON files (no whole-corpus load into RAM). Tested to complete
under 5 minutes on ~20K SC criminal judgments. MinHash near-duplicate
detection is the slowest stage; ``num_perm=128`` with 5-gram word
shingles is a reasonable balance.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

DEFAULT_DATA_DIR = _PROJECT_ROOT / "data" / "raw" / "supreme_court"
DEFAULT_STATE_FILE = _PROJECT_ROOT / "data" / "raw" / "_state" / "scraped_sc.json"
DEFAULT_OUTPUT = _PROJECT_ROOT / "data" / "processed" / "corpus_inventory.json"
DEFAULT_MAPPING = _PROJECT_ROOT / "data" / "mappings" / "ipc_bns_mapping.yaml"

TINY_DOC_CHARS = 500
HUGE_DOC_CHARS = 200_000
SPARSE_YEAR_THRESHOLD = 10
OVERFULL_YEAR_THRESHOLD = 3000
MINHASH_NUM_PERM = 128
MINHASH_SHINGLE_SIZE = 5
MINHASH_THRESHOLD = 0.85
LANG_SAMPLE_CHARS = 2000

log = logging.getLogger("inventory_corpus")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ---- I/O iteration -----------------------------------------------------


def iter_doc_files(data_dir: Path) -> Iterator[tuple[Path, str]]:
    """Yield (path, year) for every {data_dir}/{year}/{doc_id}.json file.

    Year is taken from the parent-dir name so we can survive a doc whose
    ``date`` field failed to parse.
    """
    if not data_dir.exists():
        return
    for year_dir in sorted(data_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        year = year_dir.name
        for f in sorted(year_dir.glob("*.json")):
            yield f, year


def load_doc(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.warning("Failed to load %s: %s", path, e)
        return None


# ---- Per-doc feature extraction ----------------------------------------


_WORD_RE = re.compile(r"\S+")


def word_shingles(text: str, size: int = MINHASH_SHINGLE_SIZE) -> Iterator[str]:
    words = _WORD_RE.findall(text)
    if len(words) < size:
        return
    for i in range(len(words) - size + 1):
        yield " ".join(words[i : i + size])


def bns_transition_breakdown(
    transition_per_year: dict[str, Counter[str]],
) -> dict[str, Any]:
    """Cross-tabulate IPC vs BNS citation patterns by year.

    For each year, count documents that cite ONLY IPC, ONLY BNS, BOTH,
    or NEITHER. The headline number is the 2024 row, where post-1-July
    fact patterns can prosecute under either regime depending on
    offence date — three-way splits are the empirical signature of the
    transition.
    """
    result: dict[str, Any] = {"by_year": {}, "totals": {}}
    totals = Counter()
    for year in sorted(transition_per_year):
        row = transition_per_year[year]
        result["by_year"][year] = {
            "ipc_only": row.get("ipc_only", 0),
            "bns_only": row.get("bns_only", 0),
            "both": row.get("both", 0),
            "neither": row.get("neither", 0),
            "total": sum(row.values()),
        }
        for k, v in row.items():
            totals[k] += v
    result["totals"] = {
        "ipc_only": totals.get("ipc_only", 0),
        "bns_only": totals.get("bns_only", 0),
        "both": totals.get("both", 0),
        "neither": totals.get("neither", 0),
        "total": sum(totals.values()),
    }
    return result


def detect_language_safely(text: str) -> str:
    """Best-effort language detection on the first ~2K chars. Returns
    ISO 639-1 code or 'unknown'."""
    if not text or len(text.strip()) < 100:
        return "unknown"
    # langdetect is non-deterministic by default; seed once at import time
    # via detect_langs-style calls isn't trivial — we seed random via its
    # internal module.
    from langdetect import DetectorFactory, detect

    DetectorFactory.seed = 0
    try:
        return detect(text[:LANG_SAMPLE_CHARS])
    except Exception:  # noqa: BLE001
        return "unknown"


# ---- Main aggregation --------------------------------------------------


def build_inventory(  # noqa: PLR0915 — top-level orchestration, fine
    data_dir: Path,
    state_file: Path,
    sample_size: int | None,
) -> dict[str, Any]:
    started = time.monotonic()
    started_iso = datetime.now(timezone.utc).isoformat()

    # State file (optional)
    state: dict[str, Any] = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log.warning("Could not load state file %s: %s", state_file, e)

    # ---- Stream pass 1: per-doc features ------------------------------

    files = list(iter_doc_files(data_dir))
    if sample_size is not None and sample_size < len(files):
        random.seed(0)
        files = random.sample(files, sample_size)
    log.info("Indexing %d doc files from %s", len(files), data_dir)

    # Accumulators
    docs_by_year: Counter[str] = Counter()
    confidence_by_year: dict[str, Counter[str]] = defaultdict(Counter)
    char_lens: list[int] = []
    word_lens: list[int] = []
    tiny_docs: list[str] = []
    huge_docs: list[str] = []
    act_counter: Counter[str] = Counter()
    ipc_counter: Counter[str] = Counter()
    crpc_counter: Counter[str] = Counter()
    bns_counter: Counter[str] = Counter()      # NEW: BNS section-level
    bnss_counter: Counter[str] = Counter()     # NEW: BNSS section-level
    other_act_counter: Counter[str] = Counter()
    # Per-doc IPC/BNS presence flags, scoped by year — feeds the
    # bns_transition_breakdown analysis (which year buckets we mix in
    # depends on what the corpus contains; 2024 is the headline cross-tab).
    transition_per_year: dict[str, Counter[str]] = defaultdict(Counter)
    all_doc_ids: set[str] = set()
    cases_cited_histogram: list[int] = []
    cases_cited_suspicious: list[tuple[str, int]] = []
    citations_edges: list[tuple[str, str]] = []  # (cites, is_cited)
    bench_sizes: Counter[int] = Counter()
    empty_bench_count = 0
    judge_counter: Counter[str] = Counter()
    judgment_dates: list[str] = []
    date_year_counter: Counter[str] = Counter()
    language_counter: Counter[str] = Counter()

    # MinHash LSH
    try:
        from datasketch import MinHash, MinHashLSH
        lsh: MinHashLSH | None = MinHashLSH(
            threshold=MINHASH_THRESHOLD, num_perm=MINHASH_NUM_PERM,
        )
        minhashes: dict[str, MinHash] = {}
        minhash_available = True
    except ImportError:
        lsh = None
        minhashes = {}
        minhash_available = False
        log.warning("datasketch not installed — skipping near-duplicate detection")

    for idx, (path, year) in enumerate(files):
        if idx and idx % 500 == 0:
            log.info("  %d / %d docs processed (%.1fs)", idx, len(files), time.monotonic() - started)
        rec = load_doc(path)
        if rec is None:
            continue

        doc_id = rec.get("doc_id") or path.stem
        all_doc_ids.add(doc_id)
        docs_by_year[year] += 1

        # Confidence tier from state
        conf = (state.get("docs", {}).get(doc_id) or {}).get("confidence")
        if conf:
            confidence_by_year[year][conf] += 1

        # Text stats
        text = rec.get("full_text") or ""
        char_len = len(text)
        char_lens.append(char_len)
        wc = len(_WORD_RE.findall(text))
        word_lens.append(wc)
        if char_len < TINY_DOC_CHARS:
            tiny_docs.append(doc_id)
        if char_len > HUGE_DOC_CHARS:
            huge_docs.append(doc_id)

        # Statutes
        has_ipc = False
        has_bns = False
        for s in rec.get("statutes_cited") or []:
            act = s.get("act")
            sec = s.get("section")
            if not act:
                continue
            act_counter[act] += 1
            if act == "IPC":
                has_ipc = True
                if sec:
                    ipc_counter[sec] += 1
            elif act == "BNS":
                has_bns = True
                if sec:
                    bns_counter[sec] += 1
            elif act == "BNSS":
                if sec:
                    bnss_counter[sec] += 1
            elif act == "CrPC" and sec:
                crpc_counter[sec] += 1
            elif act not in ("IPC", "CrPC", "Constitution", "BNS", "BNSS"):
                other_act_counter[act] += 1
        # Cross-tab: which combination of IPC/BNS does this doc cite?
        if has_ipc and has_bns:
            tier = "both"
        elif has_ipc:
            tier = "ipc_only"
        elif has_bns:
            tier = "bns_only"
        else:
            tier = "neither"
        transition_per_year[year][tier] += 1

        # Citation network
        cases = rec.get("cases_cited") or []
        cases_cited_histogram.append(len(cases))
        if len(cases) > 50:
            cases_cited_suspicious.append((doc_id, len(cases)))
        for other in cases:
            citations_edges.append((doc_id, other))

        # Bench
        bench = rec.get("bench") or []
        n = len(bench)
        bench_sizes[n] += 1
        if n == 0:
            empty_bench_count += 1
        for j in bench:
            if isinstance(j, str) and j.strip():
                judge_counter[j.strip()] += 1

        # Dates
        d = rec.get("date")
        if d:
            judgment_dates.append(d)
            date_year_counter[d[:4]] += 1

        # Language — skip on very short text
        lang = detect_language_safely(text)
        language_counter[lang] += 1

        # MinHash
        if minhash_available and char_len >= TINY_DOC_CHARS:
            mh = MinHash(num_perm=MINHASH_NUM_PERM)
            shingles_seen = 0
            for sh in word_shingles(text):
                mh.update(sh.encode("utf-8"))
                shingles_seen += 1
                if shingles_seen > 5000:  # cap per-doc work
                    break
            if shingles_seen > 0:
                # Avoid duplicate-key insert into LSH if a re-run hits same id
                try:
                    lsh.insert(doc_id, mh)  # type: ignore[union-attr]
                    minhashes[doc_id] = mh
                except ValueError:
                    pass

    corpus_size = sum(docs_by_year.values())
    log.info("Stream pass complete: %d docs in %.1fs", corpus_size, time.monotonic() - started)

    # ---- Text length stats --------------------------------------------

    def _pctiles(vals: list[int]) -> dict[str, float | int]:
        if not vals:
            return {"mean": 0, "median": 0, "p10": 0, "p50": 0, "p90": 0, "p99": 0, "max": 0}
        vs = sorted(vals)
        def q(p: float) -> int:
            idx = max(0, min(len(vs) - 1, int(round(p * (len(vs) - 1)))))
            return vs[idx]
        return {
            "mean": round(statistics.mean(vs), 1),
            "median": statistics.median(vs),
            "p10": q(0.10), "p50": q(0.50), "p90": q(0.90), "p99": q(0.99),
            "max": vs[-1],
        }

    # Histograms (log-scale buckets for char length)
    def _hist(vals: list[int], bins: list[int]) -> list[dict[str, int]]:
        counts = [0] * (len(bins) + 1)
        for v in vals:
            placed = False
            for i, b in enumerate(bins):
                if v < b:
                    counts[i] += 1
                    placed = True
                    break
            if not placed:
                counts[-1] += 1
        labels = [f"<{bins[0]}"]
        for i in range(1, len(bins)):
            labels.append(f"{bins[i-1]}-{bins[i]}")
        labels.append(f">={bins[-1]}")
        return [{"bucket": lbl, "count": c} for lbl, c in zip(labels, counts)]

    char_hist = _hist(char_lens, [500, 2000, 5000, 20000, 50000, 100000, 200000])

    # ---- Statute mapping coverage -------------------------------------

    top_ipc = ipc_counter.most_common(50)
    top_ipc_sections = [s for s, _ in top_ipc]
    top_bns = bns_counter.most_common(50)
    top_bns_sections = [s for s, _ in top_bns]

    mapped_ipc: set[str] = set()
    mapped_bns: set[str] = set()
    mapping_error: str | None = None
    try:
        from src.mapping.ipc_bns import load_mapping
        mapping = load_mapping()
        mapped_ipc = {e.ipc_section for e in mapping.entries if e.ipc_section}
        # Reverse-direction coverage: which BNS sections does our mapping
        # carry as a target? Includes sub-sections like "316(2)" — strip
        # the parens to also match parent-section lookups.
        for e in mapping.entries:
            for s in e.bns_sections:
                mapped_bns.add(s)
                if "(" in s:
                    mapped_bns.add(s.split("(", 1)[0])
    except Exception as e:  # noqa: BLE001
        mapping_error = str(e)
        log.warning("Could not load IPC↔BNS mapping: %s", e)

    top_ipc_mapped = [s for s in top_ipc_sections if s in mapped_ipc]
    top_ipc_unmapped = [s for s in top_ipc_sections if s not in mapped_ipc]
    # Reverse coverage on top-30 BNS — accept a hit if either the exact
    # section or its parent (e.g. "103" matches an entry stored as "103(1)") is mapped.
    top_bns_30 = [s for s, _ in top_bns[:30]]
    top_bns_mapped = [s for s in top_bns_30 if s in mapped_bns or s.split("(", 1)[0] in mapped_bns]
    top_bns_unmapped = [s for s in top_bns_30 if s not in mapped_bns and s.split("(", 1)[0] not in mapped_bns]

    # ---- Citation network --------------------------------------------

    internal_edges = [(a, b) for a, b in citations_edges if b in all_doc_ids]
    docs_with_internal_cite: set[str] = {a for a, _b in internal_edges}
    cited_counter: Counter[str] = Counter(b for _a, b in internal_edges)

    # ---- Near-duplicate pairs ----------------------------------------

    dup_pairs: list[dict[str, Any]] = []
    if minhash_available and lsh is not None:
        seen_pairs: set[tuple[str, str]] = set()
        for doc_id, mh in minhashes.items():
            candidates = lsh.query(mh)
            for other in candidates:
                if other == doc_id:
                    continue
                pair = tuple(sorted([doc_id, other]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                sim = mh.jaccard(minhashes[other])
                if sim >= MINHASH_THRESHOLD:
                    dup_pairs.append(
                        {"doc_a": pair[0], "doc_b": pair[1], "jaccard": round(sim, 3)},
                    )
        dup_pairs.sort(key=lambda d: -d["jaccard"])

    # ---- Errors from state -------------------------------------------

    errors_summary: dict[str, Any] = {}
    stats = state.get("stats") or {}
    errors_summary["total_errors_in_state"] = stats.get("errors", 0)
    errors_summary["by_year"] = {
        y: s.get("errors", 0) for y, s in (stats.get("by_year") or {}).items()
    }

    # ---- Reconciliation of disk vs state -----------------------------

    state_docs = state.get("docs") or {}
    state_saved_ids = {
        did for did, info in state_docs.items() if info.get("path")
    }
    disk_not_in_state = sorted(all_doc_ids - set(state_docs.keys()))
    state_saved_not_on_disk = sorted(state_saved_ids - all_doc_ids)

    # ---- Quality flags -----------------------------------------------

    flags: list[str] = []
    if tiny_docs:
        flags.append(
            f"{len(tiny_docs)} docs are under {TINY_DOC_CHARS} chars — "
            "likely parsing failures or stub pages (e.g. bare-act previews)."
        )
    if huge_docs:
        flags.append(
            f"{len(huge_docs)} docs exceed {HUGE_DOC_CHARS:,} chars — "
            "PDF-embedded mega-judgments; may need chunking for training."
        )
    if empty_bench_count:
        pct = empty_bench_count * 100 / max(1, corpus_size)
        flags.append(
            f"{empty_bench_count} docs ({pct:.1f}%) have empty bench field — "
            "parser gap indicator."
        )
    if disk_not_in_state:
        flags.append(
            f"{len(disk_not_in_state)} docs on disk are absent from state — "
            "orphan files from aborted runs or pre-state scraping."
        )
    if state_saved_not_on_disk:
        flags.append(
            f"{len(state_saved_not_on_disk)} docs marked saved in state but "
            "no file on disk — data loss risk."
        )
    for y, count in docs_by_year.items():
        if count < SPARSE_YEAR_THRESHOLD:
            flags.append(
                f"Year {y} has only {count} docs (< {SPARSE_YEAR_THRESHOLD}) — "
                "possible scrape incomplete."
            )
        elif count > OVERFULL_YEAR_THRESHOLD:
            flags.append(
                f"Year {y} has {count} docs (> {OVERFULL_YEAR_THRESHOLD}) — "
                "pagination overcount suspected."
            )
    if cases_cited_suspicious:
        flags.append(
            f"{len(cases_cited_suspicious)} docs cite >50 other cases — "
            "the outliers are: "
            + ", ".join(f"{d}({n})" for d, n in sorted(cases_cited_suspicious, key=lambda t: -t[1])[:5])
        )
    non_english = sum(v for k, v in language_counter.items() if k not in ("en", "unknown"))
    if non_english > 0 and corpus_size > 0:
        pct = non_english * 100 / corpus_size
        if pct > 5:
            top_other = language_counter.most_common(5)
            flags.append(
                f"{non_english} docs ({pct:.1f}%) detected as non-English: "
                f"top langs = {top_other}"
            )
    if dup_pairs:
        flags.append(
            f"{len(dup_pairs)} near-duplicate pairs detected "
            f"(Jaccard ≥ {MINHASH_THRESHOLD}) — deduplicate before training."
        )
    if mapping_error:
        flags.append(f"IPC↔BNS mapping failed to load: {mapping_error}")
    if top_ipc_unmapped:
        # Surface the unmapped top IPC sections as a flag so mapping-expansion
        # work can be prioritised.
        flags.append(
            f"{len(top_ipc_unmapped)} of the top-50 cited IPC sections are NOT "
            "in the IPC↔BNS mapping yet: "
            + ", ".join(top_ipc_unmapped[:15])
            + (", ..." if len(top_ipc_unmapped) > 15 else "")
        )

    # ---- Assemble JSON -----------------------------------------------

    inventory: dict[str, Any] = {
        "snapshot_at": started_iso,
        "runtime_seconds": round(time.monotonic() - started, 1),
        "data_dir": str(data_dir),
        "state_file": str(state_file),
        "sample_size": sample_size,
        "corpus_size": corpus_size,
        "by_year": {
            y: {
                "files_on_disk": docs_by_year[y],
                "by_confidence": dict(confidence_by_year.get(y, {})),
            }
            for y in sorted(docs_by_year)
        },
        "reconciliation": {
            "disk_not_in_state": disk_not_in_state[:200],
            "state_saved_not_on_disk": state_saved_not_on_disk[:200],
            "counts": {
                "disk_not_in_state": len(disk_not_in_state),
                "state_saved_not_on_disk": len(state_saved_not_on_disk),
            },
        },
        "text_stats": {
            "chars": _pctiles(char_lens),
            "words": _pctiles(word_lens),
            "tiny_doc_count": len(tiny_docs),
            "huge_doc_count": len(huge_docs),
            "tiny_doc_sample": tiny_docs[:20],
            "huge_doc_sample": huge_docs[:20],
            "char_histogram": char_hist,
        },
        "statutes": {
            "top_acts": [{"act": a, "count": c} for a, c in act_counter.most_common(20)],
            "top_ipc": [{"section": s, "count": c} for s, c in top_ipc],
            "top_bns": [{"section": s, "count": c} for s, c in top_bns],
            "top_bnss": [{"section": s, "count": c} for s, c in bnss_counter.most_common(30)],
            "top_crpc": [{"section": s, "count": c} for s, c in crpc_counter.most_common(30)],
            "top_other_acts": [
                {"act": a, "count": c} for a, c in other_act_counter.most_common(20)
            ],
            "mapping_coverage": {
                "top_ipc_in_mapping_count": len(top_ipc_mapped),
                "top_ipc_missing_from_mapping": top_ipc_unmapped,
                "top_bns30_in_mapping_count": len(top_bns_mapped),
                "top_bns30_missing_from_mapping": top_bns_unmapped,
                "mapping_error": mapping_error,
            },
        },
        "bns_transition": bns_transition_breakdown(transition_per_year),
        "citation_network": {
            "avg_cases_cited_per_doc": round(
                statistics.mean(cases_cited_histogram) if cases_cited_histogram else 0, 2,
            ),
            "median_cases_cited": (
                statistics.median(cases_cited_histogram) if cases_cited_histogram else 0
            ),
            "docs_with_internal_citation_pct": round(
                len(docs_with_internal_cite) * 100 / max(1, corpus_size), 1,
            ),
            "top_internally_cited_docs": [
                {"doc_id": d, "cited_by": n} for d, n in cited_counter.most_common(20)
            ],
            "suspicious_high_citation_docs": [
                {"doc_id": d, "cases_cited": n}
                for d, n in sorted(cases_cited_suspicious, key=lambda t: -t[1])[:10]
            ],
        },
        "bench": {
            "size_distribution": {
                str(sz): cnt for sz, cnt in sorted(bench_sizes.items())
            },
            "empty_bench_count": empty_bench_count,
            "empty_bench_pct": round(empty_bench_count * 100 / max(1, corpus_size), 1),
            "top_judges": [{"name": j, "count": c} for j, c in judge_counter.most_common(20)],
        },
        "temporal": {
            "docs_by_scrape_year": dict(sorted(docs_by_year.items())),
            "docs_by_judgment_year": dict(sorted(date_year_counter.items())),
            "date_parse_success_pct": round(
                len(judgment_dates) * 100 / max(1, corpus_size), 1,
            ),
        },
        "language": {
            "counts": dict(language_counter.most_common()),
            "english_pct": round(
                language_counter.get("en", 0) * 100 / max(1, corpus_size), 1,
            ),
            "non_english_pct": round(non_english * 100 / max(1, corpus_size), 1),
        },
        "duplicates": {
            "enabled": minhash_available,
            "threshold": MINHASH_THRESHOLD,
            "num_perm": MINHASH_NUM_PERM,
            "shingle_size": MINHASH_SHINGLE_SIZE,
            "pair_count": len(dup_pairs),
            "top_pairs": dup_pairs[:10],
        },
        "errors": errors_summary,
        "quality_flags": flags,
    }

    return inventory


# ---- Human-readable stdout summary -------------------------------------


def print_summary(inv: dict[str, Any]) -> None:
    ts = inv["text_stats"]
    st = inv["statutes"]
    cn = inv["citation_network"]
    bn = inv["bench"]
    lg = inv["language"]
    du = inv["duplicates"]
    print()
    print("=" * 72)
    print(f"Corpus inventory — {inv['snapshot_at']}")
    print("=" * 72)
    print(f"Total docs:             {inv['corpus_size']:,}")
    print(f"Runtime:                {inv['runtime_seconds']}s")
    print(f"Sample mode:            {inv.get('sample_size') or 'full corpus'}")
    print()
    print("--- By year (scrape-year partition) ---")
    for y, info in inv["by_year"].items():
        tier = info.get("by_confidence") or {}
        tier_s = " / ".join(f"{k}:{v}" for k, v in tier.items()) or "(no state)"
        print(f"  {y}: {info['files_on_disk']:>6,} files  [{tier_s}]")
    print()
    print("--- Text length ---")
    print(f"  chars:  mean={ts['chars']['mean']:>10,.0f}  "
          f"p50={ts['chars']['p50']:>8,}  "
          f"p90={ts['chars']['p90']:>8,}  "
          f"p99={ts['chars']['p99']:>8,}  "
          f"max={ts['chars']['max']:>10,}")
    print(f"  words:  mean={ts['words']['mean']:>10,.0f}  "
          f"p50={ts['words']['p50']:>8,}  "
          f"p90={ts['words']['p90']:>8,}  "
          f"p99={ts['words']['p99']:>8,}  "
          f"max={ts['words']['max']:>10,}")
    print(f"  tiny (<{TINY_DOC_CHARS} chars): {ts['tiny_doc_count']}   "
          f"huge (>{HUGE_DOC_CHARS:,}): {ts['huge_doc_count']}")
    print()
    print("--- Top 10 acts cited ---")
    for row in st["top_acts"][:10]:
        print(f"  {row['act']:<28} {row['count']:>6,}")
    print()
    print("--- Top 50 IPC sections cited (top 30 detailed, 31-50 compact) ---")
    mapped = set()
    try:
        from src.mapping.ipc_bns import load_mapping
        mapped = {e.ipc_section for e in load_mapping().entries if e.ipc_section}
    except Exception:  # noqa: BLE001
        pass
    for i, row in enumerate(st["top_ipc"][:30], 1):
        flag = "✓" if row["section"] in mapped else "✗"
        print(f"  {i:>2}. {flag} IPC {row['section']:<8}  {row['count']:>6,}")
    tail = st["top_ipc"][30:50]
    if tail:
        print(f"  31-50 (compact):")
        compact = []
        for row in tail:
            flag = "✓" if row["section"] in mapped else "✗"
            compact.append(f"{flag} {row['section']}({row['count']})")
        # Wrap at ~80 chars
        line = "    "
        for token in compact:
            if len(line) + len(token) + 2 > 88:
                print(line.rstrip())
                line = "    " + token + ", "
            else:
                line += token + ", "
        if line.strip():
            print(line.rstrip(", "))
    unmapped_top = st["mapping_coverage"]["top_ipc_missing_from_mapping"]
    print(f"  mapping coverage of top 50: "
          f"{st['mapping_coverage']['top_ipc_in_mapping_count']}/50")
    if unmapped_top:
        print(f"  unmapped: {', '.join(unmapped_top[:15])}"
              f"{', ...' if len(unmapped_top) > 15 else ''}")
    print()
    # ---- Top BNS sections (NEW — appears once 2024 docs are scraped) -----
    top_bns_list = st.get("top_bns") or []
    if top_bns_list:
        # Reverse mapping coverage — does our IPC↔BNS table cover the
        # BNS sections actually being cited by SC?
        mapped_bns_set: set[str] = set()
        try:
            from src.mapping.ipc_bns import load_mapping
            for e in load_mapping().entries:
                for s in e.bns_sections:
                    mapped_bns_set.add(s)
                    if "(" in s:
                        mapped_bns_set.add(s.split("(", 1)[0])
        except Exception:  # noqa: BLE001
            pass
        print("--- Top 30 BNS sections cited (NEW: post-July-2024 signal) ---")
        for i, row in enumerate(top_bns_list[:30], 1):
            sec = row["section"]
            flag = "✓" if (sec in mapped_bns_set or sec.split("(", 1)[0] in mapped_bns_set) else "✗"
            print(f"  {i:>2}. {flag} BNS {sec:<8}  {row['count']:>6,}")
        cov = st["mapping_coverage"]
        bns_mapped = cov.get("top_bns30_in_mapping_count", 0)
        bns_unmapped = cov.get("top_bns30_missing_from_mapping", []) or []
        print(f"  reverse mapping coverage of top 30 BNS: {bns_mapped}/30")
        if bns_unmapped:
            print(f"  unmapped BNS: {', '.join(bns_unmapped[:15])}"
                  f"{', ...' if len(bns_unmapped) > 15 else ''}")
        print()
    # ---- BNS transition cross-tab (IPC-only / BNS-only / Both per year) --
    trans = inv.get("bns_transition") or {}
    if trans:
        by_y = trans.get("by_year") or {}
        if by_y:
            print("--- BNS transition cross-tab (IPC vs BNS citations per year) ---")
            print(f"  {'year':<6} {'ipc_only':>10} {'bns_only':>10} "
                  f"{'both':>8} {'neither':>10} {'total':>8}")
            for y in sorted(by_y):
                r = by_y[y]
                print(f"  {y:<6} {r['ipc_only']:>10} {r['bns_only']:>10} "
                      f"{r['both']:>8} {r['neither']:>10} {r['total']:>8}")
            tot = trans.get("totals") or {}
            if tot:
                print(f"  {'TOTAL':<6} {tot.get('ipc_only',0):>10} "
                      f"{tot.get('bns_only',0):>10} {tot.get('both',0):>8} "
                      f"{tot.get('neither',0):>10} {tot.get('total',0):>8}")
            print()
    print("--- Citation network ---")
    print(f"  avg cases cited per doc:       {cn['avg_cases_cited_per_doc']}")
    print(f"  docs with internal citation:   {cn['docs_with_internal_citation_pct']}%")
    print(f"  suspicious (>50 cites):        {len(cn['suspicious_high_citation_docs'])}")
    print()
    print("--- Bench ---")
    dist = bn["size_distribution"]
    print(f"  bench sizes:   {dict(dist)}")
    print(f"  empty bench:   {bn['empty_bench_count']} ({bn['empty_bench_pct']}%)")
    print(f"  top judge:     "
          f"{bn['top_judges'][0]['name']} ({bn['top_judges'][0]['count']})"
          if bn["top_judges"] else "  top judge:     (none)")
    print()
    print("--- Language ---")
    print(f"  English:       {lg['english_pct']}%   "
          f"Non-English:   {lg['non_english_pct']}%")
    print(f"  breakdown:     {lg['counts']}")
    print()
    print("--- Near-duplicates ---")
    print(f"  pairs at J>={du['threshold']}:  {du['pair_count']}")
    for p in du["top_pairs"][:5]:
        print(f"    {p['doc_a']}  ↔  {p['doc_b']}   J={p['jaccard']}")
    print()
    print("=== QUALITY FLAGS ===")
    if inv["quality_flags"]:
        for f in inv["quality_flags"]:
            print(f"  • {f}")
    else:
        print("  (none)")
    print("=" * 72)


# ---- CLI ---------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Read-only corpus inventory / quality snapshot.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument(
        "--sample-size", type=int, default=None,
        help="If set, randomly sample this many docs (seed=0) instead of full corpus.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inv = build_inventory(
        data_dir=args.data_dir,
        state_file=args.state_file,
        sample_size=args.sample_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inv, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote inventory to %s", args.output)
    print_summary(inv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
