"""CLI command to add embeddings to existing entries.

This is a streamlined pipeline that:
1. Reads entries from the database (WHERE embedding IS NULL)
2. Generates embeddings using GPU
3. Updates entries in place

Much simpler than the full ingestion pipeline!
"""

import asyncio
import asyncpg
from datetime import datetime
from backend.config import get_settings
from backend.observ import get_logger
from backend.services.optimized import OptimizedServiceContainer
from backend.core.types import Entry

logger = get_logger(__name__)


class EmbeddingPipeline:
    """Streamlined pipeline to add embeddings to existing entries."""
    
    def __init__(self, services: OptimizedServiceContainer, batch_size: int = 512, write_batch: int = 10000):
        self.services = services
        self.batch_size = batch_size
        self.write_batch = write_batch
        self.stats = {
            'processed': 0,
            'embedded': 0,
            'failed': 0,
            'written': 0
        }
    
    async def run(self):
        """Run the embedding pipeline."""
        settings = get_settings()
        
        # Connect to database
        conn = await asyncpg.connect(settings.database_url)
        
        try:
            # Get total count
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM entries WHERE embedding IS NULL"
            )
            
            logger.info("embedding_pipeline_starting", total_entries=total)
            print(f"\n{'='*70}")
            print(f"EMBEDDING PIPELINE")
            print(f"Total entries without embeddings: {total:,}")
            print(f"Embedding batch size: {self.batch_size}")
            print(f"DB write batch size: {self.write_batch}")
            print(f"GPU Device: {self.services.embedding.device_info}")
            print(f"{'='*70}\n")
            
            # Process in batches
            fetch_size = 5000
            write_buffer = []
            start_time = datetime.utcnow()
            processed_count = 0
            
            # Keep fetching until no more rows without embeddings
            while processed_count < total:
                # Fetch batch (no OFFSET - just get the first N rows without embeddings)
                # This works because we update them as we go, so they drop out of the result set
                rows = await conn.fetch(
                    """
                    SELECT id, headword, ipa, language, definition, etymology, pos_tag, created_at
                    FROM entries
                    WHERE embedding IS NULL
                    ORDER BY id
                    LIMIT $1
                    """,
                    fetch_size
                )
                
                if not rows:
                    break
                
                # Convert to Entry objects
                entries = [
                    Entry(
                        id=row['id'],
                        headword=row['headword'],
                        ipa=row['ipa'],
                        language=row['language'],
                        definition=row['definition'],
                        etymology=row['etymology'],
                        pos_tag=row['pos_tag'],
                        embedding=None,
                        created_at=row['created_at']
                    )
                    for row in rows
                ]
                
                # Generate embeddings in sub-batches (GPU memory management)
                for i in range(0, len(entries), self.batch_size):
                    sub_batch = entries[i:i + self.batch_size]
                    definitions = [e.definition for e in sub_batch]
                    
                    try:
                        # Generate embeddings
                        embeddings = self.services.embedding.batch_embed(definitions)
                        
                        # Add to write buffer (convert embedding to string for vector type)
                        for entry, embedding in zip(sub_batch, embeddings):
                            # Convert numpy array to string representation for pgvector
                            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                            write_buffer.append((entry.id, embedding_str))
                            self.stats['embedded'] += 1
                        
                    except Exception as e:
                        logger.error("embedding_batch_failed", error=str(e), batch_size=len(sub_batch))
                        self.stats['failed'] += len(sub_batch)
                
                self.stats['processed'] += len(entries)
                processed_count += len(entries)
                
                # Flush write buffer if large enough
                if len(write_buffer) >= self.write_batch:
                    await self._flush_buffer(conn, write_buffer)
                    write_buffer = []
                
                # Progress update
                if self.stats['processed'] % 50000 == 0:
                    elapsed = (datetime.utcnow() - start_time).total_seconds()
                    rate = self.stats['processed'] / elapsed if elapsed > 0 else 0
                    remaining = (total - self.stats['processed']) / rate if rate > 0 else 0
                    
                    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] "
                          f"Progress: {100*self.stats['processed']/total:.1f}% | "
                          f"Processed: {self.stats['processed']:,}/{total:,} | "
                          f"Written: {self.stats['written']:,} | "
                          f"Rate: {rate:.0f}/s | "
                          f"ETA: {remaining/60:.1f}min")
            
            # Final flush
            if write_buffer:
                await self._flush_buffer(conn, write_buffer)
            
            # Final stats
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            rate = self.stats['processed'] / elapsed if elapsed > 0 else 0
            
            print(f"\n{'='*70}")
            print(f"EMBEDDING PIPELINE COMPLETE")
            print(f"Total processed: {self.stats['processed']:,}")
            print(f"Embeddings created: {self.stats['embedded']:,}")
            print(f"Written to DB: {self.stats['written']:,}")
            print(f"Failed: {self.stats['failed']:,}")
            print(f"Time: {elapsed/60:.1f} minutes")
            print(f"Rate: {rate:.0f} entries/sec")
            print(f"{'='*70}\n")
            
            logger.info("embedding_pipeline_complete",
                       processed=self.stats['processed'],
                       embedded=self.stats['embedded'],
                       written=self.stats['written'],
                       failed=self.stats['failed'],
                       duration_seconds=elapsed)
        
        finally:
            await conn.close()
    
    async def _flush_buffer(self, conn: asyncpg.Connection, buffer: list):
        """Flush write buffer to database."""
        if not buffer:
            return
        
        try:
            # Bulk update using executemany (faster than individual updates)
            result = await conn.executemany("""
                UPDATE entries
                SET embedding = $2::vector
                WHERE id = $1
            """, buffer)
            
            # Count successful updates
            written = len(buffer)
            self.stats['written'] += written
            
            logger.info("write_buffer_flushed", count=written)
            
        except Exception as e:
            logger.error("write_buffer_flush_failed", error=str(e), buffer_size=len(buffer))
            raise


async def main():
    """Main entry point."""
    print("\n" + "="*70)
    print("LANGVIZ EMBEDDING PIPELINE")
    print("="*70)
    
    # Initialize services
    print("\n[1/3] Initializing services...")
    services = OptimizedServiceContainer()
    await services.initialize()
    
    try:
        # Run pipeline
        print("\n[2/3] Running embedding pipeline...")
        pipeline = EmbeddingPipeline(services)
        await pipeline.run()
        
        print("\n[3/3] ✓ Complete!")
        
    finally:
        await services.close()


if __name__ == "__main__":
    asyncio.run(main())

