"""Tests for the embedding pipeline.

- Chunker tests (1-5) use tiktoken directly and are fast.
- Embedder test (6) instantiates BGE-M3 lazily; the first run downloads
  ~2.3 GB of weights. Cached thereafter.
- Vector-store test (7) uses a random vector — no model needed.
- Pipeline idempotency tests (8-9) use a fake embedder with deterministic
  hash-based vectors, so they run in milliseconds and don't need the
  real model.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.embeddings.chunker import Chunk, JudgmentChunker  # noqa: F401
from src.embeddings.pipeline import run as pipeline_run
from src.embeddings.vector_store import VectorStore


# ---- Helpers -----------------------------------------------------------


def _judgment(doc_id: str, text: str, **extra) -> dict:
    return {
        "doc_id": doc_id,
        "title": extra.get("title", f"Test Case {doc_id}"),
        "court": extra.get("court", "Supreme Court of India"),
        "date": extra.get("date", "2023-01-01"),
        "bench": extra.get("bench", ["Test J"]),
        "full_text": text,
        "statutes_cited": extra.get("statutes_cited", []),
        "cases_cited": extra.get("cases_cited", []),
        "source_url": extra.get("source_url", "https://example.test"),
    }


def _write_judgments(tmpdir: Path, judgments: list[dict]) -> Path:
    d = tmpdir / "docs"
    d.mkdir(parents=True, exist_ok=True)
    for j in judgments:
        (d / f"{j['doc_id']}.json").write_text(
            json.dumps(j, ensure_ascii=False), encoding="utf-8",
        )
    return d


class FakeEmbedder:
    """Deterministic fake. Vectors are hash-seeded from text, so identical
    chunks produce identical vectors and the VectorStore idempotency is
    actually exercised."""

    def __init__(self, dim: int = 128, model_name: str = "fake-embedder"):
        self.dim = dim
        self.model_name = model_name

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            seed = abs(hash(t)) & 0xFFFFFFFF
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(self.dim).astype(np.float32)
            v /= float(np.linalg.norm(v) + 1e-9)
            out[i] = v
        return out


# A long doc that will definitely produce multiple chunks (≈ 3K tokens).
_LONG_PARA = (
    "This Court considered the appeal at length. "
    "The learned counsel for the appellant argued that the judgment below "
    "failed to appreciate the circumstantial evidence in its proper context. "
    "The prosecution's case rested on the recovery of material objects "
    "and the testimony of the investigating officer. "
)


def _long_text(n_paragraphs: int) -> str:
    return "\n\n".join(_LONG_PARA * 30 for _ in range(n_paragraphs))


# ---- Chunker tests (1-5) ----------------------------------------------


def test_chunker_respects_paragraph_boundaries():
    text = "First paragraph one.\n\nSecond paragraph two.\n\nThird paragraph three."
    c = JudgmentChunker(target_tokens=500)
    chunks = c.chunk(_judgment("doc1", text))
    assert len(chunks) == 1  # short text → one chunk
    # The chunk should contain all three paragraph contents
    for needle in ("First paragraph", "Second paragraph", "Third paragraph"):
        assert needle in chunks[0].text


def test_chunker_handles_short_doc():
    text = "Short judgment. One sentence."
    c = JudgmentChunker(target_tokens=500)
    chunks = c.chunk(_judgment("doc1", text))
    assert len(chunks) == 1
    assert chunks[0].chunk_idx == 0
    assert chunks[0].chunk_id == "doc1__0000"
    assert "Short judgment" in chunks[0].text


def test_chunker_handles_long_doc():
    # ~3K tokens -> should produce >= 5 chunks at target=500
    text = _long_text(3)
    c = JudgmentChunker(target_tokens=500, overlap_tokens=100)
    chunks = c.chunk(_judgment("long1", text))
    assert len(chunks) >= 5
    # chunk_idx must be sequential, chunk_id must match the format
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_idx == i
        assert chunk.chunk_id == f"long1__{i:04d}"
    # No single chunk should be absurdly over the target — allow 50% slack
    # because sentence-split pieces may overshoot slightly.
    for chunk in chunks:
        assert chunk.token_count <= int(500 * 1.5)


def test_chunker_overlap_is_present():
    text = _long_text(3)
    c = JudgmentChunker(target_tokens=500, overlap_tokens=100)
    chunks = c.chunk(_judgment("ol1", text))
    assert len(chunks) >= 2
    # Overlap check: some suffix of chunk N should appear as a prefix of
    # chunk N+1. We look for ≥ 40 chars of shared text (conservative —
    # 100 tokens is ~400 chars but we don't want to be flaky on
    # whitespace normalisation).
    for i in range(len(chunks) - 1):
        tail = chunks[i].text[-400:]
        head = chunks[i + 1].text[:600]
        # find the longest common window of ≥40 chars
        found = False
        for window_len in range(200, 39, -10):
            for start in range(0, len(tail) - window_len + 1, 20):
                frag = tail[start:start + window_len]
                if len(frag.strip()) < window_len // 2:
                    continue
                if frag in head:
                    found = True
                    break
            if found:
                break
        assert found, f"no overlap detected between chunks {i} and {i+1}"


def test_chunker_chunk_ids_are_deterministic():
    j = _judgment("deterministic", _long_text(2))
    c = JudgmentChunker(target_tokens=500)
    run1 = c.chunk(j)
    run2 = c.chunk(j)
    assert [x.chunk_id for x in run1] == [x.chunk_id for x in run2]
    # Text content also stable
    assert [x.text for x in run1] == [x.text for x in run2]


# ---- Embedder test (6) — loads real BGE-M3 ----------------------------


def test_embedder_produces_1024_dim_vectors():
    """Loads BGE-M3 on first run (~2.3 GB download). Subsequent runs use
    the HuggingFace cache and are fast on CPU (~1-3s for 3 short texts)."""
    from src.embeddings.embedder import Embedder

    e = Embedder()  # defaults to BAAI/bge-m3
    texts = [
        "The appellant was convicted under Section 302 of the IPC.",
        "Anticipatory bail was sought under Section 438 Cr.P.C.",
        "NDPS commercial quantity attracts Section 37 rigour.",
    ]
    vecs = e.embed(texts)
    assert vecs.shape == (3, 1024)
    assert e.dim == 1024
    # Normalized embeddings: norms ≈ 1
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)


# ---- Vector store test (7) — fake vectors, real Qdrant ----------------


def test_vector_store_upsert_and_query(tmp_path: Path):
    store = VectorStore(path=tmp_path / "qdrant", vector_size=64)
    rng = np.random.default_rng(0)
    # Three points, the second is the "target" — a nearby query vector
    # should find it ranked first.
    v_far1 = rng.standard_normal(64).astype(np.float32)
    v_target = rng.standard_normal(64).astype(np.float32)
    v_far2 = rng.standard_normal(64).astype(np.float32)
    for v in (v_far1, v_target, v_far2):
        v /= float(np.linalg.norm(v))

    points = [
        {"chunk_id": "a__0000", "vector": v_far1, "payload": {"doc_id": "a", "chunk_id": "a__0000", "text": "far 1"}},
        {"chunk_id": "b__0000", "vector": v_target, "payload": {"doc_id": "b", "chunk_id": "b__0000", "text": "target"}},
        {"chunk_id": "c__0000", "vector": v_far2, "payload": {"doc_id": "c", "chunk_id": "c__0000", "text": "far 2"}},
    ]
    assert store.upsert(points) == 3
    assert store.count() == 3

    # Query with a vector very close to the target.
    query = v_target + 1e-3 * rng.standard_normal(64).astype(np.float32)
    query /= float(np.linalg.norm(query))
    hits = store.search(query, top_k=3)
    assert hits[0].payload["chunk_id"] == "b__0000"
    store.close()


# ---- Pipeline idempotency (8-9) — fake embedder -----------------------


def test_pipeline_is_idempotent(tmp_path: Path):
    # Three short judgments → few chunks, pipeline should embed them all
    # on pass 1, then do nothing on pass 2.
    docs_dir = _write_judgments(tmp_path, [
        _judgment("11111", "Short judgment about bail under 438 CrPC."),
        _judgment("22222", "Another short judgment about IPC 302 conviction."),
        _judgment("33333", "NDPS act Section 37 compliance."),
    ])
    state_file = tmp_path / "state.json"
    qdrant_dir = tmp_path / "qdrant"

    embedder = FakeEmbedder(dim=64)
    store = VectorStore(path=qdrant_dir, vector_size=64)
    summary1 = pipeline_run(
        data_dir=docs_dir,
        state_file=state_file,
        embedder=embedder,
        store=store,
        progress=False,
    )
    assert summary1["docs_this_run"] == 3
    chunks_after_first = summary1["total_chunks_in_store"]
    assert chunks_after_first >= 3

    # Pass 2 on the same corpus — no new docs, state should lock us out
    summary2 = pipeline_run(
        data_dir=docs_dir,
        state_file=state_file,
        embedder=embedder,
        store=store,
        progress=False,
    )
    assert summary2["docs_this_run"] == 0
    assert summary2["chunks_this_run"] == 0
    # Qdrant count should not have grown (deterministic UUIDs + no new upserts)
    assert store.count() == chunks_after_first
    store.close()


def test_pipeline_picks_up_new_docs(tmp_path: Path):
    # Pass 1 with 3 docs, then add 2 more and re-run.
    docs_dir = _write_judgments(tmp_path, [
        _judgment(f"doc_{i}", f"Judgment body about section {i} CrPC.")
        for i in range(3)
    ])
    state_file = tmp_path / "state.json"
    qdrant_dir = tmp_path / "qdrant"

    embedder = FakeEmbedder(dim=64)
    store = VectorStore(path=qdrant_dir, vector_size=64)
    s1 = pipeline_run(
        data_dir=docs_dir,
        state_file=state_file,
        embedder=embedder,
        store=store,
        progress=False,
    )
    assert s1["docs_this_run"] == 3
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["embedded_doc_ids"]) == 3

    # Add two new docs
    (docs_dir / "new_1.json").write_text(
        json.dumps(_judgment("new_1", "A newly-scraped judgment.")),
        encoding="utf-8",
    )
    (docs_dir / "new_2.json").write_text(
        json.dumps(_judgment("new_2", "Yet another newly-scraped judgment.")),
        encoding="utf-8",
    )

    s2 = pipeline_run(
        data_dir=docs_dir,
        state_file=state_file,
        embedder=embedder,
        store=store,
        progress=False,
    )
    assert s2["docs_this_run"] == 2  # only the 2 new ones
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["embedded_doc_ids"]) == 5
    assert set(state["embedded_doc_ids"]) == {"doc_0", "doc_1", "doc_2", "new_1", "new_2"}
    store.close()
