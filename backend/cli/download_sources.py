#!/usr/bin/env python3
"""
Automated Data Source Downloader for LangViz
Downloads linguistic databases from the catalog with progress tracking and validation.
"""

import asyncio
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass

import httpx
import tomli
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class DataSource:
    """Represents a data source from the catalog."""
    id: str
    name: str
    download_method: str
    url: str
    download_path: str
    git_url: Optional[str] = None
    download_url: Optional[str] = None
    priority: int = 99
    status: str = "unknown"
    entries_approx: Optional[int] = None
    
    @property
    def full_path(self) -> Path:
        """Get full filesystem path for this source."""
        # Assuming script is in backend/cli/
        project_root = Path(__file__).parent.parent.parent
        return project_root / self.download_path
    
    def __lt__(self, other):
        """Enable sorting by priority."""
        return self.priority < other.priority


class SourceDownloader:
    """Downloads and validates data sources."""
    
    def __init__(self, catalog_path: str = "data/sources/catalog.toml"):
        self.catalog_path = Path(catalog_path)
        self.project_root = Path(__file__).parent.parent.parent
        self.catalog: List[DataSource] = []
        self.downloaded: List[str] = []
        self.failed: List[tuple[str, str]] = []
        
    def load_catalog(self):
        """Load source catalog from TOML."""
        catalog_file = self.project_root / self.catalog_path
        
        if not catalog_file.exists():
            raise FileNotFoundError(f"Catalog not found: {catalog_file}")
        
        with open(catalog_file, 'rb') as f:
            data = tomli.load(f)
        
        for source_dict in data.get('source', []):
            source = DataSource(
                id=source_dict['id'],
                name=source_dict['name'],
                download_method=source_dict.get('download_method', 'unknown'),
                url=source_dict['url'],
                download_path=source_dict.get('download_path', f"data/sources/{source_dict['id']}"),
                git_url=source_dict.get('git_url'),
                download_url=source_dict.get('download_url'),
                priority=source_dict.get('priority', 99),
                status=source_dict.get('status', 'unknown'),
                entries_approx=source_dict.get('entries_approx'),
            )
            self.catalog.append(source)
        
        # Sort by priority
        self.catalog.sort()
        
        print(f"✓ Loaded {len(self.catalog)} sources from catalog")
    
    def download_git(self, source: DataSource) -> bool:
        """Download via git clone."""
        if not source.git_url:
            print(f"  ✗ No git URL specified for {source.id}")
            return False
        
        if source.full_path.exists():
            print(f"  ⤷ Already exists: {source.full_path.name}")
            return True
        
        try:
            source.full_path.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"  ⤓ Cloning {source.git_url}...")
            result = subprocess.run(
                ['git', 'clone', '--depth', '1', source.git_url, str(source.full_path)],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                print(f"  ✓ Downloaded to {source.full_path}")
                return True
            else:
                print(f"  ✗ Git clone failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout downloading {source.id}")
            return False
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False
    
    async def download_http(self, source: DataSource) -> bool:
        """Download via HTTP/HTTPS."""
        if not source.download_url:
            print(f"  ✗ No download URL specified for {source.id}")
            return False
        
        if source.full_path.exists():
            print(f"  ⤷ Already exists: {source.full_path.name}")
            return True
        
        try:
            source.full_path.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"  ⤓ Downloading {source.download_url}...")
            
            async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
                # Stream download with progress bar
                async with client.stream('GET', source.download_url) as response:
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    
                    with open(source.full_path, 'wb') as f:
                        with tqdm(
                            total=total_size,
                            unit='B',
                            unit_scale=True,
                            unit_divisor=1024,
                            desc=f"  {source.full_path.name}"
                        ) as pbar:
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                f.write(chunk)
                                pbar.update(len(chunk))
            
            print(f"  ✓ Downloaded to {source.full_path}")
            return True
            
        except httpx.HTTPError as e:
            print(f"  ✗ HTTP error: {e}")
            return False
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False
    
    async def download_source(self, source: DataSource) -> bool:
        """Download a single source based on its method."""
        print(f"\n[{source.priority}] {source.name}")
        print(f"    Method: {source.download_method}")
        
        if source.status in ['requires_scraper', 'requires_extraction', 'deferred']:
            print(f"    ⊘ Status: {source.status} - skipping automated download")
            return False
        
        if source.download_method == 'git':
            return self.download_git(source)
        elif source.download_method == 'http':
            return await self.download_http(source)
        elif source.download_method == 'manual':
            print(f"    ⊘ Manual download required - see: {source.url}")
            return False
        else:
            print(f"    ✗ Unknown download method: {source.download_method}")
            return False
    
    async def download_all(
        self,
        priority_filter: Optional[int] = None,
        source_ids: Optional[List[str]] = None
    ):
        """Download all sources matching filters."""
        print("\n" + "="*70)
        print("LangViz Data Source Downloader")
        print("="*70)
        
        sources_to_download = self.catalog
        
        if source_ids:
            sources_to_download = [s for s in self.catalog if s.id in source_ids]
            if not sources_to_download:
                print(f"\n✗ No sources found matching IDs: {source_ids}")
                return
        elif priority_filter:
            sources_to_download = [s for s in self.catalog if s.priority <= priority_filter]
        
        print(f"\nQueued: {len(sources_to_download)} sources")
        print(f"Target directory: {self.project_root}")
        
        for source in sources_to_download:
            success = await self.download_source(source)
            
            if success:
                self.downloaded.append(source.id)
            else:
                self.failed.append((source.id, source.name))
        
        # Summary
        print("\n" + "="*70)
        print("Download Summary")
        print("="*70)
        print(f"✓ Successfully downloaded: {len(self.downloaded)}")
        print(f"✗ Failed or skipped: {len(self.failed)}")
        
        if self.downloaded:
            print("\n✓ Downloaded:")
            for source_id in self.downloaded:
                print(f"  - {source_id}")
        
        if self.failed:
            print("\n✗ Failed/Skipped:")
            for source_id, name in self.failed:
                print(f"  - {source_id}: {name}")
    
    def list_sources(self):
        """List all available sources."""
        print("\n" + "="*70)
        print("Available Data Sources")
        print("="*70)
        
        by_priority: Dict[int, List[DataSource]] = {}
        for source in self.catalog:
            by_priority.setdefault(source.priority, []).append(source)
        
        for priority in sorted(by_priority.keys()):
            sources = by_priority[priority]
            print(f"\n Priority {priority}:")
            for source in sources:
                status_icon = {
                    'ready': '✓',
                    'available': '✓',
                    'requires_scraper': '⊗',
                    'requires_extraction': '⊗',
                    'deferred': '⊘',
                }.get(source.status, '?')
                
                exists = "📦" if source.full_path.exists() else "  "
                entries = f"~{source.entries_approx:,} entries" if source.entries_approx else ""
                
                print(f"  {exists} {status_icon} {source.id:25} - {source.name} {entries}")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download linguistic data sources for LangViz",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all sources
  python download_sources.py --list
  
  # Download high-priority sources (priority 1-3)
  python download_sources.py --priority 3
  
  # Download specific sources
  python download_sources.py --sources ielex kaikki_english perseus_latin
  
  # Download everything that's ready
  python download_sources.py --all
        """
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available sources and exit'
    )
    parser.add_argument(
        '--priority',
        type=int,
        metavar='N',
        help='Download sources with priority <= N'
    )
    parser.add_argument(
        '--sources',
        nargs='+',
        metavar='ID',
        help='Download specific sources by ID'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Download all ready sources'
    )
    parser.add_argument(
        '--catalog',
        default='data/sources/catalog.toml',
        help='Path to catalog file (default: data/sources/catalog.toml)'
    )
    
    args = parser.parse_args()
    
    downloader = SourceDownloader(catalog_path=args.catalog)
    downloader.load_catalog()
    
    if args.list:
        downloader.list_sources()
        return
    
    if not any([args.priority, args.sources, args.all]):
        # Default: download priority 1 (IELex)
        print("\nNo options specified. Downloading priority 1 sources...")
        print("Use --help to see all options")
        await downloader.download_all(priority_filter=1)
    elif args.all:
        await downloader.download_all()
    elif args.priority:
        await downloader.download_all(priority_filter=args.priority)
    elif args.sources:
        await downloader.download_all(source_ids=args.sources)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⊘ Download cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

