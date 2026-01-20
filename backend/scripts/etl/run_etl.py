#!/usr/bin/env python3
"""
Medical Knowledge ETL Pipeline - Main Runner

Downloads and processes medical data from:
1. MedlinePlus (NIH) - Health topics XML
2. openFDA - Drug label JSON

Usage:
    python -m scripts.etl.run_etl [--all|--medlineplus|--openfda] [options]

Examples:
    # Run all ETL pipelines
    python -m scripts.etl.run_etl --all

    # Run only MedlinePlus ETL
    python -m scripts.etl.run_etl --medlineplus

    # Run openFDA ETL with custom file
    python -m scripts.etl.run_etl --openfda --input /path/to/file.json

    # Process with limit (for testing)
    python -m scripts.etl.run_etl --all --limit 100
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.etl.config import (
    OUTPUT_DIR, DOWNLOADS_DIR,
    MEDLINEPLUS_XML_URLS, OPENFDA_DRUG_LABEL_URL,
    MAX_RECORDS_PER_SOURCE
)
from scripts.etl.medlineplus_etl import MedlinePlusETL
from scripts.etl.openfda_etl import OpenFDAETL
from scripts.etl.dedup import deduplicate_entries, validate_no_duplicates
from scripts.etl.schemas import ETLResult


def print_banner():
    """Print ETL banner"""
    print("=" * 60)
    print("    Medical Knowledge ETL Pipeline")
    print("    Transforms MedlinePlus & openFDA data")
    print("=" * 60)
    print()


def run_medlineplus_etl(
    url: Optional[str] = None,
    xml_path: Optional[Path] = None,
    limit: Optional[int] = None
) -> Dict:
    """Run MedlinePlus ETL pipeline"""
    print("\n" + "=" * 40)
    print("Running MedlinePlus ETL")
    print("=" * 40)

    # Set limit if provided
    if limit:
        import scripts.etl.config as config
        config.MAX_RECORDS_PER_SOURCE = limit

    etl = MedlinePlusETL()

    try:
        # Use default URL if not provided
        if not url and not xml_path:
            url = MEDLINEPLUS_XML_URLS['health_topics']

        results = etl.process(xml_path=xml_path, url=url)

        # Deduplicate
        print("Deduplicating entries...")
        deduped, removed = deduplicate_entries(results)
        print(f"Removed {removed} duplicates")

        # Validate
        warnings = validate_no_duplicates(deduped)
        if warnings:
            print(f"Validation warnings: {len(warnings)}")
            for w in warnings[:5]:
                print(f"  - {w}")

        # Save
        output_path = etl.save_results(deduped)

        return {
            'source': 'MedlinePlus',
            'status': 'success',
            'total_processed': etl.processed_count,
            'after_dedup': len(deduped),
            'duplicates_removed': removed,
            'output_file': str(output_path)
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'source': 'MedlinePlus',
            'status': 'failed',
            'error': str(e)
        }


def run_openfda_etl(
    url: Optional[str] = None,
    json_path: Optional[Path] = None,
    limit: Optional[int] = None
) -> Dict:
    """Run openFDA ETL pipeline"""
    print("\n" + "=" * 40)
    print("Running openFDA ETL")
    print("=" * 40)

    # Set limit if provided
    if limit:
        import scripts.etl.config as config
        config.MAX_RECORDS_PER_SOURCE = limit

    etl = OpenFDAETL()

    try:
        # Use default URL if not provided
        if not url and not json_path:
            url = OPENFDA_DRUG_LABEL_URL

        results = etl.process(json_path=json_path, url=url)

        # Deduplicate
        print("Deduplicating entries...")
        deduped, removed = deduplicate_entries(results)
        print(f"Removed {removed} duplicates")

        # Validate
        warnings = validate_no_duplicates(deduped)
        if warnings:
            print(f"Validation warnings: {len(warnings)}")
            for w in warnings[:5]:
                print(f"  - {w}")

        # Save
        output_path = etl.save_results(deduped)

        return {
            'source': 'openFDA',
            'status': 'success',
            'total_processed': etl.processed_count,
            'after_dedup': len(deduped),
            'duplicates_removed': removed,
            'output_file': str(output_path)
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'source': 'openFDA',
            'status': 'failed',
            'error': str(e)
        }


def merge_with_existing(
    new_entries: List[Dict],
    existing_file: Path,
    output_file: Optional[Path] = None
) -> Dict:
    """
    Merge new entries with existing JSON file

    Args:
        new_entries: New entries to merge
        existing_file: Path to existing JSON file
        output_file: Output path (defaults to existing_file)

    Returns:
        Merge result summary
    """
    if not existing_file.exists():
        print(f"Existing file not found: {existing_file}")
        return {'status': 'skipped', 'reason': 'file_not_found'}

    # Load existing
    with open(existing_file, 'r', encoding='utf-8') as f:
        existing = json.load(f)

    print(f"Existing entries: {len(existing)}")
    print(f"New entries: {len(new_entries)}")

    # Combine
    combined = existing + new_entries

    # Deduplicate
    deduped, removed = deduplicate_entries(combined)
    print(f"After dedup: {len(deduped)} (removed {removed})")

    # Save
    output = output_file or existing_file
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)

    return {
        'status': 'success',
        'existing_count': len(existing),
        'new_count': len(new_entries),
        'final_count': len(deduped),
        'duplicates_removed': removed,
        'output_file': str(output)
    }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Medical Knowledge ETL Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Pipeline selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--all', action='store_true',
        help='Run all ETL pipelines'
    )
    group.add_argument(
        '--medlineplus', action='store_true',
        help='Run MedlinePlus ETL only'
    )
    group.add_argument(
        '--openfda', action='store_true',
        help='Run openFDA ETL only'
    )

    # Input options
    parser.add_argument(
        '--input', '-i', type=Path,
        help='Path to local input file (XML for MedlinePlus, JSON for openFDA)'
    )
    parser.add_argument(
        '--url', type=str,
        help='URL to download data from (overrides default)'
    )

    # Processing options
    parser.add_argument(
        '--limit', type=int,
        help='Limit number of records to process (for testing)'
    )
    parser.add_argument(
        '--merge', action='store_true',
        help='Merge with existing data files instead of replacing'
    )

    # Output options
    parser.add_argument(
        '--output', '-o', type=Path,
        help='Output file path (overrides default)'
    )

    args = parser.parse_args()

    print_banner()
    results = []

    start_time = datetime.now()

    # Run selected pipelines
    if args.all or args.medlineplus:
        result = run_medlineplus_etl(
            url=args.url if args.medlineplus else None,
            xml_path=args.input if args.medlineplus else None,
            limit=args.limit
        )
        results.append(result)

        # Merge with existing if requested
        if args.merge and result.get('status') == 'success':
            existing_path = OUTPUT_DIR / 'symptoms_diseases.json'
            if existing_path.exists():
                with open(result['output_file'], 'r', encoding='utf-8') as f:
                    new_entries = json.load(f)
                merge_result = merge_with_existing(new_entries, existing_path)
                result['merge'] = merge_result

    if args.all or args.openfda:
        result = run_openfda_etl(
            url=args.url if args.openfda else None,
            json_path=args.input if args.openfda else None,
            limit=args.limit
        )
        results.append(result)

        # Merge with existing if requested
        if args.merge and result.get('status') == 'success':
            existing_path = OUTPUT_DIR / 'medications.json'
            if existing_path.exists():
                with open(result['output_file'], 'r', encoding='utf-8') as f:
                    new_entries = json.load(f)
                merge_result = merge_with_existing(new_entries, existing_path)
                result['merge'] = merge_result

    # Print summary
    elapsed = datetime.now() - start_time
    print("\n" + "=" * 60)
    print("ETL Pipeline Summary")
    print("=" * 60)
    print(f"Duration: {elapsed}")
    print()

    for result in results:
        print(f"\n{result.get('source', 'Unknown')}:")
        print(f"  Status: {result.get('status', 'unknown')}")
        if result.get('status') == 'success':
            print(f"  Processed: {result.get('total_processed', 0)}")
            print(f"  After dedup: {result.get('after_dedup', 0)}")
            print(f"  Output: {result.get('output_file', 'N/A')}")
        elif result.get('error'):
            print(f"  Error: {result.get('error')}")

    print("\n" + "=" * 60)

    # Return success if all pipelines succeeded
    success = all(r.get('status') == 'success' for r in results)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
