"""Build the v0.1 instruction dataset from the existing corpus + mappings.

Phase 1 default: rule-based generators only (mapping_qa,
section_interpretation, refusal, bns_transition). The LLM-assisted
case_summarization generator is opt-in via
``--generators ...,case_summarization`` because it costs API calls.

Output format: Alpaca-style JSONL, one record per line, schema::

    {
      "instruction": str,
      "input": str (often ""),
      "output": str,
      "_metadata": {
        "source": "mapping_qa | section_interpretation | refusal | bns_transition",
        "source_id": str,
        "generated_by": "rule_based | hand_written | claude | gemini",
        "validated": bool
      }
    }

Usage
-----
::

    # Phase 1 default — runs in ~5 seconds, no API calls
    python scripts/build_instruction_dataset.py

    # Phase 2 (later) — opt in to LLM-assisted summarization
    python scripts/build_instruction_dataset.py \\
        --generators mapping_qa,section_interpretation,refusal,bns_transition,case_summarization \\
        --provider gemini

Cost note: case_summarization runs ~200 judgments × ~50K input tokens
per call. With Gemini Flash free tier the cost is zero but the daily
quota cap is real (20 requests/day on free tier — see
docs/findings/2026-04-29_hallucination_study_v1_design.md context).
With Claude Sonnet at $3/M tokens, the run is ~$30. With paid Gemini,
fractional dollars.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.training.dataset_generator import (  # noqa: E402
    ALL_GENERATORS,
    DEFAULT_PHASE1_GENERATORS,
    build_dataset,
)

DEFAULT_OUTPUT = _PROJECT_ROOT / "data" / "processed" / "instruction_dataset_v0.1.jsonl"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument(
        "--generators",
        type=str,
        default=",".join(DEFAULT_PHASE1_GENERATORS),
        help=(
            "Comma-separated list of generators to run. "
            f"Available: {','.join(ALL_GENERATORS)}. "
            "Default excludes 'case_summarization' (Phase 2)."
        ),
    )
    p.add_argument(
        "--provider", choices=["gemini", "claude"], default="gemini",
        help="LLM provider for case_summarization (ignored if not running it).",
    )
    p.add_argument(
        "--max-cases-for-summarization", type=int, default=200,
        help="Cap on judgments to summarize (Phase 2; ignored in default Phase 1).",
    )
    p.add_argument("--resume", action="store_true",
                   help="Skip already-cached LLM responses (Phase 2).")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("build_dataset")

    requested = [g.strip() for g in args.generators.split(",") if g.strip()]
    log.info("Generators: %s", requested)
    log.info("Output: %s", args.output)

    generator_kwargs = {
        "case_summarization": {
            "provider": args.provider,
            "max_cases": args.max_cases_for_summarization,
            "resume": args.resume,
        },
    }

    summary = build_dataset(
        output_path=args.output,
        generators=requested,
        generator_kwargs=generator_kwargs,
    )

    bar = "=" * 72
    print(bar)
    print("Instruction dataset build complete")
    print(bar)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
