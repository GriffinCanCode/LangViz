-- Migration: Multi-layered similarity system
-- Adds concept clustering, phylogenetic weighting, and batch processing

-- Add concept_id to entries if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='entries' AND column_name='concept_id') THEN
        ALTER TABLE entries ADD COLUMN concept_id VARCHAR(255);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='entries' AND column_name='concept_confidence') THEN
        ALTER TABLE entries ADD COLUMN concept_confidence FLOAT CHECK (concept_confidence >= 0 AND concept_confidence <= 1);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_entries_concept ON entries(concept_id);

-- Create concepts table
CREATE TABLE IF NOT EXISTS concepts (
    id VARCHAR(255) PRIMARY KEY,
    label VARCHAR(255) NOT NULL,
    centroid vector(768) NOT NULL,
    size INTEGER NOT NULL CHECK (size >= 0),
    languages TEXT[] NOT NULL,
    sample_definitions TEXT[],
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_concepts_centroid ON concepts
USING hnsw (centroid vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_concepts_size ON concepts(size DESC);

-- Create layered similarity edges table
CREATE TABLE IF NOT EXISTS layered_similarities (
    entry_a VARCHAR(255) NOT NULL REFERENCES entries(id),
    entry_b VARCHAR(255) NOT NULL REFERENCES entries(id),
    
    -- Component scores
    semantic_score FLOAT NOT NULL CHECK (semantic_score >= 0 AND semantic_score <= 1),
    phonetic_score FLOAT NOT NULL CHECK (phonetic_score >= 0 AND phonetic_score <= 1),
    etymological_score FLOAT NOT NULL CHECK (etymological_score >= 0 AND etymological_score <= 1),
    
    -- Combined
    combined_score FLOAT NOT NULL CHECK (combined_score >= 0 AND combined_score <= 1),
    
    -- Metadata
    weights JSONB NOT NULL,
    phylogenetic_distance INTEGER,
    concept_a VARCHAR(255),
    concept_b VARCHAR(255),
    
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (entry_a, entry_b),
    CHECK (entry_a < entry_b)
);

CREATE INDEX IF NOT EXISTS idx_layered_sim_combined ON layered_similarities(combined_score DESC);
CREATE INDEX IF NOT EXISTS idx_layered_sim_semantic ON layered_similarities(semantic_score DESC);
CREATE INDEX IF NOT EXISTS idx_layered_sim_phonetic ON layered_similarities(phonetic_score DESC);
CREATE INDEX IF NOT EXISTS idx_layered_sim_concept ON layered_similarities(concept_a, concept_b);

-- Create cognate clusters table
CREATE TABLE IF NOT EXISTS cognate_clusters (
    id VARCHAR(255) PRIMARY KEY,
    concept_id VARCHAR(255) REFERENCES concepts(id),
    member_ids TEXT[] NOT NULL,
    languages TEXT[] NOT NULL,
    representative_form VARCHAR(255),
    proto_form VARCHAR(255),
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    size INTEGER NOT NULL CHECK (size >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cognate_concept ON cognate_clusters(concept_id);
CREATE INDEX IF NOT EXISTS idx_cognate_size ON cognate_clusters(size DESC);

-- Create batch processing checkpoints table
CREATE TABLE IF NOT EXISTS batch_checkpoints (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    total INTEGER NOT NULL,
    processed INTEGER NOT NULL,
    succeeded INTEGER NOT NULL,
    failed INTEGER NOT NULL,
    skipped INTEGER NOT NULL,
    branch_progress JSONB
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_timestamp ON batch_checkpoints(timestamp DESC);

-- Create phylogenetic distances cache
CREATE TABLE IF NOT EXISTS phylogenetic_distances (
    lang_a VARCHAR(3) NOT NULL,
    lang_b VARCHAR(3) NOT NULL,
    tree_distance INTEGER NOT NULL,
    prior_probability FLOAT NOT NULL,
    PRIMARY KEY (lang_a, lang_b),
    CHECK (lang_a < lang_b)
);

CREATE INDEX IF NOT EXISTS idx_phylo_languages ON phylogenetic_distances(lang_a, lang_b);

-- Create materialized view for concept statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS concept_statistics AS
SELECT
    c.id,
    c.label,
    c.size,
    c.confidence,
    COUNT(DISTINCT e.language) as num_languages,
    ARRAY_AGG(DISTINCT e.language) as languages_represented,
    AVG(e.data_quality) as avg_member_quality
FROM concepts c
LEFT JOIN entries e ON e.concept_id = c.id
GROUP BY c.id, c.label, c.size, c.confidence;

CREATE INDEX IF NOT EXISTS idx_concept_stats_id ON concept_statistics(id);

-- Function to update concept statistics
CREATE OR REPLACE FUNCTION refresh_concept_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW concept_statistics;
END;
$$ LANGUAGE plpgsql;

-- Function to compute layered similarity
CREATE OR REPLACE FUNCTION compute_layered_similarity(
    entry_a_id VARCHAR,
    entry_b_id VARCHAR,
    semantic FLOAT,
    phonetic FLOAT,
    etymological FLOAT,
    weights JSONB
)
RETURNS FLOAT AS $$
DECLARE
    w_semantic FLOAT;
    w_phonetic FLOAT;
    w_etymological FLOAT;
BEGIN
    w_semantic := (weights->>'semantic')::FLOAT;
    w_phonetic := (weights->>'phonetic')::FLOAT;
    w_etymological := (weights->>'etymological')::FLOAT;
    
    RETURN w_semantic * semantic + w_phonetic * phonetic + w_etymological * etymological;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to find similar entries using layered similarity
CREATE OR REPLACE FUNCTION find_similar_entries(
    target_entry_id VARCHAR,
    similarity_mode VARCHAR DEFAULT 'balanced',
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    entry_id VARCHAR,
    headword VARCHAR,
    language VARCHAR,
    combined_score FLOAT,
    semantic_score FLOAT,
    phonetic_score FLOAT,
    etymological_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        CASE
            WHEN ls.entry_a = target_entry_id THEN ls.entry_b
            ELSE ls.entry_a
        END as entry_id,
        e.headword,
        e.language,
        ls.combined_score,
        ls.semantic_score,
        ls.phonetic_score,
        ls.etymological_score
    FROM layered_similarities ls
    JOIN entries e ON e.id = CASE
        WHEN ls.entry_a = target_entry_id THEN ls.entry_b
        ELSE ls.entry_a
    END
    WHERE ls.entry_a = target_entry_id OR ls.entry_b = target_entry_id
    ORDER BY ls.combined_score DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update concept updated_at
CREATE OR REPLACE FUNCTION update_concept_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_concepts_timestamp
    BEFORE UPDATE ON concepts
    FOR EACH ROW
    EXECUTE FUNCTION update_concept_timestamp();

-- Create view for lexical differences
CREATE OR REPLACE VIEW lexical_differences AS
SELECT
    c.id as concept_id,
    c.label as concept_label,
    e1.language as language_a,
    e2.language as language_b,
    e1.headword as form_a,
    e2.headword as form_b,
    e1.ipa as ipa_a,
    e2.ipa as ipa_b,
    ls.semantic_score,
    ls.phonetic_score,
    ls.etymological_score,
    ls.combined_score,
    ls.phylogenetic_distance
FROM concepts c
JOIN entries e1 ON e1.concept_id = c.id
JOIN entries e2 ON e2.concept_id = c.id AND e2.language != e1.language
LEFT JOIN layered_similarities ls ON 
    (ls.entry_a = e1.id AND ls.entry_b = e2.id) OR
    (ls.entry_a = e2.id AND ls.entry_b = e1.id)
WHERE e1.language < e2.language;  -- Avoid duplicates

-- Performance: Create partial indexes for common queries
CREATE INDEX IF NOT EXISTS idx_entries_high_quality 
ON entries(concept_id, language) 
WHERE data_quality >= 0.8;

CREATE INDEX IF NOT EXISTS idx_similarities_high_combined 
ON layered_similarities(entry_a, entry_b, combined_score) 
WHERE combined_score >= 0.7;

-- Comments for documentation
COMMENT ON TABLE concepts IS 'Auto-discovered semantic concepts from UMAP + HDBSCAN clustering';
COMMENT ON TABLE layered_similarities IS 'Multi-modal similarity scores (semantic + phonetic + etymological)';
COMMENT ON TABLE cognate_clusters IS 'Cognate sets grouped by concept and phonetic similarity';
COMMENT ON TABLE phylogenetic_distances IS 'Cached tree distances between language pairs';
COMMENT ON FUNCTION compute_layered_similarity IS 'Weighted combination of similarity components';
COMMENT ON FUNCTION find_similar_entries IS 'Fast lookup of similar entries using precomputed similarities';

