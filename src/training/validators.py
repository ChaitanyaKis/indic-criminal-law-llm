"""Quality checks for instruction-dataset records.

Each ``check_*`` function returns ``None`` when the record passes and
a short reason string when it fails. The orchestrator collects
rejections to ``data/processed/_state/dataset_v0.1_rejected.jsonl``
with the reason attached, so quality issues are auditable rather
than silently dropped.

Validation philosophy: reject obvious garbage, but don't second-guess
content. A record that passes the structural and corpus-leakage
checks should be a defensible training pair.
"""

from __future__ import annotations

import re
from typing import Any, Callable

MIN_INSTRUCTION_LEN = 10
MAX_INSTRUCTION_LEN = 500
MIN_OUTPUT_LEN = 30
MAX_OUTPUT_LEN = 4000

# Patterns that indicate corpus-chunk leakage into the output. The
# generator's authored answers should never contain these — they only
# show up if a doc_id, chunk header, or score got copy-pasted from a
# retrieved chunk.
_LEAKAGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bdoc_id\s*[:=]\s*\d", re.IGNORECASE),
    re.compile(r"^---\s*Chunk\s+\d", re.MULTILINE | re.IGNORECASE),
    re.compile(r"\bscore\s*=\s*0\.\d{2,4}", re.IGNORECASE),
)

_REPEATED_CHAR_RE = re.compile(r"(.)\1{8,}")  # 9+ of the same char in a row


def check_lengths(rec: dict[str, Any]) -> str | None:
    inst = rec.get("instruction", "") or ""
    out = rec.get("output", "") or ""
    if len(inst) < MIN_INSTRUCTION_LEN:
        return f"instruction too short ({len(inst)} < {MIN_INSTRUCTION_LEN})"
    if len(inst) > MAX_INSTRUCTION_LEN:
        return f"instruction too long ({len(inst)} > {MAX_INSTRUCTION_LEN})"
    if len(out) < MIN_OUTPUT_LEN:
        return f"output too short ({len(out)} < {MIN_OUTPUT_LEN})"
    if len(out) > MAX_OUTPUT_LEN:
        return f"output too long ({len(out)} > {MAX_OUTPUT_LEN})"
    return None


def check_no_corpus_leakage(rec: dict[str, Any]) -> str | None:
    out = rec.get("output", "") or ""
    for p in _LEAKAGE_PATTERNS:
        m = p.search(out)
        if m:
            return f"corpus leakage in output: matches {p.pattern!r}"
    return None


def check_not_garbage(rec: dict[str, Any]) -> str | None:
    """Flag obvious garbage: all-caps spam, long repeated-char runs."""
    for field in ("instruction", "output"):
        text = rec.get(field, "") or ""
        # All-caps with at least 30 chars and 70%+ uppercase letters
        letters = [c for c in text if c.isalpha()]
        if len(letters) >= 30:
            up_frac = sum(1 for c in letters if c.isupper()) / len(letters)
            if up_frac > 0.7:
                return f"{field} appears all-caps ({up_frac:.0%} upper)"
        if _REPEATED_CHAR_RE.search(text):
            return f"{field} contains long repeated-char run"
    return None


_CHECKS: tuple[Callable[[dict[str, Any]], str | None], ...] = (
    check_lengths,
    check_no_corpus_leakage,
    check_not_garbage,
)


def validate(rec: dict[str, Any]) -> str | None:
    """Run all individual checks. Return reason of first failure, or None."""
    for c in _CHECKS:
        reason = c(rec)
        if reason is not None:
            return reason
    return None


class DuplicateInstructionTracker:
    """Stateful check for exact-duplicate instructions across the dataset."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def check(self, rec: dict[str, Any]) -> str | None:
        inst = (rec.get("instruction") or "").strip().lower()
        if not inst:
            return "empty instruction"
        if inst in self._seen:
            return "duplicate instruction"
        self._seen.add(inst)
        return None
