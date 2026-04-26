"""Tests for the CrPC ↔ BNSS section mapping module.

Mirrors the structure of ``test_ipc_bns_mapping.py`` with three
additional integration tests specific to procedural-code concerns:

- ``test_482_does_not_alias_to_482`` — CrPC 482 (HC inherent powers)
  must NOT map to BNSS 482; BNSS 482 is anticipatory bail (← CrPC 438).
  Number-collision guard.
- ``test_normalize_section_variants`` — procedural citations have
  many spellings ("S. 167(2)", "Sec. 167(2)", "Section 167 (2)",
  "167(2)"); the normalizer must collapse them all to one key.
- ``test_relationship_consistency_invariant`` — schema invariant: any
  BNSS section targeted by 2+ CrPC entries must have all those entries
  flagged ``many_to_one``. Catches the IPC 113/114 asymmetry kind of
  bug at table-level rather than entry-level.
"""

from __future__ import annotations

from src.mapping.crpc_bnss import (
    SectionMapping,
    _normalize_section,
    load_mapping,
    map_bnss_to_crpc,
    map_crpc_to_bnss,
    search_by_subject,
    stats,
)


def test_load_mapping_succeeds():
    t = load_mapping()
    assert t.entries, "mapping has no entries"
    # Every entry must have a coherent shape — sanity check the dataclass
    for e in t.entries:
        assert isinstance(e, SectionMapping)
        assert e.relationship in {
            "one_to_one", "one_to_many", "many_to_one",
            "removed", "new_in_bnss",
        }


def test_map_crpc_to_bnss_known_section():
    # CrPC 167(2) → BNSS 187(3), the default-bail mapping.
    m = map_crpc_to_bnss("167(2)")
    assert m is not None
    assert m.bnss_sections == ["187(3)"]
    assert "default bail" in m.subject.lower() or "default" in m.subject.lower()


def test_default_bail_mapping():
    # Same target, asserted with full doctrine notes presence so future
    # edits to the entry don't accidentally drop the doctrinal context.
    m = map_crpc_to_bnss("167(2)")
    assert m is not None
    assert m.bnss_sections == ["187(3)"]
    assert m.notes is not None
    assert "default" in m.notes.lower() or "60" in m.notes or "90" in m.notes


def test_anticipatory_bail_mapping():
    # CrPC 438 (anticipatory bail) → BNSS 482. Note: BNSS 482 is the
    # SECTION NUMBER for anticipatory bail in BNSS — unrelated to
    # CrPC 482 (inherent powers). The 482-collision test below is the
    # explicit guard.
    m = map_crpc_to_bnss("438")
    assert m is not None
    assert m.bnss_sections == ["482"]
    assert "anticipatory" in m.subject.lower() or "anticipatory" in (m.notes or "").lower()


def test_inherent_powers_mapping():
    # CrPC 482 (HC inherent powers) → BNSS 528. NOT 482.
    m = map_crpc_to_bnss("482")
    assert m is not None
    assert m.bnss_sections == ["528"]
    assert "inherent" in m.subject.lower()


def test_482_does_not_alias_to_482():
    """Number-collision guard. CrPC 482 (inherent powers) must NOT map
    to BNSS 482 (anticipatory bail). Reverse-direction: BNSS 482 must
    return CrPC 438 (anticipatory bail), not CrPC 482.

    Catches autocomplete or copy-paste mistakes that would silently
    swap the two unrelated sections.
    """
    # Forward: CrPC 482 must NOT carry BNSS 482 anywhere in its targets
    m_crpc = map_crpc_to_bnss("482")
    assert m_crpc is not None
    assert "482" not in m_crpc.bnss_sections, (
        f"CrPC 482 must not map to BNSS 482 (number collision); "
        f"got bnss_sections={m_crpc.bnss_sections}"
    )

    # Reverse: BNSS 482 must return CrPC 438 (anticipatory bail), NOT
    # CrPC 482. Both rollup and strict modes.
    rev = map_bnss_to_crpc("482")
    assert rev, "BNSS 482 reverse lookup returned no entries"
    crpc_sections = {e.crpc_section for e in rev}
    assert "438" in crpc_sections, (
        f"BNSS 482 must include CrPC 438 (anticipatory bail) in "
        f"reverse lookup; got {crpc_sections}"
    )
    assert "482" not in crpc_sections, (
        f"BNSS 482 must NOT include CrPC 482 in reverse lookup "
        f"(that would be the number-collision bug); got {crpc_sections}"
    )


def test_map_bnss_to_crpc_rollup_and_strict_modes():
    # Strict: lookup of "187(3)" returns the CrPC 167(2) entry.
    strict = map_bnss_to_crpc("187(3)", return_mode="strict")
    assert any(e.crpc_section == "167(2)" for e in strict)

    # Rollup: lookup of "187" (parent) returns the same entry via the
    # parent-rollup index. CrPC 167 (general remand) and CrPC 167(2)
    # (default bail sub-section) are two separate entries; both should
    # come back when querying the parent.
    rollup = map_bnss_to_crpc("187", return_mode="rollup")
    crpc_sections = {e.crpc_section for e in rollup}
    assert {"167", "167(2)"}.issubset(crpc_sections), (
        f"BNSS 187 rollup should include CrPC 167 + 167(2); got {crpc_sections}"
    )


def test_normalize_section_variants():
    # Procedural-code citations come in many spellings. The normalizer
    # must collapse them all to one key so map_crpc_to_bnss is robust
    # to the spelling variation in real corpora.
    expected = _normalize_section("167(2)")
    for variant in (
        "167(2)",
        "167 (2)",
        "S. 167(2)",
        "Sec. 167(2)",
        "Section 167(2)",
        "Section 167 (2)",
        "section 167(2)",
        "  S.  167  (2)  ",
    ):
        assert _normalize_section(variant) == expected, (
            f"variant {variant!r} normalized to "
            f"{_normalize_section(variant)!r}, expected {expected!r}"
        )

    # And the forward-lookup path must accept all variants too.
    for variant in ("167(2)", "S. 167(2)", "Section 167 (2)"):
        m = map_crpc_to_bnss(variant)
        assert m is not None, f"forward lookup failed for {variant!r}"
        assert m.bnss_sections == ["187(3)"]


def test_round_trip_arrest_chapter():
    # CrPC 41 (arrest without warrant) → BNSS 35.
    # Round-trip: map_bnss_to_crpc("35") in strict mode must include CrPC 41.
    m41 = map_crpc_to_bnss("41")
    assert m41 is not None
    assert m41.bnss_sections == ["35"]

    rev = map_bnss_to_crpc("35", return_mode="strict")
    assert any(e.crpc_section == "41" for e in rev), (
        f"reverse strict lookup of BNSS 35 must include CrPC 41; "
        f"got {[e.crpc_section for e in rev]}"
    )


def test_stats_returns_sane_numbers():
    s = stats()
    assert s["total_entries"] > 0
    # Sum across relationships must equal total
    assert sum(s["by_relationship"].values()) == s["total_entries"]
    # Coverage counts must be non-negative
    assert s["crpc_sections_covered"] >= 0
    assert s["bnss_sections_covered"] >= 0
    # verified_fraction is between 0 and 1
    assert 0.0 <= s["verified_fraction"] <= 1.0


def test_relationship_consistency_invariant():
    """Schema invariant: if multiple CrPC sections map to the same BNSS
    section, every one of them must carry ``relationship == "many_to_one"``.

    Catches the IPC 113/114-style asymmetry bug at the entire-table
    level. If a future edit adds a new CrPC entry that maps to an
    already-targeted BNSS section without updating the existing entry's
    relationship, this test fails.
    """
    t = load_mapping()
    # Build a count of how many entries target each (normalized) BNSS section
    bnss_targets: dict[str, list[SectionMapping]] = {}
    for e in t.entries:
        for s in e.bnss_sections:
            bnss_targets.setdefault(_normalize_section(s), []).append(e)

    for bnss_sec, entries in bnss_targets.items():
        if len(entries) <= 1:
            continue
        # Multiple entries target this BNSS section — all must be many_to_one.
        violators = [
            e for e in entries
            if e.relationship not in ("many_to_one", "new_in_bnss")
        ]
        assert not violators, (
            f"BNSS {bnss_sec} is targeted by {len(entries)} CrPC entries "
            f"but the following carry the wrong relationship label "
            f"(should be many_to_one): "
            f"{[(e.crpc_section, e.relationship) for e in violators]}"
        )


def test_subject_search_basic():
    # "bail" should turn up the bail-chapter cluster.
    hits = search_by_subject("bail")
    assert hits, "subject search for 'bail' returned no hits"
    crpc_sections = {e.crpc_section for e in hits}
    # At least anticipatory bail and default bail should appear
    assert "438" in crpc_sections
    assert "167(2)" in crpc_sections
