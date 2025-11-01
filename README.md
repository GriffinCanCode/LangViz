# LangViz

**Indo-European Etymology & Semantic Similarity Mapper**

A computational system for detecting and visualizing semantic relationships, cognate patterns, and etymological connections across Indo-European languages.

## Architecture

### Backend (Python 3.11+)
- **FastAPI** orchestration layer
- **PostgreSQL 16** with pgvector for embeddings
- **Redis** for caching
- Strong typing with Pydantic
- Protocol-based service contracts

### Specialized Services
- **Perl** (services/regexer): Dictionary parsing via gRPC
- **Rust** (services/phonetic-rs): Phonetic distance computation via PyO3

### Frontend (SvelteKit)
- D3.js network visualizations
- Cytoscape.js for graph exploration
- TypeScript for type safety

## Project Structure

```
LangViz/
├── backend/
│   ├── api/              # FastAPI routes
│   ├── core/             # Domain models & contracts
│   ├── services/         # Business logic
│   ├── storage/          # Repositories
│   └── interop/          # gRPC clients
├── services/
│   ├── regexer/          # Perl dictionary parser
│   └── phonetic-rs/      # Rust phonetic module
└── frontend/
    ├── src/
    │   ├── api/          # API client
    │   ├── viz/          # Visualizations
    │   └── routes/       # Pages
    └── package.json
```

## Setup

### Prerequisites
- Python 3.11+
- Perl 5.38+
- Rust 1.70+
- Node.js 20+
- Docker & Docker Compose

### Quick Start

1. **Clone and setup environment:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

2. **Start services:**
```bash
docker-compose up -d
```

3. **Install Python dependencies:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
pip install -r requirements.txt
```

4. **Build Rust module:**
```bash
cd services/phonetic-rs
pip install maturin
maturin develop --release
```

5. **Install Perl dependencies:**
```bash
cd services/regexer
cpanm --installdeps .
```

6. **Install frontend dependencies:**
```bash
cd frontend
npm install
```

7. **Run development servers:**
```bash
# Backend (from backend/)
python3 -m backend.main

# Frontend (from frontend/)
npm run dev
```

## Development

### Backend Testing
```bash
cd backend
pytest

# Run specific test file
pytest tests/test_cleaners.py

# With coverage
pytest --cov=backend tests/
```

### Data Ingestion
```bash
cd backend

# Ingest example Swadesh list
python3 -m cli.ingest ingest \
  --file ../data/raw/example_swadesh.csv \
  --source swadesh_207 \
  --format csv \
  --catalog ../data/sources/catalog.toml

# Validate data quality
python3 -m cli.ingest validate --limit 100
```

### Type Checking
```bash
cd backend
mypy .
```

### Frontend Development
```bash
cd frontend
npm run dev
```

## Design Principles

- **Elegance**: Clean separation of concerns
- **Extensibility**: Protocol-based contracts
- **Testability**: Dependency injection throughout
- **Strong Typing**: No `any` types, full type safety
- **Minimal Tech Debt**: Short, focused files with clear names

## License

MIT

