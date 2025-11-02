"""JSON-RPC client for R phylogenetic service.

Communicates with R statistical computing engine via subprocess (stdin/stdout) using JSON-RPC protocol.
Architecture: Process-based communication for reliability.
"""

import json
import subprocess
from typing import Optional
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from numpy.typing import NDArray

from backend.observ import get_logger

logger = get_logger(__name__)


@dataclass
class PhylogeneticTree:
    """Result from R tree inference."""
    
    newick: str
    method: str
    n_tips: int
    tip_labels: list[str]
    edge_lengths: Optional[list[float]]
    cophenetic_correlation: float
    rooted: bool
    binary: bool


@dataclass
class BootstrapResult:
    """Bootstrap analysis result."""
    
    consensus_newick: str
    support_values: list[float]
    n_bootstrap: int
    method: str


@dataclass
class HierarchicalClustering:
    """Hierarchical clustering result."""
    
    method: str
    labels: list[str]
    merge: list[list[int]]
    height: list[float]
    order: list[int]
    suggested_k_range: tuple[int, int]


@dataclass
class TreeComparison:
    """Tree topology comparison."""
    
    robinson_foulds: float
    normalized_rf: float
    max_possible_rf: float
    trees_identical: bool


@dataclass
class CopheneticResult:
    """Cophenetic correlation analysis."""
    
    correlation: float
    interpretation: str


class RPhyloClient:
    """JSON-RPC client for R phylogenetic service.
    
    Leverages R's ape/phangorn packages for publication-quality
    phylogenetic inference and statistical analysis.
    
    Communicates via subprocess (stdin/stdout) for reliability.
    """
    
    def __init__(self, r_script_path: Optional[str] = None):
        """Initialize R client.
        
        Args:
            r_script_path: Path to server.R (defaults to services/phylo-r/server.R)
        """
        if r_script_path is None:
            # Default to project structure
            project_root = Path(__file__).parent.parent.parent
            r_script_path = project_root / "services" / "phylo-r" / "server.R"
        
        self._r_script_path = Path(r_script_path)
        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0
        
        if not self._r_script_path.exists():
            raise FileNotFoundError(f"R script not found: {self._r_script_path}")
    
    def connect(self) -> None:
        """Start R subprocess."""
        try:
            self._process = subprocess.Popen(
                ["Rscript", str(self._r_script_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            logger.info(f"Started R phylo service: {self._r_script_path}")
        except FileNotFoundError:
            logger.error(
                "Rscript not found. Ensure R is installed and in PATH. "
                "Install from: https://cran.r-project.org/"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to start R service: {e}")
            raise
    
    def disconnect(self) -> None:
        """Stop R subprocess."""
        if self._process:
            self._process.stdin.close()
            self._process.stdout.close()
            self._process.stderr.close()
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            logger.info("Stopped R phylo service")
    
    def _call(self, method: str, params: dict) -> dict:
        """Make JSON-RPC call to R service via subprocess."""
        if not self._process or self._process.poll() is not None:
            raise RuntimeError("R process not running. Call connect() first.")
        
        self._request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._request_id
        }
        
        # Send request
        request_json = json.dumps(request) + "\n"
        try:
            self._process.stdin.write(request_json)
            self._process.stdin.flush()
        except Exception as e:
            logger.error(f"Failed to send request to R: {e}")
            raise RuntimeError(f"Failed to send request to R: {e}")
        
        # Receive response
        try:
            response_line = self._process.stdout.readline()
            if not response_line:
                # Check if process died
                stderr_output = self._process.stderr.read()
                raise RuntimeError(
                    f"R process terminated unexpectedly. stderr: {stderr_output}"
                )
            
            response = json.loads(response_line)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from R service: {e}")
            stderr_output = self._process.stderr.read()
            raise RuntimeError(f"Invalid JSON from R: {e}. stderr: {stderr_output}")
        
        if "error" in response:
            error_msg = response['error']['message']
            logger.error(f"R service error: {error_msg}")
            raise RuntimeError(f"R service error: {error_msg}")
        
        return response["result"]
    
    def ping(self) -> bool:
        """Check if R service is responsive."""
        try:
            result = self._call("ping", {})
            return result.get("status") == "ok"
        except Exception as e:
            logger.warning(f"R service ping failed: {e}")
            return False
    
    def infer_tree(
        self,
        distance_matrix: NDArray,
        labels: Optional[list[str]] = None,
        method: str = "nj"
    ) -> PhylogeneticTree:
        """Infer phylogenetic tree from distance matrix.
        
        Args:
            distance_matrix: Square distance matrix (numpy array)
            labels: Optional tip labels (language codes)
            method: Tree inference method ("nj", "upgma", "ml")
            
        Returns:
            PhylogeneticTree with newick string and metadata
            
        Raises:
            RuntimeError: If tree inference fails
        """
        logger.info(f"Inferring tree with method '{method}' for {len(distance_matrix)} taxa")
        
        # Convert numpy array to nested list for JSON
        distances = distance_matrix.tolist()
        
        params = {
            "distances": distances,
            "method": method
        }
        
        if labels:
            params["labels"] = labels
        
        result = self._call("infer_tree", params)
        
        tree = PhylogeneticTree(
            newick=result["newick"],
            method=result["method"],
            n_tips=result["n_tips"],
            tip_labels=result["tip_labels"],
            edge_lengths=result.get("edge_lengths"),
            cophenetic_correlation=result["cophenetic_correlation"],
            rooted=result["rooted"],
            binary=result["binary"]
        )
        
        logger.info(
            f"Tree inferred: {tree.n_tips} tips, "
            f"cophenetic correlation = {tree.cophenetic_correlation:.3f}"
        )
        
        return tree
    
    def bootstrap_tree(
        self,
        distance_matrix: NDArray,
        labels: Optional[list[str]] = None,
        method: str = "nj",
        n_bootstrap: int = 100
    ) -> BootstrapResult:
        """Perform bootstrap analysis on tree.
        
        Args:
            distance_matrix: Square distance matrix
            labels: Optional tip labels
            method: Tree inference method ("nj", "upgma")
            n_bootstrap: Number of bootstrap replicates (default 100)
            
        Returns:
            BootstrapResult with consensus tree and support values
        """
        logger.info(f"Running bootstrap analysis with {n_bootstrap} replicates")
        
        distances = distance_matrix.tolist()
        
        params = {
            "distances": distances,
            "method": method,
            "n_bootstrap": n_bootstrap
        }
        
        if labels:
            params["labels"] = labels
        
        result = self._call("bootstrap_tree", params)
        
        bootstrap = BootstrapResult(
            consensus_newick=result["consensus_newick"],
            support_values=result["support_values"],
            n_bootstrap=result["n_bootstrap"],
            method=result["method"]
        )
        
        logger.info(f"Bootstrap complete: {len(bootstrap.support_values)} support values computed")
        
        return bootstrap
    
    def cluster_hierarchical(
        self,
        distance_matrix: NDArray,
        labels: Optional[list[str]] = None,
        method: str = "ward.D2",
        compute_significance: bool = False,
        n_bootstrap: int = 100
    ) -> HierarchicalClustering:
        """Perform hierarchical clustering with R's hclust.
        
        This provides proper statistical clustering, superior to greedy threshold methods.
        
        Args:
            distance_matrix: Square distance matrix
            labels: Optional labels for items
            method: Linkage method ("ward.D2", "complete", "average", "single")
            compute_significance: Compute p-values with pvclust (slow)
            n_bootstrap: Bootstrap replicates for significance
            
        Returns:
            HierarchicalClustering with dendrogram structure
        """
        logger.info(f"Hierarchical clustering with method '{method}'")
        
        distances = distance_matrix.tolist()
        
        params = {
            "distances": distances,
            "method": method,
            "compute_significance": compute_significance,
            "n_bootstrap": n_bootstrap
        }
        
        if labels:
            params["labels"] = labels
        
        result = self._call("cluster_hierarchical", params)
        
        clustering = HierarchicalClustering(
            method=result["method"],
            labels=result["labels"],
            merge=result["merge"],
            height=result["height"],
            order=result["order"],
            suggested_k_range=tuple(result["suggested_k_range"])
        )
        
        logger.info(f"Clustering complete: suggested k range = {clustering.suggested_k_range}")
        
        return clustering
    
    def compare_trees(
        self,
        tree1_newick: str,
        tree2_newick: str
    ) -> TreeComparison:
        """Compare two phylogenetic trees using Robinson-Foulds distance.
        
        Args:
            tree1_newick: First tree in Newick format
            tree2_newick: Second tree in Newick format
            
        Returns:
            TreeComparison with topology distance metrics
        """
        logger.info("Comparing tree topologies")
        
        params = {
            "tree1_newick": tree1_newick,
            "tree2_newick": tree2_newick
        }
        
        result = self._call("compare_trees", params)
        
        comparison = TreeComparison(
            robinson_foulds=result["robinson_foulds"],
            normalized_rf=result["normalized_rf"],
            max_possible_rf=result["max_possible_rf"],
            trees_identical=result["trees_identical"]
        )
        
        logger.info(
            f"Tree comparison: RF distance = {comparison.robinson_foulds}, "
            f"normalized = {comparison.normalized_rf:.3f}"
        )
        
        return comparison
    
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
            width: Width in pixels (for raster) or inches (for vector)
            height: Height in pixels/inches
            
        Returns:
            Dict with plot metadata
        """
        logger.info(f"Generating {format} dendrogram at {output_path}")
        
        params = {
            "newick": newick,
            "output_path": output_path,
            "format": format,
            "width": width,
            "height": height
        }
        
        result = self._call("plot_dendrogram", params)
        
        logger.info(f"Dendrogram saved: {result['output_path']}")
        
        return result
    
    def cophenetic_correlation(
        self,
        newick: str,
        distance_matrix: NDArray,
        labels: Optional[list[str]] = None
    ) -> CopheneticResult:
        """Compute cophenetic correlation (tree quality metric).
        
        Measures how well the tree preserves original distances.
        
        Args:
            newick: Tree in Newick format
            distance_matrix: Original distance matrix
            labels: Optional labels
            
        Returns:
            CopheneticResult with correlation and interpretation
        """
        logger.info("Computing cophenetic correlation")
        
        distances = distance_matrix.tolist()
        
        params = {
            "newick": newick,
            "distances": distances
        }
        
        if labels:
            params["labels"] = labels
        
        result = self._call("cophenetic_correlation", params)
        
        coph = CopheneticResult(
            correlation=result["correlation"],
            interpretation=result["interpretation"]
        )
        
        logger.info(
            f"Cophenetic correlation = {coph.correlation:.3f}: {coph.interpretation}"
        )
        
        return coph
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

