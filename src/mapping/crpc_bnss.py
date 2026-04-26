"""CrPC ↔ BNSS section mapping.

Loads the structured YAML at ``data/mappings/crpc_bnss_mapping.yaml`` and
exposes query helpers: forward lookup (CrPC → BNSS), reverse lookup
(BNSS → CrPC), subject search, and coverage stats.

The YAML file — not this module — is the source of truth for every
mapping. See ``data/mappings/README.md`` for the source hierarchy and
verification protocol.

This module is the structural sibling of ``src.mapping.ipc_bns`` (with
field renames for the procedural-code regime). A future ``evidence_bsa``
module will follow the same pattern.

Number-collision watch: CrPC has its own section 482 (HC inherent
powers, → BNSS 528) and BNSS has its own section 482 (anticipatory
bail, ← CrPC 438). The two are unrelated despite the matching number.
``tests/test_crpc_bnss_mapping.py::test_482_does_not_alias_to_482``
guards against autocomplete or copy-paste mistakes that would silently
introduce the wrong mapping.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_YAML = _PROJECT_ROOT / "data" / "mappings" / "crpc_bnss_mapping.yaml"

_VALID_RELATIONSHIPS = {
    "one_to_one",
    "one_to_many",
    "many_to_one",
    "removed",
    "new_in_bnss",
}


@dataclass(frozen=True)
class SectionMapping:
    """A single CrPC ↔ BNSS row.

    ``crpc_section`` is ``None`` only when ``relationship == "new_in_bnss"``.
    ``bnss_sections`` is an empty list only when ``relationship == "removed"``.
    """

    crpc_section: str | None
    bnss_sections: list[str]
    relationship: str
    subject: str
    crpc_title: str | None
    bnss_title: str | None
    notes: str | None = None
    needs_verification: bool = False
    # Canonical lookup key derived from crpc_section (stable across
    # "167(2)", "167 (2)", "S. 167(2)" spellings). Set during load.
    _crpc_key: str | None = field(default=None, compare=False, repr=False)


# ---- Section-id normalization ------------------------------------------


# Strip a leading "Section ", "Sec.", or "S." prefix. Alternatives MUST be
# ordered longest-first — regex alternation is greedy left-to-right, so
# "(SEC|SECTION)" would match "SEC" on "SECTION" and leave "TION".
_SEC_PREFIX_RE = re.compile(
    r"^(?:SECTION|SEC|S)\.?\s*",
    flags=re.IGNORECASE,
)


def _normalize_section(raw: str) -> str:
    """Canonicalize a section id for dict lookup.

    Handles all common procedural-code citation spellings:
      ``"S. 167(2)"``, ``"Sec. 167(2)"``, ``"Section 167 (2)"``,
      ``"167 (2)"``, ``"167(2)"`` → ``"167(2)"``
      ``"482"`` → ``"482"``  ``"354(3)"`` → ``"354(3)"``
    Uppercases letter suffixes (``"41a"`` → ``"41A"``) and collapses
    internal whitespace.
    """
    s = _SEC_PREFIX_RE.sub("", raw.strip())
    s = s.upper()
    s = re.sub(r"\s+", "", s)
    # Hyphen between digit and trailing single letter (e.g. legacy "498-A"
    # style) — collapse, mirroring the IPC↔BNS normalizer.
    s = re.sub(r"(\d)-([A-Z])(?!\w)", r"\1\2", s)
    return s


def _parent_section(key: str) -> str | None:
    """Return the parent section key for a sub-section lookup, or None.

    ``"167(2)"`` → ``"167"``. ``"354(3)"`` → ``"354"``. ``"482"`` → ``None``.
    """
    m = re.match(r"^(\d+[A-Z]?)\(", key)
    if m and m.group(1) != key:
        return m.group(1)
    return None


# ---- YAML load + validation --------------------------------------------


@dataclass(frozen=True)
class MappingTable:
    """In-memory view of the mapping YAML. One instance per file."""

    version: str
    source: str
    last_verified: str
    entries: tuple[SectionMapping, ...]
    # Indexes — all built once at load time.
    by_crpc: dict[str, SectionMapping]                # normalized CrPC key → entry
    by_bnss_strict: dict[str, list[SectionMapping]]   # exact BNSS key → entries
    by_bnss_rollup: dict[str, list[SectionMapping]]   # exact + parent-rollup → entries
    by_subject: dict[str, list[SectionMapping]]       # lowercased subject → entries


def _coerce_entry(raw: dict[str, Any], idx: int) -> SectionMapping:
    try:
        relationship = raw["relationship"]
    except KeyError as exc:
        raise ValueError(f"Entry #{idx}: missing 'relationship'") from exc

    if relationship not in _VALID_RELATIONSHIPS:
        raise ValueError(
            f"Entry #{idx}: invalid relationship {relationship!r}; "
            f"expected one of {sorted(_VALID_RELATIONSHIPS)}"
        )

    crpc = raw.get("crpc")
    bnss = raw.get("bnss") or []
    if not isinstance(bnss, list):
        raise ValueError(f"Entry #{idx}: 'bnss' must be a list, got {type(bnss).__name__}")

    if relationship == "new_in_bnss" and crpc is not None:
        raise ValueError(f"Entry #{idx}: new_in_bnss must have crpc: null")
    if relationship == "removed" and bnss:
        raise ValueError(f"Entry #{idx}: removed must have bnss: []")
    if relationship != "new_in_bnss" and crpc is None:
        raise ValueError(f"Entry #{idx}: crpc is null but relationship != new_in_bnss")

    crpc_str = str(crpc) if crpc is not None else None
    return SectionMapping(
        crpc_section=crpc_str,
        bnss_sections=[str(x) for x in bnss],
        relationship=relationship,
        subject=str(raw.get("subject") or "").strip(),
        crpc_title=raw.get("crpc_title"),
        bnss_title=raw.get("bnss_title"),
        notes=raw.get("notes"),
        needs_verification=bool(raw.get("needs_verification", False)),
        _crpc_key=_normalize_section(crpc_str) if crpc_str else None,
    )


def _build_indexes(entries: list[SectionMapping]) -> tuple[
    dict[str, SectionMapping],
    dict[str, list[SectionMapping]],
    dict[str, list[SectionMapping]],
    dict[str, list[SectionMapping]],
]:
    by_crpc: dict[str, SectionMapping] = {}
    by_bnss_strict: dict[str, list[SectionMapping]] = {}
    by_bnss_rollup: dict[str, list[SectionMapping]] = {}
    by_subject: dict[str, list[SectionMapping]] = {}

    for e in entries:
        if e._crpc_key is not None:
            if e._crpc_key in by_crpc:
                raise ValueError(
                    f"Duplicate CrPC section in mapping: {e.crpc_section!r} "
                    f"(normalized key {e._crpc_key!r})"
                )
            by_crpc[e._crpc_key] = e

        for bnss_sec in e.bnss_sections:
            k = _normalize_section(bnss_sec)
            by_bnss_strict.setdefault(k, []).append(e)
            by_bnss_rollup.setdefault(k, []).append(e)
            # Parent-rollup so "BNSS 187" returns entries stored under
            # 187(2), 187(3) etc. Dedup via id() since SectionMapping
            # contains an unhashable list.
            parent = _parent_section(k)
            if parent is not None:
                bucket = by_bnss_rollup.setdefault(parent, [])
                if not any(existing is e for existing in bucket):
                    bucket.append(e)

        if e.subject:
            by_subject.setdefault(e.subject.lower(), []).append(e)

    return by_crpc, by_bnss_strict, by_bnss_rollup, by_subject


@lru_cache(maxsize=4)
def _load_mapping_cached(path_str: str) -> MappingTable:
    path = Path(path_str)
    with path.open("r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    if not isinstance(doc, dict) or "mappings" not in doc:
        raise ValueError(f"{path}: top-level 'mappings' key missing")

    raw_entries = doc["mappings"] or []
    entries = [_coerce_entry(raw, i) for i, raw in enumerate(raw_entries)]
    by_crpc, by_bnss_strict, by_bnss_rollup, by_subject = _build_indexes(entries)

    return MappingTable(
        version=str(doc.get("version", "")),
        source=str(doc.get("source", "")),
        last_verified=str(doc.get("last_verified", "")),
        entries=tuple(entries),
        by_crpc=by_crpc,
        by_bnss_strict=by_bnss_strict,
        by_bnss_rollup=by_bnss_rollup,
        by_subject=by_subject,
    )


def load_mapping(path: str | Path | None = None) -> MappingTable:
    """Load (and cache) the CrPC↔BNSS mapping file.

    Call without arguments for the project-default YAML.
    """
    p = Path(path) if path is not None else _DEFAULT_YAML
    return _load_mapping_cached(str(p.resolve()))


# ---- Public query API --------------------------------------------------


def map_crpc_to_bnss(section: str, *, table: MappingTable | None = None) -> SectionMapping | None:
    """Return the mapping entry for a CrPC section, or ``None`` if unmapped.

    Accepts common procedural-code citation spellings (``"167(2)"``,
    ``"167 (2)"``, ``"S. 167(2)"``, ``"Sec. 167(2)"``, ``"Section 167(2)"``).
    For a sub-section like ``"167(2)"``, falls back to the parent section
    ``"167"`` if no exact entry exists.
    """
    t = table or load_mapping()
    key = _normalize_section(section)
    hit = t.by_crpc.get(key)
    if hit is not None:
        return hit
    parent = _parent_section(key)
    if parent is not None:
        return t.by_crpc.get(parent)
    return None


def map_bnss_to_crpc(
    section: str,
    *,
    table: MappingTable | None = None,
    return_mode: Literal["rollup", "strict"] = "rollup",
) -> list[SectionMapping]:
    """Return all CrPC entries that map to a given BNSS section.

    BNSS consolidations are common (e.g., BNSS 187 ← CrPC 167 + sub-sections),
    so the return type is always a list. For a ``new_in_bnss`` section,
    returns a single-element list with ``crpc_section is None``.

    ``return_mode`` controls whether parent-section rollup applies:

    - ``"rollup"`` (default) — lookup of a parent like ``"187"`` also
      returns entries whose ``bnss_sections`` contain sub-sections of 187
      (e.g. ``187(2)``, ``187(3)``).
    - ``"strict"`` — only entries whose ``bnss_sections`` list contains
      the exact input string (after normalization).
    """
    t = table or load_mapping()
    key = _normalize_section(section)
    if return_mode == "strict":
        return list(t.by_bnss_strict.get(key, []))
    if return_mode != "rollup":
        raise ValueError(
            f"return_mode must be 'rollup' or 'strict', got {return_mode!r}"
        )
    hits = list(t.by_bnss_rollup.get(key, []))
    if hits:
        return hits
    parent = _parent_section(key)
    if parent is not None:
        return list(t.by_bnss_rollup.get(parent, []))
    return []


def search_by_subject(subject: str, *, table: MappingTable | None = None) -> list[SectionMapping]:
    """Find all entries whose subject contains the query (case-insensitive)."""
    t = table or load_mapping()
    needle = subject.strip().lower()
    if not needle:
        return []
    seen: set[int] = set()
    out: list[SectionMapping] = []
    for subj, entries in t.by_subject.items():
        if needle in subj:
            for e in entries:
                if id(e) in seen:
                    continue
                seen.add(id(e))
                out.append(e)
    return out


def stats(*, table: MappingTable | None = None) -> dict[str, Any]:
    """Coverage and quality summary for the loaded mapping."""
    t = table or load_mapping()
    by_rel: dict[str, int] = {}
    unverified = 0
    crpc_count = 0
    bnss_count = 0
    for e in t.entries:
        by_rel[e.relationship] = by_rel.get(e.relationship, 0) + 1
        if e.needs_verification:
            unverified += 1
        if e.crpc_section is not None:
            crpc_count += 1
        bnss_count += len(e.bnss_sections)

    total = len(t.entries)
    return {
        "version": t.version,
        "source": t.source,
        "last_verified": t.last_verified,
        "total_entries": total,
        "by_relationship": by_rel,
        "crpc_sections_covered": crpc_count,
        "bnss_sections_covered": bnss_count,
        "needs_verification_count": unverified,
        "verified_fraction": (
            round((total - unverified) / total, 3) if total else 0.0
        ),
    }
