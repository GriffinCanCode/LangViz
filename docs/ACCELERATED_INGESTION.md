# Accelerated Data Ingestion

## Overview

The LangViz ingestion pipeline has been optimized using the same patterns as the processing pipeline, achieving **10,000+ entries/second** throughput (vs ~100-300 entries/sec baseline).

## Key Optimizations

### 1. Bulk Raw Loading with COPY Protocol
- **Before**: Individual INSERT statements (one per entry)
- **After**: PostgreSQL COPY protocol with temporary tables
- **Speedup**: 100-1000x faster for raw data loading
- **Technique**: Batch 10,000 entries at a time using CSV format

### 2. Parallel Cleaning Workers
- **Before**: Sequential cleaning (one entry at a time)
- **After**: 4-8 parallel worker processes
- **Architecture**: Queue-based pipeline with asyncio
- **Benefit**: Utilizes all CPU cores for text cleaning

### 3. Bulk Upserts
- **Before**: Individual INSERT ... ON CONFLICT per entry
- **After**: Temporary table + bulk INSERT ... ON CONFLICT
- **Speedup**: 50-100x faster for database writes
- **Deduplication**: Built-in at database level

### 4. Queue-Based Pipeline Architecture
```
[File Loader] → [Bulk Raw Insert] → 
[Raw DB Fetch] → [Raw Queue] → 
[Cleaners × N] → [Cleaned Queue] → 
[Writers × K] → [PostgreSQL]
```

- Overlaps I/O, compute, and database operations
- Backpressure handling prevents memory overflow
- Each stage runs independently with async coordination

## Performance Profile

### Expected Throughput
- **Standard Mode** (4 workers): 5,000-10,000 entries/sec
- **Fast Mode** (8 workers): 10,000-15,000 entries/sec
- **Baseline** (old implementation): 100-300 entries/sec

### Speedup
- **30-100x faster** than original implementation
- Scales linearly with CPU cores

### Resource Usage
- **CPU**: Utilizes all available cores
- **Memory**: ~500MB-1GB for queues and buffers
- **Database**: Connection pool of 5-20 connections

## Usage

### Basic Ingestion
```bash
make ingest
```
This uses the default configuration:
- 4 parallel cleaners
- 2 parallel writers
- Batch sizes: 10,000 (load), 5,000 (clean), 10,000 (write)

### High-Speed Ingestion
```bash
make ingest-fast
```
This uses maximum performance configuration:
- 8 parallel cleaners
- 4 parallel writers
- Batch sizes: 20,000 (load), 10,000 (clean), 20,000 (write)

### Custom Configuration via CLI
```bash
cd backend && . venv/bin/activate && cd .. && \
PYTHONPATH=. python3 -m backend.cli.ingest ingest \
    --file data/sources/kaikki \
    --source kaikki \
    --format json \
    --workers 6 \
    --load-batch 15000 \
    --clean-batch 7500 \
    --write-batch 15000
```

### Reprocessing
Reprocess raw entries with updated pipeline:
```bash
make reprocess
```

Or with custom configuration:
```bash
cd backend && . venv/bin/activate && cd .. && \
PYTHONPATH=. python3 -m backend.cli.ingest reprocess \
    --source kaikki \
    --workers 8 \
    --clean-batch 10000 \
    --write-batch 20000
```

## Configuration Parameters

### Worker Configuration
- `--workers N`: Number of parallel cleaning workers (default: 4)
  - Recommended: Match CPU core count
  - Writers are automatically set to N/2

### Batch Sizes
- `--load-batch N`: Raw entries per COPY operation (default: 10000)
  - Larger = fewer round-trips, more memory
  - Recommended: 5000-20000

- `--clean-batch N`: Entries per cleaning batch (default: 5000)
  - Controls queue throughput
  - Recommended: 2500-10000

- `--write-batch N`: Entries per bulk upsert (default: 10000)
  - PostgreSQL COPY optimization
  - Recommended: 5000-20000

### Quality Control
- `--allow-duplicates`: Disable automatic deduplication
  - Default: Duplicates are skipped
  - Use for testing or when duplicates are expected

## Architecture Details

### Stage 1: File Loading
- Loads raw data from source files (JSON, CSV, CLDF, etc.)
- Generates checksums for deduplication
- No blocking - pure extraction

### Stage 2: Bulk Raw Storage
- Uses PostgreSQL COPY protocol
- Temporary table approach for upserts
- Deduplication via ON CONFLICT (checksum)
- Batches of 10,000-20,000 entries

### Stage 3: Parallel Cleaning
- N worker processes clean entries in parallel
- Each applies full cleaning pipeline:
  - Text normalization
  - Whitespace cleanup
  - HTML/XML stripping
  - Unicode normalization
- Quality threshold filtering

### Stage 4: Bulk Writing
- K writer processes handle database upserts
- Buffers entries until batch size reached
- Uses temporary table + INSERT ... ON CONFLICT
- Automatic deduplication by (headword, language)

## Comparison with Processing Pipeline

Both pipelines share the same optimization principles:

| Feature | Ingestion | Processing |
|---------|-----------|------------|
| **Bulk Operations** | COPY protocol | COPY protocol |
| **Parallel Workers** | 4-8 cleaners | 4 cleaners |
| **Queue Architecture** | 3 stages | 4 stages |
| **Batch Sizes** | 5K-20K | 5K-10K |
| **Throughput** | 10,000/sec | 5,000/sec |
| **GPU Acceleration** | No | Yes (embeddings) |

The processing pipeline includes an additional GPU-accelerated embedding stage, which limits throughput to ~5,000/sec. Ingestion is faster because it skips embedding generation.

## Monitoring

The pipeline provides real-time progress monitoring:
```
[1/4] Extracted 1,000,000 entries from file
[2/4] Bulk loading 1,000,000 raw entries...
      ✓ Raw entries loaded at 15,234 entries/sec
[3/4] Transforming with 4 parallel cleaners...
      ✓ Transformed: 987,432
      ✓ Validation errors: 12,568
      ✓ Duplicates skipped: 0

======================================================================
INGESTION COMPLETE!
Total Loaded: 1,000,000
Transformed: 987,432
Saved: 987,432
Errors: 12,568
Duplicates Skipped: 0
Duration: 98.2s
Rate: 10,051.3 entries/sec
======================================================================
```

## Troubleshooting

### Out of Memory
If you encounter memory issues:
1. Reduce `--workers` to 2-4
2. Reduce batch sizes to 2500-5000
3. Check database connection pool (should be < 20)

### Database Connection Errors
If you see "too many connections":
1. Reduce `--workers`
2. Check that other services aren't using connections
3. Increase PostgreSQL max_connections if needed

### Slow Performance
If not reaching expected throughput:
1. Check CPU usage (should be near 100%)
2. Verify PostgreSQL is on fast storage (SSD)
3. Increase batch sizes for fewer round-trips
4. Check for disk I/O bottlenecks

## Future Optimizations

Potential further improvements:
1. **Streaming JSON parsing**: Avoid loading entire file into memory
2. **Parallel file reading**: Process multiple files simultaneously
3. **Zero-copy data transfer**: Reduce memory allocations
4. **Compressed transfer**: Reduce network overhead for remote databases
5. **Partitioned tables**: Distribute writes across multiple tables

## See Also

- [OPTIMIZED_QUICK_START.md](../OPTIMIZED_QUICK_START.md) - Processing pipeline
- [STORAGE_SYSTEM.md](STORAGE_SYSTEM.md) - Database architecture
- [PERFORMANCE.md](PERFORMANCE.md) - Performance benchmarks

