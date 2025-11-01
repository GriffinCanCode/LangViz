"""Dependency injection container for services.

Provides singleton service instances to avoid expensive re-initialization.
Services are initialized once at application startup and reused across requests.
"""

from typing import Optional
from backend.services import PhoneticService, SemanticService, CognateService, PhyloService


class ServiceContainer:
    """Container for singleton service instances."""
    
    _phonetic_service: Optional[PhoneticService] = None
    _semantic_service: Optional[SemanticService] = None
    _cognate_service: Optional[CognateService] = None
    _phylo_service: Optional[PhyloService] = None
    
    @classmethod
    def initialize(cls) -> None:
        """Initialize all services at application startup.
        
        This loads ML models and linguistic resources once,
        avoiding expensive re-initialization on every request.
        """
        print("Initializing services...")
        
        # Initialize phonetic service (loads panphon, epitran)
        print("  - Loading phonetic analysis resources...")
        cls._phonetic_service = PhoneticService()
        
        # Initialize semantic service (loads transformer model - expensive!)
        print("  - Loading semantic transformer model (this may take a moment)...")
        cls._semantic_service = SemanticService()
        
        # Initialize cognate service (depends on above services)
        print("  - Initializing cognate detection...")
        cls._cognate_service = CognateService(
            phonetic=cls._phonetic_service,
            semantic=cls._semantic_service
        )
        
        # Initialize phylo service (R integration optional)
        print("  - Initializing phylogenetic service...")
        cls._phylo_service = PhyloService(use_r=False)  # Enable with use_r=True when R service running
        
        print("Services initialized successfully!")
    
    @classmethod
    def get_phonetic_service(cls) -> PhoneticService:
        """Get singleton phonetic service instance."""
        if cls._phonetic_service is None:
            raise RuntimeError(
                "PhoneticService not initialized. "
                "Ensure ServiceContainer.initialize() is called at startup."
            )
        return cls._phonetic_service
    
    @classmethod
    def get_semantic_service(cls) -> SemanticService:
        """Get singleton semantic service instance."""
        if cls._semantic_service is None:
            raise RuntimeError(
                "SemanticService not initialized. "
                "Ensure ServiceContainer.initialize() is called at startup."
            )
        return cls._semantic_service
    
    @classmethod
    def get_cognate_service(cls) -> CognateService:
        """Get singleton cognate service instance."""
        if cls._cognate_service is None:
            raise RuntimeError(
                "CognateService not initialized. "
                "Ensure ServiceContainer.initialize() is called at startup."
            )
        return cls._cognate_service
    
    @classmethod
    def get_phylo_service(cls) -> PhyloService:
        """Get singleton phylo service instance."""
        if cls._phylo_service is None:
            raise RuntimeError(
                "PhyloService not initialized. "
                "Ensure ServiceContainer.initialize() is called at startup."
            )
        return cls._phylo_service
    
    @classmethod
    def cleanup(cls) -> None:
        """Clean up service resources at application shutdown."""
        print("Cleaning up services...")
        # Clear references to allow garbage collection
        cls._phonetic_service = None
        cls._semantic_service = None
        cls._cognate_service = None
        cls._phylo_service = None
        print("Services cleaned up!")


# FastAPI dependency functions
def get_phonetic_service() -> PhoneticService:
    """Provide phonetic service instance for dependency injection."""
    return ServiceContainer.get_phonetic_service()


def get_semantic_service() -> SemanticService:
    """Provide semantic service instance for dependency injection."""
    return ServiceContainer.get_semantic_service()


def get_cognate_service() -> CognateService:
    """Provide cognate service instance for dependency injection."""
    return ServiceContainer.get_cognate_service()


def get_phylo_service() -> PhyloService:
    """Provide phylo service instance for dependency injection."""
    return ServiceContainer.get_phylo_service()

