.PHONY: help install db-setup db-migrate process-all query clean

help:
	@echo "LangViz - Indo-European Etymology System"
	@echo ""
	@echo "Setup:"
	@echo "  make install       - Install all dependencies"
	@echo "  make db-setup      - Initialize PostgreSQL database"
	@echo "  make db-migrate    - Run database migrations"
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
	@echo "  make test          - Run test suite"
	@echo "  make clean         - Clean generated files"

install:
	cd backend && python3 -m venv venv
	cd backend && . venv/bin/activate && pip install -r requirements.txt
	@echo "✓ Dependencies installed"

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

test:
	cd backend && . venv/bin/activate && pytest tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
