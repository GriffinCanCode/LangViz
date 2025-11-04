.PHONY: help install install-rust rust-build db-setup db-migrate ingest ingest-fast reprocess process-all query clean test-rust start-perl-bg start-r-bg check-perl check-r check-deps stop-services

help:
	@echo "LangViz - Indo-European Etymology System"
	@echo ""
	@echo "Setup:"
	@echo "  make install       - Install all dependencies (Python + Rust + R + Perl)"
	@echo "  make install-rust  - Install Rust backend only"
	@echo "  make db-setup      - Initialize PostgreSQL database"
	@echo "  make db-migrate    - Run database migrations"
	@echo ""
	@echo "Services (auto-started by process-all):"
	@echo "  make start-r       - Start R phylogenetic service (foreground)"
	@echo "  make start-perl    - Start Perl parsing service (foreground)"
	@echo "  make check-deps    - Verify all integrations are ready"
	@echo "  make stop-services - Stop background services"
	@echo ""
	@echo "Data Processing (ACCELERATED with Parallel Workers):"
	@echo "  make ingest        - Accelerated ingestion with parallel workers"
	@echo "  make ingest-fast   - Maximum speed ingestion (more workers)"
	@echo "  make process-all   - Run OPTIMIZED pipeline with ALL integrations"
	@echo "  make reprocess     - Reprocess raw entries with updated pipeline"
	@echo "  make concepts      - Discover semantic concepts"
	@echo ""
	@echo "Query:"
	@echo "  make query-tak-da  - Example: Ukrainian 'tak' vs Russian 'da'"
	@echo ""
	@echo "Development:"
	@echo "  make test          - Run Python test suite"
	@echo "  make test-rust     - Run Rust test suite"
	@echo "  make clean         - Clean generated files"

install:
	@echo "Installing Python dependencies..."
	cd backend && python3 -m venv venv
	cd backend && . venv/bin/activate && pip install -r requirements.txt
	@echo "Installing Rust backend..."
	@command -v cargo >/dev/null 2>&1 || { echo "Rust not found. Install from https://rustup.rs/"; exit 1; }
	cd backend && . venv/bin/activate && pip install maturin
	cd services/langviz-rs && ../backend/venv/bin/maturin develop --release
	@echo "✓ All dependencies installed"

install-rust:
	@echo "Building Rust computational kernel..."
	@command -v cargo >/dev/null 2>&1 || { echo "Rust not found. Install from https://rustup.rs/"; exit 1; }
	cd backend && . venv/bin/activate && pip install maturin
	cd services/langviz-rs && ../../backend/venv/bin/maturin develop --release
	@echo "✓ Rust backend installed"
	@cd backend && . venv/bin/activate && python3 -c "import langviz_core; print('✓ langviz_core successfully imported')" || echo "✗ Import failed"

rust-build:
	@echo "Rebuilding Rust backend (use this after code changes)..."
	cd services/langviz-rs && ../../backend/venv/bin/maturin develop --release
	@echo "✓ Rust backend rebuilt"

db-setup:
	createdb langviz || echo "Database exists"
	psql langviz -c "CREATE EXTENSION IF NOT EXISTS vector;"
	@echo "✓ Database ready"

db-migrate:
	psql langviz -f backend/storage/migrations/001_initial_schema.sql
	psql langviz -f backend/storage/migrations/002_provenance_layer.sql
	psql langviz -f backend/storage/migrations/003_similarity_system.sql
	@echo "✓ Migrations complete"

ingest:
	@echo ""
	@echo "Starting ACCELERATED ingestion pipeline..."
	@echo "  ✓ Parallel workers: 4 cleaners + 2 writers"
	@echo "  ✓ Bulk operations with COPY protocol"
	@echo "  ✓ Expected rate: 5,000-10,000 entries/sec"
	@echo ""
	cd backend && . venv/bin/activate && cd .. && \
		PYTHONPATH=. python3 -m backend.cli.ingest ingest \
			--file data/sources/kaikki \
			--source kaikki \
			--format json \
			--workers 4 \
			--load-batch 10000 \
			--clean-batch 5000 \
			--write-batch 10000

ingest-fast:
	@echo ""
	@echo "Starting MAXIMUM SPEED ingestion pipeline..."
	@echo "  ✓ Parallel workers: 8 cleaners + 4 writers"
	@echo "  ✓ Bulk operations with COPY protocol"
	@echo "  ✓ Expected rate: 10,000-15,000 entries/sec"
	@echo ""
	cd backend && . venv/bin/activate && cd .. && \
		PYTHONPATH=. python3 -m backend.cli.ingest ingest \
			--file data/sources/kaikki \
			--source kaikki \
			--format json \
			--workers 8 \
			--load-batch 20000 \
			--clean-batch 10000 \
			--write-batch 20000

reprocess:
	@echo ""
	@echo "Starting ACCELERATED reprocessing pipeline..."
	@echo "  ✓ Parallel workers: 4 cleaners + 2 writers"
	@echo "  ✓ Bulk operations"
	@echo ""
	cd backend && . venv/bin/activate && cd .. && \
		PYTHONPATH=. python3 -m backend.cli.ingest reprocess \
			--workers 4 \
			--clean-batch 5000 \
			--write-batch 10000

process-all: check-r
	@echo ""
	@echo "Starting optimized processing pipeline..."
	@echo "  ✓ R service will auto-start in subprocess (REQUIRED)"
	@echo "  ✓ Rust acceleration enabled (REQUIRED)"
	@echo "  ✓ GPU auto-detection enabled"
	@echo "  ⚠ Perl service optional (only for Starling dictionaries)"
	@echo ""
	cd backend && . venv/bin/activate && cd .. && \
		DEBUG=false LOG_LEVEL=INFO PYTHONPATH=. python3 -m backend.cli.process process-pipeline

embed:
	@echo ""
	@echo "Starting embedding generation pipeline..."
	@echo "  ✓ GPU acceleration enabled"
	@echo "  ✓ Processes existing entries in database"
	@echo "  ✓ Batch size: 512 (GPU)"
	@echo "  ✓ Write batch: 10,000"
	@echo ""
	cd backend && . venv/bin/activate && cd .. && \
		DEBUG=false LOG_LEVEL=INFO PYTHONPATH=. python3 -m backend.cli.embed

embed-status:
	@./scripts/check_embedding_progress.sh

concepts:
	cd backend && . venv/bin/activate && cd .. && \
		PYTHONPATH=. python3 -m backend.cli.similarity discover-concepts

query-tak-da:
	cd backend && . venv/bin/activate && cd .. && \
		PYTHONPATH=. python3 -m backend.cli.process query AFFIRMATION uk ru

start-r:
	cd services/phylo-r && ./start.sh

start-perl:
	cd services/regexer && ./start.sh

start-perl-bg:
	@echo "Starting Perl service in background..."
	@cd services/regexer && ./start.sh > /tmp/langviz-perl.log 2>&1 & echo $$! > /tmp/langviz-perl.pid
	@sleep 2

start-r-bg:
	@echo "R service will be started automatically by OptimizedServiceContainer"

check-perl:
	@echo "Checking Perl service..."
	@if ! nc -z localhost 50051 2>/dev/null; then \
		echo "ERROR: Perl service not responding on port 50051"; \
		echo "Check logs: tail -f /tmp/langviz-perl.log"; \
		exit 1; \
	fi
	@echo "✓ Perl service ready"

check-r:
	@echo "Checking R installation..."
	@if ! command -v Rscript >/dev/null 2>&1; then \
		echo "ERROR: R not found in PATH"; \
		echo "Install from: https://cran.r-project.org/"; \
		exit 1; \
	fi
	@echo "✓ R installation found"

check-deps:
	@echo "Verifying all integrations..."
	@./scripts/check_integrations.sh

stop-services:
	@echo "Stopping background services..."
	@if [ -f /tmp/langviz-perl.pid ]; then \
		kill `cat /tmp/langviz-perl.pid` 2>/dev/null || true; \
		rm /tmp/langviz-perl.pid; \
		echo "✓ Perl service stopped"; \
	fi

test:
	cd backend && . venv/bin/activate && pytest tests/ -v

test-rust:
	cd services/langviz-rs && cargo test

bench-rust:
	cd services/langviz-rs && cargo bench

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	cd services/langviz-rs && cargo clean
