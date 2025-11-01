"""Examples demonstrating the observability system.

This file shows common patterns for logging and error handling.
Run with: python3 -m backend.examples_observability
"""

from backend.observ import get_logger, timer, timed
from backend.errors import (
    InvalidIPAError,
    ProcessingError,
    DatabaseError,
    ErrorCode
)

logger = get_logger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Basic Logging Examples
# ═════════════════════════════════════════════════════════════════════════════

def example_basic_logging():
    """Demonstrate basic structured logging."""
    logger.info("application_started", version="0.1.0", environment="development")
    
    # Log with multiple context fields
    logger.info(
        "processing_entry",
        entry_id="entry-123",
        language="eng",
        headword="hello"
    )
    
    # Debug logging
    logger.debug("cache_hit", key="embeddings:hello", ttl=3600)
    
    # Warning
    logger.warning("approaching_rate_limit", current=95, limit=100)
    
    # Error with exception info
    try:
        result = 1 / 0
    except ZeroDivisionError as e:
        logger.error(
            "calculation_failed",
            operation="division",
            error=str(e),
            exc_info=True
        )


# ═════════════════════════════════════════════════════════════════════════════
# Error Handling Examples
# ═════════════════════════════════════════════════════════════════════════════

def example_validation_errors():
    """Demonstrate validation error handling."""
    ipa = "xyz"
    
    if not is_valid_ipa(ipa):
        # Raises a 400 error with structured details
        raise InvalidIPAError(ipa, "Contains invalid segments")


def example_processing_errors():
    """Demonstrate processing error handling."""
    try:
        result = complex_computation()
    except Exception as e:
        # Raises a 422 error with context
        raise ProcessingError(
            "complex_computation",
            str(e),
            input_size=1000,
            attempted_retries=3
        )


def example_database_errors():
    """Demonstrate database error handling."""
    try:
        execute_query("SELECT * FROM entries")
    except Exception as e:
        # Raises a 500 error with query context
        raise DatabaseError(
            "SELECT",
            str(e),
            table="entries",
            timeout_seconds=30
        )


# ═════════════════════════════════════════════════════════════════════════════
# Performance Timing Examples
# ═════════════════════════════════════════════════════════════════════════════

def example_timer_context():
    """Demonstrate context manager timing."""
    with timer(logger, "batch_processing", batch_size=1000):
        # Simulated work
        import time
        time.sleep(0.1)
    
    # Automatically logs:
    # batch_processing_started batch_size=1000
    # batch_processing_completed duration_ms=100.23 success=True batch_size=1000


@timed(logger)
def example_timed_function(items: list[str]) -> list[str]:
    """Demonstrate function timing decorator."""
    # Automatically logs entry and exit with duration
    import time
    time.sleep(0.05)
    return [item.upper() for item in items]


# ═════════════════════════════════════════════════════════════════════════════
# Service Integration Examples
# ═════════════════════════════════════════════════════════════════════════════

class ExampleService:
    """Example service demonstrating logging patterns."""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.logger.info("service_initialized")
    
    def process_entry(self, entry_id: str) -> dict:
        """Process an entry with comprehensive logging."""
        self.logger.info("processing_started", entry_id=entry_id)
        
        try:
            # Step 1: Validate
            self.logger.debug("validating_entry", entry_id=entry_id)
            self._validate(entry_id)
            
            # Step 2: Transform
            with timer(self.logger, "transformation", entry_id=entry_id):
                result = self._transform(entry_id)
            
            # Step 3: Complete
            self.logger.info(
                "processing_completed",
                entry_id=entry_id,
                result_size=len(str(result))
            )
            
            return result
            
        except ValueError as e:
            self.logger.warning("validation_failed", entry_id=entry_id, error=str(e))
            raise InvalidIPAError(entry_id, str(e))
        
        except Exception as e:
            self.logger.error(
                "processing_failed",
                entry_id=entry_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise ProcessingError("entry_processing", str(e), entry_id=entry_id)
    
    def _validate(self, entry_id: str) -> None:
        """Validation logic."""
        pass
    
    def _transform(self, entry_id: str) -> dict:
        """Transformation logic."""
        return {"id": entry_id, "status": "processed"}


# ═════════════════════════════════════════════════════════════════════════════
# FastAPI Route Examples
# ═════════════════════════════════════════════════════════════════════════════

"""
Example FastAPI route with proper error handling:

from fastapi import APIRouter
from backend.observ import get_logger
from backend.errors import InvalidIPAError, ProcessingError

router = APIRouter()
logger = get_logger(__name__)

@router.post("/analyze")
async def analyze_text(text: str) -> dict:
    '''Analyze text with comprehensive logging and error handling.'''
    logger.info("analyze_requested", text_length=len(text))
    
    try:
        # Validate input
        if not text.strip():
            raise ValidationError("Text cannot be empty", field="text")
        
        # Process
        with timer(logger, "text_analysis", text_length=len(text)):
            result = perform_analysis(text)
        
        logger.info("analyze_completed", result_items=len(result))
        return result
        
    except ValueError as e:
        # Convert to typed error (auto-handled by middleware)
        raise InvalidIPAError(text, str(e))
    
    except Exception as e:
        # Log unexpected errors
        logger.error(
            "analyze_failed",
            text_length=len(text),
            error=str(e),
            exc_info=True
        )
        raise ProcessingError("text_analysis", str(e), text_length=len(text))
"""


# ═════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═════════════════════════════════════════════════════════════════════════════

def is_valid_ipa(ipa: str) -> bool:
    """Dummy validation function."""
    return len(ipa) > 0 and not ipa.isdigit()


def complex_computation():
    """Dummy computation."""
    raise ValueError("Simulated computation error")


def execute_query(query: str):
    """Dummy database query."""
    raise TimeoutError("Connection timeout")


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("examples_started")
    
    # Run examples
    example_basic_logging()
    
    # Uncomment to see error examples:
    # try:
    #     example_validation_errors()
    # except InvalidIPAError as e:
    #     logger.info("caught_error", code=e.code, status=e.status_code)
    
    example_timer_context()
    result = example_timed_function(["hello", "world"])
    logger.info("timed_result", result=result)
    
    # Service example
    service = ExampleService()
    # Uncomment to see service logging:
    # service.process_entry("entry-123")
    
    logger.info("examples_completed")

