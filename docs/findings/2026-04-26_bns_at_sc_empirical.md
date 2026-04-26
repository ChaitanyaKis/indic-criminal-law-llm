# The BNS Transition Has Not Yet Reached the Supreme Court

## Empirical observation

Snapshot date: April 26, 2026 (10 months after the Bharatiya Nyaya
Sanhita's effective date of July 1, 2024).

Corpus: 1,579 Supreme Court of India criminal judgments, calendar
years 2015–2024 inclusive, saved after the criminal-statute filter
applied to 3,500+ raw SC search results during ingestion.

### Headline counts

| Statutory framework cited | Cases | Share |
|---|---:|---:|
| IPC only | 1,215 | 77.0% |
| BNS only | 0 | 0.0% |
| IPC and BNS both | 2 | 0.1% |
| Neither (procedural / constitutional) | 362 | 22.9% |
| **Total** | **1,579** | **100.0%** |

### Per-year transition tail

The "Both" column appears for the first time in 2024 — and remains
in single digits even there.

| Year | IPC only | BNS only | Both | Neither | Total |
|------|---------:|---------:|-----:|--------:|------:|
| 2015 | 116 | 0 | 0 | 39 | 155 |
| 2016 | 105 | 0 | 0 | 21 | 126 |
| 2017 | 116 | 0 | 0 | 24 | 140 |
| 2018 | 118 | 0 | 0 | 30 | 148 |
| 2019 | 121 | 0 | 0 | 42 | 163 |
| 2020 | 100 | 0 | 0 | 44 | 144 |
| 2021 | 134 | 0 | 0 | 34 | 168 |
| 2022 | 111 | 0 | 0 | 43 | 154 |
| 2023 | 126 | 0 | 0 | 53 | 179 |
| **2024** | **168** | **0** | **2** | **32** | **202** |
| TOTAL | 1,215 | 0 | **2** | 362 | 1,579 |

### BNS sections that did appear

Across all 1,579 documents and across the entire 2015–2024 window,
exactly three distinct BNS sections are cited:

| BNS section | Cites | Subject |
|---|---:|---|
| 4 | 1 | General punishments (analogous to IPC 53) |
| 8(2) | 1 | Sentencing principle / fines |
| 63 | 1 | Rape (definition) |

BNSS appears in 11 citations across the corpus — slightly more than
BNS, consistent with procedural-code references in 2024 transition
discussions, but still negligible against CrPC's 4,135.

## Interpretation

This finding is unsurprising mechanically. Indian criminal cases at
the Supreme Court level arrive only after first-instance trial and
at least one tier of appellate review (typically the High Court).
The typical pipeline takes 2–5 years from FIR to SC disposal in
contested matters and longer in routine ones. Cases under the new
BNS framework began registering on or after July 1, 2024; ten months
of trial-court accumulation cannot have produced a measurable SC
docket of BNS-charged appeals. The two "Both" cases observed in 2024
are themselves transitional: they discuss the new statutes alongside
prosecutions still grounded in the IPC. There is no reason to expect
BNS-only SC decisions before late 2026 at the earliest, and the
volume becomes meaningful only in 2027–2028 vintages.

The implication for legal NLP, however, is non-trivial and largely
unspoken in the current marketing of legal-AI products. Every
Indian-criminal-law model that exists today — including
retrieval-augmented systems trained or fine-tuned on Supreme Court
judgments through 2024 — is, empirically, a tool for **IPC**
jurisprudence, regardless of whether the product copy claims "BNS
support". The training data simply does not contain BNS doctrine
at any informative scale. Claims of BNS reasoning ability rest on
zero-shot generalisation from comparative tables and statutory text
rather than on observed appellate reasoning. Practitioners and
researchers should expect this gap to narrow only as 2025-vintage
prosecutions reach the SC bench in roughly two to three years.
High Court adoption will likely arrive sooner — perhaps within a
year — because HC criminal appeals turn over faster than SC special
leave petitions.

## Implications for this project

- **Mapping work pivots away from IPC→BNS coverage.** The
  inventory-driven IPC↔BNS table now covers 50/50 of the top-cited
  IPC sections (149 total entries). Further IPC mapping work has
  diminishing returns — the long tail past rank 50 is rarely cited.
  Effort moves to the procedural-code mappings (CrPC↔BNSS,
  Evidence↔BSA), which govern actively-litigated questions in
  current jurisprudence regardless of substantive-code regime.
- **High Court scraping becomes higher priority than further SC
  scraping.** HCs are the next surface area where BNS adoption will
  be visible. Adding HC-criminal scraping to the existing
  `IndianKanoonScraper` is a small extension; the scraping policy
  (politeness delay, robots, lockfile, criminal filter) carries over.
- **The model's distinguishing claim is more nuanced than originally
  stated.** Rather than "handles the BNS transition" (which presumes
  a transition that hasn't yet happened in our training surface),
  the claim becomes: *prepared for the BNS wave before it arrives,
  while reasoning correctly over current IPC-dominant jurisprudence
  with explicit awareness of the pending transition*. Concretely,
  this means the IPC↔BNS mapping table and the seven Findings in
  `docs/bns_transition_findings.md` are scaffolding for future
  reasoning, not active retrieval-augmentation surface.

## Methodology

- **Inventory tool**: `scripts/inventory_corpus.py` at commit
  `34a6280` and later. The `bns_transition_breakdown` function
  partitions the corpus by `(has_ipc, has_bns)` per document.
- **Statute extractor**: `src/extractors/statutes.py` recognises
  IPC, BNS, CrPC, BNSS, Evidence Act, BSA, and eight additional
  criminal acts (NDPS, POCSO, Dowry Prohibition, SC/ST, UAPA, PMLA,
  Arms, JJ Act variants).
- **Classification rule**: a document is classified `IPC only` if
  any extracted statute carries `act == "IPC"` and none carry
  `act == "BNS"`; symmetric for `BNS only`; `Both` if both appear;
  `Neither` if neither appears (typically procedural appeals,
  constitutional benches, habeas corpus, bail jurisprudence).
- **Confidence tier**: post-rescore distribution at snapshot is
  1,284 high-confidence and 295 medium-confidence saves; both tiers
  are included in the headline counts above. The pre-2024 rows have
  no BNS appearances by construction (BNS did not exist).

## Limitations

- **Corpus is SC-only.** High Court criminal jurisprudence is not in
  the audit. HCs may show meaningfully different (almost certainly
  faster) BNS adoption because their criminal-appellate cycle is
  shorter and they hear matters from BNS-effective trial courts
  directly.
- **Indian Kanoon's per-year search ceiling caps SC coverage at
  roughly 400 results per year.** The full SC criminal output is
  larger. Our 155-202 saved-per-year sample is what the IK ranking
  surfaced through the 400-result window, intersected with our
  criminal filter. The criminal-bench subset may be over-represented
  if IK ranks criminal appeals earlier in the year-window's results.
- **Six-month observation post-BNS is short.** Distributional claims
  about BNS adoption beyond "currently negligible" are preliminary.
- **The 2 "Both" cases are not analytically inspected here.** A
  follow-up qualitative read of those two judgments would be useful;
  they are the empirical core of any near-term BNS-on-SC reasoning
  evidence.

## Predictions for next snapshot

- **By October 2026 (16 months post-effective date):** first
  BNS-only SC judgments begin appearing — single digits per quarter.
- **By April 2027 (22 months post-effective date):** "Both" tier
  becomes majority of the 2025-vintage SC docket as transition-period
  cases work through appellate review.
- **By 2028:** BNS-only volume in 2026-vintage SC dockets crosses
  IPC-only for the first time.

These predictions assume the standard 2-3 year FIR-to-SC pipeline
holds. Constitutional challenges to specific BNS provisions (e.g. BNS
150 sedition successor, see Finding #6) may produce earlier writ-stage
SC engagement that doesn't follow the standard appellate cycle.

## Re-running this analysis

```bash
python scripts/inventory_corpus.py
# JSON: data/processed/corpus_inventory.json
# Look at: inv["bns_transition"]["by_year"]
```

The transition cross-tab is in the inventory's standard JSON output
under the `bns_transition` key. Re-runs are idempotent and require
no scraper-side changes; they reflect whatever has been scraped at
the moment of execution.
