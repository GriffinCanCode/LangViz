"""Concept alignment service for cross-lingual semantic clustering.

Discovers semantic concepts across languages using UMAP + HDBSCAN.
Maps entries to concepts for concept-level indexing and querying.
"""

from typing import Optional
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
import hdbscan
from umap import UMAP

from backend.core.types import Entry
from backend.core.similarity import ConceptCluster, ConceptID
from backend.services.semantic import SemanticService
from backend.observ import get_logger, timer

logger = get_logger(__name__)


@dataclass
class ConceptAligner:
    """Discovers and assigns cross-lingual semantic concepts.
    
    Uses UMAP for manifold learning + HDBSCAN for density-based clustering.
    This preserves semantic topology better than PCA + k-means.
    """
    
    semantic_service: SemanticService
    min_cluster_size: int = 50
    min_samples: int = 10
    umap_neighbors: int = 15
    umap_dim: int = 50  # Intermediate dimension for clustering
    
    def __post_init__(self):
        self._umap_model: Optional[UMAP] = None
        self._clusterer: Optional[hdbscan.HDBSCAN] = None
        self._concept_map: dict[int, ConceptCluster] = {}
    
    def discover_concepts(
        self,
        entries: list[Entry],
        use_cache: bool = True
    ) -> list[ConceptCluster]:
        """Discover semantic concepts from entry definitions.
        
        Args:
            entries: List of entries to cluster
            use_cache: Whether to use cached UMAP model
            
        Returns:
            List of discovered concept clusters
        """
        logger.info(
            "concept_discovery_started",
            entry_count=len(entries),
            min_cluster_size=self.min_cluster_size,
            use_cache=use_cache
        )
        
        # Extract definitions and embed
        definitions = [e.definition for e in entries]
        embeddings = self.semantic_service.batch_embed(definitions)
        
        # Reduce dimensionality with UMAP (preserves manifold structure)
        if not use_cache or self._umap_model is None:
            self._umap_model = UMAP(
                n_neighbors=self.umap_neighbors,
                n_components=self.umap_dim,
                metric='cosine',
                random_state=42
            )
            reduced = self._umap_model.fit_transform(embeddings)
        else:
            reduced = self._umap_model.transform(embeddings)
        
        # Cluster with HDBSCAN (finds variable-density clusters)
        self._clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            metric='euclidean',
            cluster_selection_method='eom'  # Excess of Mass
        )
        
        labels = self._clusterer.fit_predict(reduced)
        
        # Build concept clusters
        clusters = []
        cluster_assignments = defaultdict(list)
        
        for idx, label in enumerate(labels):
            if label == -1:  # Noise point
                continue
            cluster_assignments[label].append(idx)
        
        for cluster_id, member_indices in cluster_assignments.items():
            member_entries = [entries[i] for i in member_indices]
            member_embeddings = embeddings[member_indices]
            
            # Compute centroid
            centroid = np.mean(member_embeddings, axis=0)
            
            # Extract metadata
            languages = list(set(e.language for e in member_entries))
            sample_defs = [e.definition for e in member_entries[:5]]
            
            cluster = ConceptCluster(
                id=f"concept_{cluster_id:04d}",
                centroid=centroid.tolist(),
                member_ids=[e.id for e in member_entries],
                languages=languages,
                sample_definitions=sample_defs,
                confidence=self._compute_cluster_confidence(member_embeddings, centroid),
                size=len(member_entries)
            )
            
            clusters.append(cluster)
            self._concept_map[cluster_id] = cluster
        
        return clusters
    
    def assign_concept(
        self,
        entry: Entry,
        concepts: Optional[list[ConceptCluster]] = None
    ) -> tuple[ConceptID, float]:
        """Assign entry to nearest concept cluster.
        
        Args:
            entry: Entry to assign
            concepts: Pre-discovered concepts (uses cached if None)
            
        Returns:
            (ConceptID, distance) tuple
        """
        
        if concepts is None:
            if not self._concept_map:
                raise ValueError("Must run discover_concepts first or provide concepts")
            concepts = list(self._concept_map.values())
        
        # Embed definition
        embedding = np.array(self.semantic_service.get_embedding(entry.definition))
        
        # Find nearest concept centroid
        min_dist = float('inf')
        best_concept = None
        
        for concept in concepts:
            centroid = np.array(concept.centroid)
            dist = 1 - np.dot(embedding, centroid) / (
                np.linalg.norm(embedding) * np.linalg.norm(centroid)
            )
            
            if dist < min_dist:
                min_dist = dist
                best_concept = concept
        
        if best_concept is None:
            raise ValueError("No concepts available")
        
        confidence = 1.0 - min_dist
        
        return (
            ConceptID(
                id=best_concept.id,
                label=self._generate_concept_label(best_concept),
                confidence=confidence,
                member_count=best_concept.size
            ),
            min_dist
        )
    
    def batch_assign(
        self,
        entries: list[Entry],
        concepts: Optional[list[ConceptCluster]] = None
    ) -> list[tuple[ConceptID, float]]:
        """Efficiently assign multiple entries to concepts.
        
        Uses batched embedding and vectorized distance computation.
        """
        
        if concepts is None:
            if not self._concept_map:
                raise ValueError("Must run discover_concepts first or provide concepts")
            concepts = list(self._concept_map.values())
        
        # Batch embed all definitions
        definitions = [e.definition for e in entries]
        embeddings = self.semantic_service.batch_embed(definitions)
        
        # Create centroid matrix
        centroids = np.array([concept.centroid for concept in concepts])
        
        # Compute all distances at once (efficient)
        # Shape: (num_entries, num_concepts)
        distances = 1 - (embeddings @ centroids.T) / (
            np.linalg.norm(embeddings, axis=1, keepdims=True) *
            np.linalg.norm(centroids, axis=1, keepdims=True).T
        )
        
        # Find best concept for each entry
        best_concept_indices = np.argmin(distances, axis=1)
        min_distances = np.min(distances, axis=1)
        
        results = []
        for idx, (concept_idx, dist) in enumerate(zip(best_concept_indices, min_distances)):
            concept = concepts[concept_idx]
            results.append((
                ConceptID(
                    id=concept.id,
                    label=self._generate_concept_label(concept),
                    confidence=1.0 - dist,
                    member_count=concept.size
                ),
                dist
            ))
        
        return results
    
    def visualize_concepts(
        self,
        embeddings: NDArray,
        labels: NDArray,
        dim: int = 2
    ) -> NDArray:
        """Reduce to 2D/3D for visualization.
        
        Uses UMAP to preserve local manifold structure.
        NOT used for similarity computation.
        """
        
        vis_reducer = UMAP(
            n_neighbors=15,
            n_components=dim,
            metric='cosine',
            random_state=42
        )
        
        return vis_reducer.fit_transform(embeddings)
    
    def _compute_cluster_confidence(
        self,
        embeddings: NDArray,
        centroid: NDArray
    ) -> float:
        """Compute confidence score for cluster based on cohesion.
        
        Uses average cosine similarity to centroid.
        """
        
        similarities = embeddings @ centroid / (
            np.linalg.norm(embeddings, axis=1) * np.linalg.norm(centroid)
        )
        
        return float(np.mean(similarities))
    
    def _generate_concept_label(self, concept: ConceptCluster) -> str:
        """Generate human-readable label from sample definitions.
        
        TODO: Use extractive summarization or LLM for better labels.
        For now, use first few words of most common definition.
        """
        
        if not concept.sample_definitions:
            return f"concept_{concept.id}"
        
        # Simple heuristic: first definition, first 3 words
        first_def = concept.sample_definitions[0]
        words = first_def.split()[:3]
        return "_".join(words).upper()

