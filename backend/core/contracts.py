"""Service contracts and interfaces.

Defines protocols for dependency injection and testing.
"""

from abc import ABC, abstractmethod
from typing import Protocol, TypeVar
from .types import Entry, SimilarityScore, CognateSet, PhoneticFeatures


T = TypeVar('T')


class IPhoneticAnalyzer(Protocol):
    """Contract for phonetic distance computation services."""
    
    def compute_distance(self, ipa_a: str, ipa_b: str) -> float:
        """Compute phonetic distance between IPA strings."""
        ...
    
    def extract_features(self, ipa: str) -> PhoneticFeatures:
        """Extract phonological features from IPA string."""
        ...


class ISemanticAnalyzer(Protocol):
    """Contract for semantic similarity services."""
    
    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """Compute semantic similarity between definitions."""
        ...
    
    def get_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        ...


class IParser(Protocol):
    """Contract for dictionary parsing services."""
    
    def parse_dictionary(self, filepath: str) -> list[Entry]:
        """Parse dictionary file to normalized entries."""
        ...
    
    def normalize_text(self, text: str) -> str:
        """Normalize and clean input text."""
        ...


class ICognateDetector(Protocol):
    """Contract for cognate detection services."""
    
    def detect_cognates(self, entries: list[Entry]) -> list[CognateSet]:
        """Detect cognate sets from entry list."""
        ...
    
    def compute_confidence(self, entry_a: Entry, entry_b: Entry) -> float:
        """Compute cognate confidence score."""
        ...


class ICleaner(Protocol):
    """Contract for data cleaning operations.
    
    Cleaners are pure, composable transformation functions.
    """
    
    @property
    def name(self) -> str:
        """Cleaner identifier."""
        ...
    
    @property
    def version(self) -> str:
        """Cleaner version for provenance tracking."""
        ...
    
    def clean(self, value: T, **params) -> T:
        """Apply cleaning transformation.
        
        Must be idempotent and side-effect free.
        """
        ...
    
    def validate(self, value: T) -> bool:
        """Check if value passes validation."""
        ...


class IValidator(Protocol):
    """Contract for data validation."""
    
    def validate(self, data: object) -> tuple[bool, list[str]]:
        """Validate data, returning success and error messages."""
        ...


class IRepository(ABC):
    """Base repository interface for data access."""
    
    @abstractmethod
    async def get_by_id(self, id: str):
        """Retrieve entity by ID."""
        pass
    
    @abstractmethod
    async def save(self, entity) -> str:
        """Persist entity and return ID."""
        pass
    
    @abstractmethod
    async def query(self, **filters):
        """Query entities with filters."""
        pass
