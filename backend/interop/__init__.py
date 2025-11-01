"""Interoperability layer for external language services.

Provides clients for:
- Perl: Dictionary parsing and text normalization
- R: Phylogenetic inference and statistical analysis
- Rust: Phonetic distance computation (future)
"""

from .perl_client import PerlParserClient
from .r_client import RPhyloClient

__all__ = [
    "PerlParserClient",
    "RPhyloClient",
]
