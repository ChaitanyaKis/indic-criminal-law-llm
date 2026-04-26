"""Tests for the state-file lockfile.

Concurrency tests use ``multiprocessing.Process`` (not threading) because
``filelock.FileLock`` is reentrant within a single process — two threads
in the same process can both acquire the same lock and racing remains
possible at the application layer. Multiprocessing exercises the
OS-level mutual exclusion that we actually depend on.

On Windows, ``multiprocessing.Process`` uses the ``spawn`` start method,
which means worker callables must be importable at module top-level
(closures and nested functions don't work). All workers below are
top-level for that reason.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import time
from pathlib import Path


# ---- Top-level worker functions (importable for spawn) ---------------


def _save_worker(state_path_str: str, payload: dict, delay: float = 0.0) -> None:
    """Atomic save with optional pre-write sleep (to interleave with another writer)."""
    if delay:
        time.sleep(delay)
    from src.scrapers.state import atomic_save_state

    atomic_save_state(payload, state_path_str)


def _hold_lock_worker(state_path_str: str, hold_seconds: float) -> None:
    """Acquire the same FileLock used by atomic_save_state and hold it.

    Uses the public ``state_lock`` context manager so the lockfile path
    derivation matches whatever the production code uses.
    """
    from src.scrapers.state import state_lock

    with state_lock(state_path_str, timeout=10):
        time.sleep(hold_seconds)


def _try_save_with_short_timeout(
    state_path_str: str, timeout: float, result_path_str: str,
) -> None:
    """Attempt an ``atomic_save_state`` with a short timeout. Write the
    outcome to ``result_path_str`` so the parent test can inspect it."""
    from src.scrapers.state import atomic_save_state

    out = Path(result_path_str)
    try:
        atomic_save_state({"x": 1}, state_path_str, timeout=timeout)
        out.write_text("ok", encoding="utf-8")
    except RuntimeError as e:
        out.write_text(f"timeout: {e}", encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        out.write_text(f"other: {type(e).__name__}: {e}", encoding="utf-8")


# ---- Tests ------------------------------------------------------------


def test_lock_acquired_and_released(tmp_path: Path):
    """Acquiring the lock, returning, and re-acquiring it on the next call
    works — i.e. the lock is released cleanly at the end of the with-block."""
    from src.scrapers.state import atomic_save_state

    state_path = tmp_path / "state.json"
    atomic_save_state({"a": 1}, state_path)
    assert state_path.exists()

    # Second call must succeed (would block forever if the first didn't release)
    atomic_save_state({"b": 2}, state_path)
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["b"] == 2
    assert "last_updated" in data


def test_concurrent_writes_serialize(tmp_path: Path):
    """Two processes writing concurrently both succeed and produce a
    non-corrupt JSON file — the lock serializes them."""
    state_path = tmp_path / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)

    p1 = mp.Process(target=_save_worker, args=(str(state_path), {"who": "a"}, 0.0))
    p2 = mp.Process(target=_save_worker, args=(str(state_path), {"who": "b"}, 0.05))
    p1.start()
    p2.start()
    p1.join(timeout=20)
    p2.join(timeout=20)

    assert p1.exitcode == 0, f"p1 failed (exitcode={p1.exitcode})"
    assert p2.exitcode == 0, f"p2 failed (exitcode={p2.exitcode})"

    # File must be parseable JSON — no half-written state.
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data.get("who") in ("a", "b")
    assert "last_updated" in data


def test_timeout_raises_runtime_error(tmp_path: Path):
    """When another process holds the lock past our timeout, ``atomic_save_state``
    must raise a ``RuntimeError`` (wrapped from ``filelock.Timeout``) with the
    actionable message we promise."""
    state_path = tmp_path / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    result_path = tmp_path / "result.txt"

    holder = mp.Process(target=_hold_lock_worker, args=(str(state_path), 3.0))
    holder.start()
    time.sleep(0.5)  # let the holder acquire its lock

    saver = mp.Process(
        target=_try_save_with_short_timeout,
        args=(str(state_path), 0.5, str(result_path)),
    )
    saver.start()
    saver.join(timeout=15)

    holder.join(timeout=15)

    assert saver.exitcode == 0, "Saver process did not exit cleanly"
    result = result_path.read_text(encoding="utf-8")
    assert result.startswith("timeout:"), f"Expected timeout error, got: {result!r}"
    assert "Could not acquire" in result, (
        f"Expected our actionable message, got: {result!r}"
    )
