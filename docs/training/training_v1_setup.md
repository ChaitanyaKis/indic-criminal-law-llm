# Training v1 — QLoRA fine-tune of Qwen 2.5 7B Instruct

Reproducibility documentation for the first IndicCrimLawLLM training
run. Records the exact configuration so a future re-run (or an
external reviewer) can reconstruct the experiment without spelunking
through the codebase.

## Reproducibility — Commit SHA

The v1 production training run was launched against repository commit
`eed53a6`.

To reproduce: set `REPO_COMMIT` in
[`notebooks/kaggle_train_qlora.ipynb`](../../notebooks/kaggle_train_qlora.ipynb)
to this SHA. The default value `'main'` follows the latest tip and is
appropriate for ongoing experimentation, not for paper reproducibility.

## Base model

- **Model:** [`Qwen/Qwen2.5-7B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)
- **Architecture:** decoder-only transformer, 28 layers, 28 attention heads, 7B parameters.
- **Tokenizer:** Qwen 2.5's native tokenizer with the `<|im_start|>` /
  `<|im_end|>` chat template.
- **Commit pin:** the HuggingFace revision is whatever
  `from_pretrained(...)` resolves at run time (no explicit
  `revision=` pinning yet — TODO for run v2).

## Dataset

- **File:** `data/processed/instruction_dataset_v0.2.jsonl`
- **Records:** 1,869 Alpaca-style pairs.
- **Source commit:** `2c8676b` ("feat: instruction dataset v0.2 —
  per-question answer scoping").
- **Per-generator counts:**
  - `mapping_qa`: 1,245
  - `section_interpretation`: 290
  - `bns_transition`: 219 (28 narrow sub-topics + 6 syntheses + 1
    transition_overview)
  - `refusal`: 115
- **Train / eval split:** 95 / 5, deterministic (seed=42).
- **Format:** Qwen chat template, `max_seq_length=1024`, right
  truncation, no packing.

## Quantization

- **Type:** 4-bit NF4 with double quantization
  (`bnb_4bit_use_double_quant=True`).
- **Compute dtype:** `float16`.
- **Library:** `bitsandbytes` 0.44.1.

## LoRA configuration

| Field | Value |
|---|---|
| `r` (rank) | 16 |
| `lora_alpha` | 32 |
| `lora_dropout` | 0.05 |
| `bias` | `none` |
| `task_type` | `CAUSAL_LM` |
| Target modules | `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj` |

Targets every linear projection in both the attention block and the
SwiGLU MLP. With this rank, expect ~40-50M trainable parameters
(~0.6% of the 7B base).

## TrainingArguments / SFTConfig

Defined in
[`scripts/train_qlora.py`](../../scripts/train_qlora.py)
as a single `_build_training_args_kwargs` dict. Verbatim:

```python
output_dir=args.output_dir
num_train_epochs=3
per_device_train_batch_size=4
gradient_accumulation_steps=4
learning_rate=2e-4
warmup_steps=50
optim="paged_adamw_8bit"
lr_scheduler_type="cosine"
fp16=True
logging_steps=20
save_strategy="steps"
save_steps=200
save_total_limit=3
eval_strategy="steps"
eval_steps=200
load_best_model_at_end=True
metric_for_best_model="eval_loss"
gradient_checkpointing=True
gradient_checkpointing_kwargs={"use_reentrant": False}
report_to="none"
seed=42
max_seq_length=1024
dataset_text_field="text"
packing=False
```

Effective batch size: `4 * 4 = 16` examples per optimizer step.

## Hardware target

- **Platform:** Kaggle Notebooks with **GPU T4 x1** accelerator.
- **VRAM:** 16 GB.
- **Compute precision:** fp16 (T4 lacks bf16; Ampere-only).
- **Estimated VRAM at peak:**
  - Base model (4-bit NF4): ~5 GB
  - LoRA adapter weights + optimizer state (paged AdamW 8-bit): ~1 GB
  - Activations (bsz=4, seq=1024, gradient checkpointing): ~6-8 GB
  - Headroom: ~2 GB
- **Estimated wall-clock for 3 epochs:** 18-24h on a single T4.
  - Steps per epoch: `1869 * 0.95 / 16 ≈ 110` optimizer steps.
  - Total optimizer steps: ~333.
  - Step time on T4 with gradient checkpointing: ~3-4 minutes.

## Training framework

- **Trainer:** [TRL](https://github.com/huggingface/trl)
  `SFTTrainer` (0.12.2) with `SFTConfig`.
- **PEFT:** [HuggingFace PEFT](https://github.com/huggingface/peft)
  0.13.2 (`LoraConfig`, `get_peft_model`,
  `prepare_model_for_kbit_training`).
- **Optimizer:** `paged_adamw_8bit` (bitsandbytes paged optimizer —
  swaps optimizer state to CPU when VRAM is tight).
- **LR schedule:** cosine decay with 50-step warmup.
- **Mixed precision:** fp16.
- **Gradient checkpointing:** enabled, non-reentrant (required for
  PEFT compatibility — the reentrant variant breaks gradient flow
  through the LoRA wrappers).

## Evaluation

- **Eval split:** held-out 5% (~94 examples) from the same v0.2
  dataset.
- **Eval metric:** `eval_loss` (cross-entropy on the assistant
  response tokens).
- **Best-model selection:** `load_best_model_at_end=True` — the
  adapter saved at the end of training is the lowest-eval-loss
  checkpoint within `save_total_limit=3` retained checkpoints.

## Output

- **Format:** PEFT adapter (`adapter_config.json`,
  `adapter_model.safetensors`, tokenizer files) — NOT a merged
  model.
- **Size:** ~80-150 MB (the adapter weights only; the base model
  must be re-loaded at inference time).
- **Path:**
  - Local: `output/qwen25_7b_qlora_v1/` (gitignored).
  - Kaggle: `/kaggle/working/output/`. Downloaded via Kaggle's
    notebook output mechanism after the run completes.

## Smoke test

Before the long run, the Kaggle notebook
([`notebooks/kaggle_train_qlora.ipynb`](../../notebooks/kaggle_train_qlora.ipynb))
runs a 5-step smoke test by default (`SMOKE_TEST = True`). The
smoke test confirms:

1. The pinned package versions install cleanly on Kaggle.
2. Qwen 2.5 7B loads in 4-bit NF4 inside 16 GB VRAM.
3. The PEFT wrapper attaches without OOM.
4. Forward + backward pass + optimizer step works.
5. The adapter saves to `/kaggle/working/output`.

Only after smoke passes is `SMOKE_TEST = False` flipped for the
full 3-epoch run.

## Inference

After training, the adapter is applied via
[`scripts/generate.py`](../../scripts/generate.py):

```bash
python scripts/generate.py \
  --adapter-dir output/qwen25_7b_qlora_v1 \
  --prompt "What is the BNS successor to IPC 124A?"
```

The base model is re-loaded in 4-bit by default (matches training
quantization); pass `--no-quantize` for fp16 inference at the cost
of more VRAM.

## Dataset upload to Kaggle

The training notebook reads the dataset from
`/kaggle/input/<slug>/`. To populate that path:

```bash
python scripts/prepare_kaggle_dataset.py
# Edit kaggle_upload/dataset-metadata.json: replace
# REPLACE_WITH_KAGGLE_USERNAME with your actual Kaggle username.
kaggle datasets create -p kaggle_upload
```

The `kaggle_upload/` directory is gitignored — re-build it from the
source `data/processed/instruction_dataset_v0.2.jsonl` whenever a
new version of the dataset is produced.

## Open items for v2

- Pin the base-model HuggingFace revision (`revision="..."`) so a
  silent upstream re-quantization can't shift the experiment.
- Add wandb logging (`report_to="wandb"`) — the v1 run uses
  `report_to="none"` to keep the notebook self-contained.
- Add early stopping on `eval_loss` plateau.
- Consider expanding rank to 32 for v2 if v1 underfits (smoke-test
  loss curve will tell us).
