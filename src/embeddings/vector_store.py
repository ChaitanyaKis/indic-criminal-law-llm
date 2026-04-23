"""Thin Qdrant wrapper — local-file mode, collection ``judgments_v1``.

Idempotency key: each chunk's deterministic ``chunk_id`` is hashed into
a UUID5 that becomes the Qdrant point ID. Re-upserting the same chunk
overwrites the previous point without creating a duplicate.

Qdrant local-file (``QdrantClient(path=...)``) uses a single-writer
SQLite-like backend. Running multiple processes against the same path
deadlocks — safe because only ``build_embeddings.py`` writes. Reader
scripts (``query_embeddings.py``) open the same path but should not
run concurrently with the builder.
"""

from __future__ import annotations

import logging
import uuid
import warnings
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from qdrant_client import QdrantClient

# Qdrant's local-file mode emits a UserWarning on every payload-index
# create ("Payload indexes have no effect in the local Qdrant. Please
# use server Qdrant if you need payload indexes."). We still call
# create_payload_index so the same code works against server Qdrant
# later; silence the informational warning here.
warnings.filterwarnings(
    "ignore",
    message=r"Payload indexes have no effect in the local Qdrant.*",
    category=UserWarning,
)
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

DEFAULT_COLLECTION = "judgments_v1"
# Stable namespace so UUID5 hashing stays consistent across reinstalls.
_UUID_NAMESPACE = uuid.UUID("a6bd0e19-4a57-4b2f-9a1e-1c0000000001")

log = logging.getLogger(__name__)


class VectorStore:
    def __init__(
        self,
        path: Path | str,
        collection_name: str = DEFAULT_COLLECTION,
        vector_size: int = 1024,
    ):
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.client = QdrantClient(path=str(path))
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._ensure_collection()

    # ---- Collection setup --------------------------------------------

    def _ensure_collection(self) -> None:
        existing = {c.name for c in self.client.get_collections().collections}
        if self.collection_name in existing:
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
        )
        # Payload indices for the fields we'll filter on at query time.
        for field_name, schema in [
            ("doc_id", PayloadSchemaType.KEYWORD),
            ("year", PayloadSchemaType.INTEGER),
            ("court", PayloadSchemaType.KEYWORD),
            ("statutes_cited_acts", PayloadSchemaType.KEYWORD),
            ("has_ipc_302", PayloadSchemaType.BOOL),
        ]:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema,
                )
            except Exception as e:  # noqa: BLE001
                log.warning("Payload index create failed for %s: %s", field_name, e)

    # ---- ID mapping --------------------------------------------------

    @staticmethod
    def chunk_id_to_uuid(chunk_id: str) -> str:
        return str(uuid.uuid5(_UUID_NAMESPACE, chunk_id))

    # ---- Write -------------------------------------------------------

    def upsert(self, points_data: Iterable[dict[str, Any]]) -> int:
        """Upsert a batch of ``{chunk_id, vector, payload}`` dicts. The
        ``vector`` may be a list or a numpy array. Returns point count."""
        points = []
        for p in points_data:
            vec = p["vector"]
            if isinstance(vec, np.ndarray):
                vec = vec.tolist()
            points.append(PointStruct(
                id=self.chunk_id_to_uuid(p["chunk_id"]),
                vector=vec,
                payload=p["payload"],
            ))
        if not points:
            return 0
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=False,
        )
        return len(points)

    # ---- Read --------------------------------------------------------

    def search(
        self,
        vector: np.ndarray | list[float],
        top_k: int = 10,
        filter_: Filter | None = None,
    ):
        """Return a list of ScoredPoint. Thin wrapper around
        ``client.query_points`` (the ``.search()`` method was removed in
        qdrant-client 1.12+)."""
        if isinstance(vector, np.ndarray):
            vector = vector.tolist()
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=top_k,
            query_filter=filter_,
            with_payload=True,
        )
        return result.points

    def count(self) -> int:
        return self.client.count(collection_name=self.collection_name).count

    def get_collection_info(self) -> dict[str, Any]:
        info = self.client.get_collection(collection_name=self.collection_name)
        # QdrantClient returns a pydantic-style object; extract the useful bits.
        try:
            vectors_count = info.vectors_count or 0
        except AttributeError:
            vectors_count = 0
        try:
            points_count = info.points_count or 0
        except AttributeError:
            points_count = 0
        return {
            "collection": self.collection_name,
            "vector_size": self.vector_size,
            "points_count": points_count or self.count(),
            "vectors_count": vectors_count,
            "path": str(self.path),
        }

    # ---- Utility -----------------------------------------------------

    @staticmethod
    def filter_by_year(year: int) -> Filter:
        return Filter(must=[FieldCondition(key="year", match=MatchValue(value=year))])

    @staticmethod
    def filter_by_act(act: str) -> Filter:
        return Filter(must=[
            FieldCondition(key="statutes_cited_acts", match=MatchValue(value=act)),
        ])

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:  # noqa: BLE001
            pass
