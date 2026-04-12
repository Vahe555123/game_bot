from __future__ import annotations

import argparse
import asyncio
import json
import pickle
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from time import perf_counter

import aiohttp


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from parser import (  # noqa: E402
    get_all_ps_plus_subscriptions,
    match_products_by_id,
    merge_region_data,
    parse as parse_full,
    parse_in,
    parse_tr,
    process_ps_plus_only_editions,
    process_specific_products_to_db,
    uni,
    unquote,
)


STORE_URL_RE = re.compile(r"^https?://store\.playstation\.com/", re.IGNORECASE)


@dataclass
class GameGroup:
    title: str
    urls: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Parse a grouped list of PlayStation Store URLs with the manual flow "
            "(mode 4) and compare it against the automatic flow (mode 1)."
        ),
    )
    parser.add_argument(
        "--input-file",
        default=None,
        help="UTF-8 text file with grouped game names and URLs.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "scripts" / "manual_parse_output"),
        help="Directory where JSON / PKL artifacts will be written.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="HTTP timeout for PlayStation Store requests.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for smoke tests.",
    )
    return parser.parse_args()


def load_source_text(args: argparse.Namespace) -> str:
    if args.input_file:
        return Path(args.input_file).read_text(encoding="utf-8")

    if not sys.stdin.isatty():
        return sys.stdin.read()

    raise SystemExit(
        "Provide --input-file or pipe the grouped list via stdin.\n"
        "Example: Get-Content games.txt | python scripts/manual_product_compare.py",
    )


async def load_promo_data(session: aiohttp.ClientSession) -> dict[str, Any]:
    promo_path = ROOT / "promo.pkl"
    if promo_path.exists():
        with open(promo_path, "rb") as file:
            promo_data = pickle.load(file)

        if isinstance(promo_data, dict):
            return promo_data

        all_set = set(promo_data) if promo_data else set()
        return {
            "Extra": all_set,
            "Deluxe": set(),
            "All": all_set,
        }

    promo = await get_all_ps_plus_subscriptions(session)
    with open(promo_path, "wb") as file:
        pickle.dump(promo, file)
    return promo


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def is_store_url(line: str) -> bool:
    return bool(STORE_URL_RE.match(line.strip()))


def region_from_url(url: str) -> str | None:
    url = normalize_url(url)
    if "/ru-ua/" in url or "/uk-ua/" in url:
        return "UA"
    if "/en-tr/" in url:
        return "TR"
    if "/en-in/" in url:
        return "IN"
    return None


def pick_auto_url(urls: list[str]) -> str:
    normalized = [normalize_url(url) for url in urls if url]

    for preferred in ("ru-ua", "uk-ua"):
        for url in normalized:
            if f"/{preferred}/" in url:
                return url

    return normalized[0]


def parse_grouped_text(raw_text: str) -> list[GameGroup]:
    groups: list[GameGroup] = []
    current_title: str | None = None
    current_urls: list[str] = []
    seen_urls: set[str] = set()

    def flush_current() -> None:
        nonlocal current_title, current_urls
        if current_title and current_urls:
            groups.append(GameGroup(title=current_title, urls=current_urls[:]))
        current_title = None
        current_urls = []

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if is_store_url(line):
            url = normalize_url(line)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            if current_title is None:
                current_title = "Ungrouped"
            current_urls.append(url)
            continue

        # Any non-URL line is treated as a section title. Empty sections are ignored.
        flush_current()
        current_title = line

    flush_current()
    return groups


async def expand_concept_urls(session: aiohttp.ClientSession, url: str) -> list[str]:
    url = normalize_url(url)
    if "/concept/" not in url:
        return [url]

    expanded = await unquote(session, url)
    if not expanded:
        return []

    unique: list[str] = []
    seen: set[str] = set()
    for item in expanded:
        item = normalize_url(item)
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


async def parse_single_url(session: aiohttp.ClientSession, url: str, *, manual: bool) -> list[Dict[str, Any]]:
    records: list[Dict[str, Any]] = []
    for expanded_url in await expand_concept_urls(session, url):
        region = region_from_url(expanded_url)
        if manual and region == "UA":
            parsed = await parse_full(session, expanded_url, regions=["UA"])
        elif manual and region == "TR":
            parsed = await parse_tr(session, expanded_url)
        elif manual and region == "IN":
            parsed = await parse_in(session, expanded_url)
        else:
            parsed = await parse_full(session, expanded_url)

        if parsed:
            records.extend(parsed)

    return records


async def parse_manual_group(session: aiohttp.ClientSession, group: GameGroup) -> list[Dict[str, Any]]:
    parsed_records: list[Dict[str, Any]] = []
    for url in group.urls:
        parsed_records.extend(await parse_single_url(session, url, manual=True))

    ua_records = [item for item in parsed_records if item.get("region") == "UA"]
    tr_records = [item for item in parsed_records if item.get("region") == "TR"]
    in_records = [item for item in parsed_records if item.get("region") == "IN"]

    final_records: list[Dict[str, Any]] = []
    final_records.extend(ua_records)

    if tr_records and ua_records:
        tr_matches = match_products_by_id(ua_records, tr_records, "TR")
        for ua_item, tr_item in tr_matches:
            final_records.append(merge_region_data(ua_item, tr_item, "TR"))

        matched_tr_ids = {tr_item.get("id") for _, tr_item in tr_matches}
        unmatched_tr = [item for item in tr_records if item.get("id") not in matched_tr_ids]
        final_records.extend(unmatched_tr)
    elif tr_records:
        final_records.extend(tr_records)

    if in_records and ua_records:
        in_matches = match_products_by_id(ua_records, in_records, "IN")
        for ua_item, in_item in in_matches:
            final_records.append(merge_region_data(ua_item, in_item, "IN"))

        matched_in_ids = {in_item.get("id") for _, in_item in in_matches}
        unmatched_in = [item for item in in_records if item.get("id") not in matched_in_ids]
        final_records.extend(unmatched_in)
    elif in_records:
        final_records.extend(in_records)

    final_records = process_ps_plus_only_editions(final_records)
    uni(final_records)
    return final_records


async def parse_auto_group(session: aiohttp.ClientSession, group: GameGroup) -> list[Dict[str, Any]]:
    auto_url = pick_auto_url(group.urls)
    return await parse_single_url(session, auto_url, manual=False)


def round_value(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(record.get("id") or "").strip(),
        "region": str(record.get("region") or "").strip().upper(),
        "name": str(record.get("name") or "").strip(),
        "edition": str(record.get("edition") or "").strip(),
        "localization": str(record.get("localization") or "").strip(),
        "price_rub": round_value(record.get("price_rub")),
        "price_old_rub": round_value(record.get("price_old_rub")),
        "discount": str(record.get("discount") or "").strip(),
        "discount_end": str(record.get("discount_end") or "").strip(),
        "ps_plus": 1 if record.get("ps_plus") else 0,
        "ps_plus_collection": str(record.get("ps_plus_collection") or "").strip(),
        "ea_play_price": round_value(record.get("ea_play_price")),
    }


def record_signature(record: Dict[str, Any]) -> str:
    return json.dumps(normalize_record(record), ensure_ascii=False, sort_keys=True)


def record_preview(normalized: Dict[str, Any]) -> str:
    price = normalized.get("price_rub")
    price_text = f"{price:.2f}" if price is not None else "-"
    edition = normalized.get("edition") or "-"
    localization = normalized.get("localization") or "-"
    return (
        f"{normalized.get('name') or '-'} | "
        f"{normalized.get('id') or '-'} | "
        f"{normalized.get('region') or '-'} | "
        f"{edition} | "
        f"{localization} | "
        f"{price_text}"
    )


def compare_records(auto_records: list[Dict[str, Any]], manual_records: list[Dict[str, Any]]) -> Dict[str, Any]:
    auto_normalized = [normalize_record(record) for record in auto_records]
    manual_normalized = [normalize_record(record) for record in manual_records]

    auto_counter = Counter(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in auto_normalized)
    manual_counter = Counter(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in manual_normalized)

    auto_map: Dict[str, Dict[str, Any]] = {}
    manual_map: Dict[str, Dict[str, Any]] = {}
    for item in auto_normalized:
        sig = json.dumps(item, ensure_ascii=False, sort_keys=True)
        auto_map.setdefault(sig, item)
    for item in manual_normalized:
        sig = json.dumps(item, ensure_ascii=False, sort_keys=True)
        manual_map.setdefault(sig, item)

    same = sum((auto_counter & manual_counter).values())
    auto_only = auto_counter - manual_counter
    manual_only = manual_counter - auto_counter

    def expand_diff(counter: Counter[str], source_map: Dict[str, Dict[str, Any]]) -> list[Dict[str, Any]]:
        diff_items: list[Dict[str, Any]] = []
        for sig, count in counter.items():
            item = source_map.get(sig)
            for _ in range(count):
                if item:
                    diff_items.append(item)
        return diff_items

    return {
        "auto_count": len(auto_records),
        "manual_count": len(manual_records),
        "same_count": same,
        "auto_only_count": sum(auto_only.values()),
        "manual_only_count": sum(manual_only.values()),
        "auto_only": [record_preview(item) for item in expand_diff(auto_only, auto_map)],
        "manual_only": [record_preview(item) for item in expand_diff(manual_only, manual_map)],
        "match": not auto_only and not manual_only,
    }


async def main() -> None:
    args = parse_args()
    start_time = perf_counter()
    raw_text = load_source_text(args)
    groups = parse_grouped_text(raw_text)

    if args.limit is not None:
        groups = groups[: args.limit]

    if not groups:
        raise SystemExit("No game groups found in the provided input.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timeout = aiohttp.ClientTimeout(total=args.timeout)
    auto_all: list[Dict[str, Any]] = []
    manual_all: list[Dict[str, Any]] = []
    report: list[Dict[str, Any]] = []

    async with aiohttp.ClientSession(timeout=timeout) as session:
        promo = await load_promo_data(session)

        for index, group in enumerate(groups, start=1):
            print("=" * 96)
            print(f"[{index}/{len(groups)}] {group.title}")
            print(f"URLs: {len(group.urls)}")
            print(f"Auto baseline: {pick_auto_url(group.urls)}")

            try:
                auto_records = await parse_auto_group(session, group)
            except Exception as exc:  # pragma: no cover - network/runtime guard
                print(f"Auto parse failed: {type(exc).__name__}: {exc}")
                auto_records = []

            try:
                manual_records = await parse_manual_group(session, group)
            except Exception as exc:  # pragma: no cover - network/runtime guard
                print(f"Manual parse failed: {type(exc).__name__}: {exc}")
                manual_records = []

            auto_all.extend(auto_records)
            manual_all.extend(manual_records)

            diff = compare_records(auto_records, manual_records)
            diff.update(
                {
                    "title": group.title,
                    "urls": group.urls,
                    "auto_url": pick_auto_url(group.urls),
                }
            )
            report.append(diff)

            if diff["auto_count"] == 0 and diff["manual_count"] == 0:
                status = "EMPTY"
            else:
                status = "OK" if diff["match"] else "DIFF"
            print(
                f"Status: {status} | auto={diff['auto_count']} | manual={diff['manual_count']} | "
                f"same={diff['same_count']} | auto_only={diff['auto_only_count']} | "
                f"manual_only={diff['manual_only_count']}",
            )

            if status == "EMPTY":
                print("  Note: both flows returned no records for this group.")

            if diff["auto_only"]:
                print("  Only in auto:")
                for item in diff["auto_only"][:5]:
                    print(f"    - {item}")

            if diff["manual_only"]:
                print("  Only in manual:")
                for item in diff["manual_only"][:5]:
                    print(f"    - {item}")

    uni(auto_all)
    uni(manual_all)

    with open(output_dir / "auto_result.pkl", "wb") as file:
        pickle.dump(auto_all, file)
    with open(output_dir / "manual_result.pkl", "wb") as file:
        pickle.dump(manual_all, file)
    with open(output_dir / "comparison_report.json", "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    if manual_all:
        print("=" * 96)
        print("Syncing parsed records into products.db")
        await process_specific_products_to_db(manual_all, promo, start_time)

    print("=" * 96)
    print("Done")
    print(f"Groups: {len(groups)}")
    print(f"Auto records: {len(auto_all)}")
    print(f"Manual records: {len(manual_all)}")
    print(f"Artifacts: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
