"""Semantic analysis service.

Provides cross-lingual embeddings and similarity computation.
Uses sentence-transformers for multilingual semantic matching.
"""

from typing import Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from backend.core.contracts import ISemanticAnalyzer


class SemanticService(ISemanticAnalyzer):
    """Handles semantic similarity using transformer models."""
    
    def __init__(self, model_name: str = "paraphrase-multilingual-mpnet-base-v2"):
        self._model = SentenceTransformer(model_name)
        self._cache: dict[str, np.ndarray] = {}
        
    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity between texts."""
        embedding_a = self._get_cached_embedding(text_a)
        embedding_b = self._get_cached_embedding(text_b)
        return float(np.dot(embedding_a, embedding_b))
    
    def get_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        embedding = self._get_cached_embedding(text)
        return embedding.tolist()
    
    def batch_embed(self, texts: list[str]) -> np.ndarray:
        """Efficiently embed multiple texts."""
        return self._model.encode(texts, convert_to_numpy=True)
    
    def _get_cached_embedding(self, text: str) -> np.ndarray:
        """Get embedding with caching."""
        if text not in self._cache:
            self._cache[text] = self._model.encode(text, convert_to_numpy=True)
        return self._cache[text]

