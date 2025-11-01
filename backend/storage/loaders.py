"""Data loaders for various source formats.

Specialized loaders for CLDF, Swadesh lists, and other formats.
"""

import csv
import json
import hashlib
from pathlib import Path
from typing import Iterator, Optional
from dataclasses import dataclass
from datetime import datetime

try:
    import pycldf
    PYCLDF_AVAILABLE = True
except ImportError:
    PYCLDF_AVAILABLE = False


@dataclass
class RawEntry:
    """Minimally processed entry from source."""
    source_id: str
    data: dict
    checksum: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None


class CLDFLoader:
    """Load data from Cross-Linguistic Data Formats (CLDF)."""
    
    def __init__(self):
        if not PYCLDF_AVAILABLE:
            raise ImportError(
                "pycldf not installed. Install with: pip install pycldf"
            )
    
    def load(self, dataset_path: str, source_id: str) -> Iterator[RawEntry]:
        """Load CLDF dataset and yield raw entries."""
        dataset = pycldf.Dataset.from_metadata(
            Path(dataset_path) / "metadata.json"
        )
        
        # Load forms (lexical items)
        if 'FormTable' in dataset:
            for idx, form in enumerate(dataset['FormTable']):
                data = {
                    'headword': form.get('Form'),
                    'language': form.get('Language_ID'),
                    'concept': form.get('Parameter_ID'),
                    'segments': form.get('Segments'),
                    'source': form.get('Source'),
                    'comment': form.get('Comment'),
                }
                
                # Compute checksum
                checksum = hashlib.sha256(
                    json.dumps(data, sort_keys=True).encode()
                ).hexdigest()
                
                yield RawEntry(
                    source_id=source_id,
                    data=data,
                    checksum=checksum,
                    file_path=str(dataset_path),
                    line_number=idx
                )
        
        # Load cognate sets if available
        if 'CognateTable' in dataset:
            for idx, cognate in enumerate(dataset['CognateTable']):
                data = {
                    'type': 'cognate',
                    'form_id': cognate.get('Form_ID'),
                    'cognateset_id': cognate.get('Cognateset_ID'),
                    'alignment': cognate.get('Alignment'),
                    'doubt': cognate.get('Doubt'),
                }
                
                checksum = hashlib.sha256(
                    json.dumps(data, sort_keys=True).encode()
                ).hexdigest()
                
                yield RawEntry(
                    source_id=source_id,
                    data=data,
                    checksum=checksum,
                    file_path=str(dataset_path),
                    line_number=idx
                )


class SwadeshLoader:
    """Load Swadesh comparative wordlists."""
    
    def load(self, csv_path: str, source_id: str) -> Iterator[RawEntry]:
        """Load Swadesh list from CSV."""
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for line_num, row in enumerate(reader, start=2):
                # Each row has concept and translations
                concept = row.pop('concept', None)
                
                for lang, word in row.items():
                    if not word or word.strip() == '-':
                        continue
                    
                    data = {
                        'headword': word.strip(),
                        'language': lang,
                        'concept': concept,
                        'source_type': 'swadesh',
                    }
                    
                    checksum = hashlib.sha256(
                        json.dumps(data, sort_keys=True).encode()
                    ).hexdigest()
                    
                    yield RawEntry(
                        source_id=source_id,
                        data=data,
                        checksum=checksum,
                        file_path=csv_path,
                        line_number=line_num
                    )


class StarlingLoader:
    """Load Starling database format via Perl gRPC service.
    
    Delegates to Perl regex engine for complex parsing patterns.
    """
    
    def __init__(self, use_grpc: bool = True):
        """Initialize loader.
        
        Args:
            use_grpc: If True, use Perl gRPC service. If False, fallback to Python.
        """
        self._use_grpc = use_grpc
        self._grpc_client = None
    
    def load(self, file_path: str, source_id: str) -> Iterator[RawEntry]:
        """Load Starling format dictionary."""
        if self._use_grpc:
            try:
                yield from self._load_via_grpc(file_path, source_id)
                return
            except Exception as e:
                print(f"gRPC parsing failed, falling back to Python: {e}")
        
        # Fallback to Python regex
        yield from self._load_python_fallback(file_path, source_id)
    
    def _load_via_grpc(self, file_path: str, source_id: str) -> Iterator[RawEntry]:
        """Load via Perl service (Perl's superior regex via JSON-RPC)."""
        from backend.interop.perl_client import PerlParserClient
        from backend.config import get_settings
        
        settings = get_settings()
        
        with PerlParserClient(
            settings.parser_service_host,
            settings.parser_service_port
        ) as client:
            # Call Perl parser via JSON-RPC
            entries = client.parse_starling_dictionary(file_path)
            
            for idx, entry_data in enumerate(entries):
                checksum = hashlib.sha256(
                    json.dumps(entry_data, sort_keys=True).encode()
                ).hexdigest()
                
                yield RawEntry(
                    source_id=source_id,
                    data=entry_data,
                    checksum=checksum,
                    file_path=file_path,
                    line_number=idx
                )
    
    def _load_python_fallback(
        self,
        file_path: str,
        source_id: str
    ) -> Iterator[RawEntry]:
        """Fallback Python implementation (less powerful regex)."""
        with open(file_path, 'r', encoding='utf-8') as f:
            current_entry = {}
            line_num = 0
            entry_start = 0
            
            for line in f:
                line_num += 1
                line = line.strip()
                
                # Entry markers (basic patterns only)
                if line.startswith('\\lx '):
                    if current_entry:
                        yield self._create_entry(
                            source_id,
                            current_entry,
                            file_path,
                            entry_start
                        )
                    current_entry = {'headword': line[4:]}
                    entry_start = line_num
                
                elif line.startswith('\\ph '):
                    current_entry['ipa'] = line[4:].strip('[]')
                
                elif line.startswith('\\de '):
                    current_entry['definition'] = line[4:]
                
                elif line.startswith('\\et '):
                    current_entry['etymology'] = line[4:]
                
                elif line.startswith('\\ps '):
                    current_entry['pos_tag'] = line[4:]
                
                elif line.startswith('\\lg '):
                    current_entry['language'] = line[4:]
            
            # Yield last entry
            if current_entry:
                yield self._create_entry(
                    source_id,
                    current_entry,
                    file_path,
                    entry_start
                )
    
    def _create_entry(
        self,
        source_id: str,
        data: dict,
        file_path: str,
        line_number: int
    ) -> RawEntry:
        """Create RawEntry from parsed data."""
        checksum = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
        
        return RawEntry(
            source_id=source_id,
            data=data,
            checksum=checksum,
            file_path=file_path,
            line_number=line_number
        )


class JSONLoader:
    """Generic JSON dictionary loader."""
    
    def load(self, file_path: str, source_id: str) -> Iterator[RawEntry]:
        """Load entries from JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Support both list of entries and nested structures
        entries = data if isinstance(data, list) else data.get('entries', [])
        
        for idx, entry in enumerate(entries):
            checksum = hashlib.sha256(
                json.dumps(entry, sort_keys=True).encode()
            ).hexdigest()
            
            yield RawEntry(
                source_id=source_id,
                data=entry,
                checksum=checksum,
                file_path=file_path,
                line_number=idx
            )


class LoaderFactory:
    """Factory for selecting appropriate loader."""
    
    @staticmethod
    def get_loader(format: str):
        """Get loader for specified format."""
        loaders = {
            'cldf': CLDFLoader,
            'swadesh': SwadeshLoader,
            'csv': SwadeshLoader,  # Alias
            'starling': StarlingLoader,
            'json': JSONLoader,
        }
        
        loader_cls = loaders.get(format.lower())
        if not loader_cls:
            raise ValueError(f"Unknown format: {format}")
        
        return loader_cls()

