# Statute mappings

Structured, human-auditable data for the IPC → BNS / CrPC → BNSS / Evidence
Act → BSA transitions of 1 July 2024. Consumed by `src/mapping/*.py`.

## Files

| File                      | Covers                              | Status              |
|---------------------------|-------------------------------------|---------------------|
| `ipc_bns_mapping.yaml`    | Indian Penal Code → BNS, 2023       | Seed (Week 2, ~60 entries) |
| `crpc_bnss_mapping.yaml`  | CrPC → BNSS, 2023                   | Not yet written     |
| `evidence_bsa_mapping.yaml` | Evidence Act → BSA, 2023          | Not yet written     |

## Source hierarchy

Every mapping entry should trace back to, in order of preference:

1. **MHA Comparative Table** published with the BNS / BNSS / BSA Bills, 2023
   (tabled in Parliament alongside the Bills; the most authoritative side-by-side
   the Government itself has produced).
2. **PRS India legislative briefs** — `prsindia.org/billtrack/the-bharatiya-*`.
   Independent, well-cited, cross-checked against the enacted text.
3. **Standing Committee on Home Affairs report** on the BNS Bill (2023)
   — flags legislative intent where the text is ambiguous.
4. **Enacted BNS, BNSS, BSA text** as published in the Gazette of India
   (for sub-section-level precision only).

Secondary commentary (law firm newsletters, blog posts, academic articles)
may be used for context but **must not** be the sole authority for any
mapping entry.

## Verification status

Each entry carries an optional `needs_verification: true` flag. This means:

> The relationship at the main-section level is correct, but the sub-section
> index (e.g., `103(1)` vs `103(2)`) has not been cross-checked against the
> enacted text line-by-line. Treat the sub-section as a best-available guess
> until a human reviewer has verified it.

Absence of the flag means both the section-level and sub-section-level
mapping have been verified against at least one primary source above.

**As of the Week 2 seed, ~25 of ~60 entries carry `needs_verification: true`,
almost all for sub-section-index precision rather than section-level
correctness.** These should be resolved before the model is trained on
enriched citation data.

## Contributing corrections

Corrections are high-value. Open a PR against the YAML with:

- **Before / after** of the entry.
- **Source** (link to PRS brief, paragraph of the MHA table, or Gazette
  section number) — corrections citing only secondary commentary will
  not be merged.
- If the correction removes `needs_verification: true`, state which
  primary source was checked.

## Schema (enforced by `src/mapping/ipc_bns.py`)

```yaml
version: "0.1"                 # mapping-file version (bump on schema change)
source: "..."                  # top-level provenance string
last_verified: "YYYY-MM-DD"    # date the file was last cross-checked

mappings:
  - ipc: "302"                 # IPC section id (string; or null for new_in_bns)
    bns: ["103(1)"]            # list of BNS section ids; [] if removed
    relationship: one_to_one   # one_to_one | one_to_many | many_to_one
                               # | removed | new_in_bns
    subject: "Murder"          # canonical subject name (human query key)
    ipc_title: "..."           # section heading in the IPC
    bns_title: "..."           # section heading in the BNS (or null)
    notes: null                # semantic changes, edge cases; string or null
    needs_verification: true   # optional; defaults to false
```

## Out-of-scope (for now)

- Amendment history within the IPC (e.g., 376D-like additions by the 2013
  Criminal Law Amendment).
- State-law variations (Pondicherry, J&K pre-370 regime, etc.).
- Allied statutes with their own section numbering (NDPS, POCSO, PMLA).
  These retain their numbering post-2024 and do not need a mapping file.
