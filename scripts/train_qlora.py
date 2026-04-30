"""QLoRA fine-tuning of Qwen 2.5 7B Instruct on the v0.2 instruction dataset.

Target: Kaggle T4 (16 GB VRAM). Loads the base model in 4-bit NF4
quantization, attaches LoRA adapters (rank 16, alpha 32) to all linear
projections (attention q/k/v/o + MLP gate/up/down), formats examples
with Qwen's chat template, and trains via TRL's SFTTrainer.

Outputs the LoRA adapter (NOT the merged model) to ``--output-dir``.
The base model can later be re-loaded by ``scripts/generate.py`` with
the adapter applied.

Heavy ML imports (torch / transformers / peft / trl / bitsandbytes) are
deferred to ``main()``. Module-level imports stay limited to stdlib so
``python -c "import scripts.train_qlora"`` succeeds in the local venv
even without the training stack installed (those packages live only on
Kaggle, per ``notebooks/kaggle_train_qlora.ipynb``).

Usage
-----
::

    # Smoke test (5 optimizer steps, ~5 minutes on T4):
    python scripts/train_qlora.py \\
        --dataset data/processed/instruction_dataset_v0.2.jsonl \\
        --output-dir output/qwen25_7b_qlora_smoke \\
        --max-steps 5

    # Full run (3 epochs, ~18-24h on T4):
    python scripts/train_qlora.py \\
        --dataset data/processed/instruction_dataset_v0.2.jsonl \\
        --output-dir output/qwen25_7b_qlora_v1
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_DATASET = "data/processed/instruction_dataset_v0.2.jsonl"
DEFAULT_OUTPUT_DIR = "output/qwen25_7b_qlora_v1"
DEFAULT_SEED = 42

# All linear projections in Qwen 2.5's transformer block — attention
# q/k/v/o plus the SwiGLU MLP's gate/up/down.
LORA_TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05

MAX_SEQ_LENGTH = 1024
EVAL_FRACTION = 0.05


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--dataset", type=str, default=DEFAULT_DATASET)
    p.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--base-model", type=str, default=DEFAULT_BASE_MODEL)
    p.add_argument(
        "--max-steps", type=int, default=None,
        help="Override num_train_epochs with a fixed step count "
             "(use for smoke testing; default: full 3 epochs).",
    )
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument(
        "--hf-token", type=str, default=None,
        help="HuggingFace token; falls back to the HF_TOKEN env var.",
    )
    return p.parse_args(argv)


def _format_example(example: dict, tokenizer) -> dict:
    """Render one Alpaca-style row through Qwen's chat template.

    The template is whatever Qwen 2.5's tokenizer ships with — for
    Qwen2.5-Instruct that produces:

        <|im_start|>user
        {instruction}\\n{input}     # input only when present
        <|im_end|>
        <|im_start|>assistant
        {output}
        <|im_end|>
    """
    instruction = (example.get("instruction") or "").strip()
    input_text = (example.get("input") or "").strip()
    output = (example.get("output") or "").strip()
    user_content = f"{instruction}\n{input_text}" if input_text else instruction
    messages = [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": output},
    ]
    return {"text": tokenizer.apply_chat_template(messages, tokenize=False)}


def _build_training_args_kwargs(args: argparse.Namespace) -> dict:
    """Single source of truth for hyperparameters — also used by tests/docs."""
    kwargs = dict(
        output_dir=args.output_dir,
        num_train_epochs=3,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        warmup_steps=50,
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        fp16=True,
        logging_steps=20,
        save_strategy="steps",
        save_steps=200,
        save_total_limit=3,
        eval_strategy="steps",
        eval_steps=200,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        gradient_checkpointing=True,
        # PEFT + gradient checkpointing requires non-reentrant variant
        # to avoid "no grad" errors on the embedding layer.
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        seed=args.seed,
        # SFTConfig-specific:
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_text_field="text",
        packing=False,
    )
    if args.max_steps is not None:
        kwargs["max_steps"] = args.max_steps
        # When max_steps is set, num_train_epochs is ignored by the
        # HF Trainer; leaving it as 3 documents the intended full-run
        # value.
    return kwargs


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("train_qlora")

    # ---- Heavy imports (deferred so module import stays light) -----
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    hf_token = args.hf_token or os.environ.get("HF_TOKEN")

    log.info("Base model: %s", args.base_model)
    log.info("Dataset:    %s", args.dataset)
    log.info("Output dir: %s", args.output_dir)
    if args.max_steps is not None:
        log.warning("SMOKE TEST mode: max_steps=%d (overrides epochs)", args.max_steps)

    # ---- Tokenizer --------------------------------------------------
    tokenizer = AutoTokenizer.from_pretrained(
        args.base_model, token=hf_token, trust_remote_code=False,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # ---- 4-bit NF4 quantization ------------------------------------
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    # ---- Base model + PEFT wrapping --------------------------------
    log.info("Loading base model in 4-bit NF4...")
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        token=hf_token,
        trust_remote_code=False,
    )
    model.config.use_cache = False  # incompatible with gradient checkpointing
    model.config.pretraining_tp = 1
    model = prepare_model_for_kbit_training(model)
    if hasattr(model, "enable_input_require_grads"):
        # Required for gradients to flow through quantized embeddings
        # under gradient_checkpointing.
        model.enable_input_require_grads()

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=LORA_TARGET_MODULES,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)

    n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    n_total = sum(p.numel() for p in model.parameters())
    log.info(
        "Trainable params: %s / %s (%.4f%%)",
        f"{n_trainable:,}", f"{n_total:,}",
        100 * n_trainable / max(n_total, 1),
    )

    # ---- Dataset (95/5 train/eval, deterministic) ------------------
    log.info("Loading dataset: %s", args.dataset)
    dataset = load_dataset("json", data_files=args.dataset, split="train")
    dataset = dataset.shuffle(seed=args.seed)
    splits = dataset.train_test_split(test_size=EVAL_FRACTION, seed=args.seed)
    train_ds = splits["train"].map(
        lambda ex: _format_example(ex, tokenizer),
        remove_columns=splits["train"].column_names,
    )
    eval_ds = splits["test"].map(
        lambda ex: _format_example(ex, tokenizer),
        remove_columns=splits["test"].column_names,
    )
    log.info("Train: %d rows | Eval: %d rows", len(train_ds), len(eval_ds))

    # ---- Train -----------------------------------------------------
    sft_config = SFTConfig(**_build_training_args_kwargs(args))

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        tokenizer=tokenizer,
    )

    trainer.train()

    # ---- Save adapter ----------------------------------------------
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    log.info("Adapter saved to %s", args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
