"""Режим 5: точечный ремонт проблемных товаров в result.pkl.

Модуль намеренно отделён от parser.py, чтобы:
  * не раздувать parser.py (уже ~5700 строк);
  * изолировать логику группировки / оценки статусов / repair flow;
  * легко переиспользовать из тестов или ручных скриптов.

Принципы:
  * Единственный writer для result.pkl — сам режим 5, через merge_repaired_records().
  * Source of truth для ремонта — result.pkl. products.pkl и БД используются только
    как дополнительный источник URL/ID.
  * «Подтверждённое отсутствие в регионе» сохраняется в region_status_registry.json,
    чтобы не перепроверять такие товары при каждом запуске режима 5.
"""

from __future__ import annotations

import asyncio
import json as _json
import os
import pickle
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp


REGION_STATUS_FILE = "region_status_registry.json"
PROBLEM_REPORT_FILE = "problem_products_report.json"

SUPPORTED_REGIONS: Tuple[str, ...] = ("UA", "TR", "IN")
REGION_LOCALES = {"UA": "ru-ua", "TR": "en-tr", "IN": "en-in"}
LOCALE_TO_REGION = {v: k for k, v in REGION_LOCALES.items()}
PRICE_FIELD = {"UA": "price_uah", "TR": "price_try", "IN": "price_inr"}


class RegionStatus:
    FOUND_WITH_PRICE = "FOUND_WITH_PRICE"
    FOUND_FREE = "FOUND_FREE"
    NOT_AVAILABLE_IN_REGION = "NOT_AVAILABLE_IN_REGION"
    MATCH_NOT_FOUND = "MATCH_NOT_FOUND"
    PARSE_FAILED = "PARSE_FAILED"
    REQUEST_FAILED = "REQUEST_FAILED"
    UNKNOWN = "UNKNOWN"


_VALID_STATUSES = {RegionStatus.FOUND_WITH_PRICE, RegionStatus.FOUND_FREE}
_STRIP_CHARS = ("™", "®", "©", "℗", "℠")


# ---------------------------------------------------------------------------
# Текстовая нормализация и разбор ID
# ---------------------------------------------------------------------------


def normalize_text(value: Optional[str]) -> str:
    """Привести имя/edition к стабильной форме для сравнения между регионами."""
    if not value:
        return ""
    s = unicodedata.normalize("NFKD", str(value))
    for c in _STRIP_CHARS:
        s = s.replace(c, "")
    s = s.replace("’", "'").replace("`", "'")
    s = re.sub(r"[^\w\s']", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def get_id_parts(product_id: str) -> Dict[str, str]:
    """Разложить PS ID на части: prefix (EPxxxx), mid (CUSA/PPSA_NN), tail, cusa, ppsa."""
    if not product_id:
        return {"prefix": "", "mid": "", "tail": "", "cusa": "", "ppsa": ""}
    pid = product_id.upper()
    parts = pid.split("-")
    prefix = parts[0] if parts else ""
    mid = parts[1] if len(parts) >= 2 else ""
    tail = parts[-1] if len(parts) >= 3 else ""
    cusa_m = re.search(r"CUSA\d{4,5}", pid)
    ppsa_m = re.search(r"PPSA\d{4,5}", pid)
    return {
        "prefix": prefix,
        "mid": mid,
        "tail": tail,
        "cusa": cusa_m.group(0) if cusa_m else "",
        "ppsa": ppsa_m.group(0) if ppsa_m else "",
    }


def build_canonical_product_key(record: Dict) -> Tuple[str, str]:
    """Устойчивый ключ группировки одного и того же товара между регионами.

    Основной ключ - (normalize(main_name or name), normalize(edition)).
    Fallback на ID tail, если имени нет.
    """
    main_name = record.get("main_name") or record.get("name") or ""
    edition = record.get("edition") or ""
    key_name = normalize_text(main_name)
    key_edition = normalize_text(edition)
    if not key_name:
        pid = record.get("id") or ""
        tail = get_id_parts(pid)["tail"]
        key_name = tail.lower() if tail else pid.lower()
    return (key_name, key_edition)


def _canonical_key_str(key: Tuple[str, str]) -> str:
    return f"{key[0]}||{key[1]}"


# ---------------------------------------------------------------------------
# Группировка записей result.pkl по товарам
# ---------------------------------------------------------------------------


def build_product_groups(result: List[Dict]) -> List[Dict[str, Any]]:
    """Сгруппировать записи result по одному и тому же товару.

    Использует canonical key + union по ID tail: если две записи имеют одинаковый tail,
    но разные имена (локализованные переводы), они склеиваются в один group.
    """
    groups: Dict[Tuple[str, str], Dict[str, Any]] = {}
    tail_to_key: Dict[str, Tuple[str, str]] = {}

    for idx, record in enumerate(result):
        key = build_canonical_product_key(record)
        pid = (record.get("id") or "").upper()
        tail = get_id_parts(pid)["tail"] if pid else ""

        target_key = key
        if tail:
            existing_key = tail_to_key.get(tail)
            if existing_key and existing_key in groups:
                target_key = existing_key

        group = groups.setdefault(target_key, _new_group(target_key))

        region = (record.get("region") or "").upper()
        if region in SUPPORTED_REGIONS:
            # Берём первую валидную запись региона как основную; если первая невалидная -
            # валидная её заменит
            existing_rec = group["records"].get(region)
            if existing_rec is None or (not is_region_record_valid(existing_rec) and is_region_record_valid(record)):
                group["records"][region] = record
                group["indices"][region] = idx

        group["all_indices"].append(idx)
        if pid:
            group["ids"].add(pid)
        if tail:
            group["id_tails"].add(tail)
            tail_to_key.setdefault(tail, target_key)
        if record.get("name"):
            group["names"].add(record["name"])
        if record.get("main_name"):
            group["main_names"].add(record["main_name"])
        if record.get("edition"):
            group["editions"].add(record["edition"])
        if record.get("search_names"):
            for t in str(record["search_names"]).split(","):
                t = t.strip()
                if t:
                    group["search_names"].add(t)

    return list(groups.values())


def _new_group(key: Tuple[str, str]) -> Dict[str, Any]:
    return {
        "canonical_key": key,
        "records": {r: None for r in SUPPORTED_REGIONS},
        "indices": {r: None for r in SUPPORTED_REGIONS},
        "all_indices": [],
        "ids": set(),
        "id_tails": set(),
        "names": set(),
        "main_names": set(),
        "editions": set(),
        "search_names": set(),
    }


# ---------------------------------------------------------------------------
# Оценка статусов регионов
# ---------------------------------------------------------------------------


def is_region_record_valid(record: Optional[Dict]) -> bool:
    if not record:
        return False
    region = (record.get("region") or "").upper()
    price_field = PRICE_FIELD.get(region)
    if price_field and (record.get(price_field) or 0) > 0:
        return True
    if (record.get("price_rub") or 0) > 0:
        return True
    if record.get("ps_plus_collection"):
        return True
    if record.get("is_free"):
        return True
    return False


def evaluate_region_status(record: Optional[Dict], persisted_status: Optional[str] = None) -> str:
    """Определить статус конкретного региона у товара.

    persisted_status - то, что лежит в registry для этого региона.
    Если запись есть - статус вычисляется по записи (persisted игнорируется кроме
    NOT_AVAILABLE, который автоматически означает, что записи и быть не должно).
    """
    if record:
        region = (record.get("region") or "").upper()
        price_field = PRICE_FIELD.get(region)
        local_price = (record.get(price_field) or 0) if price_field else 0
        price_rub = record.get("price_rub") or 0
        if local_price > 0 or price_rub > 0:
            return RegionStatus.FOUND_WITH_PRICE
        if record.get("ps_plus_collection"):
            return RegionStatus.FOUND_FREE
        if record.get("is_free"):
            return RegionStatus.FOUND_FREE
        return RegionStatus.PARSE_FAILED
    # Записи нет
    if persisted_status == RegionStatus.NOT_AVAILABLE_IN_REGION:
        return RegionStatus.NOT_AVAILABLE_IN_REGION
    if persisted_status in (RegionStatus.PARSE_FAILED, RegionStatus.REQUEST_FAILED):
        return persisted_status
    return RegionStatus.MATCH_NOT_FOUND


def is_product_group_complete(group: Dict[str, Any], persisted: Dict[str, str]) -> bool:
    """Товар «исправен», если каждый регион либо валиден, либо подтверждённо отсутствует."""
    for region in SUPPORTED_REGIONS:
        rec = group["records"].get(region)
        status = evaluate_region_status(rec, persisted.get(region))
        if status in _VALID_STATUSES:
            continue
        if status == RegionStatus.NOT_AVAILABLE_IN_REGION:
            continue
        return False
    return True


def collect_problem_candidates(
    groups: List[Dict[str, Any]],
    status_registry: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    problems = []
    for group in groups:
        key_str = _canonical_key_str(group["canonical_key"])
        persisted = status_registry.get(key_str, {})
        if is_product_group_complete(group, persisted):
            continue
        problems.append(group)
    return problems


# ---------------------------------------------------------------------------
# Персистентность registry и отчёта
# ---------------------------------------------------------------------------


def load_status_registry() -> Dict[str, Dict[str, str]]:
    if not os.path.exists(REGION_STATUS_FILE):
        return {}
    try:
        with open(REGION_STATUS_FILE, "r", encoding="utf-8") as f:
            data = _json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"[repair] Не удалось загрузить {REGION_STATUS_FILE}: {exc}")
        return {}


def save_status_registry(registry: Dict[str, Dict[str, str]]):
    tmp = REGION_STATUS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        _json.dump(registry, f, ensure_ascii=False, indent=2)
    os.replace(tmp, REGION_STATUS_FILE)


def save_problem_report(report: List[Dict[str, Any]]):
    tmp = PROBLEM_REPORT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        _json.dump(report, f, ensure_ascii=False, indent=2, default=_default_json)
    os.replace(tmp, PROBLEM_REPORT_FILE)


def _default_json(obj):
    if isinstance(obj, set):
        return sorted(obj)
    return str(obj)


# ---------------------------------------------------------------------------
# Генерация URL-кандидатов
# ---------------------------------------------------------------------------


def build_region_url_variants(source_id: str, target_locale: str) -> List[str]:
    """Сгенерировать кандидаты product URL в target_locale на основе source_id.

    Варианты:
      * прямой replace locale,
      * вращение последней цифры в блоке CUSA####_## (как в существующем get_tr_data),
      * вращение последней цифры в блоке PPSA####_## (для IN из примера 3).
    """
    if not source_id:
        return []
    base = f"https://store.playstation.com/{target_locale}/product"
    variants: List[str] = [f"{base}/{source_id.upper()}"]
    pid = source_id.upper()

    def _rotate(marker: str) -> List[str]:
        m = re.search(rf"({marker}\d+)(\d)(_\d+)", pid)
        if not m:
            return []
        base_part, last_digit, suffix = m.group(1), m.group(2), m.group(3)
        out = []
        for d in range(10):
            if str(d) == last_digit:
                continue
            new_id = pid.replace(f"{base_part}{last_digit}{suffix}",
                                 f"{base_part}{d}{suffix}")
            out.append(f"{base}/{new_id}")
        return out

    variants.extend(_rotate("CUSA"))
    variants.extend(_rotate("PPSA"))

    seen, deduped = set(), []
    for v in variants:
        if v not in seen:
            seen.add(v)
            deduped.append(v)
    return deduped


# ---------------------------------------------------------------------------
# Поиск кандидатов и ремонт одного товара
# ---------------------------------------------------------------------------


async def _check_url_availability(session: aiohttp.ClientSession, url: str) -> str:
    """Быстрая проверка: отдаёт ли productRetrieve для URL непустой productRetrieve.

    Возвращает: "ok", "not_found", "request_failed", "parse_failed".
    """
    import parser as _parser  # отложенный импорт, чтобы избежать циркуляции

    try:
        params = _parser.get_params(url)
        if isinstance(params, list):
            params = params[0]
        async with session.get(
            "https://web.np.playstation.com/api/graphql/v1/op",
            params=params,
            headers=_parser.json_headers(url),
            timeout=aiohttp.ClientTimeout(30),
        ) as resp:
            text = await resp.text()
        if "You don't have permission to access" in text:
            return "request_failed"
        try:
            data = _parser.loads(text)
        except Exception:
            return "parse_failed"
        if data.get("errors"):
            return "not_found"
        retrieve = data.get("data", {}).get("productRetrieve")
        if retrieve is None:
            return "not_found"
        return "ok"
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        return "request_failed"
    except Exception:
        return "parse_failed"


def _pick_source_ids(group: Dict[str, Any], target_region: str) -> List[str]:
    """Собираем ID для генерации кандидатов, исключая запись target_region."""
    ids: List[str] = []
    for region in SUPPORTED_REGIONS:
        if region == target_region:
            continue
        rec = group["records"].get(region)
        if rec and rec.get("id"):
            ids.append(rec["id"].upper())
    for extra in sorted(group["ids"]):
        if extra not in ids:
            ids.append(extra)
    return ids


async def find_region_candidates(
    session: aiohttp.ClientSession,
    target_region: str,
    group: Dict[str, Any],
) -> Tuple[List[str], str]:
    """Найти существующие URL-кандидаты target_region для этого товара.

    Returns (existing_urls, outcome):
      outcome == "request_failed" -> прервать repair, сетевая/Cloudflare проблема;
      outcome == "found" и existing_urls не пуст -> можно отдать на parse*;
      outcome == "not_found" -> варианты перебраны, ни один не ответил productRetrieve.
    """
    locale = REGION_LOCALES[target_region]
    source_ids = _pick_source_ids(group, target_region)
    if not source_ids:
        return [], "not_found"

    existing_urls: List[str] = []
    seen: Set[str] = set()
    net_failed = False

    for src_id in source_ids:
        for url in build_region_url_variants(src_id, locale):
            if url in seen:
                continue
            seen.add(url)
            status = await _check_url_availability(session, url)
            if status == "ok":
                existing_urls.append(url)
            elif status == "request_failed":
                net_failed = True
                break
        if net_failed:
            break

    if net_failed:
        return existing_urls, "request_failed"
    if existing_urls:
        return existing_urls, "found"
    return [], "not_found"


async def _parse_records_for_region(
    session: aiohttp.ClientSession,
    target_region: str,
    url: str,
):
    """Вызвать нужный парсер (parse / parse_tr / parse_in) в зависимости от target_region и locale URL."""
    import parser as _parser

    locale = url.strip().rstrip("/").split("/")[3] if "/" in url else ""
    if target_region == "UA":
        # parse() принимает UA URL (ru-ua) и по regions=["UA"] вернёт только UA запись
        if locale == "ru-ua":
            return await _parser.parse(session, url, regions=["UA"])
        return []
    if target_region == "TR":
        if locale == "en-tr":
            return await _parser.parse_tr(session, url)
        return []
    if target_region == "IN":
        if locale == "en-in":
            return await _parser.parse_in(session, url)
        return []
    return []


def _record_matches_group(record: Dict, group: Dict[str, Any]) -> bool:
    """Проверить, что полученная запись относится к тому же товару."""
    key = build_canonical_product_key(record)
    group_key = group["canonical_key"]
    if key == group_key:
        return True
    # Сверка по main_name/name (локализация может отличаться)
    rec_name = normalize_text(record.get("main_name") or record.get("name") or "")
    rec_edition = normalize_text(record.get("edition") or "")
    group_names = {normalize_text(n) for n in group["main_names"].union(group["names"])}
    group_editions = {normalize_text(e) for e in group["editions"]} or {""}
    if rec_name and rec_name in group_names:
        if not rec_edition or not group_editions or rec_edition in group_editions:
            return True
    # Сверка по id tail
    pid = (record.get("id") or "").upper()
    tail = get_id_parts(pid)["tail"]
    if tail and tail in group["id_tails"]:
        return True
    return False


async def resolve_cross_region_match(
    session: aiohttp.ClientSession,
    target_region: str,
    group: Dict[str, Any],
) -> Tuple[Optional[Dict], str, List[str]]:
    """Попытаться получить полноценную запись target_region.

    Returns (record, status, candidate_urls) где status - финальный RegionStatus.
    """
    candidate_urls, outcome = await find_region_candidates(session, target_region, group)
    if outcome == "request_failed":
        return None, RegionStatus.REQUEST_FAILED, candidate_urls

    if not candidate_urls:
        return None, RegionStatus.NOT_AVAILABLE_IN_REGION, []

    parse_failures = 0
    for url in candidate_urls:
        try:
            records = await _parse_records_for_region(session, target_region, url)
        except Exception as exc:
            print(f"[repair]   parse исключение ({target_region}) {url}: {type(exc).__name__}: {exc}")
            parse_failures += 1
            continue
        if not records:
            parse_failures += 1
            continue
        for rec in records:
            if (rec.get("region") or "").upper() != target_region:
                continue
            if _record_matches_group(rec, group):
                if is_region_record_valid(rec):
                    return rec, RegionStatus.FOUND_WITH_PRICE, candidate_urls
                # запись есть, но цена/PS Plus не найдены
                return rec, RegionStatus.PARSE_FAILED, candidate_urls
    if parse_failures:
        return None, RegionStatus.PARSE_FAILED, candidate_urls
    # URL отдаёт productRetrieve, но parse() не вернул ни одной записи, которая совпадает
    return None, RegionStatus.MATCH_NOT_FOUND, candidate_urls


# ---------------------------------------------------------------------------
# Merge записей ремонта обратно в result.pkl
# ---------------------------------------------------------------------------


def merge_repaired_records(
    result: List[Dict],
    group: Dict[str, Any],
    repaired: Dict[str, Optional[Dict]],
) -> Tuple[int, int, int]:
    """Применить полученные записи к result на месте.

    repaired — {region: record_or_None}.
    Returns (added, updated, skipped_no_improvement).
    """
    import parser as _parser

    added = updated = skipped = 0
    for region, new_rec in repaired.items():
        if not new_rec:
            continue
        existing_rec = group["records"].get(region)
        existing_idx = group["indices"].get(region)

        if existing_rec is None:
            # Попробуем дополнительно через find_in_result, чтобы не создать дубль
            matches = _parser.find_in_result(
                result,
                new_rec.get("name") or "",
                new_rec.get("edition"),
                new_rec.get("description"),
                region,
            )
            if matches:
                idx, _ = matches[0]
                existing_idx = idx
                existing_rec = result[idx]

        if existing_rec is None:
            # Обогащаем UA-данными, если они есть в группе (для TR/IN)
            if region in ("TR", "IN"):
                ua_rec = group["records"].get("UA")
                if ua_rec is not None:
                    new_rec = _parser.merge_region_data(ua_rec, new_rec, region)
            result.append(new_rec)
            group["records"][region] = new_rec
            group["indices"][region] = len(result) - 1
            added += 1
            continue

        # Запись уже есть — обновляем цены и мета, не перетирая хорошее плохим
        if is_region_record_valid(new_rec) and not is_region_record_valid(existing_rec):
            # Заменить целиком, но сохранить старые длинные поля, если в новом их нет
            merged = dict(existing_rec)
            merged.update({k: v for k, v in new_rec.items() if v not in (None, "", 0, 0.0)})
            merged["region"] = region
            result[existing_idx] = merged
            group["records"][region] = merged
            updated += 1
        elif is_region_record_valid(new_rec):
            # Обновляем только цены/скидки, остальное не трогаем
            for field in (
                PRICE_FIELD[region],
                f"old_{PRICE_FIELD[region]}",
                f"ps_plus_{PRICE_FIELD[region]}",
                "price_rub",
                "price_rub_region",
                "ps_plus_price_rub",
                "discount",
                "discount_percent",
                "discount_end",
                "ps_plus_collection",
                "updated_at",
            ):
                if field in new_rec and new_rec[field] not in (None, ""):
                    existing_rec[field] = new_rec[field]
            result[existing_idx] = existing_rec
            group["records"][region] = existing_rec
            updated += 1
        else:
            skipped += 1

    return added, updated, skipped


# ---------------------------------------------------------------------------
# Верхнеуровневый pipeline
# ---------------------------------------------------------------------------


def _collect_urls_for_report(group: Dict[str, Any]) -> Dict[str, List[str]]:
    urls: Dict[str, List[str]] = {}
    for region in SUPPORTED_REGIONS:
        rec = group["records"].get(region)
        if rec and rec.get("id"):
            urls[region] = [
                f"https://store.playstation.com/{REGION_LOCALES[region]}/product/{rec['id']}"
            ]
    return urls


async def repair_group(
    session: aiohttp.ClientSession,
    group: Dict[str, Any],
    status_registry: Dict[str, Dict[str, str]],
) -> Dict[str, Any]:
    """Отремонтировать одну группу. Возвращает запись отчёта."""
    key_str = _canonical_key_str(group["canonical_key"])
    persisted = status_registry.get(key_str, {})

    report_item: Dict[str, Any] = {
        "canonical_key": list(group["canonical_key"]),
        "name": next(iter(group["main_names"] or group["names"]), ""),
        "edition": next(iter(group["editions"]), ""),
        "ids": sorted(group["ids"]),
        "id_tails": sorted(group["id_tails"]),
        "source_urls": _collect_urls_for_report(group),
        "candidate_urls": {},
        "region_statuses": {},
        "repaired_regions": [],
        "reason": {},
    }

    final_statuses: Dict[str, str] = {}
    repaired: Dict[str, Optional[Dict]] = {}

    for region in SUPPORTED_REGIONS:
        rec = group["records"].get(region)
        current_status = evaluate_region_status(rec, persisted.get(region))
        if current_status in _VALID_STATUSES:
            final_statuses[region] = current_status
            continue
        if current_status == RegionStatus.NOT_AVAILABLE_IN_REGION:
            final_statuses[region] = current_status
            continue

        # Пробуем починить регион
        new_rec, new_status, candidate_urls = await resolve_cross_region_match(
            session, region, group
        )
        final_statuses[region] = new_status
        if candidate_urls:
            report_item["candidate_urls"][region] = candidate_urls
        if new_rec is not None:
            repaired[region] = new_rec
            if new_status in _VALID_STATUSES:
                report_item["repaired_regions"].append(region)
        if new_status == RegionStatus.REQUEST_FAILED:
            report_item["reason"][region] = "сетевая ошибка / Cloudflare"
        elif new_status == RegionStatus.PARSE_FAILED:
            report_item["reason"][region] = "parser нашёл страницу, но данные не собрал"
        elif new_status == RegionStatus.MATCH_NOT_FOUND:
            report_item["reason"][region] = "нет совпадения по name/edition/id"
        elif new_status == RegionStatus.NOT_AVAILABLE_IN_REGION:
            report_item["reason"][region] = "кандидатов нет — товар реально отсутствует"

    report_item["region_statuses"] = final_statuses
    report_item["repaired_records"] = repaired

    # Обновляем persisted registry, сохраняя только не-валидные (валидные вычисляются по записи).
    updated_persisted = dict(persisted)
    for region, status in final_statuses.items():
        if status == RegionStatus.NOT_AVAILABLE_IN_REGION:
            updated_persisted[region] = status
        elif status in _VALID_STATUSES:
            # удаляем старый «плохой» статус, если теперь валидно
            updated_persisted.pop(region, None)
        else:
            # PARSE_FAILED / MATCH_NOT_FOUND / REQUEST_FAILED - не персистим,
            # чтобы в следующий запуск попытаться снова.
            if region in updated_persisted and updated_persisted[region] == RegionStatus.NOT_AVAILABLE_IN_REGION:
                # не затираем NOT_AVAILABLE случайной сетевой ошибкой
                continue
            updated_persisted.pop(region, None)
    status_registry[key_str] = updated_persisted

    return report_item


def summarize_groups(
    groups: List[Dict[str, Any]], status_registry: Dict[str, Dict[str, str]]
) -> Dict[str, int]:
    stats = {
        "records_total": 0,
        "groups_total": len(groups),
        "already_valid": 0,
        "problem_candidates": 0,
        "missing_UA": 0,
        "missing_TR": 0,
        "missing_IN": 0,
    }
    for group in groups:
        stats["records_total"] += len(group["all_indices"])
        persisted = status_registry.get(_canonical_key_str(group["canonical_key"]), {})
        if is_product_group_complete(group, persisted):
            stats["already_valid"] += 1
            continue
        stats["problem_candidates"] += 1
        for region in SUPPORTED_REGIONS:
            rec = group["records"].get(region)
            status = evaluate_region_status(rec, persisted.get(region))
            if status not in _VALID_STATUSES and status != RegionStatus.NOT_AVAILABLE_IN_REGION:
                stats[f"missing_{region}"] += 1
    return stats


async def run_mode5(promo: Optional[Dict] = None) -> None:
    """Точка входа режима 5: «Исправление ошибок продуктов»."""
    import parser as _parser  # отложенный импорт

    print("\n" + "=" * 80)
    print(" РЕЖИМ 5: ИСПРАВЛЕНИЕ ОШИБОК ПРОДУКТОВ")
    print("=" * 80)

    if not os.path.exists("result.pkl"):
        print(" ОШИБКА: result.pkl не найден — сначала запусти режим 1.")
        return

    with open("result.pkl", "rb") as f:
        result: List[Dict] = pickle.load(f)
    print(f" Загружено {len(result)} записей из result.pkl")

    # products.pkl — опциональный источник URL (если понадобится)
    extra_products: List[str] = []
    if os.path.exists("products.pkl"):
        try:
            with open("products.pkl", "rb") as f:
                extra_products = pickle.load(f)
            print(f" Дополнительно подключён products.pkl ({len(extra_products)} URLs)")
        except Exception as exc:
            print(f" [!] products.pkl не удалось прочитать: {exc}")

    status_registry = load_status_registry()

    # 1. Группировка
    groups = build_product_groups(result)
    pre_stats = summarize_groups(groups, status_registry)

    print("\nПРЕДАНАЛИЗ:")
    print(f"  Всего записей в result.pkl: {pre_stats['records_total']}")
    print(f"  Групп товаров:             {pre_stats['groups_total']}")
    print(f"  Уже валидных товаров:      {pre_stats['already_valid']}")
    print(f"  Кандидатов на ремонт:      {pre_stats['problem_candidates']}")
    print(f"  Регионов без UA:           {pre_stats['missing_UA']}")
    print(f"  Регионов без TR:           {pre_stats['missing_TR']}")
    print(f"  Регионов без IN:           {pre_stats['missing_IN']}")

    if pre_stats["problem_candidates"] == 0:
        print("\n Все товары уже валидны или подтверждённо отсутствуют. Ничего не делаю.")
        save_status_registry(status_registry)
        return

    confirm = input(f"\nЗапустить ремонт {pre_stats['problem_candidates']} товаров? (y/n): ").strip().lower()
    if confirm not in ("y", "д", "yes", "да", ""):
        print(" Отмена.")
        return

    problem_groups = collect_problem_candidates(groups, status_registry)

    # 2. Починка с контролем батча, чтобы периодически сохранять прогресс
    report: List[Dict[str, Any]] = []
    fixed = confirmed_unavailable = still_broken = 0
    status_counts = {
        RegionStatus.REQUEST_FAILED: 0,
        RegionStatus.PARSE_FAILED: 0,
        RegionStatus.MATCH_NOT_FOUND: 0,
    }

    # sessions: используем существующий TCPConnector для мягкой нагрузки на API
    connector = aiohttp.TCPConnector(
        limit=10, limit_per_host=5, keepalive_timeout=30, enable_cleanup_closed=True
    )
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=120, connect=30), connector=connector
    ) as session:
        total = len(problem_groups)
        for i, group in enumerate(problem_groups, 1):
            name_preview = next(iter(group["main_names"] or group["names"]), "?")
            print(f"\n[{i}/{total}] Repair: {name_preview!r}")
            try:
                item = await repair_group(session, group, status_registry)
            except Exception as exc:
                print(f"   [!] исключение в repair_group: {type(exc).__name__}: {exc}")
                continue

            # Счётчики
            regions_after = item["region_statuses"]
            ok_or_unavail = all(
                s in _VALID_STATUSES or s == RegionStatus.NOT_AVAILABLE_IN_REGION
                for s in regions_after.values()
            )
            if ok_or_unavail:
                if all(s in _VALID_STATUSES for s in regions_after.values()):
                    fixed += 1
                else:
                    confirmed_unavailable += 1
            else:
                still_broken += 1

            for region, status in regions_after.items():
                if status in status_counts:
                    status_counts[status] += 1

            # Merge обратно в result
            repaired = {r: rec for r, rec in item["repaired_records"].items() if rec}
            if repaired:
                added, updated, skipped = merge_repaired_records(result, group, repaired)
                print(f"   merge: +{added} новых, обновлено {updated}, пропущено {skipped}")

            report.append(_strip_report_item(item))

            # Периодическое сохранение, чтобы не терять прогресс
            if i % 20 == 0 or i == total:
                with open("result.pkl", "wb") as f:
                    pickle.dump(result, f)
                save_status_registry(status_registry)
                save_problem_report(report)

    # 3. Финальное сохранение
    with open("result.pkl", "wb") as f:
        pickle.dump(result, f)
    save_status_registry(status_registry)
    save_problem_report(report)

    print("\n" + "=" * 80)
    print(" ИТОГО РЕЖИМ 5")
    print("=" * 80)
    print(f"  Групп к ремонту:              {total}")
    print(f"  Полностью починено (fixed):   {fixed}")
    print(f"  Подтверждённо отсутствуют:    {confirmed_unavailable}")
    print(f"  Всё ещё проблемные:           {still_broken}")
    print(f"  REQUEST_FAILED (регионов):    {status_counts[RegionStatus.REQUEST_FAILED]}")
    print(f"  PARSE_FAILED (регионов):      {status_counts[RegionStatus.PARSE_FAILED]}")
    print(f"  MATCH_NOT_FOUND (регионов):   {status_counts[RegionStatus.MATCH_NOT_FOUND]}")
    print(f"\n Отчёт сохранён: {PROBLEM_REPORT_FILE}")
    print(f" Registry статусов: {REGION_STATUS_FILE}")
    print(f" result.pkl обновлён ({len(result)} записей)")

    load_to_db = input("\nЗагрузить обновлённые данные в БД? (y/n): ").strip().lower()
    if load_to_db in ("y", "д", "yes", "да"):
        if promo is None:
            promo = _load_promo()
        start = datetime.now().timestamp()
        # используем существующий процесс
        await _parser.process_and_save_to_db(result, promo, start, clear_db=False)


def _strip_report_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Удаляем тяжёлые поля из отчёта (repaired_records дублируется в result.pkl)."""
    out = dict(item)
    out.pop("repaired_records", None)
    # Финальный статус товара
    statuses = out.get("region_statuses", {})
    if all(s in _VALID_STATUSES for s in statuses.values()):
        out["final_status"] = "fixed"
    elif all(s in _VALID_STATUSES or s == RegionStatus.NOT_AVAILABLE_IN_REGION for s in statuses.values()):
        out["final_status"] = "confirmed_unavailable" if any(
            s == RegionStatus.NOT_AVAILABLE_IN_REGION for s in statuses.values()
        ) else "fixed"
    elif any(s in _VALID_STATUSES for s in statuses.values()):
        out["final_status"] = "partial"
    else:
        out["final_status"] = "failed"
    return out


def _load_promo() -> Dict[str, Set[str]]:
    if not os.path.exists("promo.pkl"):
        return {"Extra": set(), "Deluxe": set(), "All": set()}
    try:
        with open("promo.pkl", "rb") as f:
            data = pickle.load(f)
        if isinstance(data, dict):
            return data
        all_set = set(data) if data else set()
        return {"Extra": all_set, "Deluxe": set(), "All": all_set}
    except Exception:
        return {"Extra": set(), "Deluxe": set(), "All": set()}
