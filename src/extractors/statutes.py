"""Statute and constitutional citation extraction from Indian legal text.

Returns normalized citation dicts:
    [{"act": "IPC", "section": "498A", "raw": "Section 498-A IPC"}, ...]

- Deduplicated by ``(act, section)`` tuple.
- Ordered by first appearance in the input text.
- Forward direction ("Section X of <Act>") and reverse ("<Act> Section X").
- Section-number formats: 302, 498A, 498-A, 498 A, 167(2), 41(1)(a).
- Section lists: "302 and 304", "302, 303 and 306", "&".
- Ranges: "302 to 304" and "302-304" (expanded individually).
- Constitutional articles: "Article 21", "Article 22(2)", "Articles 14, 19 and 21".

The canonical act table is the single source of truth; to support a new
act, add a row to ``_ACT_TABLE`` with its canonical name and regex alternates.
"""

from __future__ import annotations

import re

# TODO: Amendment Acts (e.g., "Code of Criminal Procedure (Amendment)
# Act, 2008") currently match the base act greedy pattern. Fix by
# either (a) negative lookahead for "(Amendment)" after act name, or
# (b) separate entries in the act table for common amendment acts.
# Low priority — affects <5% of citations, doesn't corrupt existing
# extractions, just overcounts. Revisit before IPC↔BNS mapping phase.

# (canonical_name, [regex_alternates])
# Ordering: most-specific first. Prevents prefix collisions where a shorter
# abbreviation would otherwise swallow a longer one (e.g. BNSS before BNS).
_ACT_TABLE: list[tuple[str, list[str]]] = [
    ("BNSS", [
        r"Bharatiya\s+Nagarik\s+Suraksha\s+Sanhita(?:,?\s*2023)?",
        r"B\.\s*N\.\s*S\.\s*S\.?",
        r"BNSS",
    ]),
    ("BNS", [
        r"Bharatiya\s+Nyaya\s+Sanhita(?:,?\s*2023)?",
        r"B\.\s*N\.\s*S\.?(?!\s*S)",
        r"BNS(?!S)",
    ]),
    ("BSA", [
        r"Bharatiya\s+Sakshya\s+Adhiniyam(?:,?\s*2023)?",
        r"B\.\s*S\.\s*A\.?",
        r"BSA",
    ]),
    ("IPC", [
        r"Indian\s+Penal\s+Code(?:,?\s*1860)?",
        r"Penal\s+Code",
        r"I\.\s*P\.\s*C\.?",
        r"IPC",
    ]),
    ("CrPC", [
        r"Code\s+of\s+Criminal\s+Procedure(?:,?\s*1973)?",
        r"Criminal\s+Procedure\s+Code(?:,?\s*1973)?",
        r"Cr\.?\s*P\.?\s*C\.?",
        r"CrPC",
    ]),
    ("Evidence Act", [
        r"Indian\s+Evidence\s+Act(?:,?\s*1872)?",
        r"Evidence\s+Act(?:,?\s*1872)?",
        r"I\.\s*E\.\s*A\.?",
        r"IEA",
    ]),
    ("NDPS Act", [
        r"Narcotic\s+Drugs\s+and\s+Psychotropic\s+Substances\s+Act(?:,?\s*1985)?",
        r"N\.\s*D\.\s*P\.\s*S\.?\s+Act",
        r"NDPS\s+Act",
        r"NDPS",
    ]),
    ("POCSO Act", [
        r"Protection\s+of\s+Children\s+from\s+Sexual\s+Offences\s+Act(?:,?\s*2012)?",
        r"POCSO\s+Act",
        r"POCSO",
    ]),
    ("Dowry Prohibition Act", [
        r"Dowry\s+Prohibition\s+Act(?:,?\s*1961)?",
        r"D\.\s*P\.?\s+Act",
    ]),
    ("SC/ST Act", [
        r"Scheduled\s+Castes?\s+and\s+Scheduled\s+Tribes\s*\(\s*Prevention\s+of\s+Atrocities\s*\)\s*Act(?:,?\s*1989)?",
        r"SC\s*/\s*ST\s*\(?\s*Prevention\s+of\s+Atrocities\s*\)?\s*Act",
        r"SC\s*/\s*ST\s+Act",
    ]),
]


def _build_act_alt() -> str:
    parts: list[str] = []
    for _, alts in _ACT_TABLE:
        parts.extend(alts)
    return "(?:" + "|".join(parts) + ")"


_ACT_ALT = _build_act_alt()


def _normalize_act(raw: str) -> str | None:
    """Resolve a raw act string (as captured) to its canonical name."""
    cleaned = raw.strip().rstrip(",.")
    for canonical, alts in _ACT_TABLE:
        for alt in alts:
            if re.fullmatch(alt, cleaned, flags=re.IGNORECASE):
                return canonical
    return None


# One section token. Accepts: 302, 498A, 498-A, 498 A, 167(2), 41(1)(a).
# The (?!\w) after the suffix letter prevents gluing onto a following word
# (so "498A" matches but "498Adam" doesn't treat A as a suffix).
_SEC_NUM = r"\d+(?:\s*-?\s*[A-Z](?!\w))?(?:\s*\([^)\n]{1,20}\))*"

# A list: one or more section tokens joined by ",", "&", "and", "to", "-", "–".
_SEC_LIST = rf"{_SEC_NUM}(?:\s*(?:,|&|\band\b|\bto\b|-|–|—)\s*{_SEC_NUM})*"

# "Section", "Sections", "Sec.", "Secs.", "S." — but NOT bare "s" (too noisy).
_SEC_HDR = r"(?:sections?|secs?\.|s\.)"

# Forward: "Section X [of [the]] ACT" or "Section X, ACT".
_FORWARD = re.compile(
    rf"\b{_SEC_HDR}\s*({_SEC_LIST})\s*,?\s*(?:of\s+(?:the\s+)?)?({_ACT_ALT})\b",
    flags=re.IGNORECASE,
)

# Reverse: "ACT Section X" or "ACT, Section X".
_REVERSE = re.compile(
    rf"\b({_ACT_ALT})\s*,?\s*{_SEC_HDR}\s*({_SEC_LIST})",
    flags=re.IGNORECASE,
)

# Constitutional articles. Indian judgments virtually always mean the
# Constitution of India when they say "Article N".
# No trailing \b: SEC_LIST can end in ")" (sub-section), which is a non-word
# char — \b would fail there and force the engine to backtrack and drop the
# sub-section, turning "Article 22(2)" into "Article 22".
_ARTICLE = re.compile(
    rf"\bArticles?\.?\s+({_SEC_LIST})",
    flags=re.IGNORECASE,
)

_RANGE_WORD = re.compile(r"^(\d+)\s*(?:to|–|—)\s*(\d+)$", flags=re.IGNORECASE)
_RANGE_HYPHEN = re.compile(r"^(\d+)\s*-\s*(\d+)$")
_SINGLE = re.compile(r"^(\d+)(?:\s*-?\s*([A-Z]))?((?:\s*\([^)]+\))*)\s*$")

_MAX_RANGE = 50  # sanity cap; ranges wider than this are suspicious


def _expand_section_list(raw: str) -> list[str]:
    """Split a captured section list into individual normalized sections."""
    out: list[str] = []
    # Split on top-level separators: comma, ampersand, " and "
    # (but NOT "to"/"-"/dashes — those are ranges, handled per-part).
    parts = re.split(r"\s*(?:,|&|\band\b)\s*", raw, flags=re.IGNORECASE)
    for part in parts:
        part = part.strip()
        if not part:
            continue

        m = _RANGE_WORD.match(part)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            if 0 < end - start <= _MAX_RANGE:
                out.extend(str(n) for n in range(start, end + 1))
                continue

        m = _RANGE_HYPHEN.match(part)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            if 0 < end - start <= _MAX_RANGE:
                out.extend(str(n) for n in range(start, end + 1))
                continue

        m = _SINGLE.match(part)
        if m:
            num = m.group(1)
            letter = (m.group(2) or "").upper()
            subs = re.sub(r"\s+", "", m.group(3) or "")
            out.append(f"{num}{letter}{subs}")
    return out


def enrich_with_bns_mapping(citations: list[dict]) -> list[dict]:
    """Annotate IPC citations with their BNS equivalent.

    Takes the output of :func:`extract_statutes` and returns a new list with
    the same entries, each IPC citation additionally carrying a
    ``"bns_equivalent"`` key describing the mapping. Non-IPC entries are
    passed through unchanged.

    The ``bns_equivalent`` value is either ``None`` (no mapping found) or a
    dict::

        {
            "bns_sections": ["85", "86"],
            "relationship": "one_to_many",
            "subject": "Cruelty by husband or his relatives",
            "needs_verification": False,
            "notes": "...",
        }

    CrPC ↔ BNSS and Evidence Act ↔ BSA enrichment is intentionally not
    wired in yet — those mapping modules are still to be built.
    """
    # Imported here to keep the extractor import-safe even if the mapping
    # data file is temporarily absent (e.g. during early corpus setup).
    from src.mapping.ipc_bns import map_ipc_to_bns

    enriched: list[dict] = []
    for c in citations:
        out = dict(c)
        if c.get("act") == "IPC":
            m = map_ipc_to_bns(c.get("section", ""))
            if m is None:
                out["bns_equivalent"] = None
            else:
                out["bns_equivalent"] = {
                    "bns_sections": list(m.bns_sections),
                    "relationship": m.relationship,
                    "subject": m.subject,
                    "needs_verification": m.needs_verification,
                    "notes": m.notes,
                }
        enriched.append(out)
    return enriched


def extract_statutes(text: str) -> list[dict]:
    """Extract normalized statute/constitutional citations from legal text.

    Returns a list of dicts ``{"act", "section", "raw"}``, deduplicated by
    (act, section) and ordered by first appearance in ``text``.
    """
    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[int, dict]] = []

    def add(act: str, section: str, raw: str, pos: int) -> None:
        key = (act, section)
        if key in seen:
            return
        seen.add(key)
        ordered.append((pos, {"act": act, "section": section, "raw": raw}))

    for m in _FORWARD.finditer(text):
        raw_list, raw_act = m.group(1), m.group(2)
        act = _normalize_act(raw_act)
        if not act:
            continue
        raw_match = re.sub(r"\s+", " ", m.group(0)).strip()
        for sec in _expand_section_list(raw_list):
            add(act, sec, raw_match, m.start())

    for m in _REVERSE.finditer(text):
        raw_act, raw_list = m.group(1), m.group(2)
        act = _normalize_act(raw_act)
        if not act:
            continue
        raw_match = re.sub(r"\s+", " ", m.group(0)).strip()
        for sec in _expand_section_list(raw_list):
            add(act, sec, raw_match, m.start())

    for m in _ARTICLE.finditer(text):
        raw_list = m.group(1)
        raw_match = re.sub(r"\s+", " ", m.group(0)).strip()
        for sec in _expand_section_list(raw_list):
            add("Constitution", f"Article {sec}", raw_match, m.start())

    ordered.sort(key=lambda t: t[0])
    return [d for _, d in ordered]
