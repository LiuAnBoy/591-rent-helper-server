#!/usr/bin/env python3
"""
Test script for BS4 detail fetcher.

Usage:
    uv run python scripts/test_detail_bs4.py 20506491
    uv run python scripts/test_detail_bs4.py 20506491 20506488 20506485
    uv run python scripts/test_detail_bs4.py 99999999  # Test 404 handling
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawler.detail_fetcher_bs4 import DetailFetcherBs4


async def main(object_ids: list[int]):
    """Run BS4 detail fetch test."""
    print(f"\n{'=' * 60}")
    print("BS4 Detail Fetcher Test")
    print(f"Object IDs: {object_ids}")
    print(f"{'=' * 60}\n")

    fetcher = DetailFetcherBs4()

    stats = {"success": 0, "not_found": 0, "error": 0}

    try:
        await fetcher.start()

        for object_id in object_ids:
            print(f"\n--- Object {object_id} ---")
            print("Fetching detail...")

            result, status = await fetcher.fetch_detail_raw(object_id)

            stats[status] += 1

            if status == "success":
                print("Status: SUCCESS")
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif status == "not_found":
                print("Status: NOT_FOUND (404)")
            else:
                print("Status: ERROR")

            print()

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await fetcher.close()

    # Print summary
    print(f"{'=' * 60}")
    print(
        f"Summary: {stats['success']} success, {stats['not_found']} not_found, {stats['error']} error"
    )
    print(f"{'=' * 60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test BS4 detail fetcher")
    parser.add_argument("object_ids", type=int, nargs="+", help="Object ID(s) to fetch")

    args = parser.parse_args()
    asyncio.run(main(args.object_ids))
