"""Тест-скрипт: проставить фейковую скидку на товар и проверить очистку.

Usage:
    # Скидка с истёкшей датой (для теста авто-очистки + кнопки в админке)
    python3 scripts/seed_test_discount.py

    # Скидка с конкретной датой и % (например, для проверки кнопки)
    python3 scripts/seed_test_discount.py --discount-end "2026-04-29 22:59:00" --percent 50

    # Для другого товара
    python3 scripts/seed_test_discount.py --product-id UP9000-CUSA12345_00-EXAMPLE0000

    # Посмотреть текущие значения, ничего не меняя
    python3 scripts/seed_test_discount.py --show-only

После выполнения:
  1. В админке («Скидки» → «Очистить по дате») должна появиться выбранная дата
     с этим товаром в счётчике.
  2. Если discount_end в прошлом — фоновая задача в течение 5 минут (или быстрее,
     если поменял DISCOUNT_CLEANUP_INTERVAL_SECONDS) должна сама обнулить запись.
  3. Можно сразу нажать в админке «Очистить по дате» → выбрать эту дату →
     «Удалить выбранные» → «Точно удалить?» — и проверить, что строки чистятся
     в products, product_cards и result.pkl.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRODUCT_ID = "EP9000-CUSA07412_00-0000000GODOFWARN"
DEFAULT_PERCENT = 50
DEFAULT_DISCOUNT_END = "2026-04-29 22:59:00"  # в прошлом — поймает авто-очистка


def _resolve_db_path() -> str:
    explicit = os.getenv("PARSER_SQLITE_DB_PATH")
    if explicit:
        return explicit
    return str(PROJECT_ROOT / "products.db")


def _print_current_state(connection: sqlite3.Connection, product_id: str) -> None:
    cursor = connection.execute(
        """
        SELECT region, discount, discount_percent, discount_end,
               price, old_price,
               price_uah, old_price_uah,
               price_try, old_price_try,
               price_inr, old_price_inr
        FROM products
        WHERE id = ?
        ORDER BY region
        """,
        (product_id,),
    )
    rows = cursor.fetchall()
    print(f"\n[products] id={product_id} — найдено строк: {len(rows)}")
    for row in rows:
        region, discount, discount_percent, discount_end = row[0], row[1], row[2], row[3]
        price, old_price = row[4], row[5]
        loc_prices = {
            "UAH": (row[6], row[7]),
            "TRY": (row[8], row[9]),
            "INR": (row[10], row[11]),
        }
        print(
            f"  region={region:<3} discount={discount} discount_percent={discount_percent} "
            f"discount_end={discount_end} price={price} old_price={old_price} "
            f"local={loc_prices}"
        )

    cursor = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='product_cards'"
    )
    if cursor.fetchone():
        cursor = connection.execute(
            """
            SELECT card_id, has_discount, max_discount_percent,
                   ua_has_discount, ua_discount_end,
                   tr_has_discount, tr_discount_end,
                   in_has_discount, in_discount_end
            FROM product_cards
            WHERE card_id = ?
               OR ua_product_id = ?
               OR tr_product_id = ?
               OR in_product_id = ?
            """,
            (product_id, product_id, product_id, product_id),
        )
        card_row = cursor.fetchone()
        print(f"[product_cards] id={product_id}")
        if card_row:
            print(
                f"  has_discount={card_row[1]} max_discount_percent={card_row[2]} "
                f"ua_has_discount={card_row[3]}/{card_row[4]} "
                f"tr_has_discount={card_row[5]}/{card_row[6]} "
                f"in_has_discount={card_row[7]}/{card_row[8]}"
            )
        else:
            print("  (карточка не найдена)")


def _seed_products(
    connection: sqlite3.Connection,
    *,
    product_id: str,
    percent: int,
    discount_end: str,
) -> int:
    factor = (100 - percent) / 100.0
    cursor = connection.execute(
        """
        UPDATE products
        SET discount = ?,
            discount_percent = ?,
            discount_end = ?,
            old_price_uah = CASE WHEN COALESCE(price_uah, 0) > 0 AND COALESCE(old_price_uah, 0) <= 0
                                 THEN ROUND(price_uah / ?, 2) ELSE old_price_uah END,
            old_price_try = CASE WHEN COALESCE(price_try, 0) > 0 AND COALESCE(old_price_try, 0) <= 0
                                 THEN ROUND(price_try / ?, 2) ELSE old_price_try END,
            old_price_inr = CASE WHEN COALESCE(price_inr, 0) > 0 AND COALESCE(old_price_inr, 0) <= 0
                                 THEN ROUND(price_inr / ?, 2) ELSE old_price_inr END,
            old_price = CASE WHEN COALESCE(price_rub, 0) > 0 AND COALESCE(old_price, 0) <= 0
                             THEN ROUND(price_rub / ?, 2) ELSE old_price END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (percent, percent, discount_end, factor, factor, factor, factor, product_id),
    )
    return cursor.rowcount


def _seed_product_cards(
    connection: sqlite3.Connection,
    *,
    product_id: str,
    percent: int,
    discount_end: str,
) -> int:
    cursor = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='product_cards'"
    )
    if not cursor.fetchone():
        return 0
    cursor = connection.execute(
        """
        UPDATE product_cards
        SET has_discount = 1,
            max_discount_percent = ?,
            ua_has_discount = CASE WHEN COALESCE(ua_price_rub, 0) > 0 THEN 1 ELSE ua_has_discount END,
            ua_discount_percent = CASE WHEN COALESCE(ua_price_rub, 0) > 0 THEN ? ELSE ua_discount_percent END,
            ua_discount_end = CASE WHEN COALESCE(ua_price_rub, 0) > 0 THEN ? ELSE ua_discount_end END,
            tr_has_discount = CASE WHEN COALESCE(tr_price_rub, 0) > 0 THEN 1 ELSE tr_has_discount END,
            tr_discount_percent = CASE WHEN COALESCE(tr_price_rub, 0) > 0 THEN ? ELSE tr_discount_percent END,
            tr_discount_end = CASE WHEN COALESCE(tr_price_rub, 0) > 0 THEN ? ELSE tr_discount_end END,
            in_has_discount = CASE WHEN COALESCE(in_price_rub, 0) > 0 THEN 1 ELSE in_has_discount END,
            in_discount_percent = CASE WHEN COALESCE(in_price_rub, 0) > 0 THEN ? ELSE in_discount_percent END,
            in_discount_end = CASE WHEN COALESCE(in_price_rub, 0) > 0 THEN ? ELSE in_discount_end END
        WHERE card_id = ?
           OR ua_product_id = ?
           OR tr_product_id = ?
           OR in_product_id = ?
        """,
        (
            percent, percent, discount_end, percent, discount_end, percent, discount_end,
            product_id, product_id, product_id, product_id,
        ),
    )
    return cursor.rowcount


def main() -> int:
    parser = argparse.ArgumentParser(description="Засеять тестовую скидку на товар.")
    parser.add_argument("--product-id", default=DEFAULT_PRODUCT_ID, help="ID товара (без региона).")
    parser.add_argument(
        "--discount-end",
        default=DEFAULT_DISCOUNT_END,
        help="Метка discount_end (UTC) формата 'YYYY-MM-DD HH:MM:SS'.",
    )
    parser.add_argument("--percent", type=int, default=DEFAULT_PERCENT, help="Процент скидки.")
    parser.add_argument("--db", default=_resolve_db_path(), help="Путь к products.db.")
    parser.add_argument("--show-only", action="store_true", help="Только показать текущее состояние.")
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"[!] БД не найдена: {args.db}", file=sys.stderr)
        return 2

    print(f"DB: {args.db}")
    print(f"Product: {args.product_id}")
    print(f"Discount end: {args.discount_end}  (UTC)")
    print(f"Percent: {args.percent}%")

    with closing(sqlite3.connect(args.db)) as connection:
        connection.isolation_level = None  # autocommit

        print("\n=== ДО ===")
        _print_current_state(connection, args.product_id)

        if args.show_only:
            return 0

        products_updated = _seed_products(
            connection,
            product_id=args.product_id,
            percent=args.percent,
            discount_end=args.discount_end,
        )
        cards_updated = _seed_product_cards(
            connection,
            product_id=args.product_id,
            percent=args.percent,
            discount_end=args.discount_end,
        )

        if products_updated == 0:
            print(f"\n[!] В products нет строк с id={args.product_id}", file=sys.stderr)
            return 1

        print(f"\nОбновлено: products={products_updated}, product_cards={cards_updated}")

        print("\n=== ПОСЛЕ ===")
        _print_current_state(connection, args.product_id)

    print(
        "\nГотово. Теперь:\n"
        "  • Открой админку → раздел «Скидки» → кнопка «Очистить по дате» — должна\n"
        f"    появиться дата {args.discount_end} с этим товаром.\n"
        "  • Или подожди до 5 минут — фоновая задача сама очистит (если дата в прошлом).\n"
        "  • Перезапусти этот скрипт с --show-only, чтобы увидеть, что скидки занулились."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
