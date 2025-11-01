"""Unified data processing CLI - integrates all systems."""

import asyncio
import click
import asyncpg
from pathlib import Path

from backend.interop.perl_client import PerlParserClient
from backend.services.semantic import SemanticService
from backend.services.phonetic import PhoneticService
from backend.services.phylogeny import PhylogeneticTree
from backend.services.concepts import ConceptAligner
from backend.services.unified import UnifiedSimilarityService
from backend.storage.batch import BatchProcessor, BatchConfig
from backend.storage.loaders import RawEntry
from backend.storage.repositories import EntryRepository
import hashlib
import json
from datetime import datetime


async def get_pool():
    """Create database connection pool."""
    return await asyncpg.create_pool(
        host='localhost',
        database='langviz',
        user='postgres',
        password='postgres',
        min_size=5,
        max_size=20
    )


@click.group()
def cli():
    """LangViz Data Processing Pipeline"""
    pass


@cli.command()
@click.argument('source_dir', type=click.Path(exists=True))
@click.option('--source-id', default='kaikki', help='Data source identifier')
@click.option('--format', default='jsonl', help='File format')
@click.option('--use-perl', is_flag=True, help='Use Perl parser for complex formats')
def ingest_raw(source_dir, source_id, format, use_perl):
    """Ingest raw dictionary files into raw_entries table."""
    
    async def _ingest():
        pool = await get_pool()
        source_path = Path(source_dir)
        
        # Register data source
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO data_sources (id, name, source_type, format, url, quality, version, retrieved_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (id) DO NOTHING
                """,
                source_id,
                f"{source_id} dataset",
                "full_dictionary",
                format,
                str(source_path),
                "high",
                "1.0",
                datetime.utcnow()
            )
        
        click.echo(f"Ingesting from {source_path}...")
        
        if use_perl:
            # Use Perl parser
            with PerlParserClient() as perl:
                for file_path in source_path.glob('*.txt'):
                    click.echo(f"  Parsing {file_path.name} with Perl...")
                    entries = perl.parse_starling_dictionary(str(file_path))
                    await _store_raw_entries(pool, entries, source_id, str(file_path))
        else:
            # Use Python loaders
            for file_path in source_path.glob(f'*.{format}'):
                click.echo(f"  Loading {file_path.name}...")
                entries = await _load_jsonl(file_path)
                await _store_raw_entries(pool, entries, source_id, str(file_path))
        
        click.echo("Ingestion complete!")
        await pool.close()
    
    asyncio.run(_ingest())


@cli.command()
@click.option('--batch-size', default=1000, help='Entries per batch')
@click.option('--workers', default=9, help='Parallel workers')
@click.option('--source-id', default=None, help='Process specific source')
@click.option('--discover-concepts', is_flag=True, help='Run concept discovery first')
def process_pipeline(batch_size, workers, source_id, discover_concepts):
    """Run full processing pipeline: clean → embed → cluster → index."""
    
    async def _process():
        pool = await get_pool()
        
        click.echo("Initializing services...")
        semantic = SemanticService()
        phonetic = PhoneticService()
        phylogeny = PhylogeneticTree()
        concepts = ConceptAligner(semantic_service=semantic)
        
        # Step 1: Discover concepts if requested
        if discover_concepts:
            click.echo("\n[1/4] Discovering semantic concepts...")
            await _discover_concepts_internal(pool, semantic, concepts, source_id)
        
        # Step 2: Batch process entries
        click.echo("\n[2/4] Processing entries in batches...")
        config = BatchConfig(
            batch_size=batch_size,
            max_workers=workers,
            partition_by_branch=True
        )
        
        processor = BatchProcessor(
            pool=pool,
            semantic=semantic,
            concepts=concepts,
            phylogeny=phylogeny,
            config=config
        )
        
        await processor.process_all(source_id=source_id)
        
        # Step 3: Compute pairwise similarities (sample)
        click.echo("\n[3/4] Computing similarity matrix (sample)...")
        await _compute_similarities_sample(pool, semantic, phonetic, phylogeny, concepts)
        
        # Step 4: Build indexes
        click.echo("\n[4/4] Refreshing materialized views...")
        async with pool.acquire() as conn:
            await conn.execute("REFRESH MATERIALIZED VIEW data_quality_summary")
            await conn.execute("REFRESH MATERIALIZED VIEW concept_statistics")
        
        click.echo("\n✓ Pipeline complete!")
        await pool.close()
    
    asyncio.run(_process())


@cli.command()
@click.argument('concept')
@click.argument('lang-a')
@click.argument('lang-b')
def query(concept, lang_a, lang_b):
    """Query lexical difference (e.g., 'tak' vs 'da')."""
    
    async def _query():
        pool = await get_pool()
        
        semantic = SemanticService()
        phonetic = PhoneticService()
        phylogeny = PhylogeneticTree()
        concepts = ConceptAligner(semantic_service=semantic)
        
        unified = UnifiedSimilarityService(
            semantic=semantic,
            phonetic=phonetic,
            phylogeny=phylogeny,
            concepts=concepts
        )
        
        # Find entries
        async with pool.acquire() as conn:
            # Get concept
            concept_row = await conn.fetchrow(
                "SELECT id FROM concepts WHERE label ILIKE $1 LIMIT 1",
                f"%{concept}%"
            )
            
            if not concept_row:
                click.echo(f"Concept '{concept}' not found")
                return
            
            concept_id = concept_row['id']
            
            # Get entries
            entries_a = await conn.fetch(
                "SELECT * FROM entries WHERE concept_id = $1 AND language = $2 LIMIT 5",
                concept_id, lang_a
            )
            entries_b = await conn.fetch(
                "SELECT * FROM entries WHERE concept_id = $1 AND language = $2 LIMIT 5",
                concept_id, lang_b
            )
            all_entries = await conn.fetch(
                "SELECT * FROM entries WHERE concept_id = $1 LIMIT 200",
                concept_id
            )
        
        if not entries_a or not entries_b:
            click.echo("Entries not found for one or both languages")
            return
        
        # Convert to Entry objects
        from backend.core.types import Entry
        ea = [_row_to_entry(r) for r in entries_a]
        eb = [_row_to_entry(r) for r in entries_b]
        all_e = [_row_to_entry(r) for r in all_entries]
        
        # Analyze
        diff = unified.explain_difference(
            concept=concept_id,
            lang_a=lang_a,
            lang_b=lang_b,
            entries_a=ea,
            entries_b=eb,
            all_entries=all_e
        )
        
        # Display
        click.echo(f"\n{'='*70}")
        click.echo(f"  {lang_a.upper()}: '{diff.form_a}'  vs  {lang_b.upper()}: '{diff.form_b}'")
        click.echo(f"{'='*70}")
        click.echo(f"\n{diff.explanation}\n")
        click.echo(f"Cognate sets:")
        click.echo(f"  {diff.form_a}: {list(diff.cognates_a.items())[:3]}")
        click.echo(f"  {diff.form_b}: {list(diff.cognates_b.items())[:3]}")
        click.echo(f"{'='*70}\n")
        
        await pool.close()
    
    asyncio.run(_query())


async def _load_jsonl(file_path: Path) -> list[dict]:
    """Load JSONL file."""
    entries = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    return entries


async def _store_raw_entries(pool, entries: list[dict], source_id: str, file_path: str):
    """Store raw entries in database."""
    async with pool.acquire() as conn:
        for i, entry in enumerate(entries):
            checksum = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
            
            await conn.execute(
                """
                INSERT INTO raw_entries (source_id, raw_data, checksum, file_path, line_number)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (checksum) DO NOTHING
                """,
                source_id,
                json.dumps(entry),
                checksum,
                file_path,
                i + 1
            )


async def _discover_concepts_internal(pool, semantic, concepts, source_id):
    """Discover concepts from existing entries."""
    async with pool.acquire() as conn:
        query = "SELECT * FROM entries WHERE embedding IS NOT NULL"
        if source_id:
            query += f" AND source_id = '{source_id}'"
        query += " LIMIT 10000"
        
        rows = await conn.fetch(query)
        
        if not rows:
            click.echo("  No entries with embeddings found. Run batch processing first.")
            return
        
        entries = [_row_to_entry(r) for r in rows]
        click.echo(f"  Clustering {len(entries)} entries...")
        
        discovered = concepts.discover_concepts(entries)
        click.echo(f"  Found {len(discovered)} concepts")
        
        # Store
        for concept in discovered:
            await conn.execute(
                """
                INSERT INTO concepts (id, label, centroid, size, languages, sample_definitions, confidence)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (id) DO UPDATE SET
                    centroid = EXCLUDED.centroid,
                    size = EXCLUDED.size,
                    confidence = EXCLUDED.confidence
                """,
                concept.id,
                _generate_label(concept),
                concept.centroid,
                concept.size,
                concept.languages,
                concept.sample_definitions,
                concept.confidence
            )


async def _compute_similarities_sample(pool, semantic, phonetic, phylogeny, concepts):
    """Compute similarities for sample entries."""
    unified = UnifiedSimilarityService(
        semantic=semantic,
        phonetic=phonetic,
        phylogeny=phylogeny,
        concepts=concepts
    )
    
    async with pool.acquire() as conn:
        # Sample high-quality entries
        rows = await conn.fetch(
            """
            SELECT * FROM entries 
            WHERE data_quality >= 0.8 AND embedding IS NOT NULL
            LIMIT 1000
            """
        )
        
        entries = [_row_to_entry(r) for r in rows]
        click.echo(f"  Computing for {len(entries)} entries...")
        
        # Compute pairwise (sample)
        count = 0
        for i in range(min(100, len(entries))):
            for j in range(i + 1, min(100, len(entries))):
                sim = unified.compute_similarity(entries[i], entries[j])
                
                # Store if significant
                if sim.combined >= 0.5:
                    await conn.execute(
                        """
                        INSERT INTO layered_similarities (
                            entry_a, entry_b, semantic_score, phonetic_score,
                            etymological_score, combined_score, weights,
                            phylogenetic_distance, concept_a, concept_b
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (entry_a, entry_b) DO NOTHING
                        """,
                        sim.entry_a, sim.entry_b, sim.semantic, sim.phonetic,
                        sim.etymological, sim.combined, json.dumps(sim.weights),
                        sim.phylogenetic_distance, sim.concept_a, sim.concept_b
                    )
                    count += 1
        
        click.echo(f"  Stored {count} similarity edges")


def _row_to_entry(row):
    """Convert DB row to Entry."""
    from backend.core.types import Entry
    return Entry(
        id=row['id'],
        headword=row['headword'],
        ipa=row['ipa'],
        language=row['language'],
        definition=row['definition'],
        etymology=row.get('etymology'),
        pos_tag=row.get('pos_tag'),
        embedding=list(row['embedding']) if row.get('embedding') else None,
        created_at=row['created_at']
    )


def _generate_label(concept) -> str:
    """Generate concept label."""
    if concept.sample_definitions:
        words = concept.sample_definitions[0].split()[:3]
        return "_".join(words).upper()
    return concept.id


if __name__ == '__main__':
    cli()

