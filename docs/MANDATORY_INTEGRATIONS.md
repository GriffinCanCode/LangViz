# Mandatory Integrations

As of the latest update, **all language-specific optimizations are now MANDATORY** when running `make process-all`. The system will fail to start if any required service is unavailable.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│              OptimizedServiceContainer                    │
│                                                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐         │
│  │   Python   │  │    Rust    │  │     R      │         │
│  │   FastAPI  │  │  PhO3/     │  │ ape/phangorn│        │
│  │            │  │  langviz_core│ │            │        │
│  └────────────┘  └────────────┘  └────────────┘         │
│                                                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐         │
│  │    Perl    │  │   Redis    │  │ PostgreSQL │         │
│  │   Regex    │  │   Cache    │  │  +pgvector │         │
│  │   Parser   │  │            │  │            │         │
│  └────────────┘  └────────────┘  └────────────┘         │
└──────────────────────────────────────────────────────────┘
```

## Required Components

### 1. Rust (Phonetic Acceleration)
**Purpose:** 10-100x faster phonetic distance computation using Rayon parallel iterators

**Installation:**
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Build and install Rust backend
make install-rust
```

**Verification:**
```bash
cd backend && . venv/bin/activate && python3 -c "import langviz_core; print('✓ Rust OK')"
```

**What happens:** `PhoneticService(use_rust=True)` is initialized and will fail if Rust backend is not available.

---

### 2. R (Phylogenetic Analysis)
**Purpose:** Statistical phylogenetic tree inference, bootstrap analysis, hierarchical clustering

**Installation:**
```bash
# Install R from https://cran.r-project.org/
# Or on macOS:
brew install r

# Install required R packages
cd services/phylo-r
Rscript install_deps.R
```

**Required R packages:**
- `ape` - Analysis of Phylogenetics and Evolution
- `phangorn` - Phylogenetic Reconstruction and Analysis
- `jsonlite` - JSON I/O

**Verification:**
```bash
Rscript -e 'library(ape); library(phangorn); library(jsonlite); print("✓ R OK")'
```

**What happens:** `RPhyloClient()` auto-starts as a subprocess when `OptimizedServiceContainer.initialize()` is called. The system pings the R service to verify it's responsive.

---

### 3. Perl (Dictionary Parsing)
**Purpose:** Advanced regex parsing for messy dictionary formats (Starling, legacy formats)

**Installation:**
```bash
# Install Perl (usually pre-installed on Unix systems)
# On macOS/Linux: already installed
# On Windows: https://www.perl.org/get.html

# Install Perl dependencies
cd services/regexer
cpanm --installdeps .
```

**Required Perl modules:**
- `JSON::XS` - Fast JSON encoding/decoding
- `IO::Socket::INET` - TCP server
- `Unicode::Normalize` - Unicode normalization

**Starting the service:**
```bash
# Manual start (foreground)
cd services/regexer && perl server.pl

# Or use helper script
make start-perl

# Background (auto-started by make process-all)
make start-perl-bg
```

**Verification:**
```bash
nc -z localhost 50051 && echo "✓ Perl service running"
```

**What happens:** `PerlParserClient` connects to TCP port 50051. The system sends a test request to verify the service is responsive. If the service is not running, the pipeline will fail to start.

---

### 4. PostgreSQL + pgvector
**Purpose:** Primary data storage with vector similarity search

**Installation:**
```bash
# Install PostgreSQL
brew install postgresql@14  # macOS
# Or: https://www.postgresql.org/download/

# Start PostgreSQL
brew services start postgresql@14

# Setup database
make db-setup
make db-migrate
```

**Verification:**
```bash
psql langviz -c "SELECT 1" && echo "✓ PostgreSQL OK"
```

---

### 5. Redis
**Purpose:** Embedding and concept cache (hit rates >80% on re-runs)

**Installation:**
```bash
# Install Redis
brew install redis  # macOS
# Or: https://redis.io/download

# Start Redis
redis-server
```

**Verification:**
```bash
redis-cli ping && echo "✓ Redis OK"
```

---

### 6. GPU (Optional but Recommended)
**Purpose:** 5-10x faster embedding computation

**Auto-detection:**
- CUDA (NVIDIA GPUs)
- MPS (Apple Silicon M1/M2/M3)
- CPU fallback (automatic)

**Verification:**
The system will print GPU info during initialization:
```
GPU Acceleration:
  Device: cuda:0 (or mps, or cpu)
  GPU: NVIDIA GeForce RTX 3080
```

---

## Quick Setup Script

Use the integration check script to verify all dependencies:

```bash
./scripts/check_integrations.sh
```

This will check:
- ✓ Python 3 installation
- ✓ Rust toolchain and langviz_core
- ✓ R installation and required packages
- ✓ Perl installation and required modules
- ✓ PostgreSQL database and langviz DB
- ✓ Redis server running
- ✓ Perl service running on port 50051

---

## Running the Pipeline

Once all integrations are ready:

```bash
# Start Perl service in background (if not already running)
make start-perl-bg

# Run full optimized pipeline (auto-starts R subprocess)
make process-all
```

**Expected output:**
```
Starting Perl service in background...
Checking Perl service...
✓ Perl service ready
R service will be started automatically by OptimizedServiceContainer
Checking R installation...
✓ R installation found

Starting optimized processing pipeline with ALL integrations...
  ✓ Perl service running on port 50051
  ✓ R service will auto-start in subprocess
  ✓ Rust acceleration enabled
  ✓ GPU auto-detection enabled

======================================================================
OPTIMIZED PERFORMANCE PROFILE
======================================================================

GPU Acceleration:
  Device: cuda:0
  Batch Size: 512
  GPU: NVIDIA GeForce RTX 3080

Rust Acceleration:
  Phonetic: ✓ Enabled

Language-Specific Services:
  R (Phylogenetics): ✓ Connected
  Perl (Parser): ✓ Connected

Caching:
  Embedding Cache: ✓ Enabled

Database:
  Connection Pool: 10-50
  Bulk Operations: ✓ COPY protocol enabled

Expected Performance:
  Baseline: ~300 entries/sec
  Optimized: 10,000+ entries/sec
  Speedup: 30-50x faster
  6.7M entries: ~12 minutes (vs 7-10 hours baseline)

======================================================================
```

---

## Troubleshooting

### "Failed to start R phylogenetic service"
- Ensure R is installed: `which Rscript`
- Install R packages: `cd services/phylo-r && Rscript install_deps.R`
- Check R version: `Rscript --version` (requires R >= 4.0)

### "Failed to connect to Perl parser service"
- Start Perl service: `make start-perl` or `cd services/regexer && perl server.pl`
- Check port 50051: `nc -z localhost 50051`
- Check Perl modules: `perl -MJSON::XS -e 1`

### "Rust backend unavailable"
- Rebuild Rust backend: `make rust-build`
- Check installation: `cd backend && . venv/bin/activate && python3 -c "import langviz_core"`

### "Redis connection failed"
- Start Redis: `redis-server`
- Check connection: `redis-cli ping`

---

## Performance Impact

With all integrations enabled:

| Component | Speedup | Impact |
|-----------|---------|--------|
| Rust phonetic | 10-100x | Critical for distance computation |
| GPU embeddings | 5-10x | Critical for semantic vectors |
| R phylogenetics | N/A | Statistical rigor for tree inference |
| Perl parsing | 2-3x | Better handling of messy formats |
| PostgreSQL COPY | 100-1000x | Bulk insert optimization |
| Redis cache | 80%+ hits | Eliminates re-computation |

**Total speedup:** 30-50x vs baseline Python-only implementation

---

## Why Mandatory?

Previously, these were optional fallbacks:
- ❌ Rust unavailable → Python panphon (slow)
- ❌ R unavailable → Hard-coded static tree (no inference)
- ❌ Perl unavailable → Python regex (limited patterns)

**Problems with optional fallbacks:**
1. Silent performance degradation
2. Inconsistent results across environments
3. Hidden complexity in conditional logic

**Solution:** Make all optimizations mandatory
- ✓ Predictable performance
- ✓ Consistent results
- ✓ Fail fast with clear errors
- ✓ Simpler codebase

---

## Development Mode

For development/testing without all services:

```python
# DON'T use OptimizedServiceContainer
# Use individual services with fallbacks

from backend.services.phonetic import PhoneticService
phonetic = PhoneticService(use_rust=False)  # Python fallback
```

**Note:** Production pipeline (`make process-all`) requires all integrations.

---

## CI/CD Considerations

In CI/CD pipelines, ensure all services are available:

```yaml
# .github/workflows/test.yml
services:
  postgres:
    image: ankane/pgvector
  redis:
    image: redis:7

steps:
  - name: Install R
    run: |
      sudo apt-get install r-base
      Rscript -e 'install.packages(c("ape", "phangorn"))'
  
  - name: Install Perl modules
    run: |
      cpanm --installdeps services/regexer
  
  - name: Start Perl service
    run: |
      cd services/regexer && perl server.pl &
  
  - name: Install Rust
    uses: actions-rs/toolchain@v1
  
  - name: Build Rust backend
    run: make install-rust
  
  - name: Run pipeline
    run: make process-all
```

---

## Future: Docker Compose

Planned:

```yaml
version: '3.8'
services:
  postgres:
    image: ankane/pgvector
  
  redis:
    image: redis:7
  
  perl-parser:
    build: ./services/regexer
    ports:
      - "50051:50051"
  
  langviz:
    build: .
    depends_on:
      - postgres
      - redis
      - perl-parser
    environment:
      - PARSER_SERVICE_HOST=perl-parser
```

This will simplify deployment: `docker-compose up && make process-all`

