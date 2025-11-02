"""Graph service using Rust backend for high-performance operations.

Provides wrapper around langviz_core's graph algorithms with Python-friendly interface.
"""

from typing import Optional
from dataclasses import dataclass

from backend.observ import get_logger
from backend.core.types import Entry
from backend.core.similarity import LayeredSimilarity

logger = get_logger(__name__)

# Try to import Rust backend
try:
    from langviz_core import (
        py_find_cognate_sets,
        py_detect_communities,
        py_compute_pagerank,
        py_graph_stats,
        py_graph_to_json,
    )
    RUST_AVAILABLE = True
    logger.info("rust_graph_backend_loaded")
except ImportError:
    RUST_AVAILABLE = False
    logger.warning("rust_graph_backend_unavailable", fallback="python_networkx")


@dataclass
class GraphStats:
    """Graph statistics."""
    num_nodes: int
    num_edges: int
    avg_degree: float
    density: float
    num_components: int


@dataclass
class GraphCognateSet:
    """Cognate set result from graph operations.
    
    Lightweight representation for graph algorithm results.
    Use core.types.CognateSet for domain model with full validation.
    """
    id: int
    members: list[str]
    size: int


class CognateGraphService:
    """High-level graph operations using Rust backend when available."""
    
    def __init__(self, use_rust: bool = True):
        self._use_rust = use_rust and RUST_AVAILABLE
        if self._use_rust:
            logger.info("cognate_graph_service_initialized", backend="rust")
        else:
            logger.info("cognate_graph_service_initialized", backend="python_fallback")
    
    def build_cognate_network(
        self,
        similarities: list[LayeredSimilarity],
        threshold: float = 0.6
    ) -> dict:
        """Build cognate network from similarity edges.
        
        Args:
            similarities: List of LayeredSimilarity objects
            threshold: Minimum similarity to create edge
            
        Returns:
            Dict with cognate_sets and graph statistics
        """
        # Convert to edge list format
        edges = [
            (sim.entry_a, sim.entry_b, sim.combined)
            for sim in similarities
            if sim.combined >= threshold
        ]
        
        logger.info("building_cognate_network", 
                   num_similarities=len(similarities),
                   num_edges=len(edges),
                   threshold=threshold,
                   backend="rust" if self._use_rust else "python")
        
        if self._use_rust:
            return self._build_rust(edges, threshold)
        else:
            return self._build_python(edges, threshold)
    
    def _build_rust(self, edges: list[tuple[str, str, float]], threshold: float) -> dict:
        """Build network using Rust backend."""
        cognate_sets_raw = py_find_cognate_sets(edges, threshold)
        stats_raw = py_graph_stats(edges, threshold)
        
        cognate_sets = [
            GraphCognateSet(
                id=cs.id,
                members=cs.members,
                size=cs.size
            )
            for cs in cognate_sets_raw
        ]
        
        stats = GraphStats(
            num_nodes=stats_raw.num_nodes,
            num_edges=stats_raw.num_edges,
            avg_degree=stats_raw.avg_degree,
            density=stats_raw.density,
            num_components=stats_raw.num_components
        )
        
        logger.info("cognate_network_built",
                   num_sets=len(cognate_sets),
                   num_components=stats.num_components)
        
        return {
            "cognate_sets": cognate_sets,
            "stats": stats
        }
    
    def _build_python(self, edges: list[tuple[str, str, float]], threshold: float) -> dict:
        """Fallback to Python implementation."""
        # Simple greedy clustering
        from collections import defaultdict
        
        # Build adjacency list
        adj: dict[str, list[str]] = defaultdict(list)
        for a, b, weight in edges:
            if weight >= threshold:
                adj[a].append(b)
                adj[b].append(a)
        
        # Find connected components
        visited = set()
        cognate_sets = []
        set_id = 0
        
        for node in adj:
            if node not in visited:
                # BFS
                component = []
                queue = [node]
                while queue:
                    current = queue.pop(0)
                    if current in visited:
                        continue
                    visited.add(current)
                    component.append(current)
                    for neighbor in adj[current]:
                        if neighbor not in visited:
                            queue.append(neighbor)
                
                cognate_sets.append(GraphCognateSet(
                    id=set_id,
                    members=component,
                    size=len(component)
                ))
                set_id += 1
        
        stats = GraphStats(
            num_nodes=len(adj),
            num_edges=len(edges),
            avg_degree=sum(len(neighbors) for neighbors in adj.values()) / len(adj) if adj else 0,
            density=len(edges) / (len(adj) * (len(adj) - 1) / 2) if len(adj) > 1 else 0,
            num_components=len(cognate_sets)
        )
        
        return {
            "cognate_sets": cognate_sets,
            "stats": stats
        }
    
    def detect_communities(
        self,
        similarities: list[LayeredSimilarity],
        threshold: float = 0.6,
        resolution: float = 1.0
    ) -> list[list[str]]:
        """Detect communities using Louvain algorithm.
        
        Args:
            similarities: List of similarity scores
            threshold: Edge threshold
            resolution: Community detection resolution
            
        Returns:
            List of communities (each is list of entry IDs)
        """
        edges = [
            (sim.entry_a, sim.entry_b, sim.combined)
            for sim in similarities
            if sim.combined >= threshold
        ]
        
        if self._use_rust:
            communities = py_detect_communities(edges, threshold, resolution)
            logger.info("communities_detected", num_communities=len(communities), backend="rust")
            return communities
        else:
            logger.warning("community_detection_unavailable", reason="rust_backend_required")
            return []
    
    def compute_centrality(
        self,
        similarities: list[LayeredSimilarity],
        threshold: float = 0.6,
        damping: float = 0.85,
        iterations: int = 100
    ) -> dict[str, float]:
        """Compute PageRank centrality scores.
        
        Args:
            similarities: List of similarity scores
            threshold: Edge threshold
            damping: PageRank damping factor
            iterations: Number of iterations
            
        Returns:
            Dict mapping entry IDs to centrality scores
        """
        edges = [
            (sim.entry_a, sim.entry_b, sim.combined)
            for sim in similarities
            if sim.combined >= threshold
        ]
        
        if self._use_rust:
            ranks = py_compute_pagerank(edges, threshold, damping, iterations)
            logger.info("centrality_computed", num_nodes=len(ranks), backend="rust")
            return dict(ranks)
        else:
            logger.warning("centrality_computation_unavailable", reason="rust_backend_required")
            return {}
    
    def export_for_visualization(
        self,
        similarities: list[LayeredSimilarity],
        threshold: float = 0.6
    ) -> str:
        """Export graph to JSON for D3.js visualization.
        
        Args:
            similarities: List of similarity scores
            threshold: Edge threshold
            
        Returns:
            JSON string with nodes and edges
        """
        edges = [
            (sim.entry_a, sim.entry_b, sim.combined)
            for sim in similarities
            if sim.combined >= threshold
        ]
        
        if self._use_rust:
            return py_graph_to_json(edges, threshold)
        else:
            # Simple JSON export
            import json
            nodes = set()
            for a, b, _ in edges:
                nodes.add(a)
                nodes.add(b)
            
            return json.dumps({
                "nodes": [{"id": node} for node in nodes],
                "edges": [{"source": a, "target": b, "weight": w} for a, b, w in edges]
            })

