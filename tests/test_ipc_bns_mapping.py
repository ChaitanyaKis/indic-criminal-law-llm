"""Tests for the IPC ↔ BNS section-mapping module.

Runs against the real seed YAML (``data/mappings/ipc_bns_mapping.yaml``) —
not a fixture — because the YAML *is* the data under test. When the YAML
changes, these tests are the first signal that a change broke an
established mapping or left the file in an invalid schema.
"""

from __future__ import annotations

from src.mapping.ipc_bns import (
    MappingTable,
    SectionMapping,
    _normalize_section,
    load_mapping,
    map_bns_to_ipc,
    map_ipc_to_bns,
    search_by_subject,
    stats,
)


# ---- Load / schema sanity ----------------------------------------------


def test_load_returns_mapping_table():
    t = load_mapping()
    assert isinstance(t, MappingTable)
    assert t.version
    assert t.source
    assert t.last_verified
    assert len(t.entries) >= 50, f"seed target is ~50, got {len(t.entries)}"


def test_every_entry_has_valid_relationship():
    valid = {"one_to_one", "one_to_many", "many_to_one", "removed", "new_in_bns"}
    for e in load_mapping().entries:
        assert e.relationship in valid


def test_removed_entries_have_empty_bns():
    for e in load_mapping().entries:
        if e.relationship == "removed":
            assert e.bns_sections == []


def test_new_in_bns_entries_have_null_ipc():
    for e in load_mapping().entries:
        if e.relationship == "new_in_bns":
            assert e.ipc_section is None
            assert e.bns_sections, "new_in_bns entries must name a BNS section"


def test_non_new_entries_have_non_null_ipc():
    for e in load_mapping().entries:
        if e.relationship != "new_in_bns":
            assert e.ipc_section is not None


# ---- Core lookup canon ('must work — these are headline mappings') ------


def test_murder_302_to_bns_103():
    m = map_ipc_to_bns("302")
    assert m is not None
    assert "103(1)" in m.bns_sections
    assert m.subject == "Murder"


def test_498a_maps_to_bns_85_and_86():
    # The flagship one-to-many split cited in every comparative table.
    m = map_ipc_to_bns("498A")
    assert m is not None
    assert m.relationship == "one_to_many"
    assert set(m.bns_sections) == {"85", "86"}


def test_rape_375_to_bns_63():
    m = map_ipc_to_bns("375")
    assert m is not None
    assert "63" in m.bns_sections


def test_rape_punishment_376_to_bns_64():
    m = map_ipc_to_bns("376")
    assert m is not None
    assert "64" in m.bns_sections


def test_cheating_420_to_bns_318():
    m = map_ipc_to_bns("420")
    assert m is not None
    # Sub-section precision (318(4) vs 318) is flagged needs_verification;
    # only assert the parent-section identity, which is well-established.
    assert any(s.startswith("318") for s in m.bns_sections)


def test_dowry_death_304b_to_bns_80():
    m = map_ipc_to_bns("304B")
    assert m is not None
    assert "80" in m.bns_sections


# ---- Normalization: "498A" / "498-A" / "498 A" / "498  A" all resolve ---


def test_normalize_section_variants_equivalent():
    for variant in ("498A", "498-A", "498 A", "498  a", " 498a "):
        assert _normalize_section(variant) == "498A"


def test_lookup_accepts_all_section_spellings():
    canonical = map_ipc_to_bns("498A")
    assert canonical is not None
    for variant in ("498-A", "498 A", "498  a", "498a"):
        m = map_ipc_to_bns(variant)
        assert m is canonical, f"spelling {variant!r} did not resolve to same entry"


# ---- Sub-section fallback: "304(2)" falls back to parent "304" ----------


def test_subsection_falls_back_to_parent():
    parent = map_ipc_to_bns("304")
    assert parent is not None
    fallback = map_ipc_to_bns("304(2)")
    assert fallback is parent


def test_exact_subsection_beats_parent_when_present():
    # IPC 304A has its own entry; lookup of "304A" must not fall back to "304".
    a = map_ipc_to_bns("304A")
    assert a is not None
    assert a.ipc_section == "304A"
    assert a is not map_ipc_to_bns("304")


# ---- Reverse lookup BNS → IPC, including rollup ------------------------


def test_reverse_lookup_498a_from_bns_85():
    hits = map_bns_to_ipc("85")
    assert any(e.ipc_section == "498A" for e in hits)


def test_reverse_lookup_498a_from_bns_86():
    hits = map_bns_to_ipc("86")
    assert any(e.ipc_section == "498A" for e in hits)


def test_reverse_bns_316_rolls_up_to_405_406_409():
    # CBT consolidation: BNS 316 subsumes IPC 405, 406, 409.
    hits = map_bns_to_ipc("316")
    ipc_sections = {e.ipc_section for e in hits}
    assert {"405", "406", "409"}.issubset(ipc_sections)


def test_map_bns_to_ipc_rollup_mode():
    # Explicit rollup (default) — CBT consolidation covers 3+ entries
    # since IPC 405/406/409 all land on sub-sections of BNS 316.
    hits = map_bns_to_ipc("316", return_mode="rollup")
    assert len(hits) >= 3
    assert {"405", "406", "409"}.issubset({e.ipc_section for e in hits})


def test_map_bns_to_ipc_strict_mode():
    # Strict mode refuses parent-section rollup: no entry in the seed
    # YAML carries bare "316" as a bns_sections value, so strict returns [].
    hits = map_bns_to_ipc("316", return_mode="strict")
    assert hits == []
    # Sanity: strict still works when the exact key IS indexed.
    strict_85 = map_bns_to_ipc("85", return_mode="strict")
    assert any(e.ipc_section == "498A" for e in strict_85)


def test_reverse_lookup_new_in_bns_111():
    hits = map_bns_to_ipc("111")
    assert len(hits) == 1
    assert hits[0].ipc_section is None
    assert hits[0].relationship == "new_in_bns"
    assert hits[0].subject.lower() == "organised crime"


def test_unknown_section_returns_none_or_empty():
    assert map_ipc_to_bns("9999") is None
    assert map_bns_to_ipc("9999") == []


# ---- Round-trip: IPC 302 → BNS 103(1) → IPC set contains 302 ------------


def test_round_trip_302():
    forward = map_ipc_to_bns("302")
    assert forward is not None
    for bns_sec in forward.bns_sections:
        reverse_hits = map_bns_to_ipc(bns_sec)
        assert any(e.ipc_section == "302" for e in reverse_hits), (
            f"round-trip failed for 302 via BNS {bns_sec}"
        )


def test_round_trip_498a_covers_both_splits():
    forward = map_ipc_to_bns("498A")
    assert forward is not None
    for bns_sec in forward.bns_sections:
        reverse_hits = map_bns_to_ipc(bns_sec)
        assert any(e.ipc_section == "498A" for e in reverse_hits)


def test_round_trip_420():
    forward = map_ipc_to_bns("420")
    assert forward is not None
    for bns_sec in forward.bns_sections:
        reverse_hits = map_bns_to_ipc(bns_sec)
        assert any(e.ipc_section == "420" for e in reverse_hits)


# ---- Subject search ----------------------------------------------------


def test_subject_search_murder_returns_multiple_entries():
    hits = search_by_subject("murder")
    ipc_sections = {e.ipc_section for e in hits}
    # 302 (murder), 300 (murder def), 303 (by life-convict), 304 (not amounting)
    # and 307 (attempt to murder) all carry "Murder" in their subject.
    assert {"302", "300", "304", "307"}.issubset(ipc_sections)


def test_subject_search_case_insensitive():
    lo = {e.ipc_section for e in search_by_subject("rape")}
    hi = {e.ipc_section for e in search_by_subject("RAPE")}
    assert lo == hi
    assert "375" in lo and "376" in lo


def test_subject_search_empty_returns_empty():
    assert search_by_subject("") == []
    assert search_by_subject("   ") == []


def test_subject_search_no_match():
    assert search_by_subject("xyzzy-no-such-subject") == []


# ---- Relationship types work as claimed ---------------------------------


def test_one_to_many_relationship_example():
    m = map_ipc_to_bns("498A")
    assert m is not None
    assert m.relationship == "one_to_many"
    assert len(m.bns_sections) >= 2


def test_many_to_one_relationship_example():
    # IPC 380 is labelled many_to_one because BNS 305 consolidates
    # IPC 380/381/382 — even though only 380 is in our seed.
    m = map_ipc_to_bns("380")
    assert m is not None
    assert m.relationship == "many_to_one"


def test_removed_relationship_example():
    m = map_ipc_to_bns("309")
    assert m is not None
    assert m.relationship == "removed"
    assert m.bns_sections == []


def test_new_in_bns_has_organised_crime_and_terrorism():
    new_entries = [e for e in load_mapping().entries if e.relationship == "new_in_bns"]
    subjects = {e.subject.lower() for e in new_entries}
    assert "organised crime" in subjects
    assert "terrorist act" in subjects


# ---- Stats --------------------------------------------------------------


def test_stats_returns_sane_numbers():
    s = stats()
    assert s["total_entries"] >= 50
    assert s["by_relationship"]["one_to_one"] > 0
    assert s["by_relationship"]["removed"] >= 1
    assert s["by_relationship"]["new_in_bns"] >= 2
    assert 0.0 <= s["verified_fraction"] <= 1.0
    assert s["needs_verification_count"] >= 0
    assert s["needs_verification_count"] <= s["total_entries"]
    assert s["ipc_sections_covered"] + s["by_relationship"]["new_in_bns"] == s["total_entries"]


def test_stats_sum_of_relationships_equals_total():
    s = stats()
    assert sum(s["by_relationship"].values()) == s["total_entries"]
