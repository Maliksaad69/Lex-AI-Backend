"""
Embedding generator — local (sentence-transformers) with OpenAI fallback.

Usage:
    from services.ingestion.embedding import embed, EmbeddingModel

    model = EmbeddingModel()          # auto-detect best available
    vectors = model.embed(["text1", "text2"])  # returns list[list[float]]
    # or convenience:
    vectors = embed(["text1", "text2"])
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np

# ── Local Model ────────────────────────────────────────────────────────


class LocalEmbedder:
    """Sentence-transformers local model."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dim(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embeddings.tolist()


# ── OpenAI Embedder ────────────────────────────────────────────────────


class OpenAIEmbedder:
    """OpenAI text-embedding-3-small (or ada-002 fallback)."""

    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    @property
    def dim(self) -> int:
        # text-embedding-3-small = 1536, ada-002 = 1536
        return 1536

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Batch: max 2048 inputs per call for v3-small
        resp = self.client.embeddings.create(
            model=self.model_name,
            input=texts,
        )
        return [d.embedding for d in resp.data]


# ── Auto-select Embedder ───────────────────────────────────────────────


class EmbeddingModel:
    """
    Auto-selecting embedder wrapper. Singleton — first instance is cached globally.

    Priority:
      1. OpenAI if OPENAI_API_KEY is set
      2. Local sentence-transformers otherwise
    """

    _instance: Optional["EmbeddingModel"] = None

    def __new__(cls, provider=None, model_name=None):
        # Return cached instance unless explicitly requesting a different config
        if cls._instance is not None and provider is None and model_name is None:
            return cls._instance
        instance = super().__new__(cls)
        if provider is None and model_name is None:
            cls._instance = instance
        return instance

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        if hasattr(self, "_backend"):
            return  # already initialized (singleton)

        if provider is None:
            provider = "openai" if os.getenv("OPENAI_API_KEY") else "local"

        if provider == "openai":
            self._backend: LocalEmbedder | OpenAIEmbedder = OpenAIEmbedder(
                model_name=model_name or "text-embedding-3-small",
            )
        else:
            self._backend = LocalEmbedder(
                model_name=model_name or "all-MiniLM-L6-v2",
            )

    @property
    def dim(self) -> int:
        return self._backend.dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._backend.embed(texts)


# ── Convenience ────────────────────────────────────────────────────────

_default_model: Optional[EmbeddingModel] = None


def embed(
    texts: list[str],
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> list[list[float]]:
    """One-shot: embed a list of texts. Caches the model."""
    global _default_model
    if _default_model is None or provider or model_name:
        _default_model = EmbeddingModel(provider=provider, model_name=model_name)
    return _default_model.embed(texts)
