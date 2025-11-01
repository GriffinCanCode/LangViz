# Observability System

## Overview

LangViz uses a **unified observability system** built on `structlog` for production-grade structured logging and type-safe error handling. This system provides:

- **Structured logging** with automatic context propagation
- **Type-safe error taxonomy** preventing bugs at compile time
- **Automatic request tracking** via middleware
- **Zero-config setup** with sensible defaults
- **Performance timing** utilities

## Architecture

### Core Modules

1. **`backend/observ.py`** - Structured logging and context management
2. **`backend/errors.py`** - Exception hierarchy and error codes

### Design Principles

1. **Errors are events** - Every error is logged with context
2. **Context flows automatically** - Request IDs propagate through async calls
3. **Type safety** - Error codes are enums, preventing typos
4. **Separation of concerns** - Services don't handle HTTP responses
5. **Production ready** - JSON logs for aggregation, pretty console for dev

## Quick Start

### Basic Logging

```python
from backend.observ import get_logger

logger = get_logger(__name__)

# Structured logging with context
logger.info("user_action", user_id="123", action="login", ip="1.2.3.4")

# Automatic request ID included in all logs
logger.warning("rate_limit_approached", user_id="123", requests=95)

# Error logging with automatic context
logger.error("database_query_failed", query="SELECT...", error=str(e))
```

### Error Handling

```python
from backend.errors import (
    InvalidIPAError,
    DatabaseError,
    ProcessingError
)

# In services
def validate_ipa(ipa: str) -> None:
    if not is_valid(ipa):
        raise InvalidIPAError(ipa, "Contains invalid segments")

# In routes (errors auto-converted to HTTP responses)
@router.post("/similarity")
async def compute_similarity(ipa_a: str, ipa_b: str):
    try:
        return phonetic.compute_distance(ipa_a, ipa_b)
    except ValueError as e:
        raise InvalidIPAError(f"{ipa_a} or {ipa_b}", str(e))
```

### Performance Timing

```python
from backend.observ import get_logger, timer, timed

logger = get_logger(__name__)

# Context manager for timing blocks
async def process_batch():
    with timer(logger, "batch_processing", batch_size=1000):
        results = await process_entries()

# Decorator for timing functions
@timed(logger)
async def compute_similarity(a: str, b: str) -> float:
    return distance(a, b)
```

## Error Types

### Validation Errors (400)

```python
from backend.errors import ValidationError, InvalidIPAError, InvalidLanguageError

# Generic validation
raise ValidationError("Invalid format", field="headword")

# Specific IPA validation
raise InvalidIPAError("xyz", "Not valid IPA")

# Language code validation
raise InvalidLanguageError("zz")
```

### Resource Errors (404)

```python
from backend.errors import ResourceNotFoundError

raise ResourceNotFoundError("Entry", "entry-123")
```

### Processing Errors (422)

```python
from backend.errors import ProcessingError, PipelineError, EmbeddingError

# Generic processing error
raise ProcessingError("Phonetic alignment", "Sequences too different")

# Pipeline-specific error
raise PipelineError("cleaning", "normalize_unicode", "Invalid encoding")

# Embedding generation error
raise EmbeddingError("hello world", "Model not loaded")
```

### Service Errors (500)

```python
from backend.errors import ServiceError, DatabaseError, RustBackendError

# Database errors
raise DatabaseError("INSERT", "Connection timeout")

# External service errors
raise RustBackendError("phonetic_distance", "gRPC connection failed")
```

## Structured Log Format

### Development Mode

Pretty console output with colors:

```
2024-01-15T10:30:45.123456Z [info     ] similarity_requested    ipa_a=hɛloʊ ipa_b=halo request_id=abc-123
2024-01-15T10:30:45.234567Z [debug    ] similarity_computed     distance=0.87 request_id=abc-123
```

### Production Mode

JSON logs for aggregation (compatible with ELK, Datadog, etc.):

```json
{
  "event": "similarity_requested",
  "level": "info",
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "logger": "backend.api.routes",
  "ipa_a": "hɛloʊ",
  "ipa_b": "halo",
  "request_id": "abc-123"
}
```

## Context Management

### Request Context

Request IDs are automatically generated and propagated:

```python
# Middleware automatically sets request ID
# All logs within the request include it

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    set_request_id(request_id)
    # ... rest of request
    clear_context()
```

### Custom Context

Add your own context variables:

```python
from backend.observ import set_user_id, get_logger

logger = get_logger(__name__)

async def authenticate(user_id: str):
    set_user_id(user_id)
    logger.info("user_authenticated")  # Automatically includes user_id
```

## FastAPI Integration

### Error Handlers

All errors are caught by middleware and converted to consistent JSON responses:

```python
# Application error (structured)
{
  "error": {
    "code": "invalid_ipa",
    "message": "Invalid IPA: xyz (No valid segments found)",
    "field": "ipa",
    "context": {
      "ipa": "xyz",
      "reason": "No valid segments found"
    }
  }
}

# Validation error (Pydantic)
{
  "error": {
    "code": "invalid_input",
    "message": "Invalid request data",
    "context": {
      "details": [...]
    }
  }
}
```

### Response Headers

Every response includes the request ID:

```
X-Request-ID: abc-def-123-456
```

## Configuration

Configure via environment variables:

```bash
# .env
LOG_LEVEL=DEBUG          # DEBUG, INFO, WARNING, ERROR
DEBUG=true               # Enable development mode (pretty console)
```

Or in code:

```python
from backend.config import Settings

settings = Settings()
print(settings.log_level)  # "INFO"
```

## Best Practices

### 1. Use Structured Fields

❌ **Bad:**
```python
logger.info(f"User {user_id} logged in from {ip}")
```

✅ **Good:**
```python
logger.info("user_login", user_id=user_id, ip=ip)
```

### 2. Use Specific Error Types

❌ **Bad:**
```python
raise ValueError("Invalid IPA")
```

✅ **Good:**
```python
raise InvalidIPAError(ipa, "Contains invalid segments")
```

### 3. Let Middleware Handle HTTP

❌ **Bad:**
```python
try:
    result = service.compute()
except Exception as e:
    return JSONResponse(500, {"error": str(e)})
```

✅ **Good:**
```python
try:
    result = service.compute()
except ValueError as e:
    raise ProcessingError("computation", str(e))
```

### 4. Include Context in Errors

❌ **Bad:**
```python
raise DatabaseError("Query failed", "Timeout")
```

✅ **Good:**
```python
raise DatabaseError(
    "Query failed",
    "Timeout",
    query=query[:100],
    duration_ms=1500
)
```

### 5. Use Performance Timing

```python
# For critical paths
with timer(logger, "expensive_operation", batch_size=1000):
    results = process_large_batch()

# For all service methods
@timed(logger)
async def compute_embeddings(texts: list[str]):
    return model.encode(texts)
```

## Testing

### Capture Logs in Tests

```python
import structlog
from structlog.testing import LogCapture

def test_logging():
    cap = LogCapture()
    structlog.configure(processors=[cap])
    
    logger = get_logger(__name__)
    logger.info("test_event", value=42)
    
    assert cap.entries[0]["event"] == "test_event"
    assert cap.entries[0]["value"] == 42
```

### Test Error Handling

```python
from backend.errors import InvalidIPAError

def test_invalid_ipa():
    with pytest.raises(InvalidIPAError) as exc:
        service.validate("xyz")
    
    assert exc.value.code == ErrorCode.INVALID_IPA
    assert exc.value.status_code == 400
```

## Migration Guide

### Replacing Old Logging

**Before:**
```python
import logging
logger = logging.getLogger(__name__)
logger.info(f"Processing entry {entry_id}")
```

**After:**
```python
from backend.observ import get_logger
logger = get_logger(__name__)
logger.info("processing_entry", entry_id=entry_id)
```

### Replacing Print Statements

**Before:**
```python
print(f"Error: {e}")
```

**After:**
```python
from backend.observ import get_logger
logger = get_logger(__name__)
logger.error("operation_failed", error=str(e))
```

### Replacing HTTPException

**Before:**
```python
from fastapi import HTTPException

if not valid:
    raise HTTPException(400, "Invalid input")
```

**After:**
```python
from backend.errors import ValidationError

if not valid:
    raise ValidationError("Invalid input", field="field_name")
```

## Advanced Usage

### Custom Error Types

Add new errors to `backend/errors.py`:

```python
class CustomError(LangVizError):
    def __init__(self, message: str, **context):
        super().__init__(
            code=ErrorCode.CUSTOM_ERROR,  # Add to enum
            message=message,
            status_code=422,
            **context
        )
```

### Specialized Logging

```python
from backend.observ import log_database_query, log_service_call

# Database operations
log_database_query(
    logger,
    query="SELECT * FROM entries",
    duration_ms=45.2,
    rows_affected=100
)

# External service calls
log_service_call(
    logger,
    service="rust_backend",
    operation="phonetic_distance",
    duration_ms=12.3,
    success=True
)
```

## Performance Impact

- **Structlog overhead**: ~2-5μs per log call
- **Context variables**: ~0.5μs per lookup
- **JSON serialization**: ~10-20μs per log entry
- **Total impact**: Negligible for most applications

## Monitoring Integration

The structured JSON logs integrate seamlessly with:

- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Datadog**
- **Splunk**
- **CloudWatch Logs**
- **Grafana Loki**

Example Datadog query:
```
service:langviz error_code:invalid_ipa @request_id:"abc-123"
```

## Further Reading

- [structlog documentation](https://www.structlog.org/)
- [FastAPI exception handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [Structured logging best practices](https://www.structlog.org/en/stable/why.html)

