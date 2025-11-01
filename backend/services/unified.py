"""Unified similarity service combining semantic, phonetic, and phylogenetic signals.

Implements the multi-layered similarity architecture with adaptive weighting.
"""

from typing import Optional
from dataclasses import dataclass
import numpy as np

from backend.core.types import Entry
from backend.core.similarity import (
    LayeredSimilarity,
    SimilarityMode,
    SimilarityWeights,
    PhoneticAlignment,
    LexicalDifference
)
from backend.services.semantic import SemanticService
from backend.services.phonetic import PhoneticService
from backend.services.phylogeny import PhylogeneticTree
from backend.services.concepts import ConceptAligner
from backend.observ import get_logger

logger = get_logger(__name__)


@dataclass
class UnifiedSimilarityService:
    """Computes multi-modal similarity with adaptive weighting.
    
    Combines:
    - Semantic similarity (transformer embeddings)
    - Phonetic distance (feature-based alignment)
    - Phylogenetic priors (tree distance)
    
    Weights adapt based on query mode.
    """
    
    semantic: SemanticService
    phonetic: PhoneticService
    phylogeny: PhylogeneticTree
    concepts: ConceptAligner
    
    def compute_similarity(
        self,
        entry_a: Entry,
        entry_b: Entry,
        mode: SimilarityMode = SimilarityMode.BALANCED,
        custom_weights: Optional[SimilarityWeights] = None
    ) -> LayeredSimilarity:
        """Compute multi-layered similarity between entries.
        
        Args:
            entry_a: First entry
            entry_b: Second entry
            mode: Query mode (influences weights)
            custom_weights: Override default weights
            
        Returns:
            LayeredSimilarity with component breakdown
        """
        
        # Get weights for mode
        weights = custom_weights or SimilarityWeights.for_mode(mode)
        
        # Compute semantic similarity
        semantic_score = self.semantic.compute_similarity(
            entry_a.definition,
            entry_b.definition
        )
        
        # Compute phonetic distance
        phonetic_dist = self.phonetic.compute_distance(entry_a.ipa, entry_b.ipa)
        phonetic_score = 1.0 - phonetic_dist  # Convert distance to similarity
        
        # Compute phylogenetic prior
        tree_dist = self.phylogeny.path_distance(entry_a.language, entry_b.language)
        
        # Log warning for unknown languages
        if tree_dist == 999:
            logger.warning(
                f"Unknown language pair: {entry_a.language} <-> {entry_b.language}. "
                f"Using minimal etymological prior."
            )
        elif tree_dist == 15:
            logger.debug(
                f"Cross-family comparison: {entry_a.language} ({self.phylogeny.get_family(entry_a.language)}) "
                f"<-> {entry_b.language} ({self.phylogeny.get_family(entry_b.language)})"
            )
        
        prior = self.phylogeny.cognate_prior(tree_dist)
        
        # Bayesian combination: P(cognate | evidence, tree)
        # Simplified: weight prior by evidence strength
        evidence_strength = (semantic_score + phonetic_score) / 2
        etymological_score = prior * evidence_strength + (1 - evidence_strength) * 0.1
        
        # Weighted combination
        combined = (
            weights.semantic * semantic_score +
            weights.phonetic * phonetic_score +
            weights.etymological * etymological_score
        )
        
        # Get concept assignments
        concept_a, _ = self.concepts.assign_concept(entry_a)
        concept_b, _ = self.concepts.assign_concept(entry_b)
        
        return LayeredSimilarity(
            entry_a=entry_a.id,
            entry_b=entry_b.id,
            semantic=semantic_score,
            phonetic=phonetic_score,
            etymological=etymological_score,
            combined=combined,
            weights={
                "semantic": weights.semantic,
                "phonetic": weights.phonetic,
                "etymological": weights.etymological
            },
            concept_a=concept_a.id,
            concept_b=concept_b.id,
            phylogenetic_distance=tree_dist,
            alignment=None  # TODO: Add alignment details
        )
    
    def batch_similarity(
        self,
        entries: list[Entry],
        mode: SimilarityMode = SimilarityMode.BALANCED
    ) -> list[list[LayeredSimilarity]]:
        """Compute pairwise similarities for batch of entries.
        
        Optimized with vectorized operations where possible.
        
        Returns:
            Matrix of similarities (upper triangular)
        """
        
        n = len(entries)
        results = [[None for _ in range(n)] for _ in range(n)]
        
        # Batch embed all definitions
        definitions = [e.definition for e in entries]
        embeddings = self.semantic.batch_embed(definitions)
        
        # Compute semantic similarities (vectorized)
        semantic_matrix = embeddings @ embeddings.T
        
        # Compute other metrics pairwise
        for i in range(n):
            for j in range(i + 1, n):
                entry_a = entries[i]
                entry_b = entries[j]
                
                # Semantic (from precomputed matrix)
                semantic_score = float(semantic_matrix[i, j])
                
                # Phonetic
                phonetic_dist = self.phonetic.compute_distance(
                    entry_a.ipa,
                    entry_b.ipa
                )
                phonetic_score = 1.0 - phonetic_dist
                
                # Phylogenetic
                tree_dist = self.phylogeny.path_distance(
                    entry_a.language,
                    entry_b.language
                )
                prior = self.phylogeny.cognate_prior(tree_dist)
                evidence = (semantic_score + phonetic_score) / 2
                etymological_score = prior * evidence + (1 - evidence) * 0.1
                
                # Combine
                weights = SimilarityWeights.for_mode(mode)
                combined = (
                    weights.semantic * semantic_score +
                    weights.phonetic * phonetic_score +
                    weights.etymological * etymological_score
                )
                
                results[i][j] = LayeredSimilarity(
                    entry_a=entry_a.id,
                    entry_b=entry_b.id,
                    semantic=semantic_score,
                    phonetic=phonetic_score,
                    etymological=etymological_score,
                    combined=combined,
                    weights={
                        "semantic": weights.semantic,
                        "phonetic": weights.phonetic,
                        "etymological": weights.etymological
                    },
                    phylogenetic_distance=tree_dist
                )
        
        return results
    
    def explain_difference(
        self,
        concept: str,
        lang_a: str,
        lang_b: str,
        entries_a: list[Entry],
        entries_b: list[Entry],
        all_entries: list[Entry]
    ) -> LexicalDifference:
        """Analyze why two languages use different words for same concept.
        
        Example: Why does Ukrainian use 'tak' but Russian use 'da' for 'yes'?
        
        Args:
            concept: Concept ID (e.g., "AFFIRMATION")
            lang_a: First language ISO code
            lang_b: Second language ISO code
            entries_a: Entries for concept in language A
            entries_b: Entries for concept in language B
            all_entries: All entries for this concept across all languages
            
        Returns:
            LexicalDifference with explanation and cognate analysis
        """
        
        if not entries_a or not entries_b:
            raise ValueError("Need at least one entry per language")
        
        # Use primary forms
        form_a = entries_a[0]
        form_b = entries_b[0]
        
        # Compute similarity
        sim = self.compute_similarity(form_a, form_b, SimilarityMode.COGNATE_DETECTION)
        
        # Find cognate clusters across all languages
        cognate_clusters = self._cluster_cognates(all_entries)
        
        # Assign to clusters
        cluster_a = self._find_cluster(form_a, cognate_clusters)
        cluster_b = self._find_cluster(form_b, cognate_clusters)
        
        # Extract cognate distributions
        cognates_a = {
            e.language: e.headword
            for e in cognate_clusters.get(cluster_a, [])
            if e.id != form_a.id
        }
        cognates_b = {
            e.language: e.headword
            for e in cognate_clusters.get(cluster_b, [])
            if e.id != form_b.id
        }
        
        # Get phylogenetic context
        tree_dist = self.phylogeny.path_distance(lang_a, lang_b)
        
        # Generate explanation
        explanation = self._generate_explanation(
            lang_a, lang_b, form_a, form_b,
            cluster_a, cluster_b,
            cognates_a, cognates_b,
            tree_dist, sim
        )
        
        return LexicalDifference(
            concept=concept,
            language_a=lang_a,
            language_b=lang_b,
            form_a=form_a.headword,
            form_b=form_b.headword,
            cluster_a=cluster_a,
            cluster_b=cluster_b,
            cognates_a=cognates_a,
            cognates_b=cognates_b,
            tree_distance=tree_dist,
            explanation=explanation
        )
    
    def _cluster_cognates(self, entries: list[Entry]) -> dict[str, list[Entry]]:
        """Cluster entries into cognate sets.
        
        Uses phonetic + semantic similarity with threshold.
        """
        
        if not entries:
            return {}
        
        # Compute pairwise similarities
        similarities = self.batch_similarity(entries, SimilarityMode.COGNATE_DETECTION)
        
        # Simple greedy clustering (threshold-based)
        clusters = {}
        assigned = set()
        cluster_id = 0
        
        for i, entry in enumerate(entries):
            if entry.id in assigned:
                continue
            
            # Start new cluster
            cluster = [entry]
            assigned.add(entry.id)
            
            # Find similar entries
            for j, other in enumerate(entries[i + 1:], start=i + 1):
                if other.id in assigned:
                    continue
                
                sim = similarities[i][j]
                if sim and sim.combined >= 0.6:  # Cognate threshold
                    cluster.append(other)
                    assigned.add(other.id)
            
            clusters[f"cluster_{cluster_id}"] = cluster
            cluster_id += 1
        
        return clusters
    
    def _find_cluster(self, entry: Entry, clusters: dict[str, list[Entry]]) -> str:
        """Find which cluster an entry belongs to."""
        
        for cluster_id, members in clusters.items():
            if entry.id in [m.id for m in members]:
                return cluster_id
        
        return "unassigned"
    
    def _generate_explanation(
        self,
        lang_a: str,
        lang_b: str,
        form_a: Entry,
        form_b: Entry,
        cluster_a: str,
        cluster_b: str,
        cognates_a: dict[str, str],
        cognates_b: dict[str, str],
        tree_dist: int,
        sim: LayeredSimilarity
    ) -> str:
        """Generate human-readable explanation of lexical difference.
        
        Analyzes patterns and produces narrative.
        """
        
        # Get language names and branch/family info
        branch_a = self.phylogeny.get_branch(lang_a) or "unknown"
        branch_b = self.phylogeny.get_branch(lang_b) or "unknown"
        family_a = self.phylogeny.get_family(lang_a) or "unknown"
        family_b = self.phylogeny.get_family(lang_b) or "unknown"
        
        # Analyze cognate distributions
        shared_languages = set(cognates_a.keys()) & set(cognates_b.keys())
        
        explanation_parts = []
        
        # Basic difference
        explanation_parts.append(
            f"{lang_a.upper()} uses '{form_a.headword}' while {lang_b.upper()} uses '{form_b.headword}' "
            f"for the same concept."
        )
        
        # Cross-family comparison
        if family_a != family_b and family_a != "unknown" and family_b != "unknown":
            explanation_parts.append(
                f"These languages belong to different families ({family_a} vs {family_b}). "
                f"Any similarity is likely due to loanwords or chance resemblance."
            )
        
        # Phonetic similarity
        if sim.phonetic > 0.7:
            explanation_parts.append(
                f"These forms show high phonetic similarity ({sim.phonetic:.2f}), "
                f"suggesting possible cognate relationship."
            )
        elif sim.phonetic < 0.3:
            explanation_parts.append(
                f"These forms are phonetically distinct ({sim.phonetic:.2f}), "
                f"indicating likely separate origins."
            )
        
        # Cognate cluster analysis
        if cluster_a != cluster_b:
            # Get cluster distributions
            cluster_a_langs = list(cognates_a.keys())[:3]  # First 3
            cluster_b_langs = list(cognates_b.keys())[:3]
            
            if cluster_a_langs:
                explanation_parts.append(
                    f"'{form_a.headword}' clusters with forms in: {', '.join(cluster_a_langs)}."
                )
            
            if cluster_b_langs:
                explanation_parts.append(
                    f"'{form_b.headword}' clusters with forms in: {', '.join(cluster_b_langs)}."
                )
        
        # Phylogenetic context
        if tree_dist <= 2:
            explanation_parts.append(
                f"Despite close phylogenetic relationship (distance={tree_dist}), "
                f"these languages diverged lexically for this concept."
            )
        elif tree_dist >= 5:
            explanation_parts.append(
                f"This difference aligns with distant phylogenetic relationship (distance={tree_dist})."
            )
        
        # Potential explanations based on patterns
        if branch_a != branch_b:
            explanation_parts.append(
                f"This reflects the split between {branch_a} and {branch_b} branches."
            )
        else:
            explanation_parts.append(
                f"This variation exists within the {branch_a} branch, "
                f"possibly due to substrate influence, borrowing, or lexical replacement."
            )
        
        return " ".join(explanation_parts)

