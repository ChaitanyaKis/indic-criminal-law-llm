"""End-to-end RAG CLI — retrieve, generate, verify citations.

Usage
-----
::

    python scripts/ask.py --question "What is the scope of Section 498A IPC?"
    python scripts/ask.py --question "..." --top-k 5 --provider gemini
    python scripts/ask.py --question "..." --year-filter 2015-2020

Prints the question, the grounded answer, verified citations, any
hallucinated-citation warnings (to stderr), and — with ``--verbose`` —
the raw retrieved chunks that informed the answer.
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
from src.rag.citation_verifier import verify_citations  # noqa: E402
from src.rag.generator import DEFAULT_PROVIDER, RAGGenerator  # noqa: E402
from src.rag.retriever import Retriever  # noqa: E402

DEFAULT_QDRANT_DIR = _PROJECT_ROOT / "data" / "processed" / "qdrant"


def parse_year_filter(arg: str | None) -> tuple[int | None, int | None]:
    if not arg:
        return None, None
    s = arg.strip()
    if "-" in s:
        lo, hi = s.split("-", 1)
        return int(lo), int(hi)
    return int(s), int(s)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="End-to-end RAG query: retrieve, generate, verify.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--question", required=True)
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--provider", choices=["gemini", "groq", "claude"],
                   default=DEFAULT_PROVIDER)
    p.add_argument("--model", default=None,
                   help="Override the default model for the provider.")
    p.add_argument("--year-filter", type=str, default=None,
                   help="Single year (2018) or range (2015-2020).")
    p.add_argument("--act-filter", type=str, default=None,
                   help="Require retrieved chunks to cite this act "
                        "(e.g. IPC, CrPC, NDPS Act).")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--qdrant-dir", type=Path, default=DEFAULT_QDRANT_DIR)
    p.add_argument("--verbose", action="store_true",
                   help="Print the full text of every retrieved chunk.")
    p.add_argument("--json", action="store_true",
                   help="Emit a single JSON object with question/answer/"
                        "citations/verification. Suppresses pretty printing.")
    return p.parse_args(argv)


def _print_hit_summary(chunk, idx: int, verbose: bool) -> None:
    md = chunk.metadata or {}
    title = md.get("title") or "(no title)"
    year = md.get("year")
    acts = md.get("statutes_cited_acts") or []
    print(f"  [{idx}] score={chunk.score:.3f} doc_id={chunk.doc_id} "
          f"year={year}")
    print(f"      title: {title}")
    print(f"      acts:  {acts}")
    if verbose:
        print(f"      text:\n{chunk.text}\n")
    else:
        preview = chunk.text.strip().replace("\n", " ")[:180]
        print(f"      preview: {preview!r}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    year_from, year_to = parse_year_filter(args.year_filter)

    # Wire up
    embedder = Embedder()
    store = VectorStore(path=args.qdrant_dir, vector_size=embedder.dim)
    retriever = Retriever(embedder=embedder, store=store, default_top_k=args.top_k)
    generator = RAGGenerator(provider=args.provider, model=args.model)

    chunks = retriever.retrieve(
        args.question,
        top_k=args.top_k,
        year_from=year_from,
        year_to=year_to,
        acts=[args.act_filter] if args.act_filter else None,
    )

    result = generator.answer(
        args.question, chunks, temperature=args.temperature,
    )
    verification = verify_citations(result.answer, chunks)

    if args.json:
        print(json.dumps({
            "question": args.question,
            "answer": result.answer,
            "citations": result.citations,
            "verification": verification,
            "model_used": result.model_used,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "retrieved_top_3": [c.to_dict() for c in chunks[:3]],
        }, indent=2, ensure_ascii=False))
        return 0 if verification["all_valid"] else 2

    # Pretty output
    bar = "=" * 72
    print(bar)
    print("QUESTION")
    print(bar)
    print(args.question)
    print()
    print(bar)
    print(f"ANSWER   (model: {result.model_used}, provider: {args.provider})")
    print(bar)
    print(result.answer)
    print()
    print(bar)
    print("CITATION VERIFICATION")
    print(bar)
    print(f"  all_valid:          {verification['all_valid']}")
    print(f"  cited_count:        {verification['cited_count']}")
    print(f"  valid_citations:    {verification['valid_citations']}")
    if verification["invalid_citations"]:
        print(f"  HALLUCINATED IDS:   {verification['invalid_citations']}",
              file=sys.stderr)
    print()
    print(bar)
    print(f"RETRIEVED CHUNKS (top {min(len(chunks), 10)} of {len(chunks)})")
    print(bar)
    for i, c in enumerate(chunks[:10], 1):
        _print_hit_summary(c, i, args.verbose)
    if result.prompt_tokens is not None:
        print()
        print(f"Tokens: prompt={result.prompt_tokens}, "
              f"completion={result.completion_tokens}")
    return 0 if verification["all_valid"] else 2


if __name__ == "__main__":
    sys.exit(main())
