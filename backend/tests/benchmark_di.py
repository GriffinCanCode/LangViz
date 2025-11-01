"""Benchmark to demonstrate dependency injection performance improvements.

Compares per-request instantiation vs singleton pattern.
"""

import time
from backend.api.dependencies import ServiceContainer
from backend.services import SemanticService


def benchmark_per_request_creation(num_requests: int = 5):
    """Simulate old behavior: creating new service instances per request."""
    print(f"\n{'='*60}")
    print("❌ OLD: Per-Request Instantiation")
    print(f"{'='*60}")
    
    total_time = 0
    for i in range(num_requests):
        start = time.time()
        service = SemanticService()  # New instance every time
        _ = service.get_embedding("test")
        elapsed = time.time() - start
        total_time += elapsed
        print(f"  Request {i+1}: {elapsed:.3f}s")
    
    avg_time = total_time / num_requests
    print(f"\n  Average time per request: {avg_time:.3f}s")
    print(f"  Total time for {num_requests} requests: {total_time:.3f}s")
    return avg_time


def benchmark_singleton(num_requests: int = 5):
    """Simulate new behavior: reusing singleton service instance."""
    print(f"\n{'='*60}")
    print("✅ NEW: Singleton Pattern")
    print(f"{'='*60}")
    
    # Initialize once (startup cost)
    print("  Initializing services (one-time startup cost)...")
    startup_start = time.time()
    ServiceContainer.initialize()
    startup_time = time.time() - startup_start
    print(f"  Startup time: {startup_time:.3f}s")
    
    # Simulate requests
    print(f"\n  Processing {num_requests} requests:")
    total_time = 0
    for i in range(num_requests):
        start = time.time()
        service = ServiceContainer.get_semantic_service()  # Reuse singleton
        _ = service.get_embedding("test")
        elapsed = time.time() - start
        total_time += elapsed
        print(f"  Request {i+1}: {elapsed:.6f}s")
    
    avg_time = total_time / num_requests
    print(f"\n  Average time per request: {avg_time:.6f}s")
    print(f"  Total time for {num_requests} requests: {total_time:.3f}s")
    print(f"  (Startup time amortized over all requests: {startup_time/num_requests:.3f}s)")
    
    ServiceContainer.cleanup()
    return avg_time


def main():
    print("\n" + "="*60)
    print("DEPENDENCY INJECTION PERFORMANCE BENCHMARK")
    print("="*60)
    print("\nComparing OLD (per-request) vs NEW (singleton) approaches")
    print("for SemanticService with transformer model loading.\n")
    
    num_requests = 5
    
    # Benchmark old approach (WARNING: This will be slow!)
    print("\n⚠️  Warning: Old approach will be VERY slow (loads model each time)...")
    input("Press Enter to start OLD benchmark (or Ctrl+C to skip)...")
    old_avg = benchmark_per_request_creation(num_requests)
    
    # Benchmark new approach
    print("\n\n🚀 Starting NEW benchmark (much faster!)...")
    time.sleep(1)
    new_avg = benchmark_singleton(num_requests)
    
    # Summary
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  OLD (per-request):  {old_avg:.3f}s per request")
    print(f"  NEW (singleton):    {new_avg:.6f}s per request")
    print(f"\n  🎉 Speedup: {old_avg/new_avg:.1f}x faster!")
    print(f"  🎉 Time saved: {(old_avg - new_avg)*1000:.1f}ms per request")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBenchmark cancelled by user.")
    except Exception as e:
        print(f"\nError during benchmark: {e}")

