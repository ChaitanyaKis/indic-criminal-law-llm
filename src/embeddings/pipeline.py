"""Embedding pipeline — resumable, idempotent, re-runnable as corpus grows.

The core of this module is :func:`run`, which takes injected chunker/
embedder/vector-store dependencies so tests can use fakes. The CLI in
``scripts/build_embeddings.py`` wires up real implementations.

State model
-----------
The state file — default ``data/processed/_state/embedded.json`` — is
an append-only record of ``doc_id`` completions::

    {
      "version": 1,
      "last_updated": "<iso>",
      "embedded_doc_ids": ["12345", "67890", ...],
      "total_chunks": N,
      "model_name": "BAAI/bge-m3"
    }

A doc is in ``embedded_doc_ids`` iff all its chunks were upserted to
Qdrant successfully at some point. On re-run, those doc_ids are
skipped. Two guarantees:

* **Idempotent**: running the pipeline twice on an unchanged corpus is
  a no-op (state rewrite only, no new Qdrant writes).
* **Incremental**: running it after new docs appear in ``data-dir``
  embeds only the new ones.

If the user wants to reembed from scratch (e.g. model change), they
pass ``force_rebuild=True``, which resets the state and allows Qdrant
upserts to overwrite existing points by deterministic UUID.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tqdm import tqdm

from src.embeddings.chunker import Chunk, JudgmentChunker
from src.embeddings.embedder import EmbedderProtocol
from src.embeddings.vector_store import VectorStore

log = logging.getLogger(__name__)

CHUNK_BATCH_SIZE = 32        # chunks per embedder call
STATE_FLUSH_EVERY_N_DOCS = 50


# ---- State helpers -----------------------------------------------------


def fresh_state(model_name: str) -> dict[str, Any]:
    return {
        "version": 1,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "embedded_doc_ids": [],
        "total_chunks": 0,
        "model_name": model_name,
    }


def load_state(path: Path, model_name: str) -> dict[str, Any]:
    if not path.exists():
        return fresh_state(model_name)
    with path.open("r", encoding="utf-8") as f:
        state = json.load(f)
    if state.get("model_name") not in (None, model_name):
        log.warning(
            "State was built with model %s; current model is %s. "
            "Consider --force-rebuild to reembed with the new model.",
            state.get("model_name"), model_name,
        )
    return state


def save_state_atomic(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ---- SIGINT handling ---------------------------------------------------


_shutdown_requested = False


def install_sigint_handler() -> None:
    def _handler(signum: int, frame: Any) -> None:  # noqa: ARG001
        global _shutdown_requested
        if _shutdown_requested:
            log.warning("Second interrupt — exiting immediately")
            sys.exit(130)
        _shutdown_requested = True
        log.warning("SIGINT — finishing current batch, flushing state, exiting")

    signal.signal(signal.SIGINT, _handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handler)


def _is_shutdown_requested() -> bool:
    return _shutdown_requested


# ---- Pipeline run ------------------------------------------------------


def discover_doc_files(data_dir: Path) -> list[Path]:
    return sorted(Path(data_dir).glob("**/*.json"))


def _payload_for_chunk(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "chunk_idx": chunk.chunk_idx,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "text": chunk.text,
        **chunk.metadata,
    }


def _flush_chunk_buffer(
    embedder: EmbedderProtocol,
    store: VectorStore,
    chunk_buffer: list[Chunk],
) -> int:
    if not chunk_buffer:
        return 0
    texts = [c.text for c in chunk_buffer]
    vectors = embedder.embed(texts)
    points = [
        {
            "chunk_id": c.chunk_id,
            "vector": vec.tolist() if hasattr(vec, "tolist") else list(vec),
            "payload": _payload_for_chunk(c),
        }
        for c, vec in zip(chunk_buffer, vectors)
    ]
    return store.upsert(points)


def run(
    data_dir: Path,
    state_file: Path,
    embedder: EmbedderProtocol,
    store: VectorStore,
    chunker: JudgmentChunker | None = None,
    limit: int | None = None,
    force_rebuild: bool = False,
    progress: bool = True,
    model_name_for_state: str | None = None,
) -> dict[str, Any]:
    """Execute one pass of the pipeline. Returns a summary dict."""
    chunker = chunker or JudgmentChunker()
    model_name = model_name_for_state or getattr(embedder, "model_name", "unknown")

    # Load or reset state
    if force_rebuild:
        state = fresh_state(model_name)
    else:
        state = load_state(state_file, model_name)
    embedded_ids: set[str] = set(state.get("embedded_doc_ids", []))

    # Build todo list
    all_files = discover_doc_files(data_dir)
    todo: list[Path] = []
    for f in all_files:
        doc_id = f.stem
        if doc_id in embedded_ids:
            continue
        todo.append(f)
    if limit is not None:
        todo = todo[:limit]

    started = time.monotonic()
    pbar = tqdm(
        total=len(todo), desc="embedding", unit="doc", disable=not progress,
        dynamic_ncols=True,
    )

    chunk_buffer: list[Chunk] = []
    chunks_upserted = state.get("total_chunks", 0)
    docs_this_run = 0
    chunks_this_run = 0
    docs_since_flush = 0

    try:
        for doc_file in todo:
            if _is_shutdown_requested():
                break
            try:
                rec = json.loads(doc_file.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                log.warning("Skipping unreadable %s: %s", doc_file, e)
                continue
            doc_id = rec.get("doc_id") or doc_file.stem
            chunks = chunker.chunk(rec)
            for c in chunks:
                chunk_buffer.append(c)
                chunks_this_run += 1
                if len(chunk_buffer) >= CHUNK_BATCH_SIZE:
                    chunks_upserted += _flush_chunk_buffer(embedder, store, chunk_buffer)
                    chunk_buffer = []
            embedded_ids.add(str(doc_id))
            docs_this_run += 1
            docs_since_flush += 1
            pbar.update(1)
            pbar.set_postfix(chunks=chunks_this_run, total=chunks_upserted)

            if docs_since_flush >= STATE_FLUSH_EVERY_N_DOCS:
                # Also flush pending chunk buffer before state save so
                # state reflects what's actually in Qdrant.
                if chunk_buffer:
                    chunks_upserted += _flush_chunk_buffer(embedder, store, chunk_buffer)
                    chunk_buffer = []
                state["embedded_doc_ids"] = sorted(embedded_ids)
                state["total_chunks"] = chunks_upserted
                state["model_name"] = model_name
                save_state_atomic(state_file, state)
                docs_since_flush = 0

        # Final flush of remaining chunks
        if chunk_buffer:
            chunks_upserted += _flush_chunk_buffer(embedder, store, chunk_buffer)
            chunk_buffer = []
    finally:
        state["embedded_doc_ids"] = sorted(embedded_ids)
        state["total_chunks"] = chunks_upserted
        state["model_name"] = model_name
        save_state_atomic(state_file, state)
        pbar.close()

    runtime = round(time.monotonic() - started, 1)
    return {
        "data_dir": str(data_dir),
        "docs_in_corpus": len(all_files),
        "docs_already_embedded_before": len(all_files) - len(todo),
        "docs_this_run": docs_this_run,
        "chunks_this_run": chunks_this_run,
        "total_chunks_in_store": chunks_upserted,
        "qdrant": store.get_collection_info(),
        "runtime_seconds": runtime,
        "model_name": model_name,
        "state_file": str(state_file),
    }
