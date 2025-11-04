-- Populate entries in chunks without a transaction wrapper for progress visibility
-- This allows partial progress to be saved and monitored

-- Step 1: Ensure all required languages exist
INSERT INTO languages (iso_code, name, branch, subfamily)
SELECT DISTINCT 
    raw_data->>'lang_code' as iso_code,
    raw_data->>'lang' as name,
    'Unknown' as branch,
    NULL as subfamily
FROM raw_entries
WHERE raw_data->>'lang_code' IS NOT NULL
  AND raw_data->>'lang_code' != ''
ON CONFLICT (iso_code) DO NOTHING;

SELECT 'Languages ready:', COUNT(*) FROM languages;

-- Step 2: Insert entries from raw_entries (without embeddings initially)
-- Using INSERT ... SELECT for efficient bulk loading
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
        coalesce(raw_data->'senses'->0->'glosses'->>0, '')
    )) as id,
    substring(coalesce(raw_data->>'word', '') from 1 for 255) as headword,
    substring(coalesce(raw_data->'sounds'->0->>'ipa', '') from 1 for 255) as ipa,
    substring(coalesce(raw_data->>'lang_code', 'und') from 1 for 3) as language,
    coalesce(
        raw_data->'senses'->0->'glosses'->>0,
        raw_data->'senses'->0->>'raw_glosses',
        ''
    ) as definition,
    raw_data->>'etymology_text' as etymology,
    substring(coalesce(raw_data->>'pos', '') from 1 for 50) as pos_tag,
    id as raw_entry_id,
    source_id,
    0.5 as data_quality,
    CURRENT_TIMESTAMP as created_at
FROM raw_entries
WHERE raw_data->>'word' IS NOT NULL
  AND raw_data->>'word' != ''
  AND raw_data->>'lang_code' IS NOT NULL
  AND raw_data->>'lang_code' != ''
  AND raw_data->'senses' IS NOT NULL
  AND jsonb_array_length(raw_data->'senses') > 0
  AND EXISTS (
      SELECT 1 FROM languages WHERE iso_code = raw_data->>'lang_code'
  )
ON CONFLICT (id) DO NOTHING;

-- Show final stats
SELECT 
    'Processing Complete!' as status,
    (SELECT COUNT(*) FROM raw_entries) as raw_entries,
    (SELECT COUNT(*) FROM entries) as entries_created,
    (SELECT COUNT(*) FROM entries WHERE embedding IS NULL) as needs_embeddings;

