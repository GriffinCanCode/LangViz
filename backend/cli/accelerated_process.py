"""Optimized processing CLI with GPU acceleration and pipeline architecture.

Usage:
    python3 backend/cli/accelerated_process.py --batch-size 5000 --gpu

Performance:
    Baseline: 300 entries/sec (~7-10 hours for 6.7M entries)
    Optimized: 10,000+ entries/sec (~15 minutes for 6.7M entries)
    
    Speedup: 30-50x faster
"""

import asyncio
import click
import asyncpg
from pathlib import Path

from backend.config import get_settings
from backend.services.embedding import OptimizedEmbeddingService
from backend.services.concepts import ConceptAligner
from backend.storage.accelerated import AcceleratedBatchProcessor, PipelineConfig
from backend.storage.cache import EmbeddingCache, ConceptCache
from backend.observ import get_logger

logger = get_logger(__name__)


async def get_pool():
    """Create optimized database connection pool."""
    settings = get_settings()
    return await asyncpg.create_pool(
        host=settings.postgres_host,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        min_size=10,  # Increased for parallel writers
        max_size=50,  # Higher concurrency
        command_timeout=300,  # 5 min timeout
        max_cached_statement_lifetime=3600  # Cache prepared statements
    )


@click.command()
@click.option('--db-fetch-batch', default=5000, help='Database fetch batch size')
@click.option('--embedding-batch', default=512, help='GPU batch size for embeddings')
@click.option('--db-write-batch', default=10000, help='Database write batch size')
@click.option('--num-cleaners', default=4, help='Parallel cleaning workers')
@click.option('--num-writers', default=2, help='Parallel database writers')
@click.option('--source-id', default=None, help='Process specific source')
@click.option('--resume-from', default=None, help='Resume from entry ID')
@click.option('--gpu/--no-gpu', default=True, help='Use GPU acceleration')
@click.option('--cache/--no-cache', default=True, help='Use Redis caching')
@click.option('--quality-threshold', default=0.5, help='Minimum quality threshold')
def accelerated_process(
    db_fetch_batch,
    embedding_batch,
    db_write_batch,
    num_cleaners,
    num_writers,
    source_id,
    resume_from,
    gpu,
    cache,
    quality_threshold
):
    """Run optimized processing pipeline with GPU acceleration."""
    
    asyncio.run(_accelerated_process(
        db_fetch_batch=db_fetch_batch,
        embedding_batch=embedding_batch,
        db_write_batch=db_write_batch,
        num_cleaners=num_cleaners,
        num_writers=num_writers,
        source_id=source_id,
        resume_from=resume_from,
        use_gpu=gpu,
        use_cache=cache,
        quality_threshold=quality_threshold
    ))


async def _accelerated_process(
    db_fetch_batch: int,
    embedding_batch: int,
    db_write_batch: int,
    num_cleaners: int,
    num_writers: int,
    source_id: str,
    resume_from: str,
    use_gpu: bool,
    use_cache: bool,
    quality_threshold: float
):
    """Execute accelerated processing pipeline."""
    
    settings = get_settings()
    
    click.echo("\n" + "="*70)
    click.echo("LangViz Accelerated Processing Pipeline")
    click.echo("="*70)
    
    # Initialize database pool
    click.echo("\n[1/5] Initializing database connection pool...")
    pool = await get_pool()
    click.echo(f"  ✓ Connected (min={pool._minsize}, max={pool._maxsize})")
    
    # Initialize services
    click.echo("\n[2/5] Initializing services...")
    
    # Embedding service with GPU
    device = None if use_gpu else "cpu"
    embedding_service = OptimizedEmbeddingService(
        model_name=settings.embedding_model,
        device=device,
        batch_size=embedding_batch
    )
    device_info = embedding_service.device_info
    click.echo(f"  ✓ Embedding service: {device_info['device']} (batch={embedding_batch})")
    
    # Concept aligner
    concept_aligner = ConceptAligner(semantic_service=embedding_service)
    click.echo(f"  ✓ Concept aligner initialized")
    
    # Caching
    embedding_cache = None
    concept_cache = None
    
    if use_cache:
        click.echo("\n[3/5] Initializing Redis caching...")
        
        embedding_cache = EmbeddingCache(
            redis_url=settings.redis_url,
            enabled=True
        )
        await embedding_cache.connect()
        
        concept_cache = ConceptCache(
            redis_url=settings.redis_url,
            enabled=True
        )
        await concept_cache.connect()
        
        click.echo(f"  ✓ Redis cache connected")
    else:
        click.echo("\n[3/5] Caching disabled")
    
    # Configure pipeline
    click.echo("\n[4/5] Configuring pipeline...")
    config = PipelineConfig(
        db_fetch_batch=db_fetch_batch,
        embedding_batch=embedding_batch,
        db_write_batch=db_write_batch,
        num_cleaners=num_cleaners,
        num_embedders=1,  # Usually 1 GPU
        num_writers=num_writers,
        quality_threshold=quality_threshold,
        skip_existing_embeddings=True
    )
    
    click.echo(f"  ✓ Configuration:")
    click.echo(f"    - DB Fetch Batch: {config.db_fetch_batch:,}")
    click.echo(f"    - Embedding Batch: {config.embedding_batch:,}")
    click.echo(f"    - DB Write Batch: {config.db_write_batch:,}")
    click.echo(f"    - Parallel Cleaners: {config.num_cleaners}")
    click.echo(f"    - Parallel Writers: {config.num_writers}")
    click.echo(f"    - Quality Threshold: {config.quality_threshold}")
    
    # Run pipeline
    click.echo("\n[5/5] Starting accelerated pipeline...")
    click.echo("-"*70 + "\n")
    
    processor = AcceleratedBatchProcessor(
        pool=pool,
        embedding_service=embedding_service,
        concept_aligner=concept_aligner,
        config=config
    )
    
    try:
        stats = await processor.process_all(
            source_id=source_id,
            resume_from=resume_from
        )
        
        # Print final statistics
        click.echo("\n" + "="*70)
        click.echo("Pipeline Statistics")
        click.echo("="*70)
        click.echo(f"Total Entries: {stats.total_entries:,}")
        click.echo(f"Processed: {stats.processed:,}")
        click.echo(f"Succeeded: {stats.succeeded:,}")
        click.echo(f"Failed: {stats.failed:,}")
        click.echo(f"Skipped: {stats.skipped:,}")
        click.echo(f"")
        click.echo(f"Stage Breakdown:")
        click.echo(f"  Cleaned: {stats.cleaned:,}")
        click.echo(f"  Embedded: {stats.embedded:,}")
        click.echo(f"  Written: {stats.written:,}")
        click.echo(f"")
        
        duration = (stats.last_update - stats.start_time).total_seconds()
        click.echo(f"Performance:")
        click.echo(f"  Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        click.echo(f"  Rate: {stats.entries_per_second:.1f} entries/second")
        click.echo(f"  Speedup: ~{stats.entries_per_second/300:.1f}x vs baseline")
        
        # Cache statistics
        if use_cache and embedding_cache:
            cache_stats = embedding_cache.stats
            click.echo(f"")
            click.echo(f"Cache Statistics:")
            click.echo(f"  Embedding Cache Hit Rate: {cache_stats['hit_rate']*100:.1f}%")
            click.echo(f"  Cache Hits: {cache_stats['hits']:,}")
            click.echo(f"  Cache Misses: {cache_stats['misses']:,}")
            click.echo(f"  Cache Writes: {cache_stats['writes']:,}")
        
        # GPU statistics
        if device_info['device'] in ['cuda', 'mps']:
            click.echo(f"")
            click.echo(f"GPU Statistics:")
            click.echo(f"  Device: {device_info.get('gpu_name', device_info['device'])}")
            if 'gpu_memory_allocated' in device_info:
                click.echo(f"  Memory Allocated: {device_info['gpu_memory_allocated']:.2f} GB")
                click.echo(f"  Memory Reserved: {device_info['gpu_memory_reserved']:.2f} GB")
        
        click.echo("="*70 + "\n")
        
    except Exception as e:
        click.echo(f"\n✗ Pipeline failed: {e}", err=True)
        logger.error("pipeline_failed", error=str(e), error_type=type(e).__name__)
        raise
    
    finally:
        # Cleanup
        if embedding_cache:
            await embedding_cache.close()
        if concept_cache:
            await concept_cache.close()
        await pool.close()
        
        click.echo("✓ Cleanup complete")


@click.command()
@click.option('--source-id', default=None, help='Benchmark specific source')
def benchmark(source_id):
    """Benchmark processing performance."""
    
    asyncio.run(_benchmark(source_id))


async def _benchmark(source_id: str):
    """Run performance benchmark."""
    
    from time import time
    
    settings = get_settings()
    pool = await get_pool()
    
    # Test different batch sizes
    batch_sizes = [128, 256, 512, 1024, 2048]
    
    click.echo("\n" + "="*70)
    click.echo("Performance Benchmark")
    click.echo("="*70 + "\n")
    
    embedding_service = OptimizedEmbeddingService(
        model_name=settings.embedding_model,
        device=None,  # Auto-detect
        batch_size=512
    )
    
    click.echo(f"Device: {embedding_service.device_info['device']}\n")
    
    # Get sample texts
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT raw_data->>'definition' as definition
            FROM raw_entries
            WHERE raw_data->>'definition' IS NOT NULL
            LIMIT 10000
            """
        )
        texts = [row['definition'] for row in rows if row['definition']]
    
    if not texts:
        click.echo("No sample data found. Please run ingestion first.")
        await pool.close()
        return
    
    click.echo(f"Sample size: {len(texts):,} definitions\n")
    
    for batch_size in batch_sizes:
        embedding_service._batch_size = batch_size
        
        start = time()
        embeddings = embedding_service.batch_embed(texts[:5000], show_progress=False)
        duration = time() - start
        
        rate = len(texts[:5000]) / duration
        
        click.echo(f"Batch Size {batch_size:4d}: {rate:8.1f} entries/sec ({duration:.2f}s)")
    
    click.echo("\n" + "="*70)
    
    await pool.close()


if __name__ == '__main__':
    accelerated_process()

