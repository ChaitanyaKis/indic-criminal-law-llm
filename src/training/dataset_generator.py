"""Orchestrator for the instruction-dataset build.

Wires the individual generators together, validates each emitted pair,
deduplicates, and writes the accepted records to the output JSONL plus
rejected records (with reasons) to a sibling file. The CLI in
``scripts/build_instruction_dataset.py`` is the primary entry point.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from src.training.validators import DuplicateInstructionTracker, validate

log = logging.getLogger(__name__)


# Registry maps generator-name → callable(**kwargs) -> list[record]
def _get_registry() -> dict[str, Callable[..., list[dict[str, Any]]]]:
    from src.training.generators import (
        bns_transition,
        case_summarization,
        mapping_qa,
        refusal_examples,
        section_interpretation,
    )
    return {
        "mapping_qa": mapping_qa.generate_pairs,
        "section_interpretation": section_interpretation.generate_pairs,
        "refusal": refusal_examples.generate_pairs,
        "bns_transition": bns_transition.generate_pairs,
        "case_summarization": case_summarization.generate_pairs,
    }


DEFAULT_PHASE1_GENERATORS = (
    "mapping_qa",
    "section_interpretation",
    "refusal",
    "bns_transition",
)
ALL_GENERATORS = DEFAULT_PHASE1_GENERATORS + ("case_summarization",)


def build_dataset(
    output_path: Path,
    generators: list[str] | tuple[str, ...] | None = None,
    rejected_path: Path | None = None,
    generator_kwargs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the configured generators, validate, write to disk.

    Returns a summary dict with per-generator counts, accepted total,
    rejected total, and rejection reasons.
    """
    generators = list(generators or DEFAULT_PHASE1_GENERATORS)
    generator_kwargs = generator_kwargs or {}
    output_path = Path(output_path)
    rejected_path = rejected_path or output_path.with_name(
        output_path.stem + "_rejected.jsonl"
    )

    registry = _get_registry()
    for g in generators:
        if g not in registry:
            raise ValueError(f"Unknown generator {g!r}; have {sorted(registry)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rejected_path.parent.mkdir(parents=True, exist_ok=True)

    dup_tracker = DuplicateInstructionTracker()
    per_generator_emitted: dict[str, int] = {}
    per_generator_accepted: dict[str, int] = {}
    rejection_reasons: dict[str, int] = {}
    accepted_total = 0
    rejected_total = 0

    # Atomic-ish: write to a temp then rename at the end.
    tmp_out = output_path.with_name(output_path.name + ".tmp")
    tmp_rej = rejected_path.with_name(rejected_path.name + ".tmp")
    with tmp_out.open("w", encoding="utf-8") as f_out, \
         tmp_rej.open("w", encoding="utf-8") as f_rej:

        for gen_name in generators:
            log.info("Running generator: %s", gen_name)
            kwargs = generator_kwargs.get(gen_name, {})
            records = registry[gen_name](**kwargs)
            per_generator_emitted[gen_name] = len(records)
            per_generator_accepted.setdefault(gen_name, 0)

            for rec in records:
                # Run the structural / leakage checks first.
                reason = validate(rec)
                if reason is None:
                    # Then the dedup check (stateful).
                    reason = dup_tracker.check(rec)
                if reason is not None:
                    rejected_record = dict(rec)
                    rejected_record["_rejection_reason"] = reason
                    f_rej.write(json.dumps(rejected_record, ensure_ascii=False) + "\n")
                    rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                    rejected_total += 1
                    continue

                # Accepted — strip _metadata for now? Spec says drop
                # before training, keep in pipeline. So we keep it.
                f_out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                accepted_total += 1
                per_generator_accepted[gen_name] += 1

    tmp_out.replace(output_path)
    tmp_rej.replace(rejected_path)

    return {
        "output_path": str(output_path),
        "rejected_path": str(rejected_path),
        "generators": list(generators),
        "per_generator_emitted": per_generator_emitted,
        "per_generator_accepted": per_generator_accepted,
        "accepted_total": accepted_total,
        "rejected_total": rejected_total,
        "rejection_reasons": rejection_reasons,
    }
