"""Integration test for the scraper's startup-lock check.

Loads ``scripts/scrape_sc_criminal.py`` via ``importlib`` so we don't
need to add a ``scripts/__init__.py`` (the script is still primarily a
CLI entry point, not a library package).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Module-level load — runs once at test collection. The target script's
# top-level code only sets constants and registers imports; no network or
# state I/O happens on import.
_spec = importlib.util.spec_from_file_location(
    "_scrape_sc_criminal_under_test",
    _PROJECT_ROOT / "scripts" / "scrape_sc_criminal.py",
)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


def test_scraper_refuses_start_when_lock_exists(tmp_path: Path):
    """A pre-existing lock file at ``<state>.lock`` makes the startup
    helper raise ``RuntimeError`` with the actionable message that names
    the lock path, the diagnostic command, and the manual recovery."""
    state_path = tmp_path / "scraped_sc.json"
    lock_path = state_path.with_suffix(".lock")
    # filelock would create an empty file when held; replicate that.
    lock_path.write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc_info:
        _module._check_no_stale_lock(state_path)

    msg = str(exc_info.value)
    assert "Lock file exists" in msg
    assert str(lock_path) in msg, "Error must name the offending lock path"
    assert "Get-Process python" in msg, "Error must include the diagnostic command"
    assert "delete the lock file manually" in msg, (
        "Error must explain manual recovery"
    )

    # Sanity: removing the lock makes the helper succeed.
    lock_path.unlink()
    _module._check_no_stale_lock(state_path)  # must not raise
