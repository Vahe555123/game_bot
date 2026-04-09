from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import aiohttp


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from parser import SQLITE_DB_PATH, get_localization_for_region  # noqa: E402


REGION_TO_LOCALE = {
    "UA": "ru-ua",
    "TR": "en-tr",
    "IN": "en-in",
}


@dataclass
class ProductRegions:
    product_id: str
    regions: Dict[str, str | None]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh only regional localization fields in products.db.",
    )
    parser.add_argument(
        "--db",
        default=SQLITE_DB_PATH,
        help="Path to SQLite database. Defaults to DATABASE_URL/products.db.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=40,
        help="How many product ids to process before committing.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=6,
        help="How many product ids to fetch in parallel.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for smoke testing.",
    )
    parser.add_argument(
        "--checkpoint-file",
        default=str(ROOT / "scripts" / ".regional-localizations-checkpoint.json"),
        help="Checkpoint file for resume support.",
    )
    parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="Ignore and overwrite previous checkpoint.",
    )
    return parser.parse_args()


def detect_localization_code(voice: str, subtitles: str) -> str:
    voice_lower = (voice or "").lower()
    subtitles_lower = (subtitles or "").lower()

    has_russian_voice = "русский" in voice_lower or "russian" in voice_lower
    has_russian_subtitles = "русский" in subtitles_lower or "russian" in subtitles_lower

    if has_russian_voice:
        return "full"
    if has_russian_subtitles:
        return "subtitles"
    return "none"


def load_products(db_path: Path, limit: int | None = None) -> List[ProductRegions]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, region, localization
        FROM products
        WHERE region IN ('UA', 'TR', 'IN')
        ORDER BY id, region
        """
    )

    products: List[ProductRegions] = []
    current_id: str | None = None
    current_regions: Dict[str, str | None] = {}

    for row in cur.fetchall():
        product_id = row["id"]
        if current_id is None:
            current_id = product_id

        if product_id != current_id:
            products.append(ProductRegions(product_id=current_id, regions=current_regions))
            if limit is not None and len(products) >= limit:
                conn.close()
                return products
            current_id = product_id
            current_regions = {}

        current_regions[row["region"]] = row["localization"]

    if current_id is not None and (limit is None or len(products) < limit):
        products.append(ProductRegions(product_id=current_id, regions=current_regions))

    conn.close()
    return products


def load_checkpoint(path: Path, reset: bool) -> int:
    if reset or not path.exists():
        return 0

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return max(0, int(data.get("next_index", 0)))
    except Exception:
        return 0


def save_checkpoint(path: Path, next_index: int, total: int, stats: Dict[str, int]) -> None:
    payload = {
        "next_index": next_index,
        "total_products": total,
        "stats": stats,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def refresh_product(
    session: aiohttp.ClientSession,
    item: ProductRegions,
    semaphore: asyncio.Semaphore,
) -> Tuple[str, Dict[str, str], List[str]]:
    async with semaphore:
        updates: Dict[str, str] = {}
        failed_regions: List[str] = []

        for region in item.regions:
            locale = REGION_TO_LOCALE.get(region)
            if not locale:
                continue

            voice, subtitles = await get_localization_for_region(session, item.product_id, locale)
            if voice is None and subtitles is None:
                failed_regions.append(region)
                continue

            updates[region] = detect_localization_code(voice, subtitles)

        return item.product_id, updates, failed_regions


def apply_updates(
    db_path: Path,
    batch: Iterable[Tuple[str, Dict[str, str], List[str]]],
    current_map: Dict[str, Dict[str, str | None]],
) -> Dict[str, int]:
    stats = {
        "regions_checked": 0,
        "regions_updated": 0,
        "rows_changed": 0,
        "failed_regions": 0,
    }

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    for product_id, updates, failed_regions in batch:
        stats["failed_regions"] += len(failed_regions)

        for region, localization in updates.items():
            stats["regions_checked"] += 1
            previous = current_map[product_id].get(region)
            cur.execute(
                """
                UPDATE products
                SET localization = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND region = ?
                """,
                (localization, product_id, region),
            )
            stats["regions_updated"] += 1
            if previous != localization:
                stats["rows_changed"] += 1
                current_map[product_id][region] = localization

    conn.commit()
    conn.close()
    return stats


def print_progress(done: int, total: int, stats: Dict[str, int]) -> None:
    percent = (done / total * 100) if total else 100
    print(
        f"[{done}/{total}] {percent:5.1f}% | "
        f"changed={stats['rows_changed']} | "
        f"checked={stats['regions_checked']} | "
        f"failed_regions={stats['failed_regions']}"
    )


async def run() -> None:
    args = parse_args()
    db_path = Path(args.db).resolve()
    checkpoint_path = Path(args.checkpoint_file).resolve()

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    products = load_products(db_path, limit=args.limit)
    total_products = len(products)
    if total_products == 0:
        print("No UA/TR/IN products found.")
        return

    next_index = load_checkpoint(checkpoint_path, args.reset_progress)
    next_index = min(next_index, total_products)

    current_map = {item.product_id: dict(item.regions) for item in products}
    stats = {
        "regions_checked": 0,
        "regions_updated": 0,
        "rows_changed": 0,
        "failed_regions": 0,
    }

    timeout = aiohttp.ClientTimeout(total=60)
    connector = aiohttp.TCPConnector(limit=max(args.concurrency * 2, 8))
    semaphore = asyncio.Semaphore(args.concurrency)

    print(f"DB: {db_path}")
    print(f"Products to process: {total_products}")
    print(f"Starting from index: {next_index}")
    print(f"Batch size: {args.batch_size}, concurrency: {args.concurrency}")

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        for start in range(next_index, total_products, args.batch_size):
            chunk = products[start:start + args.batch_size]
            results = await asyncio.gather(
                *(refresh_product(session, item, semaphore) for item in chunk)
            )

            batch_stats = apply_updates(db_path, results, current_map)
            for key, value in batch_stats.items():
                stats[key] += value

            done = min(start + len(chunk), total_products)
            save_checkpoint(checkpoint_path, done, total_products, stats)
            print_progress(done, total_products, stats)

    if checkpoint_path.exists():
        checkpoint_path.unlink()

    print("Done.")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(run())
