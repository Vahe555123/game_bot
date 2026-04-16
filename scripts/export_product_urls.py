#!/usr/bin/env python3
"""
Выгрузка URL товаров из products.pkl в текстовый файл (по одному URL на строку).

Парсер сначала собирает URL и сохраняет их в products.pkl, затем парсит по этому списку.
Запуск из корня проекта (где лежит products.pkl):

  python scripts/export_product_urls.py
  python scripts/export_product_urls.py -o parser_logs/all_product_urls.txt
  python scripts/export_product_urls.py -i /path/to/products.pkl -o urls.txt
"""

from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Экспорт URL из products.pkl в текстовый файл")
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path("products.pkl"),
        help="Путь к products.pkl (по умолчанию ./products.pkl)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("parsed_product_urls.txt"),
        help="Куда записать URL (по умолчанию ./parsed_product_urls.txt)",
    )
    args = parser.parse_args()

    input_path = args.input
    if not input_path.is_file():
        print(f"Файл не найден: {input_path.resolve()}", file=sys.stderr)
        return 1

    with input_path.open("rb") as f:
        data = pickle.load(f)

    if not isinstance(data, list):
        print(f"Ожидался list в pickle, получено: {type(data).__name__}", file=sys.stderr)
        return 1

    lines: list[str] = []
    for item in data:
        if isinstance(item, str) and item.strip():
            lines.append(item.strip())
        elif item is not None:
            # на случай если в списке когда-либо окажутся не-строки
            s = str(item).strip()
            if s:
                lines.append(s)

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    print(f"Записано URL: {len(lines)}")
    print(f"Файл: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
