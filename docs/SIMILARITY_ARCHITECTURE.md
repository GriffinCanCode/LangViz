# Multi-Layered Similarity Architecture

## Design Philosophy

**First Principles Analysis:**

Traditional approach: Single embedding space → PCA → cosine similarity  
**Problem:** Conflates orthogonal linguistic dimensions (phonetics, semantics, etymology)

**Our Approach:** Stratified vector spaces with domain-specific metrics

## Core Innovation: Layered Similarity Computation

### Layer 1: Conceptual Alignment (Semantic Core)
**Purpose:** Group words by *what they mean* across languages

**Strategy:**
- Use multilingual sentence transformers for semantic embedding (768d)
- Cluster into **concepts** (not translations)
- Example: {English "yes", Russian "да", Ukrainian "так", Polish "tak"} → CONCEPT_AFFIRMATION
- Creates cross-lingual semantic atlas

**Why not PCA?**  
PCA is linear and loses semantic topology. Instead:
- **UMAP** for visualization (preserves manifold structure)
- **HDBSCAN** for automatic concept discovery
- Keep full 768d for similarity computation (cheap with HNSW)

**Implementation:**
```python
ConceptAligner:
    - embed_batch(definitions: List[str]) → ndarray[768]
    - discover_concepts(embeddings, min_cluster_size=50) → List[Concept]
    - assign_concept(embedding) → concept_id, confidence
```

### Layer 2: Phonetic Distance (Sound Change Patterns)
**Purpose:** Detect cognates via systematic sound correspondences

**Strategy:**
- IPA feature vectors (panphon: 24 dimensions per phoneme)
- DTW (Dynamic Time Warping) for sequence alignment
- Rust-accelerated computation for speed
- Learn sound change rules via alignment statistics

**Metrics:**
- Raw phonetic edit distance (baseline)
- Feature-weighted distance (articulation-aware)
- Contextual distance (phonotactic environment)

**Why not simple Levenshtein?**  
Sound changes are systematic: [k] → [tʃ] in palatalization is closer than [k] → [m]

**Implementation:**
```python
PhoneticAnalyzer:
    - align(ipa_a, ipa_b) → Alignment, score
    - extract_correspondence_patterns(alignments) → Dict[Rule, frequency]
    - weighted_distance(ipa_a, ipa_b, rules) → float
```

### Layer 3: Etymological Lineage (Phylogenetic Distance)
**Purpose:** Weight similarity by expected relatedness

**Strategy:**
- Phylogenetic tree of IE languages (from Glottolog)
- Path distance as prior probability
- Bayesian update with phonetic + semantic evidence

**Example:**
```
Russian ↔ Ukrainian: tree_distance=1 (close siblings)
Russian ↔ English: tree_distance=5 (distant cousins)

Prior: P(cognate|close) = 0.3, P(cognate|distant) = 0.05
Likelihood: P(phonetic_sim|cognate) from data
Posterior: P(cognate|phonetic_sim, tree_distance)
```

**Implementation:**
```python
PhylogeneticWeighting:
    - load_tree(glottolog) → Tree
    - path_distance(lang_a, lang_b) → int
    - prior_probability(distance) → float
    - posterior_cognate_prob(phonetic, semantic, phylo) → float
```

## Data Segmentation Strategy

**Challenge:** 6.7M entries, 50+ languages, heterogeneous quality

**Solution: Multi-resolution partitioning**

### Partition Scheme:
```
Level 1: By LANGUAGE BRANCH (9 branches)
  ├─ Facilitates parallelization
  └─ Captures subfamily-specific patterns

Level 2: By CONCEPT (auto-discovered clusters)
  ├─ ~2000-5000 concepts expected
  ├─ Enables concept-level indexing
  └─ Natural query unit

Level 3: By QUALITY TIER (from provenance data)
  ├─ High (>0.8): Gold standard for training
  ├─ Medium (0.5-0.8): Bulk analysis
  └─ Low (<0.5): Exclude from similarity computation
```

### Batch Processing Pipeline:
```python
1. Stream from raw_entries (immutable source)
2. Apply cleaning pipelines (headword, IPA, definition)
3. Compute embeddings (batched, GPU-accelerated)
4. Assign to concepts (HDBSCAN clustering)
5. Store in partitioned tables
```

**Parallelization:**
- Branch-level: Independent workers per language family
- Concept-level: Map-reduce over concept clusters
- Enables incremental processing (add new languages without recompute)

## Indexing Architecture

**Hybrid Strategy: Sparse + Dense**

### Sparse Index (Lexical Features)
**Use Case:** Fast pre-filtering, exact matches

**Structure:**
```sql
CREATE INDEX idx_entries_headword_trgm ON entries 
USING gin (headword gin_trgm_ops);

CREATE INDEX idx_entries_language_concept ON entries(language, concept_id);
```

**Queries:**
- Find words with similar orthography
- Filter by language + concept before vector search

### Dense Index (Semantic Vectors)
**Use Case:** Similarity search in embedding space

**Strategy:**
- pgvector HNSW index (m=16, ef=64) for 768d vectors
- Separate indexes per concept (smaller subspace = faster)
- IVF (Inverted File) index for massive scale

**Structure:**
```sql
-- Global semantic search
CREATE INDEX idx_entries_embedding_global ON entries 
USING hnsw (embedding vector_cosine_ops);

-- Per-concept search (faster)
CREATE INDEX idx_entries_embedding_c{concept_id} ON entries 
USING hnsw (embedding vector_cosine_ops)
WHERE concept_id = {concept_id};
```

### Phonetic Index (Custom)
**Challenge:** No native database support for IPA sequence similarity

**Solution:**
- Phonetic hash function (maps IPA to discrete space)
- LSH (Locality-Sensitive Hashing) for approximate neighbors
- Store in Redis for speed

**Structure:**
```python
PhoneticIndex:
    - hash(ipa_string) → [hash1, hash2, ..., hash_k]  # k=10 hash functions
    - insert(entry_id, ipa) → store in k buckets
    - search(query_ipa, k=50) → candidate_set (fast)
    - refine(candidates, query_ipa) → ranked_results (precise)
```

## Similarity Computation Formula

**Unified Score:**

```
S(word_a, word_b) = α·semantic(a,b) + β·phonetic(a,b) + γ·etymological(a,b)

where:
  semantic(a,b) = cosine(embedding_a, embedding_b)
  
  phonetic(a,b) = exp(-DTW_distance(ipa_a, ipa_b) / σ)
  
  etymological(a,b) = P(cognate | semantic, phonetic, phylo_distance)
  
  α, β, γ = learned weights (default: 0.4, 0.4, 0.2)
```

**Adaptive Weights:**
- Query type influences weights:
  - Cognate detection: β=0.6, α=0.3, γ=0.1
  - Semantic similarity: α=0.7, β=0.2, γ=0.1
  - Historical reconstruction: γ=0.5, β=0.4, α=0.1

## Query Resolution: "Why 'tak' in Ukrainian but 'da' in Russian?"

**Analysis Pipeline:**

```python
def analyze_lexical_difference(concept, lang_a, lang_b):
    """
    1. Retrieve entries for concept in both languages
    2. Compute phonetic distance (how different?)
    3. Search for cognates in other languages
    4. Identify phylogenetic pattern (borrowing? retention?)
    5. Check etymology field for historical explanation
    """
    
    entries_a = get_entries(lang=lang_a, concept="AFFIRMATION")
    entries_b = get_entries(lang=lang_b, concept="AFFIRMATION")
    
    # Find cognates across all IE languages
    cognate_clusters = cluster_cognates(
        get_entries(concept="AFFIRMATION", all_languages=True)
    )
    
    # Identify which cluster each belongs to
    cluster_a = find_cluster(entries_a[0], cognate_clusters)
    cluster_b = find_cluster(entries_b[0], cognate_clusters)
    
    # Analyze distribution
    distribution = {
        cluster: [lang for lang in cluster.languages]
        for cluster in cognate_clusters
    }
    
    # Generate narrative
    return {
        "ukrainian_form": "tak",
        "russian_form": "da",
        "explanation": "Ukrainian 'tak' is cognate with Polish 'tak', reflecting West Slavic influence or archaism. Russian 'da' is shared with South Slavic (Serbian 'da'). Both reflect different substrate influences on common Slavic stock.",
        "cognate_sets": {
            "tak_cluster": ["pl", "uk", "cs", "sk"],  # West Slavic
            "da_cluster": ["ru", "bg", "sr"],  # East/South Slavic
            "ja_cluster": ["de", "nl", "en:yea"]  # Germanic (coincidental)
        },
        "phylogenetic_context": "tree_distance(uk, pl)=2, tree_distance(uk, ru)=1",
        "historical_note": "Reflects early Balto-Slavic vs later Pan-Slavic developments"
    }
```

## Dimensionality Reduction (Visualization Only)

**NOT for similarity computation** (use full 768d embeddings)

**For human exploration:**
- UMAP: 768d → 2d/3d (preserves local structure)
- t-SNE: Alternative, but slower
- PCA: Only for explained variance analysis

**Use Cases:**
- Interactive scatter plot of vocabulary space
- Identify semantic clusters visually
- Debug concept assignment

## Performance Targets

**Indexing:**
- 6.7M entries in ~4 hours (M1 Mac, 16GB RAM)
- Parallelized by language branch (9 workers)

**Query:**
- Concept assignment: <100ms
- Similarity search (k=100): <50ms (HNSW)
- Phonetic search (k=50): <10ms (LSH in Redis)
- Full analysis (like 'tak' vs 'da'): <500ms

**Storage:**
- Raw entries: ~8GB (JSONB)
- Embeddings (768d float32): 6.7M × 768 × 4 bytes ≈ 20GB
- Indexes (HNSW + trigram): ~15GB
- **Total: ~50GB**

## Implementation Roadmap

1. **Concept Alignment Module** (Week 1)
   - UMAP + HDBSCAN clustering
   - Batch embedding pipeline
   - Concept assignment service

2. **Phylogenetic Weighting** (Week 1)
   - Load Glottolog tree
   - Distance matrix computation
   - Bayesian scoring function

3. **Phonetic LSH Index** (Week 2)
   - Redis-backed LSH
   - IPA hashing function
   - Approximate search + refinement

4. **Unified Similarity API** (Week 2)
   - Combined scoring
   - Query-specific weight adaptation
   - Explanation generation

5. **Batch Processing Pipeline** (Week 3)
   - Parallel branch processing
   - Streaming from raw_entries
   - Progress tracking & resumption

6. **Query Resolution System** (Week 3)
   - Lexical difference analyzer
   - Cognate cluster visualization
   - Historical narrative generation

## Why This Approach is Superior

**vs Standard Methods:**

| Aspect | Standard | Our Approach | Advantage |
|--------|----------|--------------|-----------|
| Embedding | Single space | Layered (semantic/phonetic/phylo) | Interpretable, domain-specific |
| Reduction | PCA (linear) | UMAP (manifold) | Preserves topology |
| Distance | Cosine only | Hybrid weighted | Multi-modal evidence |
| Indexing | Dense only | Sparse + dense | 10x faster filtering |
| Similarity | Static weights | Query-adaptive | Task-specific precision |
| Phonetics | Edit distance | Feature-based DTW | Linguistically informed |
| Phylogeny | Ignored | Bayesian prior | Reduces false positives |

**Key Innovations:**
1. **Concept-first architecture** - enables cross-lingual reasoning
2. **Phylogenetic priors** - incorporates known linguistic structure
3. **Hybrid indexing** - combines lexical and semantic search
4. **Explainable similarity** - shows *why* words are related
5. **Streaming pipeline** - processes unbounded data
6. **Quality-aware** - uses provenance for training set selection

**Testable Hypothesis:**
This architecture will achieve:
- **Cognate detection precision: >90%** (vs ~70% for phonetic-only)
- **Semantic clustering F1: >85%** (vs ~75% for single-space)
- **Query latency: <100ms** (vs ~500ms for exhaustive search)
- **Explainability: Human-validated** (novel capability)

