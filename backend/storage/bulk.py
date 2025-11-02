"""Bulk database operations using PostgreSQL COPY protocol.

COPY is 100-1000x faster than individual INSERTs because:
1. Single round-trip to database
2. Binary protocol (no parsing overhead)
3. No transaction overhead per row
4. Bypasses WAL for unlogged tables (optional)
5. Parallel loading possible

Optimization Theory:
- Reduces O(N) round trips to O(1)
- Amortizes connection overhead across all rows
- Leverages PostgreSQL's internal bulk loading optimizations
"""

import asyncio
import asyncpg
import io
import csv
from typing import Sequence, Optional
from dataclasses import asdict
from datetime import datetime

from backend.core.types import Entry
from backend.observ import get_logger

logger = get_logger(__name__)


class BulkWriter:
    """High-performance bulk database writer using COPY protocol."""
    
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool
    
    async def bulk_insert_entries(
        self,
        entries: Sequence[Entry],
        concept_assignments: Optional[Sequence[tuple]] = None,
        chunk_size: int = 10000
    ) -> int:
        """Bulk insert entries using COPY protocol.
        
        Args:
            entries: Sequence of Entry objects
            concept_assignments: Optional concept assignments (concept, confidence)
            chunk_size: Number of rows per COPY operation
            
        Returns:
            Number of rows inserted
        """
        if not entries:
            return 0
        
        start_time = datetime.utcnow()
        total_inserted = 0
        
        # Process in chunks to avoid memory issues
        for i in range(0, len(entries), chunk_size):
            chunk = entries[i:i + chunk_size]
            concept_chunk = (
                concept_assignments[i:i + chunk_size]
                if concept_assignments
                else None
            )
            
            inserted = await self._copy_entries_chunk(chunk, concept_chunk)
            total_inserted += inserted
            
            if (i // chunk_size) % 10 == 0:
                logger.info(
                    "bulk_insert_progress",
                    inserted=total_inserted,
                    total=len(entries),
                    percent=100.0 * total_inserted / len(entries)
                )
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        rate = total_inserted / duration if duration > 0 else 0
        
        logger.info(
            "bulk_insert_completed",
            total_inserted=total_inserted,
            duration_seconds=duration,
            rate_per_second=rate
        )
        
        return total_inserted
    
    async def _copy_entries_chunk(
        self,
        entries: Sequence[Entry],
        concept_assignments: Optional[Sequence[tuple]] = None
    ) -> int:
        """Copy a chunk of entries using COPY protocol."""
        
        # Prepare data in CSV format (PostgreSQL COPY format)
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
        
        for idx, entry in enumerate(entries):
            concept_id = None
            data_quality = 1.0
            
            if concept_assignments and idx < len(concept_assignments):
                concept, confidence = concept_assignments[idx]
                concept_id = concept.id if concept else None
                data_quality = confidence if confidence else 1.0
            
            # Format: id, headword, ipa, language, definition, etymology, pos_tag, 
            #         embedding, concept_id, data_quality, created_at
            writer.writerow([
                entry.id,
                entry.headword or '',
                entry.ipa or '',
                entry.language or '',
                entry.definition or '',
                entry.etymology or '',
                entry.pos_tag or '',
                _format_array(entry.embedding) if entry.embedding else None,
                concept_id or '',
                data_quality,
                entry.created_at or datetime.utcnow()
            ])
        
        # Execute COPY
        buffer.seek(0)
        
        async with self._pool.acquire() as conn:
            # Use COPY for bulk insert
            result = await conn.copy_to_table(
                'entries',
                source=buffer,
                columns=[
                    'id', 'headword', 'ipa', 'language', 'definition',
                    'etymology', 'pos_tag', 'embedding', 'concept_id',
                    'data_quality', 'created_at'
                ],
                format='csv',
                delimiter='\t'
            )
        
        return len(entries)
    
    async def bulk_upsert_entries(
        self,
        entries: Sequence[Entry],
        concept_assignments: Optional[Sequence[tuple]] = None
    ) -> int:
        """Bulk upsert entries (insert or update on conflict).
        
        Uses temporary table + INSERT ... ON CONFLICT pattern
        which is faster than individual upserts.
        """
        if not entries:
            return 0
        
        start_time = datetime.utcnow()
        
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Create temporary table
                await conn.execute("""
                    CREATE TEMPORARY TABLE entries_temp (
                        id VARCHAR(255),
                        headword VARCHAR(255),
                        ipa VARCHAR(255),
                        language VARCHAR(3),
                        definition TEXT,
                        etymology TEXT,
                        pos_tag VARCHAR(50),
                        embedding vector(768),
                        concept_id VARCHAR(255),
                        data_quality FLOAT,
                        created_at TIMESTAMP
                    ) ON COMMIT DROP
                """)
                
                # Bulk load into temp table using COPY
                buffer = io.StringIO()
                writer = csv.writer(buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
                
                for idx, entry in enumerate(entries):
                    concept_id = None
                    data_quality = 1.0
                    
                    if concept_assignments and idx < len(concept_assignments):
                        concept, confidence = concept_assignments[idx]
                        concept_id = concept.id if concept else None
                        data_quality = confidence if confidence else 1.0
                    
                    writer.writerow([
                        entry.id,
                        entry.headword or '',
                        entry.ipa or '',
                        entry.language or '',
                        entry.definition or '',
                        entry.etymology or '',
                        entry.pos_tag or '',
                        _format_array(entry.embedding) if entry.embedding else None,
                        concept_id or '',
                        data_quality,
                        entry.created_at or datetime.utcnow()
                    ])
                
                buffer.seek(0)
                
                await conn.copy_to_table(
                    'entries_temp',
                    source=buffer,
                    columns=[
                        'id', 'headword', 'ipa', 'language', 'definition',
                        'etymology', 'pos_tag', 'embedding', 'concept_id',
                        'data_quality', 'created_at'
                    ],
                    format='csv',
                    delimiter='\t'
                )
                
                # Upsert from temp table to main table
                result = await conn.execute("""
                    INSERT INTO entries (
                        id, headword, ipa, language, definition, etymology,
                        pos_tag, embedding, concept_id, data_quality, created_at
                    )
                    SELECT
                        id, headword, ipa, language, definition, etymology,
                        pos_tag, embedding::vector(768), concept_id, data_quality, created_at
                    FROM entries_temp
                    ON CONFLICT (id) DO UPDATE SET
                        headword = EXCLUDED.headword,
                        ipa = EXCLUDED.ipa,
                        definition = EXCLUDED.definition,
                        etymology = EXCLUDED.etymology,
                        pos_tag = EXCLUDED.pos_tag,
                        embedding = EXCLUDED.embedding,
                        concept_id = EXCLUDED.concept_id,
                        data_quality = EXCLUDED.data_quality,
                        updated_at = CURRENT_TIMESTAMP
                """)
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        rate = len(entries) / duration if duration > 0 else 0
        
        logger.info(
            "bulk_upsert_completed",
            total_upserted=len(entries),
            duration_seconds=duration,
            rate_per_second=rate
        )
        
        return len(entries)
    
    async def bulk_update_embeddings(
        self,
        entry_ids: Sequence[str],
        embeddings: Sequence[list[float]]
    ) -> int:
        """Bulk update embeddings for existing entries.
        
        Optimized for updating only embeddings without touching other fields.
        """
        if not entry_ids or not embeddings or len(entry_ids) != len(embeddings):
            return 0
        
        # Use unnest for bulk update
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE entries
                SET embedding = data.embedding::vector(768),
                    updated_at = CURRENT_TIMESTAMP
                FROM (
                    SELECT
                        unnest($1::text[]) AS id,
                        unnest($2::vector(768)[]) AS embedding
                ) AS data
                WHERE entries.id = data.id
                """,
                entry_ids,
                [_format_array(emb) for emb in embeddings]
            )
        
        # Parse result: "UPDATE N"
        count = int(result.split()[-1]) if result else 0
        
        logger.info("bulk_update_embeddings_completed", count=count)
        return count


def _format_array(arr: Sequence[float]) -> str:
    """Format array for PostgreSQL vector type."""
    if not arr:
        return None
    return '[' + ','.join(str(x) for x in arr) + ']'


class BulkDeleter:
    """High-performance bulk deletion operations."""
    
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool
    
    async def bulk_delete_by_ids(
        self,
        table: str,
        ids: Sequence[str]
    ) -> int:
        """Bulk delete rows by ID."""
        if not ids:
            return 0
        
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {table} WHERE id = ANY($1)",
                ids
            )
        
        count = int(result.split()[-1]) if result else 0
        logger.info("bulk_delete_completed", table=table, count=count)
        return count
    
    async def bulk_delete_by_source(
        self,
        table: str,
        source_id: str
    ) -> int:
        """Bulk delete rows by source ID."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {table} WHERE source_id = $1",
                source_id
            )
        
        count = int(result.split()[-1]) if result else 0
        logger.info("bulk_delete_by_source_completed", table=table, source=source_id, count=count)
        return count

