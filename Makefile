.PHONY: help install install-rust rust-build db-setup db-migrate process-all query clean test-rust

help:
	@echo "LangViz - Indo-European Etymology System"
	@echo ""
	@echo "Setup:"
	@echo "  make install       - Install all dependencies (Python + Rust)"
	@echo "  make install-rust  - Install Rust backend only"
	@echo "  make db-setup      - Initialize PostgreSQL database"
	@echo "  make db-migrate    - Run database migrations"
	@echo ""
	@echo "Services:"
	@echo "  make start-r       - Start R phylogenetic service"
	@echo "  make start-perl    - Start Perl parsing service"
	@echo ""
	@echo "Data Processing:"
	@echo "  make ingest        - Ingest raw Kaikki data"
	@echo "  make process-all   - Run full pipeline (clean→embed→cluster→index)"
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
	cd services/langviz-rs && ../backend/venv/bin/maturin develop --release
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
	cd backend && . venv/bin/activate && \
		python3 -m backend.cli.process ingest-raw data/sources/kaikki --source-id kaikki

process-all:
	cd backend && . venv/bin/activate && \
		python3 -m backend.cli.process process-pipeline --discover-concepts --workers 9

concepts:
	cd backend && . venv/bin/activate && \
		python3 -m backend.cli.similarity discover-concepts

query-tak-da:
	cd backend && . venv/bin/activate && \
		python3 -m backend.cli.process query AFFIRMATION uk ru

start-r:
	cd services/phylo-r && ./start.sh

start-perl:
	cd services/regexer && perl server.pl

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
