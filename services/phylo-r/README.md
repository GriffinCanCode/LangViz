# R Phylogenetic Analysis Service

JSON-RPC server providing statistical phylogenetic analysis for LangViz.

## Purpose

R excels at statistical computing and phylogenetic inference. This service provides capabilities that Python cannot match:

- **Phylogenetic tree inference** from distance matrices (Neighbor-Joining, UPGMA, Maximum Likelihood)
- **Bootstrap confidence analysis** with proper resampling
- **Hierarchical clustering** with statistical rigor (not greedy threshold methods)
- **Publication-quality dendrograms** with branch lengths and support values
- **Tree topology comparison** (Robinson-Foulds distance)
- **Cophenetic correlation** for tree quality assessment

## Architecture

Follows the Perl service pattern:
- JSON-RPC 2.0 protocol
- TCP socket communication (port 50052)
- Stateless request/response model
- Python client in `backend/interop/r_client.py`

## Dependencies

### R Packages

- **jsonlite**: JSON encoding/decoding
- **ape**: Analysis of Phylogenetics and Evolution
- **phangorn**: Phylogenetic Reconstruction and Analysis
- **pvclust**: Hierarchical clustering with p-values

### Installation

```bash
cd services/phylo-r
Rscript install_deps.R
```

Or manually:
```r
install.packages(c("jsonlite", "ape", "phangorn", "pvclust"))
```

## Usage

### Start Server

```bash
cd services/phylo-r
Rscript server.R
```

The server listens on `localhost:50052` by default.

### Python Client

```python
from backend.interop.r_client import RPhyloClient
import numpy as np

# Example distance matrix (Swadesh distances)
distances = np.array([
    [0.0, 0.3, 0.5, 0.7],
    [0.3, 0.0, 0.4, 0.6],
    [0.5, 0.4, 0.0, 0.5],
    [0.7, 0.6, 0.5, 0.0]
])

labels = ["English", "German", "French", "Hindi"]

with RPhyloClient() as client:
    # Infer tree
    tree = client.infer_tree(distances, labels, method="nj")
    print(tree.newick)
    print(f"Cophenetic correlation: {tree.cophenetic_correlation:.3f}")
    
    # Bootstrap analysis
    bootstrap = client.bootstrap_tree(distances, labels, n_bootstrap=100)
    print(f"Bootstrap support: {bootstrap.support_values}")
    
    # Hierarchical clustering
    clustering = client.cluster_hierarchical(distances, labels, method="ward.D2")
    print(f"Suggested clusters: {clustering.suggested_k_range}")
```

## API Methods

### `infer_tree`
Infer phylogenetic tree from distance matrix.

**Parameters:**
- `distances`: Square distance matrix (nested list)
- `labels`: Optional tip labels
- `method`: "nj" (Neighbor-Joining), "upgma" (UPGMA), "ml" (Maximum Likelihood)

**Returns:**
- `newick`: Tree in Newick format
- `cophenetic_correlation`: Tree quality metric (0-1)
- Metadata: n_tips, rooted, binary, etc.

### `bootstrap_tree`
Bootstrap confidence analysis.

**Parameters:**
- `distances`: Square distance matrix
- `labels`: Optional tip labels
- `method`: Tree inference method
- `n_bootstrap`: Number of replicates (default 100)

**Returns:**
- `consensus_newick`: Majority-rule consensus tree
- `support_values`: Bootstrap support for each node

### `cluster_hierarchical`
Hierarchical clustering with statistical methods.

**Parameters:**
- `distances`: Square distance matrix
- `labels`: Optional item labels
- `method`: "ward.D2", "complete", "average", "single"
- `compute_significance`: Compute p-values (slow)
- `n_bootstrap`: Bootstrap replicates for significance

**Returns:**
- Dendrogram structure (merge matrix, heights)
- `suggested_k_range`: Optimal number of clusters

### `compare_trees`
Compare two tree topologies.

**Parameters:**
- `tree1_newick`: First tree in Newick format
- `tree2_newick`: Second tree in Newick format

**Returns:**
- `robinson_foulds`: Topology distance
- `normalized_rf`: Normalized distance (0-1)
- `trees_identical`: Boolean

### `plot_dendrogram`
Generate publication-quality dendrogram.

**Parameters:**
- `newick`: Tree in Newick format
- `output_path`: File path for output
- `format`: "png", "pdf", "svg"
- `width`, `height`: Dimensions

**Returns:**
- Metadata about saved plot

### `cophenetic_correlation`
Compute tree quality metric.

**Parameters:**
- `newick`: Tree in Newick format
- `distances`: Original distance matrix

**Returns:**
- `correlation`: Cophenetic correlation (0-1)
- `interpretation`: Human-readable quality assessment

## Design Principles

### Separation of Concerns

**R handles:**
- Statistical phylogenetic inference
- Bootstrap resampling
- Hierarchical clustering
- Publication-quality plots
- Tree topology tests

**Python handles:**
- API orchestration
- Fast tree lookups (cached)
- Integration with similarity pipeline
- Database storage

**Rust will handle (future):**
- Phonetic distance computation (CPU-intensive)
- Graph algorithms

### Why R over Python?

1. **ape/phangorn** are gold-standard phylogenetics packages (30+ years development)
2. **Statistical rigor**: Proper bootstrap, likelihood methods, topology tests
3. **Publication quality**: R graphics are journal-ready
4. **Ecosystem**: Comprehensive phylogenetics tools (no Python equivalent)
5. **Performance**: Optimized Fortran/C backends in ape

### Why Not Just Use Python Libraries?

- **dendropy**: Less mature, slower, limited methods
- **scikit-bio**: Basic phylogenetics, no advanced methods
- **ete3**: Visualization-focused, not inference
- R's ecosystem is **unmatched** for phylogenetic analysis

## Testing

```bash
# Unit tests
cd services/phylo-r
Rscript -e "testthat::test_dir('tests')"

# Integration test
cd backend
python3 -m pytest tests/test_r_integration.py
```

## Troubleshooting

### Connection Refused
- Ensure R server is running: `Rscript server.R`
- Check port 50052 is not in use: `lsof -i :50052`

### Package Installation Fails
- Update R: `brew upgrade r` (macOS) or equivalent
- Use CRAN mirror: `options(repos = "https://cloud.r-project.org")`

### Timeout Errors
- Increase timeout in Python client (`_socket.settimeout(60)`)
- Bootstrap with many replicates can be slow

## Performance

- **Tree inference**: ~10-50ms for 50 taxa
- **Bootstrap (100 replicates)**: ~1-5 seconds for 50 taxa
- **Hierarchical clustering**: ~5-20ms for 100 items

For large datasets (>1000 taxa), consider:
- Subsetting to representative taxa
- Using faster methods (NJ vs ML)
- Reducing bootstrap replicates

## Future Enhancements

- Bayesian inference (MrBayes integration)
- Dated phylogenies (chronos, PATHd8)
- Ancestral state reconstruction
- Phylogenetic signal tests (K, λ)
- Parallel bootstrap computation

