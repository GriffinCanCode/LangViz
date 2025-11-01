"""FastAPI application entry point.

Configures application, middleware, and routes.
"""

import uuid
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api import router
from backend.api.dependencies import ServiceContainer
from backend.observ import get_logger, set_request_id, clear_context, log_api_request
from backend.errors import LangVizError, ErrorDetail, ErrorCode

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan for startup/shutdown tasks."""
    # Startup: Initialize services, connections
    logger.info("application_startup", version=app.version)
    ServiceContainer.initialize()
    yield
    # Shutdown: Clean up resources
    logger.info("application_shutdown")
    ServiceContainer.cleanup()


app = FastAPI(
    title="LangViz API",
    description="Indo-European Etymology & Semantic Similarity Analysis",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # SvelteKit dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(router)


# ═════════════════════════════════════════════════════════════════════════════
# Error Handlers
# ═════════════════════════════════════════════════════════════════════════════

@app.exception_handler(LangVizError)
async def langviz_error_handler(request: Request, exc: LangVizError) -> JSONResponse:
    """Handle all application-specific errors."""
    logger.warning(
        "application_error",
        error_code=exc.code.value,
        error_message=exc.message,
        path=request.url.path,
        **exc.context
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.to_detail().model_dump()}
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    logger.warning(
        "validation_error",
        path=request.url.path,
        errors=exc.errors()
    )
    
    return JSONResponse(
        status_code=400,
        content={
            "error": ErrorDetail(
                code=ErrorCode.INVALID_INPUT,
                message="Invalid request data",
                context={"details": exc.errors()}
            ).model_dump()
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """Handle HTTP exceptions."""
    logger.warning(
        "http_error",
        status_code=exc.status_code,
        path=request.url.path,
        detail=exc.detail
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": exc.detail}}
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""
    logger.error(
        "unhandled_error",
        error_type=type(exc).__name__,
        error_message=str(exc),
        path=request.url.path,
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": ErrorDetail(
                code=ErrorCode.DATABASE_ERROR,
                message="An unexpected error occurred"
            ).model_dump()
        }
    )


# ═════════════════════════════════════════════════════════════════════════════
# Request Logging Middleware
# ═════════════════════════════════════════════════════════════════════════════

@app.middleware("http")
async def logging_middleware(request: Request, call_next) -> Response:
    """Log all requests with timing and context."""
    request_id = str(uuid.uuid4())
    set_request_id(request_id)
    
    start_time = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - start_time) * 1000
    
    log_api_request(
        logger,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    response.headers["X-Request-ID"] = request_id
    clear_context()
    
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
