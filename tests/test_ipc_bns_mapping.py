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
    # Kidnapping consolidation: IPC 359, 360, 361, 363 all collapse
    # into BNS 137, so each of those IPC entries is many_to_one.
    # (The previous example — IPC 380 → BNS 305 — was wrong; 305
    # only absorbs 380, not 381/382. See 380 regression test.)
    for ipc in ("359", "360", "361", "363"):
        m = map_ipc_to_bns(ipc)
        assert m is not None
        assert m.relationship == "many_to_one", f"{ipc} rel={m.relationship}"


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


# ---- Batch 2 spot-check round-trips (5 new entries) --------------------


def test_batch2_extortion_383_round_trip():
    # IPC 383 (extortion def) → BNS 308(1); and subject search "Extortion"
    # should return at least 383, 384, 385.
    m = map_ipc_to_bns("383")
    assert m is not None
    assert "308(1)" in m.bns_sections
    reverse = map_bns_to_ipc("308(1)")
    assert any(e.ipc_section == "383" for e in reverse)
    subject_hits = {e.ipc_section for e in search_by_subject("extortion")}
    assert {"383", "384", "385"}.issubset(subject_hits)


def test_batch2_cheating_personation_416_maps_to_bns_319():
    m = map_ipc_to_bns("416")
    assert m is not None
    assert any(s.startswith("319") for s in m.bns_sections), m.bns_sections
    # Reverse lookup — rollup mode pulls the 319 sub-section entries
    reverse = map_bns_to_ipc("319")
    assert any(e.ipc_section == "416" for e in reverse)


def test_batch2_counterfeit_currency_489a_round_trip():
    # Well-established mapping: IPC 489A → BNS 178 (no verification flag)
    m = map_ipc_to_bns("489A")
    assert m is not None
    assert m.bns_sections == ["178"]
    assert m.needs_verification is False
    reverse = map_bns_to_ipc("178")
    assert any(e.ipc_section == "489A" for e in reverse)


def test_batch2_trafficking_370_subject_search_and_round_trip():
    # Subject search on the common stem "traffick" matches both
    # "Trafficking of person" (IPC 370) and "Exploitation of trafficked
    # person" (IPC 370A). "trafficking" alone would miss 370A's past tense.
    hits = {e.ipc_section for e in search_by_subject("traffick")}
    assert {"370", "370A"}.issubset(hits)
    # Round-trip 370 → BNS 143 → IPC 370 present in reverse
    m = map_ipc_to_bns("370")
    assert m is not None
    assert "143" in m.bns_sections
    reverse_ids = {e.ipc_section for e in map_bns_to_ipc("143")}
    assert "370" in reverse_ids


def test_ipc_380_maps_to_bns_305_not_others():
    # Regression: the original IPC 380 entry claimed BNS 305 consolidates
    # 380/381/382. Batch 2 showed 381→306 and 382→307 are distinct. This
    # test locks in the corrected mapping and guards against drift.
    m380 = map_ipc_to_bns("380")
    assert m380 is not None
    assert m380.bns_sections == ["305"]
    assert "306" not in m380.bns_sections
    assert "307" not in m380.bns_sections
    assert m380.relationship == "one_to_one"

    # Reverse: rollup lookup of BNS 305 must NOT pick up IPC 381 or 382.
    reverse_305 = {e.ipc_section for e in map_bns_to_ipc("305")}
    assert "380" in reverse_305
    assert "381" not in reverse_305
    assert "382" not in reverse_305

    # Sanity: 381 and 382 have their own BNS targets.
    assert map_ipc_to_bns("381").bns_sections == ["306"]
    assert map_ipc_to_bns("382").bns_sections == ["307"]


def test_ipc_34_round_trip():
    # Batch 3: IPC 34 (common intention) → BNS 3(5); ubiquitous joint-
    # liability mapping. Must round-trip cleanly.
    m = map_ipc_to_bns("34")
    assert m is not None
    assert m.bns_sections == ["3(5)"]
    assert m.relationship == "one_to_one"
    # Rollup lookup on parent BNS 3 must include IPC 34 (via 3(5) → 3).
    rollup_ids = {e.ipc_section for e in map_bns_to_ipc("3")}
    assert "34" in rollup_ids
    # Direct lookup on 3(5) must include IPC 34 too.
    direct_ids = {e.ipc_section for e in map_bns_to_ipc("3(5)")}
    assert "34" in direct_ids


def test_ipc_161_removed_in_1988():
    # Batch 3: IPC 161 was repealed in 1988 by the Prevention of
    # Corruption Act, not rolled into BNS. Lock in the removed status.
    m = map_ipc_to_bns("161")
    assert m is not None
    assert m.relationship == "removed"
    assert m.bns_sections == []
    assert m.notes is not None
    assert "Prevention of Corruption Act" in m.notes


def test_batch2_kidnap_consolidation_rolls_up_to_bns_137():
    # BNS 137 consolidates IPC 359, 360, 361, 363 (kidnapping family).
    # Reverse lookup should return all four.
    hits = {e.ipc_section for e in map_bns_to_ipc("137")}
    assert {"359", "360", "361", "363"}.issubset(hits), hits
    # Relationship for these is many_to_one
    for ipc in ("359", "360", "361", "363"):
        m = map_ipc_to_bns(ipc)
        assert m is not None
        assert m.relationship == "many_to_one", f"{ipc} rel={m.relationship}"


# ---- Batch 4: abetment chapter + inventory-driven additions -----------


def test_ipc_107_109_round_trip():
    # IPC 107 (abetment def) → BNS 45; IPC 109 (general punishment) → BNS 49.
    m107 = map_ipc_to_bns("107")
    assert m107 is not None
    assert m107.bns_sections == ["45"]
    assert m107.relationship == "one_to_one"

    m109 = map_ipc_to_bns("109")
    assert m109 is not None
    assert m109.bns_sections == ["49"]
    assert m109.relationship == "one_to_one"

    # Reverse direction must include both
    assert any(e.ipc_section == "107" for e in map_bns_to_ipc("45"))
    assert any(e.ipc_section == "109" for e in map_bns_to_ipc("49"))


def test_abetment_chapter_completeness():
    # All six abetment sections we mapped in Batch 4 must be present and
    # carry a non-empty BNS target. Guards against partial-batch
    # regressions where a chapter is half-mapped.
    abetment_ipc = ("107", "108", "109", "110", "113", "114")
    for ipc in abetment_ipc:
        m = map_ipc_to_bns(ipc)
        assert m is not None, f"IPC {ipc} (abetment) is missing from the mapping"
        assert m.bns_sections, f"IPC {ipc} carries an empty BNS target"

    # Schema-consistency: any abetment IPC section that lands on a BNS
    # section also targeted by another mapped IPC section must be
    # many_to_one. This catches the 113/114 case where both consolidate
    # into BNS 53 — both must carry the consolidation marker.
    bns_target_counts: dict[str, int] = {}
    for ipc in abetment_ipc:
        m = map_ipc_to_bns(ipc)
        for s in m.bns_sections:
            bns_target_counts[s] = bns_target_counts.get(s, 0) + 1

    for ipc in abetment_ipc:
        m = map_ipc_to_bns(ipc)
        shared = any(bns_target_counts[s] > 1 for s in m.bns_sections)
        if shared:
            assert m.relationship == "many_to_one", (
                f"IPC {ipc} shares a BNS target with another abetment "
                f"section but is labelled {m.relationship!r}, not many_to_one"
            )


def test_ipc_148_completes_rioting_block():
    # The public-order-with-weapons cluster spans two BNS sections:
    #   IPC 144 (joining unlawful assembly armed) → BNS 189(*) (unlawful-assembly family)
    #   IPC 146/147/148 (rioting def / punishment / armed)  → BNS 191(*) (rioting family)
    # Test the literal claim — each section maps within its BNS family —
    # rather than a homogenised "all in 191" framing that would be wrong
    # for IPC 144 (which lives in BNS 189).
    m144 = map_ipc_to_bns("144")
    assert m144 is not None
    assert any(s.startswith("189") for s in m144.bns_sections), m144.bns_sections

    for ipc in ("146", "147", "148"):
        m = map_ipc_to_bns(ipc)
        assert m is not None, f"IPC {ipc} missing from the rioting block"
        assert any(s.startswith("191") for s in m.bns_sections), (
            f"IPC {ipc} → {m.bns_sections}, expected 191(...)"
        )
