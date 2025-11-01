"""Structured observability system using structlog.

Provides:
- Context-aware structured logging
- Automatic request ID tracking
- JSON output for production, pretty console for dev
- Zero-config logging with sensible defaults
- Performance timing utilities

Usage:
    from backend.observ import get_logger
    
    logger = get_logger(__name__)
    logger.info("processing_entry", entry_id="abc123", language="eng")
"""

import sys
import logging
from typing import Optional
from contextvars import ContextVar
from functools import wraps
from time import perf_counter

import structlog
from structlog.typing import EventDict, WrappedLogger

from backend.config import get_settings


# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


# ═════════════════════════════════════════════════════════════════════════════
# Structlog Configuration
# ═════════════════════════════════════════════════════════════════════════════

def add_context_fields(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict
) -> EventDict:
    """Add context variables to every log entry."""
    request_id = request_id_var.get()
    if request_id:
        event_dict["request_id"] = request_id
    
    user_id = user_id_var.get()
    if user_id:
        event_dict["user_id"] = user_id
    
    return event_dict


def configure_logging() -> None:
    """Configure structlog based on environment settings."""
    settings = get_settings()
    
    # Determine if we're in development mode
    is_dev = settings.debug or settings.log_level == "DEBUG"
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper())
    )
    
    # Build processor chain
    processors = [
        structlog.contextvars.merge_contextvars,
        add_context_fields,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    # Add format-specific processors
    if is_dev:
        # Development: pretty console output
        processors.extend([
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(colors=True)
        ])
    else:
        # Production: JSON for log aggregation
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ])
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Initialize on module import
configure_logging()


# ═════════════════════════════════════════════════════════════════════════════
# Logger Factory
# ═════════════════════════════════════════════════════════════════════════════

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger for the given module.
    
    Args:
        name: Module name (typically __name__)
    
    Returns:
        Bound logger with automatic context
    
    Example:
        logger = get_logger(__name__)
        logger.info("user_login", user_id="123", ip="1.2.3.4")
    """
    return structlog.get_logger(name)


# ═════════════════════════════════════════════════════════════════════════════
# Context Management
# ═════════════════════════════════════════════════════════════════════════════

def set_request_id(request_id: str) -> None:
    """Set request ID for current context."""
    request_id_var.set(request_id)


def set_user_id(user_id: str) -> None:
    """Set user ID for current context."""
    user_id_var.set(user_id)


def clear_context() -> None:
    """Clear all context variables."""
    request_id_var.set(None)
    user_id_var.set(None)


# ═════════════════════════════════════════════════════════════════════════════
# Performance Timing
# ═════════════════════════════════════════════════════════════════════════════

def timed(logger: Optional[structlog.stdlib.BoundLogger] = None):
    """Decorator to log function execution time.
    
    Args:
        logger: Logger to use (creates one if not provided)
    
    Example:
        @timed(logger)
        async def compute_similarity(a: str, b: str) -> float:
            ...
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration = perf_counter() - start
                logger.debug(
                    "function_completed",
                    function=func.__qualname__,
                    duration_ms=round(duration * 1000, 2),
                    success=True
                )
                return result
            except Exception as e:
                duration = perf_counter() - start
                logger.error(
                    "function_failed",
                    function=func.__qualname__,
                    duration_ms=round(duration * 1000, 2),
                    error=str(e),
                    error_type=type(e).__name__,
                    success=False
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = perf_counter() - start
                logger.debug(
                    "function_completed",
                    function=func.__qualname__,
                    duration_ms=round(duration * 1000, 2),
                    success=True
                )
                return result
            except Exception as e:
                duration = perf_counter() - start
                logger.error(
                    "function_failed",
                    function=func.__qualname__,
                    duration_ms=round(duration * 1000, 2),
                    error=str(e),
                    error_type=type(e).__name__,
                    success=False
                )
                raise
        
        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class timer:
    """Context manager for timing code blocks.
    
    Example:
        with timer(logger, "database_query"):
            results = await db.execute(query)
    """
    
    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger,
        operation: str,
        **context
    ):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = perf_counter()
        self.logger.debug(f"{self.operation}_started", **self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = perf_counter() - self.start_time
        if exc_type is None:
            self.logger.info(
                f"{self.operation}_completed",
                duration_ms=round(duration * 1000, 2),
                success=True,
                **self.context
            )
        else:
            self.logger.error(
                f"{self.operation}_failed",
                duration_ms=round(duration * 1000, 2),
                error=str(exc_val),
                error_type=exc_type.__name__,
                success=False,
                **self.context
            )
        return False  # Don't suppress exceptions


# ═════════════════════════════════════════════════════════════════════════════
# Specialized Loggers
# ═════════════════════════════════════════════════════════════════════════════

def log_database_query(
    logger: structlog.stdlib.BoundLogger,
    query: str,
    duration_ms: float,
    rows_affected: int = 0
) -> None:
    """Log database query with standardized fields."""
    logger.info(
        "database_query",
        query_preview=query[:100],
        duration_ms=round(duration_ms, 2),
        rows_affected=rows_affected
    )


def log_api_request(
    logger: structlog.stdlib.BoundLogger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **extra
) -> None:
    """Log API request with standardized fields."""
    level = "info" if status_code < 400 else "warning" if status_code < 500 else "error"
    getattr(logger, level)(
        "api_request",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=round(duration_ms, 2),
        **extra
    )


def log_service_call(
    logger: structlog.stdlib.BoundLogger,
    service: str,
    operation: str,
    duration_ms: float,
    success: bool = True,
    **extra
) -> None:
    """Log external service call with standardized fields."""
    level = "info" if success else "error"
    getattr(logger, level)(
        "service_call",
        service=service,
        operation=operation,
        duration_ms=round(duration_ms, 2),
        success=success,
        **extra
    )

