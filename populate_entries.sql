-- Direct SQL approach to populate entries from raw_entries
-- This bypasses the Python pipeline and does everything in PostgreSQL

BEGIN;

-- Ensure all required languages exist
INSERT INTO languages (iso_code, name, branch, subfamily)
SELECT DISTINCT 
    raw_data->>'lang_code' as iso_code,
    raw_data->>'lang' as name,
    'Unknown' as branch,
    NULL as subfamily
FROM raw_entries
WHERE raw_data->>'lang_code' IS NOT NULL
  AND raw_data->>'lang_code' != ''
  AND NOT EXISTS (
      SELECT 1 FROM languages 
      WHERE iso_code = raw_entries.raw_data->>'lang_code'
  )
ON CONFLICT (iso_code) DO NOTHING;

-- Insert entries from raw_entries (without embeddings for now)
-- Note: Using lang_code, word, and senses from the Kaikki format
INSERT INTO entries (
    id,
    headword,
    ipa,
    language,
    definition,
    etymology,
    pos_tag,
    raw_entry_id,
    source_id,
    data_quality,
    created_at
)
SELECT 
    md5(concat(
        coalesce(raw_data->>'word', ''),
        coalesce(raw_data->>'lang_code', ''),
        coalesce(raw_data->'senses'->0->>'glosses', '')
    )) as id,
    coalesce(raw_data->>'word', '') as headword,
    coalesce(raw_data->'sounds'->0->>'ipa', '') as ipa,
    coalesce(raw_data->>'lang_code', 'und') as language,
    coalesce(
        raw_data->'senses'->0->'glosses'->>0,
        raw_data->'senses'->0->>'raw_glosses',
        ''
    ) as definition,
    raw_data->>'etymology_text' as etymology,
    raw_data->>'pos' as pos_tag,
    id as raw_entry_id,
    source_id,
    0.5 as data_quality,  -- Default quality, can be updated later
    CURRENT_TIMESTAMP as created_at
FROM raw_entries
WHERE raw_data->>'word' IS NOT NULL
  AND raw_data->>'word' != ''
  AND raw_data->>'lang_code' IS NOT NULL
  AND raw_data->>'lang_code' != ''
  AND raw_data->'senses' IS NOT NULL
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- Show stats
SELECT 'Raw entries' as table_name, COUNT(*) as count FROM raw_entries
UNION ALL
SELECT 'Entries (populated)' as table_name, COUNT(*) as count FROM entries
UNION ALL
SELECT 'Entries without embeddings' as table_name, COUNT(*) as count FROM entries WHERE embedding IS NULL;

