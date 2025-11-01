"""JSON-RPC client for Perl parsing service.

Communicates with Perl regex engine over TCP using JSON-RPC protocol.
Architecture: Simpler than gRPC, more reliable for Perl interop.
"""

import json
import socket
from typing import Optional
from backend.core.contracts import IParser


class PerlParserClient(IParser):
    """JSON-RPC client for Perl dictionary parsing service.
    
    Leverages Perl's regex engine and Lingua::IPA for messy dictionary formats.
    Uses JSON-RPC 2.0 over TCP (simpler than gRPC for Perl).
    """
    
    def __init__(self, host: str = "localhost", port: int = 50051):
        self._host = host
        self._port = port
        self._socket: Optional[socket.socket] = None
        self._request_id = 0
    
    def connect(self):
        """Establish TCP connection to Perl service."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self._host, self._port))
    
    def disconnect(self):
        """Close TCP connection."""
        if self._socket:
            self._socket.close()
            self._socket = None
    
    def _call(self, method: str, params: dict) -> dict:
        """Make JSON-RPC call to Perl service."""
        if not self._socket:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        self._request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._request_id
        }
        
        # Send request
        request_json = json.dumps(request) + "\n"
        self._socket.sendall(request_json.encode('utf-8'))
        
        # Receive response
        response_data = b''
        while b'\n' not in response_data:
            chunk = self._socket.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed by server")
            response_data += chunk
        
        response = json.loads(response_data.decode('utf-8'))
        
        if "error" in response:
            raise RuntimeError(
                f"Perl service error: {response['error']['message']}"
            )
        
        return response["result"]
    
    def parse_starling_dictionary(self, filepath: str) -> list[dict]:
        """Parse Starling format dictionary via Perl regex engine.
        
        Returns list of dicts (raw entries) for pipeline processing.
        """
        result = self._call("parse_starling", {"filepath": filepath})
        return result["entries"]
    
    def parse_dictionary(self, filepath: str) -> list:
        """Parse dictionary via Perl service.
        
        Note: For compatibility with IParser interface.
        Use parse_starling_dictionary() for raw data.
        """
        raw_entries = self.parse_starling_dictionary(filepath)
        
        from backend.core import Entry
        from datetime import datetime
        
        return [
            Entry(
                id=f"perl_{hash(str(e))}",
                headword=e.get('headword', ''),
                ipa=e.get('ipa', ''),
                language=e.get('language', ''),
                definition=e.get('definition', ''),
                etymology=e.get('etymology'),
                pos_tag=e.get('pos_tag'),
                embedding=None,
                created_at=datetime.utcnow()
            )
            for e in raw_entries
        ]
    
    def normalize_text(
        self,
        text: str,
        operations: list[str] = None
    ) -> str:
        """Normalize text via Perl's powerful regex engine.
        
        Operations: 'nfc', 'nfd', 'lowercase', 'strip_diacritics', 'strip_punctuation'
        """
        result = self._call("normalize_text", {
            "text": text,
            "operations": operations or ['nfc', 'lowercase']
        })
        return result["normalized"]
    
    def extract_ipa_from_notation(
        self,
        text: str,
        notation: str = "kirshenbaum"
    ) -> tuple[str, bool]:
        """Convert notation systems (Kirshenbaum, X-SAMPA) to IPA via Perl.
        
        Returns (ipa_string, success).
        """
        result = self._call("extract_ipa", {
            "text": text,
            "notation": notation
        })
        return result["ipa"], result["success"]
    
    def validate_ipa(self, ipa: str) -> bool:
        """Validate IPA using Lingua::IPA (Perl module)."""
        result = self._call("validate_ipa", {"ipa": ipa})
        return result["valid"]
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

