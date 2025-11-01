"""Streaming utilities for memory-efficient data processing.

Generators and async iterators for processing large datasets without
loading everything into memory. Implements backpressure, batching,
and progress tracking.
"""

import asyncio
import gzip
from pathlib import Path
from typing import AsyncIterator, Iterator, TypeVar, Callable, Optional
from collections import deque

import orjson  # Faster than stdlib json


T = TypeVar('T')


# ═══════════════════════════════════════════════════════════════════════
# JSONL STREAMING (Memory-Efficient Line-by-Line)
# ═══════════════════════════════════════════════════════════════════════

async def stream_jsonl(
    filepath: Path | str,
    batch_size: int = 1000,
    skip_errors: bool = True,
    decompress: bool = False
) -> AsyncIterator[list[dict]]:
    """Stream JSONL file in batches (async generator).
    
    Yields batches instead of individual entries for better throughput.
    Handles gzip-compressed files automatically.
    
    Args:
        filepath: Path to JSONL file
        batch_size: Number of entries per batch
        skip_errors: Continue on JSON decode errors
        decompress: Force gzip decompression
        
    Yields:
        list[dict]: Batch of parsed JSON objects
    """
    
    filepath = Path(filepath)
    
    # Determine if file is compressed
    is_compressed = decompress or filepath.suffix == '.gz'
    
    # Open file appropriately
    open_fn = gzip.open if is_compressed else open
    
    batch = []
    
    def process_batch():
        """Process batch in thread pool (orjson parsing can be CPU-bound)."""
        nonlocal batch
        result = []
        
        for line in batch:
            if not line.strip():
                continue
            
            try:
                obj = orjson.loads(line)
                result.append(obj)
            except orjson.JSONDecodeError as e:
                if not skip_errors:
                    raise
                # Skip malformed JSON
        
        batch = []
        return result
    
    with open_fn(filepath, 'rb') as f:
        for line in f:
            batch.append(line)
            
            if len(batch) >= batch_size:
                # Process batch in thread pool
                result = await asyncio.to_thread(process_batch)
                if result:
                    yield result
                batch = []
        
        # Process remaining entries
        if batch:
            result = await asyncio.to_thread(process_batch)
            if result:
                yield result


def stream_jsonl_sync(
    filepath: Path | str,
    skip_errors: bool = True
) -> Iterator[dict]:
    """Synchronous JSONL streaming (for non-async contexts).
    
    Memory-efficient generator for line-by-line processing.
    """
    
    filepath = Path(filepath)
    is_compressed = filepath.suffix == '.gz'
    open_fn = gzip.open if is_compressed else open
    
    with open_fn(filepath, 'rb') as f:
        for line_num, line in enumerate(f, start=1):
            if not line.strip():
                continue
            
            try:
                yield orjson.loads(line)
            except orjson.JSONDecodeError as e:
                if not skip_errors:
                    raise ValueError(f"Invalid JSON at line {line_num}: {e}")


# ═══════════════════════════════════════════════════════════════════════
# BATCHING (Combine items for throughput)
# ═══════════════════════════════════════════════════════════════════════

async def batch(
    iterator: AsyncIterator[T],
    batch_size: int
) -> AsyncIterator[list[T]]:
    """Batch async iterator items.
    
    Collects items into batches for more efficient processing.
    """
    
    batch = []
    
    async for item in iterator:
        batch.append(item)
        
        if len(batch) >= batch_size:
            yield batch
            batch = []
    
    # Yield remaining items
    if batch:
        yield batch


def batch_sync(iterator: Iterator[T], batch_size: int) -> Iterator[list[T]]:
    """Batch synchronous iterator items."""
    
    batch = []
    
    for item in iterator:
        batch.append(item)
        
        if len(batch) >= batch_size:
            yield batch
            batch = []
    
    if batch:
        yield batch


# ═══════════════════════════════════════════════════════════════════════
# PARALLEL MAPPING (Concurrent transformation)
# ═══════════════════════════════════════════════════════════════════════

async def map_concurrent(
    iterator: AsyncIterator[T],
    transform: Callable,
    max_concurrency: int = 10
) -> AsyncIterator[T]:
    """Apply async transformation concurrently with bounded parallelism.
    
    Maintains order and implements backpressure via semaphore.
    """
    
    semaphore = asyncio.Semaphore(max_concurrency)
    tasks = []
    
    async def bounded_transform(item: T) -> T:
        async with semaphore:
            return await transform(item)
    
    async for item in iterator:
        task = asyncio.create_task(bounded_transform(item))
        tasks.append(task)
        
        # Yield completed tasks
        while tasks and tasks[0].done():
            result = await tasks.pop(0)
            yield result
    
    # Yield remaining tasks
    for task in tasks:
        yield await task


# ═══════════════════════════════════════════════════════════════════════
# FILTERING (Remove unwanted items)
# ═══════════════════════════════════════════════════════════════════════

async def filter_async(
    iterator: AsyncIterator[T],
    predicate: Callable[[T], bool]
) -> AsyncIterator[T]:
    """Filter async iterator items."""
    
    async for item in iterator:
        if predicate(item):
            yield item


# ═══════════════════════════════════════════════════════════════════════
# PROGRESS TRACKING (Rich progress bars)
# ═══════════════════════════════════════════════════════════════════════

async def track_progress(
    iterator: AsyncIterator[T],
    total: Optional[int] = None,
    description: str = "Processing"
) -> AsyncIterator[T]:
    """Wrap async iterator with progress tracking.
    
    Uses tqdm for progress bar display.
    """
    from tqdm.asyncio import tqdm
    
    count = 0
    
    with tqdm(total=total, desc=description, unit="items") as pbar:
        async for item in iterator:
            count += 1
            pbar.update(1)
            yield item


# ═══════════════════════════════════════════════════════════════════════
# CHECKPOINTING (Resumable processing)
# ═══════════════════════════════════════════════════════════════════════

class Checkpoint:
    """Resumable checkpoint for stream processing.
    
    Saves progress to allow resuming after interruption.
    """
    
    def __init__(self, filepath: Path | str):
        self.filepath = Path(filepath)
        self.processed: set[str] = set()
        self._load()
    
    def _load(self):
        """Load checkpoint from disk."""
        if self.filepath.exists():
            with open(self.filepath, 'rb') as f:
                self.processed = set(orjson.loads(f.read()))
    
    def save(self):
        """Save checkpoint to disk."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, 'wb') as f:
            f.write(orjson.dumps(list(self.processed)))
    
    def mark_processed(self, id: str):
        """Mark item as processed."""
        self.processed.add(id)
    
    def is_processed(self, id: str) -> bool:
        """Check if item already processed."""
        return id in self.processed


async def with_checkpoint(
    iterator: AsyncIterator[T],
    checkpoint: Checkpoint,
    get_id: Callable[[T], str],
    save_interval: int = 100
) -> AsyncIterator[T]:
    """Wrap iterator with checkpointing for resumability.
    
    Args:
        iterator: Source iterator
        checkpoint: Checkpoint instance
        get_id: Function to extract unique ID from item
        save_interval: Save checkpoint every N items
    """
    
    count = 0
    
    async for item in iterator:
        item_id = get_id(item)
        
        # Skip if already processed
        if checkpoint.is_processed(item_id):
            continue
        
        yield item
        
        # Mark as processed
        checkpoint.mark_processed(item_id)
        count += 1
        
        # Periodic saves
        if count % save_interval == 0:
            checkpoint.save()
    
    # Final save
    checkpoint.save()


# ═══════════════════════════════════════════════════════════════════════
# WINDOWING (Sliding window for sequences)
# ═══════════════════════════════════════════════════════════════════════

def sliding_window(
    iterator: Iterator[T],
    window_size: int
) -> Iterator[tuple[T, ...]]:
    """Create sliding window over iterator.
    
    Example:
        [1, 2, 3, 4] with window_size=2 yields:
        (1, 2), (2, 3), (3, 4)
    """
    
    window = deque(maxlen=window_size)
    
    for item in iterator:
        window.append(item)
        
        if len(window) == window_size:
            yield tuple(window)


# ═══════════════════════════════════════════════════════════════════════
# DEDUPLICATION (Memory-efficient duplicate removal)
# ═══════════════════════════════════════════════════════════════════════

async def deduplicate(
    iterator: AsyncIterator[T],
    get_key: Callable[[T], str]
) -> AsyncIterator[T]:
    """Remove duplicates from stream based on key function.
    
    Warning: Keeps all seen keys in memory. For very large streams,
    consider using a bloom filter or external deduplication.
    """
    
    seen = set()
    
    async for item in iterator:
        key = get_key(item)
        
        if key not in seen:
            seen.add(key)
            yield item

