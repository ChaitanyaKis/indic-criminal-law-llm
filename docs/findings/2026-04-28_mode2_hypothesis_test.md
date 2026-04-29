# Mode-2 prompt-engineering hypothesis test (preliminary)

Tests the hypothesis recorded in
[`2026-04-28_hallucination_signal.md`](2026-04-28_hallucination_signal.md):
removing the "Chunk N:" ordinal preamble from the RAG prompt format
may eliminate the index-as-id collapse pattern (Mode 2), where the
model emits chunk ordinals (1, 2, 3, 4) as fabricated doc_ids.

## Setup

| Parameter | Value |
|---|---|
| Query | "What is anticipatory bail under Section 438?" |
| Top-k | 10 |
| Temperature | 0.0 |
| ThinkingConfig | thinking_budget=0 (disabled) |
| Model | gemini-2.5-flash |
| Corpus | 56,603 chunks (full) |
| Trials per arm | 5 |
| Runs collected | 2026-04-29 (single session) |

## The two prompt formats

**Control (`numbered`, current default):**

```
RETRIEVED CHUNKS:

--- Chunk 1 (doc_id: 199112586, year: 2023, score: 0.719) ---
Title: Ritu Chhabaria vs Union Of India ...
{chunk text}

--- Chunk 2 (doc_id: 88760594, year: 2020, score: 0.716) ---
...
```

The chunk ordinal sits adjacent to the doc_id, both as numerals.
Suspect for the index-as-id attention collapse documented in the
previous finding.

**Treatment (`id_only`, new):**

```
RETRIEVED CHUNKS:

[doc_id: 199112586] (year: 2023, score: 0.719)
Title: Ritu Chhabaria vs Union Of India ...
{chunk text}

---

[doc_id: 88760594] (year: 2020, score: 0.716)
...
```

No ordinal numbering. Doc_id is the only identifier. Chunks separated
by horizontal rule.

## Results

| Format | Run | cited | valid | hallucinated | hallucinated_ids | Mode |
|---|---:|---:|---:|---:|---|---|
| numbered | 1 | 4 | 4 | 0 | [] | clean |
| numbered | 2 | 4 | 4 | 0 | [] | clean |
| numbered | 3 | 4 | 4 | 0 | [] | clean |
| numbered | 4 | 4 | 4 | 0 | [] | clean |
| numbered | 5 | 4 | 4 | 0 | [] | clean |
| id_only  | 1 | 3 | 3 | 0 | [] | clean |
| id_only  | 2 | 3 | 3 | 0 | [] | clean |
| id_only  | 3 | 3 | 3 | 0 | [] | clean |
| id_only  | 4 | 3 | 3 | 0 | [] | clean |
| id_only  | 5 | 3 | 3 | 0 | [] | clean |

## Comparison

| Metric | numbered | id_only |
|---|---:|---:|
| Total citations | 20 | 15 |
| Valid | 20 | 15 |
| Hallucinated | 0 | 0 |
| Hallucination rate | 0.0% | 0.0% |
| Mode 1 occurrences | 0 / 5 | 0 / 5 |
| Mode 2 occurrences | 0 / 5 | 0 / 5 |

## Verdict: **inconclusive (statistical fluke)**

Both formats produced zero hallucinations across all 10 trials.
Neither Mode 1 (the stable `40496296` fabrication seen yesterday)
nor Mode 2 (chunk-ordinal collapse) fired in any run today. We
**cannot test the hypothesis** because the baseline failure mode is
not reproducing on this query at this point in time.

This null result has two compatible explanations:

1. **The hypothesis may be true.** id_only could in fact eliminate
   Mode 2 — but we cannot tell because Mode 2 didn't fire even in the
   numbered control today. We need a setup where Mode 2 reliably
   fires under control conditions before any treatment effect is
   visible.

2. **Gemini's serving-infra variability** (documented in
   [Finding #11](../bns_transition_findings.md#11-citation-verifier-was-silently-buggy-llm-hallucination-rate-is-measurable))
   has shifted between yesterday and today. Yesterday's session
   produced 4 stable Mode-1 fabrications + 1 Mode-2 collapse on this
   exact query at top-k=10. Today the same query at top-k=10 produces
   5 clean runs. The variability is in Gemini's infrastructure, not
   in our code (the corpus, retriever, and embeddings are byte-
   identical between sessions).

## One observable difference (not a hallucination signal)

The two formats produce different *citation counts* even when both
are clean:

- `numbered` cites **4 doc_ids** consistently across all 5 runs
- `id_only` cites **3 doc_ids** consistently across all 5 runs

Same retrieval, same model, same temperature, different prompt
format. The id_only format yields slightly more conservative
citation behaviour. This isn't directly relevant to the Mode-2
hypothesis (which is about hallucinations, not citation count) but
is a real format-induced behavioural difference worth tracking in
the planned formal study.

## Recommendation: do not change the default

The current `numbered` format is in commit history and ships clean
results today. Five-run samples per arm are too small to:

- Distinguish a real treatment effect from time-of-day Gemini
  variability
- Confirm that id_only never produces Mode 2 (proving a negative
  requires more samples)
- Quantify the `4 vs 3 citations` behavioural difference's impact on
  answer quality

Default stays `numbered` until the formal 10×10 study (or larger)
gives a defensible signal. The new `id_only` format is now available
as an opt-in via `--prompt-format id_only` for future experiments.

## What to do next (recorded for later session)

1. **Reproduce yesterday's Mode 1/2 conditions first.** Find a query
   that reliably produces hallucinations under the numbered control
   today. Without a reproducing baseline, no treatment effect can be
   measured. Candidates: queries where retrieval is weaker (low top-k
   scores), queries on doctrinally-thin topics, queries with
   ambiguous phrasing.

2. **Then run the comparison.** With a reproducing baseline, run 10
   queries × 10 runs = 100 observations per arm. Pre-register the
   hypothesis (id_only reduces Mode 2 occurrences by ≥X percentage
   points) so the post-hoc bias is bounded.

3. **Track the `4 vs 3` citation-count difference separately.**
   id_only's apparent conservatism could either be a feature (fewer
   weakly-supported citations) or a bug (the model sees fewer
   distinct chunks because the format is less salient). Worth a
   side-experiment.

The Mode-2 prompt-engineering hypothesis remains officially
untested. The infrastructure to test it is now in place.

## Side observation — session-level non-determinism in Gemini 2.5 Flash

Yesterday's 5-run smoke test on this exact query produced 4
stable-fabrication hallucinations (Mode 1) and 1 index-as-id
collapse (Mode 2). Today's 5 runs on the same query, same
prompt format, same temperature=0, same model, produced 0
hallucinations.

Within-session variability (4-then-1 yesterday) was already
documented in Finding #11. Today's between-session shift from
5/5 hallucinations to 0/5 demonstrates a larger effect: Gemini
2.5 Flash's serving infrastructure produces materially different
behavior across sessions even with deterministic-seeming inputs.

Methodological implication: any RAG hallucination measurement
must aggregate across sessions, not just runs within a session.
A single-day measurement could over- or under-estimate true
hallucination rate depending on which serving-infra state the
session caught. The proper measurement study (planned in
[`2026-04-28_hallucination_signal.md`](2026-04-28_hallucination_signal.md))
should run across at least 3 different days at different times
of day to bound this variability.

This finding strengthens the case for citation verification as
a deployment requirement, not an audit luxury: a system that
sometimes hallucinates 50% and sometimes hallucinates 0% on the
same query needs runtime guards, because users will not see the
"sometimes 0%" runs as the trustworthy ones — they will see
their specific session's behavior.

## Side observation — citation density differs by prompt format

Even with both arms clean, ``numbered`` format consistently cited
4 doc_ids per run; ``id_only`` consistently cited 3. Same
retrieval, same model — a real prompt-format behavioral effect on
citation density. Direction unclear without a quality metric
(more citations could mean either better grounding or spurious
additions). Worth tracking in the formal measurement study.
