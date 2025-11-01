"""FastAPI route definitions.

Thin routing layer that delegates to services.
Follows REST conventions with proper status codes.
"""

from fastapi import APIRouter, Depends, Query

from backend.core import Entry, SimilarityScore, CognateSet
from backend.services import PhoneticService, SemanticService, CognateService
from backend.api.dependencies import (
    get_phonetic_service,
    get_semantic_service,
    get_cognate_service
)
from backend.observ import get_logger
from backend.errors import (
    InvalidIPAError,
    NotImplementedError,
    EmbeddingError,
    ProcessingError
)


logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1")


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.post("/entries")
async def create_entry(entry: Entry):
    """Create a new lexical entry."""
    logger.info("create_entry_requested", entry_id=entry.id, language=entry.language)
    # TODO: Implement repository save
    raise NotImplementedError("Entry creation")


@router.get("/entries/{entry_id}")
async def get_entry(entry_id: str):
    """Retrieve entry by ID."""
    logger.info("get_entry_requested", entry_id=entry_id)
    # TODO: Implement repository fetch
    raise NotImplementedError("Entry retrieval")


@router.post("/similarity")
async def compute_similarity(
    ipa_a: str,
    ipa_b: str,
    phonetic: PhoneticService = Depends(get_phonetic_service)
) -> dict[str, float]:
    """Compute phonetic similarity between IPA strings."""
    logger.info("similarity_requested", ipa_a=ipa_a, ipa_b=ipa_b)
    
    try:
        distance = phonetic.compute_distance(ipa_a, ipa_b)
        logger.debug("similarity_computed", distance=distance)
        return {"distance": distance}
    except ValueError as e:
        # Convert ValueError from phonetic service to InvalidIPAError
        raise InvalidIPAError(f"{ipa_a} or {ipa_b}", str(e))


@router.post("/cognates/detect")
async def detect_cognates(
    entries: list[Entry],
    cognate: CognateService = Depends(get_cognate_service)
) -> list[CognateSet]:
    """Detect cognate sets from entry list."""
    logger.info("cognate_detection_requested", entry_count=len(entries))
    
    try:
        cognate_sets = cognate.detect_cognates(entries)
        logger.info("cognate_detection_completed", cognate_count=len(cognate_sets))
        return cognate_sets
    except Exception as e:
        raise ProcessingError("Cognate detection", str(e), entry_count=len(entries))


@router.get("/embeddings")
async def get_embedding(
    text: str = Query(..., min_length=1),
    semantic: SemanticService = Depends(get_semantic_service)
) -> dict[str, list[float]]:
    """Generate semantic embedding for text."""
    logger.info("embedding_requested", text_length=len(text))
    
    try:
        embedding = semantic.get_embedding(text)
        logger.debug("embedding_generated", dimensions=len(embedding))
        return {"embedding": embedding}
    except Exception as e:
        raise EmbeddingError(text, str(e))

