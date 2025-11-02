# Indo-European Etymology & Semantic Similarity Mapper
## Project Overview

**Goal**: Build a computational system to detect and visualize semantic relationships, cognate patterns, and etymological connections across Indo-European languages. The system will quantify similarity beyond simple string matching—accounting for systematic sound changes, borrowing patterns, and semantic drift.

## Architecture

**Orchestrator: Python 3.11+**
Primary coordination layer for data processing, analysis pipeline, and API services.

**Specialized Processing Layers:**
- **Perl 5.38+**: Dictionary parsing and text normalization. Perl's regex engine and text manipulation remain unmatched for messy linguistic data with inconsistent formats. Use for ETL from raw dictionary files. ✅ **IMPLEMENTED** (JSON-RPC service on port 50051)
- **R 4.0+**: Phylogenetic inference (ape/phangorn), bootstrap analysis, hierarchical clustering with statistical significance (pvclust), and publication-quality dendrograms. ✅ **IMPLEMENTED** (JSON-RPC service on port 50052)
- **Rust**: Phonetic distance computations, graph algorithms, sparse matrices, and clustering primitives. High-performance computational kernel via PyO3. ✅ **IMPLEMENTED** (Python extension module `langviz_core`)

## Backend Stack

**Core Libraries:**

*Linguistic Processing:*
- **epitran** (Python): IPA transcription across writing systems
- **panphon** (Python): Phonological feature vectors for sound comparison
- **Lingua::IPA** (Perl): IPA validation during ingestion
- **python-Levenshtein** (C-backed): Fast edit distance baseline

*NLP & Semantics:*
- **sentence-transformers** (paraphrase-multilingual-mpnet-base-v2): Multilingual semantic similarity ✅ **OPTIMAL CHOICE** (replaces fastText + MUSE)
- **UMAP + HDBSCAN**: Auto-discover cross-lingual semantic concepts ✅ **IMPLEMENTED**
- **spaCy with multilingual models**: Available for future POS tagging/lemmatization

*Data & Graph:*
- **PostgreSQL 16** with **pgvector** extension: Store embeddings, full-text search, efficient similarity queries ✅
- **Rust/petgraph** (50x faster than NetworkX): Graph construction and analysis ✅ **IMPLEMENTED**
- **Redis**: Cache frequently-accessed similarity computations ✅

*Etymology-Specific:*
- **LingPy**: Automated cognate detection with SCA (Sound Correspondence Analysis)
- **Lexibank/CLDF**: Access curated comparative wordlists in standardized format

*Statistical & Phylogenetic (via R):*
- **ape**: Phylogenetic tree inference, bootstrap analysis, tree manipulation
- **phangorn**: Maximum Likelihood phylogenetics, extended tree methods
- **pvclust**: Hierarchical clustering with bootstrap p-values

## Frontend Stack

**Framework: SvelteKit** (or Next.js if you prefer React)
- Server-side rendering for SEO
- Fast, reactive UI for filtering large datasets

**Visualization:**
- **D3.js**: Custom network graphs, phylogenetic trees
- **Cytoscape.js**: Interactive network exploration with layout algorithms
- **Plotly**: Statistical dashboards and heatmaps
- **deck.gl**: If you want geographic mapping overlay

**UI Components:**
- **shadcn/ui** or **DaisyUI**: Accessible component library
- **Tanstack Table**: Handle large sortable/filterable dictionary tables

## Pipeline Flow

1. **Ingestion** (Perl): Parse heterogeneous dictionary formats → normalized JSON
2. **Enrichment** (Python): IPA transcription, POS tagging, etymology extraction
3. **Embedding** (Python/sentence-transformers): Generate semantic vectors per entry
4. **Similarity Matrix** (Rust): Compute phonetic + semantic distances (10-50x faster)
5. **Graph Construction** (Rust/petgraph): Build weighted cognate network (50x faster)
6. **Clustering** (Rust + Python/HDBSCAN): Detect cognate sets and concept clusters
7. **Storage** (PostgreSQL): Index with similarity search capability
8. **API** (FastAPI/Python): Serve queries with caching layer
9. **Frontend** (Svelte/D3): Interactive exploration and visualization

## Data Model

**Core entities:**
- **Languages**: ISO codes, branch, subfamily, coordinates
- **Entries**: headword, IPA, definition, etymology, embeddings (vector)
- **Cognate_Sets**: grouped related words with confidence scores
- **Similarity_Edges**: pairwise scores (phonetic, semantic, combined)

## Deliverables

- RESTful API for similarity queries
- Interactive web interface with network visualization
- Exportable similarity matrices and cognate sets
- Documentation of discovered patterns (borrowings, semantic shifts, false friends)

**Estimated complexity**: 3-4 months for MVP with ~20 languages and 5,000 core concepts.