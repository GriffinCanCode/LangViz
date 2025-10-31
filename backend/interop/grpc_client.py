"""gRPC client for polyglot service communication.

Provides typed clients for Perl parsing service and future polyglot services.
"""

from typing import Optional
import grpc
from backend.core import Entry
from backend.core.contracts import IParser


class ParserGrpcClient(IParser):
    """gRPC client for Perl dictionary parsing service."""
    
    def __init__(self, host: str = "localhost", port: int = 50051):
        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[object] = None  # Will be typed when proto generated
        self._host = host
        self._port = port
        
    def connect(self):
        """Establish gRPC connection."""
        self._channel = grpc.insecure_channel(f"{self._host}:{self._port}")
        # self._stub = parser_pb2_grpc.ParserServiceStub(self._channel)
        
    def disconnect(self):
        """Close gRPC connection."""
        if self._channel:
            self._channel.close()
            
    def parse_dictionary(self, filepath: str) -> list[Entry]:
        """Parse dictionary via gRPC call to Perl service."""
        if not self._stub:
            raise RuntimeError("Client not connected")
            
        # TODO: Implement when proto is defined
        # request = parser_pb2.ParseRequest(filepath=filepath)
        # response = self._stub.ParseDictionary(request)
        # return [self._proto_to_entry(e) for e in response.entries]
        raise NotImplementedError("Proto definitions pending")
    
    def normalize_text(self, text: str) -> str:
        """Normalize text via Perl regex engine."""
        if not self._stub:
            raise RuntimeError("Client not connected")
            
        # TODO: Implement when proto is defined
        raise NotImplementedError("Proto definitions pending")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

