# IndicCrimLawLLM — Master Plan

A project to build training data, infrastructure, and a specialised
language model for Indian criminal law, with explicit competence
across the IPC → BNS / CrPC → BNSS / Evidence Act → BSA transitions
that took effect on July 1, 2024.

This document is the canonical project plan. The shorter pitch lives
in [`README.md`](../README.md); week-by-week journals live in
[`journal/`](../journal/); empirical findings live in
[`docs/findings/`](findings/) and the running notebook of substantive
BNS-transition observations is at
[`docs/bns_transition_findings.md`](bns_transition_findings.md).

## Deliverables

The four deliverables stated in the README are reproduced here for
reference; this plan tracks status and contributions against them.

1. **IndicCrimCorpus** — a cleaned, deduplicated corpus of Indian
   criminal law text: bare acts, Supreme Court and High Court
   judgments, and commentary.
2. **IndicCrimLaw-7B** — a 7B-parameter open-weights model fine-tuned
   on the corpus, with explicit IPC↔BNS section-mapping competence.
3. **CrimBench-IN** — a benchmark suite covering statute recall,
   section-mapping, judgment-based QA, and applied reasoning problems.
4. **Tech report** — a public write-up of data sourcing, training
   recipe, evaluation results, limitations, and responsible-use
   guidance.

## Current status (April 2026, end of Week 1.5)

- **Corpus**: 1,579 SC criminal judgments scraped (2015–2024,
  full year coverage). Resumable lockfile-protected scraping
  pipeline. HC scraping not yet started.
- **Statute mapping**: 149 IPC↔BNS entries across four
  inventory-driven batches. Top-50 cited IPC sections covered
  100%. CrPC↔BNSS and Evidence↔BSA modules not yet started.
- **Inventory + diagnostics**: corpus inventory tool runs in ~2 min
  on the full corpus and surfaces quality flags and mapping gaps.
- **Embedding + RAG**: BGE-M3 embeddings, local-file Qdrant,
  retriever with metadata filters, generator with provider choice
  (Gemini / Groq / Claude), and citation verification. Pipeline is
  idempotent and resumable.
- **Findings**: 8 BNS-transition observations published, including
  today's empirical-at-SC finding (see Contribution #6 below).

## Novel Research Contributions

These are the project's distinguishing contributions to Indian
legal NLP. Each is grounded in code, data, or a published finding
in this repository.

1. **Citation-verified RAG for Indian criminal law.** Existing
   legal-AI tools claim "source-grounded answers"; few enforce it.
   This project's `src/rag/citation_verifier.py` extracts every
   `[doc_id: <id>]` reference from a generated answer and validates
   it against the retrieved-chunks set, deterministically catching
   hallucinated doc_id citations. The smoke tests at the embedding+RAG
   commit (093ded6) demonstrate calibrated refusal behaviour: the
   generator declines to answer questions whose retrieved context
   is insufficient rather than fabricating.

2. **The IndicCrimCorpus (SC tier).** 1,579 Supreme Court of India
   criminal judgments scanning 2015–2024, with per-judgment
   structured extraction across ten recognised statutes (IPC, BNS,
   CrPC, BNSS, Evidence Act, BSA, NDPS, POCSO, Dowry Prohibition,
   SC/ST). Built via a politeness-respecting scraper
   (`scripts/scrape_sc_criminal.py`) with rate-limit, robots.txt,
   atomic state, lockfile-coordinated multi-process safety, and
   SIGINT-clean shutdown. The scraping policy is intentionally
   conservative and reproducible.

3. **Inventory-driven IPC↔BNS section mapping.** 149 entries,
   four batches, prioritised by what the corpus actually cites.
   The schema captures relationship taxonomy
   (one_to_one / many_to_one / one_to_many / removed / new_in_bns),
   per-entry verification flags, source attribution, and explicit
   notes on consolidation points. Top-50 cited IPC sections in the
   corpus are 50/50 covered. Verification calibration is honest —
   84 of 149 entries (56%) are flagged `needs_verification: true`
   reflecting that the work was done from MHA Comparative Table
   recall rather than live Gazette access.

4. **Substantive scholarship on BNS transition semantics.** Eight
   findings in `docs/bns_transition_findings.md` covering scope
   expansions ("minor girl" → "child" in IPC 366A→BNS 95;
   "girl" → "girl or boy" in IPC 366B→BNS 96), orphan provisions
   (IPC 309 attempt-to-suicide post-Mental Healthcare Act 2017,
   IPC 367's "unnatural lust" limb), prosecutorial coverage gaps
   (IPC 370A's exploitation-of-trafficked-person provision narrowing
   under BNS 144), the sedition double-cloud (IPC 124A under
   *Vombatkere* stay AND BNS 150 scope contested in scholarship),
   and the abetment-chapter consolidation as the highest-volume
   compound-charge mapping shift in the entire transition.

5. **Inventory-driven corpus diagnostics.** `scripts/inventory_corpus.py`
   produces a structured snapshot of any state of the scraped
   corpus: top-N IPC/BNS section frequencies, mapping coverage in
   both directions, year-by-year transition cross-tabulation,
   bench-size and citation-network statistics, language detection,
   MinHash near-duplicate detection, and a quality-flag list. This
   tool drives every mapping-batch priority decision in the project,
   replacing intuition with frequency-grounded data.

6. **Empirical observation that BNS jurisprudence has not yet
   reached the Supreme Court of India as of mid-2026.**
   1,579-judgment audit shows 0 BNS-only citations and only 2
   transition cases out of 202 2024-vintage judgments. Establishes
   baseline for tracking BNS adoption curve in apex jurisprudence.
   Full write-up:
   [`docs/findings/2026-04-26_bns_at_sc_empirical.md`](findings/2026-04-26_bns_at_sc_empirical.md).

## Roadmap

### Near-term (Weeks 2–4)

- CrPC ↔ BNSS mapping module (procedural code, governs current
  jurisprudence regardless of substantive code).
- Evidence Act ↔ BSA mapping module.
- Add HC criminal scraping to `IndianKanoonScraper` with the same
  filter and lockfile contract — HC adoption will surface the BNS
  wave sooner than SC.
- Targeted backfill scrape for JJ Act cases (the historical
  filter false-negatives flagged in `docs/scraper_backlog.md`).
- Investigate the 3 near-duplicate pairs flagged in the latest
  inventory.

### Medium-term (Weeks 5–8)

- Define `CrimBench-IN` task suite: statute recall, section-mapping,
  judgment-based QA with citation requirements, applied
  hypothetical-reasoning problems.
- Begin training data preparation for `IndicCrimLaw-7B`.
- Rerun BNS-at-SC empirical analysis (October 2026 snapshot).

### Long-term (Weeks 9–12)

- Train and evaluate `IndicCrimLaw-7B`.
- Author technical report.
- Open-source release with model weights, training recipe, eval
  harness, and the corpus (subject to source-platform compliance).
