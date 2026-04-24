"""Criminal-case filter for Indian Kanoon judgment records.

Given the parsed-judgment dict produced by ``IndianKanoonScraper``, decide
whether the case is criminal in nature and how confident we are.

Rules
-----
Two independent signals:

1. **Case-style marker** — criminal-jurisdiction text appears in any of
   three places: the extracted ``title`` (often stripped by IK), the
   first 2000 chars of ``full_text`` (the judgment's own header, which
   preserves the case style), or the parsed ``case_number`` field if
   present. Markers include ``Crl.A.``, ``Criminal Appeal``, ``SLP
   (Crl)``, ``Crl.M.P.``, ``Crl.Rev.``, ``Criminal Revision``, ``Habeas
   Corpus``, ``CRIMINAL APPELLATE``, ``SPECIAL LEAVE PETITION (CRIMINAL)``,
   ``WRIT PETITION (CRIMINAL)``.

2. **Criminal act citation** — the judgment cites at least one act from
   the criminal corpus: IPC, BNS, CrPC, BNSS, NDPS Act, POCSO Act,
   Dowry Prohibition Act, SC/ST Act (recognised by the statute extractor),
   or UAPA, PMLA, Arms Act, Prevention of Corruption Act, Explosives Act,
   Juvenile Justice Act (scanned directly against ``full_text``).

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

# Case-style markers — applied against title, full_text header, and
# case_number field. Expanded vs the original title-only regex to also
# catch "CRIMINAL APPELLATE JURISDICTION", "SPECIAL LEAVE PETITION
# (CRIMINAL)", and "WRIT PETITION (CRIMINAL)" — all of which appear in
# IK judgment body text but not in <title>.
_CASE_STYLE_MARKERS = re.compile(
    r"\b("
    r"crl\.?\s*a\.?|"
    r"criminal\s+appeal|"
    r"slp\s*\(\s*crl|"
    r"crl\.?\s*m\.?\s*p\.?|"
    r"crl\.?\s*rev\.?|"
    r"criminal\s+revision|"
    r"habeas\s+corpus|"
    r"criminal\s+appellate|"
    r"special\s+leave\s+petition\s*\(\s*criminal|"
    r"writ\s+petition\s*\(\s*criminal"
    r")",
    flags=re.IGNORECASE,
)

# How far into full_text we scan for case-style markers. The Supreme
# Court's header block (jurisdiction, appeal number, parties, bench) is
# always within the first ~2K chars.
_HEADER_CHARS = 2000

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
    # Juvenile Justice Act variants — the parenthetical form, the bare
    # "Juvenile Justice Act" form (often seen with "2000" or "2015"),
    # and the "JJ Act" shorthand.
    (re.compile(
        r"Juvenile\s+Justice\s*\(\s*Care\s+and\s+Protection\s+of\s+Children\s*\)\s*Act(?:,?\s*(?:2000|2015))?",
        re.IGNORECASE,
    ), "Juvenile Justice Act"),
    (re.compile(r"Juvenile\s+Justice\s*\(.+?\)\s*Act", re.IGNORECASE), "Juvenile Justice Act"),
    (re.compile(r"Juvenile\s+Justice\s+Act(?:,?\s*(?:2000|2015))?", re.IGNORECASE), "Juvenile Justice Act"),
    (re.compile(r"\bJJ\s+Act\b"), "Juvenile Justice Act"),
]


Confidence = Literal["high", "medium", "low"]


def _case_style_hits(judgment: dict[str, Any]) -> bool:
    """Check the three case-style signals: title, full_text header, case_number."""
    title = judgment.get("title") or ""
    if _CASE_STYLE_MARKERS.search(title):
        return True
    full_text = judgment.get("full_text") or ""
    if full_text and _CASE_STYLE_MARKERS.search(full_text[:_HEADER_CHARS]):
        return True
    case_number = judgment.get("case_number") or ""
    if case_number and _CASE_STYLE_MARKERS.search(case_number):
        return True
    return False


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
    full_text = judgment.get("full_text") or ""
    statutes = judgment.get("statutes_cited") or []

    case_style_match = _case_style_hits(judgment)
    act_match = _statute_list_hits(statutes) or _text_scan_hits(full_text)

    if case_style_match and act_match:
        return True, "high"
    if case_style_match or act_match:
        return True, "medium"
    return False, "low"
