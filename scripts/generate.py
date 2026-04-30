"""Inference for the QLoRA-fine-tuned Qwen 2.5 model.

Loads the base model and applies a trained LoRA adapter (produced by
``scripts/train_qlora.py``), then either runs a one-shot prompt
(``--prompt``) or an interactive REPL.

Heavy ML imports (torch / transformers / peft / bitsandbytes) are
deferred to ``main()`` so the module imports cleanly in environments
without the inference stack.

Usage
-----
::

    # One-shot:
    python scripts/generate.py --prompt "What is the BNS successor to IPC 124A?"

    # REPL:
    python scripts/generate.py
    > Has the Supreme Court ruled on any BNS cases?
    ...
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_ADAPTER_DIR = "output/qwen25_7b_qlora_v1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--adapter-dir", type=str, default=DEFAULT_ADAPTER_DIR)
    p.add_argument("--base-model", type=str, default=DEFAULT_BASE_MODEL)
    p.add_argument(
        "--prompt", type=str, default=None,
        help="One-shot generation; omit for interactive REPL.",
    )
    p.add_argument("--max-new-tokens", type=int, default=512)
    p.add_argument("--temperature", type=float, default=0.3)
    p.add_argument("--hf-token", type=str, default=None)
    p.add_argument(
        "--no-quantize", action="store_true",
        help="Load base model in fp16 instead of 4-bit (more VRAM, faster inference).",
    )
    return p.parse_args(argv)


def _generate(model, tokenizer, prompt: str, max_new_tokens: int, temperature: float) -> str:
    import torch
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated = outputs[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    log = logging.getLogger("generate")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    hf_token = args.hf_token or os.environ.get("HF_TOKEN")

    log.info("Loading tokenizer: %s", args.base_model)
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, token=hf_token)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    log.info("Loading base model: %s (quantized=%s)", args.base_model, not args.no_quantize)
    if args.no_quantize:
        base = AutoModelForCausalLM.from_pretrained(
            args.base_model,
            torch_dtype=torch.float16,
            device_map="auto",
            token=hf_token,
        )
    else:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        base = AutoModelForCausalLM.from_pretrained(
            args.base_model,
            quantization_config=bnb_config,
            device_map="auto",
            token=hf_token,
        )

    adapter_dir = Path(args.adapter_dir)
    if adapter_dir.exists() and any(adapter_dir.iterdir()):
        log.info("Applying LoRA adapter: %s", adapter_dir)
        model = PeftModel.from_pretrained(base, str(adapter_dir))
    else:
        log.warning(
            "Adapter dir %s missing or empty — generating from base model only.",
            adapter_dir,
        )
        model = base
    model.eval()

    if args.prompt is not None:
        out = _generate(model, tokenizer, args.prompt, args.max_new_tokens, args.temperature)
        print(out)
        return 0

    print("Interactive REPL. Type 'exit' / Ctrl-D to quit.")
    while True:
        try:
            prompt = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit"}:
            return 0
        out = _generate(model, tokenizer, prompt, args.max_new_tokens, args.temperature)
        print(out)


if __name__ == "__main__":
    sys.exit(main())
