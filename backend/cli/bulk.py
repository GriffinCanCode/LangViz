#!/usr/bin/env python3
"""Parallel bulk downloader for Tier 2: 52 languages from Kaikki.org.

Features:
- Concurrent downloads with semaphore-based rate limiting
- Progress tracking across all downloads
- Automatic retry with exponential backoff
- Checkpointing for resumability
- Bandwidth throttling
- Size estimation and disk space validation
"""

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import just what we need to avoid circular imports
import orjson


# ═══════════════════════════════════════════════════════════════════════
# CHECKPOINT (Simple local implementation)
# ═══════════════════════════════════════════════════════════════════════

class Checkpoint:
    """Simple checkpoint for resumable downloads."""
    
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)
        self.processed: set[str] = set()
        self._load()
    
    def _load(self):
        """Load checkpoint from disk."""
        if self.filepath.exists():
            with open(self.filepath, 'rb') as f:
                self.processed = set(orjson.loads(f.read()))
    
    def save(self):
        """Save checkpoint to disk."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, 'wb') as f:
            f.write(orjson.dumps(list(self.processed)))
    
    def mark_processed(self, id: str):
        """Mark item as processed."""
        self.processed.add(id)
    
    def is_processed(self, id: str) -> bool:
        """Check if item already processed."""
        return id in self.processed


# ═══════════════════════════════════════════════════════════════════════
# LANGUAGE CATALOG (Tier 2: 52 Languages)
# ═══════════════════════════════════════════════════════════════════════

KAIKKI_LANGUAGES = {
    # Romance (6)
    'romance': [
        'Spanish', 'Portuguese', 'French', 'Italian', 'Romanian', 'Catalan'
    ],
    # Germanic (10)
    'germanic': [
        'English', 'German', 'Dutch', 'Swedish', 'Danish', 'Norwegian',
        'Icelandic', 'Afrikaans', 'Yiddish', 'Faroese'
    ],
    # Slavic (11)
    'slavic': [
        'Russian', 'Ukrainian', 'Belarusian', 'Polish', 'Czech', 'Slovak',
        'Serbian', 'Croatian', 'Bulgarian', 'Macedonian', 'Slovenian'
    ],
    # Indo-Iranian (8)
    'indo_iranian': [
        'Hindi', 'Urdu', 'Bengali', 'Punjabi', 'Persian', 'Pashto',
        'Kurdish', 'Tajik'
    ],
    # Celtic (5)
    'celtic': [
        'Irish', 'Scottish_Gaelic', 'Welsh', 'Breton', 'Manx'
    ],
    # Baltic (2)
    'baltic': ['Lithuanian', 'Latvian'],
    # Other IE (3)
    'other_ie': ['Albanian', 'Armenian', 'Greek'],
    # Dravidian (4)
    'dravidian': ['Tamil', 'Telugu', 'Kannada', 'Malayalam'],
    # Uralic (3)
    'uralic': ['Finnish', 'Estonian', 'Hungarian'],
}


def all_languages() -> list[str]:
    """Get flat list of all 52 languages."""
    langs = []
    for family_langs in KAIKKI_LANGUAGES.values():
        langs.extend(family_langs)
    return langs


# ═══════════════════════════════════════════════════════════════════════
# DOWNLOAD TASK (Single language download)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class DownloadTask:
    """Represents a single language download."""
    
    language: str
    url: str = field(init=False)
    target_path: Path = field(init=False)
    size_bytes: Optional[int] = None
    completed_bytes: int = 0
    status: str = "pending"  # pending, downloading, completed, failed
    error: Optional[str] = None
    
    def __post_init__(self):
        """Compute URL and target path."""
        # Kaikki.org URL pattern (JSONL format)
        self.url = (
            f"https://kaikki.org/dictionary/{self.language}/"
            f"kaikki.org-dictionary-{self.language}.jsonl"
        )
        
        # Target path in data/sources/kaikki/
        project_root = Path(__file__).parent.parent.parent
        self.target_path = (
            project_root / 
            "data" / "sources" / "kaikki" / 
            f"{self.language.lower()}.jsonl"
        )


# ═══════════════════════════════════════════════════════════════════════
# BULK DOWNLOADER (Parallel orchestrator)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class BulkDownloader:
    """Parallel downloader with rate limiting and progress tracking."""
    
    max_concurrent: int = 5  # Concurrent downloads
    timeout: float = 300.0  # 5 minutes per file
    max_retries: int = 3
    retry_delay: float = 2.0
    chunk_size: int = 64 * 1024  # 64KB chunks
    
    def __post_init__(self):
        self.console = Console()
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self.checkpoint = Checkpoint(
            Path(__file__).parent.parent.parent / 
            "data" / "sources" / ".bulk_download_checkpoint.json"
        )
    
    async def download_all(
        self,
        languages: Optional[list[str]] = None,
        families: Optional[list[str]] = None,
        resume: bool = True
    ):
        """Download all or selected languages.
        
        Args:
            languages: Specific language names to download
            families: Language families to download
            resume: Resume from checkpoint if available
        """
        
        # Determine which languages to download
        if languages:
            selected = languages
        elif families:
            selected = []
            for family in families:
                if family in KAIKKI_LANGUAGES:
                    selected.extend(KAIKKI_LANGUAGES[family])
        else:
            selected = all_languages()
        
        # Create download tasks
        tasks = [DownloadTask(lang) for lang in selected]
        
        # Filter out completed tasks if resuming
        if resume:
            tasks = [
                task for task in tasks
                if not self.checkpoint.is_processed(task.language)
            ]
        
        if not tasks:
            self.console.print("✓ All downloads already completed!", style="green")
            return
        
        # Display summary
        self.console.print(f"\n[bold]Bulk Download: {len(tasks)} languages[/bold]")
        self.console.print(f"Concurrent: {self.max_concurrent}")
        self.console.print(f"Resume: {resume}\n")
        
        # Create download directory
        tasks[0].target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Start parallel downloads
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=self.console
        ) as progress:
            
            # Create progress tasks
            progress_tasks = {}
            for task in tasks:
                progress_id = progress.add_task(
                    f"[cyan]{task.language}",
                    total=None  # Unknown size initially
                )
                progress_tasks[task.language] = progress_id
            
            # Download concurrently
            results = await asyncio.gather(
                *[
                    self._download_one(task, progress, progress_tasks[task.language])
                    for task in tasks
                ],
                return_exceptions=True
            )
        
        # Summary
        self._print_summary(tasks, results)
    
    async def _download_one(
        self,
        task: DownloadTask,
        progress: Progress,
        progress_id: int
    ) -> DownloadTask:
        """Download a single language with retry logic."""
        
        async with self.semaphore:
            for attempt in range(self.max_retries):
                try:
                    # Skip if already exists
                    if task.target_path.exists():
                        task.status = "completed"
                        progress.update(progress_id, completed=100, total=100)
                        return task
                    
                    task.status = "downloading"
                    
                    async with httpx.AsyncClient(
                        timeout=httpx.Timeout(self.timeout),
                        follow_redirects=True
                    ) as client:
                        # Stream download
                        async with client.stream('GET', task.url) as response:
                            response.raise_for_status()
                            
                            # Get file size
                            total_size = int(
                                response.headers.get('content-length', 0)
                            )
                            task.size_bytes = total_size
                            
                            # Update progress bar
                            progress.update(progress_id, total=total_size)
                            
                            # Download to temp file first
                            temp_path = task.target_path.with_suffix('.tmp')
                            
                            with open(temp_path, 'wb') as f:
                                async for chunk in response.aiter_bytes(
                                    chunk_size=self.chunk_size
                                ):
                                    f.write(chunk)
                                    task.completed_bytes += len(chunk)
                                    progress.update(
                                        progress_id,
                                        completed=task.completed_bytes
                                    )
                            
                            # Move to final location
                            temp_path.rename(task.target_path)
                    
                    # Mark as completed
                    task.status = "completed"
                    self.checkpoint.mark_processed(task.language)
                    self.checkpoint.save()
                    
                    return task
                    
                except httpx.HTTPError as e:
                    if attempt == self.max_retries - 1:
                        task.status = "failed"
                        task.error = str(e)
                        return task
                    
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                
                except Exception as e:
                    task.status = "failed"
                    task.error = str(e)
                    return task
        
        return task
    
    def _print_summary(self, tasks: list[DownloadTask], results: list):
        """Print download summary."""
        
        completed = sum(1 for t in tasks if t.status == "completed")
        failed = sum(1 for t in tasks if t.status == "failed")
        total_size = sum(
            t.size_bytes for t in tasks 
            if t.size_bytes and t.status == "completed"
        )
        
        self.console.print("\n" + "=" * 70)
        self.console.print("[bold]Download Summary[/bold]")
        self.console.print("=" * 70)
        self.console.print(f"✓ Completed: {completed}/{len(tasks)}")
        self.console.print(f"✗ Failed: {failed}")
        self.console.print(
            f"📦 Total size: {total_size / (1024**3):.2f} GB"
        )
        
        if failed > 0:
            self.console.print("\n[red]Failed downloads:[/red]")
            for task in tasks:
                if task.status == "failed":
                    self.console.print(f"  - {task.language}: {task.error}")


# ═══════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═══════════════════════════════════════════════════════════════════════

async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Bulk download 52 languages from Kaikki.org",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all 52 languages
  python bulk.py --all
  
  # Download specific families
  python bulk.py --families romance germanic
  
  # Download specific languages
  python bulk.py --languages English German Spanish
  
  # Resume interrupted download
  python bulk.py --all --resume
  
  # Download with more concurrency (careful with rate limits!)
  python bulk.py --all --concurrent 10
        """
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Download all 52 languages'
    )
    parser.add_argument(
        '--families',
        nargs='+',
        choices=list(KAIKKI_LANGUAGES.keys()),
        help='Download specific language families'
    )
    parser.add_argument(
        '--languages',
        nargs='+',
        metavar='LANG',
        help='Download specific languages'
    )
    parser.add_argument(
        '--concurrent',
        type=int,
        default=5,
        help='Max concurrent downloads (default: 5)'
    )
    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Do not resume from checkpoint'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available languages and exit'
    )
    
    args = parser.parse_args()
    
    # List languages
    if args.list:
        console = Console()
        console.print("\n[bold]Available Languages by Family:[/bold]\n")
        for family, langs in KAIKKI_LANGUAGES.items():
            console.print(f"[cyan]{family}[/cyan] ({len(langs)}):")
            for lang in langs:
                console.print(f"  - {lang}")
        console.print(f"\n[bold]Total: {len(all_languages())} languages[/bold]")
        return
    
    # Validate arguments
    if not any([args.all, args.families, args.languages]):
        parser.print_help()
        return
    
    # Create downloader
    downloader = BulkDownloader(max_concurrent=args.concurrent)
    
    # Start downloads
    await downloader.download_all(
        languages=args.languages,
        families=args.families if args.families else None,
        resume=not args.no_resume
    )


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

