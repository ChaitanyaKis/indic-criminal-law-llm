"""Build (or incrementally extend) the Qdrant vector index.

Resumable and idempotent. Run it once to build from scratch; re-run it
after the scraper adds more judgments and it will embed only the new
documents. State file at ``data/processed/_state/embedded.json``
tracks which ``doc_id``s have been embedded.

Usage
-----
::

    # Full / incremental build
    python scripts/build_embeddings.py

    # Quick smoke test
    python scripts/build_embeddings.py --limit 20

    # Force reembed everything (e.g. after switching models)
    python scripts/build_embeddings.py --force-rebuild
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.embeddings.chunker import JudgmentChunker  # noqa: E402
from src.embeddings.embedder import Embedder  # noqa: E402
from src.embeddings.pipeline import (  # noqa: E402
    install_sigint_handler,
    run,
)
from src.embeddings.vector_store import VectorStore  # noqa: E402

DEFAULT_DATA_DIR = _PROJECT_ROOT / "data" / "raw" / "supreme_court"
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "data" / "processed" / "qdrant"
DEFAULT_STATE_FILE = _PROJECT_ROOT / "data" / "processed" / "_state" / "embedded.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build (or extend) the judgment embedding index.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    p.add_argument("--limit", type=int, default=None,
                   help="Stop after embedding this many new docs (useful for smoke tests).")
    p.add_argument("--force-rebuild", action="store_true",
                   help="Ignore state file; re-embed every doc. Qdrant upserts overwrite by UUID.")
    return p.parse_args(argv)


def print_banner(args: argparse.Namespace, embedder: Embedder) -> None:
    bar = "=" * 72
    print(bar)
    print("IndicCrimLawLLM — Embedding pipeline")
    print(bar)
    print(f"Data dir:       {args.data_dir}")
    print(f"Qdrant dir:     {args.output_dir}")
    print(f"State file:     {args.state_file}")
    print(f"Model:          {embedder.model_name}")
    print(f"Device:         {embedder.device}")
    print(f"Batch size:     {embedder.batch_size}")
    print(f"Force rebuild:  {args.force_rebuild}")
    print(f"Limit:          {args.limit}")
    print(f"Started at:     {datetime.now(timezone.utc).isoformat()}")
    print(bar)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    install_sigint_handler()

    chunker = JudgmentChunker()
    embedder = Embedder()
    print_banner(args, embedder)
    # Trigger eager load so the banner timing isn't misleading.
    _ = embedder.dim

    store = VectorStore(path=args.output_dir, vector_size=embedder.dim)

    summary = run(
        data_dir=args.data_dir,
        state_file=args.state_file,
        embedder=embedder,
        store=store,
        chunker=chunker,
        limit=args.limit,
        force_rebuild=args.force_rebuild,
        progress=True,
    )

    print()
    print("=" * 72)
    print("Summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
