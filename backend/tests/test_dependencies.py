"""Tests for dependency injection system.

Verifies that singleton pattern works correctly and services are reused.
"""

import pytest
from backend.api.dependencies import (
    ServiceContainer,
    get_phonetic_service,
    get_semantic_service,
    get_cognate_service
)


class TestServiceContainer:
    """Test singleton service container behavior."""
    
    @classmethod
    def setup_class(cls):
        """Initialize services once for all tests."""
        ServiceContainer.initialize()
    
    @classmethod
    def teardown_class(cls):
        """Clean up services after all tests."""
        ServiceContainer.cleanup()
    
    def test_phonetic_service_is_singleton(self):
        """Verify PhoneticService returns same instance."""
        service1 = get_phonetic_service()
        service2 = get_phonetic_service()
        
        assert service1 is service2, "PhoneticService should be singleton"
    
    def test_semantic_service_is_singleton(self):
        """Verify SemanticService returns same instance."""
        service1 = get_semantic_service()
        service2 = get_semantic_service()
        
        assert service1 is service2, "SemanticService should be singleton"
        # Verify the model is loaded only once
        assert service1._model is not None
        assert service1._model is service2._model
    
    def test_cognate_service_is_singleton(self):
        """Verify CognateService returns same instance."""
        service1 = get_cognate_service()
        service2 = get_cognate_service()
        
        assert service1 is service2, "CognateService should be singleton"
    
    def test_cognate_service_uses_injected_dependencies(self):
        """Verify CognateService uses the singleton phonetic/semantic services."""
        cognate = get_cognate_service()
        phonetic = get_phonetic_service()
        semantic = get_semantic_service()
        
        # Verify dependency injection worked correctly
        assert cognate._phonetic is phonetic
        assert cognate._semantic is semantic
    
    def test_services_are_functional(self):
        """Verify services can actually perform their operations."""
        phonetic = get_phonetic_service()
        semantic = get_semantic_service()
        
        # Verify phonetic service is initialized
        assert phonetic._feature_table is not None
        
        # Test semantic service (this is the expensive one we're optimizing)
        embedding = semantic.get_embedding("test")
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)
    
    def test_error_when_not_initialized(self):
        """Verify proper error when accessing uninitialized services."""
        ServiceContainer.cleanup()  # Clear services
        
        with pytest.raises(RuntimeError, match="not initialized"):
            get_phonetic_service()
        
        with pytest.raises(RuntimeError, match="not initialized"):
            get_semantic_service()
        
        with pytest.raises(RuntimeError, match="not initialized"):
            get_cognate_service()
        
        # Re-initialize for other tests
        ServiceContainer.initialize()


class TestPerformanceImprovement:
    """Test that singleton pattern provides performance benefits."""
    
    @classmethod
    def setup_class(cls):
        """Initialize services."""
        ServiceContainer.initialize()
    
    @classmethod
    def teardown_class(cls):
        """Clean up services."""
        ServiceContainer.cleanup()
    
    def test_semantic_model_loaded_once(self):
        """Verify semantic model is loaded only once, not per-access."""
        import time
        
        # First access (should be fast since already initialized)
        start = time.time()
        service1 = get_semantic_service()
        first_time = time.time() - start
        
        # Second access (should be equally fast)
        start = time.time()
        service2 = get_semantic_service()
        second_time = time.time() - start
        
        # Both should be very fast (< 1ms) since model is already loaded
        assert first_time < 0.01, f"First access too slow: {first_time}s"
        assert second_time < 0.01, f"Second access too slow: {second_time}s"
        
        # And they should be the same instance
        assert service1 is service2
    
    def test_embedding_cache_works(self):
        """Verify semantic service caching works correctly."""
        semantic = get_semantic_service()
        
        # First embedding
        emb1 = semantic.get_embedding("test text")
        
        # Second embedding of same text (should be cached)
        emb2 = semantic.get_embedding("test text")
        
        # Should be identical (from cache)
        assert emb1 == emb2
        
        # Verify it's actually using the cache
        assert "test text" in semantic._cache

