"""Accelerated data ingestion orchestration.

ELT-V pipeline: Extract, Load, Transform, Validate
Optimized with parallel workers, bulk operations, and queue-based architecture.

Performance Targets:
- 10,000+ entries/second for raw loading (COPY protocol)
- Parallel cleaning across CPU cores
- Bulk upserts for transformed data
"""

import tomli
import asyncio
import io
import csv
from pathlib import Path
from typing import Optional, Sequence
from datetime import datetime
from dataclasses import dataclass, field

import asyncpg

from backend.storage.provenance import Source, SourceType, DataQuality, Provenance
from backend.storage.loaders import LoaderFactory, RawEntry
from backend.storage.pipeline import PipelineFactory
from backend.storage.bulk import BulkWriter
from backend.core.types import Entry
from backend.observ import get_logger

logger = get_logger(__name__)


@dataclass
class IngestConfig:
    """Configuration for accelerated ingestion."""
    
    # Batch sizes
    load_batch: int = 10000  # Load raw entries in large batches
    clean_batch: int = 5000  # Clean in batches
    write_batch: int = 10000  # Bulk write size
    
    # Parallelism
    num_cleaners: int = 4  # Parallel cleaning workers
    num_writers: int = 2  # Parallel writers
    
    # Queue sizes
    raw_queue_size: int = 10
    cleaned_queue_size: int = 10
    
    # Quality control
    quality_threshold: float = 0.5
    skip_duplicates: bool = True


@dataclass
class IngestStats:
    """Real-time ingestion statistics."""
    
    total_loaded: int = 0
    processed: int = 0
    transformed: int = 0
    saved: int = 0
    validation_errors: int = 0
    duplicates_skipped: int = 0
    failed: int = 0
    
    start_time: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def entries_per_second(self) -> float:
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        return self.processed / elapsed if elapsed > 0 else 0.0


class IngestService:
    """Orchestrates the complete accelerated data ingestion pipeline.
    
    Architecture:
    [File Loader] → [Raw Queue] → [Bulk Raw Insert] → 
    [Raw DB Fetch] → [Cleaners × N] → [Cleaned Queue] → 
    [Writers × K] → [PostgreSQL]
    """
    
    def __init__(self, db_pool: asyncpg.Pool, config: IngestConfig = None):
        self._pool = db_pool
        self._config = config or IngestConfig()
        self._stats = IngestStats()
        self._bulk_writer = BulkWriter(db_pool)
        
        # Pipeline queues
        self._raw_queue = asyncio.Queue(maxsize=self._config.raw_queue_size)
        self._cleaned_queue = asyncio.Queue(maxsize=self._config.cleaned_queue_size)
        
        # Control flags
        self._stop_flag = asyncio.Event()
        self._error: Optional[Exception] = None
    
    async def load_source_catalog(self, catalog_path: str) -> list[Source]:
        """Load data source catalog from TOML."""
        with open(catalog_path, 'rb') as f:
            catalog = tomli.load(f)
        
        sources = []
        for src in catalog['source']:
            source = Source(
                id=src['id'],
                name=src['name'],
                type=SourceType(src['type']),
                format=src['format'],
                url=src['url'],
                languages=src['languages'],
                license=src['license'],
                quality=DataQuality(src['quality']),
                version=src.get('version'),
                retrieved_at=datetime.utcnow()
            )
            sources.append(source)
        
        return sources
    
    async def register_source(self, source: Source) -> None:
        """Register data source in database."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO data_sources (
                    id, name, source_type, format, url,
                    license, quality, version, retrieved_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    version = EXCLUDED.version,
                    retrieved_at = EXCLUDED.retrieved_at
                """,
                source.id,
                source.name,
                source.type.value,
                source.format,
                source.url,
                source.license,
                source.quality.value,
                source.version,
                source.retrieved_at
            )
    
    async def ingest_file(
        self,
        file_path: str,
        source_id: str,
        format: str,
        dry_run: bool = False
    ) -> dict[str, int]:
        """Ingest a data file through the accelerated pipeline.
        
        Returns statistics about the ingestion.
        """
        logger.info(
            "accelerated_ingestion_started",
            file_path=file_path,
            source_id=source_id,
            format=format,
            dry_run=dry_run,
            config=self._config
        )
        
        print(f"\n{'='*70}")
        print(f"ACCELERATED INGESTION PIPELINE")
        print(f"File: {file_path}")
        print(f"Source: {source_id}")
        print(f"Format: {format}")
        print(f"Configuration:")
        print(f"  Load Batch: {self._config.load_batch}")
        print(f"  Clean Batch: {self._config.clean_batch}")
        print(f"  Write Batch: {self._config.write_batch}")
        print(f"  Parallel Cleaners: {self._config.num_cleaners}")
        print(f"  Parallel Writers: {self._config.num_writers}")
        print(f"{'='*70}\n")
        
        # 1. EXTRACT: Load raw data
        logger.info("extract_phase_started")
        loader = LoaderFactory.get_loader(format)
        raw_entries = list(loader.load(file_path, source_id))
        self._stats.total_loaded = len(raw_entries)
        
        print(f"[1/4] Extracted {self._stats.total_loaded:,} entries from file")
        
        if dry_run:
            return self._stats_to_dict()
        
        # 2. LOAD: Bulk store raw entries (immutable) - OPTIMIZED WITH COPY
        logger.info("load_phase_started", count=len(raw_entries))
        print(f"[2/4] Bulk loading {len(raw_entries):,} raw entries...")
        
        await self._bulk_store_raw_entries(raw_entries)
        
        print(f"      ✓ Raw entries loaded at {self._stats.entries_per_second:.0f} entries/sec")
        
        # 3. TRANSFORM: Apply cleaning pipelines with parallel workers
        logger.info("transform_phase_started")
        print(f"[3/4] Transforming with {self._config.num_cleaners} parallel cleaners...")
        
        await self._accelerated_transform(source_id)
        
        print(f"      ✓ Transformed: {self._stats.transformed:,}")
        print(f"      ✓ Validation errors: {self._stats.validation_errors:,}")
        print(f"      ✓ Duplicates skipped: {self._stats.duplicates_skipped:,}")
        
        # 4. Final summary
        duration = (datetime.utcnow() - self._stats.start_time).total_seconds()
        
        print(f"\n{'='*70}")
        print(f"INGESTION COMPLETE!")
        print(f"Total Loaded: {self._stats.total_loaded:,}")
        print(f"Transformed: {self._stats.transformed:,}")
        print(f"Saved: {self._stats.saved:,}")
        print(f"Errors: {self._stats.validation_errors:,}")
        print(f"Duplicates Skipped: {self._stats.duplicates_skipped:,}")
        print(f"Duration: {duration:.1f}s")
        print(f"Rate: {self._stats.entries_per_second:.1f} entries/sec")
        print(f"{'='*70}\n")
        
        logger.info("accelerated_ingestion_completed", **self._stats_to_dict())
        return self._stats_to_dict()
    
    async def _bulk_store_raw_entries(self, entries: Sequence[RawEntry]) -> None:
        """Bulk store raw entries using COPY protocol - OPTIMIZED."""
        if not entries:
            return
        
        start_time = datetime.utcnow()
        
        # Process in large batches
        for i in range(0, len(entries), self._config.load_batch):
            batch = entries[i:i + self._config.load_batch]
            
            # Prepare CSV buffer for COPY
            buffer = io.StringIO()
            writer = csv.writer(buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
            
            for entry in batch:
                writer.writerow([
                    entry.source_id,
                    entry.data,  # JSONB data
                    entry.checksum,
                    entry.file_path or '',
                    entry.line_number or 0
                ])
            
            buffer.seek(0)
            
            # Bulk insert with ON CONFLICT DO NOTHING for deduplication
            async with self._pool.acquire() as conn:
                # Use temporary table approach for upsert
                async with conn.transaction():
                    await conn.execute("""
                        CREATE TEMPORARY TABLE raw_entries_temp (
                            source_id VARCHAR(255),
                            raw_data JSONB,
                            checksum VARCHAR(64),
                            file_path TEXT,
                            line_number INTEGER
                        ) ON COMMIT DROP
                    """)
                    
                    await conn.copy_to_table(
                        'raw_entries_temp',
                        source=buffer,
                        columns=['source_id', 'raw_data', 'checksum', 'file_path', 'line_number'],
                        format='csv',
                        delimiter='\t'
                    )
                    
                    # Insert from temp table with deduplication
                    await conn.execute("""
                        INSERT INTO raw_entries (source_id, raw_data, checksum, file_path, line_number)
                        SELECT source_id, raw_data::jsonb, checksum, file_path, line_number
                        FROM raw_entries_temp
                        ON CONFLICT (checksum) DO NOTHING
                    """)
            
            self._stats.processed += len(batch)
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        rate = len(entries) / duration if duration > 0 else 0
        
        logger.info(
            "bulk_raw_load_completed",
            total=len(entries),
            duration_seconds=duration,
            rate_per_second=rate
        )
    
    async def _accelerated_transform(self, source_id: str) -> None:
        """Transform entries using parallel workers and bulk operations."""
        
        # Start pipeline stages
        tasks = []
        
        # Stage 1: DB Reader (fetch raw entries)
        tasks.append(asyncio.create_task(
            self._raw_db_reader(source_id)
        ))
        
        # Stage 2: Cleaners (parallel)
        for i in range(self._config.num_cleaners):
            tasks.append(asyncio.create_task(
                self._cleaner_worker(worker_id=i)
            ))
        
        # Stage 3: Writers (parallel bulk writes)
        for i in range(self._config.num_writers):
            tasks.append(asyncio.create_task(
                self._writer_worker(worker_id=i)
            ))
        
        # Wait for completion
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error("transform_pipeline_error", error=str(e))
            self._stop_flag.set()
            raise
    
    async def _raw_db_reader(self, source_id: str) -> None:
        """Stage 1: Read raw entries from database."""
        logger.info("raw_db_reader_started", source_id=source_id)
        
        try:
            async with self._pool.acquire() as conn:
                # Stream raw entries in batches
                offset = 0
                
                while not self._stop_flag.is_set():
                    rows = await conn.fetch(
                        """
                        SELECT id, raw_data, source_id, checksum
                        FROM raw_entries
                        WHERE source_id = $1
                        ORDER BY id
                        LIMIT $2 OFFSET $3
                        """,
                        source_id, self._config.clean_batch, offset
                    )
                    
                    if not rows:
                        break
                    
                    # Put batch in queue
                    batch = [
                        {
                            'id': row['id'],
                            'raw_data': row['raw_data'],
                            'checksum': row['checksum']
                        }
                        for row in rows
                    ]
                    await self._raw_queue.put(batch)
                    offset += len(rows)
            
            # Signal completion
            for _ in range(self._config.num_cleaners):
                await self._raw_queue.put(None)
            
            logger.info("raw_db_reader_completed")
            
        except Exception as e:
            logger.error("raw_db_reader_failed", error=str(e))
            self._error = e
            self._stop_flag.set()
            raise
    
    async def _cleaner_worker(self, worker_id: int) -> None:
        """Stage 2: Clean and validate entries."""
        logger.info("cleaner_worker_started", worker_id=worker_id)
        
        pipelines = PipelineFactory.full_entry_pipeline()
        
        try:
            while not self._stop_flag.is_set():
                # Get batch from queue
                raw_batch = await self._raw_queue.get()
                
                # Check for completion signal
                if raw_batch is None:
                    await self._cleaned_queue.put(None)
                    break
                
                cleaned_entries = []
                
                for raw in raw_batch:
                    try:
                        # Apply cleaning pipelines
                        raw_data = raw['raw_data']
                        cleaned_data = {}
                        
                        for field, pipeline in pipelines.items():
                            if field in raw_data and raw_data[field]:
                                cleaned, _ = pipeline.apply(raw_data[field], track_provenance=False)
                                cleaned_data[field] = cleaned
                        
                        # Create entry
                        entry = Entry(
                            id=f"{raw_data.get('source_id', 'unknown')}_{raw['checksum'][:16]}",
                            headword=cleaned_data.get('headword', ''),
                            ipa=cleaned_data.get('ipa', ''),
                            language=cleaned_data.get('language', ''),
                            definition=cleaned_data.get('definition', ''),
                            etymology=raw_data.get('etymology'),
                            pos_tag=raw_data.get('pos_tag'),
                            embedding=None,
                            created_at=datetime.utcnow()
                        )
                        
                        # Quality check
                        if self._meets_quality_threshold(entry):
                            cleaned_entries.append(entry)
                            self._stats.transformed += 1
                        else:
                            self._stats.validation_errors += 1
                    
                    except Exception as e:
                        logger.debug("entry_cleaning_failed", error=str(e))
                        self._stats.validation_errors += 1
                
                # Put cleaned batch in next queue
                if cleaned_entries:
                    await self._cleaned_queue.put(cleaned_entries)
                
                self._raw_queue.task_done()
            
            logger.info("cleaner_worker_completed", worker_id=worker_id)
            
        except Exception as e:
            logger.error("cleaner_worker_failed", worker_id=worker_id, error=str(e))
            self._error = e
            self._stop_flag.set()
            raise
    
    async def _writer_worker(self, worker_id: int) -> None:
        """Stage 3: Bulk write to database."""
        logger.info("writer_worker_started", worker_id=worker_id)
        
        try:
            write_buffer = []
            seen_keys = set()  # For deduplication
            
            while not self._stop_flag.is_set():
                # Get cleaned batch
                cleaned_batch = await self._cleaned_queue.get()
                
                # Check for completion signal
                if cleaned_batch is None:
                    # Flush remaining buffer
                    if write_buffer:
                        await self._flush_write_buffer(write_buffer)
                    break
                
                # Deduplicate within batch
                for entry in cleaned_batch:
                    key = (entry.headword, entry.language)
                    
                    if self._config.skip_duplicates and key in seen_keys:
                        self._stats.duplicates_skipped += 1
                        continue
                    
                    seen_keys.add(key)
                    write_buffer.append(entry)
                
                # Flush if buffer is large enough
                if len(write_buffer) >= self._config.write_batch:
                    await self._flush_write_buffer(write_buffer)
                    write_buffer = []
                
                self._cleaned_queue.task_done()
            
            logger.info("writer_worker_completed", worker_id=worker_id)
            
        except Exception as e:
            logger.error("writer_worker_failed", worker_id=worker_id, error=str(e))
            self._error = e
            self._stop_flag.set()
            raise
    
    async def _flush_write_buffer(self, entries: list[Entry]) -> None:
        """Flush write buffer using bulk operations."""
        if not entries:
            return
        
        try:
            # Bulk upsert (no concept assignments for ingestion)
            written = await self._bulk_writer.bulk_upsert_entries(entries, None)
            
            self._stats.saved += written
            
        except Exception as e:
            logger.error("write_flush_failed", count=len(entries), error=str(e))
            self._stats.failed += len(entries)
            raise
    
    def _meets_quality_threshold(self, entry: Entry) -> bool:
        """Check if entry meets minimum quality threshold."""
        if not entry.headword or not entry.definition:
            return False
        if len(entry.definition) < 10:
            return False
        return True
    
    def _stats_to_dict(self) -> dict[str, int]:
        """Convert stats to dictionary."""
        return {
            'raw_loaded': self._stats.total_loaded,
            'transformed': self._stats.transformed,
            'validation_errors': self._stats.validation_errors,
            'duplicates_skipped': self._stats.duplicates_skipped,
            'saved': self._stats.saved,
            'failed': self._stats.failed
        }
    
    async def reprocess_with_pipeline(
        self,
        source_id: Optional[str] = None,
        new_pipeline_version: Optional[str] = None
    ) -> dict[str, int]:
        """Reprocess raw entries with updated pipeline using accelerated approach.
        
        This is the power of the ELT-V approach - can reprocess
        without re-downloading source data.
        """
        logger.info(
            "accelerated_reprocess_started",
            source_id=source_id,
            pipeline_version=new_pipeline_version
        )
        
        print(f"\n{'='*70}")
        print(f"ACCELERATED REPROCESSING PIPELINE")
        print(f"Source: {source_id or 'ALL'}")
        print(f"Using {self._config.num_cleaners} parallel cleaners")
        print(f"Using {self._config.num_writers} parallel writers")
        print(f"{'='*70}\n")
        
        # Reset stats for reprocessing
        self._stats = IngestStats()
        self._stop_flag.clear()
        
        # Count entries to reprocess
        async with self._pool.acquire() as conn:
            where_clause = f"WHERE source_id = '{source_id}'" if source_id else ""
            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM raw_entries {where_clause}"
            )
            self._stats.total_loaded = count
        
        print(f"Reprocessing {self._stats.total_loaded:,} raw entries...")
        
        # Use accelerated transform pipeline
        await self._accelerated_transform(source_id or '')
        
        duration = (datetime.utcnow() - self._stats.start_time).total_seconds()
        
        print(f"\n{'='*70}")
        print(f"REPROCESSING COMPLETE!")
        print(f"Reprocessed: {self._stats.transformed:,}")
        print(f"Saved: {self._stats.saved:,}")
        print(f"Errors: {self._stats.validation_errors:,}")
        print(f"Duration: {duration:.1f}s")
        print(f"Rate: {self._stats.entries_per_second:.1f} entries/sec")
        print(f"{'='*70}\n")
        
        return self._stats_to_dict()

