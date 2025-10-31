"""Repository implementations for data persistence.

Uses PostgreSQL with pgvector for embeddings and full-text search.
"""

from typing import Optional
import asyncpg
from backend.core import Entry, SimilarityScore, CognateSet
from backend.core.contracts import IRepository


class EntryRepository(IRepository):
    """Repository for lexical entries with vector search."""
    
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool
        
    async def get_by_id(self, id: str) -> Optional[Entry]:
        """Retrieve entry by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, headword, ipa, language, definition, 
                       etymology, pos_tag, embedding, created_at
                FROM entries
                WHERE id = $1
                """,
                id
            )
            return self._row_to_entry(row) if row else None
    
    async def save(self, entry: Entry) -> str:
        """Persist entry to database."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO entries (
                    id, headword, ipa, language, definition,
                    etymology, pos_tag, embedding, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO UPDATE SET
                    headword = EXCLUDED.headword,
                    ipa = EXCLUDED.ipa,
                    definition = EXCLUDED.definition,
                    etymology = EXCLUDED.etymology,
                    pos_tag = EXCLUDED.pos_tag,
                    embedding = EXCLUDED.embedding
                """,
                entry.id,
                entry.headword,
                entry.ipa,
                entry.language,
                entry.definition,
                entry.etymology,
                entry.pos_tag,
                entry.embedding,
                entry.created_at
            )
            return entry.id
    
    async def query(self, **filters) -> list[Entry]:
        """Query entries with filters."""
        conditions = []
        params = []
        
        if "language" in filters:
            conditions.append(f"language = ${len(params) + 1}")
            params.append(filters["language"])
            
        if "pos_tag" in filters:
            conditions.append(f"pos_tag = ${len(params) + 1}")
            params.append(filters["pos_tag"])
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, headword, ipa, language, definition,
                       etymology, pos_tag, embedding, created_at
                FROM entries
                {where_clause}
                """,
                *params
            )
            return [self._row_to_entry(row) for row in rows]
    
    async def similarity_search(
        self,
        embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7
    ) -> list[tuple[Entry, float]]:
        """Vector similarity search using pgvector."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, headword, ipa, language, definition,
                       etymology, pos_tag, embedding, created_at,
                       1 - (embedding <=> $1::vector) as similarity
                FROM entries
                WHERE 1 - (embedding <=> $1::vector) >= $2
                ORDER BY similarity DESC
                LIMIT $3
                """,
                embedding,
                threshold,
                limit
            )
            return [
                (self._row_to_entry(row), row["similarity"])
                for row in rows
            ]
    
    def _row_to_entry(self, row) -> Entry:
        """Convert database row to Entry model."""
        return Entry(
            id=row["id"],
            headword=row["headword"],
            ipa=row["ipa"],
            language=row["language"],
            definition=row["definition"],
            etymology=row["etymology"],
            pos_tag=row["pos_tag"],
            embedding=row["embedding"],
            created_at=row["created_at"]
        )


class CognateRepository(IRepository):
    """Repository for cognate sets."""
    
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool
        
    async def get_by_id(self, id: str) -> Optional[CognateSet]:
        """Retrieve cognate set by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, entries, confidence, proto_form, semantic_core
                FROM cognate_sets
                WHERE id = $1
                """,
                id
            )
            return self._row_to_cognate_set(row) if row else None
    
    async def save(self, cognate_set: CognateSet) -> str:
        """Persist cognate set."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cognate_sets (
                    id, entries, confidence, proto_form, semantic_core
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO UPDATE SET
                    entries = EXCLUDED.entries,
                    confidence = EXCLUDED.confidence,
                    proto_form = EXCLUDED.proto_form,
                    semantic_core = EXCLUDED.semantic_core
                """,
                cognate_set.id,
                cognate_set.entries,
                cognate_set.confidence,
                cognate_set.proto_form,
                cognate_set.semantic_core
            )
            return cognate_set.id
    
    async def query(self, **filters) -> list[CognateSet]:
        """Query cognate sets."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, entries, confidence, proto_form, semantic_core FROM cognate_sets"
            )
            return [self._row_to_cognate_set(row) for row in rows]
    
    def _row_to_cognate_set(self, row) -> CognateSet:
        """Convert database row to CognateSet model."""
        return CognateSet(
            id=row["id"],
            entries=row["entries"],
            confidence=row["confidence"],
            proto_form=row["proto_form"],
            semantic_core=row["semantic_core"]
        )

