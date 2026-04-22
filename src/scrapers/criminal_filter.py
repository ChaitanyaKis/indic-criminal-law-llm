"""Criminal-case filter for Indian Kanoon judgment records.

Given the parsed-judgment dict produced by ``IndianKanoonScraper``, decide
whether the case is criminal in nature and how confident we are.

Rules
-----
Two independent signals:

1. **Title marker** — the case heading contains a criminal-jurisdiction
   marker (``Crl.A.``, ``Criminal Appeal``, ``SLP (Crl)``, ``Crl.M.P.``,
   ``Crl.Rev.``, ``Criminal Revision``, ``Habeas Corpus``).

2. **Criminal act citation** — the judgment text cites at least one act
   from the criminal corpus: IPC, BNS, CrPC, BNSS, NDPS Act, POCSO Act,
   Dowry Prohibition Act, SC/ST Act (all recognised by our extractor),
   or UAPA, PMLA, Arms Act, Prevention of Corruption Act, Explosives Act,
   Juvenile Justice Act (scanned directly against ``full_text`` because
   the statute extractor doesn't yet know these).

Confidence:
  - ``high``   — both signals match
  - ``medium`` — exactly one matches
  - ``low``    — neither (returned alongside ``kept=False``)

Edge cases
----------
Civil cases that merely cite the IPC in passing (rare but real — e.g.
civil defamation suits citing IPC 499 for definition) will register as
``medium``. That's intended: keep for manual review rather than silently
drop. The filter is recall-biased by design; precision work happens at
the corpus-cleaning stage.
"""

from __future__ import annotations

import re
from typing import Any, Literal

_TITLE_MARKERS = re.compile(
    r"("
    r"Crl\.A\.|"
    r"Criminal\s+Appeal|"
    r"SLP\s*\(\s*Crl|"
    r"Crl\.M\.P\.|"
    r"Crl\.Rev\.|"
    r"Habeas\s+Corpus|"
    r"Criminal\s+Revision"
    r")",
    flags=re.IGNORECASE,
)

_CRIMINAL_ACTS_IN_EXTRACTOR: frozenset[str] = frozenset({
    "IPC",
    "BNS",
    "CrPC",
    "BNSS",
    "NDPS Act",
    "POCSO Act",
    "Dowry Prohibition Act",
    "SC/ST Act",
})

# Acts our statute extractor does NOT yet know about — scanned as plain
# substrings against the full judgment text. Each row is (regex, label).
# Label is unused by the current filter but kept for future telemetry.
_CRIMINAL_ACTS_TEXT_SCAN: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Unlawful\s+Activities\s*\(\s*Prevention\s*\)\s*Act", re.IGNORECASE), "UAPA"),
    (re.compile(r"\bU\.?\s*A\.?\s*P\.?\s*A\.?\b"), "UAPA"),
    (re.compile(r"Prevention\s+of\s+Money[\s-]*Laundering\s+Act", re.IGNORECASE), "PMLA"),
    (re.compile(r"\bP\.?\s*M\.?\s*L\.?\s*A\.?\b"), "PMLA"),
    (re.compile(r"Prevention\s+of\s+Corruption\s+Act", re.IGNORECASE), "POCA"),
    (re.compile(r"\bArms\s+Act\b", re.IGNORECASE), "Arms Act"),
    (re.compile(r"\bExplosives?\s+Act\b", re.IGNORECASE), "Explosives Act"),
    (re.compile(r"Juvenile\s+Justice\s*\(.+?\)\s*Act", re.IGNORECASE), "Juvenile Justice Act"),
]


Confidence = Literal["high", "medium", "low"]


def _title_hits(title: str) -> bool:
    return bool(_TITLE_MARKERS.search(title or ""))


def _statute_list_hits(statutes_cited: list[dict[str, Any]]) -> bool:
    for s in statutes_cited or []:
        if s.get("act") in _CRIMINAL_ACTS_IN_EXTRACTOR:
            return True
    return False


def _text_scan_hits(full_text: str) -> bool:
    if not full_text:
        return False
    for pattern, _label in _CRIMINAL_ACTS_TEXT_SCAN:
        if pattern.search(full_text):
            return True
    return False


def is_criminal(judgment: dict[str, Any]) -> tuple[bool, Confidence]:
    """Classify a judgment as criminal (high / medium) or non-criminal (low).

    Returns ``(kept, confidence)``. ``kept`` is True iff confidence is
    ``"high"`` or ``"medium"``.
    """
    title = judgment.get("title") or ""
    full_text = judgment.get("full_text") or ""
    statutes = judgment.get("statutes_cited") or []

    title_match = _title_hits(title)
    act_match = _statute_list_hits(statutes) or _text_scan_hits(full_text)

    if title_match and act_match:
        return True, "high"
    if title_match or act_match:
        return True, "medium"
    return False, "low"
