"""LangViz Backend - Indo-European Etymology Analysis System.

Main orchestration layer coordinating services, storage, and API.
"""

__version__ = "0.1.0"

# Observability exports for convenience
from backend.observ import get_logger, timer, timed
from backend.errors import (
    LangVizError,
    ErrorCode,
    ValidationError,
    InvalidIPAError,
    InvalidLanguageError,
    ResourceNotFoundError,
    ProcessingError,
    PipelineError,
    EmbeddingError,
    ServiceError,
    DatabaseError,
    RustBackendError,
    RateLimitError,
    NotImplementedError,
)

__all__ = [
    # Version
    "__version__",
    # Logging
    "get_logger",
    "timer",
    "timed",
    # Errors
    "LangVizError",
    "ErrorCode",
    "ValidationError",
    "InvalidIPAError",
    "InvalidLanguageError",
    "ResourceNotFoundError",
    "ProcessingError",
    "PipelineError",
    "EmbeddingError",
    "ServiceError",
    "DatabaseError",
    "RustBackendError",
    "RateLimitError",
    "NotImplementedError",
]

