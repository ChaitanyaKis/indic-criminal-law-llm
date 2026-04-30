"""Section-interpretation pairs for the top-cited statute sections.

For each section in the corpus inventory's top-50 IPC list (and the
inventory's top-30 CrPC list), generate four template-driven Q&As
explaining the section. Answers are rule-based and assembled from the
mapping table (subject, titles, BNS/BNSS analogue) — corpus
excerpts are not pulled in this v0.1 generator. Adding excerpts is a
v0.2 follow-up.

This complements ``mapping_qa.py``: that generator focuses on
section-mapping questions, this generator focuses on substantive
interpretation questions.

Source of priorities: ``data/processed/corpus_inventory.json``. If the
inventory is absent, falls back to a hard-coded canonical-section
list so the generator still runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_INVENTORY_PATH = _PROJECT_ROOT / "data" / "processed" / "corpus_inventory.json"


# Fallback if no inventory is available — covers the most-cited
# sections we know about from prior snapshots.
_FALLBACK_TOP_IPC = [
    "302", "34", "120B", "420", "149", "307", "323", "498A", "471",
    "506", "468", "201", "406", "148", "376", "467", "147", "504",
    "306", "324", "300", "409", "304B", "304", "341", "364", "363",
    "326", "342", "193", "465", "109", "354", "325", "366", "377",
    "379", "427", "114", "452", "153A", "107", "397", "392", "395",
    "304A", "500", "477A", "509", "384",
]
_FALLBACK_TOP_CRPC = [
    "482", "313", "161", "173", "164", "200", "439", "156(3)",
    "173(2)", "154", "438", "162", "319", "173(8)", "197", "202",
    "167", "167(2)", "190", "227", "378", "320", "125", "401",
    "311", "207", "397", "41", "239", "209",
]


def _load_top_sections() -> tuple[list[str], list[str]]:
    """Return (top_ipc, top_crpc). Inventory if present, else fallback."""
    if _INVENTORY_PATH.exists():
        try:
            inv = json.loads(_INVENTORY_PATH.read_text(encoding="utf-8"))
            top_ipc = [r["section"] for r in inv["statutes"]["top_ipc"]]
            top_crpc = [r["section"] for r in inv["statutes"]["top_crpc"]]
            return top_ipc, top_crpc
        except Exception:
            pass
    return list(_FALLBACK_TOP_IPC), list(_FALLBACK_TOP_CRPC)


# ---- Answer templates --------------------------------------------------


def _ipc_answer(section: str, mapping_entry: Any) -> tuple[str, str, str, str]:
    """Return (criminalize, explain, elements, deals_with) answers."""
    if mapping_entry is None:
        # No mapping data — produce a generic placeholder. We skip
        # generating pairs if mapping data is absent (caller filters).
        raise RuntimeError(f"No mapping data for IPC {section}")

    subject = mapping_entry.subject or "an offence under the Indian Penal Code"
    ipc_title = mapping_entry.ipc_title or subject
    bns_secs = mapping_entry.bns_sections or []
    rel = mapping_entry.relationship

    # Suffix that pairs to BNS where applicable
    if rel == "removed":
        bns_suffix = (
            " Note: This section has not been re-enacted in the Bharatiya "
            "Nyaya Sanhita, 2023; for post-1-July-2024 conduct it is no "
            "longer a live offence."
        )
    elif bns_secs:
        if len(bns_secs) == 1:
            bns_suffix = (
                f" Under the new Bharatiya Nyaya Sanhita, 2023, this "
                f"corresponds to BNS Section {bns_secs[0]}."
            )
        else:
            bns_suffix = (
                f" Under the new Bharatiya Nyaya Sanhita, 2023, this "
                f"corresponds to BNS Sections {', '.join(bns_secs)}."
            )
    else:
        bns_suffix = ""

    notes_clause = ""
    if mapping_entry.notes:
        first = mapping_entry.notes.split(". ")[0].strip().rstrip(".")
        if first:
            notes_clause = f" {first}."

    criminalize = (
        f"Section {section} of the Indian Penal Code, 1860 deals with "
        f"{subject.lower()}. The provision is titled \"{ipc_title}\".{notes_clause}"
        f"{bns_suffix}"
    )

    explain = (
        f"Section {section} IPC addresses {subject.lower()}. The full "
        f"section heading is \"{ipc_title}\".{notes_clause}{bns_suffix}"
    )

    # Elements answer is more cautious — the mapping doesn't carry full
    # statutory text, so we frame it as "consult the bare act" rather
    # than fabricating specific elements.
    elements = (
        f"The elements of an offence under Section {section} IPC ({subject}) "
        f"are set out in the bare act and elaborated in case law. The section "
        f"is titled \"{ipc_title}\". For an authoritative element-by-element "
        f"breakdown, consult the bare act and the leading Supreme Court "
        f"judgments interpreting this section.{bns_suffix}"
    )

    deals_with = (
        f"Section {section} of the Indian Penal Code is concerned with "
        f"{subject.lower()}.{notes_clause}{bns_suffix}"
    )

    return criminalize, explain, elements, deals_with


def _crpc_answer(section: str, mapping_entry: Any) -> tuple[str, str, str]:
    """Return (governs, explain, deals_with) answers for procedural sections."""
    if mapping_entry is None:
        raise RuntimeError(f"No mapping data for CrPC {section}")

    subject = mapping_entry.subject or "a procedural matter"
    crpc_title = mapping_entry.crpc_title or subject
    bnss_secs = mapping_entry.bnss_sections or []
    rel = mapping_entry.relationship

    if rel == "removed":
        bnss_suffix = (
            " Note: this provision has not been carried forward into the "
            "Bharatiya Nagarik Suraksha Sanhita, 2023."
        )
    elif bnss_secs:
        if len(bnss_secs) == 1:
            bnss_suffix = (
                f" Under the new Bharatiya Nagarik Suraksha Sanhita, 2023, "
                f"this corresponds to BNSS Section {bnss_secs[0]}."
            )
        else:
            bnss_suffix = (
                f" Under the new Bharatiya Nagarik Suraksha Sanhita, 2023, "
                f"this corresponds to BNSS Sections {', '.join(bnss_secs)}."
            )
    else:
        bnss_suffix = ""

    notes_clause = ""
    if mapping_entry.notes:
        first = mapping_entry.notes.split(". ")[0].strip().rstrip(".")
        if first:
            notes_clause = f" {first}."

    governs = (
        f"Section {section} of the Code of Criminal Procedure, 1973 governs "
        f"{subject.lower()}. The provision is titled \"{crpc_title}\".{notes_clause}"
        f"{bnss_suffix}"
    )

    explain = (
        f"Section {section} CrPC addresses {subject.lower()}. The section "
        f"heading is \"{crpc_title}\".{notes_clause}{bnss_suffix}"
    )

    deals_with = (
        f"Section {section} of the Code of Criminal Procedure deals with "
        f"{subject.lower()}.{notes_clause}{bnss_suffix}"
    )

    return governs, explain, deals_with


# ---- Public generator -------------------------------------------------


def generate_pairs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    top_ipc, top_crpc = _load_top_sections()

    from src.mapping.ipc_bns import load_mapping as load_ipc_bns
    from src.mapping.ipc_bns import map_ipc_to_bns
    ipc_table = load_ipc_bns()  # ensures cache is warm

    for sec in top_ipc:
        m = map_ipc_to_bns(sec)
        if m is None:
            # Skip sections we don't have in the mapping table — generating
            # interpretation without authoritative subject would be guessing.
            continue
        try:
            criminalize, explain, elements, deals_with = _ipc_answer(sec, m)
        except RuntimeError:
            continue
        for inst, output in [
            (f"What does Section {sec} of the IPC criminalize?", criminalize),
            (f"Explain Section {sec} IPC.", explain),
            (f"What are the elements of an offence under Section {sec} IPC?",
             elements),
            (f"Section {sec} of the Indian Penal Code deals with what?",
             deals_with),
        ]:
            out.append({
                "instruction": inst,
                "input": "",
                "output": output,
                "_metadata": {
                    "source": "section_interpretation",
                    "source_id": f"ipc_{sec}",
                    "generated_by": "rule_based",
                    "validated": False,
                },
            })

    from src.mapping.crpc_bnss import load_mapping as load_crpc_bnss
    from src.mapping.crpc_bnss import map_crpc_to_bnss
    crpc_table = load_crpc_bnss()

    for sec in top_crpc:
        m = map_crpc_to_bnss(sec)
        if m is None:
            continue
        try:
            governs, explain, deals_with = _crpc_answer(sec, m)
        except RuntimeError:
            continue
        for inst, output in [
            (f"What does Section {sec} of the CrPC govern?", governs),
            (f"Explain Section {sec} CrPC.", explain),
            (f"Section {sec} of the Code of Criminal Procedure deals with what?",
             deals_with),
        ]:
            out.append({
                "instruction": inst,
                "input": "",
                "output": output,
                "_metadata": {
                    "source": "section_interpretation",
                    "source_id": f"crpc_{sec}",
                    "generated_by": "rule_based",
                    "validated": False,
                },
            })

    return out
