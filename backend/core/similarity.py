"""Core similarity types and contracts for multi-layered architecture.

Defines the fundamental abstractions for semantic, phonetic, and etymological similarity.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class SimilarityMode(str, Enum):
    """Query modes that influence similarity weighting."""
    COGNATE_DETECTION = "cognate"
    SEMANTIC_SEARCH = "semantic"
    HISTORICAL_RECONSTRUCTION = "historical"
    BALANCED = "balanced"


class ConceptID(BaseModel):
    """Unique identifier for cross-lingual semantic concept."""
    model_config = ConfigDict(frozen=True)
    
    id: str
    label: str  # Human-readable label
    confidence: float = Field(ge=0.0, le=1.0)
    member_count: int = Field(ge=0)


class PhoneticAlignment(BaseModel):
    """Result of phonetic sequence alignment."""
    model_config = ConfigDict(frozen=True)
    
    sequence_a: str  # IPA
    sequence_b: str  # IPA
    aligned_a: str  # With gaps
    aligned_b: str  # With gaps
    distance: float  # DTW distance
    correspondence_rules: list[tuple[str, str]]  # Detected sound changes


class LayeredSimilarity(BaseModel):
    """Multi-modal similarity score with component breakdown."""
    model_config = ConfigDict(frozen=True)
    
    entry_a: str
    entry_b: str
    
    # Component scores
    semantic: float = Field(ge=0.0, le=1.0)
    phonetic: float = Field(ge=0.0, le=1.0)
    etymological: float = Field(ge=0.0, le=1.0)
    
    # Combined score
    combined: float = Field(ge=0.0, le=1.0)
    
    # Weights used
    weights: dict[str, float]
    
    # Supporting evidence
    concept_a: Optional[str] = None
    concept_b: Optional[str] = None
    phylogenetic_distance: Optional[int] = None
    alignment: Optional[PhoneticAlignment] = None


class PhylogeneticNode(BaseModel):
    """Node in language family tree."""
    model_config = ConfigDict(frozen=True)
    
    id: str
    name: str
    parent: Optional[str] = None
    children: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)  # ISO codes at this node
    depth: int = 0


class LexicalDifference(BaseModel):
    """Analysis of why two languages use different words for same concept."""
    model_config = ConfigDict(frozen=True)
    
    concept: str
    language_a: str
    language_b: str
    form_a: str
    form_b: str
    
    # Cognate cluster assignments
    cluster_a: str
    cluster_b: str
    
    # Related forms in other languages
    cognates_a: dict[str, str]  # lang_code → form
    cognates_b: dict[str, str]
    
    # Phylogenetic context
    tree_distance: int
    
    # Generated explanation
    explanation: str
    historical_note: Optional[str] = None


class ConceptCluster(BaseModel):
    """Auto-discovered semantic concept from embeddings."""
    model_config = ConfigDict(frozen=True)
    
    id: str
    centroid: list[float]  # Mean embedding
    member_ids: list[str]  # Entry IDs
    languages: list[str]  # Languages represented
    sample_definitions: list[str]  # Top 5 for labeling
    confidence: float = Field(ge=0.0, le=1.0)
    size: int = Field(ge=0)


class SimilarityWeights(BaseModel):
    """Configurable weights for similarity components."""
    model_config = ConfigDict(frozen=True)
    
    semantic: float = Field(ge=0.0, le=1.0)
    phonetic: float = Field(ge=0.0, le=1.0)
    etymological: float = Field(ge=0.0, le=1.0)
    
    def validate_sum(self) -> bool:
        """Ensure weights sum to 1.0."""
        return abs(sum([self.semantic, self.phonetic, self.etymological]) - 1.0) < 0.01
    
    @classmethod
    def for_mode(cls, mode: SimilarityMode) -> 'SimilarityWeights':
        """Get weights optimized for query mode."""
        presets = {
            SimilarityMode.COGNATE_DETECTION: cls(semantic=0.3, phonetic=0.6, etymological=0.1),
            SimilarityMode.SEMANTIC_SEARCH: cls(semantic=0.7, phonetic=0.2, etymological=0.1),
            SimilarityMode.HISTORICAL_RECONSTRUCTION: cls(semantic=0.1, phonetic=0.4, etymological=0.5),
            SimilarityMode.BALANCED: cls(semantic=0.4, phonetic=0.4, etymological=0.2),
        }
        return presets[mode]


class PhoneticHash(BaseModel):
    """LSH hash for approximate phonetic search."""
    model_config = ConfigDict(frozen=True)
    
    ipa: str
    hashes: list[int]  # k hash values for LSH
    num_phonemes: int
    has_clusters: bool  # Contains consonant clusters
    has_rare_sounds: bool  # Contains sounds rare in IE

