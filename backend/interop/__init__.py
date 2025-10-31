"""Interop layer for polyglot service communication.

Barrel export for gRPC clients and foreign function interfaces.
"""

from .grpc_client import ParserGrpcClient

__all__ = [
    "ParserGrpcClient",
]

