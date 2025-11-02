//! Sparse matrix operations for efficient similarity computation.

use ndarray::{Array1, Array2};
use ordered_float::OrderedFloat;
use rayon::prelude::*;
use sprs::{CsMat, TriMat};
use std::collections::BinaryHeap;

/// Sparse similarity matrix optimized for memory efficiency
pub struct SparseSimilarityMatrix {
    /// Sparse matrix in CSR format
    matrix: CsMat<f64>,
    /// Row IDs (entry IDs)
    row_ids: Vec<String>,
    /// Column IDs (entry IDs)
    col_ids: Vec<String>,
}

impl SparseSimilarityMatrix {
    /// Build sparse matrix from similarity edges with threshold
    pub fn from_edges(
        edges: Vec<(String, String, f64)>,
        threshold: f64,
    ) -> Self {
        // Create ID mappings
        let mut id_set: std::collections::HashSet<String> = std::collections::HashSet::new();
        for (a, b, _) in &edges {
            id_set.insert(a.clone());
            id_set.insert(b.clone());
        }

        let mut ids: Vec<String> = id_set.into_iter().collect();
        ids.sort();

        let id_to_idx: std::collections::HashMap<&str, usize> = ids
            .iter()
            .enumerate()
            .map(|(idx, id)| (id.as_str(), idx))
            .collect();

        let n = ids.len();
        let mut triplets = TriMat::new((n, n));

        // Add edges above threshold
        for (a, b, weight) in edges {
            if weight >= threshold {
                let i = id_to_idx[a.as_str()];
                let j = id_to_idx[b.as_str()];
                triplets.add_triplet(i, j, weight);
                if i != j {
                    triplets.add_triplet(j, i, weight); // Symmetric
                }
            }
        }

        // Add diagonal (self-similarity = 1.0)
        for i in 0..n {
            triplets.add_triplet(i, i, 1.0);
        }

        let matrix = triplets.to_csr();

        Self {
            matrix,
            row_ids: ids.clone(),
            col_ids: ids,
        }
    }

    /// Get k-nearest neighbors for a given entry
    pub fn knn(&self, entry_id: &str, k: usize) -> Vec<(String, f64)> {
        let idx = match self.row_ids.iter().position(|id| id == entry_id) {
            Some(i) => i,
            None => return vec![],
        };

        // Get row from sparse matrix
        let row = self.matrix.outer_view(idx).unwrap();

        // Use max-heap to find top-k
        let mut heap: BinaryHeap<(OrderedFloat<f64>, usize)> = BinaryHeap::new();

        for (col_idx, &value) in row.iter() {
            if col_idx != idx {
                // Skip self
                heap.push((OrderedFloat(value), col_idx));
            }
        }

        // Extract top k
        let mut results = Vec::new();
        for _ in 0..k {
            if let Some((score, col_idx)) = heap.pop() {
                results.push((self.col_ids[col_idx].clone(), score.0));
            } else {
                break;
            }
        }

        results
    }

    /// Get all neighbors above threshold
    pub fn neighbors_above_threshold(&self, entry_id: &str, threshold: f64) -> Vec<(String, f64)> {
        let idx = match self.row_ids.iter().position(|id| id == entry_id) {
            Some(i) => i,
            None => return vec![],
        };

        let row = self.matrix.outer_view(idx).unwrap();

        row.iter()
            .filter(|&(col_idx, &value)| col_idx != idx && value >= threshold)
            .map(|(col_idx, &value)| (self.col_ids[col_idx].clone(), value))
            .collect()
    }

    /// Compute dense similarity matrix for subset of entries
    pub fn to_dense_submatrix(&self, entry_ids: &[String]) -> Array2<f64> {
        let indices: Vec<usize> = entry_ids
            .iter()
            .filter_map(|id| self.row_ids.iter().position(|rid| rid == id))
            .collect();

        let n = indices.len();
        let mut dense = Array2::<f64>::zeros((n, n));

        for (i, &row_idx) in indices.iter().enumerate() {
            let row = self.matrix.outer_view(row_idx).unwrap();
            for (col_idx, &value) in row.iter() {
                if let Some(j) = indices.iter().position(|&idx| idx == col_idx) {
                    dense[[i, j]] = value;
                }
            }
        }

        dense
    }

    /// Matrix-vector multiplication (for iterative algorithms)
    pub fn matvec(&self, vec: &Array1<f64>) -> Array1<f64> {
        let mut result = Array1::<f64>::zeros(self.matrix.rows());

        for (row_idx, row) in self.matrix.outer_iterator().enumerate() {
            let mut sum = 0.0;
            for (col_idx, &value) in row.iter() {
                sum += value * vec[col_idx];
            }
            result[row_idx] = sum;
        }

        result
    }

    /// Get matrix dimensions
    pub fn shape(&self) -> (usize, usize) {
        (self.matrix.rows(), self.matrix.cols())
    }

    /// Get number of non-zero entries
    pub fn nnz(&self) -> usize {
        self.matrix.nnz()
    }

    /// Get sparsity ratio
    pub fn sparsity(&self) -> f64 {
        let total = self.matrix.rows() * self.matrix.cols();
        if total == 0 {
            0.0
        } else {
            1.0 - (self.matrix.nnz() as f64 / total as f64)
        }
    }

    /// Get entry IDs
    pub fn entry_ids(&self) -> &[String] {
        &self.row_ids
    }
}

/// Batch compute top-k similar entries for multiple queries
pub fn batch_knn(
    matrix: &SparseSimilarityMatrix,
    query_ids: &[String],
    k: usize,
) -> Vec<Vec<(String, f64)>> {
    query_ids
        .par_iter()
        .map(|id| matrix.knn(id, k))
        .collect()
}

/// Filter edges by threshold in parallel
pub fn threshold_filter(edges: Vec<(String, String, f64)>, threshold: f64) -> Vec<(String, String, f64)> {
    edges
        .into_par_iter()
        .filter(|(_, _, weight)| *weight >= threshold)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sparse_matrix_creation() {
        let edges = vec![
            ("a".to_string(), "b".to_string(), 0.9),
            ("b".to_string(), "c".to_string(), 0.8),
            ("a".to_string(), "c".to_string(), 0.7),
        ];

        let matrix = SparseSimilarityMatrix::from_edges(edges, 0.5);
        assert_eq!(matrix.shape().0, 3);
        assert!(matrix.nnz() > 0);
    }

    #[test]
    fn test_knn() {
        let edges = vec![
            ("a".to_string(), "b".to_string(), 0.9),
            ("a".to_string(), "c".to_string(), 0.7),
            ("a".to_string(), "d".to_string(), 0.5),
        ];

        let matrix = SparseSimilarityMatrix::from_edges(edges, 0.4);
        let neighbors = matrix.knn("a", 2);
        assert_eq!(neighbors.len(), 2);
        assert_eq!(neighbors[0].0, "b"); // Highest similarity
    }

    #[test]
    fn test_sparsity() {
        let edges = vec![
            ("a".to_string(), "b".to_string(), 0.9),
        ];

        let matrix = SparseSimilarityMatrix::from_edges(edges, 0.5);
        let sparsity = matrix.sparsity();
        assert!(sparsity > 0.0 && sparsity < 1.0);
    }
}

