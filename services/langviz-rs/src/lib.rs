//! LangViz Core: High-performance computational kernel for etymological analysis.
//!
//! Provides Python bindings via PyO3 for:
//! - Graph algorithms (cognate networks)
//! - Phonetic algorithms (DTW, feature-weighted distance)
//! - Sparse matrix operations
//! - Clustering primitives

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

mod cluster;
mod graph;
mod phonetic;
mod sparse;
mod types;

use cluster::{threshold_clustering_with_ids, silhouette_score, within_cluster_variance};
use graph::{CognateGraph, GraphStats};
use phonetic::{
    batch_phonetic_distance, compute_similarity_matrix, dtw_align, extract_sound_correspondences,
    lcs_ratio, phonetic_distance,
};
use sparse::{batch_knn, threshold_filter, SparseSimilarityMatrix};
use types::{Alignment, CognateSet, SimilarityEdge};

// ============================================================================
// PHONETIC FUNCTIONS
// ============================================================================

#[pyfunction]
fn py_phonetic_distance(ipa_a: &str, ipa_b: &str) -> PyResult<f64> {
    Ok(phonetic_distance(ipa_a, ipa_b))
}

#[pyfunction]
fn py_batch_phonetic_distance(pairs: Vec<(String, String)>) -> PyResult<Vec<f64>> {
    Ok(batch_phonetic_distance(pairs))
}

#[pyfunction]
fn py_lcs_ratio(ipa_a: &str, ipa_b: &str) -> PyResult<f64> {
    Ok(lcs_ratio(ipa_a, ipa_b))
}

#[pyfunction]
fn py_dtw_align(ipa_a: &str, ipa_b: &str) -> PyResult<PyAlignment> {
    let alignment = dtw_align(ipa_a, ipa_b);
    Ok(PyAlignment::from(alignment))
}

#[pyfunction]
fn py_compute_similarity_matrix(ipa_strings: Vec<String>) -> PyResult<Vec<Vec<f64>>> {
    let matrix = compute_similarity_matrix(&ipa_strings);
    let rows: Vec<Vec<f64>> = matrix
        .outer_iter()
        .map(|row| row.to_vec())
        .collect();
    Ok(rows)
}

// ============================================================================
// GRAPH FUNCTIONS
// ============================================================================

#[pyfunction]
fn py_build_cognate_graph(
    edges: Vec<(String, String, f64)>,
    threshold: f64,
) -> PyResult<usize> {
    let similarity_edges: Vec<SimilarityEdge> = edges
        .into_iter()
        .map(|(s, t, w)| SimilarityEdge::new(s, t, w))
        .collect();

    let _graph = CognateGraph::from_edges(similarity_edges, threshold);
    
    // Store in global registry (simplified for now - return placeholder)
    Ok(0)
}

#[pyfunction]
fn py_find_cognate_sets(edges: Vec<(String, String, f64)>, threshold: f64) -> PyResult<Vec<PyCognateSet>> {
    let similarity_edges: Vec<SimilarityEdge> = edges
        .into_iter()
        .map(|(s, t, w)| SimilarityEdge::new(s, t, w))
        .collect();

    let graph = CognateGraph::from_edges(similarity_edges, threshold);
    let sets = graph.find_cognate_sets();
    
    Ok(sets.into_iter().map(PyCognateSet::from).collect())
}

#[pyfunction]
fn py_detect_communities(
    edges: Vec<(String, String, f64)>,
    threshold: f64,
    resolution: f64,
) -> PyResult<Vec<Vec<String>>> {
    let similarity_edges: Vec<SimilarityEdge> = edges
        .into_iter()
        .map(|(s, t, w)| SimilarityEdge::new(s, t, w))
        .collect();

    let graph = CognateGraph::from_edges(similarity_edges, threshold);
    Ok(graph.detect_communities(resolution))
}

#[pyfunction]
fn py_compute_pagerank(
    edges: Vec<(String, String, f64)>,
    threshold: f64,
    damping: f64,
    iterations: usize,
) -> PyResult<Vec<(String, f64)>> {
    let similarity_edges: Vec<SimilarityEdge> = edges
        .into_iter()
        .map(|(s, t, w)| SimilarityEdge::new(s, t, w))
        .collect();

    let graph = CognateGraph::from_edges(similarity_edges, threshold);
    let ranks = graph.compute_pagerank(damping, iterations);
    
    let mut result: Vec<(String, f64)> = ranks.into_iter().collect();
    result.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    
    Ok(result)
}

#[pyfunction]
fn py_graph_stats(edges: Vec<(String, String, f64)>, threshold: f64) -> PyResult<PyGraphStats> {
    let similarity_edges: Vec<SimilarityEdge> = edges
        .into_iter()
        .map(|(s, t, w)| SimilarityEdge::new(s, t, w))
        .collect();

    let graph = CognateGraph::from_edges(similarity_edges, threshold);
    Ok(PyGraphStats::from(graph.stats()))
}

#[pyfunction]
fn py_graph_to_json(edges: Vec<(String, String, f64)>, threshold: f64) -> PyResult<String> {
    let similarity_edges: Vec<SimilarityEdge> = edges
        .into_iter()
        .map(|(s, t, w)| SimilarityEdge::new(s, t, w))
        .collect();

    let graph = CognateGraph::from_edges(similarity_edges, threshold);
    Ok(graph.to_json())
}

// ============================================================================
// CLUSTERING FUNCTIONS
// ============================================================================

#[pyfunction]
fn py_threshold_clustering(
    similarities: Vec<(String, String, f64)>,
    threshold: f64,
) -> PyResult<Vec<Vec<String>>> {
    Ok(threshold_clustering_with_ids(similarities, threshold))
}

#[pyfunction]
fn py_silhouette_score(
    similarities: Vec<(usize, usize, f64)>,
    clusters: Vec<Vec<usize>>,
) -> PyResult<f64> {
    Ok(silhouette_score(&similarities, &clusters))
}

#[pyfunction]
fn py_within_cluster_variance(
    similarities: Vec<(usize, usize, f64)>,
    clusters: Vec<Vec<usize>>,
) -> PyResult<f64> {
    Ok(within_cluster_variance(&similarities, &clusters))
}

// ============================================================================
// SPARSE MATRIX FUNCTIONS
// ============================================================================

#[pyfunction]
fn py_sparse_matrix_from_edges(
    edges: Vec<(String, String, f64)>,
    threshold: f64,
) -> PyResult<PySparseMatrix> {
    let matrix = SparseSimilarityMatrix::from_edges(edges, threshold);
    Ok(PySparseMatrix { inner: matrix })
}

#[pyfunction]
fn py_threshold_filter(
    edges: Vec<(String, String, f64)>,
    threshold: f64,
) -> PyResult<Vec<(String, String, f64)>> {
    Ok(threshold_filter(edges, threshold))
}

// ============================================================================
// PYTHON WRAPPER TYPES
// ============================================================================

#[pyclass]
struct PyAlignment {
    #[pyo3(get)]
    sequence_a: Vec<String>,
    #[pyo3(get)]
    sequence_b: Vec<String>,
    #[pyo3(get)]
    cost: f64,
}

impl From<Alignment> for PyAlignment {
    fn from(alignment: Alignment) -> Self {
        Self {
            sequence_a: alignment.sequence_a,
            sequence_b: alignment.sequence_b,
            cost: alignment.cost,
        }
    }
}

#[pymethods]
impl PyAlignment {
    fn correspondences(&self) -> Vec<(String, String)> {
        let mut rules = Vec::new();
        for i in 0..self.sequence_a.len().min(self.sequence_b.len()) {
            if self.sequence_a[i] != self.sequence_b[i]
                && self.sequence_a[i] != "-"
                && self.sequence_b[i] != "-"
            {
                rules.push((self.sequence_a[i].clone(), self.sequence_b[i].clone()));
            }
        }
        rules
    }
}

#[pyclass]
struct PyCognateSet {
    #[pyo3(get)]
    id: usize,
    #[pyo3(get)]
    members: Vec<String>,
    #[pyo3(get)]
    size: usize,
}

impl From<CognateSet> for PyCognateSet {
    fn from(set: CognateSet) -> Self {
        Self {
            id: set.id,
            members: set.members,
            size: set.size,
        }
    }
}

#[pyclass]
struct PyGraphStats {
    #[pyo3(get)]
    num_nodes: usize,
    #[pyo3(get)]
    num_edges: usize,
    #[pyo3(get)]
    avg_degree: f64,
    #[pyo3(get)]
    density: f64,
    #[pyo3(get)]
    num_components: usize,
}

impl From<GraphStats> for PyGraphStats {
    fn from(stats: GraphStats) -> Self {
        Self {
            num_nodes: stats.num_nodes,
            num_edges: stats.num_edges,
            avg_degree: stats.avg_degree,
            density: stats.density,
            num_components: stats.num_components,
        }
    }
}

#[pyclass]
struct PySparseMatrix {
    inner: SparseSimilarityMatrix,
}

#[pymethods]
impl PySparseMatrix {
    fn knn(&self, entry_id: &str, k: usize) -> Vec<(String, f64)> {
        self.inner.knn(entry_id, k)
    }

    fn neighbors_above_threshold(&self, entry_id: &str, threshold: f64) -> Vec<(String, f64)> {
        self.inner.neighbors_above_threshold(entry_id, threshold)
    }

    fn shape(&self) -> (usize, usize) {
        self.inner.shape()
    }

    fn nnz(&self) -> usize {
        self.inner.nnz()
    }

    fn sparsity(&self) -> f64 {
        self.inner.sparsity()
    }

    fn entry_ids(&self) -> Vec<String> {
        self.inner.entry_ids().to_vec()
    }
}

// ============================================================================
// MODULE DEFINITION
// ============================================================================

#[pymodule]
fn langviz_core(_py: Python, m: &PyModule) -> PyResult<()> {
    // Phonetic functions
    m.add_function(wrap_pyfunction!(py_phonetic_distance, m)?)?;
    m.add_function(wrap_pyfunction!(py_batch_phonetic_distance, m)?)?;
    m.add_function(wrap_pyfunction!(py_lcs_ratio, m)?)?;
    m.add_function(wrap_pyfunction!(py_dtw_align, m)?)?;
    m.add_function(wrap_pyfunction!(py_compute_similarity_matrix, m)?)?;

    // Graph functions
    m.add_function(wrap_pyfunction!(py_build_cognate_graph, m)?)?;
    m.add_function(wrap_pyfunction!(py_find_cognate_sets, m)?)?;
    m.add_function(wrap_pyfunction!(py_detect_communities, m)?)?;
    m.add_function(wrap_pyfunction!(py_compute_pagerank, m)?)?;
    m.add_function(wrap_pyfunction!(py_graph_stats, m)?)?;
    m.add_function(wrap_pyfunction!(py_graph_to_json, m)?)?;

    // Clustering functions
    m.add_function(wrap_pyfunction!(py_threshold_clustering, m)?)?;
    m.add_function(wrap_pyfunction!(py_silhouette_score, m)?)?;
    m.add_function(wrap_pyfunction!(py_within_cluster_variance, m)?)?;

    // Sparse matrix functions
    m.add_function(wrap_pyfunction!(py_sparse_matrix_from_edges, m)?)?;
    m.add_function(wrap_pyfunction!(py_threshold_filter, m)?)?;

    // Classes
    m.add_class::<PyAlignment>()?;
    m.add_class::<PyCognateSet>()?;
    m.add_class::<PyGraphStats>()?;
    m.add_class::<PySparseMatrix>()?;

    Ok(())
}

