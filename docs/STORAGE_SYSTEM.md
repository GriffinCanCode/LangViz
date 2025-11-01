# LangViz Storage & Data Cleaning System

## Overview

A sophisticated, production-ready data ingestion and cleaning system designed for computational linguistics research. Built on first principles to maximize reproducibility, testability, and extensibility.

## Architecture Philosophy

### Why ELT-V Over Traditional ETL?

**Traditional ETL Problems:**
- Data transformations happen before storage → can't reprocess without re-extracting
- Coupled transformation logic → hard to test and modify
- Lost provenance → can't audit data quality issues
- Side effects → non-reproducible results

**ELT-V Solution:**
```
Extract → Load → Transform → Validate
  ↓        ↓         ↓          ↓
Parse → Store → Clean → Check
(Perl)  (Raw)   (Pure)  (Rules)
```

**Benefits:**
1. **Reproducibility**: Reprocess with improved algorithms
2. **Auditability**: Complete transformation lineage
3. **Testability**: Pure functions, no side effects
4. **Extensibility**: Composable cleaners
5. **Resilience**: Idempotent operations

## Core Abstractions

### 1. Cleaners (Pure Functions)

Each cleaner implements a simple protocol:

```python
@dataclass(frozen=True)
class MyCleaner:
    name: str = "my_cleaner"
    version: str = "1.0.0"
    
    def clean(self, value: T, **params) -> T:
        """Pure transformation - no side effects."""
        ...
    
    def validate(self, value: T) -> bool:
        """Check if value is valid."""
        ...
```

**Design Properties:**
- Immutable (frozen dataclass)
- Pure (no side effects)
- Versioned (for provenance)
- Testable (easy unit tests)
- Composable (pipeline building)

### 2. Pipelines (Functional Composition)

Pipelines compose cleaners:

```python
pipeline = Pipeline([
    HeadwordCleaner(),
    TextNormalizer(),
    IPACleaner(),
])

cleaned, provenance = pipeline.apply(raw_value)
```

**Features:**
- Automatic provenance tracking
- Validation at each step (if strict)
- Batch processing support
- Pipeline signatures for versioning

### 3. Loaders (Format Parsers)

Minimal parsing to raw data:

```python
loader = LoaderFactory.get_loader('cldf')
for raw_entry in loader.load(file_path, source_id):
    # raw_entry contains: data, checksum, provenance
    ...
```

**Supported Formats:**
- CLDF (Cross-Linguistic Data Formats)
- Swadesh CSV lists
- Starling database format
- Generic JSON

### 4. Validators (Quality Gates)

Composable validation rules:

```python
validator = EntryValidator([
    RequiredField('headword'),
    MinLength('definition', 3),
    IPAValidator(),
    LanguageCodeValidator(),
])

is_valid, errors = validator.validate(entry)
```

## Data Flow

```
┌─────────────┐
│ Raw Files   │ (Immutable source)
└──────┬──────┘
       │ Loader
       ↓
┌─────────────┐
│ raw_entries │ (PostgreSQL: JSON + checksum)
└──────┬──────┘
       │ Pipeline
       ↓
┌─────────────┐
│ Transform   │ (Pure functions)
│   Log       │ (Audit trail)
└──────┬──────┘
       │ Validator
       ↓
┌─────────────┐
│   entries   │ (Cleaned, typed data)
└─────────────┘
```

## Database Schema

### Layered Architecture

**Layer 1: Raw Data (Immutable)**
```sql
raw_entries (
    id SERIAL,
    source_id VARCHAR(100),
    raw_data JSONB,
    checksum VARCHAR(64) UNIQUE,  -- SHA-256
    ingested_at TIMESTAMP,
    file_path TEXT,
    line_number INTEGER
)
```

**Layer 2: Transformation Log (Audit)**
```sql
transform_log (
    raw_entry_id INTEGER,
    step_name VARCHAR(100),
    step_version VARCHAR(20),
    parameters JSONB,
    executed_at TIMESTAMP,
    duration_ms INTEGER,
    success BOOLEAN,
    error_message TEXT
)
```

**Layer 3: Cleaned Data (Typed)**
```sql
entries (
    id VARCHAR(255),
    headword VARCHAR(255),
    ipa VARCHAR(255),
    language VARCHAR(3),
    definition TEXT,
    etymology TEXT,
    pos_tag VARCHAR(50),
    embedding vector(768),
    -- Provenance
    raw_entry_id INTEGER,
    source_id VARCHAR(100),
    pipeline_version VARCHAR(255),
    data_quality FLOAT,
    validation_errors TEXT[]
)
```

### Key Indexes

```sql
-- Vector similarity (HNSW)
CREATE INDEX ON entries USING hnsw (embedding vector_cosine_ops);

-- Full-text search
CREATE INDEX ON entries USING gin(to_tsvector('english', definition));

-- Fast lookups
CREATE INDEX ON entries(language);
CREATE INDEX ON entries(data_quality);
```

## Code Organization

```
backend/storage/
├── __init__.py         # Barrel exports
├── repositories.py     # Data access (EntryRepository)
├── provenance.py       # Source, TransformStep, Provenance
├── cleaners.py         # Pure cleaning functions
├── pipeline.py         # Pipeline composition
├── loaders.py          # Format-specific parsers
├── validators.py       # Validation rules
├── ingest.py           # Orchestration service
└── migrations/
    ├── 001_initial_schema.sql
    └── 002_provenance_layer.sql
```

**File Organization Principles:**
- One word, memorable names
- Single responsibility per file
- <300 lines per file (most <200)
- Strong typing throughout
- No circular dependencies

## Usage Examples

### Basic Ingestion

```python
from backend.storage import IngestService
import asyncpg

pool = await asyncpg.create_pool(database_url)
service = IngestService(pool)

# Ingest CLDF dataset
stats = await service.ingest_file(
    file_path='data/raw/ielex',
    source_id='ielex',
    format='cldf'
)

print(f"Loaded: {stats['raw_loaded']}")
print(f"Cleaned: {stats['transformed']}")
print(f"Saved: {stats['saved']}")
```

### Custom Pipeline

```python
from backend.storage import Pipeline, compose
from backend.storage.cleaners import (
    IPACleaner,
    TextNormalizer,
    HeadwordCleaner,
)

# Compose custom pipeline
pipeline = compose(
    HeadwordCleaner(),
    TextNormalizer(lowercase=False),
    IPACleaner(),
    strict=True
)

# Apply to data
cleaned, steps = pipeline.apply("  *wódr̥  ")
# Result: "wódr̥"
# Steps: [HeadwordCleaner:1.0.0, TextNormalizer:1.0.0, IPACleaner:1.0.0]
```

### Reprocessing

```python
# After improving cleaners, reprocess without re-downloading
stats = await service.reprocess_with_pipeline(
    source_id='ielex'  # or None for all
)
```

### Quality Analysis

```python
from backend.storage import ValidatorFactory

validator = ValidatorFactory.standard_entry_validator()
errors_map = validator.batch_validate(entries)

for entry_id, errors in errors_map.items():
    print(f"{entry_id}: {errors}")
```

## Performance Characteristics

### Ingestion Rates

| Format  | Entries/sec | Notes |
|---------|-------------|-------|
| CLDF    | ~500        | Metadata overhead |
| CSV     | ~1000       | Simple format |
| JSON    | ~800        | Depends on nesting |
| Starling| ~300        | Complex parsing |

### Memory Usage

- Raw entry: ~1KB average
- Cleaned entry with embedding: ~3KB
- Transform log: ~0.5KB per entry
- Total: ~4.5KB per entry

### Database Size Estimates

For 100,000 entries:
- Raw data: ~100MB
- Transform logs: ~50MB
- Entries: ~300MB
- Indexes: ~150MB
- **Total: ~600MB**

## Testing Strategy

### Unit Tests (Pure Functions)

```python
def test_ipa_cleaner():
    cleaner = IPACleaner()
    
    # Test normalization
    assert cleaner.clean("[wódr̥]") == "wódr̥"
    assert cleaner.clean("  wódr̥  ") == "wódr̥"
    
    # Test validation
    assert cleaner.validate("wódr̥") == True
    assert cleaner.validate("123") == False
```

### Integration Tests (Pipelines)

```python
async def test_full_pipeline():
    pipeline = PipelineFactory.for_ipa()
    
    result, steps = pipeline.apply("  [wódr̥]  ")
    
    assert result == "wódr̥"
    assert len(steps) > 0
    assert all(s.success for s in steps)
```

### Property Tests (Invariants)

```python
@given(st.text())
def test_cleaner_idempotent(text):
    """Cleaning twice should equal cleaning once."""
    cleaner = TextNormalizer()
    
    once = cleaner.clean(text)
    twice = cleaner.clean(once)
    
    assert once == twice
```

## Extension Points

### Adding a New Cleaner

1. Implement `ICleaner` protocol
2. Make it immutable (frozen dataclass)
3. Keep it pure (no side effects)
4. Version it
5. Add to `cleaners.py`

### Adding a New Format

1. Implement loader yielding `RawEntry`
2. Add to `LoaderFactory`
3. Register in `catalog.toml`
4. Document format specifics

### Adding New Validation Rules

1. Create rule class with `__call__`
2. Return `(bool, str)` tuple
3. Add to validator factory
4. Test edge cases

## Best Practices

### DO

✅ Preserve raw data immutably
✅ Version all cleaners and pipelines
✅ Write pure functions
✅ Track provenance
✅ Test cleaners in isolation
✅ Use strong typing
✅ Document assumptions

### DON'T

❌ Transform data before storing raw
❌ Modify cleaners without versioning
❌ Use side effects in cleaners
❌ Skip validation
❌ Ignore data quality scores
❌ Use `any` types
❌ Create circular dependencies

## Troubleshooting

### Common Issues

**Validation errors on ingest**
```bash
# Check what's failing
python3 -m backend.cli.ingest validate --limit 100
```

**Pipeline is too slow**
```python
# Use batch processing
results = pipeline.batch_apply(entries)

# Or disable provenance tracking
result, _ = pipeline.apply(value, track_provenance=False)
```

**Duplicate entries**
```python
# Check for duplicates
from backend.storage.cleaners import DuplicateDetector

detector = DuplicateDetector()
dupes = detector.detect_duplicates(entries, ['headword', 'language'])
```

## Advanced Topics

### Custom Quality Scoring

```python
def custom_quality_score(entry: Entry) -> float:
    score = 1.0
    
    # Penalize missing etymology more
    if not entry.etymology:
        score -= 0.3
    
    # Reward entries with cognate sets
    if has_cognates(entry):
        score += 0.1
    
    return max(0.0, min(1.0, score))
```

### Parallel Processing

```python
import asyncio

async def ingest_parallel(files: list[str]):
    tasks = [
        service.ingest_file(f, source, format)
        for f in files
    ]
    results = await asyncio.gather(*tasks)
    return results
```

### Streaming Large Files

```python
async def stream_ingest(file_path: str):
    loader = LoaderFactory.get_loader(format)
    
    batch = []
    async for raw_entry in loader.load_async(file_path):
        batch.append(raw_entry)
        
        if len(batch) >= 1000:
            await process_batch(batch)
            batch = []
```

## Future Enhancements

### Planned Features

- [ ] Incremental ingestion (only new entries)
- [ ] Conflict resolution strategies
- [ ] Machine learning for quality prediction
- [ ] Automated data drift detection
- [ ] Multi-language parallel processing
- [ ] Real-time streaming ingestion
- [ ] GraphQL query interface

### Research Directions

- Active learning for validation rules
- Cross-lingual entity resolution
- Automated cognate detection in pipeline
- Semantic deduplication using embeddings
- Phylogenetic-aware quality scoring

## References

- [CLDF Specification](https://cldf.clld.org/)
- [Lexibank](https://github.com/lexibank)
- [Functional Data Engineering](https://maximebeauchemin.medium.com/functional-data-engineering-a-modern-paradigm-for-batch-data-processing-2327ec32c42a)
- [Data Quality Dimensions](https://www.datasciencecentral.com/six-dimensions-data-quality/)

