//! High-performance graph algorithms for cognate network analysis.
//!
//! Replaces NetworkX operations with optimized Rust implementations using petgraph.

use ahash::AHashMap;
use petgraph::graph::{Graph, NodeIndex, UnGraph};
use petgraph::algo::{connected_components, dijkstra};
use petgraph::visit::EdgeRef;
use rayon::prelude::*;
use std::collections::HashMap;

use crate::types::{CognateSet, SimilarityEdge};

/// High-performance graph builder for cognate networks
pub struct CognateGraph {
    graph: UnGraph<String, f64>,
    node_map: AHashMap<String, NodeIndex>,
}

impl CognateGraph {
    /// Create new empty graph
    pub fn new() -> Self {
        Self {
            graph: UnGraph::new_undirected(),
            node_map: AHashMap::new(),
        }
    }

    /// Build graph from similarity edges with threshold filtering
    pub fn from_edges(edges: Vec<SimilarityEdge>, threshold: f64) -> Self {
        let mut graph_builder = Self::new();

        // Filter edges by threshold
        let filtered: Vec<_> = edges
            .into_par_iter()
            .filter(|e| e.weight.0 >= threshold)
            .collect();

        // Add nodes and edges
        for edge in filtered {
            graph_builder.add_edge(edge.source, edge.target, edge.weight.0);
        }

        graph_builder
    }

    /// Add edge to graph (creates nodes if needed)
    pub fn add_edge(&mut self, source: String, target: String, weight: f64) {
        let source_idx = self.get_or_create_node(source);
        let target_idx = self.get_or_create_node(target);
        self.graph.add_edge(source_idx, target_idx, weight);
    }

    /// Get or create node index
    fn get_or_create_node(&mut self, id: String) -> NodeIndex {
        if let Some(&idx) = self.node_map.get(&id) {
            idx
        } else {
            let idx = self.graph.add_node(id.clone());
            self.node_map.insert(id, idx);
            idx
        }
    }

    /// Find connected components (cognate sets)
    pub fn find_cognate_sets(&self) -> Vec<CognateSet> {
        let _num_components = connected_components(&self.graph);
        let mut components: HashMap<usize, Vec<String>> = HashMap::new();

        // Use Tarjan's algorithm implicitly through petgraph
        let mut component_map = vec![0; self.graph.node_count()];
        let mut current_component = 0;

        for node_idx in self.graph.node_indices() {
            if component_map[node_idx.index()] == 0 {
                current_component += 1;
                self.mark_component(node_idx, current_component, &mut component_map);
            }
        }

        // Group nodes by component
        for (idx, node) in self.graph.node_indices().zip(self.graph.node_weights()) {
            let comp_id = component_map[idx.index()];
            components
                .entry(comp_id)
                .or_insert_with(Vec::new)
                .push(node.clone());
        }

        // Convert to CognateSet structs
        components
            .into_iter()
            .map(|(id, members)| CognateSet::new(id, members))
            .collect()
    }

    /// Mark connected component using DFS
    fn mark_component(&self, start: NodeIndex, component_id: usize, component_map: &mut [usize]) {
        let mut stack = vec![start];
        while let Some(node) = stack.pop() {
            if component_map[node.index()] != 0 {
                continue;
            }
            component_map[node.index()] = component_id;

            for neighbor in self.graph.neighbors(node) {
                if component_map[neighbor.index()] == 0 {
                    stack.push(neighbor);
                }
            }
        }
    }

    /// Detect communities using Louvain algorithm (simplified)
    pub fn detect_communities(&self, resolution: f64) -> Vec<Vec<String>> {
        // Simplified Louvain: use modularity-based greedy clustering
        let mut communities: Vec<Vec<NodeIndex>> = self
            .graph
            .node_indices()
            .map(|idx| vec![idx])
            .collect();

        let mut improved = true;
        let mut iteration = 0;
        const MAX_ITERATIONS: usize = 10;

        while improved && iteration < MAX_ITERATIONS {
            improved = false;
            iteration += 1;

            // Try moving each node to neighbor's community
            for node in self.graph.node_indices() {
                let current_community = self.find_node_community(node, &communities);
                let mut best_community = current_community;
                let mut best_modularity = self.compute_modularity(&communities, resolution);

                // Check each neighbor's community
                for neighbor in self.graph.neighbors(node) {
                    let neighbor_community = self.find_node_community(neighbor, &communities);
                    if neighbor_community != current_community {
                        // Try moving node to neighbor's community
                        let new_communities =
                            self.move_node(node, current_community, neighbor_community, &communities);
                        let new_modularity = self.compute_modularity(&new_communities, resolution);

                        if new_modularity > best_modularity {
                            best_modularity = new_modularity;
                            best_community = neighbor_community;
                            improved = true;
                        }
                    }
                }

                if best_community != current_community {
                    communities = self.move_node(node, current_community, best_community, &communities);
                }
            }
        }

        // Convert to string IDs
        communities
            .into_iter()
            .filter(|c| !c.is_empty())
            .map(|community| {
                community
                    .into_iter()
                    .map(|idx| self.graph[idx].clone())
                    .collect()
            })
            .collect()
    }

    fn find_node_community(&self, node: NodeIndex, communities: &[Vec<NodeIndex>]) -> usize {
        for (idx, community) in communities.iter().enumerate() {
            if community.contains(&node) {
                return idx;
            }
        }
        0
    }

    fn move_node(
        &self,
        node: NodeIndex,
        from: usize,
        to: usize,
        communities: &[Vec<NodeIndex>],
    ) -> Vec<Vec<NodeIndex>> {
        let mut new_communities = communities.to_vec();
        new_communities[from].retain(|&n| n != node);
        new_communities[to].push(node);
        new_communities
    }

    fn compute_modularity(&self, communities: &[Vec<NodeIndex>], resolution: f64) -> f64 {
        let m = self.graph.edge_count() as f64;
        if m == 0.0 {
            return 0.0;
        }

        let mut modularity = 0.0;

        for community in communities.iter().filter(|c| !c.is_empty()) {
            let mut internal_edges = 0.0;
            let mut total_degree = 0.0;

            for &node in community {
                total_degree += self.graph.edges(node).count() as f64;

                for edge in self.graph.edges(node) {
                    if community.contains(&edge.target()) {
                        internal_edges += 1.0;
                    }
                }
            }

            internal_edges /= 2.0; // Each edge counted twice
            modularity += (internal_edges / m) - resolution * (total_degree / (2.0 * m)).powi(2);
        }

        modularity
    }

    /// Compute PageRank centrality
    pub fn compute_pagerank(&self, damping: f64, iterations: usize) -> HashMap<String, f64> {
        let n = self.graph.node_count();
        if n == 0 {
            return HashMap::new();
        }

        let mut ranks: Vec<f64> = vec![1.0 / n as f64; n];
        let mut new_ranks = vec![0.0; n];

        for _ in 0..iterations {
            new_ranks.fill((1.0 - damping) / n as f64);

            for node_idx in self.graph.node_indices() {
                let out_degree = self.graph.edges(node_idx).count();
                if out_degree > 0 {
                    let rank_contribution = ranks[node_idx.index()] / out_degree as f64;
                    for neighbor in self.graph.neighbors(node_idx) {
                        new_ranks[neighbor.index()] += damping * rank_contribution;
                    }
                }
            }

            std::mem::swap(&mut ranks, &mut new_ranks);
        }

        // Convert to HashMap with node IDs
        self.graph
            .node_indices()
            .zip(ranks.into_iter())
            .map(|(idx, rank)| (self.graph[idx].clone(), rank))
            .collect()
    }

    /// Compute shortest path distances from source node
    pub fn shortest_paths(&self, source_id: &str) -> Option<HashMap<String, f64>> {
        let source_idx = self.node_map.get(source_id)?;

        let paths = dijkstra(&self.graph, *source_idx, None, |e| *e.weight());

        Some(
            paths
                .into_iter()
                .map(|(idx, cost)| (self.graph[idx].clone(), cost))
                .collect(),
        )
    }

    /// Get graph statistics
    pub fn stats(&self) -> GraphStats {
        let num_nodes = self.graph.node_count();
        let num_edges = self.graph.edge_count();
        let avg_degree = if num_nodes > 0 {
            (2 * num_edges) as f64 / num_nodes as f64
        } else {
            0.0
        };

        let density = if num_nodes > 1 {
            (2 * num_edges) as f64 / (num_nodes * (num_nodes - 1)) as f64
        } else {
            0.0
        };

        let num_components = connected_components(&self.graph);

        GraphStats {
            num_nodes,
            num_edges,
            avg_degree,
            density,
            num_components,
        }
    }

    /// Export graph to JSON for visualization
    pub fn to_json(&self) -> String {
        let nodes: Vec<_> = self
            .graph
            .node_indices()
            .map(|idx| {
                serde_json::json!({
                    "id": self.graph[idx],
                })
            })
            .collect();

        let edges: Vec<_> = self
            .graph
            .edge_references()
            .map(|edge| {
                serde_json::json!({
                    "source": self.graph[edge.source()],
                    "target": self.graph[edge.target()],
                    "weight": edge.weight(),
                })
            })
            .collect();

        serde_json::json!({
            "nodes": nodes,
            "edges": edges,
        })
        .to_string()
    }
}

impl Default for CognateGraph {
    fn default() -> Self {
        Self::new()
    }
}

/// Graph statistics
#[derive(Debug, Clone)]
pub struct GraphStats {
    pub num_nodes: usize,
    pub num_edges: usize,
    pub avg_degree: f64,
    pub density: f64,
    pub num_components: usize,
}

