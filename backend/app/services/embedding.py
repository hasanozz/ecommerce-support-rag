from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

from ..config import Settings, get_settings


class EmbeddingService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._model = None

    @property
    def model_identity(self) -> str:
        if self.settings.embedding_provider == "hashing":
            return "hashing-sha256-v1"
        return self.settings.embedding_model

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.settings.embedding_model,
                device=self.settings.embedding_device,
            )
        return self._model

    def _hash_embedding(self, text: str) -> list[float]:
        vector = [0.0] * self.settings.embedding_dimension
        tokens = re.findall(r"[\wçğıöşüÇĞİÖŞÜ]+", text.casefold())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % len(vector)
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.settings.embedding_provider == "hashing":
            return [self._hash_embedding(text) for text in texts]
        model = self._load_model()
        prepared = [
            f"passage: {text}"
            if "e5" in self.settings.embedding_model.casefold()
            else text
            for text in texts
        ]
        vectors = model.encode(
            prepared,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    def embed_query(self, query: str) -> list[float]:
        if self.settings.embedding_provider == "hashing":
            return self._hash_embedding(query)
        model = self._load_model()
        prepared = (
            f"query: {query}"
            if "e5" in self.settings.embedding_model.casefold()
            else query
        )
        vector = model.encode(
            prepared,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vector.tolist()


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
