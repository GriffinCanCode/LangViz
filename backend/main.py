"""FastAPI application entry point.

Configures application, middleware, and routes.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan for startup/shutdown tasks."""
    # Startup: Initialize services, connections
    print("Starting LangViz Backend...")
    yield
    # Shutdown: Clean up resources
    print("Shutting down LangViz Backend...")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

