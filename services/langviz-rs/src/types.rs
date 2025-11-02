//! Shared data structures for LangViz computational kernel.

use ordered_float::OrderedFloat;
use serde::{Deserialize, Serialize};

/// Edge in similarity/cognate graph
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimilarityEdge {
    pub source: String,
    pub target: String,
    pub weight: OrderedFloat<f64>,
}

impl SimilarityEdge {
    pub fn new(source: String, target: String, weight: f64) -> Self {
        Self {
            source,
            target,
            weight: OrderedFloat(weight),
        }
    }
}

/// IPA phonetic segment with features
#[derive(Debug, Clone)]
pub struct IPASegment {
    pub grapheme: String,
    pub features: [i8; 24], // Panphon-style features
}

impl IPASegment {
    pub fn new(grapheme: String, features: [i8; 24]) -> Self {
        Self { grapheme, features }
    }

    /// Compute feature distance to another segment
    pub fn feature_distance(&self, other: &IPASegment) -> f64 {
        let mut diff = 0;
        for i in 0..24 {
            if self.features[i] != other.features[i] {
                diff += 1;
            }
        }
        diff as f64 / 24.0
    }
}

/// Edit operation in sequence alignment
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EditOp {
    Match,
    Substitute,
    Insert,
    Delete,
}

/// Result of phonetic alignment
#[derive(Debug, Clone)]
pub struct Alignment {
    pub sequence_a: Vec<String>,
    pub sequence_b: Vec<String>,
    pub operations: Vec<EditOp>,
    pub cost: f64,
}

impl Alignment {
    pub fn new(
        sequence_a: Vec<String>,
        sequence_b: Vec<String>,
        operations: Vec<EditOp>,
        cost: f64,
    ) -> Self {
        Self {
            sequence_a,
            sequence_b,
            operations,
            cost,
        }
    }

    /// Extract sound correspondence rules from alignment
    pub fn extract_correspondences(&self) -> Vec<(String, String)> {
        let mut rules = Vec::new();
        for (i, op) in self.operations.iter().enumerate() {
            if *op == EditOp::Substitute && i < self.sequence_a.len() && i < self.sequence_b.len()
            {
                rules.push((self.sequence_a[i].clone(), self.sequence_b[i].clone()));
            }
        }
        rules
    }
}

/// Node in cognate cluster
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClusterNode {
    pub id: String,
    pub cluster_id: usize,
}

/// Connected component (cognate set)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CognateSet {
    pub id: usize,
    pub members: Vec<String>,
    pub size: usize,
}

impl CognateSet {
    pub fn new(id: usize, members: Vec<String>) -> Self {
        let size = members.len();
        Self { id, members, size }
    }
}

