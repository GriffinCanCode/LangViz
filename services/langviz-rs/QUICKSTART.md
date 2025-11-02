# Rust Backend Quick Start

## 5-Minute Setup

### 1. Install Rust (if not already installed)

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Verify
rustc --version
cargo --version
```

### 2. Build Rust Backend

```bash
cd services/langviz-rs

# Install maturin (Python-Rust bridge)
pip install maturin

# Build and install (release mode for performance)
maturin develop --release
```

**Note**: Release mode is 10x faster but takes longer to compile. Use `maturin develop` for quick iteration during development.

### 3. Verify Installation

```python
python3 -c "import langviz_core; print('✓ Success!')"
```

If successful, you should see: `✓ Success!`

### 4. Test Basic Functions

```python
python3
>>> from langviz_core import py_phonetic_distance, py_find_cognate_sets
>>>
>>> # Test phonetic distance
>>> similarity = py_phonetic_distance("father", "vater")
>>> print(f"Similarity: {similarity:.3f}")
Similarity: 0.833
>>>
>>> # Test cognate detection
>>> edges = [
...     ("eng_father", "deu_vater", 0.85),
...     ("eng_father", "lat_pater", 0.82),
...     ("deu_vater", "lat_pater", 0.79),
... ]
>>> sets = py_find_cognate_sets(edges, threshold=0.7)
>>> print(f"Found {len(sets)} cognate set(s)")
>>> print(f"Members: {sets[0].members}")
Found 1 cognate set(s)
Members: ['eng_father', 'deu_vater', 'lat_pater']
```

✅ **Success!** The Rust backend is working.

## Common Issues

### "Rust not found"
- **Problem**: Rust toolchain not installed
- **Solution**: Install from https://rustup.rs/

### "maturin: command not found"
- **Problem**: maturin not installed
- **Solution**: `pip install maturin`

### "ImportError: cannot import name 'langviz_core'"
- **Problem**: Build failed or wrong Python environment
- **Solution**: 
  1. Check build output for errors
  2. Ensure you're in the same venv used for build
  3. Try `maturin develop --release` again

### "Slow build times"
- **Problem**: Release mode takes 2-5 minutes
- **Solution**: Use `maturin develop` (dev mode) for iteration, only use `--release` for final build

## Using from Python Services

The Rust backend integrates seamlessly:

```python
# backend/services/phonetic.py
from langviz_core import py_phonetic_distance

phonetic_service = PhoneticService(use_rust=True)
distance = phonetic_service.compute_distance("pater", "pitar")
```

Services automatically fall back to Python if Rust unavailable.

## Performance Comparison

Quick benchmark:

```python
import time
from langviz_core import py_batch_phonetic_distance

# Generate 1000 pairs
pairs = [("test", "best") for _ in range(1000)]

start = time.time()
similarities = py_batch_phonetic_distance(pairs)
elapsed = time.time() - start

print(f"Computed {len(pairs)} distances in {elapsed:.3f}s")
print(f"Throughput: {len(pairs)/elapsed:.0f} pairs/sec")
```

Expected output:
```
Computed 1000 distances in 0.008s
Throughput: 125000 pairs/sec
```

Compare this to pure Python (typically 10-50x slower).

## Next Steps

1. **Read the docs**: See `README.md` for full API reference
2. **Run tests**: `cargo test` in `services/langviz-rs/`
3. **Integration guide**: See `docs/RUST_INTEGRATION.md`
4. **Benchmarks**: `cargo bench` for detailed performance analysis

## Development Workflow

### Quick Iteration (Development Mode)

```bash
cd services/langviz-rs

# Fast compile, slower runtime
maturin develop

# Test changes
python3 -c "from langviz_core import py_phonetic_distance; print(py_phonetic_distance('a', 'b'))"
```

### Production Build (Release Mode)

```bash
# Slow compile, fast runtime
maturin develop --release

# Or build wheel for distribution
maturin build --release
ls target/wheels/
```

### Running Tests

```bash
# Rust tests
cargo test

# With output
cargo test -- --nocapture

# Specific test
cargo test test_phonetic_distance
```

### Benchmarking

```bash
# Run all benchmarks
cargo bench

# Specific benchmark
cargo bench phonetic
```

## Troubleshooting

### Compilation Errors

If you see errors about missing dependencies:

```bash
# Update Rust toolchain
rustup update

# Clean and rebuild
cargo clean
maturin develop --release
```

### Runtime Errors

If Python imports but functions fail:

1. Check error messages for type mismatches
2. Verify input types match Rust signatures
3. Enable logging in Python services to see fallback behavior

### Performance Issues

If Rust isn't faster than Python:

1. Ensure you're using `--release` mode
2. Check that parallel operations are actually running (8+ cores ideal)
3. Profile with `cargo flamegraph` to find bottlenecks

## Help

- **Rust API**: See `README.md`
- **Architecture**: See `docs/RUST_INTEGRATION.md`
- **Python integration**: See `backend/services/graph.py` and `backend/services/phonetic.py`
- **Issues**: Check build output for specific error messages


