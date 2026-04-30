"""Refusal training pairs from hand-crafted YAML templates.

Reads ``data/training/refusal_templates.yaml`` and emits one Alpaca
pair per (instruction, refusal) combination. Pure data transform —
no LLM calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_TEMPLATES_PATH = _PROJECT_ROOT / "data" / "training" / "refusal_templates.yaml"


def generate_pairs() -> list[dict[str, Any]]:
    if not _TEMPLATES_PATH.exists():
        return []
    doc = yaml.safe_load(_TEMPLATES_PATH.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for category_name, category in (doc.get("categories") or {}).items():
        refusal_text = (category.get("refusal") or "").strip()
        if not refusal_text:
            continue
        for inst in category.get("instructions") or []:
            inst = inst.strip()
            if not inst:
                continue
            out.append({
                "instruction": inst,
                "input": "",
                "output": refusal_text,
                "_metadata": {
                    "source": "refusal",
                    "source_id": f"refusal__{category_name}",
                    "generated_by": "hand_written",
                    "validated": False,
                },
            })
    return out
