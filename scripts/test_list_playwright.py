#!/usr/bin/env python3
"""
Test script for Playwright list fetcher.

Usage:
    python .local-docs/scripts/test_list_playwright.py --region 1 --limit 5
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.crawler.list_fetcher_playwright import ListFetcherPlaywright


async def main(region: int, limit: int, raw: bool = False):
    """Run Playwright list fetch test."""
    print(f"\n{'='*60}")
    print(f"Playwright List Fetcher Test")
    print(f"Region: {region}, Limit: {limit}")
    print(f"{'='*60}\n")

    fetcher = ListFetcherPlaywright()

    try:
        await fetcher.start()

        print("Fetching objects...")
        objects = await fetcher.fetch_objects(region=region, limit=limit)

        print(f"\n{'='*60}")
        print(f"Results: {len(objects)} objects")
        print(f"{'='*60}\n")

        for i, obj in enumerate(objects[:limit], 1):
            print(f"--- Object {i} ---")
            if raw:
                print(json.dumps(obj, ensure_ascii=False, indent=2))
            else:
                # Print key fields only
                print(json.dumps({
                    "id": obj.get("id"),
                    "title": obj.get("title"),
                    "price": obj.get("price"),
                    "kind_name": obj.get("kind_name"),
                    "region": obj.get("region"),
                    "section": obj.get("section"),
                    "area": obj.get("area"),
                    "floor_str": obj.get("floor_str"),
                    "layout_str": obj.get("layout_str"),
                    "tags": obj.get("tags"),
                }, ensure_ascii=False, indent=2))
            print()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await fetcher.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Playwright list fetcher")
    parser.add_argument("--region", type=int, default=1, help="Region code (1=Taipei, 3=New Taipei)")
    parser.add_argument("--limit", type=int, default=5, help="Number of objects to fetch")
    parser.add_argument("--raw", action="store_true", help="Show raw object data")

    args = parser.parse_args()
    asyncio.run(main(args.region, args.limit, args.raw))
