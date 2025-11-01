"""Data ingestion orchestration.

ELT-V pipeline: Extract, Load, Transform, Validate
"""

import tomli
from pathlib import Path
from typing import Optional
from datetime import datetime
import asyncpg
from backend.storage.provenance import Source, SourceType, DataQuality, Provenance
from backend.storage.loaders import LoaderFactory, RawEntry
from backend.storage.pipeline import PipelineFactory
from backend.core.types import Entry


class IngestService:
    """Orchestrates the complete data ingestion pipeline."""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self._pool = db_pool
        self._pipelines = PipelineFactory.full_entry_pipeline()
    
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
        """Ingest a data file through the complete pipeline.
        
        Returns statistics about the ingestion.
        """
        stats = {
            'raw_loaded': 0,
            'transformed': 0,
            'validation_errors': 0,
            'duplicates_skipped': 0,
            'saved': 0,
        }
        
        # 1. EXTRACT: Load raw data
        loader = LoaderFactory.get_loader(format)
        raw_entries = list(loader.load(file_path, source_id))
        stats['raw_loaded'] = len(raw_entries)
        
        if dry_run:
            return stats
        
        # 2. LOAD: Store raw entries (immutable)
        raw_ids = await self._store_raw_entries(raw_entries)
        
        # 3. TRANSFORM: Apply cleaning pipelines
        cleaned_entries = []
        for raw_entry, raw_id in zip(raw_entries, raw_ids):
            try:
                cleaned = await self._transform_entry(raw_entry, raw_id)
                cleaned_entries.append(cleaned)
                stats['transformed'] += 1
            except ValueError as e:
                stats['validation_errors'] += 1
                await self._log_transform_error(raw_id, str(e))
        
        # 4. VALIDATE: Check for duplicates and quality
        unique_entries = await self._deduplicate(cleaned_entries)
        stats['duplicates_skipped'] = len(cleaned_entries) - len(unique_entries)
        
        # 5. SAVE: Persist to main tables
        for entry in unique_entries:
            try:
                await self._save_entry(entry)
                stats['saved'] += 1
            except Exception as e:
                print(f"Error saving entry {entry.id}: {e}")
        
        return stats
    
    async def _store_raw_entries(self, entries: list[RawEntry]) -> list[int]:
        """Store raw entries and return their IDs."""
        ids = []
        
        async with self._pool.acquire() as conn:
            for entry in entries:
                # Check if already exists
                existing = await conn.fetchval(
                    "SELECT id FROM raw_entries WHERE checksum = $1",
                    entry.checksum
                )
                
                if existing:
                    ids.append(existing)
                    continue
                
                # Insert new
                raw_id = await conn.fetchval(
                    """
                    INSERT INTO raw_entries (
                        source_id, raw_data, checksum, file_path, line_number
                    ) VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    entry.source_id,
                    entry.data,
                    entry.checksum,
                    entry.file_path,
                    entry.line_number
                )
                ids.append(raw_id)
        
        return ids
    
    async def _transform_entry(
        self,
        raw: RawEntry,
        raw_id: int
    ) -> tuple[Entry, str]:
        """Apply cleaning pipelines to raw entry."""
        data = raw.data.copy()
        pipeline_version_parts = []
        
        # Apply field-specific pipelines
        for field, pipeline in self._pipelines.items():
            if field in data and data[field]:
                try:
                    cleaned, steps = pipeline.apply(data[field])
                    data[field] = cleaned
                    
                    # Log transformations
                    async with self._pool.acquire() as conn:
                        for step in steps:
                            await conn.execute(
                                """
                                INSERT INTO transform_log (
                                    raw_entry_id, step_name, step_version,
                                    parameters, executed_at, duration_ms, success
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                                """,
                                raw_id,
                                step.name,
                                step.version,
                                step.parameters,
                                step.executed_at,
                                step.duration_ms,
                                True
                            )
                    
                    pipeline_version_parts.append(pipeline.signature)
                
                except Exception as e:
                    raise ValueError(f"Failed to clean {field}: {e}")
        
        # Create Entry
        entry = Entry(
            id=f"{raw.source_id}_{raw.checksum[:16]}",
            headword=data.get('headword', ''),
            ipa=data.get('ipa', ''),
            language=data.get('language', ''),
            definition=data.get('definition', ''),
            etymology=data.get('etymology'),
            pos_tag=data.get('pos_tag'),
            embedding=None,  # Generated later
            created_at=datetime.utcnow()
        )
        
        pipeline_version = "_".join(pipeline_version_parts)
        return entry, pipeline_version, raw_id
    
    async def _deduplicate(
        self,
        entries: list[tuple[Entry, str, int]]
    ) -> list[tuple[Entry, str, int]]:
        """Remove duplicates based on headword + language."""
        seen = {}
        unique = []
        
        for entry_data in entries:
            entry = entry_data[0]
            key = (entry.headword, entry.language)
            
            if key not in seen:
                seen[key] = entry_data
                unique.append(entry_data)
        
        return unique
    
    async def _save_entry(self, entry_data: tuple[Entry, str, int]) -> None:
        """Save cleaned entry to database."""
        entry, pipeline_version, raw_id = entry_data
        
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO entries (
                    id, headword, ipa, language, definition,
                    etymology, pos_tag, embedding, created_at,
                    raw_entry_id, pipeline_version
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id) DO UPDATE SET
                    headword = EXCLUDED.headword,
                    ipa = EXCLUDED.ipa,
                    definition = EXCLUDED.definition,
                    etymology = EXCLUDED.etymology,
                    pos_tag = EXCLUDED.pos_tag,
                    updated_at = CURRENT_TIMESTAMP
                """,
                entry.id,
                entry.headword,
                entry.ipa,
                entry.language,
                entry.definition,
                entry.etymology,
                entry.pos_tag,
                entry.embedding,
                entry.created_at,
                raw_id,
                pipeline_version
            )
    
    async def _log_transform_error(self, raw_id: int, error: str) -> None:
        """Log transformation error."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO transform_log (
                    raw_entry_id, step_name, step_version,
                    executed_at, success, error_message
                ) VALUES ($1, 'pipeline', '1.0.0', $2, $3, $4)
                """,
                raw_id,
                datetime.utcnow(),
                False,
                error
            )
    
    async def reprocess_with_pipeline(
        self,
        source_id: Optional[str] = None,
        new_pipeline_version: Optional[str] = None
    ) -> dict[str, int]:
        """Reprocess raw entries with updated pipeline.
        
        This is the power of the ELT-V approach - can reprocess
        without re-downloading source data.
        """
        stats = {'reprocessed': 0, 'errors': 0}
        
        async with self._pool.acquire() as conn:
            # Fetch raw entries
            query = "SELECT id, source_id, raw_data, checksum FROM raw_entries"
            if source_id:
                query += f" WHERE source_id = '{source_id}'"
            
            rows = await conn.fetch(query)
            
            for row in rows:
                raw_entry = RawEntry(
                    source_id=row['source_id'],
                    data=row['raw_data'],
                    checksum=row['checksum']
                )
                
                try:
                    cleaned = await self._transform_entry(raw_entry, row['id'])
                    await self._save_entry(cleaned)
                    stats['reprocessed'] += 1
                except Exception as e:
                    stats['errors'] += 1
                    print(f"Error reprocessing {row['id']}: {e}")
        
        return stats

