"""Core type definitions for the Indo-European Etymology system.

Provides immutable domain models with strict typing.
All entities are Pydantic models for validation and serialization.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from numpy.typing import NDArray


class LanguageBranch(str, Enum):
    """Major Indo-European language branches."""
    INDO_IRANIAN = "indo_iranian"
    HELLENIC = "hellenic"
    ITALIC = "italic"
    GERMANIC = "germanic"
    CELTIC = "celtic"
    BALTO_SLAVIC = "balto_slavic"
    ARMENIAN = "armenian"
    ALBANIAN = "albanian"
    ANATOLIAN = "anatolian"
    TOCHARIAN = "tocharian"


class Language(BaseModel):
    """Represents a language with metadata."""
    model_config = ConfigDict(frozen=True)
    
    iso_code: str = Field(min_length=2, max_length=3)
    name: str
    branch: LanguageBranch
    subfamily: Optional[str] = None
    coordinates: Optional[tuple[float, float]] = None


class Entry(BaseModel):
    """Lexical entry with phonetic and semantic metadata."""
    model_config = ConfigDict(frozen=True)
    
    id: str
    headword: str
    ipa: str
    language: str  # ISO code
    definition: str
    etymology: Optional[str] = None
    pos_tag: Optional[str] = None
    embedding: Optional[list[float]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SimilarityScore(BaseModel):
    """Pairwise similarity metrics between entries."""
    model_config = ConfigDict(frozen=True)
    
    entry_a: str
    entry_b: str
    phonetic: float = Field(ge=0.0, le=1.0)
    semantic: float = Field(ge=0.0, le=1.0)
    combined: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class CognateSet(BaseModel):
    """Group of cognate entries with shared etymology."""
    model_config = ConfigDict(frozen=True)
    
    id: str
    entries: list[str]  # Entry IDs
    confidence: float = Field(ge=0.0, le=1.0)
    proto_form: Optional[str] = None
    semantic_core: str


class PhoneticFeatures(BaseModel):
    """Phonological feature vector for sounds."""
    model_config = ConfigDict(frozen=True)
    
    ipa: str
    features: dict[str, int]  # Feature name -> binary value
    segment_type: str  # consonant, vowel, etc.

