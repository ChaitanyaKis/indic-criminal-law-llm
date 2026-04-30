"""BNS-transition reasoning pairs (v0.2: per-question answer scoping).

v0.1 used one shared answer per finding-block: every instruction variant
under a finding returned the full bundled answer. That design risked
teaching false doctrinal associations during training (e.g., correlating
'CrPC 167(2) questions' with 'Arnesh Kumar facts' when those are
procedurally distinct).

v0.2 splits each finding into doctrinally narrow sub-topics. Each
instruction variant maps to the sub-topic answer that specifically
addresses it; only general/synthesis questions route to the bundled
answer for the whole finding. Every sub-topic answer is traceable to a
paragraph in ``docs/bns_transition_findings.md``.

Findings #1-5 are inherently narrow (one doctrinal point each) and
remain single-sub-topic. Findings #6-11 are split into 3-7 sub-topics.
Findings #10 and #11 are project-tooling observations, included here
because a sophisticated legal-NLP user is the audience.

Two v0.2-specific structural checks run at generation time:
- Sub-topic answer length must be <= the v0.1 finding-level answer
  length (sub-topic answers are NARROWER, never broader). Findings #10
  and #11 have no v0.1 baseline; the check is skipped for them.
- Within a finding, the same instruction string must not appear under
  two different sub-topics (would create contradictory training signal).
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


# v0.1 answer lengths, in characters, measured from the prior version of
# this module. Sub-topic answers in v0.2 must be <= these values.
_V01_ANSWER_LENGTHS = {
    "finding_1": 656,
    "finding_2": 599,
    "finding_3": 586,
    "finding_4": 854,
    "finding_5": 682,
    "finding_6": 908,
    "finding_7": 922,
    "finding_8": 1041,
    "finding_9": 1034,
    "transition_overview": 983,
}


# ---- Finding 1 — IPC 380 scope expansion (single sub-topic) ----------

FINDING_1 = {
    "id": "finding_1",
    "title": "IPC 380 scope expansion",
    "sub_topics": {
        "ipc_380_scope_expansion": {
            "answer": (
                "IPC Section 380 (theft in dwelling house) maps to BNS "
                "Section 305 with a meaningful scope expansion. BNS 305 is "
                "titled 'Theft in a dwelling house, or means of "
                "transportation or place of worship', extending the "
                "aggravated context beyond dwellings to include trains, "
                "buses and aircraft used in transit, and places of "
                "worship. Pre-2024 FIRs under IPC 380 used dwelling-house "
                "vocabulary; post-2024 FIRs under BNS 305 may invoke the "
                "new transport- and worship-place limbs even for fact "
                "patterns that would previously have been ordinary theft "
                "(IPC 379 / BNS 303). Documented as Finding #1 in the "
                "project's bns_transition_findings.md."
            ),
            "instruction_variants": [
                "Has IPC Section 380 changed under the BNS?",
                "What is the scope of BNS Section 305 compared to IPC 380?",
                "Did the new criminal code expand the offence of theft in dwelling house?",
                "Does theft in a vehicle attract a special section under the BNS?",
                "How does theft in a place of worship get charged under the BNS?",
                "Compare IPC 380 with its BNS counterpart.",
                "Is theft from a railway carriage now an aggravated offence under BNS?",
                "What is the practical difference between IPC 380 and BNS 305?",
            ],
        },
    },
    "synthesis": None,
}


# ---- Finding 2 — IPC 366A gender (single sub-topic) ------------------

FINDING_2 = {
    "id": "finding_2",
    "title": "IPC 366A gender scope expansion",
    "sub_topics": {
        "ipc_366a_gender_neutralisation": {
            "answer": (
                "Yes. IPC Section 366A criminalised the procuration of a "
                "'minor girl' — the section was textually gender-specific. "
                "BNS Section 95 generalises the victim category to "
                "'child' (any person under eighteen, irrespective of "
                "gender). This is a substantive availability change, not "
                "cosmetic: prosecutions for procuration of male minors "
                "were unavailable under IPC 366A and had to be charged "
                "under POCSO or residuary offences. Under BNS 95 the same "
                "fact pattern is directly chargeable. Documented as "
                "Finding #2 in the project's bns_transition_findings.md."
            ),
            "instruction_variants": [
                "Has the gender scope of IPC 366A changed under the BNS?",
                "Does BNS Section 95 cover procuration of male minors?",
                "Was IPC 366A gender-neutral?",
                "Compare IPC 366A with BNS 95 on victim gender.",
                "Can a male child victim be the subject of a procuration charge under BNS 95?",
                "What changed in the procuration offence with the BNS?",
                "Is procuration of a minor still gender-specific under Indian law?",
                "Did the BNS expand the gender scope of any sexual offences?",
            ],
        },
    },
    "synthesis": None,
}


# ---- Finding 3 — IPC 366B gender (single sub-topic) ------------------

FINDING_3 = {
    "id": "finding_3",
    "title": "IPC 366B gender scope expansion",
    "sub_topics": {
        "ipc_366b_gender_neutralisation": {
            "answer": (
                "Yes. IPC Section 366B criminalised 'importation of girl "
                "from foreign country' — gender-specific. BNS Section 96 "
                "widens the victim class to 'girl or boy' imported from "
                "any country outside India. As with IPC 366A → BNS 95, "
                "this is a substantive scope expansion masked as a "
                "re-enactment: pre-2024 cross-border trafficking of male "
                "minors had to be prosecuted under ITPA or IPC 370; "
                "post-BNS the section-specific offence is directly "
                "available. Documented as Finding #3 in the project's "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "Did IPC 366B cover male children?",
                "What does BNS Section 96 cover that IPC 366B did not?",
                "Has the importation-of-minor offence been made gender-neutral?",
                "Compare IPC 366B with BNS 96.",
                "Is cross-border trafficking of a male minor specifically punishable under BNS 96?",
                "Did the BNS expand any importation offences beyond girl victims?",
                "Tell me about the gender scope of BNS 96.",
                "What did IPC 366B require by way of victim gender?",
            ],
        },
    },
    "synthesis": None,
}


# ---- Finding 4 — Trafficking gap (single sub-topic) ------------------

FINDING_4 = {
    "id": "finding_4",
    "title": "IPC 370A trafficking-exploitation potential coverage gap",
    "sub_topics": {
        "trafficking_exploitation_gap": {
            "answer": (
                "Possibly. IPC Section 370A, inserted by the 2013 Criminal "
                "Law Amendment, punished 'exploitation of a trafficked "
                "person' — victim age and gender neutral. The BNS places "
                "adult trafficking at Section 143 and child trafficking at "
                "Section 144, and the section heading of 144 in the "
                "enacted text appears to narrow specifically to "
                "'trafficked child'. If the exploitation offence sits "
                "only inside 144, then post-trafficking exploitation of an "
                "adult victim — forced labour, bonded domestic work — may "
                "no longer have a dedicated section and would have to be "
                "prosecuted under the generalised 143 or residuary labour "
                "statutes. This is the most load-bearing potential "
                "coverage gap the project has flagged and is currently "
                "marked needs_verification: true. Documented as Finding "
                "#4 in bns_transition_findings.md."
            ),
            "instruction_variants": [
                "Is there a coverage gap for exploitation of trafficked adults under the BNS?",
                "What happened to IPC 370A in the BNS?",
                "Does BNS 143 cover exploitation of adult trafficking victims?",
                "How are adult and child trafficking distinguished under the BNS?",
                "What is the relationship between IPC 370A and BNS 144?",
                "Is exploitation of a trafficked adult separately punishable under the BNS?",
                "Compare IPC 370A with the BNS trafficking framework.",
                "Where does an adult trafficking-exploitation case sit under the new code?",
            ],
        },
    },
    "synthesis": None,
}


# ---- Finding 5 — IPC 367 unnatural-lust orphan (single sub-topic) ----

FINDING_5 = {
    "id": "finding_5",
    "title": "IPC 367 unnatural-lust limb orphaned",
    "sub_topics": {
        "ipc_367_unnatural_lust_orphan": {
            "answer": (
                "Partially. IPC Section 367 punished kidnapping or "
                "abduction 'to subject the victim to grievous hurt, "
                "slavery, or the unnatural lust of any person'. Post-"
                "Navtej Singh Johar v. Union of India (2018) the "
                "consensual-acts limb of IPC 377 was struck down; the BNS "
                "does not re-enact 377 in any form. BNS Section 140 (the "
                "consolidated kidnapping-to-harm section) carries forward "
                "the grievous-hurt and slavery limbs of IPC 367 but has "
                "no analogue for the 'unnatural lust' limb. This leaves "
                "a coverage gap for kidnapping-with-intent-for-non-"
                "consensual-same-sex-or-trans-victim-acts that previously "
                "fell under that framing. Documented as Finding #5 in "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "What happened to IPC 367 under the BNS?",
                "Does BNS 140 cover all the limbs of IPC 367?",
                "Is the 'unnatural lust' limb of IPC 367 retained in the BNS?",
                "What is the BNS successor to IPC 367?",
                "How does the abolition of IPC 377 affect IPC 367's BNS mapping?",
                "Is there a gap in BNS 140 compared to IPC 367?",
                "Tell me about the kidnapping-to-harm provision in the BNS.",
                "Does the BNS criminalise kidnapping with intent for non-consensual same-sex acts?",
            ],
        },
    },
    "synthesis": None,
}


# ---- Finding 6 — IPC 124A → BNS 150 (3 sub-topics + synthesis) -------

FINDING_6 = {
    "id": "finding_6",
    "title": "IPC 124A (sedition) → BNS 150 under double cloud",
    "sub_topics": {
        "sedition_section_mapping": {
            "answer": (
                "IPC Section 124A (sedition) does not survive into the "
                "BNS. The probable successor is BNS Section 150, titled "
                "'Acts endangering sovereignty, unity and integrity of "
                "India'. The structural mapping is recorded in this "
                "project's IPC↔BNS table with `needs_verification: true` "
                "because the scope-relation between 124A and 150 has not "
                "yet been settled by the Supreme Court. Documented as "
                "Finding #6 in bns_transition_findings.md."
            ),
            "instruction_variants": [
                "What is the BNS successor to IPC 124A?",
                "Does the BNS retain sedition as an offence?",
                "What is BNS Section 150 about?",
                "Has IPC 124A been re-enacted under the new criminal code?",
                "What replaces sedition in the Bharatiya Nyaya Sanhita?",
                "Where in the BNS would I look for the sedition provision?",
                "Is BNS 150 the same as IPC 124A?",
            ],
        },
        "vombatkere_stay_status": {
            "answer": (
                "IPC Section 124A has been in judicially-imposed abeyance "
                "since May 2022. The Constitution Bench in S.G. "
                "Vombatkere v. Union of India (W.P.(C) 682/2021) directed "
                "that all pending IPC 124A prosecutions be stayed and no "
                "fresh FIRs be registered while the Court reconsiders the "
                "Kedar Nath Singh (1962) test in light of contemporary "
                "free-speech jurisprudence. The matter is still pending. "
                "Pre-2022 sedition convictions operate under the Kedar "
                "Nath Singh 'tendency to incite violence' test; the stay "
                "has frozen post-2022 doctrine development. Documented as "
                "Finding #6 in bns_transition_findings.md."
            ),
            "instruction_variants": [
                "What is the current status of IPC Section 124A?",
                "Has the Supreme Court reconsidered Kedar Nath Singh?",
                "What did Vombatkere v. Union of India hold about sedition prosecutions?",
                "Can a fresh sedition FIR be registered today under IPC 124A?",
                "Is sedition still a prosecutable offence under the IPC?",
                "What did the Supreme Court do in S.G. Vombatkere v. Union of India?",
                "Why is IPC 124A frozen?",
            ],
        },
        "bns_150_scope_debate": {
            "answer": (
                "BNS 150's scope-relation to IPC 124A is contested in "
                "scholarship. One reading, urged by commentators critical "
                "of the BNS drafting, holds 150 broader: it explicitly "
                "names 'financial means', 'electronic communication', and "
                "'secession, armed rebellion, subversive activities' as "
                "modalities, opening prosecutorial surface area that "
                "124A's single-word 'disaffection' formula did not "
                "enumerate. A competing reading, urged by government-side "
                "commentary, holds 150 narrower: it removes the vague "
                "'disaffection towards government' limb and requires a "
                "clearer actus reus. Both readings are defensible on the "
                "text alone; no Supreme Court pronouncement has settled "
                "the question. Documented as Finding #6 in "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "Is BNS 150 broader or narrower than IPC 124A?",
                "What scope changes did BNS 150 introduce compared to sedition?",
                "Does BNS 150 remove the 'disaffection' element of IPC 124A?",
                "Has the Supreme Court ruled on the scope of BNS 150?",
                "What modalities does BNS 150 add that IPC 124A did not name?",
                "Is the scope of BNS 150 settled?",
                "Why is the BNS 150 vs IPC 124A scope debated?",
            ],
        },
    },
    "synthesis": {
        "answer": (
            "It depends on what regime applies. IPC Section 124A "
            "(sedition) is in judicially-imposed abeyance since May 2022 "
            "(Vombatkere v. Union of India): pending prosecutions are "
            "stayed and no fresh FIRs may be registered while Kedar Nath "
            "Singh (1962) is being reconsidered. The BNS does not retain "
            "124A; BNS Section 150 is the probable successor but its "
            "scope-relation to 124A is contested — broader on some "
            "readings (financial means, electronic communication, "
            "secession), narrower on others (no 'disaffection' limb, "
            "tighter actus reus). No post-BNS Supreme Court pronouncement "
            "on scope yet. Documented as Finding #6 in "
            "bns_transition_findings.md."
        ),
        "instruction_variants": [
            "Is sedition still a criminal offence in India?",
            "How should I treat sedition in a BNS-era prosecution?",
            "Give me an overview of where sedition law stands today.",
            "Summarize the IPC 124A → BNS 150 transition.",
        ],
    },
}


# ---- Finding 7 — Abetment chapter (4 sub-topics + synthesis) ---------

FINDING_7 = {
    "id": "finding_7",
    "title": "Abetment chapter consolidation (IPC 107-120 → BNS 45-62)",
    "sub_topics": {
        "abetment_chapter_consolidation": {
            "answer": (
                "The IPC's abetment chapter (Sections 107-120) is "
                "consolidated under BNS at Sections 45-62. The chapter is "
                "the foundational machinery for all co-accused criminal "
                "liability beyond common intention (IPC 34 → BNS 3(5)) "
                "and common object in unlawful assembly (IPC 149 → BNS "
                "190). The structural framework is preserved: definition, "
                "abettor, punishment, and aggravated-effect provisions "
                "are all carried forward in re-numbered form. Documented "
                "as Finding #7 in bns_transition_findings.md."
            ),
            "instruction_variants": [
                "Did the BNS change the abetment chapter?",
                "Where is abetment dealt with in the Bharatiya Nyaya Sanhita?",
                "Compare the IPC abetment chapter with the BNS chapter on abetment.",
                "What sections in the BNS deal with abetment?",
                "Has the abetment framework changed under the BNS?",
                "Where does the BNS place co-accused liability provisions?",
            ],
        },
        "ipc_107_to_bns_45_definition": {
            "answer": (
                "IPC Section 107 (definition of abetment) maps to BNS "
                "Section 45. The three classical limbs — instigation, "
                "conspiracy, and intentional aiding — are preserved in "
                "BNS 45's definition. The mapping is recorded in this "
                "project's IPC↔BNS table; verification against the "
                "enacted Gazette text is pending. Documented as Finding "
                "#7 in bns_transition_findings.md."
            ),
            "instruction_variants": [
                "What is the BNS equivalent of IPC 107?",
                "Where is the definition of abetment in the BNS?",
                "What does BNS Section 45 do?",
                "Has the definition of abetment changed under the BNS?",
                "Compare IPC 107 with BNS 45.",
                "Are the three limbs of abetment preserved in the BNS?",
            ],
        },
        "ipc_109_to_bns_49_punishment": {
            "answer": (
                "IPC Section 109 (general punishment for abetment) maps "
                "to BNS Section 49. This is the highest-volume "
                "re-rendering in the abetment chapter: '302/109 IPC' "
                "(murder read with the abetment-punishment section) is "
                "one of the most common compound charges in Indian "
                "criminal practice. In the project's 1,349-doc Supreme "
                "Court corpus IPC 109 is cited 26 times (rank 30 "
                "overall). Pre-2024 charge-sheets reading 'Section X / "
                "109 IPC' must re-render as 'Section X' / 49 BNS' for "
                "post-July-2024 conduct. A model that fails this "
                "composition silently drops co-accused liability in "
                "post-BNS reasoning. Documented as Finding #7 in "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "What is the BNS equivalent of IPC 109?",
                "How does BNS Section 49 relate to IPC 109?",
                "How would a 302/109 IPC charge be re-rendered under the BNS?",
                "Where is the general abetment-punishment provision in the BNS?",
                "What's the BNS analogue of '109 IPC'?",
                "If a charge-sheet cites IPC 109, what's the post-BNS section?",
                "What happens to compound charges like '302/109 IPC' under the new code?",
            ],
        },
        "ipc_113_114_to_bns_53_merger": {
            "answer": (
                "IPC Section 113 ('effect different from intended') and "
                "IPC Section 114 ('abettor present at offence') appear "
                "to merge into a single BNS Section 53. The exact "
                "sub-section split — whether the two limbs remain "
                "analytically distinct as 53(1)/53(2) or have been "
                "doctrinally collapsed — is the open question. The "
                "project's mapping marks both 113 and 114 as "
                "`needs_verification: true` until the enacted Gazette "
                "text resolves this. Documented as Finding #7 in "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "Are IPC 113 and 114 separate sections under the BNS?",
                "What is the BNS successor to IPC 113?",
                "What is the BNS successor to IPC 114?",
                "Has IPC 113 been merged with IPC 114 in the BNS?",
                "What does BNS Section 53 cover?",
                "Is the abettor-present-at-offence limb of IPC 114 retained in the BNS?",
                "How are IPC 113 and 114 mapped to the BNS?",
            ],
        },
    },
    "synthesis": {
        "answer": (
            "Yes — substantially. The IPC's abetment chapter (Sections "
            "107-120) is consolidated as BNS Sections 45-62 with "
            "structurally similar provisions: BNS 45 (definition, ← IPC "
            "107), BNS 46 (abettor, ← IPC 108), BNS 49 (general "
            "punishment, ← IPC 109), BNS 50 (different intention, ← IPC "
            "110), and BNS 53 which appears to merge IPC 113 (effect "
            "different from intended) and IPC 114 (abettor present at "
            "offence). Pre-2024 charge-sheets reading 'Section X / 109 "
            "IPC' must re-render as 'Section X' / 49 BNS' for post-July-"
            "2024 conduct. Documented as Finding #7 in "
            "bns_transition_findings.md."
        ),
        "instruction_variants": [
            "What is the doctrinal significance of the abetment chapter consolidation in BNS?",
            "Give me an overview of how abetment law changed with the BNS.",
            "Summarize the abetment-chapter shift from IPC to BNS.",
        ],
    },
}


# ---- Finding 8 — BNS-not-yet-at-SC empirical (3 sub-topics + synthesis)

FINDING_8 = {
    "id": "finding_8",
    "title": "BNS has not yet reached the Supreme Court (April 2026)",
    "sub_topics": {
        "bns_sc_zero_judgments": {
            "answer": (
                "Effectively no BNS-only judgments at the Supreme Court "
                "as of April 2026. A 1,579-judgment audit of the SC "
                "criminal docket from 2015-2024, performed ten months "
                "after the BNS's 1 July 2024 effective date, found zero "
                "BNS-only judgments and exactly two transition cases "
                "(judgments citing both IPC and BNS) — both from 2024. "
                "The remaining 1,215 substantive judgments cite only the "
                "IPC, and 362 procedural / constitutional matters cite "
                "neither code. Documented as Finding #8 in "
                "bns_transition_findings.md and detailed in "
                "docs/findings/2026-04-26_bns_at_sc_empirical.md."
            ),
            "instruction_variants": [
                "Has the Supreme Court ruled on any BNS cases?",
                "Are there Supreme Court decisions interpreting the Bharatiya Nyaya Sanhita?",
                "How many BNS-only judgments has the SC issued?",
                "Has any Supreme Court judgment cited the new Bharatiya Nyaya Sanhita?",
                "What did the project's audit of SC criminal judgments find about BNS adoption?",
                "How many BNS-aware Supreme Court cases exist?",
            ],
        },
        "bns_appellate_pipeline": {
            "answer": (
                "BNS-charged matters cannot have completed appellate "
                "review by mid-2026, because the standard FIR-to-Supreme-"
                "Court pipeline takes 2-5 years through trial and at "
                "least one tier of appellate review. With BNS effective "
                "from 1 July 2024, the earliest BNS-charged matters "
                "cannot reach the SC until roughly 2026-2029. The "
                "project schedules re-runs of the corpus audit in October "
                "2026 and April 2027 to track the adoption curve. High "
                "Court adoption will likely arrive sooner. Documented as "
                "Finding #8 in bns_transition_findings.md."
            ),
            "instruction_variants": [
                "When will BNS jurisprudence reach the Supreme Court?",
                "Why has the BNS not yet been tested at the Supreme Court level?",
                "How long until BNS jurisprudence accumulates at the Supreme Court?",
                "Are the High Courts ahead of the Supreme Court on BNS cases?",
                "What is the typical FIR-to-SC pipeline timeline in Indian criminal cases?",
                "When are the next BNS adoption snapshots scheduled?",
            ],
        },
        "bns_legal_nlp_implication": {
            "answer": (
                "Any Indian-criminal-law model trained or fine-tuned on "
                "Supreme Court judgments through 2024 is, today, "
                "empirically a tool for IPC jurisprudence regardless of "
                "stated BNS support. The IPC↔BNS mapping work in this "
                "project (149 entries across four batches) functions as "
                "scaffolding for the wave that hasn't yet arrived; it is "
                "not currently retrieval-augmentation surface for an "
                "existing BNS docket. Documented as Finding #8 in "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "What does the lack of BNS jurisprudence mean for legal NLP models?",
                "Can a model trained on SC judgments through 2024 reason about BNS cases?",
                "Why is the IPC↔BNS mapping work scaffolding rather than retrieval surface?",
                "How does the BNS-at-SC empirical observation reframe legal NLP for Indian criminal law?",
                "If I fine-tune on SC criminal judgments, am I getting an IPC tool or a BNS tool?",
                "What is the empirical state of BNS adoption in apex Indian criminal jurisprudence?",
            ],
        },
    },
    "synthesis": {
        "answer": (
            "Effectively no, as of April 2026. A 1,579-judgment audit of "
            "the SC criminal docket from 2015-2024 found zero BNS-only "
            "judgments and two transition cases (citing both IPC and BNS) "
            "— both from 2024. This is mechanically expected: Indian "
            "criminal cases reach the SC only after first-instance trial "
            "and at least one tier of appellate review (typically 2-5 "
            "years). BNS-charged matters cannot have completed appellate "
            "review by mid-2026. The implication for legal NLP is that "
            "any model trained on SC judgments through 2024 is "
            "empirically a tool for IPC jurisprudence regardless of "
            "stated BNS support. High Court adoption will likely arrive "
            "sooner. Documented as Finding #8 in "
            "bns_transition_findings.md."
        ),
        "instruction_variants": [
            "Give me an overview of where BNS jurisprudence stands today.",
            "Summarize the empirical state of BNS at the Supreme Court.",
            "What's the broader picture on BNS adoption in Indian apex courts?",
        ],
    },
}


# ---- Finding 9 — CrPC → BNSS (7 sub-topics + synthesis) --------------

FINDING_9 = {
    "id": "finding_9",
    "title": "CrPC → BNSS substantive procedural shifts",
    "sub_topics": {
        "default_bail_167_to_187": {
            "answer": (
                "CrPC Section 167(2) maps to BNSS Section 187(3). Under "
                "CrPC 167(2), an accused becomes entitled to bail if the "
                "chargesheet is not filed within 60 days (offences "
                "punishable with up to 10 years) or 90 days (offences "
                "punishable with death/life/10+ years). The Sanjay Dutt "
                "→ Bikramjit Singh → Sanjay Kumar Agarwal line of "
                "jurisprudence rests on this section. BNSS 187 carries "
                "the framework forward but is widely understood to "
                "introduce a new extended ceiling (up to 180 days) for "
                "organised-crime and terrorist-act offences (BNS 111 and "
                "BNS 113). Both 167 and 167(2) are flagged "
                "`needs_verification: true` in the mapping until Gazette "
                "confirmation. Documented as Finding #9 in "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "What is the BNSS equivalent of CrPC 167(2)?",
                "Has the default bail timeline changed under the BNSS?",
                "How does BNSS 187(3) handle default bail?",
                "Has the 60/90 day default-bail timeline changed under BNSS?",
                "Is there a new 180-day default-bail ceiling under the BNSS?",
                "I'm reading old case law citing Section 167(2) CrPC for default bail — what's the current provision?",
                "Compare CrPC 167(2) and BNSS 187(3) — what changed?",
                "Does the Sanjay Kumar Agarwal default-bail framework survive into the BNSS?",
            ],
        },
        "anticipatory_bail_438_to_482_collision": {
            "answer": (
                "CrPC Section 438 (anticipatory bail) maps to BNSS "
                "Section 482 — note the number collision. BNSS 482 is "
                "the new section number for anticipatory bail, unrelated "
                "to CrPC 482 (HC inherent powers, which maps to BNSS "
                "528). The Sushila Aggarwal Constitution Bench framework "
                "on the limits of anticipatory bail still applies in "
                "principle, but its precise re-application under BNSS "
                "482 — including whether explicit offence-category "
                "exclusions narrow the relief — is contested in "
                "scholarship and unresolved at the SC level. The "
                "project's test suite at "
                "tests/test_crpc_bnss_mapping.py guards against "
                "autocomplete-style edits that would alias CrPC 482 to "
                "BNSS 482. Documented as Finding #9 in "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "Is anticipatory bail still available under the BNSS?",
                "Where does anticipatory bail sit in the BNSS?",
                "What is the BNSS equivalent of CrPC 438?",
                "Why is the BNSS section number 482 a potential source of confusion?",
                "Does Sushila Aggarwal still apply under BNSS 482?",
                "If someone says 'Section 482' in 2026, do they mean CrPC or BNSS?",
                "What does BNSS 482 deal with?",
                "Has anticipatory bail been narrowed under the BNSS?",
            ],
        },
        "inherent_powers_482_to_528": {
            "answer": (
                "CrPC Section 482 (inherent powers of the High Court) "
                "maps to BNSS Section 528. CrPC 482 is the most-cited "
                "procedural section in the project's corpus (345 of "
                "4,135 CrPC citations, rank 1 by a wide margin). Quash-"
                "petition jurisprudence hangs entirely on this section. "
                "BNSS 528 retains the three classical limbs verbatim — "
                "give effect to any order under the Sanhita, prevent "
                "abuse of process, secure the ends of justice. Whether "
                "the BNSS introduces any subtle scope limits (e.g., an "
                "explicit non-quashable list for serious offences) is "
                "the open verification question. Documented as Finding "
                "#9 in bns_transition_findings.md."
            ),
            "instruction_variants": [
                "What is the BNSS equivalent of CrPC 482?",
                "Does the BNSS retain the inherent powers of the High Court?",
                "Where in the BNSS would I find the quash-petition provision?",
                "What does BNSS 528 cover?",
                "Are the three classical limbs of CrPC 482 preserved in the BNSS?",
                "Has quash jurisdiction changed under the BNSS?",
                "Compare CrPC 482 with BNSS 528.",
            ],
        },
        "arnesh_kumar_41a_to_35_7": {
            "answer": (
                "CrPC Section 41A (notice instead of arrest for offences "
                "punishable with imprisonment of seven years or less) "
                "appears to be folded into BNSS Section 35(7). 41A was "
                "inserted after Arnesh Kumar v State of Bihar (2014) to "
                "codify the notice-before-arrest framework, with "
                "mandatory case-diary entries, magisterial scrutiny, and "
                "recorded reasons for departing from notice. Whether "
                "BNSS folds 41A into a sub-section of 35 (i.e. 35(7)) or "
                "retains it as a free-standing 35A is the verification "
                "question — recall is approximately 35(7) but uncertain. "
                "Documented as Finding #9 in bns_transition_findings.md."
            ),
            "instruction_variants": [
                "What is the Arnesh Kumar regime under the BNSS?",
                "What is the BNSS equivalent of CrPC 41A?",
                "Where does the notice-before-arrest framework live in the BNSS?",
                "Does the BNSS preserve the Arnesh Kumar arrest-protection regime?",
                "Has the 7-year-offence notice rule been retained?",
                "What does BNSS 35(7) deal with?",
                "Is the Arnesh Kumar notice procedure still mandatory under the BNSS?",
            ],
        },
        "police_statements_av_recording": {
            "answer": (
                "CrPC Section 161 (police statements) maps to BNSS "
                "Section 180. Beyond the renumbering, BNSS 180 "
                "introduces mandatory audio-video recording of "
                "statements taken under the police-statement provision "
                "in offences punishable with seven-plus years' "
                "imprisonment. This is a substantive evidentiary "
                "upgrade: a defective or absent recording becomes a new "
                "vector for challenging admissibility or fairness of "
                "investigation. The CrPC 162 bar on use of police "
                "statements (→ BNSS 181) is otherwise carried forward. "
                "Documented as Finding #9 in bns_transition_findings.md."
            ),
            "instruction_variants": [
                "Has the BNSS changed how police statements are recorded?",
                "Is audio-video recording mandatory for police statements under BNSS?",
                "What is the BNSS equivalent of CrPC 161?",
                "What does BNSS 180 require?",
                "When is audio-video recording of police statements mandatory under BNSS?",
                "Can a defective audio-video recording challenge admissibility under BNSS?",
                "Has the Section 162 CrPC bar been carried forward into the BNSS?",
            ],
        },
        "plea_bargaining_invisible_at_sc": {
            "answer": (
                "Plea bargaining is empirically invisible at the Supreme "
                "Court level. CrPC sections 265A-265L (the plea-"
                "bargaining provisions inserted by the 2005 amendment) "
                "do not appear in the top-50 cited sections in the "
                "project's 1,579-doc corpus, nor any of them in the "
                "top-100. This suggests limited apex-level engagement "
                "with the framework despite its 18-year availability — "
                "an empirical signature of how rarely the SC takes up "
                "plea-bargaining questions on appeal. BNSS retains the "
                "plea bargaining chapter with renumbering (290-300, "
                "pending exact verification). Whether SC engagement "
                "increases under BNSS is an empirical question for "
                "future corpus snapshots. Documented as Finding #9 in "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "How often does the Supreme Court engage with plea bargaining?",
                "Why doesn't plea bargaining appear in the top-50 cited CrPC sections?",
                "Does the BNSS retain the plea-bargaining framework?",
                "Where in the BNSS is plea bargaining located?",
                "What is the empirical state of plea-bargaining jurisprudence at the SC?",
                "Has CrPC 265A been carried forward into the BNSS?",
                "Why is plea bargaining considered invisible at the apex level?",
            ],
        },
        "chapter_shift_pattern": {
            "answer": (
                "The CrPC→BNSS renumbering follows a structural insertion "
                "pattern. New chapters are inserted that systematically "
                "push existing sections down by +20 positions "
                "(investigation chapter: CrPC 153-176 → BNSS 173-196) or "
                "+40-46 positions (appellate/bail/inherent-powers: CrPC "
                "397/438/482 → BNSS 438/482/528). Ten section-number "
                "collisions were detected in the project's 67-entry "
                "mapping table — every one is a natural consequence of "
                "this shift, not a typo. The practical implication: a "
                "practitioner saying 'Section 482' in 2026+ must specify "
                "CrPC 482 (HC inherent powers) or BNSS 482 (anticipatory "
                "bail). Documented as Finding #9 in "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "Why are there number collisions between CrPC and BNSS section numbers?",
                "How does the CrPC→BNSS section renumbering work?",
                "Why does CrPC 482 map to BNSS 528 but BNSS 482 mean something else?",
                "What is the structural pattern behind the BNSS renumbering?",
                "How big is the section-number shift between the CrPC and BNSS?",
                "Do CrPC and BNSS share the same section numbers?",
                "How should a legal-NLP system disambiguate between CrPC 482 and BNSS 482?",
            ],
        },
    },
    "synthesis": {
        "answer": (
            "Several substantive shifts are doctrinally consequential. "
            "(a) Default-bail timeline: CrPC 167(2) → BNSS 187(3) with a "
            "new 180-day ceiling for organised-crime and terrorist-act "
            "offences. (b) Anticipatory bail: CrPC 438 → BNSS 482 (note "
            "the number collision). (c) HC inherent powers: CrPC 482 → "
            "BNSS 528, framework retained. (d) Arnesh Kumar arrest-"
            "protection: CrPC 41A → BNSS 35(7). (e) Police statements: "
            "CrPC 161 → BNSS 180 with mandatory audio-video recording in "
            "serious offences. (f) New-in-BNSS without CrPC predecessor: "
            "trial-in-absentia for proclaimed offenders and electronic-"
            "mode process (electronic FIRs, video-conferencing of witness "
            "statements, electronic summons) — genuinely new procedural "
            "machinery rather than renumbered carryovers. Documented as "
            "Finding #9 in bns_transition_findings.md."
        ),
        "instruction_variants": [
            "What changed in criminal procedure under the BNSS?",
            "Summarize the major procedural shifts from CrPC to BNSS.",
            "Give me an overview of how Indian criminal procedure changed in 2024.",
            "What are the most consequential procedural shifts from CrPC to BNSS?",
        ],
    },
}


# ---- Finding 10 — Gemini thinking-tokens (3 sub-topics + synthesis) --
# No v0.1 baseline (excluded from v0.1).

FINDING_10 = {
    "id": "finding_10",
    "title": "Gemini 2.5 Flash burns 95% of max_output_tokens on hidden reasoning",
    "sub_topics": {
        "gemini_thinking_bug": {
            "answer": (
                "Gemini 2.5 Flash and Pro burn approximately 95% of "
                "`max_output_tokens` on hidden reasoning by default. "
                "With `max_output_tokens=1024`, the model spent 980 "
                "tokens on hidden 'thinking' and produced only ~44 "
                "visible tokens. Thinking tokens count against the "
                "user-set budget but never appear in the visible "
                "response. To prevent truncation, the project disables "
                "thinking explicitly via "
                "`GenerationConfig(thinking_config=ThinkingConfig("
                "thinking_budget=0))`. Without this, "
                "`max_output_tokens=1024` becomes effectively `≈40-100` "
                "of usable output. Documented as Finding #10 in "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "Why does Gemini 2.5 Flash truncate its answers?",
                "How do I disable Gemini's thinking-token consumption?",
                "What is the thinking-budget bug in Gemini 2.5?",
                "Why does max_output_tokens=1024 produce only ~40 visible tokens with Gemini Flash?",
                "What's the API-level fix for Gemini's thinking-token issue?",
                "How many tokens does Gemini's hidden reasoning typically consume?",
            ],
        },
        "rag_thinking_implication": {
            "answer": (
                "In a RAG pipeline, Gemini 2.5's default thinking "
                "behaviour is silently catastrophic. Retrieval already "
                "does the heavy reasoning work; the model's job is to "
                "synthesize retrieved chunks into a grounded answer, "
                "which doesn't benefit from extensive chain-of-thought. "
                "With thinking enabled, the model truncates its actual "
                "answer mid-sentence to fit within the remaining budget. "
                "A practitioner debugging the resulting partial output "
                "would likely misdiagnose as model hallucination, "
                "prompt-template problems, or insufficient retrieval. "
                "Documented as Finding #10 in "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "Why might my Gemini-based RAG answers end mid-sentence?",
                "How does Gemini's thinking-budget interact with RAG?",
                "If retrieval is correct and the answer is truncated, what's the likely cause?",
                "Why is Gemini's default thinking budget bad for RAG?",
                "How should I debug a Gemini RAG that produces partial answers?",
                "Does chain-of-thought help RAG synthesis?",
            ],
        },
        "gemini_thinking_reproducibility": {
            "answer": (
                "Published RAG benchmarks using Gemini 2.5 may be "
                "silently underreporting answer quality when the default "
                "thinking budget collides with typical "
                "`max_output_tokens` settings. Researchers reproducing "
                "those benchmarks should explicitly set "
                "`thinking_config=ThinkingConfig(thinking_budget=0)` to "
                "ensure visible tokens dominate the budget. This "
                "consideration is worth a footnote in any paper's "
                "experimental-setup section. Documented as Finding #10 "
                "in bns_transition_findings.md."
            ),
            "instruction_variants": [
                "What should published RAG benchmarks document about Gemini's thinking budget?",
                "How does Gemini's thinking-budget bug affect benchmark reproducibility?",
                "What setup detail should papers using Gemini 2.5 disclose?",
                "Could existing RAG benchmarks be underreporting answer quality on Gemini?",
                "Why is the thinking-budget setting a reproducibility concern?",
            ],
        },
    },
    "synthesis": {
        "answer": (
            "Gemini 2.5 Flash and Pro consume ~95% of "
            "`max_output_tokens` on hidden reasoning by default. With "
            "`max_output_tokens=1024`, ~980 tokens go to hidden "
            "thinking, leaving ~44 for the visible answer. For RAG "
            "pipelines this is silently catastrophic: retrieval has "
            "already done the reasoning, and chain-of-thought just "
            "truncates the answer mid-sentence. The fix is "
            "`thinking_config=ThinkingConfig(thinking_budget=0)`. "
            "Implications: published Gemini-RAG benchmarks may be "
            "underreporting answer quality; experimental-setup sections "
            "should disclose the thinking-budget setting. Documented as "
            "Finding #10 in bns_transition_findings.md."
        ),
        "instruction_variants": [
            "Give me an overview of the Gemini thinking-token issue.",
            "Summarize the Gemini 2.5 thinking-budget finding.",
        ],
    },
}


# ---- Finding 11 — Citation verifier + hallucination (3 sub-topics +
# synthesis). No v0.1 baseline.

FINDING_11 = {
    "id": "finding_11",
    "title": "Citation verifier was buggy; LLM hallucinates legal citations",
    "sub_topics": {
        "citation_verifier_bug": {
            "answer": (
                "The project's citation verifier had a regex bug: it "
                "extracted only the first `doc_id` per bracketed "
                "citation group. When Gemini emitted multi-id brackets "
                "like `[doc_id: REAL, doc_id: HALLUCINATED]`, the "
                "verifier saw only `REAL` and reported the citation as "
                "valid. The hallucination was silently swallowed. The "
                "end-to-end test asserting 'all citations valid' was "
                "passing because of this — not because Gemini wasn't "
                "hallucinating, but because the verifier was failing to "
                "detect when it did. Documented as Finding #11 in "
                "bns_transition_findings.md."
            ),
            "instruction_variants": [
                "What was the bug in the citation verifier?",
                "Why was the citation verifier missing hallucinated doc_ids?",
                "How did the regex bug in citation verification work?",
                "Why was the end-to-end RAG test silently passing despite hallucinations?",
                "What did the verifier-regex bug overlook?",
                "How did multi-id brackets fool the citation verifier?",
            ],
        },
        "hallucination_rate_finding": {
            "answer": (
                "Gemini 2.5 Flash hallucinates legal case citations at a "
                "non-zero rate even when retrieval is providing high-"
                "quality grounded context. A 5-run signal capture on the "
                "anticipatory-bail query documented two distinct failure "
                "modes — stable fabrication of plausible doc_ids, and "
                "chunk-ordinal-as-doc-id collapse — at a combined "
                "hallucination rate of 50% of emitted citations. "
                "'Citation verification catches real hallucinations' is "
                "now a demonstrated claim, not a theoretical one. "
                "Documented as Finding #11 in "
                "bns_transition_findings.md and detailed in "
                "docs/findings/2026-04-28_hallucination_signal.md."
            ),
            "instruction_variants": [
                "Does Gemini 2.5 Flash hallucinate legal citations?",
                "What is the empirical hallucination rate of Gemini 2.5 on legal queries?",
                "What hallucination failure modes did the project document?",
                "How often does Gemini fabricate doc_ids despite grounded retrieval?",
                "What did the 5-run signal capture on anticipatory bail show?",
                "Are there distinct hallucination failure modes in LLM citation generation?",
                "What does the project's hallucination signal study report?",
            ],
        },
        "test_architecture_lesson": {
            "answer": (
                "The previously-passing "
                "`test_end_to_end_rag_with_known_answer` test in "
                "`tests/test_rag.py` was a false-positive — asserting "
                "correctness via a buggy verifier. The lesson for legal "
                "NLP CI: contract tests should test our code, not the "
                "LLM's behaviour. Hard contract tests verify what the "
                "codebase commits to; informational signal tests (e.g., "
                "observed hallucination rate) belong in a separate "
                "pytest mark and should not block CI. Documented as "
                "Finding #11 in bns_transition_findings.md."
            ),
            "instruction_variants": [
                "What test-architecture lesson came out of the verifier-bug discovery?",
                "Why was the end-to-end RAG test a false positive?",
                "How should legal NLP CI distinguish contract tests from signal tests?",
                "What's the difference between a contract test and an informational test?",
                "Should hallucination-rate tests be hard contract tests?",
                "What should contract tests in a RAG system verify?",
            ],
        },
    },
    "synthesis": {
        "answer": (
            "The project's citation verifier had a regex bug that "
            "extracted only the first `doc_id` per bracketed citation "
            "group, silently swallowing hallucinations in multi-id "
            "brackets. Fixing it surfaced two empirical findings: "
            "(1) Gemini 2.5 Flash hallucinates legal citations even with "
            "high-quality grounded retrieval — a 5-run signal capture "
            "documented stable fabrication and chunk-ordinal-as-doc-id "
            "collapse at a combined 50% rate of emitted citations; "
            "(2) the previously-passing end-to-end test was a false "
            "positive. The lesson for legal NLP CI: contract tests "
            "should test our code, not the LLM's behaviour. Documented "
            "as Finding #11 in bns_transition_findings.md."
        ),
        "instruction_variants": [
            "Give me an overview of the citation-verifier and hallucination findings.",
            "Summarize the verifier bug and the hallucination signal it surfaced.",
        ],
    },
}


# ---- Transition overview (multi-finding synthesis) -------------------

TRANSITION_OVERVIEW = {
    "id": "transition_overview",
    "title": "BNS / BNSS / BSA transition overview",
    "sub_topics": {
        "transition_overview": {
            "answer": (
                "The BNS / BNSS / BSA package took effect on 1 July "
                "2024. Three things matter for handling a current case: "
                "(1) which regime applies — offences committed before "
                "that date are still governed by IPC / CrPC / Evidence "
                "Act; on-or-after by the new codes; (2) most provisions "
                "are renumbering with substantive frameworks intact (IPC "
                "302 → BNS 103, CrPC 482 → BNSS 528, etc.) but a handful "
                "of sections carry real semantic shifts — gender scope "
                "expansion (IPC 366A/B), trafficking coverage ambiguity "
                "(IPC 370A → BNS 143/144), and the abetment-chapter "
                "consolidation (IPC 109 → BNS 49 etc.); (3) Supreme "
                "Court jurisprudence on the new codes is essentially nil "
                "through April 2026 — the appellate cycle has not yet "
                "produced BNS-era binding precedent at the apex level, "
                "so practitioners are reasoning from the bare act and "
                "the IPC/CrPC line of cases the BNS/BNSS substantially "
                "preserves. The IPC↔BNS and CrPC↔BNSS section mapping "
                "tables in this project's data/mappings/ are the "
                "structured reference."
            ),
            "instruction_variants": [
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
        },
    },
    "synthesis": None,
}


# ---- Public generator ------------------------------------------------


_FINDINGS = (
    FINDING_1,
    FINDING_2,
    FINDING_3,
    FINDING_4,
    FINDING_5,
    FINDING_6,
    FINDING_7,
    FINDING_8,
    FINDING_9,
    FINDING_10,
    FINDING_11,
    TRANSITION_OVERVIEW,
)


def _check_v01_length_cap(finding: dict[str, Any]) -> None:
    """Sub-topic answers must be <= the v0.1 finding answer length."""
    fid = finding["id"]
    cap = _V01_ANSWER_LENGTHS.get(fid)
    if cap is None:
        return  # Findings #10/#11 had no v0.1 baseline.
    for st_name, st in finding["sub_topics"].items():
        n = len(st["answer"].strip())
        if n > cap:
            raise AssertionError(
                f"v0.2 sub-topic answer too long: {fid}/{st_name} "
                f"is {n} chars, v0.1 baseline is {cap}. Sub-topic "
                f"answers must be NARROWER than the bundled v0.1 answer."
            )
    syn = finding.get("synthesis")
    if syn is not None:
        n = len(syn["answer"].strip())
        if n > cap:
            raise AssertionError(
                f"v0.2 synthesis answer for {fid} is {n} chars, "
                f"v0.1 baseline is {cap}."
            )


def _check_within_finding_dedup(finding: dict[str, Any]) -> None:
    """Same instruction must not appear under two sub-topics within a finding."""
    seen: dict[str, str] = {}
    for st_name, st in finding["sub_topics"].items():
        for inst in st["instruction_variants"]:
            inst_norm = inst.strip().lower()
            if inst_norm in seen:
                raise AssertionError(
                    f"Within-finding duplicate instruction in "
                    f"{finding['id']}: {inst!r} appears under both "
                    f"{seen[inst_norm]!r} and {st_name!r}."
                )
            seen[inst_norm] = st_name
    syn = finding.get("synthesis")
    if syn is not None:
        for inst in syn["instruction_variants"]:
            inst_norm = inst.strip().lower()
            if inst_norm in seen:
                raise AssertionError(
                    f"Within-finding duplicate (synthesis) in "
                    f"{finding['id']}: {inst!r} also appears under "
                    f"{seen[inst_norm]!r}."
                )
            seen[inst_norm] = "synthesis"


def generate_pairs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for finding in _FINDINGS:
        _check_v01_length_cap(finding)
        _check_within_finding_dedup(finding)
        fid = finding["id"]
        for st_name, st in finding["sub_topics"].items():
            answer = st["answer"].strip()
            for inst in st["instruction_variants"]:
                out.append({
                    "instruction": inst.strip(),
                    "input": "",
                    "output": answer,
                    "_metadata": {
                        "source": "bns_transition",
                        "source_id": f"{fid}__{st_name}",
                        "generated_by": "hand_written",
                        "validated": False,
                    },
                })
        syn = finding.get("synthesis")
        if syn is not None:
            answer = syn["answer"].strip()
            for inst in syn["instruction_variants"]:
                out.append({
                    "instruction": inst.strip(),
                    "input": "",
                    "output": answer,
                    "_metadata": {
                        "source": "bns_transition",
                        "source_id": f"{fid}__synthesis",
                        "generated_by": "hand_written",
                        "validated": False,
                    },
                })
    return out
