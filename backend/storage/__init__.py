"""Storage layer for persistence and caching.

Barrel export for repositories.
"""

from .repositories import EntryRepository, CognateRepository

__all__ = [
    "EntryRepository",
    "CognateRepository",
]

