"""Case-summarization pairs (LLM-assisted, deferred to Phase 2).

This module is a stub. The full implementation belongs to the
post-Phase-1 step where the user opts in via
``--generators ...,case_summarization`` after reviewing v0.1
rule-based output. Phase 1 explicitly excludes this generator from
the default to keep the run free and fast.

Skeleton design (for the implementation step):
- Iterate ``data/raw/supreme_court/**/*.json``, filter by
  confidence=high, length < 100K chars, year ≥ 2020, and presence of
  at least one top-50 IPC citation.
- For each selected judgment, call the LLM (Gemini Flash by default,
  or Claude Sonnet via --provider claude) with a fixed
  summarization prompt. Cache responses by content-hash to
  ``data/processed/_cache/case_summaries/<sha256>.json`` so re-runs
  do not re-call the API.
- Emit 2-3 Q&A pairs per summary: holding, reasoning, established
  principles.

Stub behaviour: returns an empty list and logs a notice.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def generate_pairs(*args, **kwargs) -> list[dict[str, Any]]:
    log.info(
        "case_summarization is a stub in v0.1; deferred to Phase 2. "
        "Returning empty pair list. Run with --generators "
        "...,case_summarization once the implementation is wired up."
    )
    return []
