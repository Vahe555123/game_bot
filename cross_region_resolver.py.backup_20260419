"""Расширенный поиск товара в целевом регионе при парсинге.

Используется как fallback в parser.get_tr_data, когда прямой product_id в
target_locale не отвечает. Перебирает:
  * прямой product_id,
  * ротацию последней цифры CUSA####,
  * ротацию последней цифры PPSA####.

Для каждого кандидата сверяет `name`/`edition` ответа с эталоном из UA, чтобы
не подменить товар: на PS Store соседние CUSA/PPSA часто принадлежат совсем
другим играм, и простое "нашли productRetrieve" без верификации опасно.

Все попытки и итог пишутся в ParseLogger, чтобы пользователь видел в логе, что
именно перебиралось и почему не нашли.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import aiohttp


_STRIP_CHARS = ("™", "®", "©", "℗", "℠")


# ---------------------------------------------------------------------------
# Нормализация строк для сравнения между регионами
# ---------------------------------------------------------------------------


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    s = str(value)
    # Удаляем спец-символы ДО NFKD, иначе ™ превращается в "TM" и остаётся в строке
    for c in _STRIP_CHARS:
        s = s.replace(c, "")
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("’", "'").replace("`", "'")
    s = re.sub(r"[^\w\s']", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


# ---------------------------------------------------------------------------
# Извлечение эталона (name/edition) из UA productRetrieve
# ---------------------------------------------------------------------------


def extract_reference_from_ua(ua_retrieve: Optional[Dict]) -> Dict[str, str]:
    """Вытащить нормализованные name и edition из UA response для последующей сверки.

    Args:
      ua_retrieve: содержимое ua["data"]["productRetrieve"].
    Returns:
      {"name": <normalized>, "edition": <normalized>}. Пустая строка если не найдено.
    """
    if not isinstance(ua_retrieve, dict):
        return {"name": "", "edition": ""}

    name = ""
    edition = ""

    concept = ua_retrieve.get("concept")
    if isinstance(concept, dict):
        name = concept.get("name") or ""
        products = concept.get("products") or []
        if products and isinstance(products, list):
            first = products[0]
            if isinstance(first, dict):
                edition = first.get("name") or ""
                if not name:
                    name = first.get("invariantName") or first.get("name") or ""

    if not name:
        name = ua_retrieve.get("name") or ua_retrieve.get("invariantName") or ""
    if not edition:
        edition = ua_retrieve.get("name") or ""

    return {
        "name": normalize_text(name),
        "edition": normalize_text(edition),
    }


def extract_retrieve_fingerprint(retrieve: Optional[Dict]) -> Dict[str, str]:
    """Те же поля name/edition, но для ответа любого региона (для сравнения)."""
    if not isinstance(retrieve, dict):
        return {"name": "", "edition": ""}
    name = ""
    edition = ""
    concept = retrieve.get("concept")
    if isinstance(concept, dict):
        name = concept.get("name") or ""
        products = concept.get("products") or []
        if products and isinstance(products, list):
            first = products[0]
            if isinstance(first, dict):
                edition = first.get("name") or ""
                if not name:
                    name = first.get("invariantName") or first.get("name") or ""
    if not name:
        name = retrieve.get("name") or retrieve.get("invariantName") or ""
    return {
        "name": normalize_text(name),
        "edition": normalize_text(edition),
    }


# ---------------------------------------------------------------------------
# Кандидаты product_id
# ---------------------------------------------------------------------------


def build_candidate_ids(source_id: str) -> List[str]:
    """Вернуть упорядоченный список кандидатов: direct, CUSA rotations, PPSA rotations."""
    if not source_id:
        return []
    pid = source_id.upper()
    out: List[str] = [pid]

    def _rotate(marker: str):
        m = re.search(rf"({marker}\d+)(\d)(_\d+)", pid)
        if not m:
            return
        base, last, suffix = m.group(1), m.group(2), m.group(3)
        for d in range(10):
            if str(d) == last:
                continue
            out.append(pid.replace(f"{base}{last}{suffix}", f"{base}{d}{suffix}"))

    _rotate("CUSA")
    _rotate("PPSA")

    seen: set = set()
    deduped: List[str] = []
    for cand in out:
        if cand not in seen:
            seen.add(cand)
            deduped.append(cand)
    return deduped


def match_score(retrieve: Dict, reference: Dict[str, str]) -> int:
    """Оценить совпадение кандидата с эталоном.

    Возвращает:
      2 — имена совпали точно (edition либо совпадает, либо пустой);
      1 — имя частично совпадает (подстрока) или reference пустой (нет с чем сравнивать);
      0 — не похоже, почти наверняка другой товар.
    """
    if not isinstance(retrieve, dict):
        return 0
    fingerprint = extract_retrieve_fingerprint(retrieve)
    rec_name = fingerprint["name"]
    rec_edition = fingerprint["edition"]

    ref_name = (reference or {}).get("name", "")
    ref_edition = (reference or {}).get("edition", "")

    if not ref_name:
        # Нет эталона — любое непустое productRetrieve считаем слабым совпадением
        return 1 if rec_name else 0

    if rec_name == ref_name:
        if ref_edition and rec_edition and rec_edition != ref_edition:
            return 1
        return 2

    if rec_name and (ref_name in rec_name or rec_name in ref_name):
        return 1

    return 0


# ---------------------------------------------------------------------------
# Основной fallback resolver
# ---------------------------------------------------------------------------


async def resolve_region_retrieve(
    session: aiohttp.ClientSession,
    source_id: str,
    target_locale: str,
    reference: Dict[str, str],
    base_params: Dict,
    *,
    json_loads,
    json_dumps,
    make_headers,
    logger=None,
    timeout_seconds: int = 30,
) -> Optional[Tuple[str, Dict, str]]:
    """Попробовать все кандидаты ID в target_locale.

    Args:
      session: aiohttp сессия.
      source_id: product_id из UA (или иного эталонного региона).
      target_locale: "en-tr" / "en-in" / "ru-ua".
      reference: нормализованный эталон {name, edition} для сверки.
      base_params: params GraphQL (с "variables" JSON-строкой); productId будет заменён.
      json_loads/json_dumps: parser.loads / parser.dumps.
      make_headers(url): парсер.json_headers(url).
      logger: ParseLogger (может быть None).

    Returns:
      (matched_id, full_response_dict, strategy) если найдено,
      иначе None.

    Поведение при Cloudflare: сразу прерываемся и возвращаем None, чтобы не
    долбить API зря.
    """
    candidates = build_candidate_ids(source_id)
    if not candidates:
        return None

    best: Optional[Tuple[int, str, Dict, str]] = None
    tried_log: List[Tuple[str, str]] = []

    variables_raw = base_params.get("variables") if isinstance(base_params, dict) else None
    try:
        variables_dict = json_loads(variables_raw) if isinstance(variables_raw, str) else (variables_raw or {})
    except Exception:
        variables_dict = {}

    base_product_url = f"https://store.playstation.com/{target_locale}/product"

    for cand_id in candidates:
        cand_url = f"{base_product_url}/{cand_id}"
        cand_variables = dict(variables_dict)
        cand_variables["productId"] = cand_id
        cand_params = dict(base_params)
        cand_params["variables"] = json_dumps(cand_variables)

        try:
            async with session.get(
                "https://web.np.playstation.com/api/graphql/v1/op",
                params=cand_params,
                headers=make_headers(cand_url),
                timeout=aiohttp.ClientTimeout(timeout_seconds),
            ) as resp:
                text = await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            tried_log.append((cand_id, f"network:{type(exc).__name__}"))
            continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            tried_log.append((cand_id, f"exception:{type(exc).__name__}"))
            continue

        if "You don't have permission to access" in text:
            tried_log.append((cand_id, "cloudflare"))
            if logger is not None:
                logger.log_cross_region_failed(
                    source_id, target_locale, tried_log, reason="cloudflare"
                )
            return None

        try:
            data = json_loads(text)
        except Exception:
            tried_log.append((cand_id, "json_parse_error"))
            continue

        if data.get("errors"):
            tried_log.append((cand_id, "graphql_errors"))
            continue

        retrieve = data.get("data", {}).get("productRetrieve") if isinstance(data.get("data"), dict) else None
        if not retrieve:
            tried_log.append((cand_id, "no_retrieve"))
            continue

        score = match_score(retrieve, reference)
        tried_log.append((cand_id, f"match={score}"))

        if score == 2:
            strategy = _classify_strategy(source_id, cand_id)
            if logger is not None:
                logger.log_cross_region_resolved(
                    source_id, target_locale, cand_id, strategy, tried_log
                )
            return cand_id, data, strategy

        if score == 1 and (best is None or best[0] < score):
            best = (score, cand_id, data, _classify_strategy(source_id, cand_id))

    if best is not None:
        if logger is not None:
            logger.log_cross_region_resolved(
                source_id, target_locale, best[1], f"{best[3]}_partial", tried_log
            )
        return best[1], best[2], best[3]

    if logger is not None:
        logger.log_cross_region_failed(source_id, target_locale, tried_log, reason="no_match")
    return None


async def resolve_via_concept(
    session: aiohttp.ClientSession,
    concept_id: str,
    target_locale: str,
    *,
    concept_params_builder,
    json_loads,
    make_headers,
    logger=None,
    timeout_seconds: int = 30,
) -> Optional[Dict]:
    """Фолбэк через concept_id (он region-agnostic).

    Когда прямой product_id и ротация CUSA/PPSA не нашли версию в target_locale
    (например, IN-версия Valhalla имеет совсем другой PPSA — 01490 вместо 01532),
    запрашиваем conceptRetrieve в целевом регионе. Ответ содержит список всех
    продуктов (изданий) этой игры в нужном регионе.

    Returns productRetrieve-shaped dict:
      {"data": {"productRetrieve": {"concept": {id, name, media, products}}}}
    чтобы вызывающий код обрабатывал его идентично обычному response.
    """
    if not concept_id or not target_locale:
        return None

    concept_url = f"https://store.playstation.com/{target_locale}/concept/{concept_id}"
    try:
        params = concept_params_builder(concept_url)
    except Exception as exc:
        if logger is not None:
            logger.log_cross_region_failed(
                f"concept:{concept_id}", target_locale,
                tried=[("concept", f"params_builder_error:{type(exc).__name__}")],
                reason="concept_params_error",
            )
        return None

    try:
        async with session.get(
            "https://web.np.playstation.com/api/graphql/v1/op",
            params=params,
            headers=make_headers(concept_url),
            timeout=aiohttp.ClientTimeout(timeout_seconds),
        ) as resp:
            text = await resp.text()
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        if logger is not None:
            logger.log_cross_region_failed(
                f"concept:{concept_id}", target_locale,
                tried=[("concept", f"network:{type(exc).__name__}")],
                reason="concept_network_error",
            )
        return None
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if logger is not None:
            logger.log_cross_region_failed(
                f"concept:{concept_id}", target_locale,
                tried=[("concept", f"exception:{type(exc).__name__}")],
                reason="concept_exception",
            )
        return None

    if "You don't have permission to access" in text:
        if logger is not None:
            logger.log_cross_region_failed(
                f"concept:{concept_id}", target_locale,
                tried=[("concept", "cloudflare")],
                reason="cloudflare",
            )
        return None

    try:
        data = json_loads(text)
    except Exception:
        if logger is not None:
            logger.log_cross_region_failed(
                f"concept:{concept_id}", target_locale,
                tried=[("concept", "json_parse_error")],
                reason="concept_json_parse_error",
            )
        return None

    if data.get("errors"):
        if logger is not None:
            logger.log_cross_region_failed(
                f"concept:{concept_id}", target_locale,
                tried=[("concept", "graphql_errors")],
                reason="concept_graphql_errors",
            )
        return None

    concept_retrieve = None
    if isinstance(data.get("data"), dict):
        concept_retrieve = data["data"].get("conceptRetrieve")
    if not isinstance(concept_retrieve, dict):
        if logger is not None:
            logger.log_cross_region_failed(
                f"concept:{concept_id}", target_locale,
                tried=[("concept", "no_concept_retrieve")],
                reason="no_concept_retrieve",
            )
        return None

    products = concept_retrieve.get("products") or []
    if not products:
        if logger is not None:
            logger.log_cross_region_failed(
                f"concept:{concept_id}", target_locale,
                tried=[("concept", "empty_products")],
                reason="concept_empty_products",
            )
        return None

    synthesized = {
        "data": {
            "productRetrieve": {
                "concept": {
                    "id": concept_retrieve.get("id") or concept_id,
                    "name": concept_retrieve.get("name") or "",
                    "media": concept_retrieve.get("media") or [],
                    "products": products,
                }
            }
        }
    }
    if logger is not None:
        logger.log_cross_region_resolved(
            f"concept:{concept_id}", target_locale,
            matched_id=f"concept:{concept_retrieve.get('id') or concept_id}",
            strategy="concept_retrieve",
            tried=[("concept", f"editions={len(products)}")],
        )
    return synthesized


def _classify_strategy(source_id: str, matched_id: str) -> str:
    if source_id.upper() == matched_id.upper():
        return "direct"
    if "CUSA" in matched_id and "CUSA" in source_id:
        src_m = re.search(r"CUSA\d{4,5}", source_id.upper())
        dst_m = re.search(r"CUSA\d{4,5}", matched_id.upper())
        if src_m and dst_m and src_m.group(0) != dst_m.group(0):
            return "cusa_rotated"
    if "PPSA" in matched_id and "PPSA" in source_id:
        src_m = re.search(r"PPSA\d{4,5}", source_id.upper())
        dst_m = re.search(r"PPSA\d{4,5}", matched_id.upper())
        if src_m and dst_m and src_m.group(0) != dst_m.group(0):
            return "ppsa_rotated"
    return "other"
