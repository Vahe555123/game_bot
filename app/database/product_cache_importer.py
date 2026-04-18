from __future__ import annotations

import json
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, TypeVar

from sqlalchemy import text

from config.settings import settings

logger = logging.getLogger(__name__)
T = TypeVar("T")

IMPORTER_VERSION = "1"
IMPORT_STATE_TABLE = "product_cache_import_state"
TEMP_KEYS_TABLE = "_product_cache_import_keys"

PRODUCT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "TEXT"),
    ("category", "TEXT"),
    ("region", "TEXT"),
    ("type", "TEXT"),
    ("name", "TEXT"),
    ("main_name", "TEXT"),
    ("image", "TEXT"),
    ("compound", "TEXT"),
    ("platforms", "TEXT"),
    ("publisher", "TEXT"),
    ("localization", "TEXT"),
    ("rating", "REAL"),
    ("info", "TEXT"),
    ("price", "REAL"),
    ("old_price", "REAL"),
    ("ps_price", "REAL"),
    ("plus_types", "TEXT"),
    ("ea_price", "REAL"),
    ("ps_plus", "INTEGER"),
    ("ea_access", "TEXT"),
    ("discount", "REAL"),
    ("discount_end", "TEXT"),
    ("tags", "TEXT"),
    ("edition", "TEXT"),
    ("description", "TEXT"),
    ("price_uah", "REAL"),
    ("old_price_uah", "REAL"),
    ("price_try", "REAL"),
    ("old_price_try", "REAL"),
    ("price_inr", "REAL"),
    ("old_price_inr", "REAL"),
    ("price_rub", "REAL"),
    ("price_rub_region", "TEXT"),
    ("ps_plus_price_uah", "REAL"),
    ("ps_plus_price_try", "REAL"),
    ("ps_plus_price_inr", "REAL"),
    ("players_min", "INTEGER"),
    ("players_max", "INTEGER"),
    ("players_online", "INTEGER"),
    ("name_localized", "TEXT"),
    ("search_names", "TEXT"),
    ("discount_percent", "INTEGER"),
    ("ps_plus_collection", "TEXT"),
    ("created_at", "TIMESTAMP"),
    ("updated_at", "TIMESTAMP"),
)

INSERT_COLUMNS = tuple(column for column, _ in PRODUCT_COLUMNS)
INSERT_COLUMNS_SQL = ", ".join(f'"{column}"' for column in INSERT_COLUMNS)
INSERT_VALUES_SQL = ", ".join(f":{column}" for column in INSERT_COLUMNS)
UPSERT_ASSIGNMENTS_SQL = ", ".join(
    f'"{column}" = excluded."{column}"' for column in INSERT_COLUMNS if column not in {"id", "region"}
)
UPSERT_PRODUCTS_SQL = f"""
    INSERT INTO products ({INSERT_COLUMNS_SQL})
    VALUES ({INSERT_VALUES_SQL})
    ON CONFLICT(id, region) DO UPDATE SET {UPSERT_ASSIGNMENTS_SQL}
"""

DEFAULT_CURRENCY_RATES: tuple[tuple[str, str, float, float | None, float, int], ...] = (
    ("UAH", "RUB", 0, 1000, 2.5, 1),
    ("UAH", "RUB", 1000, None, 2.5, 1),
    ("TRY", "RUB", 0, 1000, 3.0, 1),
    ("TRY", "RUB", 1000, None, 3.0, 1),
    ("INR", "RUB", 0, 1000, 1.2, 1),
    ("INR", "RUB", 1000, None, 1.2, 1),
)


@dataclass(frozen=True)
class ProductCacheImportResult:
    changed: bool
    reason: str
    source_path: Path | None = None
    source_count: int = 0
    prepared_count: int = 0
    deleted_stale: int = 0


@dataclass(frozen=True)
class PromoSets:
    extra: set[str]
    deluxe: set[str]
    all: set[str]


class CurrencyConverter:
    def __init__(self, connection) -> None:
        self.rates_by_currency: dict[str, list[tuple[float, float | None, float]]] = {}
        self._load_rates(connection)

    def _load_rates(self, connection) -> None:
        rows = connection.execute(
            text(
                """
                SELECT currency_from, currency_to, price_min, price_max, rate
                FROM currency_rates
                WHERE is_active = 1 AND currency_to = 'RUB'
                ORDER BY currency_from, price_min
                """
            )
        ).mappings()

        for row in rows:
            currency = str(row["currency_from"]).upper()
            self.rates_by_currency.setdefault(currency, []).append(
                (_to_float(row["price_min"]), _to_optional_float(row["price_max"]), _to_float(row["rate"]))
            )

        for currency_from, _, price_min, price_max, rate, _ in DEFAULT_CURRENCY_RATES:
            self.rates_by_currency.setdefault(currency_from, []).append((price_min, price_max, rate))

    def convert(self, amount: float, from_currency: str) -> float:
        if amount <= 0:
            return 0

        for price_min, price_max, rate in self.rates_by_currency.get(from_currency.upper(), []):
            if price_max is None and amount >= price_min:
                return round(amount * rate, 2)
            if price_max is not None and price_min <= amount <= price_max:
                return round(amount * rate, 2)

        ranges = self.rates_by_currency.get(from_currency.upper()) or []
        if ranges:
            return round(amount * ranges[-1][2], 2)
        return 0


def sync_products_from_cache(connection) -> ProductCacheImportResult:
    if not settings.PRODUCTS_REBUILD_ON_STARTUP:
        return ProductCacheImportResult(changed=False, reason="disabled")

    result_path = _resolve_project_path(settings.PRODUCTS_RESULT_CACHE_PATH)
    if not result_path.exists():
        products_count = _products_count(connection)
        log_method = logger.warning if products_count == 0 else logger.info
        log_method("Product cache %s not found; startup product rebuild skipped", result_path)
        return ProductCacheImportResult(changed=False, reason="missing_source", source_path=result_path)

    _ensure_product_columns(connection)
    _ensure_import_state_table(connection)

    promo_path = _resolve_project_path(settings.PRODUCTS_PROMO_CACHE_PATH)
    source_signature = _combined_source_signature(result_path, promo_path)
    products_count = _products_count(connection)
    previous_signature = _get_import_state(connection, "result_signature")
    previous_version = _get_import_state(connection, "importer_version")

    if (
        not settings.PRODUCTS_REBUILD_ALWAYS
        and products_count > 0
        and previous_signature == source_signature
        and previous_version == IMPORTER_VERSION
    ):
        logger.info("Product cache %s is unchanged; startup product rebuild skipped", result_path)
        return ProductCacheImportResult(changed=False, reason="unchanged", source_path=result_path)

    result = _load_result_cache(result_path)
    promo_sets = _load_promo_cache(promo_path)
    converter = CurrencyConverter(connection)
    rows = list(_prepare_product_rows(result, converter, promo_sets))

    if not rows:
        logger.warning("Product cache %s contains no importable products; existing products were kept", result_path)
        return ProductCacheImportResult(changed=False, reason="empty_prepared", source_path=result_path)

    logger.info(
        "Rebuilding products from %s: source=%s prepared=%s existing=%s",
        result_path,
        len(result),
        len(rows),
        products_count,
    )

    _upsert_products(connection, rows)
    deleted_stale = _delete_stale_products(connection, rows) if settings.PRODUCTS_REBUILD_DELETE_STALE else 0

    _set_import_state(connection, "result_signature", source_signature)
    _set_import_state(connection, "result_count", str(len(result)))
    _set_import_state(connection, "prepared_count", str(len(rows)))
    _set_import_state(connection, "importer_version", IMPORTER_VERSION)

    logger.info("Products rebuilt from cache: upserted=%s deleted_stale=%s", len(rows), deleted_stale)
    return ProductCacheImportResult(True, "imported", result_path, len(result), len(rows), deleted_stale)


def _resolve_project_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[2] / path


def _file_signature(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _combined_source_signature(result_path: Path, promo_path: Path) -> str:
    promo_signature = _file_signature(promo_path) if promo_path.exists() else "missing"
    return f"result={_file_signature(result_path)};promo={promo_signature}"


def _load_result_cache(path: Path) -> list[dict[str, Any]]:
    with path.open("rb") as file:
        payload = pickle.load(file)
    if not isinstance(payload, list):
        raise RuntimeError(f"Product cache {path} must contain a list, got {type(payload).__name__}")
    return [item for item in payload if isinstance(item, dict)]


def _load_promo_cache(path: Path) -> PromoSets:
    if not path.exists():
        return PromoSets(extra=set(), deluxe=set(), all=set())

    with path.open("rb") as file:
        payload = pickle.load(file)

    if isinstance(payload, dict):
        return PromoSets(
            extra={str(item) for item in payload.get("Extra", set())},
            deluxe={str(item) for item in payload.get("Deluxe", set())},
            all={str(item) for item in payload.get("All", set())},
        )
    if isinstance(payload, (list, set, tuple)):
        items = {str(item) for item in payload}
        return PromoSets(extra=items, deluxe=set(), all=items)

    logger.warning("Promo cache %s has unsupported payload type %s; ignoring it", path, type(payload).__name__)
    return PromoSets(extra=set(), deluxe=set(), all=set())


def _ensure_product_columns(connection) -> None:
    existing_columns = {
        row["name"] for row in connection.execute(text('PRAGMA table_info("products")')).mappings().all()
    }
    for column_name, column_type in PRODUCT_COLUMNS:
        if column_name not in existing_columns:
            connection.execute(text(f'ALTER TABLE products ADD COLUMN "{column_name}" {column_type}'))


def _ensure_import_state_table(connection) -> None:
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {IMPORT_STATE_TABLE} (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
    )


def _get_import_state(connection, key: str) -> str | None:
    return connection.execute(
        text(f"SELECT value FROM {IMPORT_STATE_TABLE} WHERE key = :key"),
        {"key": key},
    ).scalar()


def _set_import_state(connection, key: str, value: str) -> None:
    connection.execute(
        text(
            f"""
            INSERT INTO {IMPORT_STATE_TABLE} (key, value)
            VALUES (:key, :value)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """
        ),
        {"key": key, "value": value},
    )


def _products_count(connection) -> int:
    return int(connection.execute(text("SELECT COUNT(*) FROM products")).scalar() or 0)


def _upsert_products(connection, rows: list[dict[str, Any]]) -> None:
    for batch in _chunks(rows, settings.PRODUCTS_REBUILD_BATCH_SIZE):
        connection.execute(text(UPSERT_PRODUCTS_SQL), batch)


def _delete_stale_products(connection, rows: list[dict[str, Any]]) -> int:
    connection.execute(
        text(
            f"""
            CREATE TEMP TABLE IF NOT EXISTS {TEMP_KEYS_TABLE} (
                id TEXT NOT NULL,
                region TEXT NOT NULL,
                PRIMARY KEY (id, region)
            ) WITHOUT ROWID
            """
        )
    )
    connection.execute(text(f"DELETE FROM {TEMP_KEYS_TABLE}"))

    keys = [{"id": row["id"], "region": row["region"]} for row in rows]
    for batch in _chunks(keys, settings.PRODUCTS_REBUILD_BATCH_SIZE):
        connection.execute(
            text(f"INSERT OR IGNORE INTO {TEMP_KEYS_TABLE} (id, region) VALUES (:id, :region)"),
            batch,
        )

    result = connection.execute(
        text(
            f"""
            DELETE FROM products
            WHERE NOT EXISTS (
                SELECT 1
                FROM {TEMP_KEYS_TABLE} cache_keys
                WHERE cache_keys.id = products.id
                  AND cache_keys.region = products.region
            )
            """
        )
    )
    connection.execute(text(f"DROP TABLE IF EXISTS {TEMP_KEYS_TABLE}"))
    return int(result.rowcount or 0)


def _prepare_product_rows(
    result: Iterable[dict[str, Any]],
    converter: CurrencyConverter,
    promo_sets: PromoSets,
) -> Iterable[dict[str, Any]]:
    for product in result:
        price_uah = _to_float(product.get("price_uah"))
        price_try = _to_float(product.get("price_try"))
        price_inr = _to_float(product.get("price_inr"))
        if price_uah <= 0 and price_try <= 0 and price_inr <= 0:
            continue

        product_id = _to_text(product.get("id"))
        if not product_id:
            continue

        name = _to_text(product.get("name"))
        if "\u041f\u043e\u0434\u043f\u0438\u0441\u043a\u0430 PlayStation Plus" in name or "EA Play \u043d\u0430" in name:
            continue

        old_price_uah = _to_float(product.get("old_price_uah"))
        old_price_try = _to_float(product.get("old_price_try"))
        old_price_inr = _to_float(product.get("old_price_inr"))
        old_prices_rub = [
            converted
            for converted in (
                converter.convert(old_price_uah, "UAH") if old_price_uah > 0 else 0,
                converter.convert(old_price_try, "TRY") if old_price_try > 0 else 0,
                converter.convert(old_price_inr, "INR") if old_price_inr > 0 else 0,
            )
            if converted > 0
        ]
        old_price_rub = min(old_prices_rub) if old_prices_rub else None

        ps_plus_price_uah = _to_optional_float(product.get("ps_plus_price_uah"))
        ps_plus_price_try = _to_optional_float(product.get("ps_plus_price_try"))
        ps_plus_price_inr = _to_optional_float(product.get("ps_plus_price_inr"))
        ps_plus_prices_rub = [
            converted
            for converted in (
                converter.convert(ps_plus_price_uah or 0, "UAH") if ps_plus_price_uah else 0,
                converter.convert(ps_plus_price_try or 0, "TRY") if ps_plus_price_try else 0,
                converter.convert(ps_plus_price_inr or 0, "INR") if ps_plus_price_inr else 0,
            )
            if converted > 0
        ]
        ps_plus_price_rub = min(ps_plus_prices_rub) if ps_plus_prices_rub else None

        prices_with_regions = [
            (converted, region)
            for converted, region in (
                (converter.convert(price_uah, "UAH"), "UA") if price_uah > 0 else (0, "UA"),
                (converter.convert(price_try, "TRY"), "TR") if price_try > 0 else (0, "TR"),
                (converter.convert(price_inr, "INR"), "IN") if price_inr > 0 else (0, "IN"),
            )
            if converted > 0
        ]
        price_rub, price_rub_region = min(prices_with_regions, key=lambda item: item[0])

        category = product.get("category")
        if isinstance(category, list):
            category = ",".join(str(item) for item in category)

        yield {
            "id": product_id,
            "category": _to_optional_text(category),
            "region": _to_text(product.get("region")) or "UA",
            "type": _to_optional_text(product.get("type")),
            "name": name,
            "main_name": _to_optional_text(product.get("main_name")),
            "image": _to_optional_text(product.get("image")),
            "compound": _to_storage_value(product.get("compound")),
            "platforms": _to_optional_text(product.get("platforms")),
            "publisher": _to_optional_text(product.get("publisher")),
            "localization": _to_optional_text(product.get("localization")),
            "rating": _to_float(product.get("rating")),
            "info": _to_storage_value(product.get("info")),
            "price": price_rub,
            "old_price": old_price_rub,
            "ps_price": ps_plus_price_rub,
            "plus_types": None,
            "ea_price": None,
            "ps_plus": _to_int(product.get("ps_plus")),
            "ea_access": _to_optional_text(product.get("ea_access", 0)),
            "discount": _to_float(product.get("discount_percent")),
            "discount_end": _to_optional_text(product.get("discount_end")),
            "tags": _to_storage_value(product.get("tags")),
            "edition": _to_optional_text(product.get("edition")),
            "description": _to_optional_text(product.get("description")),
            "price_uah": price_uah,
            "old_price_uah": old_price_uah,
            "price_try": price_try,
            "old_price_try": old_price_try,
            "price_inr": price_inr,
            "old_price_inr": old_price_inr,
            "price_rub": price_rub,
            "price_rub_region": price_rub_region,
            "ps_plus_price_uah": ps_plus_price_uah,
            "ps_plus_price_try": ps_plus_price_try,
            "ps_plus_price_inr": ps_plus_price_inr,
            "players_min": _to_optional_int(product.get("players_min")),
            "players_max": _to_optional_int(product.get("players_max")),
            "players_online": _to_int(product.get("players_online")),
            "name_localized": _to_optional_text(product.get("name_localized")),
            "search_names": _to_storage_value(product.get("search_names")),
            "discount_percent": _to_int(product.get("discount_percent")),
            "ps_plus_collection": _resolve_ps_plus_collection(product, promo_sets),
            "created_at": product.get("created_at"),
            "updated_at": product.get("updated_at"),
        }


def _resolve_ps_plus_collection(product: dict[str, Any], promo_sets: PromoSets) -> str | None:
    existing = _to_optional_text(product.get("ps_plus_collection"))
    if existing:
        return existing

    names = {_to_text(product.get("name")), _to_text(product.get("main_name"))}
    names.discard("")
    if names & promo_sets.deluxe:
        return "Deluxe"
    if names & (promo_sets.extra | promo_sets.all):
        return "Extra"
    return None


def _to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_optional_float(value: Any) -> float | None:
    parsed = _to_float(value)
    return parsed if parsed > 0 else None


def _to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return _to_int(value)


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _to_optional_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _to_storage_value(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, set):
        value = sorted(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _chunks(items: list[T], size: int) -> Iterable[list[T]]:
    safe_size = max(int(size or 1000), 1)
    for index in range(0, len(items), safe_size):
        yield items[index : index + safe_size]
