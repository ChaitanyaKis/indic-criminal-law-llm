"""Citation verifier — catches hallucinated doc_id references.

The generator is instructed to cite sources as ``[doc_id: <id>, ...]`` or
``[doc_id: <id>]``. This module extracts every such citation from the
answer, checks each against the ``doc_id`` set of the retrieved chunks,
and reports any that don't match. A citation to a doc_id that wasn't in
the retrieval context is a hallucination and must be flagged.

Downstream (future work) we'll also track *unsupported claims* — assertions
that carry no citation. That's semantically harder (needs claim detection)
and is stubbed out in the return shape for now.
"""

from __future__ import annotations

import re
from typing import Any

# Matches:  [doc_id: 12345]   or   [doc_id: 12345, short excerpt...]
# also tolerates "doc_id=12345" and plain bracket form, case-insensitive.
_CITATION_PATTERN = re.compile(
    r"\[\s*doc_id\s*[:=]\s*([A-Za-z0-9_\-]+)",
    flags=re.IGNORECASE,
)


def extract_citations(answer: str) -> list[str]:
    """Return the list of doc_ids referenced in the answer, in order of
    first appearance, deduplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _CITATION_PATTERN.finditer(answer or ""):
        did = m.group(1)
        if did in seen:
            continue
        seen.add(did)
        out.append(did)
    return out


def verify_citations(
    answer: str, retrieved_chunks: list[dict[str, Any]] | list,
) -> dict[str, Any]:
    """Check that every ``[doc_id: X]`` citation in ``answer`` refers to a
    doc_id present in the retrieved chunks.

    ``retrieved_chunks`` may be a list of :class:`RetrievedChunk` objects
    or plain dicts with a ``doc_id`` key.

    Returns::

        {
          "all_valid": bool,
          "valid_citations": [doc_id, ...],
          "invalid_citations": [doc_id, ...],
          "cited_count": int,
          "unsupported_claims": [],   # stub for future claim-level check
        }
    """
    valid_ids: set[str] = set()
    for c in retrieved_chunks or []:
        did = getattr(c, "doc_id", None) if not isinstance(c, dict) else c.get("doc_id")
        if did is not None:
            valid_ids.add(str(did))

    cited = extract_citations(answer or "")
    valid: list[str] = []
    invalid: list[str] = []
    for did in cited:
        if did in valid_ids:
            valid.append(did)
        else:
            invalid.append(did)

    return {
        "all_valid": len(invalid) == 0,
        "valid_citations": valid,
        "invalid_citations": invalid,
        "cited_count": len(cited),
        "unsupported_claims": [],
    }
