//! Advanced phonetic algorithms with feature-weighted distance and DTW alignment.

use ndarray::{Array2, Axis};
use rayon::prelude::*;
use unicode_segmentation::UnicodeSegmentation;

use crate::types::{Alignment, EditOp, IPASegment};

/// Compute normalized Levenshtein distance between IPA strings
pub fn phonetic_distance(ipa_a: &str, ipa_b: &str) -> f64 {
    let segments_a: Vec<&str> = ipa_a.graphemes(true).collect();
    let segments_b: Vec<&str> = ipa_b.graphemes(true).collect();

    let distance = levenshtein(&segments_a, &segments_b);
    let max_len = segments_a.len().max(segments_b.len()) as f64;

    if max_len == 0.0 {
        1.0 // Both empty = perfect match
    } else {
        1.0 - (distance as f64 / max_len)
    }
}

/// Standard Levenshtein distance using dynamic programming
fn levenshtein(a: &[&str], b: &[&str]) -> usize {
    let len_a = a.len();
    let len_b = b.len();

    if len_a == 0 {
        return len_b;
    }
    if len_b == 0 {
        return len_a;
    }

    let mut prev_row: Vec<usize> = (0..=len_b).collect();
    let mut curr_row = vec![0; len_b + 1];

    for (i, seg_a) in a.iter().enumerate() {
        curr_row[0] = i + 1;

        for (j, seg_b) in b.iter().enumerate() {
            let cost = if seg_a == seg_b { 0 } else { 1 };

            curr_row[j + 1] = std::cmp::min(
                std::cmp::min(curr_row[j] + 1, prev_row[j + 1] + 1),
                prev_row[j] + cost,
            );
        }

        std::mem::swap(&mut prev_row, &mut curr_row);
    }

    prev_row[len_b]
}

/// Batch compute phonetic distances for multiple pairs (parallelized)
pub fn batch_phonetic_distance(pairs: Vec<(String, String)>) -> Vec<f64> {
    pairs
        .par_iter()
        .map(|(a, b)| phonetic_distance(a, b))
        .collect()
}

/// Feature-weighted phonetic distance using 24D feature vectors
pub fn feature_weighted_distance(segments_a: &[IPASegment], segments_b: &[IPASegment]) -> f64 {
    let len_a = segments_a.len();
    let len_b = segments_b.len();

    if len_a == 0 && len_b == 0 {
        return 0.0;
    }
    if len_a == 0 || len_b == 0 {
        return 1.0;
    }

    // Dynamic programming with feature costs
    let mut dp = Array2::<f64>::zeros((len_a + 1, len_b + 1));

    // Initialize first row and column
    for i in 0..=len_a {
        dp[[i, 0]] = i as f64;
    }
    for j in 0..=len_b {
        dp[[0, j]] = j as f64;
    }

    // Fill DP table with feature-weighted costs
    for i in 1..=len_a {
        for j in 1..=len_b {
            let seg_a = &segments_a[i - 1];
            let seg_b = &segments_b[j - 1];

            // Substitution cost is feature distance
            let subst_cost = if seg_a.grapheme == seg_b.grapheme {
                0.0
            } else {
                seg_a.feature_distance(seg_b)
            };

            dp[[i, j]] = f64::min(
                f64::min(
                    dp[[i - 1, j]] + 1.0,      // Deletion
                    dp[[i, j - 1]] + 1.0,      // Insertion
                ),
                dp[[i - 1, j - 1]] + subst_cost, // Substitution
            );
        }
    }

    let distance = dp[[len_a, len_b]];
    let max_len = len_a.max(len_b) as f64;

    distance / max_len
}

/// Dynamic Time Warping alignment for phonetic sequences
pub fn dtw_align(ipa_a: &str, ipa_b: &str) -> Alignment {
    let segments_a: Vec<String> = ipa_a.graphemes(true).map(|s| s.to_string()).collect();
    let segments_b: Vec<String> = ipa_b.graphemes(true).map(|s| s.to_string()).collect();

    let len_a = segments_a.len();
    let len_b = segments_b.len();

    if len_a == 0 || len_b == 0 {
        return Alignment::new(segments_a, segments_b, vec![], 0.0);
    }

    // DTW cost matrix
    let mut cost = Array2::<f64>::from_elem((len_a + 1, len_b + 1), f64::INFINITY);
    cost[[0, 0]] = 0.0;

    // Fill cost matrix
    for i in 1..=len_a {
        for j in 1..=len_b {
            let match_cost = if segments_a[i - 1] == segments_b[j - 1] {
                0.0
            } else {
                1.0
            };

            cost[[i, j]] = match_cost
                + f64::min(
                    f64::min(cost[[i - 1, j]], cost[[i, j - 1]]),
                    cost[[i - 1, j - 1]],
                );
        }
    }

    // Backtrack to find alignment path
    let mut i = len_a;
    let mut j = len_b;
    let mut operations = Vec::new();
    let mut aligned_a = Vec::new();
    let mut aligned_b = Vec::new();

    while i > 0 || j > 0 {
        if i == 0 {
            // Only insertions left
            operations.push(EditOp::Insert);
            aligned_a.push("-".to_string());
            aligned_b.push(segments_b[j - 1].clone());
            j -= 1;
        } else if j == 0 {
            // Only deletions left
            operations.push(EditOp::Delete);
            aligned_a.push(segments_a[i - 1].clone());
            aligned_b.push("-".to_string());
            i -= 1;
        } else {
            // Find minimum cost predecessor
            let diag = cost[[i - 1, j - 1]];
            let up = cost[[i - 1, j]];
            let left = cost[[i, j - 1]];

            if diag <= up && diag <= left {
                // Diagonal (match or substitute)
                if segments_a[i - 1] == segments_b[j - 1] {
                    operations.push(EditOp::Match);
                } else {
                    operations.push(EditOp::Substitute);
                }
                aligned_a.push(segments_a[i - 1].clone());
                aligned_b.push(segments_b[j - 1].clone());
                i -= 1;
                j -= 1;
            } else if up < left {
                // Up (deletion)
                operations.push(EditOp::Delete);
                aligned_a.push(segments_a[i - 1].clone());
                aligned_b.push("-".to_string());
                i -= 1;
            } else {
                // Left (insertion)
                operations.push(EditOp::Insert);
                aligned_a.push("-".to_string());
                aligned_b.push(segments_b[j - 1].clone());
                j -= 1;
            }
        }
    }

    // Reverse since we backtracked
    operations.reverse();
    aligned_a.reverse();
    aligned_b.reverse();

    Alignment::new(aligned_a, aligned_b, operations, cost[[len_a, len_b]])
}

/// Longest Common Subsequence ratio
pub fn lcs_ratio(ipa_a: &str, ipa_b: &str) -> f64 {
    let segments_a: Vec<&str> = ipa_a.graphemes(true).collect();
    let segments_b: Vec<&str> = ipa_b.graphemes(true).collect();

    let lcs_len = lcs_length(&segments_a, &segments_b);
    let max_len = segments_a.len().max(segments_b.len()) as f64;

    if max_len == 0.0 {
        1.0
    } else {
        lcs_len as f64 / max_len
    }
}

/// Compute length of longest common subsequence
fn lcs_length(a: &[&str], b: &[&str]) -> usize {
    let len_a = a.len();
    let len_b = b.len();

    let mut dp = vec![vec![0; len_b + 1]; len_a + 1];

    for i in 1..=len_a {
        for j in 1..=len_b {
            if a[i - 1] == b[j - 1] {
                dp[i][j] = dp[i - 1][j - 1] + 1;
            } else {
                dp[i][j] = dp[i - 1][j].max(dp[i][j - 1]);
            }
        }
    }

    dp[len_a][len_b]
}

/// Extract sound correspondence patterns from multiple alignments
pub fn extract_sound_correspondences(alignments: &[Alignment]) -> Vec<(String, String, usize)> {
    use std::collections::HashMap;

    let mut correspondence_counts: HashMap<(String, String), usize> = HashMap::new();

    for alignment in alignments {
        for correspondence in alignment.extract_correspondences() {
            *correspondence_counts.entry(correspondence).or_insert(0) += 1;
        }
    }

    let mut correspondences: Vec<_> = correspondence_counts
        .into_iter()
        .map(|((a, b), count)| (a, b, count))
        .collect();

    // Sort by frequency
    correspondences.sort_by(|a, b| b.2.cmp(&a.2));

    correspondences
}

/// Compute phonetic similarity matrix for batch of IPA strings
pub fn compute_similarity_matrix(ipa_strings: &[String]) -> Array2<f64> {
    let n = ipa_strings.len();
    let mut matrix = Array2::<f64>::zeros((n, n));

    // Diagonal is 1.0 (self-similarity)
    for i in 0..n {
        matrix[[i, i]] = 1.0;
    }

    // Compute upper triangle (parallel)
    let pairs: Vec<_> = (0..n)
        .flat_map(|i| (i + 1..n).map(move |j| (i, j)))
        .collect();

    let similarities: Vec<_> = pairs
        .par_iter()
        .map(|&(i, j)| phonetic_distance(&ipa_strings[i], &ipa_strings[j]))
        .collect();

    // Fill matrix (symmetric)
    for (idx, &(i, j)) in pairs.iter().enumerate() {
        let sim = similarities[idx];
        matrix[[i, j]] = sim;
        matrix[[j, i]] = sim;
    }

    matrix
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_phonetic_distance() {
        let dist = phonetic_distance("pater", "pitar");
        assert!(dist > 0.6 && dist < 1.0);
    }

    #[test]
    fn test_identical() {
        let dist = phonetic_distance("test", "test");
        assert_eq!(dist, 1.0);
    }

    #[test]
    fn test_dtw_align() {
        let alignment = dtw_align("pater", "patɛr");
        assert!(alignment.cost < 2.0);
        assert!(!alignment.operations.is_empty());
    }

    #[test]
    fn test_lcs() {
        let ratio = lcs_ratio("abcd", "acd");
        assert!(ratio > 0.7);
    }
}

