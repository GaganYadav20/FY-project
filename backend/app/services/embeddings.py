"""
Embedding Service for semantic similarity checks.

Provides sentence embeddings for the Originality Check Agent.
Falls back gracefully when sentence-transformers is not installed.
"""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Sentence embedding service using sentence-transformers.
    Falls back to None if the library is not installed.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._available = False
        self._load_model()

    def _load_model(self):
        """Try to load the sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._model = SentenceTransformer(self.model_name)
            self._available = True
            logger.info(f"Embedding model loaded: {self.model_name}")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Originality agent will use n-gram matching only. "
                "To enable semantic similarity: pip install sentence-transformers"
            )
        except Exception as exc:
            logger.warning(f"Failed to load embedding model: {exc}. Falling back to n-gram matching.")

    @property
    def available(self) -> bool:
        return self._available

    def encode(self, texts: List[str]) -> Optional[list]:
        """
        Encode texts into embeddings.

        Returns:
            List of embedding vectors, or None if unavailable.
        """
        if not self._available or not self._model:
            return None
        try:
            return self._model.encode(texts, convert_to_numpy=True).tolist()
        except Exception as exc:
            logger.error(f"Embedding encode failed: {exc}")
            return None

    def similarity(self, text1: str, text2: str) -> Optional[float]:
        """
        Compute cosine similarity between two texts.

        Returns:
            Float 0-1, or None if unavailable.
        """
        if not self._available:
            return None
        embeddings = self.encode([text1, text2])
        if embeddings is None or len(embeddings) < 2:
            return None
        try:
            import numpy as np  # type: ignore
            a, b = np.array(embeddings[0]), np.array(embeddings[1])
            norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(np.dot(a, b) / (norm_a * norm_b))
        except Exception as exc:
            logger.error(f"Similarity computation failed: {exc}")
            return None


# Singleton instance — created once, reused across requests
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> Optional[EmbeddingService]:
    """
    Get the shared EmbeddingService instance.

    Returns None safely if sentence-transformers is not installed,
    letting the Originality Agent fall back to n-gram matching.
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
        if not _embedding_service.available:
            # Return None so callers know embeddings aren't available
            return None
    return _embedding_service if _embedding_service.available else None
