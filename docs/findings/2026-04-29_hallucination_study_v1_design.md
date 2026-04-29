# Hallucination Study v1 — Pre-registration

**Status:** committed before any runs are executed.
**Authoring date:** 2026-04-29.
**Lessons applied:** the April 28 null-result test
([`2026-04-28_mode2_hypothesis_test.md`](2026-04-28_mode2_hypothesis_test.md))
showed that single-query 5-run experiments can't distinguish a real
treatment effect from Gemini's session-to-session serving-infra
variability. This study is designed around that finding.

## What this study measures

This is an **exploratory measurement study** of Gemini 2.5 Flash's
hallucination behaviour on grounded RAG queries against the project's
1,579-doc Supreme Court criminal corpus. It is not a hypothesis test
between two systems — it produces the project's first reliable
hallucination-rate baseline, against which future measurements
(prompt-format experiments, retriever swaps, model upgrades) can be
compared.

The deliverable is a defensible baseline number — *"on grounded
Indian-criminal-law queries against this corpus, Gemini 2.5 Flash
hallucinates X% of citations, with mode breakdown M1, M2, M_novel"* —
that the paper can cite without footnoting "single-query, single-day,
N=5".

## Hypotheses (registered before runs)

**H₀ (null):** any-mode hallucination rate < 5% (consistent with a
polished commercial RAG system).

**H₁ (alternative):** any-mode hallucination rate ≥ 5%.

**Decision rule:** reject H₀ with strong evidence iff the observed
rate exceeds **10%** AND the lower bound of the 95% Wilson confidence
interval exceeds **5%**. The two-threshold rule prevents weak
borderline rejections.

## Pre-registered interpretation thresholds

| Observed rate | Interpretation |
|---|---|
| < 5% | Verifier may be over-engineering for current Gemini behaviour. Low-priority feature for product. |
| 5%–10% | Verifier is useful but not load-bearing. Borderline. |
| 10%–25% | Verifier is required for any deployable legal RAG. Strong evidence. |
| > 25% | Catastrophic; Gemini-2.5-Flash should not be the production generator without an additional grounding layer. |

## Secondary registered questions

1. **Does Mode 2 (index-as-id collapse) reproduce in this study?**
   If 0 occurrences across 100 runs, that's evidence Mode 2 is
   serving-state-specific (consistent with the April 28 finding). If
   it appears in even 1 run, we have the second clean reproduction.
2. **Does session affect rate significantly?** Test with chi-squared
   on the (session × hallucinated-yes/no) 2×2 contingency table.
   p < 0.05 → session-level variability is large enough to require
   multi-session aggregation as a methodological default.
3. **Does retrieval quality predict hallucination rate?** Look at
   per-query mean top-k score vs per-query hallucination rate;
   correlation coefficient with 95% CI. Pre-registered direction:
   **negative** (worse retrieval → more hallucination).

## Sample size justification

100 observations (10 queries × 10 runs) is the minimum that gives:

- **±10% Wilson half-width** for the overall any-mode rate at any
  observed value (the worst case is rate ≈ 50%, where Wilson 95% CI
  half-width = 9.8% at N=100). At N=50 the half-width climbs to 14%,
  too wide to distinguish 5% from 15%.
- **Per-query stability:** 10 runs per query is enough to see whether
  a query produces the same hallucination deterministically across
  runs (Mode 1 stable signature) or produces variable failures.
- **Two-session split:** 50 runs per session is enough to do
  chi-squared on session-level variability with reasonable power.

Larger N (say, 500+) would tighten CIs further, but at the cost of
~10× the API budget. 100 is the sweet spot for a v1.

## Query selection (locked)

10 queries chosen for stratified coverage. Selected before running.
Final list:

### Substantive criminal law (3 queries, high-frequency offences)

- **Q1**: "What is the procedure for default bail under Section 167(2) CrPC?"
- **Q2**: "What is anticipatory bail under Section 438?"
- **Q3**: "What did the Supreme Court hold about Section 498A IPC and arrest of relatives?"

### Procedural reasoning (3 queries, sub-section precision needed)

- **Q4**: "When can a Magistrate order further investigation under Section 173(8) CrPC?"
- **Q5**: "What is the inherent power of the High Court under Section 482 CrPC?"
- **Q6**: "When is sanction required under Section 197 CrPC for prosecuting a public servant?"

### Edge cases (2 queries, thin corpus coverage)

- **Q7**: "What are the bail conditions under UAPA?"
- **Q8**: "How should hostile witness testimony be appreciated?"

### BNS-transition (2 queries, directly tests project headline)

- **Q9**: "Has the Supreme Court ruled on any Bharatiya Nyaya Sanhita cases?"
- **Q10**: "How does BNS Section 103 differ from IPC 302?"

The Q7/Q8 edge cases test whether the model graceful-refuses ("the
retrieved context does not contain enough information") or
hallucinates to fill the gap. The Q9/Q10 BNS queries test the empty-
retrieval case directly — per the [BNS-at-SC empirical
finding](2026-04-26_bns_at_sc_empirical.md), the corpus contains 3
total BNS citations, so retrieval will be very weak for these
queries.

## Configuration (locked)

| Parameter | Value |
|---|---|
| Model | gemini-2.5-flash |
| Temperature | 0 |
| ThinkingConfig | thinking_budget=0 (disabled) |
| max_output_tokens | 1024 |
| Prompt format | `numbered` (current default; testing baseline, not treatment) |
| Top-k retrieval | 10 |
| Embedder | BGE-M3 |
| Corpus | 56,603 chunks (full SC criminal, 2015-2024) |
| Runs per query | 10 (split 5+5 across two sessions) |
| Min session gap | 1 hour wall-clock |
| Inter-run sleep | 5 seconds |

## Mode classification rules (auto, applied during run)

- `clean`: `invalid_citations == []`
- `mode_1_stable`: any invalid id matches `\d{7,}` (real Indian
  Kanoon-shaped) and is not in the retrieval set
- `mode_2_index`: any invalid id is a short integer 1–9 (chunk
  ordinal collapse)
- `novel`: invalid_citations exist but match neither pattern

If multiple modes apply to one run (e.g., one Mode-1 fabrication +
one Mode-2 ordinal), classify by the **most-novel** present (novel
> mode_2 > mode_1 > clean) and record the full breakdown in a
separate field. This biases toward surfacing unusual behaviour.

## Per-run logging schema

JSON-line written to `data/processed/hallucination_study_v1.jsonl`,
one line per run, atomic-append:

```json
{
  "run_id": "Q1__01",
  "query_id": "Q1",
  "query": "...",
  "run_number": 1,
  "session_id": "2026-04-29T10:30",
  "timestamp_iso": "...",
  "model": "gemini-2.5-flash",
  "temperature": 0,
  "thinking_disabled": true,
  "prompt_format": "numbered",
  "top_k": 10,
  "retrieval": {
    "chunks_returned": 10,
    "top_score": 0.xxx,
    "min_score": 0.xxx,
    "doc_ids_in_retrieval": [...]
  },
  "answer": {
    "text": "...",
    "completion_tokens": N,
    "finish_reason": "STOP",
    "cited_doc_ids": [...]
  },
  "verification": {
    "cited_count": N,
    "valid_count": N,
    "valid_citations": [...],
    "invalid_citations": [...],
    "all_valid": true,
    "hallucination_mode": "clean"
  },
  "errors": []
}
```

## Stopping rule and analysis discipline

1. **Run all 100 observations before peeking at any aggregate
   statistics.** Do not run 50, look, decide whether to run 50 more.
   This is the standard pre-registration discipline.
2. **The script is resumable.** `--resume` skips run_ids already in
   the JSONL. If a session is interrupted (network, API down), restart
   it; do not retry individual runs at decision time.
3. **Errors are recorded, not retried at the analysis stage.** If a
   run hits an API error, that run's `errors` list captures it. The
   analysis treats errored runs as missing data (excluded from the
   denominator), not as zero-hallucination passes.
4. **Analysis uses only the locked schema.** No post-hoc subsetting
   to find a more flattering rate. If we want to investigate
   sub-questions later, those are separate exploratory analyses,
   labelled as such.

## Aggregation and reporting

The analyzer produces:

- **Overall any-mode rate** with 95% Wilson CI.
- **Per-mode rate** (clean / mode_1 / mode_2 / novel) with CIs.
- **Per-query rate** with CI; query × mode contingency.
- **Session-level rate**; chi-squared on session × hallucinated-yes/no.
- **Retrieval-quality correlation:** per-query mean top-k score vs
  per-query rate, Pearson r and 95% CI.
- **Per-query stability:** count of distinct cited-doc-id sets across
  10 runs; lower = more stable.
- **"User-saved-by-verifier" tally:** runs where the answer carried
  ≥1 hallucinated citation that would have shipped without
  verification (= hallucinated-runs count).
- **Top-5 surprising findings** auto-flagged: queries with high
  variance, novel-mode runs, sessions with significantly different
  rates, etc.

Output goes to:
- `data/processed/hallucination_study_v1_analysis.json` (machine-readable)
- `docs/findings/2026-04-29_hallucination_study_v1_results.md` (paper-grade prose, written **after** runs complete; this design doc commits before any data is collected)

## What this study will NOT do

- Will not change any defaults regardless of result.
- Will not test prompt-format alternatives (`numbered` only — that's
  the locked control). The id_only follow-up is for a later study.
- Will not test other models or other retrievers. Single-system
  baseline.
- Will not retry hallucinated runs to see if they re-hallucinate.
  That's a separate study.

## Commitment

This document commits to git before any run is executed. The
analysis script and runner script are committed alongside it. The
JSONL data file and the results-prose doc remain uncommitted until
review of the final results.

The pre-registration is the contract: any departure from this plan
during analysis must be explicitly noted in the results doc as
"deviation from pre-registration."
