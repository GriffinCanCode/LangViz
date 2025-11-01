"""gRPC client for polyglot service communication.

Provides typed clients for Perl parsing service (superior regex) and Rust services.
Architecture: Python orchestrates, Perl parses messy data, Rust computes phonetics.
"""

from typing import Optional
import grpc
from backend.core import Entry
from backend.core.contracts import IParser


class ParserGrpcClient(IParser):
    """gRPC client for Perl dictionary parsing service.
    
    Leverages Perl's regex engine and Lingua::IPA for complex dictionary formats.
    """
    
    def __init__(self, host: str = "localhost", port: int = 50051):
        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[object] = None
        self._host = host
        self._port = port
        
    def connect(self):
        """Establish gRPC connection to Perl service."""
        self._channel = grpc.insecure_channel(
            f"{self._host}:{self._port}",
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024),
            ]
        )
        
        try:
            from backend.interop import parser_pb2_grpc
            self._stub = parser_pb2_grpc.ParserServiceStub(self._channel)
        except ImportError:
            raise RuntimeError(
                "gRPC stubs not generated. Run: "
                "python3 -m grpc_tools.protoc -I services/regexer/proto "
                "--python_out=backend/interop --grpc_python_out=backend/interop "
                "services/regexer/proto/parser.proto"
            )
        
    def disconnect(self):
        """Close gRPC connection."""
        if self._channel:
            self._channel.close()
    
    def parse_starling_dictionary(self, filepath: str) -> list[dict]:
        """Parse Starling format dictionary via Perl regex engine.
        
        Returns list of dicts (raw entries) rather than Entry objects,
        since these need further cleaning in the pipeline.
        """
        if not self._stub:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        try:
            from backend.interop import parser_pb2
            
            request = parser_pb2.ParseRequest(
                filepath=filepath,
                format="starling"
            )
            
            response = self._stub.ParseDictionary(request, timeout=60.0)
            
            # Convert proto entries to dicts
            return [
                {
                    'headword': entry.headword,
                    'ipa': entry.ipa,
                    'language': entry.language,
                    'definition': entry.definition,
                    'etymology': entry.etymology if entry.HasField('etymology') else None,
                    'pos_tag': entry.pos_tag if entry.HasField('pos_tag') else None,
                }
                for entry in response.entries
            ]
        
        except grpc.RpcError as e:
            raise RuntimeError(f"gRPC call failed: {e.code()} - {e.details()}")
    
    def parse_dictionary(self, filepath: str) -> list[Entry]:
        """Parse dictionary via gRPC call to Perl service.
        
        Note: This returns Entry objects for IParser compatibility,
        but parse_starling_dictionary() is preferred for raw data.
        """
        raw_entries = self.parse_starling_dictionary(filepath)
        
        from datetime import datetime
        return [
            Entry(
                id=f"perl_{hash(str(e))}",
                headword=e['headword'],
                ipa=e['ipa'],
                language=e['language'],
                definition=e['definition'],
                etymology=e.get('etymology'),
                pos_tag=e.get('pos_tag'),
                embedding=None,
                created_at=datetime.utcnow()
            )
            for e in raw_entries
        ]
    
    def normalize_text(self, text: str, operations: list[str] = None) -> str:
        """Normalize text via Perl's powerful regex engine.
        
        Operations: 'nfc', 'nfd', 'lowercase', 'strip_diacritics', 'strip_punctuation'
        """
        if not self._stub:
            raise RuntimeError("Client not connected")
        
        try:
            from backend.interop import parser_pb2
            
            request = parser_pb2.NormalizeRequest(
                text=text,
                operations=operations or ['nfc', 'lowercase']
            )
            
            response = self._stub.NormalizeText(request, timeout=5.0)
            return response.normalized
        
        except grpc.RpcError as e:
            raise RuntimeError(f"gRPC normalization failed: {e.details()}")
    
    def extract_ipa_from_notation(
        self,
        text: str,
        notation: str = "kirshenbaum"
    ) -> tuple[str, bool]:
        """Convert notation systems (Kirshenbaum, X-SAMPA) to IPA via Perl.
        
        Returns (ipa_string, success).
        """
        if not self._stub:
            raise RuntimeError("Client not connected")
        
        try:
            from backend.interop import parser_pb2
            
            request = parser_pb2.ExtractIPARequest(
                text=text,
                notation=notation
            )
            
            response = self._stub.ExtractIPA(request, timeout=5.0)
            return response.ipa, response.success
        
        except grpc.RpcError as e:
            return "", False
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

