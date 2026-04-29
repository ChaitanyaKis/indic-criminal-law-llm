"""Tests for the RAG stack.

- Retriever tests use a fake embedder + in-memory Qdrant so they don't
  need BGE-M3 and run in milliseconds.
- Citation-verifier tests are pure-string; no I/O.
- Generator test hits the real Gemini free tier; skipped when
  ``GEMINI_API_KEY`` is not set.
- End-to-end test uses BGE-M3 against whatever is currently in the
  local Qdrant index (built by the smoke pass of
  ``scripts/build_embeddings.py``). Skipped if the index is empty.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from dotenv import load_dotenv

from src.embeddings.vector_store import VectorStore
from src.rag.citation_verifier import extract_citations, verify_citations
from src.rag.retriever import Retriever


# ---- Fixtures / helpers -----------------------------------------------


class FakeEmbedder:
    dim = 64
    model_name = "fake"

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            seed = abs(hash(t)) & 0xFFFFFFFF
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(self.dim).astype(np.float32)
            v /= float(np.linalg.norm(v) + 1e-9)
            out[i] = v
        return out


def _populate_store(store: VectorStore, items: list[tuple[str, str, int, str, list[str]]]):
    """items: [(chunk_id, doc_id, year, text, acts), ...]"""
    embedder = FakeEmbedder()
    texts = [it[3] for it in items]
    vecs = embedder.embed(texts)
    points = []
    for (cid, did, year, text, acts), v in zip(items, vecs):
        points.append({
            "chunk_id": cid,
            "vector": v,
            "payload": {
                "chunk_id": cid,
                "doc_id": did,
                "text": text,
                "year": year,
                "statutes_cited_acts": acts,
                "title": f"Case {did}",
            },
        })
    store.upsert(points)


# ---- Retriever tests --------------------------------------------------


def test_retriever_returns_k_results(tmp_path: Path):
    store = VectorStore(path=tmp_path / "qdrant", vector_size=64)
    _populate_store(store, [
        (f"doc{i}__0000", str(1000 + i), 2015 + (i % 5),
         f"Judgment body {i} about criminal procedure.",
         ["IPC"] if i % 2 else ["CrPC"])
        for i in range(5)
    ])
    r = Retriever(embedder=FakeEmbedder(), store=store, default_top_k=3)
    hits = r.retrieve("criminal procedure")
    assert len(hits) == 3


def test_retriever_filter_by_year(tmp_path: Path):
    store = VectorStore(path=tmp_path / "qdrant", vector_size=64)
    _populate_store(store, [
        ("a__0000", "1001", 2015, "Case from 2015", ["IPC"]),
        ("b__0000", "1002", 2018, "Case from 2018", ["IPC"]),
        ("c__0000", "1003", 2021, "Case from 2021", ["IPC"]),
    ])
    r = Retriever(embedder=FakeEmbedder(), store=store, default_top_k=10)
    hits = r.retrieve("case", year_from=2016, year_to=2019)
    years = {h.metadata.get("year") for h in hits}
    assert years == {2018}


# ---- Citation verifier tests ------------------------------------------


def test_citation_verifier_catches_hallucinated_doc_id():
    answer = (
        "Section 498A was interpreted in [doc_id: 12345] as covering "
        "only direct relatives [doc_id: 99999, fabricated case]."
    )
    chunks = [{"doc_id": "12345", "text": "..."}]
    result = verify_citations(answer, chunks)
    assert result["all_valid"] is False
    assert "99999" in result["invalid_citations"]
    assert "12345" in result["valid_citations"]
    assert result["cited_count"] == 2


def test_citation_verifier_passes_valid_citations():
    answer = (
        "The court held that Section 498A is gender-neutral in application "
        "[doc_id: 111]. Also [doc_id: 222]."
    )
    chunks = [{"doc_id": "111", "text": "..."}, {"doc_id": "222", "text": "..."}]
    result = verify_citations(answer, chunks)
    assert result["all_valid"] is True
    assert result["invalid_citations"] == []
    assert set(result["valid_citations"]) == {"111", "222"}


def test_citation_verifier_extraction_handles_variations():
    answer = (
        "First [DOC_ID: abc123] then [doc_id=def456] plus a plain sentence."
    )
    ids = extract_citations(answer)
    assert ids == ["abc123", "def456"]


# ---- Generator test (hits Gemini free tier) ---------------------------


@pytest.mark.skipif(
    not (load_dotenv() or True) or not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set",
)
def test_generator_with_gemini():
    from src.rag.generator import RAGGenerator

    gen = RAGGenerator(provider="gemini")
    chunks = [{
        "doc_id": "test_001",
        "text": (
            "The Supreme Court held in this judgment that an accused person "
            "must be produced before a Magistrate within 24 hours of arrest "
            "under Article 22(2) of the Constitution of India."
        ),
        "metadata": {"title": "Test Case 1", "year": 2020, "court": "Supreme Court of India"},
        "score": 0.9,
    }]
    result = gen.answer("What is the time limit for producing an arrested person?", chunks)
    assert "24 hours" in result.answer or "twenty-four" in result.answer.lower()
    # Citation must be present and refer to the supplied doc_id
    assert "test_001" in result.answer


# ---- End-to-end smoke test against the actual local Qdrant ------------
#
# Replaces the previous test_end_to_end_rag_with_known_answer, which
# asserted ``verification['all_valid']`` and was therefore implicitly
# claiming that Gemini never hallucinates a citation. The April 28
# debugging cycle revealed that (a) the verifier's regex was buggy and
# silently swallowing hallucinations and (b) once fixed, Gemini does
# emit hallucinated doc_ids on real legal queries. The "test passing"
# was a false positive from the verifier bug, not a guarantee from the
# LLM.
#
# Lesson: contract tests should test our code, not the LLM's behaviour.
# This smoke test asserts only the pipeline contract (returns a non-
# trivial answer, the verification dict has the expected shape) and
# logs the hallucination signal as informational output.


@pytest.mark.smoke
@pytest.mark.skipif(
    not (load_dotenv() or True) or not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set",
)
def test_rag_end_to_end_smoke_with_known_query(capsys):
    """End-to-end smoke: real Gemini, real Qdrant, real verification.
    Captures the hallucination signal but does NOT fail the build if
    Gemini hallucinates — that's measurement, not contract."""
    from pathlib import Path

    qdrant_dir = Path("data/processed/qdrant")
    if not qdrant_dir.exists() or not any(qdrant_dir.glob("**/*")):
        pytest.skip("No Qdrant index built yet")

    from src.embeddings.embedder import Embedder
    from src.embeddings.vector_store import VectorStore as VS
    from src.rag.generator import RAGGenerator
    from src.rag.retriever import Retriever as Rt

    embedder = Embedder()
    store = VS(path=qdrant_dir, vector_size=embedder.dim)
    if store.count() == 0:
        pytest.skip("Qdrant index is empty")

    retriever = Rt(embedder=embedder, store=store, default_top_k=5)
    generator = RAGGenerator(provider="gemini")
    chunks = retriever.retrieve(
        "anticipatory bail under Section 438 CrPC", top_k=5,
    )
    result = generator.answer(
        "What is anticipatory bail under Section 438?",
        chunks,
        temperature=0.0,
    )
    verification = verify_citations(result.answer, chunks)

    # Hard assertions (must pass — these are our contract):
    assert result.answer is not None
    assert len(result.answer) > 100, (
        f"Answer suspiciously short ({len(result.answer)} chars) — "
        "did Gemini get truncated by max_output_tokens or thinking-budget?"
    )
    assert isinstance(verification["cited_count"], int)
    assert verification["cited_count"] >= 0
    assert isinstance(verification["valid_citations"], list)
    assert isinstance(verification["invalid_citations"], list)

    # Soft signal (logged, never asserted) — measures the real Gemini
    # hallucination rate on a grounded legal query.
    with capsys.disabled():
        print(
            f"\nE2E smoke signal: cited={verification['cited_count']}, "
            f"valid={len(verification['valid_citations'])}, "
            f"hallucinated={len(verification['invalid_citations'])}, "
            f"all_valid={verification['all_valid']}"
        )
        if verification["invalid_citations"]:
            print(
                f"  hallucinated ids: {verification['invalid_citations']}"
            )
