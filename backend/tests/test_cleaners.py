"""Test suite for data cleaners.

Demonstrates testing strategy for pure functions.
"""

import pytest
from backend.storage.cleaners import (
    IPACleaner,
    TextNormalizer,
    HeadwordCleaner,
    DefinitionCleaner,
    LanguageCodeCleaner,
)


class TestIPACleaner:
    """Test IPA cleaning and validation."""
    
    def setup_method(self):
        self.cleaner = IPACleaner()
    
    def test_removes_brackets(self):
        assert self.cleaner.clean("[wódr̥]") == "wódr̥"
        assert self.cleaner.clean("/wódr̥/") == "wódr̥"
    
    def test_normalizes_unicode(self):
        # Test NFC normalization
        input_nfd = "wo\u0301dr\u0325"  # NFD: ó and ̥ as combining
        result = self.cleaner.clean(input_nfd)
        assert result == "wódr̥"
    
    def test_removes_whitespace(self):
        assert self.cleaner.clean("  wódr̥  ") == "wódr̥"
        assert self.cleaner.clean("wó  dr̥") == "wó dr̥"
    
    def test_idempotent(self):
        """Cleaning twice should equal cleaning once."""
        value = "  [wódr̥]  "
        once = self.cleaner.clean(value)
        twice = self.cleaner.clean(once)
        assert once == twice
    
    def test_validation(self):
        assert self.cleaner.validate("wódr̥") == True
        assert self.cleaner.validate("aɪ") == True
        assert self.cleaner.validate("") == False


class TestTextNormalizer:
    """Test text normalization."""
    
    def setup_method(self):
        self.cleaner = TextNormalizer()
    
    def test_lowercase(self):
        result = self.cleaner.clean("HELLO World", lowercase=True)
        assert result == "hello world"
    
    def test_preserve_case(self):
        result = self.cleaner.clean("HELLO", lowercase=False)
        assert result == "HELLO"
    
    def test_remove_punctuation(self):
        result = self.cleaner.clean(
            "Hello, world!",
            remove_punctuation=True
        )
        assert result == "hello world"
    
    def test_normalize_whitespace(self):
        result = self.cleaner.clean("  hello   world  ")
        assert result == "hello world"
    
    def test_unicode_normalization(self):
        # Test with different Unicode forms
        nfd = "café"  # é as combining character
        result = self.cleaner.clean(nfd, unicode_form="NFC")
        assert result == "café"


class TestHeadwordCleaner:
    """Test headword cleaning."""
    
    def setup_method(self):
        self.cleaner = HeadwordCleaner()
    
    def test_removes_markers(self):
        assert self.cleaner.clean("*wódr̥") == "wódr̥"
        assert self.cleaner.clean("†obsolete") == "obsolete"
    
    def test_removes_parentheticals(self):
        assert self.cleaner.clean("word (alt)") == "word"
        assert self.cleaner.clean("word (1)") == "word"
    
    def test_normalizes_unicode(self):
        result = self.cleaner.clean("wo\u0301rd")
        assert "word" in result or "wórd" in result


class TestDefinitionCleaner:
    """Test definition cleaning."""
    
    def setup_method(self):
        self.cleaner = DefinitionCleaner()
    
    def test_removes_citations(self):
        text = "Definition with citation[1] and another[2]."
        result = self.cleaner.clean(text)
        assert "[1]" not in result
        assert "[2]" not in result
    
    def test_removes_html(self):
        text = "Definition with <b>bold</b> text."
        result = self.cleaner.clean(text)
        assert "<b>" not in result
        assert result == "Definition with bold text."
    
    def test_truncation(self):
        long_text = "word " * 100
        result = self.cleaner.clean(long_text, max_length=50)
        assert len(result) <= 53  # +3 for "..."
        assert result.endswith("...")


class TestLanguageCodeCleaner:
    """Test language code normalization."""
    
    def setup_method(self):
        self.cleaner = LanguageCodeCleaner()
    
    def test_full_name_to_code(self):
        assert self.cleaner.clean("English") == "en"
        assert self.cleaner.clean("german") == "de"
        assert self.cleaner.clean("LATIN") == "la"
    
    def test_preserves_iso_codes(self):
        assert self.cleaner.clean("en") == "en"
        assert self.cleaner.clean("grc") == "grc"
    
    def test_validation(self):
        assert self.cleaner.validate("en") == True
        assert self.cleaner.validate("grc") == True
        assert self.cleaner.validate("xyz") == False
        assert self.cleaner.validate("English") == False


class TestCleanerComposition:
    """Test composing multiple cleaners."""
    
    def test_pipeline_composition(self):
        from backend.storage.pipeline import Pipeline
        
        pipeline = Pipeline([
            HeadwordCleaner(),
            TextNormalizer(),
        ])
        
        result, steps = pipeline.apply("  *Word (alt)  ")
        
        assert result == "word"
        assert len(steps) == 2
        assert steps[0].name == "headword_cleaner"
        assert steps[1].name == "text_normalizer"


# Property-based tests (if hypothesis is installed)
try:
    from hypothesis import given, strategies as st
    
    class TestCleanerProperties:
        """Property-based tests for cleaners."""
        
        @given(st.text())
        def test_text_normalizer_idempotent(self, text):
            """Normalizing twice should equal normalizing once."""
            cleaner = TextNormalizer()
            once = cleaner.clean(text)
            twice = cleaner.clean(once)
            assert once == twice
        
        @given(st.text(min_size=1))
        def test_cleaner_preserves_type(self, text):
            """Cleaners should preserve type."""
            cleaner = TextNormalizer()
            result = cleaner.clean(text)
            assert isinstance(result, str)

except ImportError:
    pass  # hypothesis not installed

