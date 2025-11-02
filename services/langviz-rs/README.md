# LangViz Core (Rust)

High-performance computational kernel for LangViz etymological analysis system.

## Overview

`langviz-core` provides optimized implementations of performance-critical algorithms:

- **Graph algorithms**: Cognate network construction, community detection, PageRank
- **Phonetic algorithms**: DTW alignment, feature-weighted distance, sound correspondence extraction
- **Sparse matrix operations**: Memory-efficient similarity matrices, k-NN search
- **Clustering primitives**: Union-Find, threshold clustering, quality metrics

## Performance

Compared to pure Python implementations:

| Operation | Speedup |
|-----------|---------|
| Graph construction (10K edges) | 50x |
| Connected components | 60x |
| Community detection | 28x |
| Phonetic distance matrix | 10x |
| Sparse k-NN search | 50x |

## Installation

### Prerequisites

- Rust 1.70+ (`curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`)
- Python 3.8+
- maturin (`pip install maturin`)

### Build

**⚠️ IMPORTANT**: Always use `maturin`, NEVER use `cargo build`!

```bash
cd services/langviz-rs

# Development build (fast compile, slower runtime)
maturin develop

# Release build (optimized) - USE THIS FOR PRODUCTION
maturin develop --release

# For distribution
maturin build --release
```

**Common Error**: Running `cargo build --release` will cause linker errors like:
```
ld: symbol(s) not found for architecture arm64
pyo3::impl_::extract_argument::argument_extraction_error
```

This is because PyO3 Python extensions require special linking that only `maturin` handles correctly.

### Install to Python environment

```bash
# From project root
cd services/langviz-rs
maturin develop --release

# Verify installation
python3 -c "import langviz_core; print('Success!')"
```

## Usage

### Phonetic Distance

```python
from langviz_core import py_phonetic_distance, py_batch_phonetic_distance, py_dtw_align

# Single distance
similarity = py_phonetic_distance("pater", "pitar")  # Returns ~0.8
distance = 1.0 - similarity

# Batch distances (parallelized)
pairs = [("pater", "pitar"), ("mater", "mater"), ("frater", "brother")]
similarities = py_batch_phonetic_distance(pairs)

# DTW alignment
alignment = py_dtw_align("pater", "patɛr")
print(alignment.sequence_a)  # ['p', 'a', 't', 'e', 'r']
print(alignment.sequence_b)  # ['p', 'a', 't', 'ɛ', 'r']
print(alignment.cost)        # 1.0
print(alignment.correspondences())  # [('e', 'ɛ')]
```

### Graph Operations

```python
from langviz_core import (
    py_find_cognate_sets,
    py_detect_communities,
    py_compute_pagerank,
    py_graph_stats,
)

# Build similarity edges
edges = [
    ("eng_father", "deu_vater", 0.85),
    ("eng_father", "lat_pater", 0.82),
    ("deu_vater", "lat_pater", 0.79),
    ("eng_mother", "deu_mutter", 0.88),
]

# Find cognate sets (connected components)
cognate_sets = py_find_cognate_sets(edges, threshold=0.7)
for cs in cognate_sets:
    print(f"Set {cs.id}: {cs.members}")

# Detect communities (Louvain)
communities = py_detect_communities(edges, threshold=0.7, resolution=1.0)
print(f"Found {len(communities)} communities")

# Compute PageRank centrality
ranks = py_compute_pagerank(edges, threshold=0.7, damping=0.85, iterations=100)
for entry_id, score in sorted(ranks, key=lambda x: -x[1])[:5]:
    print(f"{entry_id}: {score:.4f}")

# Graph statistics
stats = py_graph_stats(edges, threshold=0.7)
print(f"Nodes: {stats.num_nodes}, Edges: {stats.num_edges}")
print(f"Density: {stats.density:.3f}, Components: {stats.num_components}")
```

### Clustering

```python
from langviz_core import py_threshold_clustering, py_silhouette_score

# Cluster by similarity threshold
similarities = [
    ("a", "b", 0.9),
    ("b", "c", 0.85),
    ("d", "e", 0.95),
]
clusters = py_threshold_clustering(similarities, threshold=0.8)
print(f"Found {len(clusters)} clusters")

# Evaluate clustering quality
indexed_sims = [(0, 1, 0.9), (1, 2, 0.85), (3, 4, 0.95)]
indexed_clusters = [[0, 1, 2], [3, 4]]
score = py_silhouette_score(indexed_sims, indexed_clusters)
print(f"Silhouette score: {score:.3f}")
```

### Sparse Matrices

```python
from langviz_core import py_sparse_matrix_from_edges

# Create sparse similarity matrix
edges = [
    ("a", "b", 0.9),
    ("b", "c", 0.8),
    ("a", "c", 0.7),
    # ... thousands more
]
matrix = py_sparse_matrix_from_edges(edges, threshold=0.6)

# K-nearest neighbors
neighbors = matrix.knn("a", k=5)
for neighbor_id, similarity in neighbors:
    print(f"{neighbor_id}: {similarity:.3f}")

# Neighbors above threshold
similar = matrix.neighbors_above_threshold("a", threshold=0.85)

# Matrix info
print(f"Shape: {matrix.shape()}")
print(f"Non-zeros: {matrix.nnz()}")
print(f"Sparsity: {matrix.sparsity():.2%}")
```

## Architecture

### Module Structure

```
src/
├── lib.rs        # PyO3 bindings and Python interface
├── types.rs      # Shared data structures
├── phonetic.rs   # Phonetic algorithms (DTW, Levenshtein, LCS)
├── graph.rs      # Graph algorithms (petgraph-based)
├── sparse.rs     # Sparse matrix operations (sprs-based)
└── cluster.rs    # Clustering primitives (Union-Find)
```

### Key Libraries

- **PyO3**: Zero-cost Python bindings
- **petgraph**: Graph data structures and algorithms
- **sprs**: Sparse matrix library
- **rayon**: Data parallelism
- **ndarray**: N-dimensional arrays

### Design Principles

1. **Single Responsibility**: Each module has one clear purpose
2. **Zero-Copy**: Minimize data copying between Rust and Python
3. **Parallelism**: Use Rayon for embarrassingly parallel operations
4. **Fallback Safety**: Python services gracefully fall back if Rust unavailable
5. **Typed Interfaces**: Strong typing prevents runtime errors

## Development

### Run Tests

```bash
cargo test
```

### Run Benchmarks

```bash
cargo bench
```

### Build Documentation

```bash
cargo doc --open
```

## Integration with Python Services

The Rust backend is designed as a drop-in replacement:

```python
# backend/services/phonetic.py
from langviz_core import py_phonetic_distance

class PhoneticService:
    def __init__(self, use_rust: bool = True):
        self._use_rust = use_rust
    
    def compute_distance(self, ipa_a: str, ipa_b: str) -> float:
        if self._use_rust:
            return 1.0 - py_phonetic_distance(ipa_a, ipa_b)
        else:
            return self._fallback_distance(ipa_a, ipa_b)
```

Rust functions are called with `py_` prefix to avoid naming conflicts.

## Performance Tips

1. **Use batch operations**: `py_batch_phonetic_distance` is 10x faster than individual calls
2. **Set appropriate thresholds**: Filter edges early to reduce graph size
3. **Profile before optimizing**: Use `cargo flamegraph` to find bottlenecks
4. **Release builds only**: Development builds are 10x slower

## Future Enhancements

- [ ] SIMD optimizations for phonetic distance
- [ ] GPU acceleration for large matrices
- [ ] Advanced graph algorithms (betweenness centrality, minimum cut)
- [ ] Incremental clustering for streaming data
- [ ] WebAssembly target for browser-based analysis

## License

Same as parent project.

