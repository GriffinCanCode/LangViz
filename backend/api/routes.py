"""FastAPI route definitions.

Thin routing layer that delegates to services.
Follows REST conventions with proper status codes.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from backend.core import Entry, SimilarityScore, CognateSet
from backend.services import PhoneticService, SemanticService, CognateService


router = APIRouter(prefix="/api/v1")


# Dependency injection
def get_phonetic_service() -> PhoneticService:
    """Provide phonetic service instance."""
    return PhoneticService()


def get_semantic_service() -> SemanticService:
    """Provide semantic service instance."""
    return SemanticService()


def get_cognate_service(
    phonetic: PhoneticService = Depends(get_phonetic_service),
    semantic: SemanticService = Depends(get_semantic_service)
) -> CognateService:
    """Provide cognate service instance."""
    return CognateService(phonetic, semantic)


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.post("/entries")
async def create_entry(entry: Entry):
    """Create a new lexical entry."""
    # TODO: Implement repository save
    raise HTTPException(501, "Not implemented")


@router.get("/entries/{entry_id}")
async def get_entry(entry_id: str):
    """Retrieve entry by ID."""
    # TODO: Implement repository fetch
    raise HTTPException(501, "Not implemented")


@router.post("/similarity")
async def compute_similarity(
    ipa_a: str,
    ipa_b: str,
    phonetic: PhoneticService = Depends(get_phonetic_service)
) -> dict[str, float]:
    """Compute phonetic similarity between IPA strings."""
    distance = phonetic.compute_distance(ipa_a, ipa_b)
    return {"distance": distance}


@router.post("/cognates/detect")
async def detect_cognates(
    entries: list[Entry],
    cognate: CognateService = Depends(get_cognate_service)
) -> list[CognateSet]:
    """Detect cognate sets from entry list."""
    return cognate.detect_cognates(entries)


@router.get("/embeddings")
async def get_embedding(
    text: str = Query(..., min_length=1),
    semantic: SemanticService = Depends(get_semantic_service)
) -> dict[str, list[float]]:
    """Generate semantic embedding for text."""
    embedding = semantic.get_embedding(text)
    return {"embedding": embedding}

