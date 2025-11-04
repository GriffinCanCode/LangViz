"""Phonetic analysis service.

Integrates Rust-powered distance computation with Python linguistic libraries.
Uses epitran for IPA transcription and panphon for feature extraction.
"""

from typing import Optional

import epitran
import panphon

from backend.core import PhoneticFeatures
from backend.core.contracts import IPhoneticAnalyzer
from backend.observ import get_logger
from backend.errors import InvalidIPAError

logger = get_logger(__name__)

# Try to import Rust backend
try:
    from langviz_core import (
        py_phonetic_distance,
        py_batch_phonetic_distance,
        py_lcs_ratio,
        py_dtw_align,
    )
    RUST_AVAILABLE = True
    logger.info("rust_phonetic_backend_loaded")
except ImportError:
    RUST_AVAILABLE = False
    logger.warning("rust_phonetic_backend_unavailable", fallback="python_panphon")


class PhoneticService(IPhoneticAnalyzer):
    """Orchestrates phonetic analysis using multiple backends."""
    
    def __init__(self, use_rust: bool = True):
        self._feature_table = panphon.FeatureTable()
        self._transliterators: dict[str, epitran.Epitran] = {}
        self._use_rust = use_rust and RUST_AVAILABLE
        
        if self._use_rust:
            logger.info("phonetic_service_initialized", backend="rust")
        else:
            logger.info("phonetic_service_initialized", backend="python_panphon")
        
    def compute_distance(self, ipa_a: str, ipa_b: str) -> float:
        """Compute phonetic distance with Rust acceleration."""
        logger.debug("computing_distance", ipa_a=ipa_a, ipa_b=ipa_b, using_rust=self._use_rust)
        
        if self._use_rust:
            try:
                # Rust returns similarity (1.0 = identical), convert to distance
                similarity = py_phonetic_distance(ipa_a, ipa_b)
                return 1.0 - similarity
            except Exception as e:
                logger.warning("rust_phonetic_distance_failed", error=str(e), fallback=True)
                return self._fallback_distance(ipa_a, ipa_b)
        return self._fallback_distance(ipa_a, ipa_b)
    
    def batch_compute_distance(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Batch compute phonetic distances (parallelized with Rust)."""
        logger.debug("batch_computing_distance", num_pairs=len(pairs), using_rust=self._use_rust)
        
        if self._use_rust:
            try:
                # Rust returns similarities, convert to distances
                similarities = py_batch_phonetic_distance(pairs)
                return [1.0 - sim for sim in similarities]
            except Exception as e:
                logger.warning("rust_batch_distance_failed", error=str(e), fallback=True)
                return [self.compute_distance(a, b) for a, b in pairs]
        return [self.compute_distance(a, b) for a, b in pairs]
    
    def align_sequences(self, ipa_a: str, ipa_b: str) -> dict:
        """Align two IPA sequences using DTW.
        
        Returns alignment with cost and operations.
        """
        if self._use_rust:
            try:
                alignment = py_dtw_align(ipa_a, ipa_b)
                return {
                    "sequence_a": alignment.sequence_a,
                    "sequence_b": alignment.sequence_b,
                    "cost": alignment.cost,
                    "correspondences": alignment.correspondences()
                }
            except Exception as e:
                logger.warning("rust_dtw_failed", error=str(e))
                return {"error": str(e)}
        else:
            logger.warning("dtw_unavailable", reason="rust_backend_required")
            return {"error": "DTW requires Rust backend"}
    
    def lcs_similarity(self, ipa_a: str, ipa_b: str) -> float:
        """Compute longest common subsequence similarity."""
        if self._use_rust:
            try:
                return py_lcs_ratio(ipa_a, ipa_b)
            except Exception as e:
                logger.warning("rust_lcs_failed", error=str(e))
                return 0.0
        else:
            # Simple fallback
            return 0.0
    
    def extract_features(self, ipa: str) -> PhoneticFeatures:
        """Extract panphon features for IPA segment."""
        segments = self._feature_table.word_to_segs(ipa)
        if not segments:
            logger.warning("invalid_ipa_segments", ipa=ipa)
            raise InvalidIPAError(ipa, "No valid segments found")
        
        features = self._feature_table.word_to_vector_list(ipa)[0]
        feature_dict = dict(zip(self._feature_table.names, features))
        
        return PhoneticFeatures(
            ipa=ipa,
            features=feature_dict,
            segment_type=self._classify_segment(feature_dict)
        )
    
    def transcribe(self, text: str, lang_code: str) -> str:
        """Transcribe text to IPA for given language."""
        logger.debug("transcribing_text", text=text, lang_code=lang_code)
        
        if lang_code not in self._transliterators:
            logger.info("initializing_transliterator", lang_code=lang_code)
            self._transliterators[lang_code] = epitran.Epitran(lang_code)
        
        return self._transliterators[lang_code].transliterate(text)
    
    def _fallback_distance(self, ipa_a: str, ipa_b: str) -> float:
        """Feature-based distance when Rust unavailable."""
        distance = self._feature_table.feature_edit_distance(ipa_a, ipa_b)
        max_len = max(len(ipa_a), len(ipa_b))
        return 1.0 - (distance / max_len) if max_len > 0 else 0.0
    
    def _classify_segment(self, features: dict[str, int]) -> str:
        """Classify phoneme type from features."""
        if features.get("syl", 0) == 1:
            return "vowel"
        if features.get("son", 0) == -1:
            return "consonant"
        return "sonorant"

