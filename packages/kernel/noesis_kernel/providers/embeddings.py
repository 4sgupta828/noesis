"""Embeddings provider port + deterministic fake + local backend stub.

A single port with pluggable backends so ingestion never hard-depends on a paid
service: FakeEmbedder (tests), LocalEmbedder (sentence-transformers, zero credit
even in prod), and a hosted backend added later. The vector `dim` is fixed at
the schema level to whichever backend a deployment chooses.
"""
from __future__ import annotations

import hashlib
import struct
from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    @property
    def dim(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbedder:
    """Deterministic, offline embeddings for tests — hashed, unit-norm vectors.

    Same text → same vector, no network. Not semantically meaningful; it exists
    so retrieval *plumbing* can be tested at zero cost.
    """

    def __init__(self, dim: int = 64):
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec: list[float] = []
            counter = 0
            # Expand a SHA-256 stream into `dim` floats in [-1, 1].
            while len(vec) < self._dim:
                digest = hashlib.sha256(f"{text}|{counter}".encode()).digest()
                for i in range(0, len(digest), 4):
                    if len(vec) >= self._dim:
                        break
                    (u,) = struct.unpack("<I", digest[i:i + 4])
                    vec.append((u / 2**31) - 1.0)
                counter += 1
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            out.append([x / norm for x in vec])
        return out


class LocalEmbedder:
    """sentence-transformers backend — zero credit, runs on the box.

    Lazy-imports the model so the dependency is optional until used.
    """

    def __init__(self, model_id: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self._model_id = model_id
        self._model = None
        self._dim: int | None = None

    def _ensure(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy, optional dep

            self._model = SentenceTransformer(self._model_id)
            self._dim = int(self._model.get_sentence_embedding_dimension())

    @property
    def dim(self) -> int:
        self._ensure()
        assert self._dim is not None
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._ensure()
        assert self._model is not None
        return [v.tolist() for v in self._model.encode(texts, normalize_embeddings=True)]
