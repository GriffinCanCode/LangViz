# R Integration Architecture

## Overview

LangViz integrates R for **statistical phylogenetic analysis** and **hierarchical clustering**, leveraging R's unmatched ecosystem for computational biology and statistical computing.

## Rationale: Why R?

### R's Unique Strengths

1. **Gold-Standard Phylogenetics**
   - **ape** (Analysis of Phylogenetics and Evolution): 30+ years of development
   - **phangorn** (Phylogenetic Reconstruction): Maximum Likelihood, Bayesian methods
   - **pvclust**: Hierarchical clustering with statistical significance (bootstrap p-values)
   
2. **Publication-Quality Graphics**
   - Journal-ready dendrograms with branch lengths, support values
   - Customizable phylogenetic trees (cladograms, phylograms, fan trees)
   
3. **Statistical Rigor**
   - Proper bootstrap resampling (not pseudo-bootstrap)
   - Likelihood ratio tests for tree topologies
   - Cophenetic correlation for tree quality assessment
   
4. **No Python Equivalent**
   - `dendropy`: Less mature, slower, limited methods
   - `scikit-bio`: Basic phylogenetics only
   - `ete3`: Visualization-focused, not inference

### What R Does Better Than Python

| Task | Python | R | Winner |
|------|--------|---|--------|
| Phylogenetic tree inference | Limited (dendropy) | Gold standard (ape/phangorn) | **R** |
| Bootstrap confidence | Basic | Proper statistical methods | **R** |
| Hierarchical clustering | scikit-learn (no significance) | pvclust (with p-values) | **R** |
| Tree topology tests | Not available | Comprehensive (ape) | **R** |
| Publication dendrograms | matplotlib (basic) | ape graphics (journal-ready) | **R** |
| Statistical tests | Good | **Excellent** | **R** |

## Architecture

### Separation of Concerns

**R handles (via JSON-RPC service):**
- Phylogenetic tree inference from distance matrices
- Bootstrap confidence analysis
- Hierarchical clustering with statistical significance
- Tree topology comparison (Robinson-Foulds distance)
- Publication-quality dendrogram generation
- Cophenetic correlation and tree quality metrics

**Python handles:**
- API orchestration
- Fast tree lookups (cached static tree)
- Integration with similarity pipeline
- Database storage
- Request routing

**Rust will handle (future):**
- Phonetic distance computation (CPU-intensive)
- Graph algorithms (community detection)

### Communication Protocol

Follows the **Perl interop pattern** for consistency:

```
┌─────────────┐                    ┌─────────────┐
│   Python    │  JSON-RPC 2.0      │      R      │
│   FastAPI   │ ─────────────────> │   Server    │
│   Backend   │  TCP Socket        │  (port      │
│             │ <───────────────── │   50052)    │
└─────────────┘                    └─────────────┘
```

**Protocol**: JSON-RPC 2.0 over TCP
- **Port**: 50052 (Perl uses 50051)
- **Format**: Newline-delimited JSON
- **Timeout**: 30 seconds (configurable for long computations)

### File Structure

```
services/phylo-r/
  ├── server.R              # R JSON-RPC server
  ├── install_deps.R        # Dependency installation script
  ├── DESCRIPTION           # R package metadata
  └── README.md             # Service documentation

backend/interop/
  ├── __init__.py
  ├── perl_client.py        # Perl service client
  └── r_client.py           # R service client (NEW)

backend/services/
  ├── phylo.py              # High-level phylo service (NEW)
  └── phylogeny.py          # Static tree (fast lookups)
```

## Usage

### Starting R Service

```bash
# Install dependencies
cd services/phylo-r
Rscript install_deps.R

# Start server
Rscript server.R
```

The server will listen on `localhost:50052`.

### Python Integration

#### Low-Level: Direct R Client

```python
from backend.interop.r_client import RPhyloClient
import numpy as np

# Distance matrix (linguistic distances)
distances = np.array([
    [0.0, 0.3, 0.5, 0.7],
    [0.3, 0.0, 0.4, 0.6],
    [0.5, 0.4, 0.0, 0.5],
    [0.7, 0.6, 0.5, 0.0]
])

labels = ["English", "German", "French", "Hindi"]

with RPhyloClient() as client:
    # Check connectivity
    if not client.ping():
        raise RuntimeError("R service not available")
    
    # Infer tree
    tree = client.infer_tree(distances, labels, method="nj")
    print(f"Tree: {tree.newick}")
    print(f"Quality: {tree.cophenetic_correlation:.3f}")
    
    # Bootstrap analysis
    bootstrap = client.bootstrap_tree(
        distances, labels, n_bootstrap=100
    )
    print(f"Support values: {bootstrap.support_values}")
```

#### High-Level: PhyloService

```python
from backend.services.phylo import PhyloService
import numpy as np

# Initialize service
phylo = PhyloService(use_r=True)

# Infer tree (cached)
tree = phylo.infer_tree_from_distances(
    distances, labels, method="nj"
)

# Bootstrap (slow - use for important analyses)
bootstrap = phylo.bootstrap_tree(
    distances, labels, n_bootstrap=100
)

# Fast lookups (static tree)
distance = phylo.path_distance("en", "de")
prior = phylo.cognate_prior(distance)
```

#### Dependency Injection (FastAPI)

```python
from fastapi import Depends
from backend.api.dependencies import get_phylo_service
from backend.services.phylo import PhyloService

@router.post("/phylo/infer")
async def infer_tree(
    distance_matrix: list[list[float]],
    labels: list[str],
    phylo: PhyloService = Depends(get_phylo_service)
):
    """Infer phylogenetic tree from distance matrix."""
    import numpy as np
    distances = np.array(distance_matrix)
    
    tree = phylo.infer_tree_from_distances(
        distances, labels, method="nj"
    )
    
    return {
        "newick": tree.newick,
        "cophenetic_correlation": tree.cophenetic_correlation,
        "method": tree.method
    }
```

## R Service API

### Methods

#### `infer_tree`
Infer phylogenetic tree from distance matrix.

**Parameters:**
```json
{
  "distances": [[0.0, 0.3], [0.3, 0.0]],
  "labels": ["en", "de"],
  "method": "nj"  // "nj", "upgma", or "ml"
}
```

**Returns:**
```json
{
  "newick": "(en:0.15,de:0.15);",
  "method": "nj",
  "n_tips": 2,
  "tip_labels": ["en", "de"],
  "edge_lengths": [0.15, 0.15],
  "cophenetic_correlation": 0.95,
  "rooted": false,
  "binary": true
}
```

#### `bootstrap_tree`
Bootstrap confidence analysis.

**Parameters:**
```json
{
  "distances": [[0.0, 0.3], [0.3, 0.0]],
  "labels": ["en", "de"],
  "method": "nj",
  "n_bootstrap": 100
}
```

**Returns:**
```json
{
  "consensus_newick": "(en,de);",
  "support_values": [0.85, 0.92, 1.0],
  "n_bootstrap": 100,
  "method": "nj"
}
```

#### `cluster_hierarchical`
Hierarchical clustering with statistical significance.

**Parameters:**
```json
{
  "distances": [[0.0, 0.2], [0.2, 0.0]],
  "labels": ["word1", "word2"],
  "method": "ward.D2",  // "ward.D2", "complete", "average", "single"
  "compute_significance": false,
  "n_bootstrap": 100
}
```

**Returns:**
```json
{
  "method": "ward.D2",
  "labels": ["word1", "word2"],
  "merge": [[-1, -2]],
  "height": [0.2],
  "order": [0, 1],
  "suggested_k_range": [2, 4]
}
```

#### `compare_trees`
Compare tree topologies using Robinson-Foulds distance.

**Parameters:**
```json
{
  "tree1_newick": "((en,de),(fr,es));",
  "tree2_newick": "((en,fr),(de,es));"
}
```

**Returns:**
```json
{
  "robinson_foulds": 2.0,
  "normalized_rf": 0.5,
  "max_possible_rf": 4.0,
  "trees_identical": false
}
```

#### `plot_dendrogram`
Generate publication-quality dendrogram.

**Parameters:**
```json
{
  "newick": "(en,de);",
  "output_path": "/tmp/tree.png",
  "format": "png",  // "png", "pdf", "svg"
  "width": 800,
  "height": 600
}
```

**Returns:**
```json
{
  "output_path": "/tmp/tree.png",
  "format": "png",
  "n_tips": 2
}
```

#### `cophenetic_correlation`
Compute tree quality metric.

**Parameters:**
```json
{
  "newick": "(en,de);",
  "distances": [[0.0, 0.3], [0.3, 0.0]],
  "labels": ["en", "de"]
}
```

**Returns:**
```json
{
  "correlation": 0.95,
  "interpretation": "Excellent tree fit"
}
```

## Performance

### Benchmarks

| Operation | Size | Time | Notes |
|-----------|------|------|-------|
| Tree inference (NJ) | 50 taxa | ~10ms | Fast |
| Tree inference (ML) | 50 taxa | ~50ms | Slower but more accurate |
| Bootstrap (100x) | 50 taxa | ~1-5s | Depends on method |
| Hierarchical clustering | 100 items | ~5-20ms | Very fast |

### Optimization Tips

1. **Use caching**: `PhyloService` caches inferred trees
2. **Reduce bootstrap replicates**: 50-100 is usually sufficient
3. **Prefer NJ over ML**: Faster for large datasets
4. **Batch operations**: Group multiple tree inferences

## Testing

### Unit Tests (Mocked)

```bash
cd backend
python3 -m pytest tests/test_r_integration.py -v
```

### Integration Tests (Requires R Service)

```bash
# Start R service
cd services/phylo-r
Rscript server.R &

# Run integration tests
cd backend
python3 -m pytest tests/test_r_integration.py::TestRServiceIntegration -v
```

## Troubleshooting

### Connection Refused

**Problem**: `ConnectionRefusedError: [Errno 61] Connection refused`

**Solution**:
1. Ensure R service is running: `cd services/phylo-r && Rscript server.R`
2. Check port: `lsof -i :50052`
3. Verify R packages: `Rscript install_deps.R`

### Timeout Errors

**Problem**: `TimeoutError: R service timeout`

**Solution**:
1. Increase timeout in client: `client._socket.settimeout(60)`
2. Reduce bootstrap replicates
3. Use faster methods (NJ instead of ML)

### Package Installation Fails

**Problem**: R package installation errors

**Solution**:
1. Update R: `brew upgrade r` (macOS)
2. Use CRAN mirror: `options(repos = "https://cloud.r-project.org")`
3. Install manually: `R -e "install.packages('ape')"`

## Future Enhancements

### Planned Features

1. **Bayesian inference** (MrBayes integration)
2. **Dated phylogenies** (chronos, PATHd8)
3. **Ancestral state reconstruction**
4. **Phylogenetic signal tests** (Blomberg's K, Pagel's λ)
5. **Parallel bootstrap** computation
6. **Tree visualization** improvements (fan trees, circular layouts)

### Potential Optimizations

1. **Connection pooling**: Reuse R connections
2. **Async communication**: Non-blocking RPC calls
3. **Result caching**: Redis for computed trees
4. **Batch processing**: Multiple trees in single request

## Related Documentation

- [Dependency Injection System](DEPENDENCY_INJECTION.md)
- [Similarity Architecture](SIMILARITY_ARCHITECTURE.md)
- [Storage System](STORAGE_SYSTEM.md)
- [R Service README](../services/phylo-r/README.md)

## References

### R Packages

- **ape**: Paradis, E., & Schliep, K. (2019). ape 5.0: an environment for modern phylogenetics and evolutionary analyses in R. *Bioinformatics*, 35(3), 526-528.
- **phangorn**: Schliep, K. P. (2011). phangorn: phylogenetic analysis in R. *Bioinformatics*, 27(4), 592-593.
- **pvclust**: Suzuki, R., & Shimodaira, H. (2006). Pvclust: an R package for assessing the uncertainty in hierarchical clustering. *Bioinformatics*, 22(12), 1540-1542.

### Phylogenetic Methods

- **Neighbor-Joining**: Saitou, N., & Nei, M. (1987). The neighbor-joining method: a new method for reconstructing phylogenetic trees. *Molecular Biology and Evolution*, 4(4), 406-425.
- **Maximum Likelihood**: Felsenstein, J. (1981). Evolutionary trees from DNA sequences: a maximum likelihood approach. *Journal of Molecular Evolution*, 17(6), 368-376.
- **Bootstrap**: Felsenstein, J. (1985). Confidence limits on phylogenies: an approach using the bootstrap. *Evolution*, 39(4), 783-791.

