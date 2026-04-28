"""Background and on-demand cleanup of expired PlayStation Store discounts.

PSN refreshes the sale catalogue weekly (new sales appear on Wednesday, old ones
expire on Thursday). The discount parser used to wipe all discount fields before
re-fetching, which broke any sale that was still active. Now the parser only
UPSERTs fresh data and this module owns expiry — both as a periodic background
job and as an admin action grouped by `discount_end`.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# ---------- DB-side queries ----------------------------------------------------

_PRODUCTS_DISCOUNT_HAS = (
    "(COALESCE(discount, 0) > 0 OR COALESCE(discount_percent, 0) > 0 "
    "OR COALESCE(old_price, 0) > 0 OR COALESCE(old_price_uah, 0) > 0 "
    "OR COALESCE(old_price_try, 0) > 0 OR COALESCE(old_price_inr, 0) > 0)"
)

_PRODUCTS_CLEAR_SQL = """
    UPDATE products
    SET discount = 0,
        discount_percent = 0,
        discount_end = NULL,
        old_price = NULL,
        old_price_uah = 0,
        old_price_try = 0,
        old_price_inr = 0,
        updated_at = CURRENT_TIMESTAMP
    WHERE rowid IN ({placeholders})
"""

_PRODUCT_CARDS_CLEAR_SQL = """
    UPDATE product_cards
    SET min_old_price_rub = NULL,
        max_discount_percent = NULL,
        has_discount = 0,
        ua_old_price_uah = NULL,
        ua_old_price_rub = NULL,
        ua_discount_percent = NULL,
        ua_has_discount = 0,
        ua_discount_end = NULL,
        tr_old_price_try = NULL,
        tr_old_price_rub = NULL,
        tr_discount_percent = NULL,
        tr_has_discount = 0,
        tr_discount_end = NULL,
        in_old_price_inr = NULL,
        in_old_price_rub = NULL,
        in_discount_percent = NULL,
        in_has_discount = 0,
        in_discount_end = NULL
    WHERE rowid IN ({placeholders})
"""


@dataclass
class DiscountExpiryStats:
    products_cleared: int = 0
    product_cards_cleared: int = 0
    result_cache_cleared: int = 0
    matched_dates: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "products_cleared": self.products_cleared,
            "product_cards_cleared": self.product_cards_cleared,
            "result_cache_cleared": self.result_cache_cleared,
            "matched_dates": list(self.matched_dates or ()),
        }


# ---------- helpers ------------------------------------------------------------


def _sqlite_db_path() -> str:
    """Resolve the same SQLite path the parser uses without importing parser.py."""
    explicit_path = os.getenv("PARSER_SQLITE_DB_PATH")
    if explicit_path:
        return explicit_path
    project_root = Path(__file__).resolve().parents[2]
    return str(project_root / "products.db")


def _now_utc_string() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _parse_discount_end(value: object) -> Optional[datetime]:
    """Parse a `discount_end` value as naive UTC.

    Stored values come from the parser as strings like '2026-05-06 22:59:00',
    matching PSN's UTC-equivalent timestamps shown to users in their local TZ.
    """
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _expired_filter(threshold: datetime, end: datetime) -> bool:
    return end < threshold


# ---------- DB cleanup ---------------------------------------------------------


def _clear_products_for_rowids(connection: sqlite3.Connection, rowids: list[int]) -> None:
    if not rowids:
        return
    placeholders = ",".join("?" for _ in rowids)
    connection.execute(_PRODUCTS_CLEAR_SQL.format(placeholders=placeholders), rowids)


def _clear_product_cards_for_rowids(connection: sqlite3.Connection, rowids: list[int]) -> None:
    if not rowids:
        return
    placeholders = ",".join("?" for _ in rowids)
    connection.execute(_PRODUCT_CARDS_CLEAR_SQL.format(placeholders=placeholders), rowids)


def _product_cards_exists(connection: sqlite3.Connection) -> bool:
    cursor = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'product_cards'"
    )
    return cursor.fetchone() is not None


def _clear_db_by_predicate(predicate_sql: str, params: Iterable) -> tuple[int, int, list[str]]:
    """Run cleanup against products + product_cards rows matching `predicate_sql`.

    Returns (products_cleared, product_cards_cleared, matched_end_dates).
    """
    db_path = _sqlite_db_path()
    products_cleared = 0
    product_cards_cleared = 0
    matched_dates: list[str] = []

    with closing(sqlite3.connect(db_path)) as connection:
        connection.isolation_level = None  # autocommit

        cursor = connection.execute(
            f"SELECT DISTINCT discount_end FROM products WHERE {predicate_sql} AND {_PRODUCTS_DISCOUNT_HAS}",
            list(params),
        )
        matched_dates = sorted(
            {row[0] for row in cursor.fetchall() if row and row[0]},
        )

        cursor = connection.execute(
            f"SELECT rowid FROM products WHERE {predicate_sql} AND {_PRODUCTS_DISCOUNT_HAS}",
            list(params),
        )
        product_rowids = [row[0] for row in cursor.fetchall()]
        _clear_products_for_rowids(connection, product_rowids)
        products_cleared = len(product_rowids)

        if _product_cards_exists(connection) and matched_dates:
            placeholders = ",".join("?" for _ in matched_dates)
            cursor = connection.execute(
                f"""
                SELECT rowid FROM product_cards
                WHERE (
                    ua_discount_end IN ({placeholders})
                    OR tr_discount_end IN ({placeholders})
                    OR in_discount_end IN ({placeholders})
                )
                """,
                list(matched_dates) * 3,
            )
            card_rowids = [row[0] for row in cursor.fetchall()]
            _clear_product_cards_for_rowids(connection, card_rowids)
            product_cards_cleared = len(card_rowids)

    return products_cleared, product_cards_cleared, matched_dates


# ---------- result.pkl cleanup ------------------------------------------------


def _clear_result_pkl_records(matcher) -> int:
    """Zero out discount fields in result.pkl for records matching `matcher(end_dt)`.

    Imports the parser lazily — it is a heavy module and we don't want to drag it
    into web-process import paths just for cleanup helpers.
    """
    try:
        from parser import (  # type: ignore
            _load_manual_result_cache,
            _save_manual_result_cache,
        )
    except Exception:
        logger.exception("Failed to import parser cache helpers; skipping result.pkl cleanup")
        return 0

    try:
        records = _load_manual_result_cache()
    except Exception:
        logger.exception("Failed to load result.pkl; skipping cleanup")
        return 0

    changed = 0
    for record in records:
        end = _parse_discount_end(record.get("discount_end"))
        if end is None:
            continue
        if not matcher(end):
            continue
        if not any(
            (record.get(field) or 0) for field in (
                "discount",
                "discount_percent",
                "old_price",
                "old_price_uah",
                "old_price_try",
                "old_price_inr",
            )
        ) and not record.get("discount_end"):
            continue
        record["discount"] = 0
        record["discount_percent"] = 0
        record["discount_end"] = None
        record["old_price"] = None
        record["old_price_uah"] = 0.0
        record["old_price_try"] = 0.0
        record["old_price_inr"] = 0.0
        changed += 1

    if changed:
        try:
            _save_manual_result_cache(records)
        except Exception:
            logger.exception("Failed to save result.pkl after cleanup")
            return 0
    return changed


# ---------- product_cards refresh ---------------------------------------------


def _refresh_product_cards_for_ids(product_ids: list[str]) -> None:
    if not product_ids:
        return
    try:
        from app.database.connection import (  # type: ignore
            engine as _app_engine,
            _ensure_product_cards_search_index,
        )
        from app.database.product_card_rebuilder import rebuild_product_cards_for_ids  # type: ignore
        from config.settings import settings  # type: ignore

        if not getattr(settings, "PRODUCTS_USE_CARDS_TABLE", False):
            return

        with _app_engine.begin() as connection:
            rebuild_product_cards_for_ids(connection, product_ids)
            _ensure_product_cards_search_index(connection)
    except Exception:
        logger.exception("Failed to refresh product_cards after discount expiry")


def _affected_product_ids_for_predicate(predicate_sql: str, params: Iterable) -> list[str]:
    db_path = _sqlite_db_path()
    with closing(sqlite3.connect(db_path)) as connection:
        cursor = connection.execute(
            f"SELECT DISTINCT id FROM products WHERE {predicate_sql} AND {_PRODUCTS_DISCOUNT_HAS}",
            list(params),
        )
        return [row[0] for row in cursor.fetchall() if row and row[0]]


# ---------- Public API ---------------------------------------------------------


def clear_expired_discounts_now() -> DiscountExpiryStats:
    """Clear every product whose `discount_end` is already in the past (UTC).

    Synchronous; intended to run inside `asyncio.to_thread` from the loop.
    """
    threshold = _now_utc_string()
    predicate_sql = "discount_end IS NOT NULL AND discount_end != '' AND discount_end < ?"
    params = (threshold,)

    affected_ids = _affected_product_ids_for_predicate(predicate_sql, params)
    products_cleared, product_cards_cleared, matched_dates = _clear_db_by_predicate(predicate_sql, params)

    cache_cleared = _clear_result_pkl_records(
        lambda end_dt: end_dt < datetime.now(timezone.utc).replace(tzinfo=None)
    )

    if products_cleared or product_cards_cleared or cache_cleared:
        logger.info(
            "Discount expiry sweep: products=%s, product_cards=%s, result.pkl=%s, dates=%s",
            products_cleared,
            product_cards_cleared,
            cache_cleared,
            matched_dates,
        )
        _refresh_product_cards_for_ids(affected_ids)

    return DiscountExpiryStats(
        products_cleared=products_cleared,
        product_cards_cleared=product_cards_cleared,
        result_cache_cleared=cache_cleared,
        matched_dates=matched_dates,
    )


def list_discount_end_groups() -> list[dict]:
    """Return distinct `discount_end` values + product counts, sorted ASC.

    Used by the admin UI to let an operator pick which sale wave to wipe.
    """
    db_path = _sqlite_db_path()
    with closing(sqlite3.connect(db_path)) as connection:
        cursor = connection.execute(
            f"""
            SELECT discount_end, COUNT(DISTINCT id) AS product_count, COUNT(*) AS rows_count
            FROM products
            WHERE discount_end IS NOT NULL AND discount_end != '' AND {_PRODUCTS_DISCOUNT_HAS}
            GROUP BY discount_end
            ORDER BY discount_end ASC
            """
        )
        rows = cursor.fetchall()
    return [
        {
            "discount_end": row[0],
            "products_count": int(row[1] or 0),
            "rows_count": int(row[2] or 0),
        }
        for row in rows
    ]


def clear_discounts_ending_on(discount_ends: Iterable[str]) -> DiscountExpiryStats:
    """Clear all products whose `discount_end` matches any of the given values.

    Called from the admin endpoint after the operator confirms the selection.
    """
    end_values = sorted({str(value).strip() for value in discount_ends if str(value).strip()})
    if not end_values:
        return DiscountExpiryStats()

    placeholders = ",".join("?" for _ in end_values)
    predicate_sql = f"discount_end IN ({placeholders})"

    affected_ids = _affected_product_ids_for_predicate(predicate_sql, end_values)
    products_cleared, product_cards_cleared, matched_dates = _clear_db_by_predicate(
        predicate_sql, end_values
    )

    end_set = set(end_values)
    cache_cleared = _clear_result_pkl_records(
        lambda end_dt: end_dt.strftime("%Y-%m-%d %H:%M:%S") in end_set
        or end_dt.strftime("%Y-%m-%d") in end_set
    )

    if products_cleared or product_cards_cleared or cache_cleared:
        _refresh_product_cards_for_ids(affected_ids)

    return DiscountExpiryStats(
        products_cleared=products_cleared,
        product_cards_cleared=product_cards_cleared,
        result_cache_cleared=cache_cleared,
        matched_dates=matched_dates,
    )


# ---------- Background loop ----------------------------------------------------


_loop_task: asyncio.Task | None = None


def _cleanup_interval_seconds() -> int:
    raw = (os.getenv("DISCOUNT_CLEANUP_INTERVAL_SECONDS") or "").strip()
    try:
        value = int(raw) if raw else 300
    except ValueError:
        value = 300
    return max(value, 60)


async def expire_finished_discounts_loop() -> None:
    interval = _cleanup_interval_seconds()
    logger.info("Discount expiry loop started: interval=%ss", interval)
    try:
        while True:
            try:
                await asyncio.to_thread(clear_expired_discounts_now)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Discount expiry sweep failed; will retry on next tick")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Discount expiry loop cancelled")
        raise


def start_discount_expiry_loop() -> asyncio.Task | None:
    global _loop_task
    if _loop_task is not None and not _loop_task.done():
        return _loop_task
    if (os.getenv("DISCOUNT_CLEANUP_DISABLED") or "").strip().lower() in {"1", "true", "yes"}:
        logger.info("Discount expiry loop disabled by DISCOUNT_CLEANUP_DISABLED")
        return None
    _loop_task = asyncio.create_task(expire_finished_discounts_loop(), name="discount-expiry-loop")
    return _loop_task


async def stop_discount_expiry_loop() -> None:
    global _loop_task
    task = _loop_task
    if task is None:
        return
    _loop_task = None
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass
