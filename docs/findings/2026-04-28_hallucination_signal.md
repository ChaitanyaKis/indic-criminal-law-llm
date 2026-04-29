# Five-run hallucination signal — anticipatory bail query

Supplementary observation file for [Finding #11](../bns_transition_findings.md#11-citation-verifier-was-silently-buggy-llm-hallucination-rate-is-measurable).
Five repeated runs of the same RAG query, identical configuration, to
test whether Gemini 2.5 Flash hallucinates legal citations
deterministically or stochastically when temperature is fixed at 0.

## Setup

| Parameter | Value |
|---|---|
| Question | "What is anticipatory bail under Section 438?" |
| Model | gemini-2.5-flash |
| Temperature | 0.0 |
| ThinkingConfig | thinking_budget=0 (disabled) |
| max_output_tokens | 1024 |
| Retriever | BGE-M3 over 56,603-chunk full corpus, top-k=10 |
| Test driver | `tests/test_rag.py::test_rag_end_to_end_smoke_with_known_query` |
| Run dates | 2026-04-28 (all five runs in same session) |

## Results

| Run | cited | valid | hallucinated | hallucinated doc_ids |
|---:|---:|---:|---:|---|
| 1 | 3 | 2 | 1 | `40496296` |
| 2 | 3 | 2 | 1 | `40496296` |
| 3 | 3 | 2 | 1 | `40496296` |
| 4 | 3 | 2 | 1 | `40496296` |
| 5 | 4 | 0 | **4** | `1`, `2`, `3`, `4` |

## Two distinct failure modes

### Mode 1: Stable fabrication (deterministic, indistinguishable from real)

Observed in **4 of 5 runs**. Gemini cited two valid doc_ids plus the
same fabricated id `40496296` across four otherwise-identical runs.
The fabricated id has the syntactic shape of a genuine Indian Kanoon
document id — eight digits, no leading zero, the same format real
SC criminal-judgment ids carry. **A practitioner inspecting the
output cannot tell, by appearance alone, that `40496296` is fake.**
The model has internalised the *shape* of a valid citation and emits
plausible noise that satisfies it.

### Mode 2: Index-as-id collapse (catastrophic, but visible)

Observed in **1 of 5 runs** (run 5). The model broke entirely and
emitted `[doc_id: 1]`, `[doc_id: 2]`, `[doc_id: 3]`, `[doc_id: 4]` —
treating the chunk ordinals from the retrieval block of the prompt
("Chunk 1, Chunk 2…") as if they were the structured doc_id field
inside each chunk. All four citations were fabricated; none were
valid. This is qualitatively worse than Mode 1 in that it produces
*more* hallucinations per response, but qualitatively easier to
detect because the fabricated values are clearly not Indian Kanoon
ids — even a non-technical user would notice that real legal-case
references are not single digits.

### What would have shipped without citation verification

In **at least 4 of 5 runs**, the response would have shipped a fake
legal citation that a practitioner had no programmatic way to flag.
Mode 1 fabrications pass appearance-based review trivially. The fifth
run's Mode 2 collapse would likely have been caught by an attentive
human reader, but a busy practitioner skimming the citations might
not have checked. This is the empirical evidence that citation
verification is a *required* component of a legal RAG product, not
an optional feature.

## Non-determinism at temperature=0

Runs 1–4 were byte-for-byte identical. Run 5 diverged completely with
no parameter change between calls. This implies the variability is
not in our sampling code (we set temperature=0 and disabled thinking;
both runs went through the same prompt) but in **Gemini's serving
infrastructure** — possibly KV-cache state, batch composition, or
load-routing differences between two requests issued seconds apart.

The implication for reproducibility: any RAG benchmark that reports
"on this question, the model produces output X" with a single run is
making an unsupported claim. Even at temperature=0, the response is
not a single point estimate; it's a distribution with a heavy mode
(Mode 1, ~80% in this small sample) and a thin tail (Mode 2, ~20%).
Single-shot evaluation underestimates the variance.

## Mode 2 prompt-engineering hypothesis (untested)

The Mode-2 collapse may be a prompt-format artefact. Our retrieval
block presents chunks with a "--- Chunk 1 (doc_id: ...) ---" preamble
where the chunk number sits adjacent to the doc_id, both as numerals.
A model with a brittle attention pattern might occasionally extract
the chunk-ordinal token instead of the doc_id token when generating
citations.

**Hypothesis:** removing the "Chunk N" preamble from the user prompt
(presenting chunks only by their doc_id payload, with no separate
ordinal numbering) eliminates Mode 2 entirely. **Status: untested.**
This is a candidate follow-up experiment, not a claim. Testing
requires a clean before/after comparison with sufficient sample size
to distinguish a 1-in-5 mode from noise — naively, ≥30 runs per
condition. Documented here so the hypothesis isn't lost between
sessions.

## Planned measurement study

Proper quantification requires **10 queries × 10 runs = 100
observations minimum**, ideally diversified across:

- **Substantive sections**: IPC 302 (murder), IPC 498A (cruelty),
  IPC 376 (rape) — well-represented in corpus.
- **Procedural sections**: CrPC 167(2) (default bail), CrPC 438
  (anticipatory bail), CrPC 482 (inherent powers) — well-represented
  in corpus.
- **Edge cases**: questions with thin corpus coverage where retrieval
  is weak (likely to push the model toward unsupported fabrication).

Per query, capture: per-run cited count, valid/invalid split, the
fabricated-id list, and whether each run is Mode 1 (stable) or Mode 2
(collapse). With 100 data points we get separable estimates of:

- Per-query stable-hallucination rate
- Per-query collapse rate
- Whether retrieval-quality metrics (top-k score distribution,
  semantic-relevance signal) correlate with hallucination rate

Planned as a separate session. Designing the query set carefully and
pre-registering hypotheses matters more than running the harness
fast.
