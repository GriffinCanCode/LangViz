#!/usr/bin/env python3
"""Tier 1 Source Scraper: Critical PIE and ancient language sources.

Orchestrates extraction from:
1. UT Austin PIE Lexicon (HTML)
2. Academia Prisca Late PIE (PDF)
3. eDIL Irish Dictionary (HTML)
4. Sanskrit sources (TBD)
5. Old Church Slavonic (TBD)
6. Classical Armenian (TBD)

Uses unified extraction strategies from storage/extractors.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import orjson
from rich.console import Console
from rich.progress import track

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.extractors import (
    HTMLExtractor,
    HTMLSelector,
    PDFExtractor,
    PDFExtractionRule,
    ExtractorFactory,
)


# ═══════════════════════════════════════════════════════════════════════
# SOURCE CONFIGURATIONS (Type-safe extraction rules)
# ═══════════════════════════════════════════════════════════════════════

class SourceConfig:
    """Configuration for each Tier 1 source."""
    
    # UT Austin PIE Lexicon
    UT_AUSTIN_PIE = {
        'id': 'ut_austin_pie',
        'name': 'UT Austin PIE Lexicon',
        'url': 'https://lrc.la.utexas.edu/lex',
        'type': 'html',
        'selector': HTMLSelector(
            entry_selector='div.entry',  # Adjust based on actual HTML
            headword_selector='span.headword',
            definition_selector='span.meaning',
            etymology_selector='span.etymology',
            language='pie'  # Proto-Indo-European
        ),
        'output': 'data/sources/ut_austin_pie/entries.jsonl'
    }
    
    # eDIL Irish Dictionary
    EDIL_IRISH = {
        'id': 'edil_irish',
        'name': 'eDIL Irish Dictionary',
        'url': 'http://www.dil.ie/',  # Need to implement pagination
        'type': 'html',
        'selector': HTMLSelector(
            entry_selector='div.dil-entry',
            headword_selector='span.headword',
            definition_selector='div.definition',
            etymology_selector='div.etymology',
            language='sga'  # Old Irish
        ),
        'output': 'data/sources/edil/entries.jsonl',
        'pagination': True,
        'pagination_pattern': 'http://www.dil.ie/?page={}'
    }
    
    # Academia Prisca Late PIE
    ACADEMIA_PRISCA = {
        'id': 'academia_prisca_pie',
        'name': 'Academia Prisca Late PIE Lexicon',
        'url': 'https://academiaprisca.org/dnghu/en/resources/PIE_Lexicon.pdf',
        'type': 'pdf',
        'rule': PDFExtractionRule(
            entry_pattern=r'^\*\w+',  # PIE roots start with *
            headword_pattern=r'(\*\w+[-\w]*)',
            definition_pattern=r'(?:meaning:|def:)\s*(.+)',
            etymology_pattern=r'(?:from|<)\s*(.+)',
            language='pie'
        ),
        'output': 'data/sources/academia_prisca/entries.jsonl'
    }


# ═══════════════════════════════════════════════════════════════════════
# SCRAPER ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════

class TierOneScraper:
    """Orchestrates scraping of Tier 1 critical sources."""
    
    def __init__(self):
        self.console = Console()
        self.project_root = Path(__file__).parent.parent.parent
    
    async def scrape_source(self, config: dict) -> tuple[str, int, Optional[str]]:
        """Scrape a single source.
        
        Returns:
            (source_id, num_entries, error_message)
        """
        
        self.console.print(f"\n[cyan]Scraping: {config['name']}[/cyan]")
        self.console.print(f"URL: {config['url']}")
        
        try:
            # Create output directory
            output_path = self.project_root / config['output']
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get appropriate extractor
            extractor = ExtractorFactory.create(config['type'])
            
            # Extract entries
            entries = []
            
            if config['type'] == 'html':
                # HTML extraction
                if config.get('pagination'):
                    # Handle paginated sources
                    entries = await self._scrape_paginated(
                        extractor,
                        config
                    )
                else:
                    # Single-page extraction
                    async for entry in extractor.extract(
                        config['url'],
                        config['id'],
                        config['selector']
                    ):
                        entries.append(entry)
            
            elif config['type'] == 'pdf':
                # PDF extraction (download first)
                pdf_path = await self._download_pdf(config['url'])
                
                async for entry in extractor.extract(
                    str(pdf_path),
                    config['id'],
                    config['rule']
                ):
                    entries.append(entry)
            
            # Write entries to JSONL
            with open(output_path, 'wb') as f:
                for entry in entries:
                    f.write(orjson.dumps(entry))
                    f.write(b'\n')
            
            self.console.print(
                f"[green]✓ Extracted {len(entries)} entries to {output_path}[/green]"
            )
            
            return config['id'], len(entries), None
            
        except Exception as e:
            error_msg = f"Failed to scrape {config['name']}: {e}"
            self.console.print(f"[red]✗ {error_msg}[/red]")
            import traceback
            traceback.print_exc()
            return config['id'], 0, error_msg
    
    async def _scrape_paginated(
        self,
        extractor: HTMLExtractor,
        config: dict
    ) -> list[dict]:
        """Scrape paginated HTML source."""
        
        all_entries = []
        page = 1
        max_pages = 100  # Safety limit
        
        while page <= max_pages:
            url = config['pagination_pattern'].format(page)
            
            try:
                entries_on_page = []
                async for entry in extractor.extract(
                    url,
                    config['id'],
                    config['selector']
                ):
                    entries_on_page.append(entry)
                
                if not entries_on_page:
                    # No more pages
                    break
                
                all_entries.extend(entries_on_page)
                self.console.print(
                    f"  Page {page}: {len(entries_on_page)} entries"
                )
                page += 1
                
                # Rate limiting
                await asyncio.sleep(1.0)
                
            except Exception as e:
                self.console.print(f"  [yellow]Page {page} failed: {e}[/yellow]")
                break
        
        return all_entries
    
    async def _download_pdf(self, url: str) -> Path:
        """Download PDF to temp location."""
        import httpx
        
        filename = url.split('/')[-1]
        pdf_path = self.project_root / 'data' / 'sources' / '.temp' / filename
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        
        if pdf_path.exists():
            self.console.print(f"  Using cached PDF: {pdf_path}")
            return pdf_path
        
        self.console.print(f"  Downloading PDF: {url}")
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            
            with open(pdf_path, 'wb') as f:
                f.write(response.content)
        
        self.console.print(f"  [green]✓ Downloaded to {pdf_path}[/green]")
        return pdf_path
    
    async def scrape_all(
        self,
        sources: Optional[list[str]] = None
    ):
        """Scrape all or selected Tier 1 sources.
        
        Args:
            sources: List of source IDs to scrape (None = all)
        """
        
        # Available sources
        available = {
            'ut_austin_pie': SourceConfig.UT_AUSTIN_PIE,
            'edil_irish': SourceConfig.EDIL_IRISH,
            'academia_prisca_pie': SourceConfig.ACADEMIA_PRISCA,
        }
        
        # Select sources
        if sources:
            configs = [available[s] for s in sources if s in available]
        else:
            configs = list(available.values())
        
        if not configs:
            self.console.print("[red]No valid sources specified[/red]")
            return
        
        # Display summary
        self.console.print("\n[bold]Tier 1 Scraper: Critical Sources[/bold]")
        self.console.print(f"Sources: {len(configs)}\n")
        
        # Scrape sequentially (to be respectful of rate limits)
        results = []
        for config in configs:
            result = await self.scrape_source(config)
            results.append(result)
        
        # Summary
        self._print_summary(results)
    
    def _print_summary(self, results: list[tuple[str, int, Optional[str]]]):
        """Print scraping summary."""
        
        self.console.print("\n" + "=" * 70)
        self.console.print("[bold]Scraping Summary[/bold]")
        self.console.print("=" * 70)
        
        total_entries = 0
        successful = 0
        failed = 0
        
        for source_id, num_entries, error in results:
            if error:
                failed += 1
                self.console.print(
                    f"[red]✗ {source_id}: {error}[/red]"
                )
            else:
                successful += 1
                total_entries += num_entries
                self.console.print(
                    f"[green]✓ {source_id}: {num_entries:,} entries[/green]"
                )
        
        self.console.print(f"\nSuccessful: {successful}/{len(results)}")
        self.console.print(f"Total entries: {total_entries:,}")


# ═══════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═══════════════════════════════════════════════════════════════════════

async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Scrape Tier 1 critical linguistic sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape all Tier 1 sources
  python scrape.py --all
  
  # Scrape specific sources
  python scrape.py --sources ut_austin_pie edil_irish
  
  # List available sources
  python scrape.py --list
        """
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Scrape all Tier 1 sources'
    )
    parser.add_argument(
        '--sources',
        nargs='+',
        choices=['ut_austin_pie', 'edil_irish', 'academia_prisca_pie'],
        help='Scrape specific sources'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available sources and exit'
    )
    
    args = parser.parse_args()
    
    # List sources
    if args.list:
        console = Console()
        console.print("\n[bold]Available Tier 1 Sources:[/bold]\n")
        
        sources = [
            ('ut_austin_pie', 'UT Austin PIE Lexicon', '~2,000 roots'),
            ('edil_irish', 'eDIL Irish Dictionary', '~35,000 entries'),
            ('academia_prisca_pie', 'Academia Prisca Late PIE', '~4,000 entries'),
        ]
        
        for source_id, name, size in sources:
            console.print(f"[cyan]{source_id}[/cyan]")
            console.print(f"  {name} ({size})\n")
        
        return
    
    # Validate arguments
    if not any([args.all, args.sources]):
        parser.print_help()
        return
    
    # Create scraper
    scraper = TierOneScraper()
    
    # Start scraping
    if args.all:
        await scraper.scrape_all()
    else:
        await scraper.scrape_all(sources=args.sources)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⊘ Scraping cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

