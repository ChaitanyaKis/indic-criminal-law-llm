# IPC↔BNS Mapping Verification Backlog

Status: 25 of 69 seed entries require legal review before being used in
training data or user-facing enrichment.

Source of truth: Enacted text of Bharatiya Nyaya Sanhita, 2023 (as
published in the Gazette of India). Cross-reference with MHA Comparative
Table and PRS India's analytical note.

## Entries requiring verification

Grouped by uncertainty type. Section-level identity is correct for all
rows below; the flag tracks sub-section-index precision, relationship
classification, or scope questions that need a primary-source check.

### Sub-section index precision (20 entries)

These map to a known BNS parent section; the parenthetical sub-section
index is the best-available guess pending a line-by-line read against the
enacted BNS.

| IPC Section | Proposed BNS | Relationship | Uncertainty | Priority |
|---|---|---|---|---|
| 323 | 115(2) | one_to_one | sub-section index (115(2) vs 115(3)) | high |
| 324 | 118(1) | one_to_one | sub-section index (118(1) vs 118(2)) | high |
| 325 | 117(2) | one_to_one | sub-section index (117(2) vs 117(3)) | high |
| 326 | 118(2) | one_to_one | sub-section index (118(2) vs 118(3)) | high |
| 420 | 318(4) | one_to_one | sub-section index (318(4) vs 318(2)) | high |
| 506 | 351(2) + 351(3) | one_to_many | which sub-sections carry basic vs aggravated | high |
| 141 | 189(1) | one_to_one | sub-section index | high |
| 143 | 189(2) | one_to_one | sub-section index | high |
| 147 | 191(2) | one_to_one | sub-section index | high |
| 376B | 67 | one_to_one | whether 67 or 68 carries separation-intercourse | medium |
| 376C | 68 | one_to_one | whether 67 or 68 carries authority-intercourse | medium |
| 390 | 309(1) | one_to_one | sub-section index | medium |
| 391 | 310(1) | one_to_one | sub-section index | medium |
| 392 | 309(4) | one_to_one | sub-section index | medium |
| 395 | 310(2) | one_to_one | sub-section index | medium |
| 396 | 310(3) | one_to_one | sub-section index | medium |
| 409 | 316(5) | one_to_one | sub-section index (316(4) vs 316(5)) | medium |
| 494 | 82(1) | one_to_one | sub-section index | medium |
| 495 | 82(2) | one_to_one | sub-section index | medium |
| 144 | 189(4) | one_to_one | sub-section index | medium |
| 146 | 191(1) | one_to_one | sub-section index | low |

### Relationship classification (1 entry)

| IPC Section | Proposed BNS | Relationship | Uncertainty | Priority |
|---|---|---|---|---|
| 380 | 305 | many_to_one | whether BNS 305 also absorbs IPC 381, 382 (is the consolidation scope as claimed?) | medium |

### Structural / definitional (1 entry)

| IPC Section | Proposed BNS | Relationship | Uncertainty | Priority |
|---|---|---|---|---|
| 351 | 130 | one_to_one | whether BNS 130 is a single section or has sub-parts (130(1), 130(2)); does the definition appear verbatim? | low |

### Scope drift — removed vs partial mapping (1 entry)

| IPC Section | Proposed BNS | Relationship | Uncertainty | Priority |
|---|---|---|---|---|
| 377 | (none) | removed | whether non-consensual acts against men / trans persons / bestiality get *any* BNS coverage, or the gap is real; awaits legislative amendment or SC clarification | low |

### New-in-BNS sub-section index (1 entry)

| IPC Section | Proposed BNS | Relationship | Uncertainty | Priority |
|---|---|---|---|---|
| — | 103(2) | new_in_bns | whether mob-lynching sits at 103(2) or a different sub-index of BNS 103 | medium |

## Verification protocol

1. Consult enacted BNS text (Gazette of India notification of the
   Bharatiya Nyaya Sanhita, 2023).
2. If the mapping holds, flip `needs_verification: false` on the YAML
   entry and add two fields:
   ```yaml
   verified_by: "<reviewer name or handle>"
   verified_on: "YYYY-MM-DD"
   ```
3. If the mapping is wrong, correct the `bns` list and either:
   - Keep `needs_verification: true` with updated `notes`, or
   - Re-classify (e.g. `one_to_one` → `one_to_many`) and re-flag.
4. If the section is genuinely ambiguous (e.g. IPC 377 scope question),
   document the ambiguity in `notes` and leave the flag raised. Do not
   force a mapping.

## Priority legend

- **high** — high-frequency prosecutions (property / hurt / intimidation /
  public order); errors here have large downstream blast radius on
  training data and model outputs.
- **medium** — meaningful volume or contested framing; verify before
  model training but not before corpus enrichment.
- **low** — rarely invoked or awaiting external (legislative / judicial)
  resolution.

## Out of scope for this backlog

- CrPC ↔ BNSS and Evidence Act ↔ BSA mappings — separate modules, built
  after the bulk judgment crawler is running.
- Amendment-chain history within the IPC (e.g. which sections were added
  by the 2013 Criminal Law Amendment).
- Allied statutes that retain their numbering post-2024 (NDPS, POCSO,
  PMLA) — no mapping needed.
