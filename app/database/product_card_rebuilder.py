"""
Перестроение таблицы product_cards из products.

Одна строка в product_cards = один логический товар.
UA/TR/IN версии товара сводятся в одну строку по group_key (обычно = products.id).

Эта таблица — только для каталога и витрины. Покупки, избранное и
cross-region resolver продолжают работать с таблицей products(id, region).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import bindparam, text

from config.settings import settings

logger = logging.getLogger(__name__)

CARDS_REBUILD_STATE_KEY = "product_cards_signature"
CARDS_REBUILD_VERSION_KEY = "product_cards_version"
CARDS_REBUILD_VERSION = "2"

# Приоритет локализации: меньше число — лучше
_LOCALIZATION_RANK = {
    "full": 0,
    "subtitles": 1,
    "interface": 2,
    "none": 3,
}

# Приоритет региона при выборе "представителя" общих полей: UA → TR → IN
_REGION_PRIORITY = {"UA": 0, "TR": 1, "IN": 2}

_REGION_MASK = {"UA": 1, "TR": 2, "IN": 4}


@dataclass(frozen=True)
class CardRebuildResult:
    changed: bool
    reason: str
    source_count: int = 0
    cards_count: int = 0
    elapsed_s: float = 0.0


def rebuild_product_cards(connection) -> CardRebuildResult:
    """
    Перестроить product_cards из products.

    Стратегия: пишем в пустую product_cards одним батчем INSERT'ов.
    Если products пуста — карточки не трогаем.
    """
    if not settings.PRODUCTS_USE_CARDS_TABLE:
        return CardRebuildResult(changed=False, reason="feature_disabled")

    started = time.monotonic()

    products_count = int(
        connection.execute(text("SELECT COUNT(*) FROM products")).scalar() or 0
    )
    if products_count == 0:
        logger.warning("rebuild_product_cards: products table is empty; skipping")
        return CardRebuildResult(changed=False, reason="empty_products")

    signature = _products_signature(connection)
    existing_signature = _get_state(connection, CARDS_REBUILD_STATE_KEY)
    existing_version = _get_state(connection, CARDS_REBUILD_VERSION_KEY)
    cards_count_existing = int(
        connection.execute(text("SELECT COUNT(*) FROM product_cards")).scalar() or 0
    )

    if (
        existing_signature == signature
        and existing_version == CARDS_REBUILD_VERSION
        and cards_count_existing > 0
    ):
        logger.info("product_cards unchanged (signature match, %s cards); skipping rebuild", cards_count_existing)
        return CardRebuildResult(changed=False, reason="unchanged", cards_count=cards_count_existing)

    logger.info(
        "Rebuilding product_cards: products=%s existing_cards=%s",
        products_count,
        cards_count_existing,
    )

    # Ленивый импорт чтобы избежать цикла connection ↔ product_cache_importer.
    from app.database.product_cache_importer import CurrencyConverter

    converter = CurrencyConverter(connection)

    rows = _load_products(connection)
    groups = _group_by_card_id(rows)
    cards = [_build_card_row(group, converter) for group in groups.values()]
    favorites_by_card_id = _load_favorites_counts(connection, set(groups.keys()))
    for card in cards:
        card["favorites_count"] = favorites_by_card_id.get(card["card_id"], 0)

    connection.execute(text("DELETE FROM product_cards"))
    _insert_cards(connection, cards)

    _set_state(connection, CARDS_REBUILD_STATE_KEY, signature)
    _set_state(connection, CARDS_REBUILD_VERSION_KEY, CARDS_REBUILD_VERSION)

    elapsed = time.monotonic() - started
    logger.info(
        "product_cards rebuilt: source_rows=%s cards=%s elapsed=%.1fs",
        products_count,
        len(cards),
        elapsed,
    )
    return CardRebuildResult(
        changed=True,
        reason="rebuilt",
        source_count=products_count,
        cards_count=len(cards),
        elapsed_s=elapsed,
    )


def rebuild_product_cards_for_ids(connection, product_ids: Iterable[str]) -> CardRebuildResult:
    """
    Пересобрать только карточки, затронутые конкретными products.id.

    Нужен для ручного парсинга из админки: после добавления 1-10 товаров нельзя
    пересобирать всю витрину на десятках тысяч строк и подвешивать сайт.
    """
    if not settings.PRODUCTS_USE_CARDS_TABLE:
        return CardRebuildResult(changed=False, reason="feature_disabled")

    ids = sorted({str(product_id).strip() for product_id in product_ids if product_id})
    if not ids:
        return CardRebuildResult(changed=False, reason="empty_ids")

    started = time.monotonic()

    # Если таблица ещё не создана, лучше мягко отдать fallback на старый путь каталога,
    # чем ронять ручной парсинг.
    cards_table_exists = connection.execute(
        text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'product_cards'")
    ).scalar()
    if not cards_table_exists:
        logger.warning("rebuild_product_cards_for_ids: product_cards table is missing; skipping")
        return CardRebuildResult(changed=False, reason="missing_product_cards")

    rows = _load_products_for_ids(connection, ids)
    groups = _group_by_card_id(rows)

    delete_stmt = text("DELETE FROM product_cards WHERE card_id IN :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    connection.execute(delete_stmt, {"ids": ids})

    if groups:
        from app.database.product_cache_importer import CurrencyConverter

        converter = CurrencyConverter(connection)
        cards = [_build_card_row(group, converter) for group in groups.values()]
        favorites_by_card_id = _load_favorites_counts(connection, set(groups.keys()))
        for card in cards:
            card["favorites_count"] = favorites_by_card_id.get(card["card_id"], 0)
        _insert_cards(connection, cards)
    else:
        cards = []

    elapsed = time.monotonic() - started
    logger.info(
        "product_cards partially rebuilt: requested=%s source_rows=%s cards=%s elapsed=%.2fs",
        len(ids),
        len(rows),
        len(cards),
        elapsed,
    )
    return CardRebuildResult(
        changed=True,
        reason="partial_rebuilt",
        source_count=len(rows),
        cards_count=len(cards),
        elapsed_s=elapsed,
    )


# ── Группировка и сборка карточек ─────────────────────────────────────────────


_SOURCE_COLUMNS = (
    "id", "region", "category", "type", "name", "main_name", "search_names", "image",
    "compound", "platforms", "publisher", "localization", "rating", "info", "edition",
    "description", "tags",
    "price_uah", "old_price_uah", "price_try", "old_price_try", "price_inr", "old_price_inr",
    "price_rub", "price_rub_region",
    "ps_plus_price_uah", "ps_plus_price_try", "ps_plus_price_inr",
    "ps_plus", "ea_access", "ps_plus_collection",
    "plus_types", "discount", "discount_end", "discount_percent",
    "release_date", "created_at",
    "players_min", "players_max", "players_online",
)


def _load_products(connection) -> list[dict[str, Any]]:
    columns_sql = ", ".join(f'"{col}"' for col in _SOURCE_COLUMNS)
    rows = connection.execute(text(f"SELECT {columns_sql} FROM products")).mappings().all()
    return [dict(row) for row in rows]


def _load_products_for_ids(connection, product_ids: list[str]) -> list[dict[str, Any]]:
    columns_sql = ", ".join(f'"{col}"' for col in _SOURCE_COLUMNS)
    stmt = text(f"SELECT {columns_sql} FROM products WHERE id IN :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    rows = connection.execute(stmt, {"ids": product_ids}).mappings().all()
    return [dict(row) for row in rows]


def _group_by_card_id(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """
    Группируем по products.id.

    В подавляющем большинстве случаев один и тот же PPSA присутствует во всех
    трёх регионах, так что один product.id даёт одну карточку с UA/TR/IN.

    TODO: последующий проход — обнаружение cross-region-ID случаев (Valhalla)
    по совпадению нормализованного main_name + edition + publisher и слияние
    их в одну карточку. Пока такие случаи остаются отдельными карточками —
    ровно как в текущем каталоге, без регрессии.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        product_id = row.get("id")
        if not product_id:
            continue
        groups.setdefault(product_id, []).append(row)
    return groups


def _build_card_row(group: list[dict[str, Any]], converter) -> dict[str, Any]:
    by_region: dict[str, dict[str, Any]] = {}
    for item in group:
        region = (item.get("region") or "").strip().upper()
        if region in _REGION_PRIORITY:
            by_region[region] = item

    # Представитель для общих полей — первый доступный по приоритету UA→TR→IN.
    representative = _pick_representative(by_region)

    card_id = representative["id"]

    main_name = representative.get("main_name") or representative.get("name")
    sort_name = (main_name or representative.get("name") or representative.get("id") or "").lower()

    best_loc = _best_localization([item.get("localization") for item in by_region.values()])
    release_date = _best_date_value([item.get("release_date") for item in by_region.values()])
    added_at = _best_date_value([item.get("created_at") for item in by_region.values()])

    regions_mask = 0
    for region_code, mask_bit in _REGION_MASK.items():
        if region_code in by_region:
            regions_mask |= mask_bit

    ua = by_region.get("UA") or {}
    tr = by_region.get("TR") or {}
    in_ = by_region.get("IN") or {}

    ua_price_rub = _region_rub(converter, ua.get("price_uah"), "UAH", fallback=ua.get("price_rub") if ua.get("region") == "UA" else None)
    tr_price_rub = _region_rub(converter, tr.get("price_try"), "TRY", fallback=tr.get("price_rub") if tr.get("region") == "TR" else None)
    in_price_rub = _region_rub(converter, in_.get("price_inr"), "INR", fallback=in_.get("price_rub") if in_.get("region") == "IN" else None)

    ua_old_price_rub = _region_rub(converter, ua.get("old_price_uah"), "UAH")
    tr_old_price_rub = _region_rub(converter, tr.get("old_price_try"), "TRY")
    in_old_price_rub = _region_rub(converter, in_.get("old_price_inr"), "INR")

    candidates_for_min = [
        (ua_price_rub, "UA", ua_old_price_rub),
        (tr_price_rub, "TR", tr_old_price_rub),
        (in_price_rub, "IN", in_old_price_rub),
    ]
    priced = [c for c in candidates_for_min if c[0] and c[0] > 0]
    if priced:
        min_entry = min(priced, key=lambda c: c[0])
        min_price_rub, min_price_region, min_old_price_rub = min_entry
    else:
        min_price_rub, min_price_region, min_old_price_rub = None, None, None

    ua_discount_percent = _compute_discount_percent(ua.get("price_uah"), ua.get("old_price_uah"))
    tr_discount_percent = _compute_discount_percent(tr.get("price_try"), tr.get("old_price_try"))
    in_discount_percent = _compute_discount_percent(in_.get("price_inr"), in_.get("old_price_inr"))
    discount_values = [d for d in (ua_discount_percent, tr_discount_percent, in_discount_percent) if d]
    max_discount = max(discount_values) if discount_values else None

    has_discount = 1 if any(discount_values) else 0
    has_ps_plus_collection = 1 if representative.get("ps_plus_collection") else 0
    has_ea_access = 1 if _truthy_ea_access(representative.get("ea_access")) else 0

    ua_ps_plus_price_rub = _region_rub(converter, ua.get("ps_plus_price_uah"), "UAH")
    tr_ps_plus_price_rub = _region_rub(converter, tr.get("ps_plus_price_try"), "TRY")
    in_ps_plus_price_rub = _region_rub(converter, in_.get("ps_plus_price_inr"), "INR")

    return {
        "card_id": card_id,
        "name": representative.get("name"),
        "main_name": main_name,
        "search_names": representative.get("search_names"),
        "sort_name": sort_name,
        "image": representative.get("image"),
        "category": representative.get("category"),
        "type": representative.get("type"),
        "platforms": representative.get("platforms"),
        "publisher": representative.get("publisher"),
        "edition": representative.get("edition"),
        "description": representative.get("description"),
        "info": representative.get("info"),
        "compound": representative.get("compound"),
        "tags": representative.get("tags"),
        "rating": _to_optional_float(representative.get("rating")),
        "release_date": release_date,
        "added_at": added_at,
        "players_min": _to_optional_int(representative.get("players_min")),
        "players_max": _to_optional_int(representative.get("players_max")),
        "players_online": _to_optional_int(representative.get("players_online")),
        "best_localization": best_loc,
        "ps_plus_collection": representative.get("ps_plus_collection"),
        "ea_access": representative.get("ea_access"),
        "min_price_rub": min_price_rub,
        "min_price_region": min_price_region,
        "min_old_price_rub": min_old_price_rub,
        "max_discount_percent": max_discount,
        "has_discount": has_discount,
        "has_ps_plus": has_ps_plus_collection,
        "has_ea_access": has_ea_access,
        "regions_mask": regions_mask,
        # UA
        "ua_product_id": ua.get("id") if ua else None,
        "ua_localization": ua.get("localization") if ua else None,
        "ua_price_uah": _to_optional_float(ua.get("price_uah")) if ua else None,
        "ua_old_price_uah": _to_optional_float(ua.get("old_price_uah")) if ua else None,
        "ua_price_rub": ua_price_rub,
        "ua_old_price_rub": ua_old_price_rub,
        "ua_ps_plus_price_uah": _to_optional_float(ua.get("ps_plus_price_uah")) if ua else None,
        "ua_ps_plus_price_rub": ua_ps_plus_price_rub,
        "ua_discount_percent": ua_discount_percent,
        "ua_has_discount": 1 if ua_discount_percent else 0,
        "ua_discount_end": ua.get("discount_end") if ua else None,
        "ua_ps_plus": _to_optional_int(ua.get("ps_plus")) if ua else None,
        # TR
        "tr_product_id": tr.get("id") if tr else None,
        "tr_localization": tr.get("localization") if tr else None,
        "tr_price_try": _to_optional_float(tr.get("price_try")) if tr else None,
        "tr_old_price_try": _to_optional_float(tr.get("old_price_try")) if tr else None,
        "tr_price_rub": tr_price_rub,
        "tr_old_price_rub": tr_old_price_rub,
        "tr_ps_plus_price_try": _to_optional_float(tr.get("ps_plus_price_try")) if tr else None,
        "tr_ps_plus_price_rub": tr_ps_plus_price_rub,
        "tr_discount_percent": tr_discount_percent,
        "tr_has_discount": 1 if tr_discount_percent else 0,
        "tr_discount_end": tr.get("discount_end") if tr else None,
        "tr_ps_plus": _to_optional_int(tr.get("ps_plus")) if tr else None,
        # IN
        "in_product_id": in_.get("id") if in_ else None,
        "in_localization": in_.get("localization") if in_ else None,
        "in_price_inr": _to_optional_float(in_.get("price_inr")) if in_ else None,
        "in_old_price_inr": _to_optional_float(in_.get("old_price_inr")) if in_ else None,
        "in_price_rub": in_price_rub,
        "in_old_price_rub": in_old_price_rub,
        "in_ps_plus_price_inr": _to_optional_float(in_.get("ps_plus_price_inr")) if in_ else None,
        "in_ps_plus_price_rub": in_ps_plus_price_rub,
        "in_discount_percent": in_discount_percent,
        "in_has_discount": 1 if in_discount_percent else 0,
        "in_discount_end": in_.get("discount_end") if in_ else None,
        "in_ps_plus": _to_optional_int(in_.get("ps_plus")) if in_ else None,
        "favorites_count": 0,
    }


def _pick_representative(by_region: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for region in ("UA", "TR", "IN"):
        if region in by_region:
            return by_region[region]
    # Формально недостижимо — group_by_card_id пропускает пустые группы.
    return next(iter(by_region.values()))


def _best_localization(codes: list[Any]) -> str | None:
    ranked: list[tuple[int, str]] = []
    for code in codes:
        if not code:
            continue
        code_str = str(code).strip().lower()
        rank = _LOCALIZATION_RANK.get(code_str)
        if rank is None:
            continue
        ranked.append((rank, code_str))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0])
    return ranked[0][1]


def _best_date_value(values: Iterable[Any]) -> str | None:
    normalized = [str(value).strip() for value in values if value]
    return max(normalized) if normalized else None


def _region_rub(converter, local_value: Any, currency: str, fallback: Any = None) -> float | None:
    """Конвертировать локальную цену в рубли через CurrencyConverter.

    Если продукт в products.price_rub уже содержит цену именно этого региона
    (fallback), используем её как наиболее точное значение.
    """
    if fallback is not None:
        try:
            fv = float(fallback)
            if fv > 0:
                return round(fv, 2)
        except (TypeError, ValueError):
            pass
    try:
        amount = float(local_value) if local_value is not None else 0.0
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    converted = converter.convert(amount, currency)
    return converted if converted and converted > 0 else None


def _compute_discount_percent(current: Any, old: Any) -> int | None:
    try:
        cur = float(current) if current is not None else 0.0
        old_v = float(old) if old is not None else 0.0
    except (TypeError, ValueError):
        return None
    if old_v <= 0 or cur <= 0 or old_v <= cur:
        return None
    return int(round(((old_v - cur) / old_v) * 100))


def _truthy_ea_access(value: Any) -> bool:
    if value in (None, "", 0, "0", False):
        return False
    return True


def _to_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed else None


def _to_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _load_favorites_counts(connection, card_ids: set[str]) -> dict[str, int]:
    if not card_ids:
        return {}
    rows = connection.execute(
        text(
            "SELECT product_id AS card_id, COUNT(*) AS cnt "
            "FROM user_favorite_products GROUP BY product_id"
        )
    ).mappings().all()
    return {row["card_id"]: int(row["cnt"] or 0) for row in rows if row["card_id"] in card_ids}


_INSERT_COLUMNS = (
    "card_id", "name", "main_name", "search_names", "sort_name", "image", "category",
    "type", "platforms", "publisher", "edition", "description", "info", "compound", "tags",
    "rating", "release_date", "added_at", "players_min", "players_max", "players_online",
    "best_localization", "ps_plus_collection", "ea_access",
    "min_price_rub", "min_price_region", "min_old_price_rub",
    "max_discount_percent", "has_discount", "has_ps_plus", "has_ea_access", "regions_mask",
    "favorites_count",
    "ua_product_id", "ua_localization", "ua_price_uah", "ua_old_price_uah", "ua_price_rub",
    "ua_old_price_rub", "ua_ps_plus_price_uah", "ua_ps_plus_price_rub", "ua_discount_percent",
    "ua_has_discount", "ua_discount_end", "ua_ps_plus",
    "tr_product_id", "tr_localization", "tr_price_try", "tr_old_price_try", "tr_price_rub",
    "tr_old_price_rub", "tr_ps_plus_price_try", "tr_ps_plus_price_rub", "tr_discount_percent",
    "tr_has_discount", "tr_discount_end", "tr_ps_plus",
    "in_product_id", "in_localization", "in_price_inr", "in_old_price_inr", "in_price_rub",
    "in_old_price_rub", "in_ps_plus_price_inr", "in_ps_plus_price_rub", "in_discount_percent",
    "in_has_discount", "in_discount_end", "in_ps_plus",
)
_INSERT_SQL = (
    f"INSERT INTO product_cards ({', '.join(_INSERT_COLUMNS)}) VALUES "
    f"({', '.join(':' + col for col in _INSERT_COLUMNS)})"
)


def _insert_cards(connection, cards: list[dict[str, Any]]) -> None:
    batch_size = max(int(getattr(settings, "PRODUCTS_REBUILD_BATCH_SIZE", 1000) or 1000), 1)
    for start in range(0, len(cards), batch_size):
        batch = cards[start : start + batch_size]
        connection.execute(text(_INSERT_SQL), batch)


def _products_signature(connection) -> str:
    """
    Сигнатура таблицы products — дешёвый отпечаток. Хэш не считаем: используем
    count + max(rowid) + сумму длин имён как быстрый инвариант, который меняется
    при любом существенном изменении содержимого.
    """
    row = connection.execute(
        text(
            "SELECT COUNT(*) AS cnt, "
            "COALESCE(MAX(rowid), 0) AS max_rowid, "
            "COALESCE(SUM(LENGTH(COALESCE(main_name, name, id))), 0) AS name_len "
            "FROM products"
        )
    ).mappings().first()
    return f"cnt={row['cnt']};maxid={row['max_rowid']};nlen={row['name_len']}"


def _get_state(connection, key: str) -> str | None:
    return connection.execute(
        text("SELECT value FROM product_cache_import_state WHERE key = :key"),
        {"key": key},
    ).scalar()


def _set_state(connection, key: str, value: str) -> None:
    connection.execute(
        text(
            "INSERT INTO product_cache_import_state (key, value) VALUES (:key, :value) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
        ),
        {"key": key, "value": value},
    )
