"""Test accelerated pipeline to isolate performance bottlenecks."""

import asyncio
from datetime import datetime


async def test_pipeline_stages_independently():
    """Test each pipeline stage independently to isolate bottlenecks."""
    
    # Test 1: Queue throughput
    queue = asyncio.Queue(maxsize=10)
    
    async def producer():
        for i in range(1000):
            await queue.put(i)
        await queue.put(None)
    
    async def consumer():
        count = 0
        while True:
            item = await queue.get()
            if item is None:
                break
            count += 1
        return count
    
    start = datetime.utcnow()
    result = await asyncio.gather(producer(), consumer())
    duration = (datetime.utcnow() - start).total_seconds()
    
    print(f"Queue throughput: {1000/duration:.0f} items/sec")
    assert result[1] == 1000, "All items should be processed"


async def test_writer_termination_signals():
    """Test that writer workers receive and handle termination signals correctly."""
    
    queue = asyncio.Queue()
    num_writers = 2
    completed_writers = []
    
    async def writer_worker(worker_id):
        """Simulated writer worker."""
        while True:
            batch = await queue.get()
            if batch is None:
                completed_writers.append(worker_id)
                break
            # Simulate work
            await asyncio.sleep(0.001)
    
    # Start writers
    writers = [asyncio.create_task(writer_worker(i)) for i in range(num_writers)]
    
    # Send some work
    for i in range(100):
        await queue.put(f"batch_{i}")
    
    # Send termination signals
    for _ in range(num_writers):
        await queue.put(None)
    
    # Wait for completion with timeout
    await asyncio.wait_for(asyncio.gather(*writers), timeout=5.0)
    
    assert len(completed_writers) == num_writers, f"Expected {num_writers} writers to complete, got {len(completed_writers)}"
    print(f"✓ All {num_writers} writers terminated correctly")


async def test_multi_stage_pipeline_termination():
    """Test that termination signals propagate correctly through multi-stage pipeline.
    
    Architecture (matches accelerated pipeline):
    - Stage 1: Multiple cleaners -> cleaned_queue
    - Stage 2: Single embedder (bottleneck) -> embedded_queue  
    - Stage 3: Multiple writers
    """
    
    cleaned_queue = asyncio.Queue()
    embedded_queue = asyncio.Queue()
    
    num_cleaners = 4
    num_writers = 2
    
    cleaners_completed = []
    embedder_completed = []
    writers_completed = []
    
    async def cleaner_worker(worker_id):
        """Stage 1: Clean data."""
        while True:
            batch = await cleaned_queue.get()
            if batch is None:
                cleaners_completed.append(worker_id)
                # Send completion signal
                await cleaned_queue.put(None)
                break
            # Forward processed data
            await cleaned_queue.put(f"cleaned_{batch}")
    
    async def embedder_worker():
        """Stage 2: Compute embeddings (single bottleneck)."""
        none_count = 0
        while True:
            batch = await cleaned_queue.get()
            if batch is None:
                none_count += 1
                # Wait until ALL cleaners have sent their completion signals
                if none_count >= num_cleaners:
                    # Now send completion signals to all writers
                    for _ in range(num_writers):
                        await embedded_queue.put(None)
                    embedder_completed.append(0)
                    break
                # Continue consuming None signals from other cleaners
                continue
            # Process and forward
            await embedded_queue.put(f"embedded_{batch}")
    
    async def writer_worker(worker_id):
        """Stage 3: Write data."""
        while True:
            batch = await embedded_queue.get()
            if batch is None:
                writers_completed.append(worker_id)
                break
            # Simulate work
            await asyncio.sleep(0.001)
    
    # Start workers
    cleaners = [asyncio.create_task(cleaner_worker(i)) for i in range(num_cleaners)]
    embedder = asyncio.create_task(embedder_worker())
    writers = [asyncio.create_task(writer_worker(i)) for i in range(num_writers)]
    
    # Send work
    for i in range(100):
        await cleaned_queue.put(f"batch_{i}")
    
    # Send initial termination signals to cleaners
    for _ in range(num_cleaners):
        await cleaned_queue.put(None)
    
    # Wait for completion with timeout
    await asyncio.wait_for(
        asyncio.gather(*cleaners, embedder, *writers), 
        timeout=10.0
    )
    
    assert len(cleaners_completed) == num_cleaners, f"Cleaners: Expected {num_cleaners}, got {len(cleaners_completed)}"
    assert len(embedder_completed) == 1, f"Embedder: Expected 1, got {len(embedder_completed)}"
    assert len(writers_completed) == num_writers, f"Writers: Expected {num_writers}, got {len(writers_completed)}"
    
    print(f"✓ Multi-stage pipeline terminated correctly")
    print(f"  Cleaners:  {len(cleaners_completed)}/{num_cleaners} workers")
    print(f"  Embedder: {len(embedder_completed)}/1 worker")
    print(f"  Writers:   {len(writers_completed)}/{num_writers} workers")


if __name__ == "__main__":
    print("Running pipeline tests...\n")
    
    print("Test 1: Queue throughput")
    asyncio.run(test_pipeline_stages_independently())
    
    print("\nTest 2: Writer termination signals")
    asyncio.run(test_writer_termination_signals())
    
    print("\nTest 3: Multi-stage pipeline termination")
    asyncio.run(test_multi_stage_pipeline_termination())
    
    print("\n✓ All tests passed!")

