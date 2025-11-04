"""Accelerated batch processor with async pipeline architecture.

Pipeline Theory & Optimization:
- Producer-Consumer pattern: Overlap I/O, compute, and database operations
- Work-stealing for load balancing across CPU cores
- Zero-copy data transfer where possible
- Backpressure handling to prevent memory overflow

Performance Targets:
- 10,000+ entries/second (vs ~300/sec baseline)
- 6.7M entries in < 12 minutes (vs 7-10 hours)
- Linear scaling with CPU cores and GPU presence
"""

import asyncio
import asyncpg
from typing import AsyncIterator, Optional, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

from backend.core.types import Entry
from backend.storage.pipeline import Pipeline, PipelineFactory
from backend.storage.bulk import BulkWriter
from backend.services.embedding import OptimizedEmbeddingService
from backend.services.concepts import ConceptAligner
from backend.observ import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for accelerated pipeline."""
    
    # Batch sizes (tuned for GPU memory and network latency)
    db_fetch_batch: int = 5000  # Large DB fetches (network is bottleneck)
    embedding_batch: int = 512  # GPU batch size (memory constraint)
    db_write_batch: int = 10000  # Bulk write size (COPY optimization)
    
    # Parallelism
    num_cleaners: int = 4  # Parallel cleaning workers
    num_embedders: int = 1  # Usually 1 GPU, but can be >1 for multi-GPU
    num_writers: int = 2  # Parallel DB writers
    
    # Queue sizes (backpressure control)
    raw_queue_size: int = 10  # ~50K entries buffered
    cleaned_queue_size: int = 10  # ~5K entries buffered
    embedded_queue_size: int = 5  # ~2.5K entries buffered
    
    # Quality control
    quality_threshold: float = 0.5
    skip_existing_embeddings: bool = True


@dataclass
class PipelineStats:
    """Real-time pipeline statistics."""
    
    total_entries: int = 0
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    
    # Stage-specific stats
    cleaned: int = 0
    embedded: int = 0
    written: int = 0
    
    # Timing
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    
    # Queue depths (for monitoring)
    raw_queue_depth: int = 0
    cleaned_queue_depth: int = 0
    embedded_queue_depth: int = 0
    
    @property
    def entries_per_second(self) -> float:
        """Current processing rate."""
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        return self.processed / elapsed if elapsed > 0 else 0.0
    
    @property
    def estimated_remaining_seconds(self) -> float:
        """ETA to completion."""
        if self.entries_per_second == 0:
            return float('inf')
        remaining = self.total_entries - self.processed
        return remaining / self.entries_per_second


class AcceleratedBatchProcessor:
    """High-performance batch processor with async pipeline.
    
    Architecture:
    
    [DB Reader] → [Raw Queue] → [Cleaners × N] → [Cleaned Queue] →
    [Embedders × M] → [Embedded Queue] → [Writers × K] → [PostgreSQL]
    
    Each stage runs independently with async coordination.
    Backpressure prevents memory overflow.
    """
    
    def __init__(
        self,
        pool: asyncpg.Pool,
        embedding_service: OptimizedEmbeddingService,
        concept_aligner: ConceptAligner,
        config: PipelineConfig = None
    ):
        self._pool = pool
        self._embedding = embedding_service
        self._concepts = concept_aligner
        self._config = config or PipelineConfig()
        self._stats = PipelineStats()
        self._bulk_writer = BulkWriter(pool)
        
        # Pipeline queues
        self._raw_queue = asyncio.Queue(maxsize=self._config.raw_queue_size)
        self._cleaned_queue = asyncio.Queue(maxsize=self._config.cleaned_queue_size)
        self._embedded_queue = asyncio.Queue(maxsize=self._config.embedded_queue_size)
        
        # Control flags
        self._stop_flag = asyncio.Event()
        self._error: Optional[Exception] = None
    
    async def process_all(
        self,
        source_id: Optional[str] = None,
        resume_from: Optional[str] = None
    ) -> PipelineStats:
        """Process all entries through accelerated pipeline.
        
        Returns:
            Final statistics
        """
        logger.info(
            "accelerated_pipeline_starting",
            config=self._config,
            gpu_info=self._embedding.device_info
        )
        
        # Count total entries
        self._stats.total_entries = await self._count_entries(source_id, resume_from)
        
        print(f"\n{'='*70}")
        print(f"Accelerated Pipeline Processing")
        print(f"Total Entries: {self._stats.total_entries:,}")
        print(f"Configuration:")
        print(f"  DB Fetch Batch: {self._config.db_fetch_batch}")
        print(f"  Embedding Batch: {self._config.embedding_batch}")
        print(f"  DB Write Batch: {self._config.db_write_batch}")
        print(f"  Parallel Cleaners: {self._config.num_cleaners}")
        print(f"  Parallel Writers: {self._config.num_writers}")
        print(f"  GPU Device: {self._embedding.device_info['device']}")
        print(f"{'='*70}\n")
        
        # Start pipeline stages
        tasks = []
        
        # Stage 1: DB Reader (producer)
        tasks.append(asyncio.create_task(
            self._db_reader(source_id, resume_from)
        ))
        
        # Stage 2: Cleaners (parallel)
        for i in range(self._config.num_cleaners):
            tasks.append(asyncio.create_task(
                self._cleaner_worker(worker_id=i)
            ))
        
        # Stage 3: Embedders (parallel, usually 1 GPU)
        for i in range(self._config.num_embedders):
            tasks.append(asyncio.create_task(
                self._embedder_worker(worker_id=i)
            ))
        
        # Stage 4: Writers (parallel)
        for i in range(self._config.num_writers):
            tasks.append(asyncio.create_task(
                self._writer_worker(worker_id=i)
            ))
        
        # Note: Need to send None signal to each worker stage
        
        # Stage 5: Progress monitor
        tasks.append(asyncio.create_task(
            self._progress_monitor()
        ))
        
        # Wait for completion or error
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error("pipeline_error", error=str(e), error_type=type(e).__name__)
            self._error = e
            self._stop_flag.set()
            raise
        
        # Final report
        duration = (datetime.utcnow() - self._stats.start_time).total_seconds()
        
        print(f"\n{'='*70}")
        print(f"Pipeline Complete!")
        print(f"Total Processed: {self._stats.processed:,}")
        print(f"Succeeded: {self._stats.succeeded:,}")
        print(f"Failed: {self._stats.failed:,}")
        print(f"Skipped: {self._stats.skipped:,}")
        print(f"Duration: {duration:.1f}s")
        print(f"Rate: {self._stats.entries_per_second:.1f} entries/sec")
        print(f"Speedup: {self._estimate_speedup():.1f}x vs baseline")
        print(f"{'='*70}\n")
        
        return self._stats
    
    async def _db_reader(
        self,
        source_id: Optional[str],
        resume_from: Optional[str]
    ) -> None:
        """Stage 1: Read raw entries from database."""
        logger.info("db_reader_started")
        
        try:
            async with self._pool.acquire() as conn:
                # Build query
                where_clauses = []
                params = []
                
                if source_id:
                    where_clauses.append(f"source_id = ${len(params) + 1}")
                    params.append(source_id)
                
                if resume_from:
                    where_clauses.append(f"id > ${len(params) + 1}")
                    params.append(resume_from)
                
                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
                
                # Stream in large batches using fetch with LIMIT/OFFSET
                offset = 0
                batch = []
                
                while not self._stop_flag.is_set():
                    rows = await conn.fetch(
                        f"""
                        SELECT id, raw_data, source_id
                        FROM raw_entries
                        {where_sql}
                        ORDER BY id
                        LIMIT ${ len(params) + 1} OFFSET ${len(params) + 2}
                        """,
                        *params, self._config.db_fetch_batch, offset
                    )
                    
                    if not rows:
                        break
                    
                    for row in rows:
                        batch.append(row['raw_data'])  # Already a dict from JSONB column
                        
                        if len(batch) >= self._config.db_fetch_batch:
                            await self._raw_queue.put(batch)
                            batch = []
                    
                    offset += len(rows)
                
                # Send remaining
                if batch:
                    await self._raw_queue.put(batch)
            
            # Signal completion
            for _ in range(self._config.num_cleaners):
                await self._raw_queue.put(None)
            
            logger.info("db_reader_completed")
            
        except Exception as e:
            logger.error("db_reader_failed", error=str(e))
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
                        # Map Kaikki fields to our schema
                        mapped_raw = {
                            'headword': raw.get('word', ''),
                            'language': raw.get('lang_code', ''),
                            'ipa': (raw.get('sounds', [{}])[0].get('ipa', '') if raw.get('sounds') else ''),
                            'definition': ', '.join(
                                gloss for sense in raw.get('senses', [])
                                for gloss in (sense.get('glosses', []) or [sense.get('raw_glosses', '')])
                            ) if raw.get('senses') else '',
                            'pos_tag': raw.get('pos', ''),
                            'etymology': raw.get('etymology_text', '')
                        }
                        
                        # Apply cleaning pipelines
                        cleaned_data = {}
                        
                        for field, pipeline in pipelines.items():
                            if field in mapped_raw and mapped_raw[field]:
                                cleaned, _ = pipeline.apply(mapped_raw[field], track_provenance=False)
                                cleaned_data[field] = cleaned
                            else:
                                cleaned_data[field] = mapped_raw.get(field, '')
                        
                        # Create entry
                        entry = Entry(
                            id=self._generate_entry_id(cleaned_data),
                            headword=cleaned_data.get('headword', ''),
                            ipa=cleaned_data.get('ipa', ''),
                            language=cleaned_data.get('language', ''),
                            definition=cleaned_data.get('definition', ''),
                            etymology=cleaned_data.get('etymology', ''),
                            pos_tag=cleaned_data.get('pos_tag', ''),
                            embedding=None,  # Will be computed
                            created_at=datetime.utcnow()
                        )
                        
                        # Quality check
                        if self._meets_quality_threshold(entry):
                            cleaned_entries.append(entry)
                            self._stats.cleaned += 1
                        else:
                            self._stats.skipped += 1
                            if self._stats.skipped <= 5:  # Log first few skips for debugging
                                logger.debug("entry_skipped_quality", 
                                           headword=entry.headword, 
                                           ipa=entry.ipa,
                                           definition=entry.definition[:50] if entry.definition else None,
                                           language=entry.language)
                    
                    except Exception as e:
                        logger.debug("entry_cleaning_failed", error=str(e))
                        self._stats.failed += 1
                    
                    self._stats.processed += 1
                
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
    
    async def _embedder_worker(self, worker_id: int) -> None:
        """Stage 3: Compute embeddings (GPU-accelerated)."""
        logger.info("embedder_worker_started", worker_id=worker_id, device=self._embedding.device_info)
        
        try:
            none_count = 0
            while not self._stop_flag.is_set():
                # Get cleaned batch
                cleaned_batch = await self._cleaned_queue.get()
                
                # Check for completion signal
                if cleaned_batch is None:
                    none_count += 1
                    # Wait until ALL cleaners have sent their completion signals
                    if none_count >= self._config.num_cleaners:
                        # Now send completion signals to all writers
                        for _ in range(self._config.num_writers):
                            await self._embedded_queue.put(None)
                        break
                    # Continue consuming None signals from other cleaners
                    continue
                
                # Filter entries needing embeddings
                if self._config.skip_existing_embeddings:
                    entries_to_embed = [e for e in cleaned_batch if e.embedding is None]
                else:
                    entries_to_embed = cleaned_batch
                
                if not entries_to_embed:
                    await self._embedded_queue.put(cleaned_batch)
                    self._cleaned_queue.task_done()
                    continue
                
                # Compute embeddings in sub-batches (GPU memory management)
                embedded_entries = []
                
                for i in range(0, len(entries_to_embed), self._config.embedding_batch):
                    sub_batch = entries_to_embed[i:i + self._config.embedding_batch]
                    definitions = [e.definition for e in sub_batch]
                    
                    # Run in executor (blocking GPU operation)
                    loop = asyncio.get_event_loop()
                    embeddings = await loop.run_in_executor(
                        None,
                        self._embedding.batch_embed,
                        definitions,
                        False
                    )
                    
                    # Create new entries with embeddings (immutable)
                    for entry, embedding in zip(sub_batch, embeddings):
                        embedded_entry = Entry(
                            id=entry.id,
                            headword=entry.headword,
                            ipa=entry.ipa,
                            language=entry.language,
                            definition=entry.definition,
                            etymology=entry.etymology,
                            pos_tag=entry.pos_tag,
                            embedding=embedding.tolist(),
                            created_at=entry.created_at
                        )
                        embedded_entries.append(embedded_entry)
                    
                    self._stats.embedded += len(sub_batch)
                
                # Put embedded batch in next queue
                await self._embedded_queue.put(embedded_entries)
                self._cleaned_queue.task_done()
            
            logger.info("embedder_worker_completed", worker_id=worker_id)
            
        except Exception as e:
            logger.error("embedder_worker_failed", worker_id=worker_id, error=str(e))
            self._error = e
            self._stop_flag.set()
            raise
    
    async def _writer_worker(self, worker_id: int) -> None:
        """Stage 4: Bulk write to database."""
        logger.info("writer_worker_started", worker_id=worker_id)
        
        try:
            write_buffer = []
            
            while not self._stop_flag.is_set():
                # Get embedded batch
                embedded_batch = await self._embedded_queue.get()
                
                # Check for completion signal
                if embedded_batch is None:
                    # Flush remaining buffer
                    if write_buffer:
                        await self._flush_write_buffer(write_buffer)
                    break
                
                # Add to write buffer
                write_buffer.extend(embedded_batch)
                
                # Flush if buffer is large enough
                if len(write_buffer) >= self._config.db_write_batch:
                    await self._flush_write_buffer(write_buffer)
                    write_buffer = []
                
                self._embedded_queue.task_done()
            
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
        
        logger.info("flushing_write_buffer", entry_count=len(entries))
        
        try:
            # Assign concepts in batch
            logger.debug("batch_assigning_concepts", entry_count=len(entries))
            concept_assignments = self._concepts.batch_assign(entries)
            logger.debug("concepts_assigned", count=len(concept_assignments))
            
            # Bulk upsert
            logger.debug("bulk_upserting", entry_count=len(entries))
            written = await self._bulk_writer.bulk_upsert_entries(
                entries,
                concept_assignments
            )
            logger.info("bulk_upsert_complete", written=written)
            
            self._stats.written += written
            self._stats.succeeded += written
            
        except Exception as e:
            logger.error("write_flush_failed", count=len(entries), error=str(e))
            self._stats.failed += len(entries)
            raise
    
    async def _progress_monitor(self) -> None:
        """Monitor and report progress."""
        logger.info("progress_monitor_started")
        
        try:
            while not self._stop_flag.is_set():
                await asyncio.sleep(10)  # Update every 10 seconds
                
                # Update queue depths
                self._stats.raw_queue_depth = self._raw_queue.qsize()
                self._stats.cleaned_queue_depth = self._cleaned_queue.qsize()
                self._stats.embedded_queue_depth = self._embedded_queue.qsize()
                
                # Calculate progress
                percent = 100.0 * self._stats.processed / self._stats.total_entries if self._stats.total_entries > 0 else 0
                eta_seconds = self._stats.estimated_remaining_seconds
                eta_minutes = eta_seconds / 60
                
                # Print progress
                print(f"\r[{datetime.utcnow().strftime('%H:%M:%S')}] "
                      f"Progress: {percent:.1f}% | "
                      f"Processed: {self._stats.processed:,}/{self._stats.total_entries:,} | "
                      f"Rate: {self._stats.entries_per_second:.0f}/s | "
                      f"ETA: {eta_minutes:.1f}min | "
                      f"Queues: R{self._stats.raw_queue_depth} "
                      f"C{self._stats.cleaned_queue_depth} "
                      f"E{self._stats.embedded_queue_depth}",
                      end='', flush=True)
            
            logger.info("progress_monitor_completed")
            
        except Exception as e:
            logger.error("progress_monitor_failed", error=str(e))
    
    async def _count_entries(
        self,
        source_id: Optional[str],
        resume_from: Optional[str]
    ) -> int:
        """Count total entries to process."""
        async with self._pool.acquire() as conn:
            where_clauses = []
            params = []
            
            if source_id:
                where_clauses.append(f"source_id = ${len(params) + 1}")
                params.append(source_id)
            
            if resume_from:
                where_clauses.append(f"id > ${len(params) + 1}")
                params.append(resume_from)
            
            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            
            result = await conn.fetchval(
                f"SELECT COUNT(*) FROM raw_entries {where_sql}",
                *params
            )
            return result or 0
    
    def _meets_quality_threshold(self, entry: Entry) -> bool:
        """Check if entry meets minimum quality threshold."""
        # Require headword and definition (IPA is optional)
        if not entry.headword or not entry.definition:
            return False
        if len(entry.definition) < 5:  # Relaxed from 10 to 5
            return False
        return True
    
    def _generate_entry_id(self, data: dict) -> str:
        """Generate deterministic entry ID from data."""
        import hashlib
        content = f"{data.get('headword', '')}{data.get('language', '')}{data.get('definition', '')}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()
        return f"entry_{hash_val[:16]}"
    
    def _estimate_speedup(self) -> float:
        """Estimate speedup vs baseline (300 entries/sec)."""
        baseline = 300.0  # entries/sec
        return self._stats.entries_per_second / baseline if self._stats.entries_per_second > 0 else 1.0

