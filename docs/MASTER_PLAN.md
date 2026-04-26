# Indic Criminal Law LLM — Master Project Plan

> **Version:** 1.0 | **Start date:** Summer 2026 | **Duration:** 12 weeks | **Status:** Planning complete, ready to execute

---

## Current status (April 2026)

- **Corpus**: 1,579 Supreme Court criminal judgments scraped (2015–2024, full year coverage). Resumable lockfile-protected scraping pipeline. HC scraping not yet started.
- **Statute mapping**: **216 entries total** — 149 IPC↔BNS (four inventory-driven batches; top-50 cited IPC sections covered 100%) + 67 CrPC↔BNSS (Batch 5; v0 with 100% `needs_verification` pending Gazette cross-check). Evidence↔BSA module not yet started.
- **Findings**: **9** BNS-transition observations published in `docs/bns_transition_findings.md`, plus the standalone empirical write-up in `docs/findings/2026-04-26_bns_at_sc_empirical.md`.
- **Tests**: **106 passing** (1 pre-existing HF-Hub network flake on the embedder test, unrelated to mapping or scraper code).
- **Embedding + RAG stack** (citation-verified): wired but not yet run at full corpus scale; smoke-tested on 20 docs / 441 chunks.
- **Inventory diagnostics**: corpus inventory tool runs in ~2 min on the full corpus and produces a structured snapshot driving every mapping batch's priorities.

---

## 0. Locked Decisions

| Decision | Value |
|---|---|
| Domain | Indian criminal law (substantive + procedural + evidence) |
| Primary goal | Research paper + open-source release |
| Secondary goal | Portfolio artifact |
| Team | Solo |
| Duration | 12 weeks, full-time |
| Budget | ~$20 (RunPod emergencies) + free tiers + applied grants |
| License posture | Fully open — model, data, benchmark, code all public |

---

## 1. Mission Statement (one paragraph)

Build an open-source specialized language model for Indian criminal law reasoning that handles the IPC→BNS statutory transition as a first-class feature, maintains high citation fidelity against a verified case-law corpus, and supports Hindi-language legal queries. Release the model, a cleaned criminal law corpus, and a novel evaluation benchmark for Indian legal NLP, accompanied by a technical paper targeting a venue like the NLLP workshop at EMNLP or a direct arXiv preprint.

---

## 2. Scope — Critical Sub-scoping Within "Criminal Law"

"Criminal law broadly" is too vast for a 12-week solo project. Here is the principled scoping:

### IN SCOPE for V1

**Substantive criminal law**
- IPC 1860 (all 511 sections) — historical corpus
- BNS 2023 (all 358 sections) — current law
- IPC↔BNS mapping as an explicit model capability

**Procedural criminal law**
- CrPC 1973 — historical
- BNSS 2023 — current
- Focus areas: FIR, arrest, bail, charge, trial, appeal, limitation

**Evidence**
- Indian Evidence Act 1872 — historical
- Bharatiya Sakshya Adhiniyam 2023 — current
- Focus: admissibility, burden of proof, presumptions

**Case law coverage**
- Supreme Court criminal judgments: all available (~20K–30K)
- High Court criminal judgments from 10 courts (Bombay, Delhi, Madras, Calcutta, Allahabad, Karnataka, Kerala, Punjab & Haryana, Gujarat, Telangana): ~80K–120K
- Post-2010 emphasis for relevance; pre-2010 sampled strategically

### OUT OF SCOPE for V1 (reserve for V2)

- NDPS Act (narcotics) — huge, specialized, deserves own scope
- UAPA, PMLA — sensitive, political, specialized
- IT Act cybercrime provisions — specialized technical vocabulary
- Economic offences (SEBI, companies criminal) — regulatory overlap
- Military, juvenile justice special statutes
- State-specific criminal amendments

### Why this scope is defensible for a research paper

1. **BNS/IPC transition** is a natural, timely, under-studied NLP problem
2. Criminal law is **~60% of Indian case law volume** — largest single domain
3. Bail and arrest reasoning has **immediate social relevance** (undertrial population)
4. Procedural criminal law has **clean eval targets** (outcome labels, limitation calculations)
5. Multilingual angle is **strongest in criminal law** because FIRs are often in Hindi/regional languages

---

## 3. Novel Research Contributions (the paper angle)

The paper's claimed contributions — these must each be real and defensible:

1. **IndicCrimLaw-7B** — first open-source LLM specifically fine-tuned for Indian criminal law reasoning
2. **IndicCrimCorpus** — cleaned, deduplicated, metadata-enriched corpus of Indian criminal law (~20B tokens, publicly released)
3. **CrimBench-IN** — a novel evaluation benchmark covering:
   - Section identification and interpretation
   - IPC↔BNS mapping correctness
   - Citation fidelity (does the model invent cases?)
   - Procedural reasoning (bail, limitation, jurisdiction)
   - Multilingual criminal QA (Hindi↔English)
   - Multi-hop precedent reasoning
4. **Citation verification framework** — a retrieval-grounded post-processing method that reduces hallucinated citations by >X% (measured)
5. **Analysis of BNS transition failure modes** — empirical characterization of where pre-BNS-trained LLMs fail on post-BNS questions (nobody has published this)
6. **Empirical observation that BNS jurisprudence has not yet reached the Supreme Court** (April 2026 snapshot) — 1,579-judgment audit shows 0 BNS-only citations and only 2 transition cases through end-2024, ten months post-effective-date. Establishes baseline for tracking BNS adoption curve in apex jurisprudence. See `docs/findings/2026-04-26_bns_at_sc_empirical.md`.

---

## 4. Deliverables (what's public by end of week 12)

- [ ] **GitHub repository** (public, MIT license) with reproducible code, Docker, full README
- [ ] **IndicCrimCorpus dataset** on HuggingFace Hub with datasheet
- [ ] **IndicCrimLaw-7B model** on HuggingFace Hub with model card
- [ ] **CrimBench-IN benchmark** on HuggingFace Hub with leaderboard setup
- [ ] **Technical report / arXiv preprint** (8–12 pages)
- [ ] **Blog post** on HuggingFace or personal site, lawyer-accessible
- [ ] **Live demo** on HuggingFace Spaces (free CPU, with API fallback)
- [ ] **W&B public dashboard** with all training runs for full reproducibility

---

## 5. Compute & Resources Strategy

### Free-tier compute stack (the workhorses)

| Resource | Quota | Use for |
|---|---|---|
| Kaggle Notebooks | 30 hrs/week T4 or P100 | Main fine-tuning compute |
| Google Colab free | T4, ~12 hr sessions | Quick experiments, debugging |
| Hugging Face Spaces | Free CPU | Demo hosting |
| Hugging Face Hub | Unlimited public repos | Model + dataset hosting |
| Qdrant Cloud free | 1 GB cluster | Vector DB for RAG |
| Supabase free | 500 MB Postgres | Metadata, citations DB |
| GitHub | Unlimited public | Code, docs |
| Weights & Biases | Free academic | Experiment tracking |

### Free API tiers (for synthetic data generation and baselines)

| API | Use |
|---|---|
| Google AI Studio (Gemini) | Primary synthetic data generator — generous free tier |
| Groq | Fast inference on Llama/Mixtral for baselines |
| Together AI | $5 free on signup |
| Anthropic/OpenAI | Small new-user credits — save for gold-standard eval |

### Grants to apply for (Week 1, critical)

- [ ] **Google TRC** — free TPU v4 for research (sign.cloud.google.com/trc)
- [ ] **Hugging Face Community Grants** — Spaces GPU, Discord application
- [ ] **NVIDIA Inception** — framed as research startup
- [ ] **AI4Bharat collaboration email** — IIT Madras, most relevant group in India

### Paid backup ($20 budget)

- **RunPod spot A100** — $0.30–0.80/hr, for emergency training runs in weeks 7–9

### Student Pack (already earmarked)

- Azure $100 — only if the tenant issue resolves, else skip
- DigitalOcean $200 — reserve for Qdrant/API hosting if HF Spaces insufficient
- GitHub Copilot Pro — enable, use daily
- JetBrains PyCharm Pro — optional, VS Code + Cursor also fine

---

## 6. Data Pipeline

### Sources (tiered by priority)

**Tier 1 — must have (Weeks 1–2):**
- Indian Kanoon — primary source for all case law
  - SC criminal judgments 1950–present
  - Top-10 HC criminal judgments 2010–present
  - API available (~₹2K/month if needed) or respectful scraping with rate limits
- India Code (indiacode.nic.in) — IPC, BNS, CrPC, BNSS, Evidence Act, BSA
- Official BNS text from MHA / PRS India
- IPC↔BNS official mapping table (Gazette notification / MHA circular)

**Tier 2 — should have (Weeks 2–3):**
- Law Commission reports on criminal law (reports 41, 42, 47, 154, 156, 185, 213, 277, etc.)
- Parliamentary debates on BNS/BNSS/BSA bills (2023) — legislative intent gold
- NCRB annual reports — statistical grounding
- Supreme Court's own SUVAS-translated judgments (EN↔HI parallel data)

**Tier 3 — nice to have (Weeks 3–4):**
- Select District Court bail orders via eCourts (procedural variety)
- CBI court orders (special court jurisprudence)
- Selected textbook-style open content (only CC-licensed)

### Pipeline architecture

```
[Sources] → [Scraper] → [Raw storage] → [OCR/clean] → [Dedupe] →
[Parse + chunk] → [Metadata extract] → [Citation graph] →
[Embed] → [Vector DB] + [Structured DB] → [Consumed by RAG/Training]
```

### Cleaning steps (in order)

1. **OCR repair** for scanned PDFs (pre-2005 mostly) — use `marker` or `docTR`, not Tesseract
2. **Boilerplate removal** — headers, footers, page numbers, court stamps
3. **Deduplication** — MinHash LSH at document level + near-dup at chunk level
4. **Language detection** — tag Hindi vs English segments
5. **Semantic chunking** — ~500–1000 tokens, respect paragraph and section boundaries
6. **Citation extraction** — regex pass (CrLJ, SCC, AIR patterns) + LLM pass for edge cases
7. **Metadata extraction** — court, bench, date, case number, sections cited, outcome label, statutes invoked

### Storage schema (JSONL + Parquet)

```json
{
  "doc_id": "sc_2019_1234",
  "court": "Supreme Court of India",
  "bench": ["Justice X", "Justice Y"],
  "date": "2019-07-15",
  "case_number": "Cr.A. 456/2018",
  "title": "State of Maharashtra v. X",
  "statutes_cited": ["IPC 302", "IPC 34", "CrPC 161"],
  "cases_cited": ["doc_id_1", "doc_id_2"],
  "outcome": "appeal_dismissed",
  "language": "en",
  "text": "...",
  "chunks": [{"chunk_id": "...", "text": "...", "embedding_id": "..."}],
  "source_url": "https://indiankanoon.org/doc/...",
  "ingested_at": "2026-05-15T10:30:00Z"
}
```

### Target corpus stats (end of week 2)

- Documents: 100K–150K (SC + top-10 HC criminal)
- Tokens: 3–6 billion
- Size on disk: ~20–40 GB (text only)
- Embedded chunks: ~2–4 million
- Vector DB size: ~8–15 GB

---

## 7. Tech Stack (frozen)

### Core ML
- Python 3.11
- PyTorch 2.x
- Hugging Face `transformers`, `datasets`, `peft`, `accelerate`, `trl`
- `bitsandbytes` (4-bit quantization)
- **Unsloth** (primary fine-tuning framework — 2× speed, half VRAM)
- `sentence-transformers` (embeddings)

### RAG
- **LlamaIndex** (RAG orchestration)
- **Qdrant** (vector DB — cloud free tier + local Docker)
- **BGE-M3** (multilingual embedding model)
- **BGE-reranker-v2-m3** (reranking)
- BM25 via `rank_bm25` for hybrid retrieval

### Data engineering
- `polars` (fast dataframes)
- `datasketch` (MinHash dedup)
- `marker` or `docTR` (PDF/OCR)
- `spacy` + legal-NER models for entity extraction
- `ruff` for code hygiene

### Experiment tracking
- **Weights & Biases** (all runs logged)

### Serving
- **FastAPI** (backend)
- **Gradio** or **Streamlit** (demo UI)
- **Ollama** (local model serving for development)
- **vLLM** (if production inference needed)

### Orchestration
- **Docker** + docker-compose (reproducibility)
- **DVC** (optional, data version control)
- **Make** or `just` (task runner)

### Base models to try (ranked by priority)

1. **Qwen 2.5 7B** — strong multilingual, best starting point
2. **Llama 3.1 8B** — solid fallback, well-understood
3. **Sarvam-1** — Indic-native, test for Hindi capability
4. **Gemma 2 9B** — if license aligns with release plan

---

## 8. 12-Week Timeline (week-by-week)

### Week 1 — Foundations

**Inputs:** project plan (this doc), clean dev environment

**Do:**
- Set up GitHub org + repo structure
- Write and file all grant applications (TRC, HF, NVIDIA Inception, AI4Bharat email)
- Scrape 1,000 SC criminal judgments end-to-end as pipeline validation
- Build initial metadata schema, test on the 1K corpus
- Set up W&B project, Qdrant cloud, HF org

**Outputs:**
- Repo with scaffolding, CI, pre-commit hooks
- 1K cleaned SC judgments in JSONL
- First entry in running project journal
- All grant applications submitted

**Success criteria:** can re-run full pipeline on 1K docs in <1 hour

### Week 2 — Scale data pipeline

**Do:**
- Scale scraper to full SC criminal corpus (~20K–30K)
- Begin top-10 HC criminal scrape (background process, several days)
- Ingest bare acts (IPC, BNS, CrPC, BNSS, Evidence, BSA)
- Build IPC↔BNS mapping table as structured data
- OCR pipeline for pre-2005 scans

**Outputs:**
- Full SC criminal corpus (~25K docs)
- First 30K HC docs
- Statutes ingested with section-level granularity
- IPC↔BNS mapping JSON

**Success criteria:** retrieval over corpus returns relevant docs for 20 test queries

### Week 3 — RAG v1 baseline

**Do:**
- Embed full corpus with BGE-M3
- Index in Qdrant with proper metadata filters
- Build LlamaIndex retrieval pipeline: hybrid (dense + BM25) + rerank
- Wire Gemini (free tier) as generator
- Build 100-question eval set by hand (mix of easy/medium/hard)
- Run baseline eval, log all metrics to W&B

**Outputs:**
- Working RAG system, queryable via CLI and notebook
- 100-question eval with gold answers
- Baseline numbers: retrieval recall@10, citation precision, answer correctness

**Success criteria:** retrieval recall@10 > 0.75, answer correctness > 0.60

### Week 4 — RAG v2 refinements

**Do:**
- Add query decomposition for multi-hop questions
- Implement citation verification post-processing
- Add temporal filtering (pre/post July 1, 2024 for BNS)
- Add citation-graph traversal (retrieve cited-by chain)
- Rerun eval, compare to v1

**Outputs:**
- Improved RAG system with verified citations
- Ablation study of each addition (W&B report)
- Draft of first paper section: "RAG baseline and grounding"

**Success criteria:** citation precision > 0.90, answer correctness > 0.75

### Week 5 — Instruction dataset (synthesis phase)

**Do:**
- Design instruction taxonomy:
  - Section identification ("What does BNS 103 cover?")
  - Summarization ("Summarize the ratio in this judgment")
  - Precedent application ("Given facts X, find relevant precedents")
  - Drafting ("Draft a bail application for these facts")
  - IPC↔BNS conversion ("Convert this IPC-based FIR to BNS")
  - Multi-hop reasoning ("Cases where X was granted despite Y")
  - Procedural ("Is this appeal within limitation?")
- Generate 30K–50K synthetic (instruction, response) pairs using Gemini on your corpus
- Hand-curate 1,000 gold examples yourself (this is the most important work of the project)
- Seed with IndianBailJudgments-1200 and OpenNyAI datasets

**Outputs:**
- `instructions_v1.jsonl` with ~35K examples
- Schema-validated, deduplicated, quality-filtered
- 10% held out as test set (never trained on)

**Success criteria:** spot-check of 100 random examples shows >85% are coherent and legally correct

### Week 6 — Instruction dataset (filtering + hardening)

**Do:**
- Quality filtering pass: length, language consistency, citation validity
- Adversarial hard-negative generation: cases where obvious answer is wrong
- BNS↔IPC parallel pair generation (same facts, old vs new law)
- Hindi-language instruction subset (5K examples)
- Dataset card + datasheet

**Outputs:**
- `instructions_v2.jsonl` — filtered, ~30K high-quality examples
- Hindi subset — 5K examples
- Dataset published (private initially) on HF

**Success criteria:** dataset ready for training, datasheet complete

### Week 7 — Fine-tuning run 1 (Qwen 2.5 7B)

**Do:**
- QLoRA config on Qwen 2.5 7B
- Kaggle or RunPod spot A100 training
- ~8–12 hours per epoch, aim for 2 epochs
- Log everything to W&B
- Evaluate on held-out eval set + CrimBench-IN draft

**Outputs:**
- First trained model `IndicCrimLaw-7B-qwen-v1`
- W&B report with all metrics
- Paper draft: methods section

**Success criteria:** fine-tuned model beats base Qwen on CrimBench-IN by clear margin

### Week 8 — Fine-tuning run 2 + ablations

**Do:**
- Try Llama 3.1 8B for comparison
- Ablate: dataset size, LoRA rank, target modules, LR schedule
- 3–5 runs total, W&B tracks everything

**Outputs:**
- Best model identified, ablation table for paper
- Selected final architecture

**Success criteria:** have a clear best model with justified design decisions

### Week 9 — CrimBench-IN (the benchmark)

**Do:**
- Build the formal benchmark with 6–8 tasks:
  1. BNS↔IPC mapping (500 questions)
  2. Section interpretation (500 questions)
  3. Citation fidelity (200 prompts, measure hallucination rate)
  4. Procedural reasoning (300 questions — bail, limitation, jurisdiction)
  5. Multi-hop precedent (200 questions)
  6. Hindi criminal QA (300 questions)
  7. (Optional) Summarization with ROUGE-L
  8. (Optional) Drafting with human eval
- Run all baselines: Gemini, Claude, GPT-4, Llama base, Qwen base, your fine-tune, your fine-tune + RAG

**Outputs:**
- CrimBench-IN v1 published on HF
- Full baseline leaderboard
- Paper: results section with full tables

**Success criteria:** your model+RAG is #1 or #2 on the benchmark, clearly

### Week 10 — Paper draft + demo

**Do:**
- Full paper draft (introduction, related work, data, methods, results, discussion, limitations, ethics)
- Build HF Spaces demo with your model
- Gradio UI with example queries, comparison to base models
- Record 3-min video walkthrough

**Outputs:**
- Paper draft v1 (~8 pages)
- Live demo URL
- Demo video

**Success criteria:** paper is submission-ready, demo is shareable

### Week 11 — Polish + release prep

**Do:**
- Incorporate feedback (self-review, advisor review if any, AI4Bharat review if connection made)
- Final model card with limitations, intended use, safety considerations
- Blog post for lawyer audience (non-technical)
- Reproducibility audit: can someone clone and rerun?

**Outputs:**
- Polished repo with README, tutorials, notebooks
- Paper v2
- Blog post draft

**Success criteria:** another ML engineer could reproduce the project from the repo

### Week 12 — Ship

**Do:**
- Submit arXiv preprint (Monday)
- Post to HF with model card, dataset card, benchmark card
- Blog post published
- Reddit (r/MachineLearning, r/LawSchoolIndia), Twitter, Hacker News
- Direct outreach: AI4Bharat, CDS IISc, IIIT-D Precog, Ashoka legal NLP group
- Target: NLLP workshop submission if deadline aligns, else keep improving for next cycle

**Outputs:**
- Public release across all channels
- Launch thread with narrative

**Success criteria:** Project has meaningful traction (stars, forks, citations in first 4 weeks)

---

## 9. Evaluation — CrimBench-IN Design

This is the single most cited thing the project will produce. Design it rigorously.

### Task 1 — BNS↔IPC mapping
- Format: given an old IPC section and a fact pattern, identify the correct BNS section and vice versa
- 500 examples, 250 each direction
- Metric: exact-match section accuracy, partial credit for adjacent sections
- Source: MHA mapping table + hand-verified

### Task 2 — Section interpretation
- Format: given a section, answer factual/interpretive questions about it
- 500 examples across IPC, BNS, CrPC, BNSS, Evidence, BSA
- Metric: answer correctness (exact-match or rubric-based)

### Task 3 — Citation fidelity
- Format: open-ended prompts likely to elicit case citations
- 200 prompts
- Metric: precision and recall of citations against verified corpus (hallucinations = 0 score)
- **This is a novel metric we formalize**

### Task 4 — Procedural reasoning
- Sub-tasks: bail eligibility, limitation calculation, jurisdictional correctness, forum selection
- 300 examples
- Metric: accuracy on closed-form answers

### Task 5 — Multi-hop precedent reasoning
- Format: questions requiring reasoning across 2+ judgments
- 200 examples
- Metric: answer correctness + retrieval hop-accuracy

### Task 6 — Hindi criminal QA
- Format: Hindi question, expected answer in Hindi or English
- 300 examples
- Metric: answer correctness + language consistency

### Baselines to run
1. Gemini 1.5 Flash (free tier)
2. Gemini 1.5 Pro (paid, but free tier useful)
3. Claude Haiku (new-user credits)
4. GPT-4o-mini (new-user credits)
5. Qwen 2.5 7B base (no fine-tuning)
6. Llama 3.1 8B base
7. Indic-BERT, InLegalBERT where task applies
8. **Your model alone**
9. **Your model + RAG**

---

## 10. Paper Strategy

### Target venues (in priority order)

1. **NLLP workshop at EMNLP** — perfect fit, deadline typically July–August
2. **ACL/EMNLP/NAACL main** — if results are strong
3. **AACL** — Asian NLP venue, values regional work
4. **Direct arXiv preprint** — if timing misses all venues
5. **JMLR or TMLR** — if scope expands beyond workshop

### Paper outline (8–12 pages)

1. Introduction — the BNS transition problem, why Indian criminal law NLP matters
2. Related work — Indian legal NLP, domain-adapted LLMs, RAG for law
3. Data — IndicCrimCorpus construction and release
4. Methods — fine-tuning + RAG architecture, citation verification
5. CrimBench-IN — benchmark design
6. Experiments — all baselines, main results, ablations
7. Analysis — failure modes, especially BNS transition cases
8. Discussion — limitations, ethical considerations, legal accuracy caveats
9. Conclusion

---

## 11. Risks and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Scraping gets rate-limited or blocked | Medium | High | Use Indian Kanoon paid API (₹2K/mo) as backup; respect robots.txt; spread across weeks |
| OCR on old scans is poor | High | Medium | Use `marker`/`docTR` (transformer-based, much better than Tesseract); accept that pre-2005 corpus will have noise |
| Synthetic data is low quality | Medium | High | 1000 gold hand-curated examples + quality filters + spot-check protocol |
| Fine-tuning doesn't beat RAG baseline | Medium | High | This is a legitimate finding — write paper accordingly; try continued pretraining as fallback |
| Compute runs out mid-project | Low–Medium | High | Kaggle 30h/week + $20 RunPod buffer + TRC if approved; stay efficient (QLoRA, small ablations) |
| Scope creep into "all of criminal law" | High | High | This document is the anchor. Changes require explicit review. |
| Solo burnout | Medium | Very High | Weekly breaks mandatory. Public weekly journal enforces pacing. |
| Legal accuracy — model gives harmful advice | Always present | Critical | Strong disclaimers on demo; narrow framing as research tool; ethics section in paper |
| Paper rejected from target venue | Medium | Medium | arXiv preprint guaranteed; resubmission cycle built in |
| Indian Kanoon objects to redistribution | Low | High | Release corpus as scraper + list of URLs + cleaning scripts, not raw text dump. Judgments themselves are public domain (Copyright Act 52(1)(q)(iv)). |

---

## 12. First-48-Hours Kickoff Checklist

Do these in order. Do not skip ahead.

### Hour 0–2 — accounts & grants

- [ ] Create/confirm GitHub account with student verification active
- [ ] Apply to Google TRC — sign.cloud.google.com/trc — use abstract from this doc
- [ ] Apply to NVIDIA Inception (frame as research project)
- [ ] Email AI4Bharat (aihub@cse.iitm.ac.in or their contact) — one-paragraph intro + project abstract
- [ ] Sign up: Kaggle (verify phone for GPU), HuggingFace, Weights & Biases, Qdrant Cloud, Google AI Studio, Groq, RunPod
- [ ] Redeem GitHub Copilot Pro

### Hour 2–4 — repo scaffolding

- [ ] Create GitHub repo `indic-criminal-law-llm` (public, MIT, empty README)
- [ ] Local clone, Python 3.11 env, install base deps
- [ ] Set up `pre-commit`, `ruff`, `pytest`, `.gitignore`, `.env.example`
- [ ] Commit this MASTER_PLAN.md to `docs/`
- [ ] Create project in W&B, get API key, add to `.env`

### Hour 4–8 — first data touch

- [ ] Fetch 50 Supreme Court criminal judgments from Indian Kanoon manually (save as reference)
- [ ] Write v0 scraper for Indian Kanoon with explicit rate limiting (1 req / 3 sec minimum)
- [ ] Scrape 1,000 SC criminal judgments over next ~24 hours (background)
- [ ] Write initial cleaning script — strip boilerplate, detect language, split into chunks
- [ ] Store as JSONL, commit sample (10 docs) to repo

### Hour 8–16 — first model touch

- [ ] Run Unsloth quickstart on any small dataset on Kaggle — confirm QLoRA pipeline works
- [ ] Run LlamaIndex quickstart with your 50 manually-fetched docs — confirm RAG pipeline works
- [ ] Embed 50 docs with BGE-M3, index in local Qdrant, query with 5 test questions

### Hour 16–48 — close Week 1 setup

- [ ] Build metadata extraction v0 (court, date, sections cited)
- [ ] Design the eval set format
- [ ] Write the project journal entry for Day 1 (public in repo)
- [ ] Plan Week 2 in detail

---

## 13. Project Journaling Protocol

Commit a markdown journal entry every Friday to `journal/YYYY-WW.md`. Each entry:

- What got done this week (bullets)
- What failed or blocked (honest)
- Metrics snapshot (latest eval numbers)
- Plan for next week
- One thing learned

Public journaling is how you stay honest with a solo project. It also becomes blog-post source material later.

---

## 14. Appendices

### A. Key URLs

- Indian Kanoon: indiankanoon.org
- India Code: indiacode.nic.in
- PRS India (for BNS/BNSS context): prsindia.org
- Supreme Court of India: main.sci.gov.in
- eCourts: ecourts.gov.in
- Law Commission: lawcommissionofindia.nic.in
- AI4Bharat: ai4bharat.iitm.ac.in
- OpenNyAI: opennyai.org
- Unsloth: github.com/unslothai/unsloth
- LlamaIndex: docs.llamaindex.ai
- Qdrant: qdrant.tech
- HuggingFace: huggingface.co

### B. Seed datasets (existing open)

- OpenNyAI InJudgements (HF: `opennyaiorg/InJudgements_dataset`)
- IndianBailJudgments-1200 (arXiv 2507.02506)
- LegalEval shared task data
- InLegalBERT pretraining data (partial)
- AI4Bharat IndicNLPSuite (for Indic language baselines)

### C. Reading list (first 2 weeks, alongside coding)

- Karpathy, *"Let's build GPT"* (YouTube) — tokenization + arch refresher
- HF NLP course — PEFT chapter
- Lewis et al., *"Retrieval-Augmented Generation"* — original RAG paper
- Chalkidis et al., *"LexGLUE"* — legal NLP benchmark design
- Shaheen et al. (2024) on Indian legal corpora — scan the literature
- BNS/BNSS/BSA bare text + PRS comparison documents

### D. Tooling commands reference

```bash
# Environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Fine-tune (local test)
python scripts/train.py --config configs/qwen7b_qlora.yaml --dry-run

# Build vector index
python scripts/embed_corpus.py --input data/cleaned --output qdrant://...

# Evaluate
python scripts/eval.py --model <hf-id> --benchmark crimbench_in

# Serve demo
python demo/app.py
```

### E. One-paragraph project abstract (reusable)

> We present IndicCrimLaw-7B, an open-source language model specialized for Indian criminal law reasoning, along with IndicCrimCorpus — a cleaned, deduplicated corpus of Indian Supreme Court and High Court criminal judgments — and CrimBench-IN, the first benchmark explicitly designed to evaluate large language models on Indian criminal law tasks including the recently enacted Bharatiya Nyaya Sanhita (2023) transition from the Indian Penal Code (1860). The model is fine-tuned via QLoRA on Qwen 2.5 7B using a curated instruction dataset covering section interpretation, IPC↔BNS mapping, procedural reasoning, citation-grounded question answering, and Hindi-language legal queries. When paired with retrieval-augmented generation over the released corpus, the system achieves substantial improvements over frontier proprietary models on tasks requiring verified citation fidelity and BNS/IPC transition awareness. All artifacts — model weights, training data, benchmark, evaluation code — are released under permissive licenses to support research on low-resource legal NLP.

---

**This document is the source of truth. Update it when scope changes. Do not let the plan drift silently.**
