//! Clustering primitives for cognate detection.

use ahash::AHashMap;
use rayon::prelude::*;
use std::collections::HashMap;

/// Union-Find data structure for connected components
pub struct UnionFind {
    parent: Vec<usize>,
    rank: Vec<usize>,
}

impl UnionFind {
    /// Create new UnionFind with n elements
    pub fn new(n: usize) -> Self {
        Self {
            parent: (0..n).collect(),
            rank: vec![0; n],
        }
    }

    /// Find root with path compression
    pub fn find(&mut self, x: usize) -> usize {
        if self.parent[x] != x {
            self.parent[x] = self.find(self.parent[x]);
        }
        self.parent[x]
    }

    /// Union by rank
    pub fn union(&mut self, x: usize, y: usize) {
        let root_x = self.find(x);
        let root_y = self.find(y);

        if root_x == root_y {
            return;
        }

        match self.rank[root_x].cmp(&self.rank[root_y]) {
            std::cmp::Ordering::Less => {
                self.parent[root_x] = root_y;
            }
            std::cmp::Ordering::Greater => {
                self.parent[root_y] = root_x;
            }
            std::cmp::Ordering::Equal => {
                self.parent[root_y] = root_x;
                self.rank[root_x] += 1;
            }
        }
    }

    /// Get all connected components
    pub fn components(&mut self) -> Vec<Vec<usize>> {
        let n = self.parent.len();
        let mut groups: HashMap<usize, Vec<usize>> = HashMap::new();

        for i in 0..n {
            let root = self.find(i);
            groups.entry(root).or_insert_with(Vec::new).push(i);
        }

        groups.into_values().collect()
    }
}

/// Cluster entries by similarity threshold using Union-Find
pub fn threshold_clustering(
    similarities: Vec<(usize, usize, f64)>,
    n_items: usize,
    threshold: f64,
) -> Vec<Vec<usize>> {
    let mut uf = UnionFind::new(n_items);

    for (i, j, sim) in similarities {
        if sim >= threshold {
            uf.union(i, j);
        }
    }

    uf.components()
}

/// Cluster with string IDs
pub fn threshold_clustering_with_ids(
    similarities: Vec<(String, String, f64)>,
    threshold: f64,
) -> Vec<Vec<String>> {
    // Build ID mapping
    let mut id_set: std::collections::HashSet<String> = std::collections::HashSet::new();
    for (a, b, _) in &similarities {
        id_set.insert(a.clone());
        id_set.insert(b.clone());
    }

    let mut ids: Vec<String> = id_set.into_iter().collect();
    ids.sort();

    let id_to_idx: AHashMap<&str, usize> = ids
        .iter()
        .enumerate()
        .map(|(idx, id)| (id.as_str(), idx))
        .collect();

    // Convert to indices
    let indexed_similarities: Vec<(usize, usize, f64)> = similarities
        .into_iter()
        .filter_map(|(a, b, sim)| {
            let i = id_to_idx.get(a.as_str())?;
            let j = id_to_idx.get(b.as_str())?;
            Some((*i, *j, sim))
        })
        .collect();

    // Cluster
    let clusters = threshold_clustering(indexed_similarities, ids.len(), threshold);

    // Convert back to IDs
    clusters
        .into_iter()
        .map(|cluster| cluster.into_iter().map(|idx| ids[idx].clone()).collect())
        .collect()
}

/// Compute silhouette score for clustering quality
pub fn silhouette_score(
    similarities: &[(usize, usize, f64)],
    clusters: &[Vec<usize>],
) -> f64 {
    // Build similarity lookup
    let mut sim_map: HashMap<(usize, usize), f64> = HashMap::new();
    for &(i, j, sim) in similarities {
        sim_map.insert((i.min(j), i.max(j)), sim);
    }

    // Find cluster assignment for each point
    let mut cluster_assignment: HashMap<usize, usize> = HashMap::new();
    for (cluster_id, cluster) in clusters.iter().enumerate() {
        for &point in cluster {
            cluster_assignment.insert(point, cluster_id);
        }
    }

    // Compute silhouette for each point
    let points: Vec<usize> = cluster_assignment.keys().copied().collect();

    let scores: Vec<f64> = points
        .par_iter()
        .map(|&point| {
            let cluster_id = cluster_assignment[&point];
            let cluster = &clusters[cluster_id];

            if cluster.len() == 1 {
                return 0.0; // Singleton cluster
            }

            // a: mean intra-cluster distance
            let mut intra_sum = 0.0;
            let mut intra_count = 0;
            for &other in cluster {
                if other != point {
                    let key = (point.min(other), point.max(other));
                    if let Some(&sim) = sim_map.get(&key) {
                        intra_sum += 1.0 - sim; // Convert similarity to distance
                        intra_count += 1;
                    }
                }
            }
            let a = if intra_count > 0 {
                intra_sum / intra_count as f64
            } else {
                0.0
            };

            // b: min mean inter-cluster distance
            let mut min_inter = f64::INFINITY;
            for (other_cluster_id, other_cluster) in clusters.iter().enumerate() {
                if other_cluster_id != cluster_id {
                    let mut inter_sum = 0.0;
                    let mut inter_count = 0;
                    for &other in other_cluster {
                        let key = (point.min(other), point.max(other));
                        if let Some(&sim) = sim_map.get(&key) {
                            inter_sum += 1.0 - sim;
                            inter_count += 1;
                        }
                    }
                    if inter_count > 0 {
                        let mean_inter = inter_sum / inter_count as f64;
                        min_inter = min_inter.min(mean_inter);
                    }
                }
            }
            let b = min_inter;

            // Silhouette coefficient
            if a < b {
                1.0 - (a / b)
            } else if a > b {
                (b / a) - 1.0
            } else {
                0.0
            }
        })
        .collect();

    // Mean silhouette score
    if scores.is_empty() {
        0.0
    } else {
        scores.iter().sum::<f64>() / scores.len() as f64
    }
}

/// Compute within-cluster variance
pub fn within_cluster_variance(
    similarities: &[(usize, usize, f64)],
    clusters: &[Vec<usize>],
) -> f64 {
    let mut sim_map: HashMap<(usize, usize), f64> = HashMap::new();
    for &(i, j, sim) in similarities {
        sim_map.insert((i.min(j), i.max(j)), sim);
    }

    let mut total_variance = 0.0;
    let mut total_pairs = 0;

    for cluster in clusters {
        if cluster.len() < 2 {
            continue;
        }

        // Compute mean similarity within cluster
        let mut sum = 0.0;
        let mut count = 0;
        for i in 0..cluster.len() {
            for j in i + 1..cluster.len() {
                let key = (cluster[i].min(cluster[j]), cluster[i].max(cluster[j]));
                if let Some(&sim) = sim_map.get(&key) {
                    sum += sim;
                    count += 1;
                }
            }
        }

        if count > 0 {
            let mean = sum / count as f64;

            // Compute variance
            let mut variance_sum = 0.0;
            for i in 0..cluster.len() {
                for j in i + 1..cluster.len() {
                    let key = (cluster[i].min(cluster[j]), cluster[i].max(cluster[j]));
                    if let Some(&sim) = sim_map.get(&key) {
                        variance_sum += (sim - mean).powi(2);
                    }
                }
            }

            total_variance += variance_sum;
            total_pairs += count;
        }
    }

    if total_pairs > 0 {
        total_variance / total_pairs as f64
    } else {
        0.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_union_find() {
        let mut uf = UnionFind::new(5);
        uf.union(0, 1);
        uf.union(2, 3);
        uf.union(1, 2);

        assert_eq!(uf.find(0), uf.find(3));
        assert_ne!(uf.find(0), uf.find(4));
    }

    #[test]
    fn test_threshold_clustering() {
        let similarities = vec![
            (0, 1, 0.9),
            (1, 2, 0.85),
            (3, 4, 0.95),
        ];

        let clusters = threshold_clustering(similarities, 5, 0.8);
        assert_eq!(clusters.len(), 2); // Two clusters: {0,1,2} and {3,4}
    }

    #[test]
    fn test_clustering_with_ids() {
        let similarities = vec![
            ("a".to_string(), "b".to_string(), 0.9),
            ("b".to_string(), "c".to_string(), 0.85),
        ];

        let clusters = threshold_clustering_with_ids(similarities, 0.8);
        assert!(!clusters.is_empty());
        assert!(clusters[0].len() >= 2);
    }
}

