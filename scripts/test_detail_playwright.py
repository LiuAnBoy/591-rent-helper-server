#!/usr/bin/env python3
"""
Test script for Playwright detail fetcher.

Usage:
    uv run python scripts/test_detail_playwright.py 20506491
    uv run python scripts/test_detail_playwright.py 20506491 20506488 20506485
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawler.detail_fetcher_playwright import DetailFetcherPlaywright


async def main(object_ids: list[int]):
    """Run Playwright detail fetch test."""
    print(f"\n{'='*60}")
    print(f"Playwright Detail Fetcher Test")
    print(f"Object IDs: {object_ids}")
    print(f"{'='*60}\n")

    fetcher = DetailFetcherPlaywright()

    try:
        await fetcher.start()

        for object_id in object_ids:
            print(f"\n--- Object {object_id} ---")
            print(f"Fetching detail...")

            result = await fetcher.fetch_detail_raw(object_id)

            if result:
                print(f"Status: SUCCESS")
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"Status: FAILED (returned None)")

            print()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await fetcher.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Playwright detail fetcher")
    parser.add_argument("object_ids", type=int, nargs="+", help="Object ID(s) to fetch")

    args = parser.parse_args()
    asyncio.run(main(args.object_ids))
