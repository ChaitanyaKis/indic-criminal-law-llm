# IndicCrimLaw

An open-source research project building a specialized LLM for Indian criminal
law, with first-class handling of the **IPC → BNS** (and CrPC → BNSS,
Evidence Act → BSA) transition that took effect 1 July 2024.

The goal is to produce a model and evaluation stack that understands *both*
the colonial-era statutes still governing pre-2024 offences and the new
Bharatiya Nyaya Sanhita regime, and can reason across the mapping between
them.

## Deliverables

1. **IndicCrimCorpus** — a cleaned, deduplicated corpus of Indian criminal
   law text: bare acts (IPC, BNS, CrPC, BNSS, Evidence Act, BSA, allied
   statutes), Supreme Court and High Court judgments, and commentary.
2. **IndicCrimLaw-7B** — a 7B-parameter open-weights model fine-tuned on the
   corpus, with explicit IPC↔BNS section-mapping competence.
3. **CrimBench-IN** — a benchmark suite covering statute recall,
   section-mapping, judgment-based QA, and applied reasoning problems.
4. **Tech report** — a public write-up of data sourcing, training recipe,
   evaluation results, limitations, and responsible-use guidance.

## Status

**Week 1 of 12.** Repository scaffold and environment setup.

## Quick start (Windows)

```powershell
# From the project root
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Copy the env template and fill in your keys
copy .env.example .env
notepad .env
```

Open a Jupyter kernel for the project:

```powershell
python -m ipykernel install --user --name indic-crim-law --display-name "IndicCrimLaw (py3.11)"
```

## Documentation

The detailed plan lives in [docs/MASTER_PLAN.md](docs/MASTER_PLAN.md).

## License

Released under the MIT License. See `LICENSE` for the full text.
