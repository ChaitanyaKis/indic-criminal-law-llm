"""Targeted tests for the citation-verifier multi-id extraction.

The verifier is the project's core differentiator. The previous regex
captured only the first ``doc_id`` per bracket, which silently
under-counted valid citations and — worse — could miss hallucinated
ids in mixed brackets like ``[doc_id: REAL, doc_id: FAKE]``. These
tests lock in the corrected behaviour where every ``doc_id`` inside
every bracket is extracted.

Existing tests in ``tests/test_rag.py`` (single-id-per-bracket,
hallucination detection, format variations) still pass; this file adds
the multi-id coverage.
"""

from __future__ import annotations

from src.rag.citation_verifier import extract_citations, verify_citations


def test_single_citation_per_bracket():
    """Pre-existing one-id-per-bracket behaviour preserved."""
    answer = (
        "Section 167(2) is the default-bail provision [doc_id: 199112586]. "
        "It was reaffirmed in [doc_id: 88760594]."
    )
    ids = extract_citations(answer)
    assert ids == ["199112586", "88760594"]


def test_multiple_citations_in_one_bracket():
    """Multiple doc_ids in a single bracket — the bug this commit fixes."""
    answer = (
        "Default bail is an indefeasible right "
        "[doc_id: A, doc_id: B, doc_id: C]."
    )
    ids = extract_citations(answer)
    assert ids == ["A", "B", "C"], (
        f"Expected all three ids, got {ids}. The single-id-per-bracket "
        "regex bug is resurfacing."
    )


def test_mixed_valid_and_hallucinated_in_bracket():
    """Hallucinations hidden in mixed brackets MUST be caught.

    This is the most important test in the file: the single-id regex
    would have silently passed the hallucinated FAKE_ID. The fixed
    regex catches it; the verifier flags it as invalid.
    """
    answer = (
        "The Court held the default-bail right is constitutional "
        "[doc_id: REAL_ID, doc_id: FAKE_ID]."
    )
    chunks = [{"doc_id": "REAL_ID", "text": "..."}]  # only REAL_ID retrieved
    result = verify_citations(answer, chunks)

    assert result["cited_count"] == 2, (
        f"Both ids in the bracket must count toward cited_count; "
        f"got {result['cited_count']}"
    )
    assert "REAL_ID" in result["valid_citations"]
    assert "FAKE_ID" in result["invalid_citations"], (
        "FAKE_ID hallucination must be flagged — silent passes here are "
        "exactly the failure mode the verifier was built to prevent"
    )
    assert result["all_valid"] is False


def test_complex_bracket_formats():
    """Mixed spacing, no spaces, plain text adjacent to doc_id, "=" form."""
    cases = [
        # (answer, expected_ids)
        ("[A, doc_id: B]", ["B"]),                 # plain "A" is not a citation
        ("[doc_id:A,doc_id:B]", ["A", "B"]),       # no spaces around colons or comma
        ("[ doc_id : A ]", ["A"]),                 # extra spaces
        ("[doc_id=X, doc_id=Y]", ["X", "Y"]),      # = instead of :
        ("[DOC_ID: X1, doc_id: X2]", ["X1", "X2"]),  # mixed case
        # Two separate brackets — order preserved across brackets too
        ("[doc_id: P1] then [doc_id: P2, doc_id: P3]", ["P1", "P2", "P3"]),
    ]
    for answer, expected in cases:
        ids = extract_citations(answer)
        assert ids == expected, (
            f"answer={answer!r}: expected {expected}, got {ids}"
        )


def test_verifier_correctly_separates_valid_and_hallucinated():
    """Verifier-contract test: with a known retrieval set and a synthetic
    LLM output mixing real and fabricated ids in a single bracket, the
    verifier must correctly partition them.

    This is the deterministic backstop for the project's headline claim
    ("we catch hallucinated citations"). The previous e2e test in
    test_rag.py implicitly asserted that Gemini never hallucinates,
    which we cannot control. This test asserts what we DO control: that
    given the LLM's output, our verifier separates valid from invalid
    correctly. Always passes regardless of LLM behaviour.
    """
    retrieved = [
        {"doc_id": "A", "text": "..."},
        {"doc_id": "B", "text": "..."},
        {"doc_id": "C", "text": "..."},
    ]
    answer = (
        "The court held the right is constitutional "
        "[doc_id: A, doc_id: D, doc_id: B, doc_id: HALLUCINATED]."
    )
    result = verify_citations(answer, retrieved)

    assert result["cited_count"] == 4, (
        f"All four ids in the multi-id bracket must be counted; "
        f"got {result['cited_count']}"
    )
    assert sorted(result["valid_citations"]) == ["A", "B"]
    assert sorted(result["invalid_citations"]) == ["D", "HALLUCINATED"]
    assert result["all_valid"] is False
