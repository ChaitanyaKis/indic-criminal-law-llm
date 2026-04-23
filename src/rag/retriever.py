"""RAG retriever: dense similarity over Qdrant, with optional metadata filters.

Thin wrapper around :class:`VectorStore` that accepts a natural-language
query, encodes it with the same BGE-M3 model used at index time, and
returns a list of :class:`RetrievedChunk` dicts enriched with the fields
the generator will cite (doc_id, court, date, year, bench, statutes).

Filters supported
-----------------
- ``year_from`` / ``year_to`` (inclusive) — judgment-year range
- ``acts`` — list; chunk's ``statutes_cited_acts`` must contain any of these
- ``court`` — exact court string

Multiple filters are AND-combined; a list-valued filter like ``acts``
is OR within itself (Qdrant ``should``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from qdrant_client.http.models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    Range,
)

from src.embeddings.embedder import EmbedderProtocol
from src.embeddings.vector_store import VectorStore

log = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: str
    doc_id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "text": self.text,
            "score": round(float(self.score), 4),
            "metadata": self.metadata,
        }


class Retriever:
    def __init__(
        self,
        embedder: EmbedderProtocol,
        store: VectorStore,
        default_top_k: int = 10,
    ):
        self.embedder = embedder
        self.store = store
        self.default_top_k = default_top_k

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        acts: list[str] | None = None,
        court: str | None = None,
    ) -> list[RetrievedChunk]:
        k = top_k if top_k is not None else self.default_top_k
        filter_ = self._build_filter(year_from, year_to, acts, court)
        vec = self.embedder.embed([query])[0]
        hits = self.store.search(vector=vec, top_k=k, filter_=filter_)
        return [self._to_chunk(h) for h in hits]

    # ---- Internal ----------------------------------------------------

    @staticmethod
    def _build_filter(
        year_from: int | None,
        year_to: int | None,
        acts: list[str] | None,
        court: str | None,
    ) -> Filter | None:
        must: list[FieldCondition] = []
        if year_from is not None or year_to is not None:
            must.append(FieldCondition(
                key="year",
                range=Range(
                    gte=year_from if year_from is not None else None,
                    lte=year_to if year_to is not None else None,
                ),
            ))
        if court:
            must.append(FieldCondition(key="court", match=MatchValue(value=court)))
        if acts:
            must.append(FieldCondition(
                key="statutes_cited_acts",
                match=MatchAny(any=list(acts)),
            ))
        return Filter(must=must) if must else None

    @staticmethod
    def _to_chunk(hit) -> RetrievedChunk:
        p = hit.payload or {}
        metadata_keys = ("title", "court", "date", "year", "bench",
                         "statutes_cited_acts", "chunk_idx",
                         "char_start", "char_end")
        metadata = {k: p.get(k) for k in metadata_keys if p.get(k) is not None}
        return RetrievedChunk(
            chunk_id=p.get("chunk_id") or str(hit.id),
            doc_id=str(p.get("doc_id") or ""),
            text=p.get("text") or "",
            score=float(hit.score),
            metadata=metadata,
        )
