"""Phylogenetic service combining R statistical inference with Python caching.

Separates concerns:
- R (via interop): Tree inference, bootstrap, statistical clustering
- Python: Fast lookups, caching, integration with similarity pipeline

This replaces the hard-coded tree in phylogeny.py with data-driven inference.
"""

from typing import Optional
from dataclasses import dataclass, field
import numpy as np
from numpy.typing import NDArray
from functools import lru_cache

from backend.interop.r_client import (
    RPhyloClient,
    PhylogeneticTree as RTree,
    BootstrapResult,
    HierarchicalClustering,
    TreeComparison
)
from backend.core.similarity import PhylogeneticNode
from backend.observ import get_logger

logger = get_logger(__name__)


@dataclass
class PhyloService:
    """Phylogenetic service with R backend and Python caching.
    
    Provides two modes:
    1. Static tree (fast lookups) - from phylogeny.py
    2. Inferred tree (statistical rigor) - from R service
    
    Use static tree for API queries, inferred tree for analysis.
    """
    
    use_r: bool = False  # Enable R integration (spawns R subprocess)
    r_script_path: Optional[str] = None  # Path to R server.R script
    
    # Cache for inferred trees (keyed by distance matrix hash)
    _tree_cache: dict[str, RTree] = field(default_factory=dict)
    
    # Static tree from phylogeny.py for fast lookups
    _static_tree: Optional[object] = None
    
    def __post_init__(self):
        """Initialize service and check R availability."""
        if self.use_r:
            self._check_r_service()
    
    def _check_r_service(self) -> bool:
        """Check if R service is available."""
        try:
            with RPhyloClient(self.r_script_path) as client:
                available = client.ping()
                if available:
                    logger.info("R phylo service is available")
                else:
                    logger.warning("R phylo service ping failed")
                return available
        except Exception as e:
            logger.warning(
                f"R phylo service not available: {e}. "
                f"Falling back to static tree. "
                f"To enable R features, ensure R is installed with required packages."
            )
            return False
    
    def infer_tree_from_distances(
        self,
        distance_matrix: NDArray,
        labels: list[str],
        method: str = "nj",
        use_cache: bool = True
    ) -> RTree:
        """Infer phylogenetic tree from distance matrix using R.
        
        This provides data-driven tree inference, superior to hard-coded trees.
        
        Args:
            distance_matrix: Square distance matrix (linguistic distances)
            labels: Language codes (ISO 639)
            method: Tree inference method ("nj", "upgma", "ml")
            use_cache: Use cached tree if available
            
        Returns:
            PhylogeneticTree with newick string and statistics
            
        Raises:
            RuntimeError: If R service not available
        """
        if not self.use_r:
            raise RuntimeError(
                "R service not enabled. Set use_r=True or start R service."
            )
        
        # Cache key from matrix hash
        cache_key = f"{method}_{hash(distance_matrix.tobytes())}"
        
        if use_cache and cache_key in self._tree_cache:
            logger.debug("Using cached tree")
            return self._tree_cache[cache_key]
        
        logger.info(f"Inferring tree for {len(labels)} languages with method '{method}'")
        
        with RPhyloClient(self.r_script_path) as client:
            tree = client.infer_tree(distance_matrix, labels, method)
        
        # Cache result
        if use_cache:
            self._tree_cache[cache_key] = tree
        
        logger.info(
            f"Tree inferred: cophenetic correlation = {tree.cophenetic_correlation:.3f}"
        )
        
        return tree
    
    def bootstrap_tree(
        self,
        distance_matrix: NDArray,
        labels: list[str],
        method: str = "nj",
        n_bootstrap: int = 100
    ) -> BootstrapResult:
        """Compute bootstrap confidence for tree.
        
        Provides statistical support values for tree branches.
        
        Args:
            distance_matrix: Square distance matrix
            labels: Language codes
            method: Tree inference method
            n_bootstrap: Bootstrap replicates (100-1000 recommended)
            
        Returns:
            BootstrapResult with consensus tree and support values
        """
        if not self.use_r:
            raise RuntimeError("R service required for bootstrap analysis")
        
        logger.info(f"Bootstrap analysis with {n_bootstrap} replicates")
        
        with RPhyloClient(self.r_script_path) as client:
            result = client.bootstrap_tree(
                distance_matrix,
                labels,
                method,
                n_bootstrap
            )
        
        return result
    
    def cluster_cognates_hierarchical(
        self,
        distance_matrix: NDArray,
        labels: list[str],
        method: str = "ward.D2"
    ) -> HierarchicalClustering:
        """Cluster cognates using hierarchical clustering.
        
        This is statistically superior to greedy threshold clustering.
        
        Args:
            distance_matrix: Pairwise cognate distances
            labels: Word forms or entry IDs
            method: Linkage method ("ward.D2", "complete", "average")
            
        Returns:
            HierarchicalClustering with dendrogram structure
        """
        if not self.use_r:
            raise RuntimeError("R service required for hierarchical clustering")
        
        logger.info(f"Hierarchical clustering with method '{method}'")
        
        with RPhyloClient(self.r_script_path) as client:
            result = client.cluster_hierarchical(
                distance_matrix,
                labels,
                method
            )
        
        return result
    
    def compare_trees(
        self,
        tree1_newick: str,
        tree2_newick: str
    ) -> TreeComparison:
        """Compare two tree topologies.
        
        Useful for testing hypotheses about language relationships.
        
        Args:
            tree1_newick: First tree (e.g., from Swadesh data)
            tree2_newick: Second tree (e.g., from grammar features)
            
        Returns:
            TreeComparison with Robinson-Foulds distance
        """
        if not self.use_r:
            raise RuntimeError("R service required for tree comparison")
        
        with RPhyloClient(self.r_script_path) as client:
            result = client.compare_trees(tree1_newick, tree2_newick)
        
        return result
    
    def plot_dendrogram(
        self,
        newick: str,
        output_path: str,
        format: str = "png",
        width: int = 800,
        height: int = 600
    ) -> dict:
        """Generate publication-quality dendrogram.
        
        Args:
            newick: Tree in Newick format
            output_path: Output file path
            format: Image format ("png", "pdf", "svg")
            width, height: Dimensions
            
        Returns:
            Dict with plot metadata
        """
        if not self.use_r:
            raise RuntimeError("R service required for dendrogram plotting")
        
        with RPhyloClient(self.r_script_path) as client:
            result = client.plot_dendrogram(
                newick,
                output_path,
                format,
                width,
                height
            )
        
        return result
    
    def get_static_tree(self):
        """Get static tree for fast lookups (from phylogeny.py).
        
        Use this for API queries requiring low latency.
        """
        if self._static_tree is None:
            from backend.services.phylogeny import PhylogeneticTree
            self._static_tree = PhylogeneticTree()
        
        return self._static_tree
    
    def path_distance(self, lang_a: str, lang_b: str) -> int:
        """Get tree path distance between languages (fast lookup).
        
        Uses static tree for low latency.
        """
        return self.get_static_tree().path_distance(lang_a, lang_b)
    
    def cognate_prior(self, distance: int) -> float:
        """Get cognate prior probability from tree distance (fast lookup).
        
        Uses static tree for low latency.
        """
        return self.get_static_tree().cognate_prior(distance)
    
    @lru_cache(maxsize=1024)
    def get_branch(self, lang: str) -> Optional[str]:
        """Get language branch (cached)."""
        return self.get_static_tree().get_branch(lang)
    
    @lru_cache(maxsize=1024)
    def get_family(self, lang: str) -> Optional[str]:
        """Get language family (cached)."""
        return self.get_static_tree().get_family(lang)


def create_distance_matrix_from_similarities(
    similarities: list[tuple[str, str, float]]
) -> tuple[NDArray, list[str]]:
    """Convert pairwise similarities to distance matrix.
    
    Helper function to prepare data for R phylogenetic inference.
    
    Args:
        similarities: List of (id_a, id_b, similarity_score) tuples
        
    Returns:
        Tuple of (distance_matrix, labels)
    """
    # Extract unique IDs
    ids = set()
    for id_a, id_b, _ in similarities:
        ids.add(id_a)
        ids.add(id_b)
    
    labels = sorted(list(ids))
    id_to_idx = {id_: idx for idx, id_ in enumerate(labels)}
    
    n = len(labels)
    matrix = np.zeros((n, n))
    
    # Fill matrix
    for id_a, id_b, similarity in similarities:
        idx_a = id_to_idx[id_a]
        idx_b = id_to_idx[id_b]
        
        # Convert similarity to distance
        distance = 1.0 - similarity
        
        matrix[idx_a, idx_b] = distance
        matrix[idx_b, idx_a] = distance
    
    return matrix, labels

