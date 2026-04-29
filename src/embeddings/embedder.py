"""Sentence-transformer wrapper defaulting to BGE-M3.

Kept as a thin class so tests and the pipeline can inject a fake embedder
without touching the real model. The class is lazy — the transformer
weights load on first ``embed()`` call, not on ``__init__()`` — so
constructing an Embedder as part of normal imports is cheap.
"""

from __future__ import annotations

import logging
from typing import Protocol

import numpy as np

DEFAULT_MODEL = "BAAI/bge-m3"

log = logging.getLogger(__name__)


class EmbedderProtocol(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...


class Embedder:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str | None = None,
        batch_size: int | None = None,
    ):
        import torch

        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
                log.warning(
                    "CUDA not available; %s on CPU is slow (~1-3s per chunk). "
                    "Full runs on >1K chunks will take tens of minutes.",
                    model_name,
                )
        self.device = device
        self.model_name = model_name
        self.batch_size = batch_size if batch_size is not None else (16 if device == "cuda" else 8)
        self._model = None  # lazy

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            log.info("Loading %s on %s ...", self.model_name, self.device)
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    @property
    def dim(self) -> int:
        # sentence-transformers 5.x renamed the method; fall back for older
        # installs.
        m = self.model
        getter = getattr(m, "get_embedding_dimension", None) or m.get_sentence_embedding_dimension
        return getter()

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vecs = self.model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vecs.astype(np.float32)
