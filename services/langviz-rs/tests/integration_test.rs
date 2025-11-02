use langviz_core::*;

#[test]
fn test_phonetic_distance_basic() {
    let dist = phonetic::phonetic_distance("test", "test");
    assert_eq!(dist, 1.0); // Identical = similarity 1.0
    
    let dist2 = phonetic::phonetic_distance("pater", "mater");
    assert!(dist2 > 0.5 && dist2 < 1.0); // Similar but not identical
}

#[test]
fn test_batch_phonetic() {
    let pairs = vec![
        ("pater".to_string(), "pitar".to_string()),
        ("mater".to_string(), "meter".to_string()),
    ];
    
    let distances = phonetic::batch_phonetic_distance(pairs);
    assert_eq!(distances.len(), 2);
    assert!(distances[0] > 0.5);
}

#[test]
fn test_dtw_alignment() {
    let alignment = phonetic::dtw_align("abc", "adc");
    assert!(alignment.cost < 2.0);
    assert_eq!(alignment.sequence_a.len(), 3);
    assert_eq!(alignment.sequence_b.len(), 3);
}

#[test]
fn test_lcs() {
    let ratio = phonetic::lcs_ratio("abcde", "ace");
    assert!(ratio > 0.5 && ratio <= 1.0);
}

#[test]
fn test_graph_construction() {
    use types::SimilarityEdge;
    
    let edges = vec![
        SimilarityEdge::new("a".to_string(), "b".to_string(), 0.9),
        SimilarityEdge::new("b".to_string(), "c".to_string(), 0.85),
    ];
    
    let graph = graph::CognateGraph::from_edges(edges, 0.5);
    let stats = graph.stats();
    
    assert_eq!(stats.num_nodes, 3);
    assert_eq!(stats.num_edges, 2);
}

#[test]
fn test_cognate_sets() {
    use types::SimilarityEdge;
    
    let edges = vec![
        SimilarityEdge::new("a".to_string(), "b".to_string(), 0.9),
        SimilarityEdge::new("b".to_string(), "c".to_string(), 0.85),
        SimilarityEdge::new("d".to_string(), "e".to_string(), 0.95),
    ];
    
    let graph = graph::CognateGraph::from_edges(edges, 0.8);
    let sets = graph.find_cognate_sets();
    
    assert_eq!(sets.len(), 2); // Two components: {a,b,c} and {d,e}
}

#[test]
fn test_pagerank() {
    use types::SimilarityEdge;
    
    let edges = vec![
        SimilarityEdge::new("a".to_string(), "b".to_string(), 0.9),
        SimilarityEdge::new("b".to_string(), "c".to_string(), 0.85),
        SimilarityEdge::new("c".to_string(), "a".to_string(), 0.8),
    ];
    
    let graph = graph::CognateGraph::from_edges(edges, 0.7);
    let ranks = graph.compute_pagerank(0.85, 20);
    
    assert_eq!(ranks.len(), 3);
    
    // Sum of ranks should be ~1.0
    let sum: f64 = ranks.values().sum();
    assert!((sum - 1.0).abs() < 0.01);
}

#[test]
fn test_union_find() {
    use cluster::UnionFind;
    
    let mut uf = UnionFind::new(5);
    uf.union(0, 1);
    uf.union(2, 3);
    
    assert_eq!(uf.find(0), uf.find(1));
    assert_ne!(uf.find(0), uf.find(2));
    
    uf.union(1, 2);
    assert_eq!(uf.find(0), uf.find(3));
}

#[test]
fn test_threshold_clustering() {
    let similarities = vec![
        (0, 1, 0.9),
        (1, 2, 0.85),
        (3, 4, 0.95),
    ];
    
    let clusters = cluster::threshold_clustering(similarities, 5, 0.8);
    
    assert_eq!(clusters.len(), 2); // Two clusters
}

#[test]
fn test_sparse_matrix() {
    let edges = vec![
        ("a".to_string(), "b".to_string(), 0.9),
        ("b".to_string(), "c".to_string(), 0.8),
        ("a".to_string(), "c".to_string(), 0.7),
    ];
    
    let matrix = sparse::SparseSimilarityMatrix::from_edges(edges, 0.5);
    
    assert_eq!(matrix.shape().0, 3);
    assert!(matrix.nnz() > 0);
    assert!(matrix.sparsity() < 1.0);
}

#[test]
fn test_sparse_knn() {
    let edges = vec![
        ("a".to_string(), "b".to_string(), 0.9),
        ("a".to_string(), "c".to_string(), 0.7),
        ("a".to_string(), "d".to_string(), 0.5),
    ];
    
    let matrix = sparse::SparseSimilarityMatrix::from_edges(edges, 0.4);
    let neighbors = matrix.knn("a", 2);
    
    assert_eq!(neighbors.len(), 2);
    // First neighbor should be "b" (highest similarity)
    assert_eq!(neighbors[0].0, "b");
    assert!((neighbors[0].1 - 0.9).abs() < 0.01);
}

#[test]
fn test_sound_correspondences() {
    let alignments = vec![
        phonetic::dtw_align("pater", "pitar"),
        phonetic::dtw_align("mater", "mitar"),
    ];
    
    let correspondences = phonetic::extract_sound_correspondences(&alignments);
    
    // Should find e->i correspondence
    assert!(!correspondences.is_empty());
}

#[test]
fn test_similarity_matrix() {
    let ipa_strings = vec![
        "pater".to_string(),
        "pitar".to_string(),
        "mater".to_string(),
    ];
    
    let matrix = phonetic::compute_similarity_matrix(&ipa_strings);
    
    assert_eq!(matrix.shape(), (3, 3));
    
    // Diagonal should be 1.0
    assert_eq!(matrix[[0, 0]], 1.0);
    assert_eq!(matrix[[1, 1]], 1.0);
    
    // Matrix should be symmetric
    assert_eq!(matrix[[0, 1]], matrix[[1, 0]]);
}


