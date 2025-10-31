-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create languages table
CREATE TABLE IF NOT EXISTS languages (
    iso_code VARCHAR(3) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    branch VARCHAR(50) NOT NULL,
    subfamily VARCHAR(50),
    latitude FLOAT,
    longitude FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create entries table with vector support
CREATE TABLE IF NOT EXISTS entries (
    id VARCHAR(255) PRIMARY KEY,
    headword VARCHAR(255) NOT NULL,
    ipa VARCHAR(255) NOT NULL,
    language VARCHAR(3) NOT NULL REFERENCES languages(iso_code),
    definition TEXT NOT NULL,
    etymology TEXT,
    pos_tag VARCHAR(50),
    embedding vector(768),  -- sentence-transformers default dimension
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient queries
CREATE INDEX idx_entries_language ON entries(language);
CREATE INDEX idx_entries_pos_tag ON entries(pos_tag);
CREATE INDEX idx_entries_headword ON entries(headword);

-- Create vector similarity index (HNSW for fast approximate search)
CREATE INDEX idx_entries_embedding ON entries 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Create full-text search index
CREATE INDEX idx_entries_definition_fts ON entries 
USING gin(to_tsvector('english', definition));

-- Create cognate sets table
CREATE TABLE IF NOT EXISTS cognate_sets (
    id VARCHAR(255) PRIMARY KEY,
    entries TEXT[] NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    proto_form VARCHAR(255),
    semantic_core TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create similarity edges table
CREATE TABLE IF NOT EXISTS similarity_edges (
    entry_a VARCHAR(255) NOT NULL REFERENCES entries(id),
    entry_b VARCHAR(255) NOT NULL REFERENCES entries(id),
    phonetic_score FLOAT NOT NULL CHECK (phonetic_score >= 0 AND phonetic_score <= 1),
    semantic_score FLOAT NOT NULL CHECK (semantic_score >= 0 AND semantic_score <= 1),
    combined_score FLOAT NOT NULL CHECK (combined_score >= 0 AND combined_score <= 1),
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (entry_a, entry_b),
    CHECK (entry_a < entry_b)  -- Enforce ordering to prevent duplicates
);

CREATE INDEX idx_similarity_edges_score ON similarity_edges(combined_score DESC);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for entries table
CREATE TRIGGER update_entries_updated_at 
    BEFORE UPDATE ON entries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

