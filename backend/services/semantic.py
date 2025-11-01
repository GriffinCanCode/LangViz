"""Semantic analysis service.

Provides cross-lingual embeddings and similarity computation.
Uses sentence-transformers for multilingual semantic matching.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

from backend.core.contracts import ISemanticAnalyzer
from backend.observ import get_logger
from backend.errors import EmbeddingError

logger = get_logger(__name__)


class SemanticService(ISemanticAnalyzer):
    """Handles semantic similarity using transformer models."""
    
    def __init__(self, model_name: str = "paraphrase-multilingual-mpnet-base-v2"):
        logger.info("initializing_semantic_service", model_name=model_name)
        try:
            self._model = SentenceTransformer(model_name)
            self._cache: dict[str, np.ndarray] = {}
            logger.info("semantic_service_initialized", model_name=model_name)
        except Exception as e:
            logger.error("semantic_service_init_failed", model_name=model_name, error=str(e))
            raise EmbeddingError(model_name, f"Failed to load model: {str(e)}")
        
    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity between texts."""
        logger.debug("computing_semantic_similarity", text_a_len=len(text_a), text_b_len=len(text_b))
        embedding_a = self._get_cached_embedding(text_a)
        embedding_b = self._get_cached_embedding(text_b)
        similarity = float(np.dot(embedding_a, embedding_b))
        logger.debug("semantic_similarity_computed", similarity=similarity)
        return similarity
    
    def get_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        embedding = self._get_cached_embedding(text)
        return embedding.tolist()
    
    def batch_embed(self, texts: list[str]) -> np.ndarray:
        """Efficiently embed multiple texts."""
        logger.info("batch_embedding_started", batch_size=len(texts))
        try:
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            logger.info("batch_embedding_completed", batch_size=len(texts), embedding_dim=embeddings.shape[1])
            return embeddings
        except Exception as e:
            logger.error("batch_embedding_failed", batch_size=len(texts), error=str(e))
            raise EmbeddingError(f"batch of {len(texts)} texts", str(e))
    
    def _get_cached_embedding(self, text: str) -> np.ndarray:
        """Get embedding with caching."""
        if text not in self._cache:
            logger.debug("embedding_cache_miss", text_len=len(text), cache_size=len(self._cache))
            try:
                self._cache[text] = self._model.encode(text, convert_to_numpy=True)
            except Exception as e:
                logger.error("embedding_generation_failed", text_len=len(text), error=str(e))
                raise EmbeddingError(text[:50], str(e))
        else:
            logger.debug("embedding_cache_hit", text_len=len(text))
        return self._cache[text]

