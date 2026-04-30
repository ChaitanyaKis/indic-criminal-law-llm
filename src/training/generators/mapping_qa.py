"""Rule-based instruction pairs from the IPC↔BNS and CrPC↔BNSS tables.

For each mapping entry we produce 4-6 question variants and an
authoritative answer assembled from the entry's own fields
(``subject``, ``ipc_title`` / ``crpc_title``, ``bns_title`` / ``bnss_title``,
``relationship``, ``notes``). When ``needs_verification: true`` is set
on the entry, the answer carries a soft caveat directing the reader
to the Gazette for sub-section precision.

The two tables share a near-identical structure, so this module
treats them through a single ``MappingTableSpec`` adapter and emits
two batches of pairs: one for the substantive code, one for the
procedural code.

No LLM calls. Deterministic given the YAMLs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class MappingTableSpec:
    """Adapter so this generator can iterate either mapping table."""

    code_old: str   # "IPC" / "CrPC"
    code_new: str   # "BNS" / "BNSS"
    code_old_full: str   # "Indian Penal Code" etc.
    code_new_full: str   # "Bharatiya Nyaya Sanhita" etc.
    sections_attr: str   # "ipc_section" / "crpc_section"
    new_sections_attr: str   # "bns_sections" / "bnss_sections"
    title_old_attr: str   # "ipc_title" / "crpc_title"
    title_new_attr: str   # "bns_title" / "bnss_title"
    new_in_relationship: str   # "new_in_bns" / "new_in_bnss"
    source_label: str   # "mapping_qa_ipc_bns" / "mapping_qa_crpc_bnss"


_IPC_BNS_SPEC = MappingTableSpec(
    code_old="IPC",
    code_new="BNS",
    code_old_full="Indian Penal Code, 1860",
    code_new_full="Bharatiya Nyaya Sanhita, 2023",
    sections_attr="ipc_section",
    new_sections_attr="bns_sections",
    title_old_attr="ipc_title",
    title_new_attr="bns_title",
    new_in_relationship="new_in_bns",
    source_label="mapping_qa_ipc_bns",
)

_CRPC_BNSS_SPEC = MappingTableSpec(
    code_old="CrPC",
    code_new="BNSS",
    code_old_full="Code of Criminal Procedure, 1973",
    code_new_full="Bharatiya Nagarik Suraksha Sanhita, 2023",
    sections_attr="crpc_section",
    new_sections_attr="bnss_sections",
    title_old_attr="crpc_title",
    title_new_attr="bnss_title",
    new_in_relationship="new_in_bnss",
    source_label="mapping_qa_crpc_bnss",
)


# ---- Answer construction -----------------------------------------------


def _format_new_sections(sections: list[str], code: str) -> str:
    if not sections:
        return ""
    if len(sections) == 1:
        return f"{code} Section {sections[0]}"
    return f"{code} Sections " + ", ".join(sections)


def _verification_caveat() -> str:
    return (
        " Note: this mapping is preliminary at the sub-section level; "
        "verify against the official Gazette text for precise sub-section "
        "indices before relying on it in pleadings."
    )


def _relationship_phrase(rel: str, spec: MappingTableSpec) -> str:
    return {
        "one_to_one": "a one-to-one re-enactment",
        "many_to_one": "consolidated together with several other "
                      f"{spec.code_old} sections into a single {spec.code_new} section",
        "one_to_many": "split across multiple "
                      f"{spec.code_new} sections",
        "removed": "no longer in force — repealed and not re-enacted",
    }.get(rel, "preserved")


def _build_answer_forward(entry: Any, spec: MappingTableSpec) -> str:
    """Answer for 'What is the {NEW} equivalent of {OLD} Section X?'"""
    old_sec = getattr(entry, spec.sections_attr)
    new_secs = getattr(entry, spec.new_sections_attr)
    rel = entry.relationship
    subject = entry.subject

    if rel == "removed":
        ans = (
            f"{spec.code_old} Section {old_sec} ({subject}) has not been re-enacted "
            f"in the {spec.code_new_full}. It is no longer a live offence under the "
            f"new criminal code."
        )
        if entry.notes:
            ans += f" {entry.notes}"
        return ans

    rel_phrase = _relationship_phrase(rel, spec)
    new_block = _format_new_sections(new_secs, spec.code_new)
    ans = (
        f"{spec.code_old} Section {old_sec} ({subject}) maps to {new_block} "
        f"under the {spec.code_new_full}. This is {rel_phrase}."
    )
    if entry.notes:
        # Notes can be long; keep first sentence or first 280 chars.
        first_sentence = entry.notes.split(". ")[0].strip().rstrip(".")
        if first_sentence:
            ans += f" {first_sentence}."
    if entry.needs_verification:
        ans += _verification_caveat()
    return ans


def _build_answer_reverse(entry: Any, spec: MappingTableSpec) -> str:
    """Answer for 'Which {OLD} section corresponds to {NEW} Section X?'"""
    old_sec = getattr(entry, spec.sections_attr)
    new_secs = getattr(entry, spec.new_sections_attr)
    rel = entry.relationship
    subject = entry.subject

    if rel == spec.new_in_relationship:
        new_block = _format_new_sections(new_secs, spec.code_new)
        return (
            f"{new_block} ({subject}) is a new offence introduced by the "
            f"{spec.code_new_full}. It has no direct predecessor in the "
            f"{spec.code_old_full}."
        )

    new_block = _format_new_sections(new_secs, spec.code_new)
    ans = (
        f"{new_block} ({subject}) carries forward {spec.code_old} Section "
        f"{old_sec}, with the relationship being {_relationship_phrase(rel, spec)}."
    )
    if entry.needs_verification:
        ans += _verification_caveat()
    return ans


def _build_answer_replacement(entry: Any, spec: MappingTableSpec) -> str:
    """Answer for 'Has {OLD} Section X been replaced under the new code?'"""
    old_sec = getattr(entry, spec.sections_attr)
    new_secs = getattr(entry, spec.new_sections_attr)
    rel = entry.relationship
    subject = entry.subject

    if rel == "removed":
        return (
            f"Yes — {spec.code_old} Section {old_sec} ({subject}) was repealed "
            f"and has not been re-enacted in the {spec.code_new_full}. Cases "
            f"that previously rested on this section no longer have a direct "
            f"successor provision."
        )

    new_block = _format_new_sections(new_secs, spec.code_new)
    ans = (
        f"Yes. {spec.code_old} Section {old_sec} ({subject}) has been replaced "
        f"by {new_block} under the {spec.code_new_full}. For offences committed "
        f"on or after 1 July 2024 the new section governs; for earlier conduct "
        f"the {spec.code_old} provisions continue to apply."
    )
    if entry.needs_verification:
        ans += _verification_caveat()
    return ans


def _build_answer_what_is_new(entry: Any, spec: MappingTableSpec) -> str:
    """Answer for 'What is {NEW} Section X?'"""
    new_secs = getattr(entry, spec.new_sections_attr)
    rel = entry.relationship
    subject = entry.subject
    old_sec = getattr(entry, spec.sections_attr)

    new_block = _format_new_sections(new_secs, spec.code_new)
    if rel == spec.new_in_relationship:
        ans = (
            f"{new_block} addresses {subject}. It is a new offence introduced "
            f"by the {spec.code_new_full}, with no direct {spec.code_old} predecessor."
        )
    else:
        ans = (
            f"{new_block} addresses {subject}. It carries forward "
            f"{spec.code_old} Section {old_sec} into the {spec.code_new_full}."
        )
    if entry.notes:
        first_sentence = entry.notes.split(". ")[0].strip().rstrip(".")
        if first_sentence:
            ans += f" {first_sentence}."
    if entry.needs_verification:
        ans += _verification_caveat()
    return ans


def _build_answer_old_case(entry: Any, spec: MappingTableSpec) -> str:
    """Answer for 'Reading an old case citing {OLD} X — what's the current section?'"""
    old_sec = getattr(entry, spec.sections_attr)
    new_secs = getattr(entry, spec.new_sections_attr)
    rel = entry.relationship
    subject = entry.subject

    if rel == "removed":
        return (
            f"{spec.code_old} Section {old_sec} ({subject}) has no current successor — "
            f"the provision was repealed and not re-enacted in the "
            f"{spec.code_new_full}. The older case still applies to conduct from "
            f"the period when {spec.code_old} {old_sec} was in force, but no new "
            f"prosecutions can be brought under it."
        )

    new_block = _format_new_sections(new_secs, spec.code_new)
    return (
        f"{spec.code_old} Section {old_sec} ({subject}) corresponds to {new_block} "
        f"in the current {spec.code_new_full}. For citations or pleadings drafted "
        f"after 1 July 2024 against post-effective-date conduct, you would refer "
        f"to the {spec.code_new} provision."
    )


# ---- Question template builders ---------------------------------------


def _questions_for_entry(entry: Any, spec: MappingTableSpec) -> list[tuple[str, str]]:
    """Return list of (instruction, output) pairs for one mapping entry."""
    pairs: list[tuple[str, str]] = []
    old_sec = getattr(entry, spec.sections_attr)
    new_secs = getattr(entry, spec.new_sections_attr)
    rel = entry.relationship
    subject = entry.subject

    # ---- Branch on relationship type --------------------------------

    if rel == spec.new_in_relationship:
        # NEW IN BNS/BNSS — only forward-from-new questions make sense
        new_block = _format_new_sections(new_secs, spec.code_new)
        ans_what_is = _build_answer_what_is_new(entry, spec)
        ans_reverse = _build_answer_reverse(entry, spec)

        if not new_secs:
            return []
        pairs.extend([
            (f"What is {new_block}?", ans_what_is),
            (f"Which {spec.code_old} section corresponds to {new_secs[0]} {spec.code_new}?", ans_reverse),
            (f"Is {spec.code_new} Section {new_secs[0]} a new provision or a re-enactment?",
             ans_what_is),
            (f"Tell me about Section {new_secs[0]} of the {spec.code_new_full}.",
             ans_what_is),
        ])
        return pairs

    if rel == "removed":
        # REMOVED — no new section to anchor reverse questions on
        ans_forward = _build_answer_forward(entry, spec)
        ans_repl = _build_answer_replacement(entry, spec)
        ans_oldcase = _build_answer_old_case(entry, spec)

        pairs.extend([
            (f"What is the {spec.code_new} equivalent of {spec.code_old} Section {old_sec}?",
             ans_forward),
            (f"Has {spec.code_old} {old_sec} been replaced under the new criminal code?",
             ans_repl),
            (f"I'm reading an old case citing {spec.code_old} {old_sec} — what's the current section?",
             ans_oldcase),
            (f"Is {spec.code_old} Section {old_sec} still law in India?", ans_repl),
        ])
        return pairs

    # ---- Standard mapped section (one_to_one, many_to_one, one_to_many)
    ans_forward = _build_answer_forward(entry, spec)
    ans_reverse = _build_answer_reverse(entry, spec)
    ans_repl = _build_answer_replacement(entry, spec)
    ans_what_is_new = _build_answer_what_is_new(entry, spec)
    ans_oldcase = _build_answer_old_case(entry, spec)
    new_block = _format_new_sections(new_secs, spec.code_new)
    primary_new = new_secs[0] if new_secs else ""

    pairs.extend([
        # 1. Forward: old → new
        (f"What is the {spec.code_new} equivalent of {spec.code_old} Section {old_sec}?",
         ans_forward),
        # 2. Reverse: new → old
        (f"Which {spec.code_old} section corresponds to {spec.code_new} Section {primary_new}?",
         ans_reverse),
        # 3. Replacement framing
        (f"Has {spec.code_old} {old_sec} been replaced under the {spec.code_new}?",
         ans_repl),
        # 4. Subject-led (only if subject is non-trivial)
        *([
            (f"Under the {spec.code_new_full}, which section deals with {subject.lower()}?",
             ans_reverse)
        ] if subject and len(subject) > 5 else []),
        # 5. What is the new section
        (f"What is Section {primary_new} of the {spec.code_new}?",
         ans_what_is_new),
        # 6. Old case → current section
        (f"I'm reading an old judgment citing {spec.code_old} {old_sec} — what's the current section?",
         ans_oldcase),
    ])
    return pairs


# ---- Public generator -------------------------------------------------


def generate_pairs() -> list[dict[str, Any]]:
    """Generate Alpaca-format pairs from both mapping tables."""
    out: list[dict[str, Any]] = []

    # IPC ↔ BNS
    from src.mapping.ipc_bns import load_mapping as load_ipc_bns
    table = load_ipc_bns()
    for entry in table.entries:
        for inst, output in _questions_for_entry(entry, _IPC_BNS_SPEC):
            section_id = entry.ipc_section or (entry.bns_sections[0] if entry.bns_sections else "?")
            out.append({
                "instruction": inst,
                "input": "",
                "output": output,
                "_metadata": {
                    "source": "mapping_qa",
                    "source_id": f"ipc_bns__{section_id}",
                    "generated_by": "rule_based",
                    "validated": False,
                },
            })

    # CrPC ↔ BNSS
    from src.mapping.crpc_bnss import load_mapping as load_crpc_bnss
    table2 = load_crpc_bnss()
    for entry in table2.entries:
        for inst, output in _questions_for_entry(entry, _CRPC_BNSS_SPEC):
            section_id = entry.crpc_section or (entry.bnss_sections[0] if entry.bnss_sections else "?")
            out.append({
                "instruction": inst,
                "input": "",
                "output": output,
                "_metadata": {
                    "source": "mapping_qa",
                    "source_id": f"crpc_bnss__{section_id}",
                    "generated_by": "rule_based",
                    "validated": False,
                },
            })

    return out
