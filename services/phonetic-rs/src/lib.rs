use pyo3::prelude::*;
use unicode_segmentation::UnicodeSegmentation;
use rayon::prelude::*;

/// Compute Levenshtein distance between two IPA strings.
/// Optimized for phonetic segments rather than raw characters.
#[pyfunction]
fn phonetic_distance(ipa_a: &str, ipa_b: &str) -> PyResult<f64> {
    let segments_a: Vec<&str> = ipa_a.graphemes(true).collect();
    let segments_b: Vec<&str> = ipa_b.graphemes(true).collect();
    
    let distance = levenshtein(&segments_a, &segments_b);
    let max_len = segments_a.len().max(segments_b.len()) as f64;
    
    if max_len == 0.0 {
        Ok(0.0)
    } else {
        Ok(1.0 - (distance as f64 / max_len))
    }
}

/// Compute Levenshtein distance using dynamic programming.
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
                std::cmp::min(
                    curr_row[j] + 1,      // insertion
                    prev_row[j + 1] + 1   // deletion
                ),
                prev_row[j] + cost        // substitution
            );
        }
        
        std::mem::swap(&mut prev_row, &mut curr_row);
    }
    
    prev_row[len_b]
}

/// Batch compute phonetic distances for multiple pairs.
/// Uses Rayon for parallel processing.
#[pyfunction]
fn batch_phonetic_distance(pairs: Vec<(String, String)>) -> PyResult<Vec<f64>> {
    let distances: Vec<f64> = pairs
        .par_iter()
        .map(|(a, b)| phonetic_distance(a, b).unwrap_or(0.0))
        .collect();
    
    Ok(distances)
}

/// Compute longest common subsequence ratio.
#[pyfunction]
fn lcs_ratio(ipa_a: &str, ipa_b: &str) -> PyResult<f64> {
    let segments_a: Vec<&str> = ipa_a.graphemes(true).collect();
    let segments_b: Vec<&str> = ipa_b.graphemes(true).collect();
    
    let lcs_len = lcs_length(&segments_a, &segments_b);
    let max_len = segments_a.len().max(segments_b.len()) as f64;
    
    if max_len == 0.0 {
        Ok(1.0)
    } else {
        Ok(lcs_len as f64 / max_len)
    }
}

/// Compute length of longest common subsequence.
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

/// Python module definition.
#[pymodule]
fn langviz_phonetic(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(phonetic_distance, m)?)?;
    m.add_function(wrap_pyfunction!(batch_phonetic_distance, m)?)?;
    m.add_function(wrap_pyfunction!(lcs_ratio, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_phonetic_distance() {
        let result = phonetic_distance("pater", "pitar").unwrap();
        assert!(result > 0.6 && result < 1.0);
    }
    
    #[test]
    fn test_identical_strings() {
        let result = phonetic_distance("test", "test").unwrap();
        assert_eq!(result, 1.0);
    }
}

