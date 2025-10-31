"""Phonetic analysis service.

Integrates Rust-powered distance computation with Python linguistic libraries.
Uses epitran for IPA transcription and panphon for feature extraction.
"""

from typing import Optional
import epitran
import panphon
from backend.core import PhoneticFeatures
from backend.core.contracts import IPhoneticAnalyzer


class PhoneticService(IPhoneticAnalyzer):
    """Orchestrates phonetic analysis using multiple backends."""
    
    def __init__(self):
        self._feature_table = panphon.FeatureTable()
        self._transliterators: dict[str, epitran.Epitran] = {}
        # Rust module will be imported when available
        self._rust_backend: Optional[object] = None
        
    def compute_distance(self, ipa_a: str, ipa_b: str) -> float:
        """Compute phonetic distance with Rust acceleration."""
        if self._rust_backend:
            return self._rust_backend.phonetic_distance(ipa_a, ipa_b)
        return self._fallback_distance(ipa_a, ipa_b)
    
    def extract_features(self, ipa: str) -> PhoneticFeatures:
        """Extract panphon features for IPA segment."""
        segments = self._feature_table.word_to_segs(ipa)
        if not segments:
            raise ValueError(f"Invalid IPA string: {ipa}")
        
        features = self._feature_table.word_to_vector_list(ipa)[0]
        feature_dict = dict(zip(self._feature_table.names, features))
        
        return PhoneticFeatures(
            ipa=ipa,
            features=feature_dict,
            segment_type=self._classify_segment(feature_dict)
        )
    
    def transcribe(self, text: str, lang_code: str) -> str:
        """Transcribe text to IPA for given language."""
        if lang_code not in self._transliterators:
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

