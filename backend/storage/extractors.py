"""Unified extraction strategies for diverse source formats.

Strategy pattern for HTML, PDF, and API extraction with:
- Stream-based processing (memory efficient)
- Automatic retry with exponential backoff
- Type-safe extraction rules via Pydantic
- Composable selectors for extensibility
"""

import asyncio
import hashlib
import json
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Protocol, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════
# EXTRACTION RULES (Type-Safe Configuration)
# ═══════════════════════════════════════════════════════════════════════

class HTMLSelector(BaseModel):
    """CSS selector rule for HTML extraction."""
    entry_selector: str = Field(description="CSS selector for entry containers")
    headword_selector: str = Field(description="Selector for headword within entry")
    definition_selector: Optional[str] = None
    etymology_selector: Optional[str] = None
    ipa_selector: Optional[str] = None
    language: str = Field(description="ISO language code")


class PDFExtractionRule(BaseModel):
    """Rule for structured PDF extraction."""
    entry_pattern: str = Field(description="Regex pattern for entry start")
    headword_pattern: str = Field(description="Regex to extract headword")
    definition_pattern: Optional[str] = None
    etymology_pattern: Optional[str] = None
    language: str


# ═══════════════════════════════════════════════════════════════════════
# EXTRACTOR PROTOCOL (Contract for all strategies)
# ═══════════════════════════════════════════════════════════════════════

class IExtractor(Protocol):
    """Contract for all extraction strategies."""
    
    @abstractmethod
    async def extract(
        self,
        source: str,
        source_id: str,
        **params
    ) -> AsyncIterator[dict]:
        """Extract entries from source.
        
        Args:
            source: URL or file path
            source_id: Identifier for provenance
            **params: Strategy-specific parameters
            
        Yields:
            dict: Normalized entry data
        """
        ...


# ═══════════════════════════════════════════════════════════════════════
# HTML EXTRACTOR (BeautifulSoup + lxml)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class HTMLExtractor:
    """Extract dictionary entries from HTML using CSS selectors.
    
    Uses lxml parser for speed, BeautifulSoup for ergonomics.
    Supports both local files and remote URLs with retry logic.
    """
    
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    
    async def extract(
        self,
        source: str,
        source_id: str,
        selector: HTMLSelector,
        **params
    ) -> AsyncIterator[dict]:
        """Extract from HTML using selector rules."""
        
        # Fetch HTML content
        html = await self._fetch_html(source)
        
        # Parse with lxml (fastest HTML parser)
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract entries
        entries = soup.select(selector.entry_selector)
        
        for idx, entry in enumerate(entries):
            data = {
                'headword': self._extract_text(entry, selector.headword_selector),
                'language': selector.language,
                'source_type': 'scraped_html',
                'source_url': source,
            }
            
            # Optional fields
            if selector.definition_selector:
                data['definition'] = self._extract_text(
                    entry, selector.definition_selector
                )
            
            if selector.etymology_selector:
                data['etymology'] = self._extract_text(
                    entry, selector.etymology_selector
                )
            
            if selector.ipa_selector:
                data['ipa'] = self._extract_text(
                    entry, selector.ipa_selector
                )
            
            # Skip invalid entries
            if not data['headword']:
                continue
            
            yield data
    
    async def _fetch_html(self, source: str) -> str:
        """Fetch HTML from URL or file with retry logic."""
        
        # Local file
        if Path(source).exists():
            return Path(source).read_text(encoding='utf-8')
        
        # Remote URL with retries
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(source)
                    response.raise_for_status()
                    return response.text
            except httpx.HTTPError as e:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        raise RuntimeError(f"Failed to fetch {source}")
    
    def _extract_text(self, element: Tag, selector: str) -> str:
        """Extract and clean text from element."""
        found = element.select_one(selector)
        if not found:
            return ""
        
        text = found.get_text(strip=True)
        return text.replace('\n', ' ').strip()


# ═══════════════════════════════════════════════════════════════════════
# PDF EXTRACTOR (pdfplumber for structured text)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PDFExtractor:
    """Extract dictionary entries from structured PDFs.
    
    Uses pdfplumber for accurate text extraction with layout preservation.
    Designed for academic lexicons with regular structure.
    """
    
    async def extract(
        self,
        source: str,
        source_id: str,
        rule: PDFExtractionRule,
        **params
    ) -> AsyncIterator[dict]:
        """Extract from PDF using regex rules."""
        
        if not PDF_AVAILABLE:
            raise ImportError("pdfplumber required: pip install pdfplumber")
        
        # Run in thread pool (pdfplumber is sync)
        entries = await asyncio.to_thread(
            self._extract_sync,
            source,
            source_id,
            rule
        )
        
        for entry in entries:
            yield entry
    
    def _extract_sync(
        self,
        source: str,
        source_id: str,
        rule: PDFExtractionRule
    ) -> list[dict]:
        """Synchronous PDF extraction (blocking)."""
        import re
        
        entries = []
        current_entry = {}
        
        with pdfplumber.open(source) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                
                # Split into lines
                for line in text.split('\n'):
                    line = line.strip()
                    
                    # Check if new entry starts
                    if re.match(rule.entry_pattern, line):
                        # Save previous entry
                        if current_entry and current_entry.get('headword'):
                            entries.append(current_entry)
                        
                        # Start new entry
                        headword_match = re.search(rule.headword_pattern, line)
                        current_entry = {
                            'headword': headword_match.group(1) if headword_match else line,
                            'language': rule.language,
                            'source_type': 'pdf',
                            'page': page_num,
                        }
                    
                    # Extract additional fields from continuation lines
                    elif current_entry:
                        if rule.definition_pattern:
                            def_match = re.search(rule.definition_pattern, line)
                            if def_match:
                                current_entry['definition'] = def_match.group(1)
                        
                        if rule.etymology_pattern:
                            etym_match = re.search(rule.etymology_pattern, line)
                            if etym_match:
                                current_entry['etymology'] = etym_match.group(1)
        
        # Don't forget last entry
        if current_entry and current_entry.get('headword'):
            entries.append(current_entry)
        
        return entries


# ═══════════════════════════════════════════════════════════════════════
# API EXTRACTOR (for Wiktionary, Oxford, etc.)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class APIExtractor:
    """Extract from REST APIs with rate limiting.
    
    Implements:
    - Automatic rate limiting (requests per second)
    - Retry with exponential backoff
    - Response validation
    """
    
    rate_limit: float = 200.0  # requests per second
    timeout: float = 10.0
    max_retries: int = 3
    
    def __post_init__(self):
        self._semaphore = asyncio.Semaphore(int(self.rate_limit))
        self._delay = 1.0 / self.rate_limit
    
    async def extract(
        self,
        source: str,
        source_id: str,
        transform: callable = None,
        **params
    ) -> AsyncIterator[dict]:
        """Extract from API endpoint.
        
        Args:
            source: Base API URL
            source_id: Provenance identifier
            transform: Function to transform API response to our format
            **params: API-specific parameters
        """
        
        async with self._semaphore:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await self._fetch_with_retry(client, source, params)
                
                # Apply transformation if provided
                if transform:
                    data = transform(response.json())
                else:
                    data = response.json()
                
                # Handle both single entries and lists
                entries = data if isinstance(data, list) else [data]
                
                for entry in entries:
                    yield entry
            
            # Rate limiting delay
            await asyncio.sleep(self._delay)
    
    async def _fetch_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict
    ) -> httpx.Response:
        """Fetch with exponential backoff retry."""
        
        for attempt in range(self.max_retries):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response
            except httpx.HTTPError as e:
                if attempt == self.max_retries - 1:
                    raise
                delay = self._delay * (2 ** attempt)
                await asyncio.sleep(delay)
        
        raise RuntimeError(f"Failed to fetch {url}")


# ═══════════════════════════════════════════════════════════════════════
# FACTORY (Select appropriate extractor)
# ═══════════════════════════════════════════════════════════════════════

class ExtractorFactory:
    """Factory for selecting appropriate extractor strategy."""
    
    @staticmethod
    def create(source_type: str) -> IExtractor:
        """Create extractor for source type."""
        
        extractors = {
            'html': HTMLExtractor(),
            'pdf': PDFExtractor(),
            'api': APIExtractor(),
        }
        
        extractor = extractors.get(source_type.lower())
        if not extractor:
            raise ValueError(f"Unknown source type: {source_type}")
        
        return extractor

