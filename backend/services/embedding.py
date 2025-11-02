"""Optimized embedding service with GPU acceleration and batching.

Designed for high-throughput processing of millions of entries.
Key optimizations:
- GPU acceleration (CUDA/MPS)
- Large batch processing (512-2048 entries)
- Async processing with queue
- Memory-efficient streaming
"""

import asyncio
import torch
import numpy as np
from typing import AsyncIterator, Optional
from collections.abc import Sequence
from sentence_transformers import SentenceTransformer

from backend.core.contracts import ISemanticAnalyzer
from backend.observ import get_logger
from backend.errors import EmbeddingError

logger = get_logger(__name__)


class OptimizedEmbeddingService(ISemanticAnalyzer):
    """GPU-accelerated embedding service for high-throughput processing."""
    
    def __init__(
        self,
        model_name: str = "paraphrase-multilingual-mpnet-base-v2",
        device: Optional[str] = None,
        batch_size: int = 512  # Larger batches for GPU
    ):
        logger.info("initializing_optimized_embedding_service", model_name=model_name)
        
        # Auto-detect best device
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
                logger.info("gpu_detected", device="CUDA", gpu_count=torch.cuda.device_count())
            elif torch.backends.mps.is_available():
                device = "mps"
                logger.info("gpu_detected", device="Apple MPS")
            else:
                device = "cpu"
                logger.warning("no_gpu_detected", device="CPU", performance="degraded")
        
        self._model = SentenceTransformer(model_name, device=device)
        self._device = device
        self._batch_size = batch_size
        self._cache: dict[str, np.ndarray] = {}
        
        # Enable GPU optimizations
        if device in ["cuda", "mps"]:
            # Use mixed precision for faster inference
            self._model.half() if device == "cuda" else None
            logger.info(
                "optimized_embedding_service_ready",
                device=device,
                batch_size=batch_size,
                precision="fp16" if device == "cuda" else "fp32"
            )
    
    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity between texts."""
        embedding_a = self._get_cached_embedding(text_a)
        embedding_b = self._get_cached_embedding(text_b)
        return float(np.dot(embedding_a, embedding_b))
    
    def get_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        embedding = self._get_cached_embedding(text)
        return embedding.tolist()
    
    def batch_embed(
        self,
        texts: Sequence[str],
        show_progress: bool = False
    ) -> np.ndarray:
        """Efficiently embed multiple texts with GPU acceleration.
        
        Args:
            texts: Sequence of texts to embed
            show_progress: Show progress bar
            
        Returns:
            Array of embeddings (N, 768)
        """
        if not texts:
            return np.array([])
        
        logger.info(
            "batch_embedding_started",
            batch_size=len(texts),
            device=self._device,
            gpu_batch_size=self._batch_size
        )
        
        try:
            # Use sentence-transformers built-in batching
            # It handles GPU memory management automatically
            embeddings = self._model.encode(
                texts,
                batch_size=self._batch_size,
                convert_to_numpy=True,
                show_progress_bar=show_progress,
                normalize_embeddings=True,  # Normalize for cosine similarity
                device=self._device
            )
            
            logger.info(
                "batch_embedding_completed",
                batch_size=len(texts),
                embedding_dim=embeddings.shape[1],
                device=self._device
            )
            
            return embeddings
            
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                logger.warning(
                    "gpu_oom_fallback",
                    original_batch=self._batch_size,
                    fallback_batch=self._batch_size // 2
                )
                # Fallback to smaller batches
                self._batch_size = self._batch_size // 2
                return self.batch_embed(texts, show_progress)
            raise EmbeddingError(f"batch of {len(texts)} texts", str(e))
        except Exception as e:
            logger.error("batch_embedding_failed", batch_size=len(texts), error=str(e))
            raise EmbeddingError(f"batch of {len(texts)} texts", str(e))
    
    async def stream_embed(
        self,
        texts: AsyncIterator[list[str]],
        output_queue: asyncio.Queue
    ) -> None:
        """Stream embeddings asynchronously for pipeline processing.
        
        Processes batches from an async iterator and puts results in queue.
        Enables producer-consumer pattern for parallel processing.
        """
        batch_count = 0
        
        async for text_batch in texts:
            if not text_batch:
                continue
                
            # Run embedding in thread pool (blocking operation)
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                self.batch_embed,
                text_batch,
                False
            )
            
            # Put in output queue
            await output_queue.put((text_batch, embeddings))
            batch_count += 1
            
            if batch_count % 10 == 0:
                logger.info("stream_embed_progress", batches_processed=batch_count)
        
        # Signal completion
        await output_queue.put(None)
        logger.info("stream_embed_completed", total_batches=batch_count)
    
    def _get_cached_embedding(self, text: str) -> np.ndarray:
        """Get embedding with caching."""
        if text not in self._cache:
            self._cache[text] = self._model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
        return self._cache[text]
    
    def clear_cache(self) -> None:
        """Clear embedding cache to free memory."""
        cache_size = len(self._cache)
        self._cache.clear()
        logger.info("cache_cleared", entries=cache_size)
    
    @property
    def device_info(self) -> dict:
        """Get device information."""
        info = {
            "device": self._device,
            "batch_size": self._batch_size,
            "cache_size": len(self._cache)
        }
        
        if self._device == "cuda":
            info.update({
                "gpu_name": torch.cuda.get_device_name(0),
                "gpu_memory_allocated": torch.cuda.memory_allocated(0) / 1e9,
                "gpu_memory_reserved": torch.cuda.memory_reserved(0) / 1e9
            })
        
        return info

