"""Type-safe exception hierarchy and error codes.

Provides structured error handling with:
- Domain-specific exception taxonomy
- HTTP status code mapping
- Structured error details
- FastAPI integration via middleware
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    """Type-safe error codes for API responses."""
    
    # Validation errors (400)
    INVALID_IPA = "invalid_ipa"
    INVALID_LANGUAGE = "invalid_language"
    INVALID_INPUT = "invalid_input"
    MISSING_FIELD = "missing_field"
    
    # Resource errors (404)
    ENTRY_NOT_FOUND = "entry_not_found"
    SOURCE_NOT_FOUND = "source_not_found"
    LANGUAGE_NOT_FOUND = "language_not_found"
    
    # Processing errors (422)
    TRANSFORMATION_FAILED = "transformation_failed"
    PIPELINE_FAILED = "pipeline_failed"
    EMBEDDING_FAILED = "embedding_failed"
    
    # Service errors (500)
    DATABASE_ERROR = "database_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    RUST_BACKEND_ERROR = "rust_backend_error"
    
    # Resource limits (429)
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    
    # Not implemented (501)
    NOT_IMPLEMENTED = "not_implemented"


class ErrorDetail(BaseModel):
    """Structured error information for API responses."""
    
    code: ErrorCode
    message: str
    field: Optional[str] = None
    context: dict = Field(default_factory=dict)


class LangVizError(Exception):
    """Base exception for all application errors.
    
    Provides structured error information and HTTP status mapping.
    """
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        field: Optional[str] = None,
        status_code: int = 500,
        **context
    ):
        self.code = code
        self.message = message
        self.field = field
        self.status_code = status_code
        self.context = context
        super().__init__(message)
    
    def to_detail(self) -> ErrorDetail:
        """Convert to API error detail."""
        return ErrorDetail(
            code=self.code,
            message=self.message,
            field=self.field,
            context=self.context
        )


# ═════════════════════════════════════════════════════════════════════════════
# Validation Errors (400)
# ═════════════════════════════════════════════════════════════════════════════

class ValidationError(LangVizError):
    """Invalid input data."""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INVALID_INPUT,
        field: Optional[str] = None,
        **context
    ):
        super().__init__(
            code=code,
            message=message,
            field=field,
            status_code=400,
            **context
        )


class InvalidIPAError(ValidationError):
    """IPA string is malformed or contains invalid segments."""
    
    def __init__(self, ipa: str, reason: Optional[str] = None):
        message = f"Invalid IPA: {ipa}"
        if reason:
            message += f" ({reason})"
        super().__init__(
            message=message,
            code=ErrorCode.INVALID_IPA,
            field="ipa",
            ipa=ipa,
            reason=reason
        )


class InvalidLanguageError(ValidationError):
    """Language code is not supported or malformed."""
    
    def __init__(self, language: str):
        super().__init__(
            message=f"Invalid language code: {language}",
            code=ErrorCode.INVALID_LANGUAGE,
            field="language",
            language=language
        )


# ═════════════════════════════════════════════════════════════════════════════
# Resource Errors (404)
# ═════════════════════════════════════════════════════════════════════════════

class ResourceNotFoundError(LangVizError):
    """Requested resource does not exist."""
    
    def __init__(
        self,
        resource_type: str,
        identifier: str,
        code: ErrorCode = ErrorCode.ENTRY_NOT_FOUND
    ):
        super().__init__(
            code=code,
            message=f"{resource_type} not found: {identifier}",
            status_code=404,
            resource_type=resource_type,
            identifier=identifier
        )


# ═════════════════════════════════════════════════════════════════════════════
# Processing Errors (422)
# ═════════════════════════════════════════════════════════════════════════════

class ProcessingError(LangVizError):
    """Data processing or transformation failed."""
    
    def __init__(
        self,
        operation: str,
        reason: str,
        code: ErrorCode = ErrorCode.TRANSFORMATION_FAILED,
        **context
    ):
        super().__init__(
            code=code,
            message=f"{operation} failed: {reason}",
            status_code=422,
            operation=operation,
            reason=reason,
            **context
        )


class PipelineError(ProcessingError):
    """Cleaning or transformation pipeline failed."""
    
    def __init__(
        self,
        pipeline: str,
        step: str,
        reason: str,
        **context
    ):
        super().__init__(
            operation=f"Pipeline '{pipeline}' at step '{step}'",
            reason=reason,
            code=ErrorCode.PIPELINE_FAILED,
            pipeline=pipeline,
            step=step,
            **context
        )


class EmbeddingError(ProcessingError):
    """Semantic embedding generation failed."""
    
    def __init__(self, text: str, reason: str):
        super().__init__(
            operation="Embedding generation",
            reason=reason,
            code=ErrorCode.EMBEDDING_FAILED,
            text=text
        )


# ═════════════════════════════════════════════════════════════════════════════
# Service Errors (500)
# ═════════════════════════════════════════════════════════════════════════════

class ServiceError(LangVizError):
    """Internal service or infrastructure failure."""
    
    def __init__(
        self,
        service: str,
        reason: str,
        code: ErrorCode = ErrorCode.EXTERNAL_SERVICE_ERROR,
        **context
    ):
        super().__init__(
            code=code,
            message=f"Service error in {service}: {reason}",
            status_code=500,
            service=service,
            reason=reason,
            **context
        )


class DatabaseError(ServiceError):
    """Database operation failed."""
    
    def __init__(self, operation: str, reason: str, **context):
        super().__init__(
            service="database",
            reason=f"{operation} failed: {reason}",
            code=ErrorCode.DATABASE_ERROR,
            operation=operation,
            **context
        )


class RustBackendError(ServiceError):
    """Rust microservice call failed."""
    
    def __init__(self, operation: str, reason: str):
        super().__init__(
            service="rust_backend",
            reason=f"{operation}: {reason}",
            code=ErrorCode.RUST_BACKEND_ERROR,
            operation=operation
        )


# ═════════════════════════════════════════════════════════════════════════════
# Rate Limiting (429)
# ═════════════════════════════════════════════════════════════════════════════

class RateLimitError(LangVizError):
    """Rate limit exceeded."""
    
    def __init__(self, limit: int, window: str, retry_after: Optional[int] = None):
        message = f"Rate limit exceeded: {limit} requests per {window}"
        if retry_after:
            message += f". Retry after {retry_after}s"
        
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            status_code=429,
            limit=limit,
            window=window,
            retry_after=retry_after
        )


# ═════════════════════════════════════════════════════════════════════════════
# Not Implemented (501)
# ═════════════════════════════════════════════════════════════════════════════

class NotImplementedError(LangVizError):
    """Feature not yet implemented."""
    
    def __init__(self, feature: str):
        super().__init__(
            code=ErrorCode.NOT_IMPLEMENTED,
            message=f"Not implemented: {feature}",
            status_code=501,
            feature=feature
        )

