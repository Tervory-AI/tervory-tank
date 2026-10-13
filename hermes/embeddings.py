"""Local embeddings. The model runs in this container. No provider key.

BAAI/bge-small-en-v1.5 is the default (384 dimensions, CPU). Client text is
not sent to an embedding API.
"""

from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class FastEmbedder:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self.model_name = model_name
        self.dim = 384
        self._model: object | None = None

    def load(self) -> None:
        if self._model is not None:
            return
        from fastembed import TextEmbedding

        model = TextEmbedding(model_name=self.model_name, cuda=False)
        sample = next(iter(model.embed(["."])))
        self.dim = int(len(sample))
        self._model = model

    def embed(self, text: str) -> list[float]:
        self.load()
        model = self._model
        if model is None:
            raise RuntimeError("embedding model is not loaded")
        vector = next(iter(model.embed([text])))  # type: ignore[attr-defined]
        return [float(item) for item in vector]
