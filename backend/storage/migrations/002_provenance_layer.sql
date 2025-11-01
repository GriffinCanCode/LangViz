-- Add provenance and data quality tracking

-- Create data sources table
CREATE TABLE IF NOT EXISTS data_sources (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    format VARCHAR(50) NOT NULL,
    url TEXT,
    license VARCHAR(100),
    quality VARCHAR(20) NOT NULL,
    version VARCHAR(50),
    retrieved_at TIMESTAMP NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create raw entries table (immutable source of truth)
CREATE TABLE IF NOT EXISTS raw_entries (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(100) NOT NULL REFERENCES data_sources(id),
    raw_data JSONB NOT NULL,
    checksum VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 of raw_data
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT,
    line_number INTEGER
);

CREATE INDEX idx_raw_entries_source ON raw_entries(source_id);
CREATE INDEX idx_raw_entries_checksum ON raw_entries(checksum);

-- Create transform log table (tracks all transformations)
CREATE TABLE IF NOT EXISTS transform_log (
    id SERIAL PRIMARY KEY,
    raw_entry_id INTEGER NOT NULL REFERENCES raw_entries(id),
    step_name VARCHAR(100) NOT NULL,
    step_version VARCHAR(20) NOT NULL,
    parameters JSONB,
    executed_at TIMESTAMP NOT NULL,
    duration_ms INTEGER,
    success BOOLEAN NOT NULL,
    error_message TEXT
);

CREATE INDEX idx_transform_log_raw_entry ON transform_log(raw_entry_id);
CREATE INDEX idx_transform_log_step ON transform_log(step_name);

-- Add provenance columns to entries table
ALTER TABLE entries 
ADD COLUMN IF NOT EXISTS raw_entry_id INTEGER REFERENCES raw_entries(id),
ADD COLUMN IF NOT EXISTS source_id VARCHAR(100) REFERENCES data_sources(id),
ADD COLUMN IF NOT EXISTS pipeline_version VARCHAR(255),
ADD COLUMN IF NOT EXISTS data_quality FLOAT CHECK (data_quality >= 0 AND data_quality <= 1),
ADD COLUMN IF NOT EXISTS validation_errors TEXT[];

CREATE INDEX idx_entries_raw_entry ON entries(raw_entry_id);
CREATE INDEX idx_entries_source ON entries(source_id);
CREATE INDEX idx_entries_quality ON entries(data_quality);

-- Create data quality metrics table
CREATE TABLE IF NOT EXISTS quality_metrics (
    id SERIAL PRIMARY KEY,
    entry_id VARCHAR(255) REFERENCES entries(id),
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quality_metrics_entry ON quality_metrics(entry_id);
CREATE INDEX idx_quality_metrics_name ON quality_metrics(metric_name);

-- Create duplicate detection table
CREATE TABLE IF NOT EXISTS entry_duplicates (
    entry_a VARCHAR(255) NOT NULL REFERENCES entries(id),
    entry_b VARCHAR(255) NOT NULL REFERENCES entries(id),
    similarity_score FLOAT NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (entry_a, entry_b),
    CHECK (entry_a < entry_b)
);

CREATE INDEX idx_entry_duplicates_score ON entry_duplicates(similarity_score DESC);

-- Create materialized view for data quality dashboard
CREATE MATERIALIZED VIEW IF NOT EXISTS data_quality_summary AS
SELECT 
    ds.id as source_id,
    ds.name as source_name,
    ds.quality as source_quality,
    COUNT(e.id) as total_entries,
    AVG(e.data_quality) as avg_entry_quality,
    COUNT(CASE WHEN e.data_quality >= 0.8 THEN 1 END) as high_quality_count,
    COUNT(CASE WHEN e.data_quality < 0.5 THEN 1 END) as low_quality_count,
    COUNT(CASE WHEN e.validation_errors IS NOT NULL THEN 1 END) as entries_with_errors,
    MAX(e.updated_at) as last_updated
FROM data_sources ds
LEFT JOIN entries e ON e.source_id = ds.id
GROUP BY ds.id, ds.name, ds.quality;

CREATE INDEX idx_dq_summary_source ON data_quality_summary(source_id);

-- Function to compute entry quality score
CREATE OR REPLACE FUNCTION compute_entry_quality(entry_row entries)
RETURNS FLOAT AS $$
DECLARE
    quality_score FLOAT := 1.0;
BEGIN
    -- Deduct for missing fields
    IF entry_row.etymology IS NULL THEN
        quality_score := quality_score - 0.1;
    END IF;
    
    IF entry_row.pos_tag IS NULL THEN
        quality_score := quality_score - 0.1;
    END IF;
    
    IF entry_row.embedding IS NULL THEN
        quality_score := quality_score - 0.2;
    END IF;
    
    -- Deduct for validation errors
    IF entry_row.validation_errors IS NOT NULL THEN
        quality_score := quality_score - (0.1 * array_length(entry_row.validation_errors, 1));
    END IF;
    
    -- Deduct for short definitions
    IF LENGTH(entry_row.definition) < 10 THEN
        quality_score := quality_score - 0.2;
    END IF;
    
    RETURN GREATEST(0.0, quality_score);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Trigger to auto-compute quality on insert/update
CREATE OR REPLACE FUNCTION update_entry_quality()
RETURNS TRIGGER AS $$
BEGIN
    NEW.data_quality := compute_entry_quality(NEW);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER compute_quality_on_save
    BEFORE INSERT OR UPDATE ON entries
    FOR EACH ROW
    EXECUTE FUNCTION update_entry_quality();

