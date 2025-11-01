"""CLI tool for data ingestion.

Provides command-line interface for ingesting dictionary data.
"""

import asyncio
import asyncpg
import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_settings
from storage import IngestService


async def ingest_command(args):
    """Ingest a data file."""
    settings = get_settings()
    
    # Connect to database
    pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=1,
        max_size=5
    )
    
    service = IngestService(pool)
    
    # Register source if catalog provided
    if args.catalog:
        sources = await service.load_source_catalog(args.catalog)
        for source in sources:
            await service.register_source(source)
            print(f"Registered source: {source.id}")
    
    # Ingest file
    if args.file:
        print(f"Ingesting {args.file}...")
        stats = await service.ingest_file(
            file_path=args.file,
            source_id=args.source,
            format=args.format,
            dry_run=args.dry_run
        )
        
        print("\nIngestion Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    await pool.close()


async def reprocess_command(args):
    """Reprocess raw entries with updated pipeline."""
    settings = get_settings()
    
    pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=1,
        max_size=5
    )
    
    service = IngestService(pool)
    
    print(f"Reprocessing source: {args.source or 'all'}...")
    stats = await service.reprocess_with_pipeline(
        source_id=args.source
    )
    
    print("\nReprocessing Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    await pool.close()


async def validate_command(args):
    """Validate entries in database."""
    from backend.storage import ValidatorFactory
    
    settings = get_settings()
    
    pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=1,
        max_size=5
    )
    
    validator = ValidatorFactory.standard_entry_validator()
    
    # Fetch entries to validate
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, headword, ipa, language, definition,
                   etymology, pos_tag, embedding, created_at
            FROM entries
            LIMIT $1
            """,
            args.limit
        )
    
    from backend.core.types import Entry
    entries = [
        Entry(
            id=row['id'],
            headword=row['headword'],
            ipa=row['ipa'],
            language=row['language'],
            definition=row['definition'],
            etymology=row['etymology'],
            pos_tag=row['pos_tag'],
            embedding=row['embedding'],
            created_at=row['created_at']
        )
        for row in rows
    ]
    
    errors_map = validator.batch_validate(entries)
    
    print(f"\nValidated {len(entries)} entries")
    print(f"Errors found: {len(errors_map)}")
    
    if errors_map and not args.quiet:
        print("\nValidation Errors:")
        for entry_id, errors in list(errors_map.items())[:10]:
            print(f"  {entry_id}:")
            for error in errors:
                print(f"    - {error}")
    
    await pool.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="LangViz Data Ingestion CLI"
    )
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # Ingest command
    ingest_parser = subparsers.add_parser(
        'ingest',
        help='Ingest a data file'
    )
    ingest_parser.add_argument(
        '--file',
        required=True,
        help='Path to data file'
    )
    ingest_parser.add_argument(
        '--source',
        required=True,
        help='Source ID from catalog'
    )
    ingest_parser.add_argument(
        '--format',
        required=True,
        choices=['cldf', 'swadesh', 'starling', 'json', 'csv'],
        help='Data format'
    )
    ingest_parser.add_argument(
        '--catalog',
        help='Path to source catalog TOML'
    )
    ingest_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate without storing'
    )
    
    # Reprocess command
    reprocess_parser = subparsers.add_parser(
        'reprocess',
        help='Reprocess raw entries with updated pipeline'
    )
    reprocess_parser.add_argument(
        '--source',
        help='Source ID to reprocess (all if omitted)'
    )
    
    # Validate command
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate entries in database'
    )
    validate_parser.add_argument(
        '--limit',
        type=int,
        default=1000,
        help='Number of entries to validate'
    )
    validate_parser.add_argument(
        '--quiet',
        action='store_true',
        help='Only show summary'
    )
    
    args = parser.parse_args()
    
    # Execute command
    if args.command == 'ingest':
        asyncio.run(ingest_command(args))
    elif args.command == 'reprocess':
        asyncio.run(reprocess_command(args))
    elif args.command == 'validate':
        asyncio.run(validate_command(args))


if __name__ == '__main__':
    main()

