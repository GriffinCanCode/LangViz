# Dependency Injection System

## Overview

The LangViz backend uses a **singleton pattern** for service dependencies to avoid expensive re-initialization of ML models and linguistic resources on every request.

## Architecture

### ServiceContainer (`backend.api.dependencies.ServiceContainer`)

A centralized container that manages singleton service instances:

- **PhoneticService**: Loads panphon feature tables and epitran transliterators
- **SemanticService**: Loads transformer models (expensive! ~500MB+)
- **CognateService**: Depends on the above services

### Lifecycle

```
Application Startup → ServiceContainer.initialize()
  ├─ Load PhoneticService (panphon, epitran)
  ├─ Load SemanticService (transformer model)
  └─ Initialize CognateService (with injected dependencies)

Request → Dependency Injection → Reuse Singleton Instances

Application Shutdown → ServiceContainer.cleanup()
```

## Implementation

### Startup (main.py)

```python
from backend.api.dependencies import ServiceContainer

@asynccontextmanager
async def lifespan(app: FastAPI):
    ServiceContainer.initialize()  # Load services once
    yield
    ServiceContainer.cleanup()      # Clean up on shutdown
```

### Route Dependencies (routes.py)

```python
from backend.api.dependencies import (
    get_phonetic_service,
    get_semantic_service,
    get_cognate_service
)

@router.post("/similarity")
async def compute_similarity(
    ipa_a: str,
    ipa_b: str,
    phonetic: PhoneticService = Depends(get_phonetic_service)  # Singleton instance
):
    return phonetic.compute_distance(ipa_a, ipa_b)
```

## Benefits

1. **Performance**: Transformer model loaded once at startup (not per-request)
2. **Memory Efficiency**: Single model instance in memory, not N copies
3. **Fast Response Times**: No model loading delay on each request
4. **Resource Reuse**: Panphon/epitran transliterators cached and shared

## Performance Impact

### Before (Per-Request Initialization)
- **First Request**: ~2-5 seconds (model loading)
- **Memory**: N × 500MB (N concurrent requests)
- **CPU**: Repeated deserialization of model weights

### After (Singleton Pattern)
- **Startup**: ~2-5 seconds (one-time cost)
- **Per Request**: ~10-100ms (actual computation only)
- **Memory**: 500MB (shared instance)
- **CPU**: Computation only, no loading overhead

## Thread Safety

FastAPI runs with async workers, but each worker process has its own memory space. The singleton pattern is safe within each worker. For true multi-threaded scenarios, consider adding locks if needed.

## Testing

Services can be mocked by replacing the singleton instances in `ServiceContainer` before tests run:

```python
# In test setup
ServiceContainer._semantic_service = MockSemanticService()
```

## Future Enhancements

- Add health checks that verify service initialization
- Implement lazy loading for rarely-used services
- Add metrics for service usage and performance
- Consider caching strategies for frequently-accessed data

