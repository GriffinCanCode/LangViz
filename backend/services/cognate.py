"""Cognate detection service.

Implements LingPy-based cognate detection with custom scoring.
Combines phonetic and semantic signals for cognate identification.
"""

from typing import Optional
from collections import defaultdict
import lingpy
from backend.core import Entry, CognateSet, SimilarityScore
from backend.core.contracts import ICognateDetector, IPhoneticAnalyzer, ISemanticAnalyzer


class CognateService(ICognateDetector):
    """Detects cognate sets using multi-modal similarity."""
    
    def __init__(
        self,
        phonetic: IPhoneticAnalyzer,
        semantic: ISemanticAnalyzer,
        threshold: float = 0.7
    ):
        self._phonetic = phonetic
        self._semantic = semantic
        self._threshold = threshold
        
    def detect_cognates(self, entries: list[Entry]) -> list[CognateSet]:
        """Cluster entries into cognate sets."""
        similarity_matrix = self._build_similarity_matrix(entries)
        clusters = self._cluster_entries(entries, similarity_matrix)
        
        return [
            CognateSet(
                id=f"cognate_set_{i}",
                entries=[e.id for e in cluster],
                confidence=self._compute_set_confidence(cluster, similarity_matrix),
                proto_form=None,  # TODO: Reconstruct proto-form
                semantic_core=self._extract_semantic_core(cluster)
            )
            for i, cluster in enumerate(clusters)
        ]
    
    def compute_confidence(self, entry_a: Entry, entry_b: Entry) -> float:
        """Compute cognate confidence score."""
        phonetic_score = self._phonetic.compute_distance(entry_a.ipa, entry_b.ipa)
        semantic_score = self._semantic.compute_similarity(
            entry_a.definition,
            entry_b.definition
        )
        return self._combine_scores(phonetic_score, semantic_score)
    
    def _build_similarity_matrix(
        self,
        entries: list[Entry]
    ) -> dict[tuple[str, str], SimilarityScore]:
        """Build pairwise similarity matrix."""
        matrix = {}
        for i, entry_a in enumerate(entries):
            for entry_b in entries[i + 1:]:
                phonetic = self._phonetic.compute_distance(entry_a.ipa, entry_b.ipa)
                semantic = self._semantic.compute_similarity(
                    entry_a.definition,
                    entry_b.definition
                )
                combined = self._combine_scores(phonetic, semantic)
                
                matrix[(entry_a.id, entry_b.id)] = SimilarityScore(
                    entry_a=entry_a.id,
                    entry_b=entry_b.id,
                    phonetic=phonetic,
                    semantic=semantic,
                    combined=combined,
                    confidence=combined
                )
        return matrix
    
    def _cluster_entries(
        self,
        entries: list[Entry],
        matrix: dict[tuple[str, str], SimilarityScore]
    ) -> list[list[Entry]]:
        """Cluster entries using threshold-based approach."""
        clusters = []
        assigned = set()
        
        for entry in entries:
            if entry.id in assigned:
                continue
                
            cluster = [entry]
            assigned.add(entry.id)
            
            for other in entries:
                if other.id in assigned:
                    continue
                    
                key = (
                    (entry.id, other.id)
                    if entry.id < other.id
                    else (other.id, entry.id)
                )
                
                if key in matrix and matrix[key].combined >= self._threshold:
                    cluster.append(other)
                    assigned.add(other.id)
            
            clusters.append(cluster)
        
        return clusters
    
    def _combine_scores(self, phonetic: float, semantic: float) -> float:
        """Weighted combination of phonetic and semantic scores."""
        return 0.6 * phonetic + 0.4 * semantic
    
    def _compute_set_confidence(
        self,
        cluster: list[Entry],
        matrix: dict[tuple[str, str], SimilarityScore]
    ) -> float:
        """Average confidence across cluster pairs."""
        if len(cluster) < 2:
            return 1.0
            
        scores = []
        for i, entry_a in enumerate(cluster):
            for entry_b in cluster[i + 1:]:
                key = (
                    (entry_a.id, entry_b.id)
                    if entry_a.id < entry_b.id
                    else (entry_b.id, entry_a.id)
                )
                if key in matrix:
                    scores.append(matrix[key].combined)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _extract_semantic_core(self, cluster: list[Entry]) -> str:
        """Extract common semantic meaning from cluster."""
        # Simple implementation: return first definition
        # TODO: Use NLP to extract common semantic components
        return cluster[0].definition if cluster else ""

