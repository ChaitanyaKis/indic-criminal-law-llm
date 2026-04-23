"""Retrieval smoke-test CLI for the Qdrant index.

Encodes ``--query`` with the same embedder used at index time and
prints the top-k hits with light metadata and a snippet of each chunk.
Read-only against the Qdrant path — safe to run while the builder is
idle (but not concurrently with a running ``build_embeddings.py``;
Qdrant local-file mode is single-writer).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.embeddings.embedder import Embedder  # noqa: E402
from src.embeddings.vector_store import VectorStore  # noqa: E402

DEFAULT_QDRANT_DIR = _PROJECT_ROOT / "data" / "processed" / "qdrant"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Query the judgment embedding index.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--query", required=True, help="Natural-language query string.")
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--filter-year", type=int, default=None)
    p.add_argument("--filter-act", type=str, default=None,
                   help="Restrict to chunks whose statutes_cited_acts contains this act.")
    p.add_argument("--qdrant-dir", type=Path, default=DEFAULT_QDRANT_DIR)
    p.add_argument("--json", action="store_true",
                   help="Emit JSON array instead of pretty output.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    embedder = Embedder()
    store = VectorStore(path=args.qdrant_dir, vector_size=embedder.dim)

    filter_ = None
    if args.filter_year is not None:
        filter_ = VectorStore.filter_by_year(args.filter_year)
    elif args.filter_act is not None:
        filter_ = VectorStore.filter_by_act(args.filter_act)

    vec = embedder.embed([args.query])[0]
    hits = store.search(vector=vec, top_k=args.top_k, filter_=filter_)

    if args.json:
        out = [
            {
                "score": round(float(h.score), 4),
                "doc_id": h.payload.get("doc_id"),
                "chunk_id": h.payload.get("chunk_id"),
                "year": h.payload.get("year"),
                "title": h.payload.get("title"),
                "acts": h.payload.get("statutes_cited_acts") or [],
                "text_preview": (h.payload.get("text") or "")[:300],
            }
            for h in hits
        ]
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    print()
    print(f"Query: {args.query!r}")
    if filter_:
        print(f"Filter: year={args.filter_year} act={args.filter_act}")
    print(f"Top {len(hits)} hits (of {args.top_k} requested):")
    print("=" * 72)
    for i, h in enumerate(hits, 1):
        p = h.payload or {}
        title = p.get("title") or "(no title)"
        year = p.get("year")
        acts = p.get("statutes_cited_acts") or []
        preview = (p.get("text") or "").strip().replace("\n", " ")[:200]
        print(f"{i}. [score={h.score:.3f}]  doc_id={p.get('doc_id')}  year={year}")
        print(f"   title:   {title}")
        print(f"   acts:    {acts}")
        print(f"   chunk:   {p.get('chunk_id')}")
        print(f"   preview: {preview!r}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
