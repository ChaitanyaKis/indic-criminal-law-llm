# BNS Transition — Substantive Observations

Running notebook of non-trivial semantic changes discovered while building
the IPC↔BNS mapping. These are not clerical renumberings; they are scope,
gender, or doctrinal shifts that will affect how a model reasons about
pre- vs post-July-2024 FIRs, charges, and judgments. Candidate material
for the paper's "Analysis of BNS Transition" section.

Verification status: preliminary, flagged against enacted Gazette text
pending legal review.

---

## 1. IPC 380 scope expansion (theft in dwelling)

IPC 380 criminalised theft committed in a "building, tent or vessel used
as a human dwelling, or used for the custody of property". BNS 305 keeps
this core and extends the aggravated context to "means of transportation"
(trains, buses, aircraft, vessels used for transit — not just as dwellings)
and "places of worship". For legal-NLP purposes: a pre-2024 FIR under IPC
380 will describe the *locus* in dwelling-house vocabulary, while a
post-2024 FIR under BNS 305 may invoke bus/train/temple-theft fact
patterns that previously fell under plain theft (IPC 379). A model
reasoning over charge-sheets across the 2024 boundary must know this
aggravation creep exists — or it will either under-charge post-BNS
judgments or hallucinate 305 applicability pre-BNS.

Verification status: Inferred from MHA Table + PRS note.

## 2. IPC 366A gender scope expansion ("minor girl" → "child")

IPC 366A, "Procuration of minor girl", was explicitly and textually
gender-specific: it punished inducing a *minor girl* under eighteen to
go from any place with intent that she be forced or seduced to illicit
intercourse. BNS 95 generalises the victim to "child" (any person under
eighteen, irrespective of gender). This is a substantive availability
change, not cosmetic: prosecutions for procuration of male minors were
unavailable under IPC 366A and had to be charged under other sections
(POCSO where applicable, or residuary offences); under BNS 95 the same
fact pattern is directly chargeable. For training data: identical
conduct against a male minor in 2023 vs 2025 will produce different
FIR sections — the model should not treat this as noise.

Verification status: Inferred from MHA Table + PRS note.

## 3. IPC 366B gender scope expansion ("girl" → "girl or boy")

Same pattern as IPC 366A, one section over. IPC 366B, "Importation of
girl from foreign country", was gender-specific; BNS 96 widens to "girl
or boy imported from any country outside India" (the PRS analytical note
flags this expansion explicitly). Pre-2024 cases involving cross-border
trafficking of male minors had to be prosecuted under ITPA or the
trafficking provisions (IPC 370); post-BNS the section-specific import
offence is directly available. The prosecutorial route diverges even
where the underlying fact pattern is identical.

Verification status: Inferred from PRS India analytical note.

## 4. IPC 370 / 370A → BNS 143 / 144 potential scope gap

IPC 370A, inserted by the 2013 Criminal Law Amendment, punished
"exploitation of a trafficked person" — victim age and gender neutral.
BNS places adult trafficking at 143 and child trafficking at 144, and
the section heading of 144 in the enacted text appears to narrow
explicitly to "trafficked child". If the *exploitation* offence sits
only inside 144, then post-trafficking exploitation of an adult victim
(forced labour in a factory, bonded domestic work) may no longer have
a dedicated section — it would have to be prosecuted under the
generalised 143 or residuary labour statutes. This is the single most
load-bearing mapping in this batch and is also the one I'm least able
to verify from memory. If confirmed, it is a prosecutorial coverage
gap, not a nomenclature change, and warrants immediate legal review.

Verification status: **Needs Gazette verification (critical priority)**.

## 5. IPC 367 "unnatural lust" limb orphaned

IPC 367 punished kidnapping or abduction to subject the victim to
"grievous hurt, slavery, or the unnatural lust of any person" — the
third limb being a 377-era reference to non-consensual same-sex acts.
Post-*Navtej Singh Johar v Union of India* (2018) the consensual-acts
part of 377 was struck down; BNS simply does not re-enact 377 and,
correspondingly, BNS 140 (the consolidated kidnapping-to-harm section)
covers only the grievous-hurt and slavery limbs of IPC 367. Non-
consensual acts that would historically have fallen under the "unnatural
lust" framing — particularly same-sex and trans-victim assaults after
kidnapping — have no direct BNS successor. This chains with the IPC 377
coverage gap already flagged in `mapping_verification_backlog.md`; the
kidnapping-adjacent limb is a second vector of the same underlying
legislative omission and deserves the same treatment in the paper's
discussion of BNS's handling of post-377 offences.

Verification status: Inferred from MHA Table + PRS note.

## 6. IPC 124A (sedition) → BNS 150 under a double cloud

The sedition offence under IPC 124A has been in judicially-imposed
abeyance since May 2022. In *S.G. Vombatkere v Union of India*
(W.P.(C) 682/2021) the Supreme Court directed that all pending IPC
124A prosecutions be stayed and no fresh FIRs be registered under
the section while it reconsidered the Kedar Nath Singh (1962)
test in light of contemporary free-speech jurisprudence. The matter
is still pending; IPC 124A has effectively been frozen — prosecutable
on paper but not in practice — for the entirety of the BNS-drafting
window.

BNS 150 is the probable 124A successor but is actively contested in
legal scholarship and its scope-relation to 124A is unsettled. One
reading, urged by commentators critical of the BNS drafting, holds
that 150 is *broader*: it explicitly names "financial means",
"electronic communication", and "secession, armed rebellion,
subversive activities" as modalities, opening prosecutorial surface
area that 124A's single-word "disaffection" formula did not
enumerate. A competing reading, urged by government-side commentary,
holds that 150 is *narrower*: it removes the vague "disaffection
towards government established by law" limb and requires a clearer
actus reus (acts tending to endangerment of sovereignty, unity, or
integrity). Both readings are defensible on the text alone; neither
has been settled by the Supreme Court, and no reported BNS 150
prosecution as of this mapping date has reached the SC.

The NLP implication is material. Pre-2022 judgments under IPC 124A
operate under Kedar Nath Singh's "tendency to incite violence" test;
the Vombatkere stay has frozen any post-2022 doctrine development
under IPC 124A; and BNS 150 doctrine is empty. A model trained on
pre-2022 sedition convictions without temporal awareness will
project Kedar Nath Singh doctrine forward onto BNS 150 fact
patterns, over-confidently. The mapping entry flags this
(`needs_verification: true`) but the robust fix is training-time
temporal conditioning: the model should know that citing sedition
doctrine for a 2024+ fact pattern requires hedging on both the stay
and the scope-debate. Not a training-data problem; an evaluation
problem.

Verification status: Inferred from public legal commentary; awaits
post-enactment case law.

## 7. Abetment chapter consolidation (IPC 107-120 → BNS 45-62)

The IPC's abetment chapter (sections 107-120) is the foundational
machinery for **all** co-accused criminal liability in Indian law
beyond the two narrow doctrines of common intention (IPC 34 → BNS
3(5)) and common object in unlawful assembly (IPC 149 → BNS 190).
"302/109 IPC" — murder read with the general abetment-punishment
section — is one of the most common compound charges in Indian
criminal practice; in the current 1,349-doc Supreme Court corpus
the inventory shows IPC 109 cited 26 times (rank 30 overall, top-10
among purely procedural/general-principles sections).

BNS 45-62 appears to consolidate the chapter with structurally
similar provisions: BNS 45 (abetment definition, IPC 107), BNS 46
(abettor, IPC 108), BNS 49 (general punishment, IPC 109), BNS 50
(abetment with different intention, IPC 110), and BNS 53 — which
appears to merge IPC 113 ("effect different from intended") and IPC
114 ("abettor present at offence") into a single section. The exact
sub-section split within BNS 53 is the open question: do the two
limbs remain analytically distinct (sub-sections 53(1) / 53(2)) or
have they been doctrinally collapsed? The mapping marks both 113
and 114 as ``needs_verification: true`` until the enacted Gazette
text resolves this.

The NLP implication is one of the largest-volume mapping shifts in
the entire IPC→BNS transition. Every pre-2024 charge-sheet that
reads "Section X / 109 IPC" (X being any substantive offence) must
re-render as "Section X' / 49 BNS" for any post-July-2024 fact
pattern, where X' is the substantive offence's BNS analogue. A model
that fails this composition silently drops co-accused liability in
post-BNS reasoning — an error whose downstream impact runs through
practically every multi-accused criminal case the model encounters.

Verification status: Inferred from MHA Comparative Table; sub-section
precision pending Gazette check.

## 8. Empirical: BNS has not yet reached the Supreme Court (April 2026)

A 1,579-judgment audit of the SC criminal docket from 2015–2024,
performed ten months after the BNS's July 1, 2024 effective date,
finds that BNS jurisprudence has effectively not yet reached the
Supreme Court of India. Across the entire corpus there are zero
BNS-only judgments and exactly two transition cases (judgments
citing both IPC and BNS) — both from 2024. The remaining 1,215
substantive judgments cite only the IPC, and 362 procedural /
constitutional matters cite neither code. The two "Both" cases
represent the entire BNS-aware SC reasoning surface as of April
2026.

This is mechanically expected — the standard FIR-to-SC pipeline
takes 2–5 years, so BNS-charged matters cannot have completed
appellate review yet — but the implication for legal NLP is the
opposite of the typical product narrative. Every Indian-criminal-law
model trained or fine-tuned on SC judgments through 2024 is, today,
empirically a tool for IPC jurisprudence regardless of stated BNS
support. The IPC↔BNS mapping work in this project (149 entries
across four batches) functions as scaffolding for the wave that
hasn't yet arrived; it is not currently retrieval-augmentation
surface for an existing BNS docket.

The full empirical write-up — methodology, year-by-year breakdown,
limitations, predictions for the next snapshot, and project
implications — lives in
[`docs/findings/2026-04-26_bns_at_sc_empirical.md`](findings/2026-04-26_bns_at_sc_empirical.md).
Re-runs in October 2026 and April 2027 are scheduled to track the
adoption curve as 2025-vintage prosecutions reach the SC bench.

Verification status: Direct empirical observation from the project's
own corpus inventory. Numbers reproducible via
`python scripts/inventory_corpus.py`.

## 9. CrPC → BNSS: substantive procedural shifts to track

The procedural-code mapping (CrPC 1973 → BNSS 2023) is a structurally
different exercise from IPC → BNS. Most of CrPC carries forward in
BNSS as renumbering with substantive frameworks intact, but four
procedural shifts are doctrinally consequential and worth flagging
for any retrieval system trained on pre-2024 procedural jurisprudence.

**Default-bail timeline grid (CrPC 167(2) → BNSS 187(3)).** This is
the highest-stakes single procedural mapping in the entire transition.
Under CrPC 167(2), an accused becomes entitled to bail if the
chargesheet is not filed within 60 days (offences punishable with up
to 10 years) or 90 days (offences punishable with death/life/10+
years). The Sanjay Dutt → Bikramjit Singh → Sanjay Kumar Agarwal line
of jurisprudence rests on this section. BNSS 187 carries the
framework forward but is widely understood to introduce a new
extended ceiling (up to 180 days) for organised-crime and
terrorist-act offences (corresponding to BNS 111 and BNS 113, both
new-in-BNS substantive offences). Whether this extension lives within
187 itself or in a parallel BNSS provision needs Gazette
verification. The mapping flags both 167 and 167(2) as
``needs_verification: true``.

**Anticipatory bail (CrPC 438 → BNSS 482) — note the number
collision.** CrPC 438 (the Sushila Aggarwal Constitution Bench
framework) maps to BNSS 482. This is unrelated to CrPC 482 (HC
inherent powers, → BNSS 528). Whether BNSS 482 narrows the scope of
anticipatory bail with explicit offence-category exclusions — and how
the Sushila Aggarwal limits-of-pre-arrest-bail framework re-applies
under BNSS 482 — is contested in scholarship and unresolved at the
SC level. The test suite at `tests/test_crpc_bnss_mapping.py::
test_482_does_not_alias_to_482` guards against autocomplete or
copy-paste edits that would silently introduce the wrong mapping.

**Inherent powers of the High Court (CrPC 482 → BNSS 528).** The
most-cited procedural section in the corpus (345 of 4,135 CrPC
citations, rank 1 by a wide margin). Quash-petition jurisprudence
hangs entirely on this section. BNSS 528 retains the three classical
limbs (give effect to any order under the Sanhita / prevent abuse of
process / secure the ends of justice) verbatim. Whether the BNSS
introduces any subtle scope limits — e.g., an explicit non-quashable
list for serious offences — is the verification question.

**Arnesh Kumar arrest-protection regime (CrPC 41/41A → BNSS 35/35(7)).**
CrPC 41A was inserted after Arnesh Kumar v State of Bihar (2014) to
codify the notice-instead-of-arrest framework for offences punishable
with imprisonment of seven years or less. The compliance regime
(mandatory case-diary entries, magisterial scrutiny, recorded reasons
for departing from notice) is heavily-cited current procedural-
protection jurisprudence. Whether BNSS folds 41A into a sub-section
of 35 (i.e. 35(7)) or retains it as a free-standing 35A is the
verification question — recall is approximately 35(7) but uncertain.

**Police statements (CrPC 161 → BNSS 180): substantive enhancement.**
Beyond the renumbering, BNSS 180 is reported to introduce mandatory
audio-video recording of statements taken under the police-statement
provision in offences punishable with seven-plus years' imprisonment.
This is a substantive evidentiary upgrade: a defective or absent
recording becomes a new possible vector for challenging admissibility
or fairness of investigation. The 162 bar on use of police statements
(→ BNSS 181) is otherwise carried forward.

**New in BNSS (no CrPC predecessor).** Two procedural innovations
appear on the new-in-BNSS side and warrant explicit mention. First,
BNSS introduces a formal **trial-in-absentia** framework for
proclaimed offenders (used together with BNSS 84 / CrPC 82
proclamation procedure). Pre-BNSS criminal trials required the
accused's presence with limited exceptions; BNSS codifies an explicit
trial-in-absentia mechanism. Second, BNSS makes **electronic /
video-conferencing trial proceedings** a default option subject to
court direction, rather than the limited exception they were under
CrPC. Both are doctrinally consequential and worth tracking in
future SC engagement.

**Empirical observation — plea bargaining is invisible at SC.** The
1,579-doc corpus inventory shows that CrPC 265A-265L (the plea
bargaining provisions inserted by the Code of Criminal Procedure
(Amendment) Act, 2005) do not appear in the top-50 cited sections,
nor any of them in the top-100. This suggests limited apex-level
engagement with the plea-bargaining framework despite its 18-year
availability — an empirical signature of how rarely the SC takes up
plea-bargaining questions on appeal. BNSS retains the plea bargaining
chapter with renumbering (290-300, pending exact verification).
Whether SC engagement with plea bargaining will increase under BNSS
is an empirical question for future corpus snapshots, but the
baseline going in is that the framework runs almost entirely in
trial courts and rarely reaches the apex docket.

Verification status: All six CrPC → BNSS mappings flagged in this
finding carry ``needs_verification: true`` in
`data/mappings/crpc_bnss_mapping.yaml`, reflecting that the entire
table was built from MHA Comparative Table recall rather than against
the enacted Gazette text. The substantive-shift claims above are
sourced to PRS India's analytical note and standard practitioner
references; sub-section indices in particular need a line-by-line
cross-check.

### Empirical pattern: systematic chapter-shift produces predictable section-number collisions

The CrPC→BNSS renumbering is not random; it's a structural insertion
of new chapters that systematically pushes existing sections down by
+20 positions (investigation chapter: CrPC 153–176 → BNSS 173–196)
or +40-46 positions (appellate/bail/inherent-powers: CrPC 397/438/482
→ BNSS 438/482/528). Ten section-number collisions were detected in
our 67-entry mapping table — every one of them is the natural
consequence of this shift, not a typo.

Practical implication: a practitioner saying "Section 482" in 2026+
must specify CrPC 482 (HC inherent powers, doctrine carrier) or BNSS
482 (anticipatory bail). The same number now denotes wholly unrelated
provisions. Any legal-NLP system that doesn't disambiguate by code
will silently misroute reasoning. Our mapping schema (separate
crpc_section / bnss_sections fields) preserves the disambiguation;
free-text retrieval over corpus that conflates "Section 482" citations
will not.

---

## Next additions to this notebook (not yet written)

- Minimum-sentence upward drift across BNS (304, 316, 376 — flagged in
  respective mapping notes).
- New-in-BNS offences: organised crime (111), terrorist act (113), mob
  lynching (103(2)), hit-and-run (106(2)), and the digital-impersonation
  adjunct to cheating (319). Each is a first-order shift in the
  prosecutorial surface area, not a renumbering.
- BNS's introduction of community service as an alternative punishment
  (notably BNS 356 for defamation) — first time in Indian criminal law.
