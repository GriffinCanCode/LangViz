"""Data provenance and lineage tracking.

Immutable record of data transformations and source attribution.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Classification of data sources."""
    COMPARATIVE_WORDLIST = "comparative_wordlist"
    ETYMOLOGICAL = "etymological"
    FULL_DICTIONARY = "full_dictionary"
    COGNATE_PAIRS = "cognate_pairs"
    COGNATE_SETS = "cognate_sets"


class DataQuality(str, Enum):
    """Quality assessment levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class Source(BaseModel):
    """Metadata about a data source."""
    model_config = {"frozen": True}
    
    id: str
    name: str
    type: SourceType
    format: str
    url: str
    languages: list[str]
    license: str
    quality: DataQuality
    version: Optional[str] = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)


class TransformStep(BaseModel):
    """Single transformation in processing pipeline."""
    model_config = {"frozen": True}
    
    id: str
    name: str
    version: str
    parameters: dict[str, object]
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: Optional[int] = None


class Provenance(BaseModel):
    """Complete lineage of a data record."""
    model_config = {"frozen": True}
    
    record_id: str
    source: Source
    transforms: list[TransformStep]
    checksum: str  # SHA-256 of raw data
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def pipeline_version(self) -> str:
        """Version identifier for entire pipeline."""
        steps = "_".join(f"{t.name}:{t.version}" for t in self.transforms)
        return f"{self.source.id}_{steps}"

