"""Locked, atomic state-file I/O.

Background
----------
Two days ago, the rescore script raced with the scraper's
``save_state_atomic`` and the scraper's stale in-memory snapshot
clobbered 835 fresh confidence labels written by the rescore. This
module provides the shared lock that both writers must use to make
their writes serializable.

Design
------
- ``filelock.FileLock`` (cross-platform, well-tested, OS-level locks).
- One lockfile per state file, derived as ``<state>.lock``.
- 30-second timeout on acquisition; longer than any single write or
  rescore takes, short enough to fail-fast if a stuck process holds the
  lock.

Usage
-----
One-shot writes (the scraper after every flush)::

    from src.scrapers.state import atomic_save_state
    atomic_save_state(state, "data/raw/_state/scraped_sc.json")

One-shot reads::

    from src.scrapers.state import load_state
    state = load_state("data/raw/_state/scraped_sc.json", default={})

Read-modify-write (the rescore script's ``apply_transitions``)::

    from src.scrapers.state import state_lock, read_state, write_state
    with state_lock(path):
        state = read_state(path)
        # mutate
        write_state(state, path)
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from filelock import FileLock, Timeout

# 30s — covers the longest write we issue (rescore flushing ~3K-doc
# state with stat recomputation runs in well under a second on disk).
LOCK_TIMEOUT = 30


def _lock_path(state_path: Path) -> Path:
    """Compute the lockfile path for a given state file.

    ``foo.json`` -> ``foo.lock``. Path-with-suffix replacement so we
    don't accumulate ``.json.lock`` doubled extensions.
    """
    if state_path.suffix:
        return state_path.with_suffix(".lock")
    return state_path.parent / (state_path.name + ".lock")


def _lock_for(state_path: Path, timeout: float) -> FileLock:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(_lock_path(state_path)), timeout=timeout)


def _raise_timeout(state_path: Path, timeout: float, op: str) -> None:
    raise RuntimeError(
        f"Could not acquire state file lock {_lock_path(state_path)} "
        f"within {timeout}s for {op}. Another scraper or rescore may "
        "be running. Check Get-Process python."
    )


# ---- Unsafe primitives (caller must hold the lock) --------------------


def read_state(state_path: Path | str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read the state file. Caller is expected to be inside ``state_lock``.

    Returns ``default`` (or ``{}`` if not given) when the file is absent.
    """
    p = Path(state_path)
    if not p.exists():
        return default if default is not None else {}
    return json.loads(p.read_text(encoding="utf-8"))


def write_state(state: dict[str, Any], state_path: Path | str) -> None:
    """Atomically replace the state file. Caller is expected to be inside
    ``state_lock``."""
    p = Path(state_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp = p.with_name(p.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


# ---- Locked one-shot helpers -----------------------------------------


def atomic_save_state(
    state: dict[str, Any],
    state_path: Path | str,
    timeout: float = LOCK_TIMEOUT,
) -> None:
    """Acquire the lock and atomically replace the state file."""
    p = Path(state_path)
    lock = _lock_for(p, timeout)
    try:
        with lock:
            write_state(state, p)
    except Timeout:
        _raise_timeout(p, timeout, "write")


def load_state(
    state_path: Path | str,
    default: dict[str, Any] | None = None,
    timeout: float = LOCK_TIMEOUT,
) -> dict[str, Any]:
    """Acquire the lock and read the state file. Returns ``default`` (or
    ``{}``) when the file is absent."""
    p = Path(state_path)
    if not p.exists():
        return default if default is not None else {}
    lock = _lock_for(p, timeout)
    try:
        with lock:
            return read_state(p, default)
    except Timeout:
        _raise_timeout(p, timeout, "read")
        # unreachable but keeps mypy happy
        return default if default is not None else {}


# ---- Context manager for read-modify-write ---------------------------


@contextmanager
def state_lock(
    state_path: Path | str,
    timeout: float = LOCK_TIMEOUT,
) -> Iterator[Path]:
    """Hold the lock across a read-modify-write block.

    Usage::

        with state_lock(path) as p:
            state = read_state(p)
            state["foo"] = "bar"
            write_state(state, p)
    """
    p = Path(state_path)
    lock = _lock_for(p, timeout)
    try:
        with lock:
            yield p
    except Timeout:
        _raise_timeout(p, timeout, "lock")
