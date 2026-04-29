"""Run the hallucination measurement study (pre-registered).

Per query, performs N runs against the live RAG stack (BGE-M3
retrieval + Qdrant + Gemini 2.5 Flash with thinking disabled), logs
each run as a JSONL line, and supports resumption across sessions.

Pre-registration: see
``docs/findings/2026-04-29_hallucination_study_v1_design.md``.

Usage
-----
::

    # Session 1
    python scripts/run_hallucination_study.py --runs-per-query 5 \\
        --session-tag session_1

    # Session 2 (≥1 hour later, resumes after seeing existing run_ids)
    python scripts/run_hallucination_study.py --runs-per-query 5 \\
        --session-tag session_2 --resume
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from tqdm import tqdm

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Suppress HF Hub liveness pings — model is cached locally.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

DEFAULT_QUERIES = _PROJECT_ROOT / "data" / "mappings" / "hallucination_study_queries.yaml"
DEFAULT_OUTPUT = _PROJECT_ROOT / "data" / "processed" / "hallucination_study_v1.jsonl"
DEFAULT_QDRANT = _PROJECT_ROOT / "data" / "processed" / "qdrant"
INTER_RUN_SLEEP_SECONDS = 5

log = logging.getLogger("hallucination_study")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ---- Mode classification (locked from design doc) ----------------------


_MODE_1_RE = re.compile(r"^\d{7,}$")     # real-Indian-Kanoon-shape ids
_MODE_2_RE = re.compile(r"^[1-9]$")      # single-digit chunk ordinals 1-9


def classify_mode(invalid_ids: list[str]) -> str:
    """Apply locked mode-classification rules.

    Per the design doc, when multiple modes apply, classify by
    most-novel (novel > mode_2 > mode_1). This biases toward
    surfacing unusual behaviour.
    """
    if not invalid_ids:
        return "clean"
    has_mode_1 = False
    has_mode_2 = False
    has_other = False
    for s in invalid_ids:
        if _MODE_1_RE.match(s):
            has_mode_1 = True
        elif _MODE_2_RE.match(s):
            has_mode_2 = True
        else:
            has_other = True
    if has_other:
        return "novel"
    if has_mode_2:
        return "mode_2_index"
    if has_mode_1:
        return "mode_1_stable"
    return "novel"


# ---- JSONL append-only state ------------------------------------------


def existing_run_ids(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()
    ids: set[str] = set()
    with output_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            rid = rec.get("run_id")
            if rid:
                ids.add(rid)
    return ids


def append_jsonl(output_path: Path, record: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()


# ---- Single run --------------------------------------------------------


def run_one(
    *,
    query_id: str,
    query: str,
    run_number: int,
    session_id: str,
    embedder,
    store,
    retriever,
    generator,
    top_k: int,
    prompt_format: str,
) -> dict[str, Any]:
    from src.rag.citation_verifier import verify_citations, extract_citations

    started = time.monotonic()
    errors: list[str] = []

    try:
        chunks = retriever.retrieve(query, top_k=top_k)
    except Exception as e:  # noqa: BLE001
        errors.append(f"retrieval: {type(e).__name__}: {e}")
        chunks = []

    retrieval_block: dict[str, Any] = {
        "chunks_returned": len(chunks),
        "doc_ids_in_retrieval": [c.doc_id for c in chunks],
    }
    if chunks:
        scores = [c.score for c in chunks]
        retrieval_block["top_score"] = round(max(scores), 4)
        retrieval_block["min_score"] = round(min(scores), 4)
    else:
        retrieval_block["top_score"] = None
        retrieval_block["min_score"] = None

    answer_text = ""
    completion_tokens: int | None = None
    finish_reason: str | None = None
    cited_doc_ids: list[str] = []

    if not errors:
        try:
            result = generator.answer(
                query, chunks,
                temperature=0.0,
                max_output_tokens=1024,
                prompt_format=prompt_format,
            )
            answer_text = result.answer
            completion_tokens = result.completion_tokens
            cited_doc_ids = extract_citations(answer_text)
        except Exception as e:  # noqa: BLE001
            errors.append(f"generation: {type(e).__name__}: {e}")

    verification = verify_citations(answer_text, chunks) if answer_text else {
        "cited_count": 0,
        "valid_citations": [],
        "invalid_citations": [],
        "all_valid": True,
        "unsupported_claims": [],
    }
    invalid = list(verification.get("invalid_citations") or [])
    mode = classify_mode(invalid)

    record = {
        "run_id": f"{query_id}__{run_number:02d}",
        "query_id": query_id,
        "query": query,
        "run_number": run_number,
        "session_id": session_id,
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "model": "gemini-2.5-flash",
        "temperature": 0,
        "thinking_disabled": True,
        "prompt_format": prompt_format,
        "top_k": top_k,
        "retrieval": retrieval_block,
        "answer": {
            "text": answer_text,
            "completion_tokens": completion_tokens,
            "finish_reason": finish_reason,
            "cited_doc_ids": cited_doc_ids,
        },
        "verification": {
            "cited_count": verification.get("cited_count", 0),
            "valid_count": len(verification.get("valid_citations") or []),
            "valid_citations": list(verification.get("valid_citations") or []),
            "invalid_citations": invalid,
            "all_valid": bool(verification.get("all_valid", True)),
            "hallucination_mode": mode,
        },
        "errors": errors,
        "wall_seconds": round(time.monotonic() - started, 2),
    }
    return record


# ---- CLI ---------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the hallucination measurement study (pre-registered).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--queries-file", type=Path, default=DEFAULT_QUERIES)
    p.add_argument("--runs-per-query", type=int, default=5,
                   help="Runs to perform per query in this session.")
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--qdrant-dir", type=Path, default=DEFAULT_QDRANT)
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--prompt-format", choices=["numbered", "id_only"],
                   default="numbered")
    p.add_argument("--session-tag", default=None,
                   help="Manual session id; defaults to minute-resolution timestamp.")
    p.add_argument("--resume", action="store_true",
                   help="Skip runs whose run_id is already in the output JSONL.")
    p.add_argument("--inter-run-sleep", type=float, default=INTER_RUN_SLEEP_SECONDS)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    queries_doc = yaml.safe_load(args.queries_file.read_text(encoding="utf-8"))
    queries = queries_doc["queries"]
    log.info("Loaded %d queries from %s", len(queries), args.queries_file)

    session_id = args.session_tag or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    log.info("Session id: %s", session_id)

    done_run_ids = existing_run_ids(args.output) if args.resume else set()
    if done_run_ids:
        log.info("Resuming: %d runs already in %s", len(done_run_ids), args.output)

    # Wire up the RAG stack once and reuse across all runs.
    from src.embeddings.embedder import Embedder
    from src.embeddings.vector_store import VectorStore
    from src.rag.generator import RAGGenerator
    from src.rag.retriever import Retriever

    embedder = Embedder()
    store = VectorStore(path=args.qdrant_dir, vector_size=embedder.dim)
    retriever = Retriever(embedder=embedder, store=store, default_top_k=args.top_k)
    generator = RAGGenerator(provider="gemini")
    log.info("Stack ready (model=%s, device=%s, qdrant_points=%d)",
             embedder.model_name, embedder.device, store.count())

    # Build the run plan: every (query, run_number) up to runs-per-query
    # PER session, resumable across sessions if --resume.
    plan: list[tuple[dict[str, Any], int]] = []
    for q in queries:
        # Find the next available run_number for this query that's not
        # already in the output file. This makes session 2 cleanly pick
        # up after session 1 without conflict.
        existing_for_q = [int(r.split("__")[1]) for r in done_run_ids if r.startswith(q["id"] + "__")]
        next_n = (max(existing_for_q) if existing_for_q else 0) + 1
        for k in range(args.runs_per_query):
            plan.append((q, next_n + k))
    log.info("Plan: %d runs (queries × runs-per-query)", len(plan))

    pbar = tqdm(plan, desc=f"study/{session_id}", unit="run")
    for q, run_n in pbar:
        run_id = f"{q['id']}__{run_n:02d}"
        if run_id in done_run_ids:
            continue
        pbar.set_postfix(qid=q["id"], n=run_n)
        record = run_one(
            query_id=q["id"],
            query=q["text"],
            run_number=run_n,
            session_id=session_id,
            embedder=embedder,
            store=store,
            retriever=retriever,
            generator=generator,
            top_k=args.top_k,
            prompt_format=args.prompt_format,
        )
        append_jsonl(args.output, record)
        done_run_ids.add(run_id)
        if args.inter_run_sleep > 0:
            time.sleep(args.inter_run_sleep)
    pbar.close()

    log.info("Session complete. Total runs in %s: %d",
             args.output, len(existing_run_ids(args.output)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
