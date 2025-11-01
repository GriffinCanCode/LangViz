"""Storage layer for persistence and caching.

Barrel export for repositories, cleaners, pipelines, and ingest.
"""

from .repositories import EntryRepository, CognateRepository
from backend.interop.perl_client import PerlParserClient
from .cleaners import (
    IPACleaner,
    TextNormalizer,
    HeadwordCleaner,
    DefinitionCleaner,
    LanguageCodeCleaner,
    DuplicateDetector,
)
from .pipeline import Pipeline, PipelineFactory, compose
from .loaders import LoaderFactory, CLDFLoader, SwadeshLoader, StarlingLoader
from .ingest import IngestService
from .validators import EntryValidator, ValidatorFactory
from .provenance import Source, Provenance, TransformStep

__all__ = [
    # Repositories
    "EntryRepository",
    "CognateRepository",
    # Cleaners
    "IPACleaner",
    "TextNormalizer",
    "HeadwordCleaner",
    "DefinitionCleaner",
    "LanguageCodeCleaner",
    "DuplicateDetector",
    # Pipelines
    "Pipeline",
    "PipelineFactory",
    "compose",
    # Loaders
    "LoaderFactory",
    "CLDFLoader",
    "SwadeshLoader",
    "StarlingLoader",

    # Ingest
    "IngestService",
    # Validators
    "EntryValidator",
    "ValidatorFactory",
    # Provenance
    "Source",
    "Provenance",
    "TransformStep",
]

