"""Composable data cleaning transformations.

Pure functions implementing ICleaner protocol.
Each cleaner is single-purpose, testable, and composable.
"""

import re
import unicodedata
from typing import Optional
from dataclasses import dataclass
import panphon


@dataclass(frozen=True)
class IPACleaner:
    """Normalize and validate IPA transcriptions."""
    
    name: str = "ipa_cleaner"
    version: str = "1.0.0"
    
    def __post_init__(self):
        object.__setattr__(self, '_feature_table', panphon.FeatureTable())
    
    def clean(self, ipa: str, **params) -> str:
        """Normalize IPA string."""
        # Unicode normalization to NFC (canonical composition)
        normalized = unicodedata.normalize('NFC', ipa.strip())
        
        # Remove brackets if present
        normalized = re.sub(r'[\[\]/]', '', normalized)
        
        # Standardize stress markers
        normalized = normalized.replace('ˈ', 'ˈ').replace('ˌ', 'ˌ')
        
        # Remove multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized
    
    def validate(self, ipa: str) -> bool:
        """Check if IPA string is valid."""
        try:
            # Check if panphon can parse all segments
            segs = self._feature_table.word_to_segs(ipa)
            return len(segs) > 0
        except:
            return False


@dataclass(frozen=True)
class TextNormalizer:
    """Normalize text with configurable operations."""
    
    name: str = "text_normalizer"
    version: str = "1.0.0"
    
    def clean(
        self,
        text: str,
        lowercase: bool = True,
        remove_punctuation: bool = False,
        normalize_whitespace: bool = True,
        unicode_form: str = "NFC",
        **params
    ) -> str:
        """Apply text normalization pipeline."""
        result = text
        
        # Unicode normalization
        if unicode_form in ('NFC', 'NFD', 'NFKC', 'NFKD'):
            result = unicodedata.normalize(unicode_form, result)
        
        # Lowercase
        if lowercase:
            result = result.lower()
        
        # Remove punctuation
        if remove_punctuation:
            result = re.sub(r'[^\w\s]', '', result)
        
        # Normalize whitespace
        if normalize_whitespace:
            result = re.sub(r'\s+', ' ', result.strip())
        
        return result
    
    def validate(self, text: str) -> bool:
        """Check if text is valid."""
        return bool(text and text.strip())


@dataclass(frozen=True)
class HeadwordCleaner:
    """Clean dictionary headwords."""
    
    name: str = "headword_cleaner"
    version: str = "1.0.0"
    
    def clean(self, headword: str, **params) -> str:
        """Clean headword, removing markers and normalizing."""
        # Remove common dictionary markers
        cleaned = re.sub(r'[*†‡§¶]', '', headword)
        
        # Remove parentheticals (often contain alternate forms)
        cleaned = re.sub(r'\([^)]*\)', '', cleaned)
        
        # Unicode normalization
        cleaned = unicodedata.normalize('NFC', cleaned)
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned.strip())
        
        return cleaned
    
    def validate(self, headword: str) -> bool:
        """Check if headword is valid."""
        return bool(headword and len(headword.strip()) > 0)


@dataclass(frozen=True)
class DefinitionCleaner:
    """Clean and normalize definitions."""
    
    name: str = "definition_cleaner"
    version: str = "1.0.0"
    
    def clean(
        self,
        definition: str,
        remove_citations: bool = True,
        max_length: Optional[int] = None,
        **params
    ) -> str:
        """Clean definition text."""
        cleaned = definition
        
        # Remove citation markers [1], [2], etc.
        if remove_citations:
            cleaned = re.sub(r'\[\d+\]', '', cleaned)
        
        # Remove HTML tags
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        
        # Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned.strip())
        
        # Truncate if needed
        if max_length and len(cleaned) > max_length:
            cleaned = cleaned[:max_length].rsplit(' ', 1)[0] + '...'
        
        return cleaned
    
    def validate(self, definition: str) -> bool:
        """Check if definition is valid."""
        return bool(definition and len(definition.strip()) >= 3)


@dataclass(frozen=True)
class LanguageCodeCleaner:
    """Normalize language codes to ISO 639."""
    
    name: str = "language_code_cleaner"
    version: str = "1.0.0"
    
    # Common mappings to ISO codes
    _mappings: dict[str, str] = None
    
    def __post_init__(self):
        mappings = {
            'english': 'en',
            'german': 'de',
            'french': 'fr',
            'spanish': 'es',
            'italian': 'it',
            'portuguese': 'pt',
            'russian': 'ru',
            'polish': 'pl',
            'latin': 'la',
            'greek': 'grc',
            'ancient greek': 'grc',
            'sanskrit': 'sa',
            'hindi': 'hi',
            'persian': 'fa',
            'dutch': 'nl',
            'swedish': 'sv',
            'norwegian': 'no',
            'danish': 'da',
            'icelandic': 'is',
            'proto-indo-european': 'pie',
        }
        object.__setattr__(self, '_mappings', mappings)
    
    def clean(self, code: str, **params) -> str:
        """Normalize language code."""
        code_lower = code.lower().strip()
        
        # If it's a full name, map to ISO code
        if code_lower in self._mappings:
            return self._mappings[code_lower]
        
        # If it's already an ISO code (2-3 letters)
        if re.match(r'^[a-z]{2,3}$', code_lower):
            return code_lower
        
        # Default: return lowercase
        return code_lower
    
    def validate(self, code: str) -> bool:
        """Check if language code is valid."""
        return bool(code and re.match(r'^[a-z]{2,3}$', code.lower()))


@dataclass(frozen=True)
class DuplicateDetector:
    """Detect and handle duplicates."""
    
    name: str = "duplicate_detector"
    version: str = "1.0.0"
    
    def detect_duplicates(
        self,
        entries: list[dict],
        key_fields: list[str]
    ) -> list[tuple[int, int]]:
        """Find duplicate entries based on key fields.
        
        Returns list of (index_a, index_b) tuples for duplicates.
        """
        seen = {}
        duplicates = []
        
        for idx, entry in enumerate(entries):
            # Create key from specified fields
            key = tuple(entry.get(field) for field in key_fields)
            
            if key in seen:
                duplicates.append((seen[key], idx))
            else:
                seen[key] = idx
        
        return duplicates
    
    def clean(self, entries: list[dict], **params) -> list[dict]:
        """Remove duplicates, keeping first occurrence."""
        key_fields = params.get('key_fields', ['headword', 'language'])
        seen = set()
        unique = []
        
        for entry in entries:
            key = tuple(entry.get(field) for field in key_fields)
            if key not in seen:
                seen.add(key)
                unique.append(entry)
        
        return unique
    
    def validate(self, entries: list[dict]) -> bool:
        """Check if there are no duplicates."""
        key_fields = ['headword', 'language']
        duplicates = self.detect_duplicates(entries, key_fields)
        return len(duplicates) == 0

