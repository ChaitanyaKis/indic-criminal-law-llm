"""BNS-transition reasoning pairs grounded in Findings #1-#9.

Each finding in ``docs/bns_transition_findings.md`` describes a real
substantive shift (or absence of one) the project discovered while
building the mapping tables. This generator emits Q&A pairs whose
answers are derived directly from those findings — never speculating
beyond what the doc records.

Findings #10 (Gemini thinking-tokens) and #11 (citation verifier
hallucination signal) are project-tooling observations, not legal
findings, and are excluded here.

The instruction templates within each finding are designed for variety
in how a practitioner might pose the same question.
"""

from __future__ import annotations

from typing import Any


# ---- Per-finding question banks ---------------------------------------


FINDING_1_IPC_380_SCOPE = {
    "answer": (
        "IPC Section 380 (theft in dwelling house) maps to BNS Section 305 "
        "with a meaningful scope expansion: BNS 305 is titled \"Theft in a "
        "dwelling house, or means of transportation or place of worship\". "
        "The aggravation now expressly extends beyond dwellings to include "
        "vehicles (trains, buses, aircraft used in transit) and places of "
        "worship. Pre-2024 FIRs under IPC 380 used dwelling-house "
        "vocabulary; post-2024 FIRs under BNS 305 may invoke the new "
        "transport- and worship-place limbs even for fact patterns that "
        "would previously have been ordinary theft (IPC 379 / BNS 303). "
        "This is documented as Finding #1 in the project's "
        "bns_transition_findings.md notebook."
    ),
    "instructions": [
        "Has IPC Section 380 changed under the BNS?",
        "What is the scope of BNS Section 305 compared to IPC 380?",
        "Did the new criminal code expand the offence of theft in dwelling house?",
        "Does theft in a vehicle attract a special section under the BNS?",
        "How does theft in a place of worship get charged under the BNS?",
        "Compare IPC 380 with its BNS counterpart.",
        "Is theft from a railway carriage now an aggravated offence under BNS?",
        "What is the practical difference between IPC 380 and BNS 305?",
    ],
}

FINDING_2_IPC_366A_GENDER = {
    "answer": (
        "Yes. IPC Section 366A criminalised the procuration of a \"minor "
        "girl\" — the section was textually gender-specific. Under the "
        "Bharatiya Nyaya Sanhita, 2023, BNS Section 95 generalises the "
        "victim category to \"child\" — any person under eighteen, "
        "irrespective of gender. This is a substantive availability "
        "change, not a cosmetic one: prosecutions for procuration of male "
        "minors were unavailable under IPC 366A and had to be charged "
        "under POCSO or residuary offences. Under BNS 95 the same fact "
        "pattern is directly chargeable. Documented as Finding #2 in the "
        "project's bns_transition_findings.md notebook."
    ),
    "instructions": [
        "Has the gender scope of IPC 366A changed under the BNS?",
        "Does BNS Section 95 cover procuration of male minors?",
        "Was IPC 366A gender-neutral?",
        "Compare IPC 366A with BNS 95 on victim gender.",
        "Can a male child victim be the subject of a procuration charge under BNS 95?",
        "What changed in the procuration offence with the BNS?",
        "Is procuration of a minor still gender-specific under Indian law?",
        "Did the BNS expand the gender scope of any sexual offences?",
    ],
}

FINDING_3_IPC_366B_GENDER = {
    "answer": (
        "Yes. IPC Section 366B criminalised \"importation of girl from "
        "foreign country\" — gender-specific. BNS Section 96 widens the "
        "victim class to \"girl or boy\" imported from any country "
        "outside India. The expansion is documented in the PRS India "
        "analytical note on the BNS Bill and tracked as Finding #3 in "
        "the project's bns_transition_findings.md. As with IPC 366A → "
        "BNS 95, this is a substantive scope expansion masked as a "
        "re-enactment: pre-2024 cross-border trafficking of male minors "
        "had to be prosecuted under ITPA or IPC 370; post-BNS the "
        "section-specific offence is directly available."
    ),
    "instructions": [
        "Did IPC 366B cover male children?",
        "What does BNS Section 96 cover that IPC 366B did not?",
        "Has the importation-of-minor offence been made gender-neutral?",
        "Compare IPC 366B with BNS 96.",
        "Is cross-border trafficking of a male minor specifically punishable under BNS 96?",
        "Did the BNS expand any importation offences beyond girl victims?",
        "Tell me about the gender scope of BNS 96.",
        "What did IPC 366B require by way of victim gender?",
    ],
}

FINDING_4_TRAFFICKING_GAP = {
    "answer": (
        "Possibly. IPC Section 370A, inserted by the 2013 Criminal Law "
        "Amendment, punished \"exploitation of a trafficked person\" — "
        "victim age and gender neutral. The BNS structure places adult "
        "trafficking at Section 143 and child trafficking at Section "
        "144, and the section heading of BNSS 144 in the enacted text "
        "appears to narrow specifically to \"trafficked child\". If the "
        "exploitation offence sits only inside 144, then post-trafficking "
        "exploitation of an adult victim — forced labour in a factory, "
        "bonded domestic work — may no longer have a dedicated section "
        "and would have to be prosecuted under the generalised 143 or "
        "residuary labour statutes. This is the most load-bearing "
        "potential coverage gap the project has flagged and is currently "
        "marked needs_verification: true; it is documented as Finding #4 "
        "in the project's bns_transition_findings.md notebook."
    ),
    "instructions": [
        "Is there a coverage gap for exploitation of trafficked adults under the BNS?",
        "What happened to IPC 370A in the BNS?",
        "Does BNS 143 cover exploitation of adult trafficking victims?",
        "How are adult and child trafficking distinguished under the BNS?",
        "What is the relationship between IPC 370A and BNS 144?",
        "Is exploitation of a trafficked adult separately punishable under the BNS?",
        "Compare IPC 370A with the BNS trafficking framework.",
        "Where does an adult trafficking-exploitation case sit under the new code?",
    ],
}

FINDING_5_IPC_367_ORPHAN = {
    "answer": (
        "Partially. IPC Section 367 punished kidnapping or abduction \"to "
        "subject the victim to grievous hurt, slavery, or the unnatural "
        "lust of any person\". Post-Navtej Singh Johar v. Union of India "
        "(2018) the consensual-acts limb of IPC 377 was struck down; the "
        "BNS does not re-enact 377 in any form. BNS Section 140 (the "
        "consolidated kidnapping-to-harm section) carries forward the "
        "grievous-hurt and slavery limbs of IPC 367 but has no analogue "
        "for the \"unnatural lust\" limb. This leaves a coverage gap for "
        "kidnapping-with-intent-for-non-consensual-same-sex-or-trans-"
        "victim-acts that previously fell under that framing. Documented "
        "as Finding #5 in the project's bns_transition_findings.md."
    ),
    "instructions": [
        "What happened to IPC 367 under the BNS?",
        "Does BNS 140 cover all the limbs of IPC 367?",
        "Is the 'unnatural lust' limb of IPC 367 retained in the BNS?",
        "What is the BNS successor to IPC 367?",
        "How does the abolition of IPC 377 affect IPC 367's BNS mapping?",
        "Is there a gap in BNS 140 compared to IPC 367?",
        "Tell me about the kidnapping-to-harm provision in the BNS.",
        "Does the BNS criminalise kidnapping with intent for non-consensual same-sex acts?",
    ],
}

FINDING_6_IPC_124A_SEDITION = {
    "answer": (
        "It depends on what regime applies. IPC Section 124A (sedition) "
        "has been in judicially-imposed abeyance since May 2022 — the "
        "Constitution Bench in S.G. Vombatkere v. Union of India (W.P.(C) "
        "682/2021) directed that all pending IPC 124A prosecutions be "
        "stayed and no fresh FIRs be registered while the Court "
        "reconsiders the Kedar Nath Singh (1962) test. The matter is "
        "still pending. The BNS does not retain 124A; BNS Section 150 "
        "(\"Acts endangering sovereignty, unity and integrity of India\") "
        "is the probable successor but its scope-relation to 124A is "
        "contested in scholarship. Some readings hold BNS 150 broader "
        "(adding 'financial means', 'electronic communication', and "
        "explicit 'secession/armed rebellion' modalities); others hold "
        "it narrower (removing the vague 'disaffection' limb). No "
        "post-BNS Supreme Court pronouncement on scope yet. Documented "
        "as Finding #6 in the project's bns_transition_findings.md."
    ),
    "instructions": [
        "Is sedition still a criminal offence in India?",
        "What is the current status of IPC Section 124A?",
        "Has the Supreme Court reconsidered Kedar Nath Singh?",
        "What did Vombatkere v. Union of India hold about sedition prosecutions?",
        "Does the BNS retain sedition as an offence?",
        "What is BNS Section 150 about?",
        "Is BNS 150 broader or narrower than IPC 124A?",
        "Can a fresh sedition FIR be registered today under IPC 124A?",
        "How should I treat sedition in a BNS-era prosecution?",
    ],
}

FINDING_7_ABETMENT_CHAPTER = {
    "answer": (
        "Yes — substantially. The IPC's abetment chapter (Sections 107-"
        "120) is the foundational machinery for all co-accused criminal "
        "liability beyond common intention (Section 34) and common "
        "object (Section 149). \"302/109 IPC\" — murder read with the "
        "general abetment-punishment section — is one of the most "
        "common compound charges in Indian criminal practice. The BNS "
        "consolidates the chapter as Sections 45-62, with structurally "
        "similar provisions: BNS 45 (abetment definition, ← IPC 107), "
        "BNS 46 (abettor, ← IPC 108), BNS 49 (general punishment, ← "
        "IPC 109), BNS 50 (different intention, ← IPC 110), and BNS 53 "
        "which appears to merge IPC 113 (effect different from intended) "
        "and IPC 114 (abettor present at offence) into a single section. "
        "Pre-2024 charge-sheets reading \"Section X / 109 IPC\" must "
        "re-render as \"Section X' / 49 BNS\" for post-July-2024 conduct. "
        "Documented as Finding #7 in the project's bns_transition_findings.md."
    ),
    "instructions": [
        "Did the BNS change the abetment chapter?",
        "What is the BNS equivalent of IPC 109?",
        "How does BNS Section 49 relate to IPC 109?",
        "Compare IPC abetment provisions with BNS abetment chapter.",
        "What sections in the BNS deal with abetment?",
        "How would a 302/109 IPC charge be re-rendered under the BNS?",
        "Are IPC 113 and 114 separate sections under the BNS?",
        "What is the doctrinal significance of the abetment chapter consolidation in BNS?",
        "Where is the general abetment-punishment provision in the BNS?",
        "Has IPC 107's definition of abetment been preserved in the BNS?",
    ],
}

FINDING_8_BNS_AT_SC = {
    "answer": (
        "Effectively no, as of April 2026. A 1,579-judgment audit of the "
        "Supreme Court of India's criminal docket from 2015-2024 — "
        "performed by this project ten months after the BNS's 1 July "
        "2024 effective date — found zero BNS-only judgments and exactly "
        "two transition cases (judgments citing both IPC and BNS) in "
        "the entire corpus, both from 2024. The remaining 1,215 "
        "substantive judgments cite only the IPC, and 362 procedural / "
        "constitutional matters cite neither code. This is mechanically "
        "expected — Indian criminal cases reach the Supreme Court only "
        "after first-instance trial and at least one tier of appellate "
        "review (typically 2-5 years). BNS-charged matters cannot have "
        "completed appellate review by mid-2026. The implication for "
        "legal NLP is that any model trained on SC judgments through "
        "2024 is empirically a tool for IPC jurisprudence regardless of "
        "stated BNS support. High Court adoption will likely arrive "
        "sooner. Documented as Finding #8 in bns_transition_findings.md "
        "and detailed in docs/findings/2026-04-26_bns_at_sc_empirical.md."
    ),
    "instructions": [
        "Has the Supreme Court ruled on any BNS cases?",
        "Are there Supreme Court decisions interpreting the Bharatiya Nyaya Sanhita?",
        "When will BNS jurisprudence reach the Supreme Court?",
        "How many BNS-only judgments has the SC issued?",
        "Has any Supreme Court judgment cited the new Bharatiya Nyaya Sanhita?",
        "Why has the BNS not yet been tested at the Supreme Court level?",
        "What did the project's audit of SC criminal judgments find about BNS adoption?",
        "How long until BNS jurisprudence accumulates at the Supreme Court?",
        "Are the High Courts ahead of the Supreme Court on BNS cases?",
        "What is the empirical state of BNS adoption in apex Indian criminal jurisprudence?",
    ],
}

FINDING_9_CRPC_BNSS = {
    "answer": (
        "Yes — four substantive shifts are doctrinally consequential, "
        "documented as Finding #9 in the project's "
        "bns_transition_findings.md. (a) Default-bail timeline: CrPC "
        "167(2) maps to BNSS 187(3); the BNSS is widely understood to "
        "introduce a 180-day extended ceiling for organised-crime and "
        "terrorist-act offences in addition to the existing 60/90-day "
        "grids. (b) Anticipatory bail: CrPC 438 maps to BNSS 482 — note "
        "the number collision, BNSS 482 is the new section number for "
        "anticipatory bail, unrelated to CrPC 482 (HC inherent powers, "
        "which maps to BNSS 528). (c) High Court inherent powers: CrPC "
        "482 → BNSS 528, framework retained. (d) Arnesh Kumar arrest-"
        "protection regime: CrPC 41A (notice instead of arrest for "
        "≤7-year offences) appears to be folded into BNSS 35(7), needs "
        "verification. The BNSS also adds (i) mandatory audio-video "
        "recording of police statements in serious offences (BNSS 180, "
        "← CrPC 161), (ii) a formal trial-in-absentia framework for "
        "proclaimed offenders, and (iii) electronic-mode proceedings as "
        "a default option."
    ),
    "instructions": [
        "What changed in criminal procedure under the BNSS?",
        "Has the default bail timeline changed under the BNSS?",
        "What is the BNSS equivalent of CrPC 167(2)?",
        "Is anticipatory bail still available under the BNSS?",
        "Where does anticipatory bail sit in the BNSS?",
        "Does the BNSS retain the inherent powers of the High Court?",
        "What is the Arnesh Kumar regime under the BNSS?",
        "Has the BNSS changed how police statements are recorded?",
        "What is the new BNSS provision on trial in absentia?",
        "Are video-conference trials standard under the BNSS?",
        "Compare CrPC 167(2) and BNSS 187(3) — what changed?",
        "What are the most consequential procedural shifts from CrPC to BNSS?",
        "Why is the BNSS section number 482 a potential source of confusion?",
    ],
}

# Generic "should I worry about the BNS transition" framing pairs that
# tie multiple findings together.
TRANSITION_OVERVIEW = {
    "answer": (
        "The BNS / BNSS / BSA package took effect on 1 July 2024. Three "
        "things matter for handling a current case: (1) which regime "
        "applies — offences committed before that date are still "
        "governed by IPC / CrPC / Evidence Act; on-or-after by the new "
        "codes; (2) most provisions are renumbering with substantive "
        "frameworks intact (IPC 302 → BNS 103, CrPC 482 → BNSS 528, etc.) "
        "but a handful of sections carry real semantic shifts — gender "
        "scope expansion (IPC 366A/B), trafficking coverage "
        "ambiguity (IPC 370A → BNS 143/144), and the abetment-chapter "
        "consolidation (IPC 109 → BNS 49 etc.); (3) Supreme Court "
        "jurisprudence on the new codes is essentially nil through "
        "April 2026 — the appellate cycle has not yet produced BNS-era "
        "binding precedent at the apex level, so practitioners are "
        "reasoning from the bare act and the IPC/CrPC line of cases the "
        "BNS/BNSS substantially preserves. The IPC↔BNS and CrPC↔BNSS "
        "section mapping tables in this project's data/mappings/ are "
        "the structured reference."
    ),
    "instructions": [
        "What do I need to know about the BNS transition?",
        "How should a lawyer handle a case that straddles the IPC and BNS regimes?",
        "Give me an overview of the criminal law transition in 2024.",
        "What are the most important things to know about the BNS / BNSS / BSA package?",
        "How is the BNS-IPC transition handled in current Indian criminal practice?",
        "Should I be using the IPC or the BNS for a 2025 case?",
        "What's the practical impact of the BNS for criminal defence work?",
        "How significant is the BNS in current Indian criminal jurisprudence?",
        "What changes did the new criminal code package bring overall?",
    ],
}

# ---- Public generator -------------------------------------------------


_FINDING_BLOCKS = (
    FINDING_1_IPC_380_SCOPE,
    FINDING_2_IPC_366A_GENDER,
    FINDING_3_IPC_366B_GENDER,
    FINDING_4_TRAFFICKING_GAP,
    FINDING_5_IPC_367_ORPHAN,
    FINDING_6_IPC_124A_SEDITION,
    FINDING_7_ABETMENT_CHAPTER,
    FINDING_8_BNS_AT_SC,
    FINDING_9_CRPC_BNSS,
    TRANSITION_OVERVIEW,
)


def generate_pairs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, block in enumerate(_FINDING_BLOCKS, start=1):
        finding_tag = (
            f"finding_{idx}" if idx <= 9 else "transition_overview"
        )
        answer = block["answer"].strip()
        for inst in block["instructions"]:
            out.append({
                "instruction": inst.strip(),
                "input": "",
                "output": answer,
                "_metadata": {
                    "source": "bns_transition",
                    "source_id": finding_tag,
                    "generated_by": "hand_written",
                    "validated": False,
                },
            })
    return out
