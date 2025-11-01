"""Composable data cleaning pipeline.

Functional composition of cleaners with automatic provenance tracking.
"""

from typing import TypeVar, Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime
from backend.core.contracts import ICleaner
from backend.storage.provenance import TransformStep


T = TypeVar('T')


@dataclass
class Pipeline:
    """Composable transformation pipeline.
    
    Applies sequence of cleaners while tracking provenance.
    Pure functional design - no side effects.
    """
    
    cleaners: list[ICleaner] = field(default_factory=list)
    strict: bool = True  # Fail on validation errors
    
    def add(self, cleaner: ICleaner) -> 'Pipeline':
        """Add cleaner to pipeline (returns new pipeline)."""
        return Pipeline(
            cleaners=self.cleaners + [cleaner],
            strict=self.strict
        )
    
    def compose(self, other: 'Pipeline') -> 'Pipeline':
        """Compose two pipelines."""
        return Pipeline(
            cleaners=self.cleaners + other.cleaners,
            strict=self.strict and other.strict
        )
    
    def apply(
        self,
        value: T,
        track_provenance: bool = True,
        **params
    ) -> tuple[T, Optional[list[TransformStep]]]:
        """Apply pipeline to value.
        
        Returns (cleaned_value, provenance_steps).
        """
        result = value
        steps = [] if track_provenance else None
        
        for cleaner in self.cleaners:
            start = datetime.utcnow()
            
            # Apply transformation
            result = cleaner.clean(result, **params)
            
            # Track provenance
            if track_provenance:
                duration = (datetime.utcnow() - start).microseconds // 1000
                step = TransformStep(
                    id=f"{cleaner.name}_{start.timestamp()}",
                    name=cleaner.name,
                    version=cleaner.version,
                    parameters=params,
                    executed_at=start,
                    duration_ms=duration
                )
                steps.append(step)
            
            # Validate if strict mode
            if self.strict and not cleaner.validate(result):
                raise ValueError(
                    f"Validation failed after {cleaner.name}: {result}"
                )
        
        return result, steps
    
    def batch_apply(
        self,
        values: list[T],
        **params
    ) -> list[tuple[T, Optional[list[TransformStep]]]]:
        """Apply pipeline to multiple values."""
        return [self.apply(v, **params) for v in values]
    
    def validate_all(self, values: list[T]) -> list[tuple[int, str]]:
        """Validate all values, returning list of (index, error) pairs."""
        errors = []
        
        for idx, value in enumerate(values):
            try:
                self.apply(value, track_provenance=False)
            except ValueError as e:
                errors.append((idx, str(e)))
        
        return errors
    
    @property
    def signature(self) -> str:
        """Unique signature for this pipeline configuration."""
        parts = [f"{c.name}:{c.version}" for c in self.cleaners]
        return "_".join(parts)


@dataclass
class PipelineFactory:
    """Factory for common pipeline configurations."""
    
    @staticmethod
    def for_headwords() -> Pipeline:
        """Pipeline for cleaning headwords."""
        from backend.storage.cleaners import (
            HeadwordCleaner,
            TextNormalizer,
        )
        
        return Pipeline([
            HeadwordCleaner(),
            TextNormalizer(),
        ])
    
    @staticmethod
    def for_ipa() -> Pipeline:
        """Pipeline for cleaning IPA transcriptions."""
        from backend.storage.cleaners import IPACleaner
        
        return Pipeline([IPACleaner()], strict=True)
    
    @staticmethod
    def for_definitions() -> Pipeline:
        """Pipeline for cleaning definitions."""
        from backend.storage.cleaners import (
            DefinitionCleaner,
            TextNormalizer,
        )
        
        return Pipeline([
            DefinitionCleaner(),
            TextNormalizer(lowercase=False),
        ])
    
    @staticmethod
    def for_language_codes() -> Pipeline:
        """Pipeline for normalizing language codes."""
        from backend.storage.cleaners import LanguageCodeCleaner
        
        return Pipeline([LanguageCodeCleaner()], strict=True)
    
    @staticmethod
    def full_entry_pipeline() -> dict[str, Pipeline]:
        """Complete pipeline for dictionary entries."""
        return {
            'headword': PipelineFactory.for_headwords(),
            'ipa': PipelineFactory.for_ipa(),
            'definition': PipelineFactory.for_definitions(),
            'language': PipelineFactory.for_language_codes(),
        }


def compose(*cleaners: ICleaner, strict: bool = True) -> Pipeline:
    """Convenience function to compose cleaners into pipeline."""
    return Pipeline(list(cleaners), strict=strict)

