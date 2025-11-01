"""Batch processing pipeline for large-scale entry processing.

Streams from raw entries, applies cleaning pipelines, computes embeddings,
assigns concepts, and stores in partitioned tables.

Designed for 6.7M+ entries with parallelization and progress tracking.
"""

import asyncio
import hashlib
from typing import AsyncIterator, Optional
from dataclasses import dataclass, field
from datetime import datetime
import asyncpg

from backend.core.types import Entry
from backend.storage.pipeline import Pipeline, PipelineFactory
from backend.storage.provenance import TransformStep
from backend.services.semantic import SemanticService
from backend.services.concepts import ConceptAligner
from backend.services.phylogeny import PhylogeneticTree


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    
    batch_size: int = 1000  # Process in batches of 1000
    max_workers: int = 9  # One per IE branch
    quality_threshold: float = 0.5  # Minimum quality to process
    checkpoint_interval: int = 10000  # Save progress every N entries
    partition_by_branch: bool = True  # Partition by language branch
    recompute_embeddings: bool = False  # Force recompute existing embeddings


@dataclass
class BatchProgress:
    """Tracks processing progress."""
    
    total_entries: int = 0
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_checkpoint: datetime = field(default_factory=datetime.utcnow)
    branch_progress: dict[str, int] = field(default_factory=dict)
    
    @property
    def percent_complete(self) -> float:
        """Completion percentage."""
        if self.total_entries == 0:
            return 0.0
        return 100.0 * self.processed / self.total_entries
    
    @property
    def elapsed_seconds(self) -> float:
        """Time elapsed since start."""
        return (datetime.utcnow() - self.start_time).total_seconds()
    
    @property
    def entries_per_second(self) -> float:
        """Processing rate."""
        if self.elapsed_seconds == 0:
            return 0.0
        return self.processed / self.elapsed_seconds
    
    @property
    def estimated_remaining_seconds(self) -> float:
        """Estimated time to completion."""
        if self.entries_per_second == 0:
            return float('inf')
        remaining = self.total_entries - self.processed
        return remaining / self.entries_per_second


@dataclass
class BatchProcessor:
    """Processes entries in parallel batches with progress tracking.
    
    Pipeline:
    1. Stream from raw_entries (by branch if partitioned)
    2. Apply cleaning pipelines
    3. Filter by quality
    4. Compute embeddings (batched)
    5. Assign concepts
    6. Store in entries table
    7. Update provenance
    """
    
    pool: asyncpg.Pool
    semantic: SemanticService
    concepts: ConceptAligner
    phylogeny: PhylogeneticTree
    config: BatchConfig = field(default_factory=BatchConfig)
    
    async def process_all(
        self,
        source_id: Optional[str] = None,
        resume_from: Optional[str] = None
    ) -> BatchProgress:
        """Process all entries from raw storage.
        
        Args:
            source_id: Filter by specific source (None = all sources)
            resume_from: Resume from checkpoint (entry ID)
            
        Returns:
            BatchProgress with final statistics
        """
        
        progress = BatchProgress()
        
        # Count total entries
        progress.total_entries = await self._count_entries(source_id, resume_from)
        
        print(f"Starting batch processing of {progress.total_entries} entries...")
        print(f"Config: {self.config}")
        
        if self.config.partition_by_branch:
            # Process by language branch in parallel
            await self._process_by_branch(source_id, resume_from, progress)
        else:
            # Process all entries sequentially
            await self._process_sequential(source_id, resume_from, progress)
        
        # Final report
        print(f"\n{'='*60}")
        print(f"Batch processing complete!")
        print(f"Total: {progress.total_entries}")
        print(f"Succeeded: {progress.succeeded}")
        print(f"Failed: {progress.failed}")
        print(f"Skipped: {progress.skipped}")
        print(f"Time: {progress.elapsed_seconds:.1f}s")
        print(f"Rate: {progress.entries_per_second:.1f} entries/sec")
        print(f"{'='*60}\n")
        
        return progress
    
    async def _process_by_branch(
        self,
        source_id: Optional[str],
        resume_from: Optional[str],
        progress: BatchProgress
    ):
        """Process entries partitioned by language branch in parallel."""
        
        # Get IE branches
        branches = [
            "indo_iranian", "hellenic", "italic", "germanic", "celtic",
            "balto_slavic", "armenian", "albanian", "anatolian", "tocharian"
        ]
        
        # Create worker tasks
        tasks = []
        for branch in branches:
            task = asyncio.create_task(
                self._process_branch(branch, source_id, resume_from, progress)
            )
            tasks.append(task)
        
        # Wait for all branches to complete
        await asyncio.gather(*tasks)
    
    async def _process_branch(
        self,
        branch: str,
        source_id: Optional[str],
        resume_from: Optional[str],
        progress: BatchProgress
    ):
        """Process entries for a specific language branch."""
        
        print(f"[{branch}] Starting branch processing...")
        
        # Stream entries for this branch
        async for batch in self._stream_entries_by_branch(
            branch, source_id, resume_from
        ):
            # Process batch
            results = await self._process_batch(batch, progress)
            
            # Update progress
            progress.branch_progress[branch] = progress.branch_progress.get(branch, 0) + len(batch)
            
            # Checkpoint if needed
            if progress.processed % self.config.checkpoint_interval == 0:
                await self._save_checkpoint(progress)
                self._print_progress(progress)
    
    async def _process_sequential(
        self,
        source_id: Optional[str],
        resume_from: Optional[str],
        progress: BatchProgress
    ):
        """Process all entries sequentially."""
        
        async for batch in self._stream_entries(source_id, resume_from):
            await self._process_batch(batch, progress)
            
            if progress.processed % self.config.checkpoint_interval == 0:
                await self._save_checkpoint(progress)
                self._print_progress(progress)
    
    async def _process_batch(
        self,
        raw_entries: list[dict],
        progress: BatchProgress
    ) -> list[Entry]:
        """Process a batch of raw entries.
        
        1. Clean and validate
        2. Filter by quality
        3. Compute embeddings (batched)
        4. Assign concepts
        5. Store
        """
        
        pipelines = PipelineFactory.full_entry_pipeline()
        processed_entries = []
        
        for raw in raw_entries:
            try:
                # Apply cleaning pipelines
                cleaned_data = {}
                provenance_steps = []
                
                for field, pipeline in pipelines.items():
                    if field in raw:
                        cleaned, steps = pipeline.apply(raw[field])
                        cleaned_data[field] = cleaned
                        if steps:
                            provenance_steps.extend(steps)
                
                # Create entry
                entry = Entry(
                    id=self._generate_entry_id(cleaned_data),
                    headword=cleaned_data.get('headword', ''),
                    ipa=cleaned_data.get('ipa', ''),
                    language=cleaned_data.get('language', ''),
                    definition=cleaned_data.get('definition', ''),
                    etymology=raw.get('etymology'),
                    pos_tag=raw.get('pos_tag')
                )
                
                # Quality check
                if not self._meets_quality_threshold(entry):
                    progress.skipped += 1
                    continue
                
                processed_entries.append(entry)
                progress.succeeded += 1
                
            except Exception as e:
                print(f"Error processing entry: {e}")
                progress.failed += 1
            
            progress.processed += 1
        
        # Batch operations for efficiency
        if processed_entries:
            # Compute embeddings in batch
            if not self.config.recompute_embeddings:
                entries_needing_embeddings = [
                    e for e in processed_entries if e.embedding is None
                ]
            else:
                entries_needing_embeddings = processed_entries
            
            if entries_needing_embeddings:
                definitions = [e.definition for e in entries_needing_embeddings]
                embeddings = self.semantic.batch_embed(definitions)
                
                # Update entries with embeddings
                for i, entry in enumerate(entries_needing_embeddings):
                    # Create new entry with embedding (immutable)
                    processed_entries[i] = Entry(
                        **{**entry.dict(), 'embedding': embeddings[i].tolist()}
                    )
            
            # Assign concepts in batch
            concept_assignments = self.concepts.batch_assign(processed_entries)
            
            # Store entries
            await self._store_batch(processed_entries, concept_assignments)
        
        return processed_entries
    
    async def _stream_entries(
        self,
        source_id: Optional[str],
        resume_from: Optional[str]
    ) -> AsyncIterator[list[dict]]:
        """Stream raw entries in batches."""
        
        async with self.pool.acquire() as conn:
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
            
            # Stream in batches
            async with conn.transaction():
                cursor = await conn.cursor(
                    f"""
                    SELECT id, raw_data, source_id
                    FROM raw_entries
                    {where_sql}
                    ORDER BY id
                    """,
                    *params
                )
                
                batch = []
                async for row in cursor:
                    batch.append(dict(row['raw_data']))
                    
                    if len(batch) >= self.config.batch_size:
                        yield batch
                        batch = []
                
                if batch:
                    yield batch
    
    async def _stream_entries_by_branch(
        self,
        branch: str,
        source_id: Optional[str],
        resume_from: Optional[str]
    ) -> AsyncIterator[list[dict]]:
        """Stream entries filtered by language branch."""
        
        # Get languages in this branch
        branch_languages = self._get_branch_languages(branch)
        
        if not branch_languages:
            return
            yield  # Make this a generator
        
        async with self.pool.acquire() as conn:
            # Build query with language filter
            where_clauses = [
                f"raw_data->>'language' = ANY(${1})"
            ]
            params = [branch_languages]
            
            if source_id:
                where_clauses.append(f"source_id = ${len(params) + 1}")
                params.append(source_id)
            
            if resume_from:
                where_clauses.append(f"id > ${len(params) + 1}")
                params.append(resume_from)
            
            where_sql = f"WHERE {' AND '.join(where_clauses)}"
            
            # Stream
            async with conn.transaction():
                cursor = await conn.cursor(
                    f"""
                    SELECT id, raw_data, source_id
                    FROM raw_entries
                    {where_sql}
                    ORDER BY id
                    """,
                    *params
                )
                
                batch = []
                async for row in cursor:
                    batch.append(dict(row['raw_data']))
                    
                    if len(batch) >= self.config.batch_size:
                        yield batch
                        batch = []
                
                if batch:
                    yield batch
    
    async def _store_batch(
        self,
        entries: list[Entry],
        concept_assignments: list[tuple]
    ):
        """Store batch of entries in database."""
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for entry, (concept, _) in zip(entries, concept_assignments):
                    await conn.execute(
                        """
                        INSERT INTO entries (
                            id, headword, ipa, language, definition,
                            etymology, pos_tag, embedding, concept_id, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (id) DO UPDATE SET
                            embedding = EXCLUDED.embedding,
                            concept_id = EXCLUDED.concept_id
                        """,
                        entry.id,
                        entry.headword,
                        entry.ipa,
                        entry.language,
                        entry.definition,
                        entry.etymology,
                        entry.pos_tag,
                        entry.embedding,
                        concept.id,
                        entry.created_at
                    )
    
    def _get_branch_languages(self, branch: str) -> list[str]:
        """Get all language codes for a branch."""
        
        # Recursively collect languages from branch and sub-branches
        languages = []
        
        def collect_languages(node_id: str):
            node = self.phylogeny.nodes.get(node_id)
            if not node:
                return
            
            languages.extend(node.languages)
            for child_id in node.children:
                collect_languages(child_id)
        
        collect_languages(branch)
        return languages
    
    async def _count_entries(
        self,
        source_id: Optional[str],
        resume_from: Optional[str]
    ) -> int:
        """Count total entries to process."""
        
        async with self.pool.acquire() as conn:
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
        
        # Basic checks
        if not entry.headword or not entry.ipa or not entry.definition:
            return False
        
        if len(entry.definition) < 10:
            return False
        
        return True
    
    def _generate_entry_id(self, data: dict) -> str:
        """Generate deterministic entry ID from data."""
        
        # Hash headword + language + definition
        content = f"{data.get('headword', '')}{data.get('language', '')}{data.get('definition', '')}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()
        return f"entry_{hash_val[:16]}"
    
    async def _save_checkpoint(self, progress: BatchProgress):
        """Save processing checkpoint."""
        
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO batch_checkpoints (
                    timestamp, total, processed, succeeded, failed, skipped
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                datetime.utcnow(),
                progress.total_entries,
                progress.processed,
                progress.succeeded,
                progress.failed,
                progress.skipped
            )
    
    def _print_progress(self, progress: BatchProgress):
        """Print progress update."""
        
        print(f"\n[Progress] {progress.percent_complete:.1f}% complete")
        print(f"  Processed: {progress.processed}/{progress.total_entries}")
        print(f"  Succeeded: {progress.succeeded}")
        print(f"  Failed: {progress.failed}")
        print(f"  Skipped: {progress.skipped}")
        print(f"  Rate: {progress.entries_per_second:.1f} entries/sec")
        print(f"  ETA: {progress.estimated_remaining_seconds/60:.1f} min")
        
        if progress.branch_progress:
            print(f"  Branch progress:")
            for branch, count in progress.branch_progress.items():
                print(f"    {branch}: {count}")

