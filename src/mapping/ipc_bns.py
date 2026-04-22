"""IPC ↔ BNS section mapping.

Loads the structured YAML at ``data/mappings/ipc_bns_mapping.yaml`` and
exposes query helpers: forward lookup (IPC → BNS), reverse lookup
(BNS → IPC), subject search, and coverage stats.

The YAML file — not this module — is the source of truth for every
mapping. See ``data/mappings/README.md`` for the source hierarchy and
verification protocol.

Sibling modules planned for later weeks:
    - ``src.mapping.crpc_bnss``   CrPC → BNSS
    - ``src.mapping.evidence_bsa``  Evidence Act → BSA
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_YAML = _PROJECT_ROOT / "data" / "mappings" / "ipc_bns_mapping.yaml"

_VALID_RELATIONSHIPS = {
    "one_to_one",
    "one_to_many",
    "many_to_one",
    "removed",
    "new_in_bns",
}


@dataclass(frozen=True)
class SectionMapping:
    """A single IPC ↔ BNS row.

    ``ipc_section`` is ``None`` only when ``relationship == "new_in_bns"``.
    ``bns_sections`` is an empty list only when ``relationship == "removed"``.
    """

    ipc_section: str | None
    bns_sections: list[str]
    relationship: str
    subject: str
    ipc_title: str | None
    bns_title: str | None
    notes: str | None = None
    needs_verification: bool = False
    # Canonical lookup key derived from ipc_section (stable across
    # "498A" / "498-A" / "498 A" spellings). Set during load.
    _ipc_key: str | None = field(default=None, compare=False, repr=False)


# ---- Section-id normalization ------------------------------------------


def _normalize_section(raw: str) -> str:
    """Canonicalize a section id for dict lookup.

    ``"498-A"``, ``"498 A"``, ``"498A"`` → ``"498A"``.
    ``"41 (1)(b)"`` → ``"41(1)(b)"``. Preserves parentheses verbatim.
    """
    s = raw.strip().upper()
    s = re.sub(r"\s+", "", s)
    # Strip a hyphen only when it sits between a digit and a letter suffix
    # (498-A → 498A). Do NOT strip hyphens in "304-II" style roman suffixes
    # or anywhere else — those stay literal for now.
    s = re.sub(r"(\d)-([A-Z])(?!\w)", r"\1\2", s)
    return s


def _parent_section(key: str) -> str | None:
    """Return the parent section key for a sub-section lookup, or None.

    ``"304(2)"`` → ``"304"``. ``"498A(1)"`` → ``"498A"``. ``"302"`` → ``None``.
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
    by_ipc: dict[str, SectionMapping]                # normalized IPC key → entry
    by_bns_strict: dict[str, list[SectionMapping]]   # exact BNS key → entries
    by_bns_rollup: dict[str, list[SectionMapping]]   # exact + parent-rollup → entries
    by_subject: dict[str, list[SectionMapping]]      # lowercased subject → entries


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

    ipc = raw.get("ipc")
    bns = raw.get("bns") or []
    if not isinstance(bns, list):
        raise ValueError(f"Entry #{idx}: 'bns' must be a list, got {type(bns).__name__}")

    if relationship == "new_in_bns" and ipc is not None:
        raise ValueError(f"Entry #{idx}: new_in_bns must have ipc: null")
    if relationship == "removed" and bns:
        raise ValueError(f"Entry #{idx}: removed must have bns: []")
    if relationship != "new_in_bns" and ipc is None:
        raise ValueError(f"Entry #{idx}: ipc is null but relationship != new_in_bns")

    ipc_str = str(ipc) if ipc is not None else None
    return SectionMapping(
        ipc_section=ipc_str,
        bns_sections=[str(x) for x in bns],
        relationship=relationship,
        subject=str(raw.get("subject") or "").strip(),
        ipc_title=raw.get("ipc_title"),
        bns_title=raw.get("bns_title"),
        notes=raw.get("notes"),
        needs_verification=bool(raw.get("needs_verification", False)),
        _ipc_key=_normalize_section(ipc_str) if ipc_str else None,
    )


def _build_indexes(entries: list[SectionMapping]) -> tuple[
    dict[str, SectionMapping],
    dict[str, list[SectionMapping]],
    dict[str, list[SectionMapping]],
    dict[str, list[SectionMapping]],
]:
    by_ipc: dict[str, SectionMapping] = {}
    by_bns_strict: dict[str, list[SectionMapping]] = {}
    by_bns_rollup: dict[str, list[SectionMapping]] = {}
    by_subject: dict[str, list[SectionMapping]] = {}

    for e in entries:
        if e._ipc_key is not None:
            if e._ipc_key in by_ipc:
                raise ValueError(
                    f"Duplicate IPC section in mapping: {e.ipc_section!r} "
                    f"(normalized key {e._ipc_key!r})"
                )
            by_ipc[e._ipc_key] = e

        for bns_sec in e.bns_sections:
            k = _normalize_section(bns_sec)
            by_bns_strict.setdefault(k, []).append(e)
            by_bns_rollup.setdefault(k, []).append(e)
            # Parent-rollup index so "BNS 316" returns entries stored under
            # 316(1), 316(2), 316(5). Dedup via id() since SectionMapping
            # contains an unhashable list.
            parent = _parent_section(k)
            if parent is not None:
                bucket = by_bns_rollup.setdefault(parent, [])
                if not any(existing is e for existing in bucket):
                    bucket.append(e)

        if e.subject:
            by_subject.setdefault(e.subject.lower(), []).append(e)

    return by_ipc, by_bns_strict, by_bns_rollup, by_subject


@lru_cache(maxsize=4)
def _load_mapping_cached(path_str: str) -> MappingTable:
    path = Path(path_str)
    with path.open("r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    if not isinstance(doc, dict) or "mappings" not in doc:
        raise ValueError(f"{path}: top-level 'mappings' key missing")

    raw_entries = doc["mappings"] or []
    entries = [_coerce_entry(raw, i) for i, raw in enumerate(raw_entries)]
    by_ipc, by_bns_strict, by_bns_rollup, by_subject = _build_indexes(entries)

    return MappingTable(
        version=str(doc.get("version", "")),
        source=str(doc.get("source", "")),
        last_verified=str(doc.get("last_verified", "")),
        entries=tuple(entries),
        by_ipc=by_ipc,
        by_bns_strict=by_bns_strict,
        by_bns_rollup=by_bns_rollup,
        by_subject=by_subject,
    )


def load_mapping(path: str | Path | None = None) -> MappingTable:
    """Load (and cache) the IPC↔BNS mapping file.

    Call without arguments for the project-default YAML.
    """
    p = Path(path) if path is not None else _DEFAULT_YAML
    return _load_mapping_cached(str(p.resolve()))


# ---- Public query API --------------------------------------------------


def map_ipc_to_bns(section: str, *, table: MappingTable | None = None) -> SectionMapping | None:
    """Return the mapping entry for an IPC section, or ``None`` if unmapped.

    Accepts any reasonable spelling (``"498A"``, ``"498-A"``, ``"498 A"``).
    For a sub-section like ``"304(2)"``, falls back to the parent section
    ``"304"`` if no exact entry exists — this reflects the common case where
    the YAML maps at the parent-section level.
    """
    t = table or load_mapping()
    key = _normalize_section(section)
    hit = t.by_ipc.get(key)
    if hit is not None:
        return hit
    parent = _parent_section(key)
    if parent is not None:
        return t.by_ipc.get(parent)
    return None


def map_bns_to_ipc(
    section: str,
    *,
    table: MappingTable | None = None,
    return_mode: Literal["rollup", "strict"] = "rollup",
) -> list[SectionMapping]:
    """Return all IPC entries that map to a given BNS section.

    BNS consolidations are common (e.g., BNS 316 ← IPC 405, 406, 409), so the
    return type is always a list. For a ``new_in_bns`` section, returns a
    single-element list with ``ipc_section is None``. Unknown section → ``[]``.

    ``return_mode`` controls whether parent-section rollup applies:

    - ``"rollup"`` (default) — lookup of a parent section like ``"316"`` also
      returns entries whose ``bns_sections`` contain sub-sections of 316 (e.g.
      ``316(1)``, ``316(2)``, ``316(5)``). Matches lawyer intuition when asked
      *"what IPC sections does BNS 316 correspond to?"*.
    - ``"strict"`` — only entries whose ``bns_sections`` list contains the
      exact input string (after normalization). Useful for reverse-indexing
      citations where precision matters more than recall.
    """
    t = table or load_mapping()
    key = _normalize_section(section)
    if return_mode == "strict":
        return list(t.by_bns_strict.get(key, []))
    if return_mode != "rollup":
        raise ValueError(
            f"return_mode must be 'rollup' or 'strict', got {return_mode!r}"
        )
    hits = list(t.by_bns_rollup.get(key, []))
    if hits:
        return hits
    parent = _parent_section(key)
    if parent is not None:
        return list(t.by_bns_rollup.get(parent, []))
    return []


def search_by_subject(subject: str, *, table: MappingTable | None = None) -> list[SectionMapping]:
    """Find all entries whose subject contains the query (case-insensitive).

    Matches as substring so ``"murder"`` catches entries subjected "Murder"
    and "Murder by life-convict".
    """
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
    ipc_count = 0
    bns_count = 0
    for e in t.entries:
        by_rel[e.relationship] = by_rel.get(e.relationship, 0) + 1
        if e.needs_verification:
            unverified += 1
        if e.ipc_section is not None:
            ipc_count += 1
        bns_count += len(e.bns_sections)

    total = len(t.entries)
    return {
        "version": t.version,
        "source": t.source,
        "last_verified": t.last_verified,
        "total_entries": total,
        "by_relationship": by_rel,
        "ipc_sections_covered": ipc_count,
        "bns_sections_covered": bns_count,
        "needs_verification_count": unverified,
        "verified_fraction": (
            round((total - unverified) / total, 3) if total else 0.0
        ),
    }
