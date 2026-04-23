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
