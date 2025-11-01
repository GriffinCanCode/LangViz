# LangViz Data Layer

## Architecture

This data system follows an **ELT-V** (Extract, Load, Transform, Validate) architecture optimized for linguistic data processing.

### Design Principles

1. **Immutable Raw Layer**: Original data is preserved in `raw_entries` table
2. **Composable Transformations**: Pure functions in pipelines
3. **Provenance Tracking**: Full lineage from source to processed entry
4. **Idempotent Operations**: Safe to rerun without side effects
5. **Strong Typing**: Pydantic models throughout

### Key Benefits

- **Reproducibility**: Reprocess with improved algorithms without re-downloading
- **Auditability**: Track every transformation step
- **Testability**: Pure functions with no side effects
- **Extensibility**: Add cleaners without modifying existing code

## Directory Structure

```
data/
├── raw/          # Downloaded source files (immutable)
├── interim/      # Temporary processing artifacts
├── processed/    # Final cleaned datasets for export
├── sources/      # Source metadata and configurations
│   └── catalog.toml  # Registry of available data sources
└── README.md     # This file
```

## Data Sources

Available Indo-European language data sources are catalogued in `sources/catalog.toml`:

- **Swadesh Lists**: 207-item comparative wordlists
- **IE-CoR (IELex)**: Indo-European Cognate Database (CLDF format)
- **Wiktionary**: Community-maintained multilingual dictionary
- **Starling**: Tower of Babel etymological databases
- **Ciobanu Cognates**: Research cognate pairs dataset

## Usage

### Ingesting Data

```bash
# Ingest a CLDF dataset
python3 -m backend.cli.ingest ingest \
  --file data/raw/ielex \
  --source ielex \
  --format cldf \
  --catalog data/sources/catalog.toml

# Ingest a Swadesh list CSV
python3 -m backend.cli.ingest ingest \
  --file data/raw/swadesh_207.csv \
  --source swadesh_207 \
  --format csv

# Dry run (validate without storing)
python3 -m backend.cli.ingest ingest \
  --file data/raw/test.json \
  --source test \
  --format json \
  --dry-run
```

### Reprocessing Data

When you improve cleaning pipelines, reprocess without re-downloading:

```bash
# Reprocess all data
python3 -m backend.cli.ingest reprocess

# Reprocess specific source
python3 -m backend.cli.ingest reprocess --source ielex
```

### Validating Data

```bash
# Validate entries
python3 -m backend.cli.ingest validate --limit 1000

# Quiet mode (summary only)
python3 -m backend.cli.ingest validate --quiet
```

## Data Pipeline

### 1. Extract (Loaders)

Format-specific loaders parse raw data:
- `CLDFLoader`: CLDF metadata-driven datasets
- `SwadeshLoader`: CSV comparative wordlists
- `StarlingLoader`: Starling database format
- `JSONLoader`: Generic JSON dictionaries

### 2. Load (Raw Storage)

Store immutable raw data with checksums:
- Deduplicate based on SHA-256 hash
- Track file path and line number
- Enable future reprocessing

### 3. Transform (Cleaners & Pipelines)

Composable cleaning operations:

**Field-Specific Cleaners:**
- `IPACleaner`: Normalize IPA transcriptions
- `HeadwordCleaner`: Remove markers and artifacts
- `DefinitionCleaner`: Clean definition text
- `LanguageCodeCleaner`: Normalize to ISO 639
- `TextNormalizer`: Unicode and whitespace normalization

**Pipeline Composition:**
```python
from backend.storage import Pipeline, IPACleaner, TextNormalizer

# Build custom pipeline
pipeline = Pipeline([
    IPACleaner(),
    TextNormalizer(lowercase=False),
])

# Apply to data
cleaned, provenance = pipeline.apply(raw_ipa)
```

### 4. Validate (Validators)

Quality checks before storage:
- Required field validation
- Format validation (IPA, language codes)
- Length constraints
- Domain-specific rules

## Data Quality

### Quality Scoring

Each entry receives an automated quality score (0.0 - 1.0):
- 1.0 = All fields present, validated, with embeddings
- 0.8+ = High quality (recommended for research)
- 0.5-0.8 = Medium quality
- <0.5 = Low quality (needs review)

Penalties:
- Missing etymology: -0.1
- Missing POS tag: -0.1
- Missing embeddings: -0.2
- Validation errors: -0.1 each
- Short definition (<10 chars): -0.2

### Quality Dashboard

View data quality metrics:
```sql
SELECT * FROM data_quality_summary ORDER BY avg_entry_quality DESC;
```

## Database Schema

### Core Tables

- `data_sources`: Source metadata and provenance
- `raw_entries`: Immutable raw data with checksums
- `entries`: Cleaned, validated entries (main table)
- `transform_log`: Complete transformation history
- `quality_metrics`: Per-entry quality measurements

### Provenance Tracking

Every entry links back to:
1. Source (which dataset?)
2. Raw entry (original data)
3. Transform steps (what cleaning was applied?)
4. Pipeline version (reproducibility)

## Extending the System

### Adding a New Cleaner

```python
from dataclasses import dataclass
from backend.core.contracts import ICleaner

@dataclass(frozen=True)
class MyCleaner:
    name: str = "my_cleaner"
    version: str = "1.0.0"
    
    def clean(self, value: str, **params) -> str:
        # Your cleaning logic
        return value.strip()
    
    def validate(self, value: str) -> bool:
        return bool(value)
```

### Adding a New Loader

```python
from backend.storage.loaders import RawEntry

class MyLoader:
    def load(self, file_path: str, source_id: str):
        # Parse file
        for entry_data in parsed_entries:
            yield RawEntry(
                source_id=source_id,
                data=entry_data,
                checksum=compute_checksum(entry_data)
            )
```

## Best Practices

1. **Always preserve raw data**: Store originals in `data/raw/`
2. **Version pipelines**: Update cleaner versions when changing logic
3. **Test cleaners**: Unit test each cleaner in isolation
4. **Document sources**: Update `catalog.toml` with metadata
5. **Track quality**: Monitor `data_quality_summary` view
6. **Reprocess strategically**: When pipelines improve, reprocess

## Performance

### Optimization Strategies

- **Batch processing**: Use `batch_apply()` for pipelines
- **Parallel ingestion**: Process multiple files concurrently
- **Index usage**: PostgreSQL HNSW for vector similarity
- **Caching**: Redis for frequently accessed transformations

### Benchmarks

Typical ingestion rates (M1 Mac):
- CLDF dataset: ~500 entries/sec
- Swadesh CSV: ~1000 entries/sec
- Full pipeline with validation: ~200 entries/sec

## Troubleshooting

### Common Issues

**Import Error: pycldf not found**
```bash
pip install pycldf clldutils
```

**Database connection error**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Verify connection settings
cat .env | grep POSTGRES
```

**Validation errors on ingest**
```bash
# Use dry-run to test
python3 -m backend.cli.ingest ingest --dry-run ...

# Check validation rules
python3 -m backend.cli.ingest validate --limit 100
```

## References

- [CLDF Specification](https://cldf.clld.org/)
- [Lexibank Datasets](https://github.com/lexibank)
- [ISO 639 Language Codes](https://iso639-3.sil.org/)
- [IPA Chart](https://www.internationalphoneticassociation.org/content/ipa-chart)

