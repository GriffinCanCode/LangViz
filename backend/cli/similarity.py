"""CLI for similarity system operations.

Commands:
- discover-concepts: Run UMAP + HDBSCAN clustering
- compute-similarities: Build pairwise similarity matrix
- analyze-difference: Explain lexical differences
- visualize: Create 2D/3D visualizations
- batch-process: Process raw entries in bulk
"""

import asyncio
import click
import asyncpg
from pathlib import Path

from backend.services.semantic import SemanticService
from backend.services.phonetic import PhoneticService
from backend.services.phylogeny import PhylogeneticTree
from backend.services.concepts import ConceptAligner
from backend.services.unified import UnifiedSimilarityService
from backend.services.visualize import VisualizationReducer, ConceptVisualizer
from backend.storage.batch import BatchProcessor, BatchConfig
from backend.core.similarity import SimilarityMode


@click.group()
def cli():
    """LangViz Similarity System CLI"""
    pass


@cli.command()
@click.option('--min-cluster-size', default=50, help='Minimum concept cluster size')
@click.option('--source-id', default=None, help='Filter by data source')
@click.option('--limit', default=None, type=int, help='Limit entries for testing')
async def discover_concepts(min_cluster_size, source_id, limit):
    """Discover semantic concepts using UMAP + HDBSCAN."""
    
    click.echo("Initializing services...")
    
    # Initialize services
    semantic = SemanticService()
    concepts = ConceptAligner(
        semantic_service=semantic,
        min_cluster_size=min_cluster_size
    )
    
    # Connect to database
    pool = await asyncpg.create_pool(
        dsn="postgresql://localhost/langviz"  # TODO: Config
    )
    
    click.echo("Loading entries...")
    
    # Load entries
    async with pool.acquire() as conn:
        query = "SELECT * FROM entries"
        if source_id:
            query += f" WHERE source_id = '{source_id}'"
        if limit:
            query += f" LIMIT {limit}"
        
        rows = await conn.fetch(query)
        entries = [_row_to_entry(row) for row in rows]
    
    click.echo(f"Loaded {len(entries)} entries")
    click.echo("Discovering concepts (this may take several minutes)...")
    
    # Run clustering
    discovered = concepts.discover_concepts(entries)
    
    click.echo(f"\nDiscovered {len(discovered)} concepts!")
    click.echo("\nTop concepts by size:")
    for concept in sorted(discovered, key=lambda c: c.size, reverse=True)[:10]:
        click.echo(f"  {concept.id}: {concept.size} members, confidence={concept.confidence:.3f}")
        click.echo(f"    Languages: {', '.join(concept.languages[:5])}")
        click.echo(f"    Sample: {concept.sample_definitions[0][:60]}...")
    
    # Store concepts
    click.echo("\nStoring concepts in database...")
    async with pool.acquire() as conn:
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
    
    click.echo("Done!")
    await pool.close()


@cli.command()
@click.option('--batch-size', default=1000, help='Batch size for processing')
@click.option('--workers', default=9, help='Number of parallel workers')
@click.option('--source-id', default=None, help='Filter by data source')
@click.option('--resume-from', default=None, help='Resume from entry ID')
async def batch_process(batch_size, workers, source_id, resume_from):
    """Process raw entries in parallel batches."""
    
    click.echo("Initializing batch processor...")
    
    # Initialize services
    semantic = SemanticService()
    phylogeny = PhylogeneticTree()
    concepts = ConceptAligner(semantic_service=semantic)
    
    # Connect to database
    pool = await asyncpg.create_pool(
        dsn="postgresql://localhost/langviz",
        min_size=workers,
        max_size=workers * 2
    )
    
    # Configure processor
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
    
    click.echo(f"Starting batch processing with {workers} workers...")
    click.echo(f"Batch size: {batch_size}")
    if source_id:
        click.echo(f"Source filter: {source_id}")
    
    # Run processing
    progress = await processor.process_all(
        source_id=source_id,
        resume_from=resume_from
    )
    
    click.echo(f"\nProcessing complete!")
    click.echo(f"Total: {progress.total_entries}")
    click.echo(f"Succeeded: {progress.succeeded}")
    click.echo(f"Failed: {progress.failed}")
    click.echo(f"Time: {progress.elapsed_seconds:.1f}s")
    
    await pool.close()


@cli.command()
@click.argument('concept')
@click.argument('language-a')
@click.argument('language-b')
async def analyze_difference(concept, language_a, language_b):
    """Analyze why two languages use different words for same concept.
    
    Example: analyze-difference AFFIRMATION uk ru
    """
    
    click.echo(f"Analyzing lexical difference for concept '{concept}'")
    click.echo(f"Languages: {language_a} vs {language_b}")
    
    # Initialize services
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
    
    # Connect to database
    pool = await asyncpg.create_pool(dsn="postgresql://localhost/langviz")
    
    # Load entries
    async with pool.acquire() as conn:
        # Find concept ID
        concept_row = await conn.fetchrow(
            "SELECT id FROM concepts WHERE label ILIKE $1",
            f"%{concept}%"
        )
        
        if not concept_row:
            click.echo(f"Concept '{concept}' not found. Run discover-concepts first.")
            return
        
        concept_id = concept_row['id']
        
        # Load entries for each language
        entries_a_rows = await conn.fetch(
            "SELECT * FROM entries WHERE concept_id = $1 AND language = $2",
            concept_id, language_a
        )
        entries_b_rows = await conn.fetch(
            "SELECT * FROM entries WHERE concept_id = $1 AND language = $2",
            concept_id, language_b
        )
        all_rows = await conn.fetch(
            "SELECT * FROM entries WHERE concept_id = $1",
            concept_id
        )
        
        entries_a = [_row_to_entry(row) for row in entries_a_rows]
        entries_b = [_row_to_entry(row) for row in entries_b_rows]
        all_entries = [_row_to_entry(row) for row in all_rows]
    
    if not entries_a or not entries_b:
        click.echo(f"No entries found for one or both languages")
        return
    
    # Analyze
    click.echo(f"\nFound {len(entries_a)} entries for {language_a}")
    click.echo(f"Found {len(entries_b)} entries for {language_b}")
    click.echo("\nAnalyzing...")
    
    difference = unified.explain_difference(
        concept=concept_id,
        lang_a=language_a,
        lang_b=language_b,
        entries_a=entries_a,
        entries_b=entries_b,
        all_entries=all_entries
    )
    
    # Display results
    click.echo(f"\n{'='*60}")
    click.echo(f"Lexical Difference Analysis")
    click.echo(f"{'='*60}")
    click.echo(f"\nConcept: {concept}")
    click.echo(f"{language_a.upper()}: '{difference.form_a}'")
    click.echo(f"{language_b.upper()}: '{difference.form_b}'")
    click.echo(f"\nPhylogenetic distance: {difference.tree_distance}")
    click.echo(f"\nCognate clusters:")
    click.echo(f"  '{difference.form_a}' clusters with: {list(difference.cognates_a.keys())[:5]}")
    click.echo(f"  '{difference.form_b}' clusters with: {list(difference.cognates_b.keys())[:5]}")
    click.echo(f"\nExplanation:")
    click.echo(f"  {difference.explanation}")
    click.echo(f"{'='*60}\n")
    
    await pool.close()


@cli.command()
@click.option('--method', type=click.Choice(['umap', 'tsne', 'pca']), default='umap')
@click.option('--dimensions', type=click.Choice(['2', '3']), default='2')
@click.option('--output', default='visualization.html', help='Output HTML file')
async def visualize(method, dimensions, output):
    """Create interactive visualization of concept space."""
    
    click.echo(f"Creating {dimensions}D visualization using {method.upper()}...")
    
    # Initialize
    reducer = VisualizationReducer(
        method=method,
        n_dimensions=int(dimensions)
    )
    visualizer = ConceptVisualizer(reducer=reducer)
    
    # Connect to database
    pool = await asyncpg.create_pool(dsn="postgresql://localhost/langviz")
    
    # Load concepts
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM concepts ORDER BY size DESC LIMIT 100")
        
        if not rows:
            click.echo("No concepts found. Run discover-concepts first.")
            return
        
        centroids = [row['centroid'] for row in rows]
        labels = [row['label'] for row in rows]
    
    click.echo(f"Loaded {len(centroids)} concepts")
    click.echo("Computing visualization...")
    
    # Create visualization
    import numpy as np
    plot_data = visualizer.visualize_concepts(
        concept_centroids=np.array(centroids),
        concept_labels=labels
    )
    
    # Export
    from backend.services.visualize import export_plotly_scatter
    export_plotly_scatter(plot_data, output)
    
    click.echo(f"Visualization saved to {output}")
    await pool.close()


def _row_to_entry(row):
    """Convert database row to Entry object."""
    from backend.core.types import Entry
    return Entry(
        id=row['id'],
        headword=row['headword'],
        ipa=row['ipa'],
        language=row['language'],
        definition=row['definition'],
        etymology=row.get('etymology'),
        pos_tag=row.get('pos_tag'),
        embedding=row.get('embedding'),
        created_at=row['created_at']
    )


def _generate_label(concept) -> str:
    """Generate label from sample definitions."""
    if not concept.sample_definitions:
        return f"concept_{concept.id}"
    
    first_def = concept.sample_definitions[0]
    words = first_def.split()[:3]
    return "_".join(words).upper()


if __name__ == '__main__':
    cli(_anyio_backend='asyncio')

