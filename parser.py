import asyncio
import aiohttp
from json import dumps, loads
import json as json_module
from random import choice
from bs4 import BeautifulSoup as bs
from time import perf_counter
from re import findall
import re
import aiosqlite
from dotenv import load_dotenv
from datetime import datetime
import os
import pickle
import sys
import hashlib
import traceback
import unicodedata
from typing import List, Dict, Set, Tuple, Optional


load_dotenv()

SQLITE_DB_PATH = os.getenv("PARSER_SQLITE_DB_PATH", "products.db")


# Configuration
class ParserConfig:
    """Конфигурация парсера с автоматической перезагрузкой из JSON"""

    CONFIG_FILE = "public/parser-config.json"

    def __init__(self):
        self.last_modified = 0
        self.load_config()

    def load_config(self):
        """Загружает конфигурацию из JSON файла"""
        try:
            if os.path.exists(self.CONFIG_FILE):
                # Проверяем время модификации
                current_modified = os.path.getmtime(self.CONFIG_FILE)

                if current_modified != self.last_modified:
                    with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                        config = loads(f.read())

                    self.MAX_RETRIES = config.get('MAX_RETRIES', 3)
                    self.REQUEST_TIMEOUT = config.get('REQUEST_TIMEOUT', 120)
                    self.BATCH_SIZE_PAGES = config.get('BATCH_SIZE_PAGES', 30)
                    self.BATCH_SIZE_PRODUCTS = config.get('BATCH_SIZE_PRODUCTS', 70)
                    self.BATCH_SIZE_UNQUOTE = config.get('BATCH_SIZE_UNQUOTE', 250)
                    self.SLEEP_BETWEEN_BATCHES = config.get('SLEEP_BETWEEN_BATCHES', 3)
                    self.SLEEP_ON_CLOUDFLARE = config.get('SLEEP_ON_CLOUDFLARE', 30)
                    self.ACCESS_DENIED_CHECK_INTERVAL = config.get('ACCESS_DENIED_CHECK_INTERVAL', 60)
                    self.CONFIG_CHECK_INTERVAL = config.get('CONFIG_CHECK_INTERVAL', 5)

                    self.last_modified = current_modified

                    if current_modified > 0:
                        print(f"Конфигурация обновлена: BATCH_PRODUCTS={self.BATCH_SIZE_PRODUCTS}, SLEEP={self.SLEEP_BETWEEN_BATCHES}с")
            else:
                # Значения по умолчанию
                self.set_defaults()
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}, используются значения по умолчанию")
            self.set_defaults()

    def set_defaults(self):
        """Устанавливает значения по умолчанию"""
        self.MAX_RETRIES = 3
        self.REQUEST_TIMEOUT = 120
        self.BATCH_SIZE_PAGES = 30
        self.BATCH_SIZE_PRODUCTS = 70
        self.BATCH_SIZE_UNQUOTE = 250
        self.SLEEP_BETWEEN_BATCHES = 3
        self.SLEEP_ON_CLOUDFLARE = 30
        self.ACCESS_DENIED_CHECK_INTERVAL = 60
        self.CONFIG_CHECK_INTERVAL = 5

    # Дополнительные категории для парсинга
    # Категории для разных типов подписок PS Plus
    PS_PLUS_EXTRA_URL = "https://store.playstation.com/ru-ua/category/d0446d4b-dc9a-4f1e-86ec-651f099c9b29"  # PS Plus Extra
    PS_PLUS_DELUXE_URL = "https://store.playstation.com/ru-ua/category/30e3fe35-8f2d-4496-95bc-844f56952e3c"  # PS Plus Deluxe

    # URL категории для получения всех игр из подписок Extra/Deluxe (для обратной совместимости)
    PS_PLUS_COLLECTION_URL = "https://store.playstation.com/ru-ua/category/3f772501-f6f8-49b7-abac-874a88ca4897"

    EXTRA_CATEGORIES = [PS_PLUS_EXTRA_URL, PS_PLUS_DELUXE_URL]  # Для обратной совместимости


# Глобальный экземпляр конфигурации
parser_config = ParserConfig()

PARSER_LOGS_DIR = "parser_logs"
CHECKPOINT_FILE = "parser_checkpoint.json"


class ParseLogger:
    """Логирование ошибок парсинга в файл для каждого запуска"""

    def __init__(self):
        os.makedirs(PARSER_LOGS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_path = os.path.join(PARSER_LOGS_DIR, f"parse_{timestamp}.log")
        self._file = open(self.log_path, "w", encoding="utf-8")
        self._counts = {"PRODUCT_ERROR": 0, "PRICE_MISSING": 0, "PARSE_EXCEPTION": 0}
        self._write(f"Лог парсинга запущен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'=' * 100}\n")

    def _write(self, line: str):
        self._file.write(line + "\n")
        self._file.flush()

    def _ts(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log_product_error(self, url: str, reason: str):
        self._counts["PRODUCT_ERROR"] += 1
        self._write(f"[{self._ts()}] PRODUCT_ERROR | URL: {url} | Причина: {reason}")

    def log_region_price_error(self, url: str, product_name: str, region: str, reason: str):
        self._counts["PRICE_MISSING"] += 1
        self._write(f"[{self._ts()}] PRICE_MISSING | URL: {url} | Продукт: {product_name} | Регион: {region} | Причина: {reason}")

    def log_parse_exception(self, url: str, exc: BaseException):
        self._counts["PARSE_EXCEPTION"] += 1
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        short = str(exc) or type(exc).__name__
        self._write(f"[{self._ts()}] PARSE_EXCEPTION | URL: {url} | Причина: {short}")
        self._write("  " + "  ".join(tb))

    def log_summary(self, total_products: int = 0, parsed_count: int = 0):
        total_errors = sum(self._counts.values())
        self._write(f"\n{'=' * 100}")
        self._write(f"ИТОГО ЗА СЕССИЮ")
        self._write(f"{'=' * 100}")
        if total_products:
            self._write(f"Всего товаров для парсинга: {total_products}")
            self._write(f"Успешно спарсено записей: {parsed_count}")
        self._write(f"Всего ошибок: {total_errors}")
        for error_type, count in self._counts.items():
            self._write(f"  {error_type}: {count}")
        self._write(f"{'=' * 100}")
        self._file.close()
        print(f"\n Лог ошибок сохранен: {self.log_path} (ошибок: {total_errors})")

    def close(self):
        if not self._file.closed:
            self._file.close()


def save_checkpoint(started_at: str, total_products: int, parsed_index: int, results_count: int, db_cleared: bool = False):
    data = {
        "started_at": started_at,
        "total_products": total_products,
        "parsed_index": parsed_index,
        "results_count": results_count,
        "db_cleared": db_cleared,
        "phase": "parsing",
    }
    tmp_path = CHECKPOINT_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json_module.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, CHECKPOINT_FILE)


def load_checkpoint() -> Optional[Dict]:
    if not os.path.exists(CHECKPOINT_FILE):
        return None
    try:
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json_module.load(f)
    except Exception:
        return None


def remove_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)


# Регионы для парсинга
REGIONS = {
    "UA": {
        "code": "ru-ua",
        "currency": "UAH",
        "name": "Украина",
        "divide_price_by_100": True  # UAH приходит в копейках
    },
    "TR": {
        "code": "en-tr",
        "currency": "TRY",
        "name": "Турция",
        "divide_price_by_100": True  # TRY приходит в курушах
    },
    "IN": {
        "code": "en-in",
        "currency": "INR",
        "name": "Индия",
        "divide_price_by_100": False  # INR уже приходит в рупиях, не в пайсах!
    }
}


_FREE_PRICE_TEXTS = frozenset({
    "бесплатно", "free", "бесплатная версия",
    "free version", "free trial", "бесплатная пробная версия",
    "ücretsiz",
})

_PURCHASE_CTA_TYPES = frozenset({"ADD_TO_CART", "PREORDER", "BUY_NOW", "DOWNLOAD"})
_PRICE_CTA_TYPES = frozenset({"ADD_TO_CART", "PREORDER", "BUY_NOW"})


def is_free_price_text(text: str) -> bool:
    if not text:
        return False
    return text.strip().lower() in _FREE_PRICE_TEXTS


def parse_price_value(value, divide_by_100=True):
    """
    Безопасно парсит значение цены, обрабатывая запятые как разделители тысяч
    
    Args:
        value: Значение цены (может быть int, float или str)
        divide_by_100: Делить ли на 100 (если цена в минимальных единицах)
    
    Returns:
        float: Распарсенная цена
    """
    if value is None:
        return 0.0
    
    # Если это уже число, просто делим на 100 если нужно
    if isinstance(value, (int, float)):
        return value / 100.0 if divide_by_100 else float(value)
    
    # Если это строка, обрабатываем
    if isinstance(value, str):
        # Убираем все пробелы и запятые (разделители тысяч)
        cleaned = value.replace(',', '').replace(' ', '').strip()
        
        # Пытаемся преобразовать в число
        try:
            num_value = float(cleaned)
            return num_value / 100.0 if divide_by_100 else num_value
        except (ValueError, TypeError):
            return 0.0
    
    return 0.0


def detect_ps_plus_type_from_cta_text(cta_data: dict) -> Optional[str]:
    """
    Определяет тип PS Plus подписки из текста CTA
    
    Проверяет различные текстовые поля в CTA на наличие указаний типа подписки:
    - "PlayStation Plus Extra" или "Extra" -> "Extra"
    - "PlayStation Plus Deluxe" или "Deluxe" -> "Deluxe"
    - "PlayStation Plus Premium" или "Premium" -> "Deluxe" (Premium = Deluxe в некоторых регионах)
    - Просто "PlayStation Plus" -> None (используется определение из категорий)
    
    Args:
        cta_data: Данные CTA элемента (может содержать price, label, text, description и т.д.)
    
    Returns:
        str: "Extra", "Deluxe", или None если не найдено явного указания
    """
    # Список полей, в которых может быть текст с типом подписки
    text_fields = [
        'label',
        'text',
        'description',
        'offerText',
        'discountInfo',
        'title'
    ]
    
    # Также проверяем price.discountText и другие вложенные поля
    price_data = cta_data.get('price', {})
    if price_data:
        text_fields.extend([
            'discountText',
            'label',
            'text',
            'description'
        ])
    
    # Объединяем все текстовые поля для поиска
    all_texts = []
    for field in text_fields:
        if field in cta_data:
            value = cta_data[field]
            if isinstance(value, str):
                all_texts.append(value)
        if price_data and field in price_data:
            value = price_data[field]
            if isinstance(value, str):
                all_texts.append(value)
    
    # Ищем указания на тип подписки (без учета регистра)
    combined_text = ' '.join(all_texts).lower()
    
    # Удаляем спецсимволы для лучшего поиска (nbsp и т.д.)
    combined_text = combined_text.replace('\xa0', ' ').replace('&nbsp;', ' ').replace('\u00a0', ' ')
    
    # Проверяем на "Deluxe" или "Premium" (Premium может означать Deluxe в некоторых регионах)
    # Важно: проверяем, что это именно PlayStation Plus, а не что-то другое
    if ('deluxe' in combined_text or 'premium' in combined_text):
        if 'playstation' in combined_text and 'plus' in combined_text:
            return "Deluxe"
    
    # Проверяем на "Extra"
    # Важно: проверяем, что это именно PlayStation Plus Extra
    if 'extra' in combined_text:
        if 'playstation' in combined_text and 'plus' in combined_text:
            return "Extra"
    
    # Если просто "PlayStation Plus" без указания типа - возвращаем None
    # (будет использовано определение из категорий или типа CTA)
    return None


# Currency converter
class CurrencyConverter:
    """Конвертер валют через базу данных currency_rates"""

    def __init__(self):
        self.rates_cache = {}
        self.missing_rates_warned = set()
        self.db_path = SQLITE_DB_PATH

    async def load_rates(self):
        """Загружает курсы валют из БД"""
        self.rates_cache = {}
        self.missing_rates_warned = set()
        await ensure_database_schema()
        async with aiosqlite.connect(self.db_path) as db:
            await prepare_sqlite_connection(db)
            cursor = await db.execute("""
                SELECT currency_from, currency_to, price_min, price_max, rate
                FROM currency_rates
                WHERE is_active = 1
                ORDER BY currency_from, price_min
            """)
            rows = await cursor.fetchall()

            for row in rows:
                currency_from, currency_to, price_min, price_max, rate = row
                key = f"{currency_from}_to_{currency_to}"

                if key not in self.rates_cache:
                    self.rates_cache[key] = []

                self.rates_cache[key].append({
                    'price_min': price_min,
                    'price_max': price_max,
                    'rate': rate
                })

        print(f"Загружено курсов валют: {len(self.rates_cache)} пар")

    def convert(self, amount: float, from_currency: str, to_currency: str = "RUB") -> float:
        """
        Конвертирует сумму из одной валюты в другую

        Args:
            amount: Сумма для конвертации
            from_currency: Исходная валюта (UAH, TRY, INR)
            to_currency: Целевая валюта (по умолчанию RUB)

        Returns:
            Сконвертированная сумма в рублях
        """
        if not amount or amount <= 0:
            return 0

        key = f"{from_currency}_to_{to_currency}"

        if key not in self.rates_cache and key in self.missing_rates_warned:
            return 0

        if key not in self.rates_cache:
            self.missing_rates_warned.add(key)
            print(f"[!]️ Курс {from_currency} -> {to_currency} не найден!")
            return 0

        # Ищем подходящий диапазон
        for rate_range in self.rates_cache[key]:
            price_min = rate_range['price_min']
            price_max = rate_range['price_max']
            rate = rate_range['rate']

            # Если price_max = None, значит это открытый диапазон (от price_min и выше)
            if price_max is None:
                if amount >= price_min:
                    return round(amount * rate, 2)
            else:
                if price_min <= amount <= price_max:
                    return round(amount * rate, 2)

        # Если не нашли подходящий диапазон, используем последний (самый высокий)
        if self.rates_cache[key]:
            rate = self.rates_cache[key][-1]['rate']
            return round(amount * rate, 2)

        return 0


# Глобальный конвертер валют
currency_converter = CurrencyConverter()


# Access control
class AccessController:
    """Контроллер для управления доступом при блокировках и потере интернета"""

    def __init__(self):
        self.is_blocked = False
        self.no_internet = False
        self.test_url = "https://store.playstation.com/ru-ua/pages/browse"
        self.internet_check_urls = [
            "https://www.google.com",
            "https://1.1.1.1",  # Cloudflare DNS
            "https://8.8.8.8",  # Google DNS
        ]

    async def check_internet(self, session: aiohttp.ClientSession) -> bool:
        """Проверяет наличие интернет-соединения"""
        for url in self.internet_check_urls:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(10)) as resp:
                    if resp.status < 500:  # Любой ответ кроме серверной ошибки = интернет есть
                        return True
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                continue
        return False

    async def check_access(self, session: aiohttp.ClientSession) -> Tuple[bool, str]:
        """
        Проверяет доступность сайта
        Возвращает: (доступен, причина_недоступности)
        """
        try:
            async with session.get(self.test_url, headers=page_headers(), timeout=aiohttp.ClientTimeout(30)) as resp:
                html = await resp.text()

            # Проверяем блокировку Cloudflare
            if "You don't have permission to access" in html:
                return False, "cloudflare"
            return True, ""

        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            # Сетевая ошибка - проверяем интернет
            has_internet = await self.check_internet(session)
            if not has_internet:
                return False, "no_internet"
            # Интернет есть, но сайт недоступен
            return False, "site_down"

        except Exception:
            return False, "unknown"

    async def wait_for_access(self, session: aiohttp.ClientSession):
        """Ожидает восстановления доступа (блокировка или интернет)"""
        if not self.is_blocked and not self.no_internet:
            # Первая проверка - определяем причину
            has_access, reason = await self.check_access(session)

            if reason == "no_internet":
                self.no_internet = True
                print("\n" + "=" * 80)
                print(" ПОТЕРЯ ИНТЕРНЕТ-СОЕДИНЕНИЯ")
                print("=" * 80)
                print(f" Ожидание восстановления интернета (проверка каждые {parser_config.ACCESS_DENIED_CHECK_INTERVAL} сек)...")
            elif reason == "cloudflare":
                self.is_blocked = True
                print("\n" + "=" * 80)
                print(" ОБНАРУЖЕНА БЛОКИРОВКА CLOUDFLARE")
                print("=" * 80)
                print(f" Ожидание восстановления доступа (проверка каждые {parser_config.ACCESS_DENIED_CHECK_INTERVAL} сек)...")
            elif reason == "site_down":
                print("\n" + "=" * 80)
                print("САЙТ НЕДОСТУПЕН")
                print("=" * 80)
                print(f" Ожидание восстановления сайта (проверка каждые {parser_config.ACCESS_DENIED_CHECK_INTERVAL} сек)...")
            else:
                print("\n" + "=" * 80)
                print("НЕИЗВЕСТНАЯ ОШИБКА ДОСТУПА")
                print("=" * 80)
                print(f" Повтор попыток (проверка каждые {parser_config.ACCESS_DENIED_CHECK_INTERVAL} сек)...")

        while True:
            has_access, reason = await self.check_access(session)

            if has_access:
                # Доступ восстановлен
                if self.no_internet:
                    print("\n" + "=" * 80)
                    print("ИНТЕРНЕТ ВОССТАНОВЛЕН")
                    print("=" * 80)
                    self.no_internet = False
                elif self.is_blocked:
                    print("\n" + "=" * 80)
                    print("БЛОКИРОВКА СНЯТА")
                    print("=" * 80)
                    self.is_blocked = False
                else:
                    print("\n" + "=" * 80)
                    print("ДОСТУП ВОССТАНОВЛЕН")
                    print("=" * 80)

                print("Продолжение парсинга...\n")
                return True

            # Обновляем статус
            if reason == "no_internet":
                if not self.no_internet:
                    self.no_internet = True
                    self.is_blocked = False
                    print(" Переключено на ожидание интернета...")
            elif reason == "cloudflare":
                if not self.is_blocked:
                    self.is_blocked = True
                    self.no_internet = False
                    print(" Обнаружена блокировка Cloudflare...")

            await asyncio.sleep(parser_config.ACCESS_DENIED_CHECK_INTERVAL)


# Глобальный экземпляр контроллера доступа
access_controller = AccessController()


# Utility functions
def format_time(seconds: float) -> str:
    """Форматирует секунды в читаемый формат (Ч:ММ:СС)"""
    if seconds < 0:
        return "0:00:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def print_progress_bar(current: int, total: int, elapsed: float, prefix: str = "", suffix: str = ""):
    """Выводит прогресс-бар с ETA"""
    if total == 0:
        return

    progress = current / total
    percent = progress * 100

    # Рассчитываем ETA
    if current > 0 and progress > 0:
        avg_time_per_item = elapsed / current
        remaining_items = total - current
        eta_seconds = avg_time_per_item * remaining_items
        eta_str = format_time(eta_seconds)
    else:
        eta_str = "расчет..."

    # Прогресс-бар
    bar_length = 40
    filled_length = int(bar_length * progress)
    bar = '#' * filled_length + '-' * (bar_length - filled_length)

    # Скорость
    items_per_sec = current / elapsed if elapsed > 0 else 0

    try:
        print(f"\r{prefix} |{bar}| {percent:.1f}% [{current}/{total}] | "
              f"{format_time(elapsed)} | {items_per_sec:.1f}/s | ETA: {eta_str} {suffix}",
              end='', flush=True)
    except UnicodeEncodeError:
        # Fallback для проблем с кодировкой
        print(f"\r{prefix} |{bar}| {percent:.1f}% [{current}/{total}] | "
              f"{format_time(elapsed)} | {items_per_sec:.1f}/s | ETA: {eta_str}",
              end='', flush=True)


def get_params(url: str):
    product_type, sku = url.split("/")[-2:]
    queries = {
        "concept": {
                "operationName": "conceptRetrieveForCtasWithPrice",
                "variables": dumps({"conceptId": sku}),
                "extensions": dumps({
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "eab9d873f90d4ad98fd55f07b6a0a606e6b3925f2d03b70477234b79c1df30b5"
                    }
                })
            }
        ,
        "product": [
            {
                "operationName": "productRetrieveForCtasWithPrice",
                "variables": dumps({"productId": sku}),
                "extensions": dumps({
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "8872b0419dcab2fea5916ef698544c237b1096f9e76acc6aacf629551adee8cd"
                    }
                })
            },
            {
                "operationName": "productRetrieveForUpsellWithCtas",
                "variables": dumps({"productId": sku}),
                "extensions": dumps({
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "fb0bfa0af4d8dc42b28fa5c077ed715543e7fb8a3deff8117a50b99864d246f1"
                    }
                })
            }
        ]
    }
    return queries[product_type]


def get_random_user_agent() -> str:
    """Возвращает случайный User-Agent из большой коллекции для максимальной защиты"""
    return choice([
        # Chrome на Windows (разные версии)
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',

        # Chrome на macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',

        # Chrome на Linux
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',

        # Firefox на Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:117.0) Gecko/20100101 Firefox/117.0',

        # Firefox на macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13.6; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14.1; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0',

        # Firefox на Linux
        'Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',

        # Safari на macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',

        # Edge на Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.0.0',

        # Edge на macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',

        # Opera на Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 OPR/104.0.0.0',

        # Opera на macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0',

        # Brave на Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Brave/120.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Brave/119.0.0.0',

        # Vivaldi на Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Vivaldi/6.5.3206.63',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Vivaldi/6.4.3160.47',

        # Старые версии для разнообразия
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',

        # Дополнительные Chrome Windows (версии 113-122)
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Fedora; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Debian; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:116.0) Gecko/20100101 Firefox/116.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:114.0) Gecko/20100101 Firefox/114.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:113.0) Gecko/20100101 Firefox/113.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:119.0) Gecko/20100101 Firefox/119.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:118.0) Gecko/20100101 Firefox/118.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:117.0) Gecko/20100101 Firefox/117.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13.0; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13.1; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13.2; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13.3; rv:119.0) Gecko/20100101 Firefox/119.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14.0; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14.2; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:119.0) Gecko/20100101 Firefox/119.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:118.0) Gecko/20100101 Firefox/118.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:117.0) Gecko/20100101 Firefox/117.0',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (X11; Debian; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:116.0) Gecko/20100101 Firefox/116.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.2 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.0.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 OPR/103.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 OPR/102.0.0.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 OPR/104.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Brave/121.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Brave/118.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Brave/117.0.0.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Brave/121.0.0.0',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Brave/120.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Brave/121.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Brave/120.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Brave/121.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Vivaldi/6.6.3271.48',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Vivaldi/6.3.3160.41',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Vivaldi/6.2.3105.58',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Vivaldi/6.6.3271.48',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Vivaldi/6.5.3206.63',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Vivaldi/6.6.3271.48',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Vivaldi/6.5.3206.63',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Vivaldi/6.6.3271.48',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 YaBrowser/24.1.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 YaBrowser/24.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 YaBrowser/24.1.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 YaBrowser/24.1.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:112.0) Gecko/20100101 Firefox/112.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:115.0) Gecko/20100101 Firefox/115.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:115.0) Gecko/20100101 Firefox/115.0',
    ])


def json_headers(url: str) -> Dict[str, str]:
    """Генерирует заголовки для JSON запросов"""
    return {
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,ru;q=0.9",
        "apollographql-client-name": "@sie-private/web-commerce-anywhere",
        "apollographql-client-version": "3.23.0",
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "disable_query_whitelist": "false",
        "Origin": "https://store.playstation.com",
        "Pragma": "no-cache",
        "Priority": "u=1, i",
        "Referer": "https://store.playstation.com/",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "User-Agent": get_random_user_agent(),
        "x-psn-app-ver": "@sie-private/web-commerce-anywhere/3.23.0-d3947b39a30477ef83ad9e5fc7f3f6a72e17bb6b",
        "x-psn-store-locale-override": url.split("/")[-3] if len(url.split("/")) > 3 else "ru-ua"
    }


def page_headers() -> Dict[str, str]:
    """Генерирует заголовки для страниц"""
    return {
        "authority": "store.playstation.com",
        "method": "GET",
        "scheme": "https",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "priority": "u=0, i",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": get_random_user_agent()
    }


# Edition type normalizer
class EditionTypeNormalizer:
    """Унификация типов изданий"""

    EDITION_MAPPINGS = {
        "Полная версия игры": "Игра",
        "PS2 HD+": "Игра",
        "Полная ознакомительная версия игры": "Демо",
        "Демоверсия": "Демо",
        "Набор": "Набор",
        "Сезонный абонемент": "Season Pass",
        "Пакет": "Дополнение",
        "Дополнение": "Дополнение",
        "Доп. материалы": "Дополнение",
        "Валюта игры": "Внутриигровая валюта",
        "Виртуальные деньги": "Внутриигровая валюта",
        "Косметический предмет": "Косметика",
    }

    @staticmethod
    def normalize_type(product_type: str) -> str:
        """Нормализует тип продукта"""
        if not product_type:
            return "Игра"

        product_type_lower = product_type.lower()

        # Проверяем точные совпадения
        if product_type in EditionTypeNormalizer.EDITION_MAPPINGS:
            return EditionTypeNormalizer.EDITION_MAPPINGS[product_type]

        # Проверяем подстроки
        if "подписка" in product_type_lower:
            return "Подписка"
        if "демо" in product_type_lower or "demo" in product_type_lower:
            return "Демо"
        if "предзаказ" in product_type_lower:
            return "Предзаказ"
        if "дополнение" in product_type_lower or "dlc" in product_type_lower or "доп" in product_type_lower:
            return "Дополнение"
        if "набор" in product_type_lower or "bundle" in product_type_lower:
            return "Набор"
        if "валюта" in product_type_lower or "points" in product_type_lower or "баксы" in product_type_lower:
            return "Внутриигровая валюта"

        return "Игра"


# Duplicate detector
class DuplicateDetector:
    """Детектор дубликатов продуктов"""

    def __init__(self):
        self.seen_urls: Set[str] = set()
        self.seen_products: Set[str] = set()
        self.seen_hashes: Set[str] = set()

    def is_duplicate_url(self, url: str) -> bool:
        """Проверяет, является ли URL дубликатом"""
        normalized_url = self._normalize_url(url)
        if normalized_url in self.seen_urls:
            return True
        self.seen_urls.add(normalized_url)
        return False

    def is_duplicate_product(self, name: str, edition: str, platforms: List[str], description: str) -> bool:
        """Проверяет, является ли продукт дубликатом (используется после парсинга)"""
        product_key = (
            name.strip().lower(),
            edition.strip().lower() if edition else "",
            " ".join(sorted(platforms)) if platforms else "",
            (description[:100] if description else "").strip().lower()
        )

        if product_key in self.seen_products:
            return True
        self.seen_products.add(product_key)
        return False

    def get_product_hash(self, product: Dict) -> str:
        """Создает хэш продукта для проверки дубликатов"""
        hash_string = f"{product.get('name', '')}_{product.get('edition', '')}_{product.get('platforms', '')}_{product.get('id', '')}"
        return hashlib.md5(hash_string.encode()).hexdigest()

    def is_duplicate_hash(self, product_hash: str) -> bool:
        """Проверяет дубликат по хэшу"""
        if product_hash in self.seen_hashes:
            return True
        self.seen_hashes.add(product_hash)
        return False

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Нормализует URL для сравнения"""
        url = url.lower().strip()
        # Убираем trailing slash
        url = url.rstrip('/')
        # Убираем query параметры для некоторых URL
        if '?' in url and 'concept' not in url and 'product' not in url:
            url = url.split('?')[0]
        return url


async def get_pages(session: aiohttp.ClientSession, url: str):
    """Получает список страниц категории"""
    try:
        async with session.get(url, headers=page_headers()) as resp:
            html = await resp.text()

        if "You don't have permission to access" in html:
            print(f"Обнаружена блокировка на {url}")
            await access_controller.wait_for_access(session)
            # Повторяем запрос после восстановления доступа
            return await get_pages(session, url)

        soup = bs(html, "html.parser")
        _main = soup.find("div", {"id": "__next"})
        if not _main:
            return []

        _main = _main.find("main")
        if not _main:
            return []

        section = _main.find("section", {"class": "ems-sdk-grid"})
        if not section:
            return [url]

        psw = section.find("div", {"class": "psw-l-stack-center"})
        if not psw:
            return [url]

        nav = psw.find("nav")
        if not nav:
            return [url]

        ol = nav.find("ol")
        if not ol:
            return [url]

        items = ol.find_all("li")
        if not items:
            return [url]

        count = int(items[-1].find("span").text)
        return [f"{url}/{i}" for i in range(1, count + 1)]

    except (asyncio.CancelledError, KeyboardInterrupt):
        return []
    except Exception as e:
        print(f"Error getting pages from {url}: {e}")
        return []


async def get_products(session: aiohttp.ClientSession, url: str):
    """Получает список продуктов со страницы"""
    for attempt in range(parser_config.MAX_RETRIES):
        try:
            async with session.get(url, headers=page_headers()) as resp:
                html = await resp.text()

            if "You don't have permission to access" in html:
                await access_controller.wait_for_access(session)
                # Повторяем запрос после восстановления доступа
                continue

            soup = bs(html, "html.parser")
            _main = soup.find("div", {"id": "__next"})
            if not _main:
                continue

            _main = _main.find("main")
            if not _main:
                continue

            section = _main.find("section", {"class": "ems-sdk-grid"})
            if not section:
                continue

            ul = section.find("ul", {"class": "psw-grid-list psw-l-grid"})
            if not ul:
                continue

            products = ul.find_all("li")
            return ["https://store.playstation.com" + i.find("a")["href"] for i in products if i.find("a")]

        except (asyncio.CancelledError, KeyboardInterrupt):
            return []
        except Exception as e:
            if attempt == parser_config.MAX_RETRIES - 1:
                print(f"Failed to get products from {url}: {e}")
            await asyncio.sleep(2)

    return []

async def unquote(session: aiohttp.ClientSession, url: str):
    """Разворачивает concept URL в product URL"""
    try:
        if "product" in url:
            return [url]

        async with session.get(
            "https://web.np.playstation.com/api/graphql/v1/op",
            headers=json_headers(url),
            params=get_params(url)
        ) as resp:
            text = await resp.text()

        json_data = loads(text)
        products = json_data.get("data", {}).get("conceptRetrieve", {}).get("products", [])

        if not products:
            return []

        base_url = "/".join(url.split("/")[:4])
        return [f'{base_url}/product/{product["id"]}' for product in products]

    except (asyncio.CancelledError, KeyboardInterrupt):
        return []
    except Exception:
        return []


async def get_tr_data(session: aiohttp.ClientSession, tr_url: str, params: Dict) -> Optional[Dict]:
    """
    Получает TR данные по точному product ID с fallback на перебор последней цифры CUSA
    """
    # Сначала пробуем точный product ID
    try:
        async with session.get(
            "https://web.np.playstation.com/api/graphql/v1/op",
            params=params,
            headers=json_headers(tr_url),
            timeout=aiohttp.ClientTimeout(30)
        ) as resp:
            text = await resp.text()
            data = loads(text)

            # Проверяем успешность запроса
            if data.get("data") and data["data"].get("productRetrieve"):
                return data
    except Exception:
        pass

    # Если не получилось, пробуем варианты CUSA с разными последними цифрами
    # Извлекаем product_id из params
    try:
        params_dict = loads(params.get("variables", "{}")) if isinstance(params.get("variables"), str) else params.get("variables", {})
        original_product_id = params_dict.get("productId", "")

        if original_product_id and "CUSA" in original_product_id:
            # Ищем CUSA в product_id (формат: EP0001-CUSA05848_00-FARCRY5GAME00000)
            match = re.search(r'(CUSA\d{4})(\d)', original_product_id)

            if match:
                cusa_base = match.group(1)  # CUSA05848 -> CUSA0584
                last_digit = match.group(2)  # 8

                # Перебираем цифры от 0 до 9, кроме уже проверенной
                for digit in range(10):
                    if str(digit) == last_digit:
                        continue  # Уже проверили

                    # Формируем новый product_id с другой последней цифрой
                    new_product_id = original_product_id.replace(
                        f"{cusa_base}{last_digit}",
                        f"{cusa_base}{digit}"
                    )

                    # Формируем новые params
                    new_params_dict = params_dict.copy()
                    new_params_dict["productId"] = new_product_id

                    new_params = params.copy()
                    new_params["variables"] = dumps(new_params_dict)

                    try:
                        async with session.get(
                            "https://web.np.playstation.com/api/graphql/v1/op",
                            params=new_params,
                            headers=json_headers(tr_url),
                            timeout=aiohttp.ClientTimeout(30)
                        ) as resp:
                            text = await resp.text()
                            data = loads(text)

                            # Проверяем успешность запроса
                            if data.get("data") and data["data"].get("productRetrieve"):
                                print(f"  TR CUSA fallback: {original_product_id} -> {new_product_id}")
                                return data
                    except Exception:
                        continue
    except Exception:
        pass

    return None


async def get_localization_for_region(session: aiohttp.ClientSession, product_id: str, region_code: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Парсит локализацию (озвучка и субтитры) для конкретного региона

    Args:
        session: aiohttp сессия
        product_id: ID продукта (например EP0001-CUSA12345_00-GAME000000000000)
        region_code: Код региона (ru-ua, en-tr, en-in)

    Returns:
        Tuple[voice_languages, subtitles] - строки с языками или (None, None) если не удалось спарсить
    """
    counter = 0
    max_retries = 3

    while counter < max_retries:
        try:
            url = f"https://store.playstation.com/{region_code}/product/{product_id}"
            async with session.get(url, headers=page_headers(), timeout=aiohttp.ClientTimeout(30)) as resp:
                text = await resp.text()

            # Проверка на блокировку
            if "You don't have permission to access" in text:
                await access_controller.wait_for_access(session)
                counter = 0
                continue

            soup = bs(text, "html.parser")
            _main = soup.find("main")
            if not _main:
                counter += 1
                await asyncio.sleep(5)
                continue

            pdp = _main.find("div", {"class": "pdp-main psw-dark-theme"})
            if not pdp:
                counter += 1
                await asyncio.sleep(5)
                continue

            psw_list = pdp.find_all("div", {"class": "psw-m-t-10 psw-fill-x"})
            psw = None
            for _psw in psw_list:
                if _psw.find("div", {"class": "pdp-info"}):
                    psw = _psw
                    break

            if not psw:
                counter += 1
                await asyncio.sleep(5)
                continue

            game_info = psw.find("div", {"data-qa": "gameInfo"})
            if not game_info:
                counter += 1
                await asyncio.sleep(5)
                continue

            dl = game_info.find("dl")
            if not dl:
                counter += 1
                await asyncio.sleep(5)
                continue

            # Парсим локализацию
            voice_languages = ""
            subtitles = ""

            # Общие языки озвучки
            if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#voice-value"}):
                voice_languages = dl.find("dd", {"data-qa": "gameInfo#releaseInformation#voice-value"}).text

            # Общие субтитры
            if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#subtitles-value"}):
                subtitles = dl.find("dd", {"data-qa": "gameInfo#releaseInformation#subtitles-value"}).text

            # PS5 озвучка
            if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps5Voice-value"}):
                voice_languages += " " + dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps5Voice-value"}).text

            # PS4 озвучка
            if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps4Voice-value"}):
                voice_languages += " " + dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps4Voice-value"}).text

            # PS5 субтитры
            if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps5Subtitles-value"}):
                subtitles += " " + dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps5Subtitles-value"}).text

            # PS4 субтитры
            if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps4Subtitles-value"}):
                subtitles += " " + dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps4Subtitles-value"}).text

            return voice_languages.strip(), subtitles.strip()

        except (asyncio.CancelledError, KeyboardInterrupt):
            return None, None
        except Exception as e:
            counter += 1
            await asyncio.sleep(5)

    # Если не удалось спарсить после всех попыток
    return None, None


async def parse(session: aiohttp.ClientSession, url: str, regions: list = None, logger: ParseLogger = None):
    """
    Парсит товар из указанных регионов

    Args:
        session: aiohttp сессия
        url: URL товара (ru-ua)
        regions: Список регионов для парсинга ["UA", "TR", "IN"].
                 По умолчанию None = все регионы
        logger: Опциональный ParseLogger для записи ошибок

    Returns:
        List[Dict]: Список товаров по регионам
    """
    # Если regions не указан, парсим все регионы (режимы 1, 2, 3)
    if regions is None:
        regions = ["UA", "TR", "IN"]

    params_price, params = get_params(url)

    # Формируем URL для разных регионов только если они запрошены
    tr_url = None
    in_url = None

    if "TR" in regions:
        tr_url = url.split("/")
        tr_url[3] = "en-tr"
        tr_url = "/".join(tr_url)

    if "IN" in regions:
        in_url = url.split("/")
        in_url[3] = "en-in"
        in_url = "/".join(in_url)

    async def get_ext_data(product):
        pdp = None
        psw = None
        game_info = None
        dl = None

        counter = 0

        platforms = None
        publisher = None
        voice_languages = None
        subtitles = None
        description = None
        ext_info = None
        json = None

        while (not pdp and not psw and not game_info and not dl) and counter < 3:
            try:
                async with session.get(f"https://store.playstation.com/ru-ua/product/{product}", headers=page_headers()) as resp:
                    text = await resp.text()

                if "You don't have permission to access" in text:
                    counter = 0
                    await asyncio.sleep(30)
                    continue

                soup = bs(text, "html.parser")

                _main = soup.find("main")
                pdp = _main.find("div", {"class": "pdp-main psw-dark-theme"})
                if not pdp:
                    counter += 1
                    await asyncio.sleep(5)
                    continue
                psw = pdp.find_all("div", {"class": "psw-m-t-10 psw-fill-x"})


                for _psw in psw:
                    if _psw.find("div", {"class": "pdp-info"}):
                        psw = _psw
                        break
                else:
                    counter += 1
                    await asyncio.sleep(5)
                    continue
                game_info = psw.find("div", {"data-qa": "gameInfo"})
                if not game_info:
                    counter += 1
                    await asyncio.sleep(5)
                    continue

                dl = game_info.find("dl")
                if not dl:
                    counter += 1
                    await asyncio.sleep(5)
                    continue

                soup = bs(text, "html.parser")
                json = soup.find("script", {"id": "__NEXT_DATA__", "type": "application/json"}).text

                json = loads(json)

                if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#platform-value"}):
                    platforms = dl.find("dd", {"data-qa": "gameInfo#releaseInformation#platform-value"}).text.split(', ')
                if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#publisher-value"}):
                    publisher = dl.find("dd", {"data-qa": "gameInfo#releaseInformation#publisher-value"}).text

                voice_languages, subtitles = "", ""
                if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#voice-value"}):
                    voice_languages = dl.find("dd", {"data-qa": "gameInfo#releaseInformation#voice-value"}).text
                if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#subtitles-value"}):
                    subtitles = dl.find("dd", {"data-qa": "gameInfo#releaseInformation#subtitles-value"}).text

                if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps5Voice-value"}):
                    voice_languages += dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps5Voice-value"}).text
                if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps4Voice-value"}):
                    voice_languages += dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps4Voice-value"}).text

                if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps5Subtitles-value"}):
                    subtitles += dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps5Subtitles-value"}).text
                if dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps4Voice-value"}):
                    subtitles += dl.find("dd", {"data-qa": "gameInfo#releaseInformation#ps4Subtitles-value"}).text

                # Парсинг количества игроков
                players_min = None
                players_max = None
                players_online = False

                # Ищем информацию о количестве игроков в HTML
                players_dd = dl.find("dd", {"data-qa": "gameInfo#releaseInformation#playerCount-value"})
                if not players_dd:
                    players_dd = dl.find("dd", {"data-qa": "gameInfo#releaseInformation#players-value"})

                if players_dd:
                    players_text = players_dd.text.strip()

                    # Онлайн игроки
                    if "онлайн" in players_text.lower() or "online" in players_text.lower():
                        players_online = True

                    # Парсинг диапазона игроков (например, "1-4 игрока" или "1 игрок")
                    import re
                    numbers = re.findall(r'\d+', players_text)
                    if numbers:
                        players_min = int(numbers[0])
                        if len(numbers) > 1:
                            players_max = int(numbers[1])
                        else:
                            players_max = players_min

                # Если не нашли в HTML, пробуем парсить из JSON (compatibilityNoticesByPlatform)
                if players_min is None and json and "props" in json:
                    try:
                        product_data = json["props"]["pageProps"]["apolloState"]
                        for key, value in product_data.items():
                            if key.startswith("Product:") and isinstance(value, dict):
                                compat = value.get("compatibilityNoticesByPlatform", {})
                                common_notices = compat.get("Common", [])
                                if common_notices:
                                    for notice in common_notices:
                                        if notice.get("type") == "NO_OF_PLAYERS":
                                            player_value = notice.get("value", "")
                                            numbers = re.findall(r'\d+', str(player_value))
                                            if numbers:
                                                players_min = int(numbers[0])
                                                if len(numbers) > 1:
                                                    players_max = int(numbers[1])
                                                else:
                                                    players_max = players_min
                                        elif notice.get("type") == "OFFLINE_PLAY_MODE":
                                            if notice.get("value") == "ENABLED":
                                                players_online = False
                                        elif "ONLINE" in notice.get("type", ""):
                                            players_online = True
                                    break
                    except Exception as e:
                        # Если не удалось распарсить JSON, продолжаем без игроков
                        pass

                description = bs(json["props"]["pageProps"]["batarangs"]["overview"]["text"], "html.parser").get_text("\n\n", strip=True)
                ext_info = json["props"]["pageProps"]["batarangs"]["compatibility-notices"]["text"]
                _tmp = findall(r">([^<]+)</", ext_info)
                if len(_tmp) > 1:
                    ext_info = dumps(_tmp[1:])


            except (asyncio.CancelledError, KeyboardInterrupt):
                return []
            except:
                counter += 1
                await asyncio.sleep(5)

        return product, platforms, publisher, voice_languages, subtitles, description, ext_info, json, players_min, players_max, players_online

    counter = 0
    max_parse_retries = 4

    while counter < max_parse_retries:
        try:
            async with session.get("https://web.np.playstation.com/api/graphql/v1/op", params=params, headers=json_headers(url)) as ua_resp:
                ua = await ua_resp.text()
            async with session.get("https://web.np.playstation.com/api/graphql/v1/op", params=params_price, headers=json_headers(url)) as ua_resp_price:
                ua_price = await ua_resp_price.text()


            ua = loads(ua)
            ua_price = loads(ua_price)
            ua_products = []
            ua_price_product = []

            if not ua.get("data") or not ua["data"].get("productRetrieve"):
                return []

            if ua["data"]["productRetrieve"].get("concept") and ua["data"]["productRetrieve"].get("topCategory") != "ADD_ON":
                ua_products = ua["data"]["productRetrieve"]["concept"]["products"]

                # Получаем TR данные только если TR в списке регионов
                if "TR" in regions and tr_url:
                    tr_price = await get_tr_data(session, tr_url, params)
                    if not tr_price:
                        # Если нет данных для TR, создаем пустую структуру
                        tr_price = {"data": {"productRetrieve": {}}}
                else:
                    tr_price = {"data": {"productRetrieve": {}}}

                # Получаем IN данные только если IN в списке регионов
                if "IN" in regions and in_url:
                    in_price = await get_tr_data(session, in_url, params)
                    if not in_price:
                        # Если нет данных для IN, создаем пустую структуру
                        in_price = {"data": {"productRetrieve": {}}}
                else:
                    in_price = {"data": {"productRetrieve": {}}}
            else:
                ua_price_product = ua_price.get("data", {}).get("productRetrieve") or {}

                # Получаем TR данные только если TR в списке регионов
                if "TR" in regions and tr_url:
                    tr_price = await get_tr_data(session, tr_url, params_price)
                    if not tr_price:
                        # Если нет данных для TR, создаем пустую структуру
                        tr_price = {"data": {"productRetrieve": {}}}
                else:
                    tr_price = {"data": {"productRetrieve": {}}}

                # Получаем IN данные только если IN в списке регионов
                if "IN" in regions and in_url:
                    in_price = await get_tr_data(session, in_url, params_price)
                    if not in_price:
                        # Если нет данных для IN, создаем пустую структуру
                        in_price = {"data": {"productRetrieve": {}}}
                else:
                    in_price = {"data": {"productRetrieve": {}}}

            if not tr_price or not tr_price.get("data", {}).get("productRetrieve"):
                # Если TR недоступен, продолжаем только с UA данными
                tr_price = {"data": {"productRetrieve": {}}}

            if not in_price or not in_price.get("data", {}).get("productRetrieve"):
                # Если IN недоступен, продолжаем без IN данных
                in_price = {"data": {"productRetrieve": {}}}

            # Get TR price products
            tr_price_data = tr_price["data"]["productRetrieve"]
            tr_price_products = []

            if tr_price_data and isinstance(tr_price_data, dict):
                if "concept" in tr_price_data and tr_price_data["concept"] and "products" in tr_price_data["concept"]:
                    tr_price_products = tr_price_data["concept"]["products"]
                elif "webctas" in tr_price_data:
                    tr_price_products = [tr_price_data]

            # Get IN price products
            in_price_data = in_price["data"]["productRetrieve"]
            in_price_products = []

            if in_price_data and isinstance(in_price_data, dict):
                if "concept" in in_price_data and in_price_data["concept"] and "products" in in_price_data["concept"]:
                    in_price_products = in_price_data["concept"]["products"]
                elif "webctas" in in_price_data:
                    in_price_products = [in_price_data]

            result = []

            if "errors" in ua:
                errors_list = ua.get("errors", [])
                is_concept_unavailable = any(
                    "not available" in str(e.get("message", "")).lower()
                    for e in errors_list if isinstance(e, dict)
                )
                if is_concept_unavailable:
                    return []
                if logger:
                    errors_text = str(errors_list)[:200]
                    logger.log_product_error(url, f"GraphQL вернул errors: {errors_text}")
                return []

            ua_concept = ua["data"]["productRetrieve"].get("concept")
            if ua_concept and isinstance(ua_concept, dict) and "name" in ua_concept:
                main_name = ua_concept["name"]
            elif ua["data"]["productRetrieve"].get("name"):
                main_name = ua["data"]["productRetrieve"]["name"]

            tags = []

            try:

                if ua_products:
                    _pre_ext = await asyncio.gather(*[get_ext_data(p["id"]) for p in ua_products])
                    ext = {k[0]: k[1:] for k in _pre_ext}


                    for product in ua_products:
                        if main_name not in tags:
                            tags.append(main_name)
                        ID = product["id"]
                        name = product["name"]

                        platforms, publisher, voice_languages, subtitles, description, ext_info, json, players_min, players_max, players_online = ext[ID]

                        # Получаем локализации для TR и IN регионов только если они запрошены
                        voice_languages_tr, subtitles_tr = None, None
                        voice_languages_in, subtitles_in = None, None

                        if "TR" in regions:
                            voice_languages_tr, subtitles_tr = await get_localization_for_region(session, ID, "en-tr")
                        if "IN" in regions:
                            voice_languages_in, subtitles_in = await get_localization_for_region(session, ID, "en-in")

                        # Безопасный парсинг рейтинга
                        stars = 0.0
                        try:
                            star_rating_text = json["props"]["pageProps"]["batarangs"]["star-rating"]["text"]
                            star_matches = findall(r">([^<]+)</", star_rating_text)
                            if star_matches:
                                stars_json = loads(star_matches[0])
                                stars = stars_json["cache"][f"Product:{ID}"]["starRating"]["averageRating"]
                        except (KeyError, IndexError, ValueError, TypeError) as e:
                            print(f"   Не удалось получить рейтинг для {ID}: {type(e).__name__}")
                            stars = 0.0

                        if not publisher:
                            if logger:
                                logger.log_product_error(url, f"Продукт {ID} ({name}) пропущен: нет publisher")
                            continue
                        category = []
                        if product["localizedGenres"]:
                            category = list(set(i["value"] for i in product["localizedGenres"]))
                        product_type = ""
                        if "Подписка" in name:
                            product_type = "Подписка"
                        else:
                            if product["skus"][0]["name"].lower() != "демоверсия" or product["skus"][0]["name"].lower() != "Полная ознакомительная версия игры":
                                product_type = product["skus"][0]["name"]
                            else:
                                if len(product["skus"]) > 1:
                                    product_type = product["skus"][1]["name"]
                            if product["skus"][0]["name"].lower() == "демоверсия" or product["skus"][0]["name"].lower() == "полная ознакомительная версия игры" or not product_type:
                                product_type = "Игра"

                        # Нормализуем тип продукта
                        product_type = EditionTypeNormalizer.normalize_type(product_type)


                        image = product["media"]
                        if not image:
                            tr_concept = tr_price.get("data", {}).get("productRetrieve", {}).get("concept", {})
                            if tr_concept:
                                image = tr_concept.get("media", [])
                        if not image:
                            image = []
                        for img in image:
                            if img["role"] == "MASTER":
                                image = img["url"]
                                break

                        tags.append(name)

                        if name != product["invariantName"]:
                            tags.append(product["invariantName"])

                        # Собираем все уникальные названия из всех регионов для двуязычного поиска
                        all_region_names = set()
                        all_region_names.add(name)  # UA название
                        all_region_names.add(main_name)  # Основное название
                        if product["invariantName"]:
                            all_region_names.add(product["invariantName"])

                        tr_name = ""
                        in_name = ""

                        # Добавляем названия из TR региона (если парсили TR)
                        if "TR" in regions and tr_price_products:
                            for trl_product in tr_price_products:
                                eq_id = trl_product["id"].split("-")[-1][:-1] == ID.split("-")[-1][:-1]
                                if any([ID == tr["id"] for tr in tr_price_products]):
                                    eq_id = trl_product["id"] == ID
                                if eq_id:
                                    tr_name = trl_product.get("name", "")
                                    if tr_name:
                                        all_region_names.add(tr_name)
                                    tr_invariant = trl_product.get("invariantName", "")
                                    if tr_invariant and tr_invariant != tr_name:
                                        all_region_names.add(tr_invariant)
                                    break

                        # Добавляем названия из IN региона (если парсили IN)
                        if "IN" in regions and in_price_products:
                            for in_product in in_price_products:
                                eq_id = in_product["id"].split("-")[-1][:-1] == ID.split("-")[-1][:-1]
                                if any([ID == inp["id"] for inp in in_price_products]):
                                    eq_id = in_product["id"] == ID
                                if eq_id:
                                    in_name = in_product.get("name", "")
                                    if in_name:
                                        all_region_names.add(in_name)
                                    in_invariant = in_product.get("invariantName", "")
                                    if in_invariant and in_invariant != in_name:
                                        all_region_names.add(in_invariant)
                                    break

                        # Обновляем теги всеми названиями из всех регионов
                        tags = list(all_region_names)

                        uah_price = 0
                        uah_old_price = 0
                        discount = ""
                        discount_end = None

                        trl_price = 0
                        trl_old_price = 0
                        inr_price = 0
                        inr_old_price = 0

                        # ps_plus_essential = False
                        # ps_plus_extra = False
                        # ps_plus_delux = False
                        ps_plus = False
                        ea_access = False
                        ps_plus_collection_ua = None  # Определяется по CTA типу для UA
                        ps_plus_collection_tr = None  # Определяется по CTA типу для TR
                        ps_plus_collection_in = None  # Определяется по CTA типу для IN

                        ps_price_ua = None
                        ea_price_ua = None
                        ps_price_tr = None
                        ea_price_tr = None
                        ps_price_in = None
                        ea_price_in = None
                        for price in product["webctas"]:
                            if price["type"] in _PURCHASE_CTA_TYPES or ("UPSELL" in price["type"] and ("EA_ACCESS" in price["type"] or "PS_PLUS" in price["type"]) and "TRIAL" not in price["type"]):
                                if price["type"] == "PREORDER":
                                    product_type = "Предзаказ"
                                if price["price"]["discountedPrice"] and price["type"] in _PURCHASE_CTA_TYPES and not uah_price:
                                    uah_price = parse_price_value(price["price"].get("discountedValue", 0))
                                if price["price"]["basePrice"] and price["type"] in _PURCHASE_CTA_TYPES and not uah_old_price:
                                    uah_old_price = parse_price_value(price["price"].get("basePriceValue", 0))
                                if "PS_PLUS" in price["type"] and price["price"]["discountedPrice"] == "Входит в подписку":
                                    ps_plus = True
                                    # Сначала проверяем текст CTA на наличие явного указания типа подписки
                                    cta_type_from_text = detect_ps_plus_type_from_cta_text(price)
                                    
                                    if cta_type_from_text:
                                        # Если найдено явное указание в тексте (Extra или Deluxe), используем его
                                        ps_plus_collection_ua = cta_type_from_text
                                    else:
                                        # Если в тексте нет явного указания, используем определение по типу CTA
                                        if price["type"] == "UPSELL_PS_PLUS_GAME_CATALOG":
                                            ps_plus_collection_ua = "Deluxe/Extra"
                                        elif price["type"] == "UPSELL_PS_PLUS_FREE":
                                            ps_plus_collection_ua = "Essential"
                                        elif price["type"] == "UPSELL_PS_PLUS_CLASSICS_CATALOG":
                                            ps_plus_collection_ua = "Deluxe"
                                        elif price["type"] == "UPSELL_PS_PLUS_CLASSIC_GAME_COLLECTION":
                                            ps_plus_collection_ua = "Deluxe"
                                if "EA_ACCESS" in price["type"] and price["price"]["discountedPrice"] == "Входит в подписку":
                                    ea_access = True
                                if "UPSELL_PS_PLUS_DISCOUNT" == price["type"]:
                                    ps_price_ua = parse_price_value(price["price"].get("discountedValue", 0))
                                if "UPSELL_EA_ACCESS_DISCOUNT" == price["type"]:
                                    ea_price_ua = parse_price_value(price["price"].get("discountedValue", 0))
                                if price["price"]["discountText"] and price["type"] in _PURCHASE_CTA_TYPES:
                                    discount = price["price"]["discountText"]
                                if price["price"]["endTime"] and price["type"] in _PURCHASE_CTA_TYPES:
                                    discount_end = datetime.fromtimestamp(int(price["price"]["endTime"])//1000)

                        is_free_ua = any(
                            p["type"] in _PURCHASE_CTA_TYPES and is_free_price_text(p["price"].get("discountedPrice", ""))
                            for p in product.get("webctas", [])
                        )
                        ua_webctas = product.get("webctas", [])
                        is_unavailable_ua = bool(ua_webctas) and all(p.get("type") == "UNAVAILABLE" for p in ua_webctas)
                        is_free_tr = False
                        is_free_in = False
                        is_unavailable_tr = False
                        is_unavailable_in = False

                        if tr_price_products:
                            for trl_product in tr_price_products:
                                eq_id = trl_product["id"].split("-")[-1][:-1] == ID.split("-")[-1][:-1]
                                if any([ID == tr["id"] for tr in tr_price_products]):
                                    eq_id = trl_product["id"] == ID
                                if eq_id:
                                    for trl in trl_product["webctas"]:
                                        if trl["type"] in _PURCHASE_CTA_TYPES or ("UPSELL" in trl["type"] and ("EA_ACCESS" in trl["type"] or "PS_PLUS" in trl["type"]) and "TRIAL" not in trl["type"]):
                                        # if trl["type"] in ["ADD_TO_CART", "PREORDER"] or "UPSELL" in trl["type"]:
                                            if trl["price"]["discountedPrice"] and trl["type"] in _PURCHASE_CTA_TYPES and not trl_price:
                                                trl_price = parse_price_value(trl["price"].get("discountedValue", 0))
                                            if trl["price"]["basePrice"] and trl["type"] in _PURCHASE_CTA_TYPES and not trl_old_price:
                                                trl_old_price = parse_price_value(trl["price"].get("basePriceValue", 0))
                                            if "PS_PLUS" in trl["type"] and trl["price"]["discountedPrice"] == "Included":
                                                ps_plus = True
                                                # Сначала проверяем текст CTA на наличие явного указания типа подписки
                                                cta_type_from_text = detect_ps_plus_type_from_cta_text(trl)
                                                
                                                if cta_type_from_text:
                                                    # Если найдено явное указание в тексте (Extra или Deluxe), используем его
                                                    ps_plus_collection_tr = cta_type_from_text
                                                else:
                                                    # Если в тексте нет явного указания, используем определение по типу CTA
                                                    if trl["type"] == "UPSELL_PS_PLUS_GAME_CATALOG":
                                                        ps_plus_collection_tr = "Deluxe/Extra"
                                                    elif trl["type"] == "UPSELL_PS_PLUS_FREE":
                                                        ps_plus_collection_tr = "Essential"
                                                    elif trl["type"] == "UPSELL_PS_PLUS_CLASSICS_CATALOG":
                                                        ps_plus_collection_tr = "Deluxe/Premium"
                                                    elif trl["type"] == "UPSELL_PS_PLUS_CLASSIC_GAME_COLLECTION":
                                                        ps_plus_collection_tr = "Deluxe/Premium"
                                            if "EA_ACCESS" in trl["type"] and trl["price"]["discountedPrice"] == "Included":
                                                ea_access = True
                                            if "UPSELL_PS_PLUS_DISCOUNT" == trl["type"]:
                                                ps_price_tr = parse_price_value(trl["price"].get("discountedValue", 0))
                                            if "UPSELL_EA_ACCESS_DISCOUNT" == trl["type"]:
                                                ea_price_tr = parse_price_value(trl["price"].get("discountedValue", 0))
                                    is_free_tr = any(
                                        p["type"] in _PURCHASE_CTA_TYPES and is_free_price_text(p["price"].get("discountedPrice", ""))
                                        for p in trl_product.get("webctas", [])
                                    )
                                    tr_webctas = trl_product.get("webctas", [])
                                    is_unavailable_tr = bool(tr_webctas) and all(p.get("type") == "UNAVAILABLE" for p in tr_webctas)
                                    break

                        # Обработка цен из индийского региона
                        if in_price_products:
                            for in_product in in_price_products:
                                eq_id = in_product["id"].split("-")[-1][:-1] == ID.split("-")[-1][:-1]
                                if any([ID == inp["id"] for inp in in_price_products]):
                                    eq_id = in_product["id"] == ID
                                if eq_id:
                                    for inp in in_product["webctas"]:
                                        if inp["type"] in _PURCHASE_CTA_TYPES or ("UPSELL" in inp["type"] and ("EA_ACCESS" in inp["type"] or "PS_PLUS" in inp["type"]) and "TRIAL" not in inp["type"]):
                                            if inp["price"]["discountedPrice"] and inp["type"] in _PURCHASE_CTA_TYPES and not inr_price:
                                                inr_price = parse_price_value(inp["price"].get("discountedValue", 0), divide_by_100=False)
                                            if inp["price"]["basePrice"] and inp["type"] in _PURCHASE_CTA_TYPES and not inr_old_price:
                                                inr_old_price = parse_price_value(inp["price"].get("basePriceValue", 0), divide_by_100=False)
                                            if "PS_PLUS" in inp["type"] and inp["price"]["discountedPrice"] == "Included":
                                                ps_plus = True
                                                # Сначала проверяем текст CTA на наличие явного указания типа подписки
                                                cta_type_from_text = detect_ps_plus_type_from_cta_text(inp)
                                                
                                                if cta_type_from_text:
                                                    # Если найдено явное указание в тексте (Extra или Deluxe), используем его
                                                    ps_plus_collection_in = cta_type_from_text
                                                else:
                                                    # Если в тексте нет явного указания, используем определение по типу CTA
                                                    if inp["type"] == "UPSELL_PS_PLUS_GAME_CATALOG":
                                                        ps_plus_collection_in = "Deluxe/Extra"
                                                    elif inp["type"] == "UPSELL_PS_PLUS_FREE":
                                                        ps_plus_collection_in = "Essential"
                                                    elif inp["type"] == "UPSELL_PS_PLUS_CLASSICS_CATALOG":
                                                        ps_plus_collection_in = "Deluxe/Premium"
                                                    elif inp["type"] == "UPSELL_PS_PLUS_CLASSIC_GAME_COLLECTION":
                                                        ps_plus_collection_in = "Deluxe/Premium"
                                            if "EA_ACCESS" in inp["type"] and inp["price"]["discountedPrice"] == "Included":
                                                ea_access = True
                                            if "UPSELL_PS_PLUS_DISCOUNT" == inp["type"]:
                                                ps_price_in = parse_price_value(inp["price"].get("discountedValue", 0), divide_by_100=False)
                                            if "UPSELL_EA_ACCESS_DISCOUNT" == inp["type"]:
                                                ea_price_in = parse_price_value(inp["price"].get("discountedValue", 0), divide_by_100=False)
                                    is_free_in = any(
                                        p["type"] in _PURCHASE_CTA_TYPES and is_free_price_text(p["price"].get("discountedPrice", ""))
                                        for p in in_product.get("webctas", [])
                                    )
                                    in_webctas = in_product.get("webctas", [])
                                    is_unavailable_in = bool(in_webctas) and all(p.get("type") == "UNAVAILABLE" for p in in_webctas)
                                    break

                        edition = product["edition"]
                        compound = ""
                        if edition:
                            if edition["features"]:
                                compound = dumps(edition["features"])
                            edition = edition["name"]
                            if not edition:
                                edition = name

                        # Функция для определения кода локализации по языкам
                        def get_localization_code(voice_langs: str, subs: str) -> str:
                            """
                            Определяет код локализации на основе языков озвучки и субтитров

                            Логика:
                            - Если в Voice есть Russian → "full" (полностью на русском)
                            - Иначе если в Screen Languages есть Russian → "subtitles" (русские субтитры)
                            - Иначе → "none" (нет русского)

                            Returns:
                                "full" - полностью на русском (есть озвучка)
                                "subtitles" - только русские субтитры
                                "none" - нет русского языка

                            Примечание:
                                Пустые строки ("", "") означают что данные получены, но языков нет = "none"
                            """
                            # Проверяем наличие русского в разных написаниях
                            has_russian_voice = voice_langs and ("русский" in voice_langs.lower() or "russian" in voice_langs.lower())
                            has_russian_subs = subs and ("русский" in subs.lower() or "russian" in subs.lower())

                            if has_russian_voice:
                                return "full"  # Полностью на русском (есть озвучка)
                            elif has_russian_subs:
                                return "subtitles"  # Только русские субтитры
                            else:
                                return "none"  # Нет русского языка (или пустые строки)

                        # Определяем локализацию для каждого региона отдельно
                        localization_code = get_localization_code(voice_languages, subtitles)
                        # Для TR и IN: если функция вернула данные (даже пустые строки), вызываем get_localization_code
                        # None означает ошибку парсинга, пустые строки ("", "") означают что языков нет = "none"
                        localization_tr = get_localization_code(voice_languages_tr, subtitles_tr) if (voice_languages_tr is not None and subtitles_tr is not None) else None
                        localization_in = get_localization_code(voice_languages_in, subtitles_in) if (voice_languages_in is not None and subtitles_in is not None) else None

                        if not uah_price:
                            uah_price = uah_old_price
                        if not trl_price:
                            trl_price = trl_old_price
                        if not inr_price:
                            inr_price = inr_old_price

                        for t in range(len(tags)):
                            for c in ['™', '®', '©', '℗', '℠', "’"]:
                                to_replace = ""
                                if "’" in tags[t]:
                                    to_replace = "'"
                                tags[t] = tags[t].replace(c, to_replace)

                        # Создаем 3 отдельные записи для каждого региона
                        if product_type:
                            # Базовые данные, общие для всех регионов
                            base_data = {
                                "id": ID,
                                "category": category,
                                "type": product_type,
                                "name": name,
                                "main_name": main_name,
                                "name_localized": name if name != main_name else None,
                                "search_names": ",".join(set(tags)),
                                "image": image,
                                "compound": compound,
                                "platforms": ",".join(platforms) if platforms else None,
                                "publisher": publisher,
                                "rating": stars,
                                "info": ext_info,
                                "ps_plus": 1 if ps_plus else 0,
                                "ps_plus_collection": None,  # Устанавливается индивидуально для каждого региона
                                "ea_access": 1 if ea_access else 0,
                                "tags": ",".join(set(tags)),
                                "edition": edition,
                                "description": description,
                                "players_min": players_min,
                                "players_max": players_max,
                                "players_online": 1 if players_online else 0,
                                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }

                            # 1. UA запись - только если UA в списке регионов
                            if "UA" in regions and (uah_price > 0 or ps_plus_collection_ua or is_free_ua):
                                discount_percent_ua = 0
                                if uah_old_price and uah_old_price > uah_price > 0:
                                    discount_percent_ua = round(((uah_old_price - uah_price) / uah_old_price) * 100)

                                price_rub_ua = currency_converter.convert(uah_price, "UAH", "RUB")
                                old_price_rub_ua = currency_converter.convert(uah_old_price, "UAH", "RUB") if uah_old_price else None
                                ps_plus_price_rub_ua = currency_converter.convert(ps_price_ua, "UAH", "RUB") if ps_price_ua else None

                                ua_record = base_data.copy()
                                ua_record.update({
                                    "region": "UA",
                                    "localization": localization_code,
                                    "price": price_rub_ua,
                                    "old_price": old_price_rub_ua,
                                    "ps_price": ps_plus_price_rub_ua,
                                    "price_uah": uah_price,
                                    "old_price_uah": uah_old_price,
                                    "price_try": 0.0,
                                    "old_price_try": 0.0,
                                    "price_inr": 0.0,
                                    "old_price_inr": 0.0,
                                    "price_rub": price_rub_ua,
                                    "price_rub_region": "UA",
                                    "ps_plus_price_uah": ps_price_ua,
                                    "ps_plus_price_try": None,
                                    "ps_plus_price_inr": None,
                                    "discount": discount_percent_ua,
                                    "discount_percent": discount_percent_ua,
                                    "discount_end": discount_end.strftime("%Y-%m-%d %H:%M:%S") if discount_end else None,
                                })
                                # Обновляем ps_plus и ps_plus_collection для UA региона
                                ua_record["ps_plus"] = 1 if ps_plus_collection_ua else ua_record["ps_plus"]
                                ua_record["ps_plus_collection"] = ps_plus_collection_ua
                                result.append(ua_record)

                            # 2. TR запись - только если TR в списке регионов
                            if "TR" in regions and (trl_price > 0 or ps_plus_collection_tr or is_free_tr):
                                discount_percent_tr = 0
                                if trl_old_price and trl_old_price > trl_price > 0:
                                    discount_percent_tr = round(((trl_old_price - trl_price) / trl_old_price) * 100)

                                price_rub_tr = currency_converter.convert(trl_price, "TRY", "RUB")
                                old_price_rub_tr = currency_converter.convert(trl_old_price, "TRY", "RUB") if trl_old_price else None
                                ps_plus_price_rub_tr = currency_converter.convert(ps_price_tr, "TRY", "RUB") if ps_price_tr else None

                                tr_record = base_data.copy()
                                if tr_name:
                                    tr_record["name"] = tr_name
                                    tr_record["name_localized"] = tr_name if tr_name != main_name else None
                                tr_record.update({
                                    "region": "TR",
                                    "localization": localization_tr if localization_tr else None,
                                    "price": price_rub_tr,
                                    "old_price": old_price_rub_tr,
                                    "ps_price": ps_plus_price_rub_tr,
                                    "price_uah": 0.0,
                                    "old_price_uah": 0.0,
                                    "price_try": trl_price,
                                    "old_price_try": trl_old_price,
                                    "price_inr": 0.0,
                                    "old_price_inr": 0.0,
                                    "price_rub": price_rub_tr,
                                    "price_rub_region": "TR",
                                    "ps_plus_price_uah": None,
                                    "ps_plus_price_try": ps_price_tr,
                                    "ps_plus_price_inr": None,
                                    "discount": discount_percent_tr,
                                    "discount_percent": discount_percent_tr,
                                    "discount_end": discount_end.strftime("%Y-%m-%d %H:%M:%S") if discount_end else None,
                                })
                                # Обновляем ps_plus и ps_plus_collection для TR региона
                                tr_record["ps_plus"] = 1 if ps_plus_collection_tr else tr_record["ps_plus"]
                                tr_record["ps_plus_collection"] = ps_plus_collection_tr
                                result.append(tr_record)

                            # 3. IN запись - только если IN в списке регионов
                            if "IN" in regions and (inr_price > 0 or ps_plus_collection_in or is_free_in):
                                discount_percent_in = 0
                                if inr_old_price and inr_old_price > inr_price > 0:
                                    discount_percent_in = round(((inr_old_price - inr_price) / inr_old_price) * 100)

                                price_rub_in = currency_converter.convert(inr_price, "INR", "RUB")
                                old_price_rub_in = currency_converter.convert(inr_old_price, "INR", "RUB") if inr_old_price else None
                                ps_plus_price_rub_in = currency_converter.convert(ps_price_in, "INR", "RUB") if ps_price_in else None

                                in_record = base_data.copy()
                                if in_name:
                                    in_record["name"] = in_name
                                    in_record["name_localized"] = in_name if in_name != main_name else None
                                in_record.update({
                                    "region": "IN",
                                    "localization": localization_in if localization_in else None,
                                    "price": price_rub_in,
                                    "old_price": old_price_rub_in,
                                    "ps_price": ps_plus_price_rub_in,
                                    "price_uah": 0.0,
                                    "old_price_uah": 0.0,
                                    "price_try": 0.0,
                                    "old_price_try": 0.0,
                                    "price_inr": inr_price,
                                    "old_price_inr": inr_old_price,
                                    "price_rub": price_rub_in,
                                    "price_rub_region": "IN",
                                    "ps_plus_price_uah": None,
                                    "ps_plus_price_try": None,
                                    "ps_plus_price_inr": ps_price_in,
                                    "discount": discount_percent_in,
                                    "discount_percent": discount_percent_in,
                                    "discount_end": discount_end.strftime("%Y-%m-%d %H:%M:%S") if discount_end else None,
                                })
                                # Обновляем ps_plus и ps_plus_collection для IN региона
                                in_record["ps_plus"] = 1 if ps_plus_collection_in else in_record["ps_plus"]
                                in_record["ps_plus_collection"] = ps_plus_collection_in
                                result.append(in_record)

                            if logger:
                                if "UA" in regions and uah_price <= 0 and not ps_plus_collection_ua and not is_free_ua and not is_unavailable_ua:
                                    logger.log_region_price_error(url, name, "UA", "UAH цена = 0 и нет PS Plus подписки")
                                if "TR" in regions and trl_price <= 0 and not ps_plus_collection_tr and not is_free_tr and not is_unavailable_tr:
                                    logger.log_region_price_error(url, name, "TR", "TRY цена = 0 и нет PS Plus подписки")
                                if "IN" in regions and inr_price <= 0 and not ps_plus_collection_in and not is_free_in and not is_unavailable_in:
                                    logger.log_region_price_error(url, name, "IN", "INR цена = 0 и нет PS Plus подписки")

                    # Обрабатываем издания с PS Plus без цены
                    if result:
                        result = process_ps_plus_only_editions(result)
                else:
                    # ua_price_product может быть dict (одиночный addon) или list (несколько)
                    if isinstance(ua_price_product, list):
                        if len(ua_price_product) == 0:
                            return []
                        ua_price_product = ua_price_product[0]
                    if not ua_price_product or not isinstance(ua_price_product, dict) or "id" not in ua_price_product:
                        if logger:
                            logger.log_product_error(url, "ua_price_product не содержит 'id' — пропускаем")
                        return []

                    tags = [main_name]
                    ID = ua_price_product["id"]
                    product, platforms, publisher, voice_languages, subtitles, description, ext_info, json, players_min, players_max, players_online = await get_ext_data(ID)

                    stars = 0.0
                    try:
                        star_rating_text = json["props"]["pageProps"]["batarangs"]["star-rating"]["text"]
                        star_matches = findall(r">([^<]+)</", star_rating_text)
                        if star_matches:
                            stars_json = loads(star_matches[0])
                            stars = stars_json["cache"][f"Product:{ID}"]["starRating"]["averageRating"]
                    except (KeyError, IndexError, ValueError, TypeError):
                        stars = 0.0

                    if not publisher:
                        if logger:
                            logger.log_product_error(url, f"Addon {ID} пропущен: нет publisher")
                        return result

                    category = [ua_price_product["skus"][0]["name"]]
                    name = ua_price_product["name"]
                    product_type = ua_price_product["skus"][0]["name"]  # "Виртуальные деньги" вместо жестко закодированного "Дополнение"
                    image = json["props"]["pageProps"]["batarangs"]["background-image"]["text"]
                    image = loads(findall(r">([^<]+)</", image)[0])
                    image = image["cache"][f"Product:{ID}"]["media"]
                    for img in image:
                        if img["role"] == "MASTER":
                            image = img["url"]
                            break
                    compound = ""

                    tags.append(name)

                    if name != ua_price_product["invariantName"]:
                        tags.append(ua_price_product["invariantName"])

                    # Собираем все уникальные названия из всех регионов для двуязычного поиска
                    all_region_names_addon = set()
                    all_region_names_addon.add(name)  # UA название
                    all_region_names_addon.add(main_name)  # Основное название
                    if ua_price_product["invariantName"]:
                        all_region_names_addon.add(ua_price_product["invariantName"])

                    tr_name = ""
                    in_name = ""

                    # Добавляем названия из TR региона (если парсили TR)
                    if "TR" in regions and tr_price_products:
                        # tr_price_products может быть списком или словарем
                        if isinstance(tr_price_products, dict):
                            tr_name = tr_price_products.get("name", "")
                            if tr_name:
                                all_region_names_addon.add(tr_name)
                            tr_invariant = tr_price_products.get("invariantName", "")
                            if tr_invariant and tr_invariant != tr_name:
                                all_region_names_addon.add(tr_invariant)
                        elif isinstance(tr_price_products, list):
                            for _trl in tr_price_products:
                                if _trl.get("id") == ID:
                                    tr_name = _trl.get("name", "")
                                    if tr_name:
                                        all_region_names_addon.add(tr_name)
                                    tr_invariant = _trl.get("invariantName", "")
                                    if tr_invariant and tr_invariant != tr_name:
                                        all_region_names_addon.add(tr_invariant)
                                    break

                    # Добавляем названия из IN региона (если парсили IN)
                    if "IN" in regions and in_price_products:
                        # in_price_products может быть списком или словарем
                        if isinstance(in_price_products, dict):
                            in_name = in_price_products.get("name", "")
                            if in_name:
                                all_region_names_addon.add(in_name)
                            in_invariant = in_price_products.get("invariantName", "")
                            if in_invariant and in_invariant != in_name:
                                all_region_names_addon.add(in_invariant)
                        elif isinstance(in_price_products, list):
                            for _inp in in_price_products:
                                if _inp.get("id") == ID:
                                    in_name = _inp.get("name", "")
                                    if in_name:
                                        all_region_names_addon.add(in_name)
                                    in_invariant = _inp.get("invariantName", "")
                                    if in_invariant and in_invariant != in_name:
                                        all_region_names_addon.add(in_invariant)
                                    break

                    # Обновляем теги всеми названиями из всех регионов
                    tags = list(all_region_names_addon)

                    uah_price = 0
                    uah_old_price = 0
                    discount = ""
                    discount_end = None
                    trl_price = 0
                    trl_old_price = 0
                    inr_price = 0
                    inr_old_price = 0

                    ps_plus = False
                    ea_access = False
                    ps_plus_collection_ua = None
                    ps_plus_collection_tr = None
                    ps_plus_collection_in = None

                    ps_price_ua = None
                    ea_price_ua = None
                    ps_price_tr = None
                    ea_price_tr = None
                    ps_price_in = None
                    ea_price_in = None

                    if ua_price_product.get("webctas"):
                        for price in ua_price_product["webctas"]:
                            if price["type"] in _PURCHASE_CTA_TYPES or ("UPSELL" in price["type"] and ("EA_ACCESS" in price["type"] or "PS_PLUS" in price["type"]) and "TRIAL" not in price["type"]):
                                if price["type"] == "PREORDER":
                                    product_type = "Предзаказ"
                                if price["price"]["discountedPrice"] and price["type"] in _PURCHASE_CTA_TYPES and not uah_price:
                                    uah_price = parse_price_value(price["price"].get("discountedValue", 0))
                                if price["price"]["basePrice"] and price["type"] in _PURCHASE_CTA_TYPES and not uah_old_price:
                                    uah_old_price = parse_price_value(price["price"].get("basePriceValue", 0))
                                if "PS_PLUS" in price["type"] and price["price"]["discountedPrice"] == "Входит в подписку":
                                    ps_plus = True
                                    cta_type_from_text = detect_ps_plus_type_from_cta_text(price)
                                    if cta_type_from_text:
                                        ps_plus_collection_ua = cta_type_from_text
                                    else:
                                        if price["type"] == "UPSELL_PS_PLUS_GAME_CATALOG":
                                            ps_plus_collection_ua = "Deluxe/Extra"
                                        elif price["type"] == "UPSELL_PS_PLUS_FREE":
                                            ps_plus_collection_ua = "Essential"
                                        elif price["type"] == "UPSELL_PS_PLUS_CLASSICS_CATALOG":
                                            ps_plus_collection_ua = "Deluxe/Premium"
                                if "EA_ACCESS" in price["type"] and price["price"]["discountedPrice"] == "Входит в подписку":
                                    ea_access = True
                                if "UPSELL_PS_PLUS_DISCOUNT" == price["type"]:
                                    ps_price_ua = parse_price_value(price["price"].get("discountedValue", 0))
                                if "UPSELL_EA_ACCESS_DISCOUNT" == price["type"]:
                                    ea_price_ua = parse_price_value(price["price"].get("discountedValue", 0))
                                if price["price"]["discountText"] and price["type"] in _PURCHASE_CTA_TYPES:
                                    discount = price["price"]["discountText"]
                                if price["price"]["endTime"] and price["type"] in _PURCHASE_CTA_TYPES:
                                    discount_end = datetime.fromtimestamp(int(price["price"]["endTime"])//1000)

                    if tr_price_products and isinstance(tr_price_products, list) and len(tr_price_products) > 0:
                        matched_tr = None
                        for _trl in tr_price_products:
                            if isinstance(_trl, dict) and _trl.get("id") == ID and _trl.get("webctas"):
                                matched_tr = _trl
                                break
                        if not matched_tr and isinstance(tr_price_products[0], dict):
                            matched_tr = tr_price_products[0]
                        tr_price_products = matched_tr if matched_tr else {}
                    elif not tr_price_products or (isinstance(tr_price_products, list) and len(tr_price_products) == 0):
                        tr_price = await get_tr_data(session, tr_url, params_price)
                        if tr_price and tr_price.get("data", {}).get("productRetrieve"):
                            tr_price_products = tr_price["data"]["productRetrieve"]
                        else:
                            tr_price_products = {}


                    if isinstance(tr_price_products, dict) and tr_price_products.get("id") == ID and tr_price_products.get("webctas"):
                        for trl in tr_price_products["webctas"]:
                            if trl["type"] in _PURCHASE_CTA_TYPES or ("UPSELL" in trl["type"] and ("EA_ACCESS" in trl["type"] or "PS_PLUS" in trl["type"]) and "TRIAL" not in trl["type"]):
                                if trl["price"]["discountedPrice"] and trl["type"] in _PURCHASE_CTA_TYPES and not trl_price:
                                    trl_price = parse_price_value(trl["price"].get("discountedValue", 0))
                                if trl["price"]["basePrice"] and trl["type"] in _PURCHASE_CTA_TYPES and not trl_old_price:
                                    trl_old_price = parse_price_value(trl["price"].get("basePriceValue", 0))
                                if "PS_PLUS" in trl["type"] and trl["price"]["discountedPrice"] == "Included":
                                    ps_plus = True
                                    cta_type_from_text = detect_ps_plus_type_from_cta_text(trl)
                                    if cta_type_from_text:
                                        ps_plus_collection_tr = cta_type_from_text
                                    else:
                                        if trl["type"] == "UPSELL_PS_PLUS_GAME_CATALOG":
                                            ps_plus_collection_tr = "Deluxe/Extra"
                                        elif trl["type"] == "UPSELL_PS_PLUS_FREE":
                                            ps_plus_collection_tr = "Essential"
                                        elif trl["type"] == "UPSELL_PS_PLUS_CLASSICS_CATALOG":
                                            ps_plus_collection_tr = "Deluxe/Premium"
                                if "EA_ACCESS" in trl["type"] and trl["price"]["discountedPrice"] == "Included":
                                    ea_access = True
                                if "UPSELL_PS_PLUS_DISCOUNT" == trl["type"]:
                                    ps_price_tr = parse_price_value(trl["price"].get("discountedValue", 0))
                                if "UPSELL_EA_ACCESS_DISCOUNT" == trl["type"]:
                                    ea_price_tr = parse_price_value(trl["price"].get("discountedValue", 0))

                    # IN price extraction for addons
                    if "IN" in regions and in_price_products:
                        matched_in = None
                        if isinstance(in_price_products, list) and len(in_price_products) > 0:
                            for _inp in in_price_products:
                                if isinstance(_inp, dict) and _inp.get("id") == ID and _inp.get("webctas"):
                                    matched_in = _inp
                                    break
                            if not matched_in and isinstance(in_price_products[0], dict):
                                matched_in = in_price_products[0]
                        elif isinstance(in_price_products, dict) and in_price_products.get("webctas"):
                            matched_in = in_price_products

                        if matched_in and matched_in.get("webctas"):
                            for inp in matched_in["webctas"]:
                                if inp["type"] in _PURCHASE_CTA_TYPES or ("UPSELL" in inp["type"] and ("EA_ACCESS" in inp["type"] or "PS_PLUS" in inp["type"]) and "TRIAL" not in inp["type"]):
                                    if inp["price"]["discountedPrice"] and inp["type"] in _PURCHASE_CTA_TYPES and not inr_price:
                                        inr_price = parse_price_value(inp["price"].get("discountedValue", 0), divide_by_100=False)
                                    if inp["price"]["basePrice"] and inp["type"] in _PURCHASE_CTA_TYPES and not inr_old_price:
                                        inr_old_price = parse_price_value(inp["price"].get("basePriceValue", 0), divide_by_100=False)
                                    if "PS_PLUS" in inp["type"] and inp["price"]["discountedPrice"] == "Included":
                                        ps_plus = True
                                        cta_type_from_text = detect_ps_plus_type_from_cta_text(inp)
                                        if cta_type_from_text:
                                            ps_plus_collection_in = cta_type_from_text
                                        else:
                                            if inp["type"] == "UPSELL_PS_PLUS_GAME_CATALOG":
                                                ps_plus_collection_in = "Deluxe/Extra"
                                            elif inp["type"] == "UPSELL_PS_PLUS_FREE":
                                                ps_plus_collection_in = "Essential"
                                            elif inp["type"] == "UPSELL_PS_PLUS_CLASSICS_CATALOG":
                                                ps_plus_collection_in = "Deluxe/Premium"
                                    if "EA_ACCESS" in inp["type"] and inp["price"]["discountedPrice"] == "Included":
                                        ea_access = True
                                    if "UPSELL_PS_PLUS_DISCOUNT" == inp["type"]:
                                        ps_price_in = parse_price_value(inp["price"].get("discountedValue", 0), divide_by_100=False)
                                    if "UPSELL_EA_ACCESS_DISCOUNT" == inp["type"]:
                                        ea_price_in = parse_price_value(inp["price"].get("discountedValue", 0), divide_by_100=False)

                    edition = ua_price_product.get("skus", [{}])[0].get("name", "")

                    # Получаем локализации для TR и IN регионов только если они запрошены
                    voice_languages_tr, subtitles_tr = None, None
                    voice_languages_in, subtitles_in = None, None

                    if "TR" in regions:
                        voice_languages_tr, subtitles_tr = await get_localization_for_region(session, ID, "en-tr")
                    if "IN" in regions:
                        voice_languages_in, subtitles_in = await get_localization_for_region(session, ID, "en-in")

                    # Функция для определения кода локализации (та же что и для обычных продуктов)
                    def get_localization_code_addon(voice_langs: str, subs: str) -> str:
                        """
                        Логика:
                        - Если в Voice есть Russian → "full"
                        - Иначе если в Screen Languages есть Russian → "subtitles"
                        - Иначе → "none"

                        Примечание:
                            Пустые строки ("", "") означают что данные получены, но языков нет = "none"
                        """
                        has_russian_voice = voice_langs and ("русский" in voice_langs.lower() or "russian" in voice_langs.lower())
                        has_russian_subs = subs and ("русский" in subs.lower() or "russian" in subs.lower())

                        if has_russian_voice:
                            return "full"  # Полностью на русском
                        elif has_russian_subs:
                            return "subtitles"  # Только русские субтитры
                        else:
                            return "none"  # Нет русского языка (или пустые строки)

                    # Определяем локализацию для каждого региона
                    localization_code = get_localization_code_addon(voice_languages, subtitles)
                    localization_tr = get_localization_code_addon(voice_languages_tr, subtitles_tr) if (voice_languages_tr is not None and subtitles_tr is not None) else None
                    localization_in = get_localization_code_addon(voice_languages_in, subtitles_in) if (voice_languages_in is not None and subtitles_in is not None) else None

                    if not uah_price:
                        uah_price = uah_old_price
                    if not trl_price:
                        trl_price = trl_old_price
                    if not inr_price:
                        inr_price = inr_old_price

                    # Нормализуем тип продукта
                    product_type = EditionTypeNormalizer.normalize_type(product_type)

                    for t in range(len(tags)):
                        for c in ['tm', 'TM', '®', '©', '℗', '℠', 'R', "’"]:
                            to_replace = ""
                            if c == "’":
                                to_replace = "'"
                            tags[t] = tags[t].replace(c, to_replace)

                    # Создаем отдельные записи для каждого региона (addon)
                    # Базовые данные
                    base_data = {
                        "id": ID,
                        "category": category,
                        "type": product_type,
                        "name": name,
                        "main_name": main_name,
                        "name_localized": name if name != main_name else None,
                        "search_names": ",".join(set(tags)),
                        "image": image,
                        "compound": compound,
                        "platforms": ",".join(platforms) if platforms else None,
                        "publisher": publisher,
                        "rating": stars,
                        "info": ext_info,
                        "ps_plus": 1 if ps_plus else 0,
                        "ps_plus_collection": None,
                        "ea_access": 1 if ea_access else 0,
                        "tags": ",".join(set(tags)),
                        "edition": edition,
                        "description": description,
                        "players_min": players_min,
                        "players_max": players_max,
                        "players_online": 1 if players_online else 0,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    _ua_addon_webctas = ua_price_product.get("webctas", [])
                    is_free_addon_ua = any(
                        p["type"] in _PURCHASE_CTA_TYPES and is_free_price_text(p["price"].get("discountedPrice", ""))
                        for p in _ua_addon_webctas
                    )
                    is_unavailable_addon_ua = bool(_ua_addon_webctas) and all(p.get("type") == "UNAVAILABLE" for p in _ua_addon_webctas)

                    is_free_addon_tr = False
                    is_unavailable_addon_tr = False
                    if isinstance(tr_price_products, dict) and tr_price_products.get("webctas"):
                        _tr_addon_webctas = tr_price_products.get("webctas", [])
                        is_free_addon_tr = any(
                            p["type"] in _PURCHASE_CTA_TYPES and is_free_price_text(p["price"].get("discountedPrice", ""))
                            for p in _tr_addon_webctas
                        )
                        is_unavailable_addon_tr = bool(_tr_addon_webctas) and all(p.get("type") == "UNAVAILABLE" for p in _tr_addon_webctas)

                    is_free_addon_in = False
                    is_unavailable_addon_in = False
                    if isinstance(in_price_products, (dict, list)):
                        _in_webctas = []
                        if isinstance(in_price_products, dict):
                            _in_webctas = in_price_products.get("webctas", [])
                        elif isinstance(in_price_products, list) and len(in_price_products) > 0 and isinstance(in_price_products[0], dict):
                            _in_webctas = in_price_products[0].get("webctas", [])
                        is_free_addon_in = any(
                            p["type"] in _PURCHASE_CTA_TYPES and is_free_price_text(p["price"].get("discountedPrice", ""))
                            for p in _in_webctas
                        )
                        is_unavailable_addon_in = bool(_in_webctas) and all(p.get("type") == "UNAVAILABLE" for p in _in_webctas)

                    # UA запись - только если UA в списке регионов
                    if "UA" in regions and (uah_price > 0 or ps_plus_collection_ua or is_free_addon_ua):
                        discount_percent_ua = 0
                        if uah_old_price and uah_old_price > uah_price > 0:
                            discount_percent_ua = round(((uah_old_price - uah_price) / uah_old_price) * 100)

                        price_rub_ua = currency_converter.convert(uah_price, "UAH", "RUB")
                        old_price_rub_ua = currency_converter.convert(uah_old_price, "UAH", "RUB") if uah_old_price else None
                        ps_plus_price_rub_ua = currency_converter.convert(ps_price_ua, "UAH", "RUB") if ps_price_ua else None

                        ua_record = base_data.copy()
                        ua_record.update({
                            "region": "UA",
                            "localization": localization_code,
                            "price": price_rub_ua,
                            "old_price": old_price_rub_ua,
                            "ps_price": ps_plus_price_rub_ua,
                            "price_uah": uah_price,
                            "old_price_uah": uah_old_price,
                            "price_try": 0.0,
                            "old_price_try": 0.0,
                            "price_inr": 0.0,
                            "old_price_inr": 0.0,
                            "price_rub": price_rub_ua,
                            "price_rub_region": "UA",
                            "ps_plus_price_uah": ps_price_ua,
                            "ps_plus_price_try": None,
                            "ps_plus_price_inr": None,
                            "discount": discount_percent_ua,
                            "discount_percent": discount_percent_ua,
                            "discount_end": discount_end.strftime("%Y-%m-%d %H:%M:%S") if discount_end else None,
                        })
                        ua_record["ps_plus"] = 1 if ps_plus_collection_ua else ua_record["ps_plus"]
                        ua_record["ps_plus_collection"] = ps_plus_collection_ua
                        result.append(ua_record)

                    # TR запись - только если TR в списке регионов
                    if "TR" in regions and (trl_price > 0 or ps_plus_collection_tr or is_free_addon_tr):
                        discount_percent_tr = 0
                        if trl_old_price and trl_old_price > trl_price > 0:
                            discount_percent_tr = round(((trl_old_price - trl_price) / trl_old_price) * 100)

                        price_rub_tr = currency_converter.convert(trl_price, "TRY", "RUB")
                        old_price_rub_tr = currency_converter.convert(trl_old_price, "TRY", "RUB") if trl_old_price else None
                        ps_plus_price_rub_tr = currency_converter.convert(ps_price_tr, "TRY", "RUB") if ps_price_tr else None

                        tr_record = base_data.copy()
                        if tr_name:
                            tr_record["name"] = tr_name
                            tr_record["name_localized"] = tr_name if tr_name != main_name else None
                        tr_record.update({
                            "region": "TR",
                            "localization": localization_tr if localization_tr else None,
                            "price": price_rub_tr,
                            "old_price": old_price_rub_tr,
                            "ps_price": ps_plus_price_rub_tr,
                            "price_uah": 0.0,
                            "old_price_uah": 0.0,
                            "price_try": trl_price,
                            "old_price_try": trl_old_price,
                            "price_inr": 0.0,
                            "old_price_inr": 0.0,
                            "price_rub": price_rub_tr,
                            "price_rub_region": "TR",
                            "ps_plus_price_uah": None,
                            "ps_plus_price_try": ps_price_tr,
                            "ps_plus_price_inr": None,
                            "discount": discount_percent_tr,
                            "discount_percent": discount_percent_tr,
                            "discount_end": discount_end.strftime("%Y-%m-%d %H:%M:%S") if discount_end else None,
                        })
                        tr_record["ps_plus"] = 1 if ps_plus_collection_tr else tr_record["ps_plus"]
                        tr_record["ps_plus_collection"] = ps_plus_collection_tr
                        result.append(tr_record)

                    # IN запись - только если IN в списке регионов
                    if "IN" in regions and (inr_price > 0 or ps_plus_collection_in or is_free_addon_in):
                        discount_percent_in = 0
                        if inr_old_price and inr_old_price > inr_price > 0:
                            discount_percent_in = round(((inr_old_price - inr_price) / inr_old_price) * 100)

                        price_rub_in = currency_converter.convert(inr_price, "INR", "RUB")
                        old_price_rub_in = currency_converter.convert(inr_old_price, "INR", "RUB") if inr_old_price else None
                        ps_plus_price_rub_in = currency_converter.convert(ps_price_in, "INR", "RUB") if ps_price_in else None

                        in_record = base_data.copy()
                        if in_name:
                            in_record["name"] = in_name
                            in_record["name_localized"] = in_name if in_name != main_name else None
                        in_record.update({
                            "region": "IN",
                            "localization": localization_in if localization_in else None,
                            "price": price_rub_in,
                            "old_price": old_price_rub_in,
                            "ps_price": ps_plus_price_rub_in,
                            "price_uah": 0.0,
                            "old_price_uah": 0.0,
                            "price_try": 0.0,
                            "old_price_try": 0.0,
                            "price_inr": inr_price,
                            "old_price_inr": inr_old_price,
                            "price_rub": price_rub_in,
                            "price_rub_region": "IN",
                            "ps_plus_price_uah": None,
                            "ps_plus_price_try": None,
                            "ps_plus_price_inr": ps_price_in,
                            "discount": discount_percent_in,
                            "discount_percent": discount_percent_in,
                            "discount_end": discount_end.strftime("%Y-%m-%d %H:%M:%S") if discount_end else None,
                        })
                        in_record["ps_plus"] = 1 if ps_plus_collection_in else in_record["ps_plus"]
                        in_record["ps_plus_collection"] = ps_plus_collection_in
                        result.append(in_record)

                    if logger:
                        if "UA" in regions and uah_price <= 0 and not ps_plus_collection_ua and not is_free_addon_ua and not is_unavailable_addon_ua:
                            logger.log_region_price_error(url, name, "UA", "UAH цена = 0 (addon)")
                        if "TR" in regions and trl_price <= 0 and not ps_plus_collection_tr and not is_free_addon_tr and not is_unavailable_addon_tr:
                            logger.log_region_price_error(url, name, "TR", "TRY цена = 0 (addon)")
                        if "IN" in regions and inr_price <= 0 and not ps_plus_collection_in and not is_free_addon_in and not is_unavailable_addon_in:
                            logger.log_region_price_error(url, name, "IN", "INR цена = 0 (addon)")

                # Обрабатываем издания с PS Plus без цены
                if result:
                    result = process_ps_plus_only_editions(result)

                return result

            except (asyncio.CancelledError, KeyboardInterrupt):
                return []

        except (asyncio.CancelledError, KeyboardInterrupt):
                return []

        except Exception as _exc:
            if logger:
                logger.log_parse_exception(url, _exc)
            counter += 1
            backoff = min(5 * (2 ** (counter - 1)), 60)
            await asyncio.sleep(backoff)
    else:
        if logger:
            logger.log_product_error(url, f"Все {counter} попыток исчерпаны, товар пропущен")
        return []


async def parse_tr(session: aiohttp.ClientSession, url: str):
    """
    Парсит товар из TR региона (специально для режима 4)
    Возвращает товары только с TR ценами (trl_price) из API, БЕЗ HTML парсинга

    Для матчинга с UA используется: name + edition
    Все остальные данные (platforms, publisher, description, etc) берутся из UA

    Args:
        session: aiohttp сессия
        url: TR URL (https://store.playstation.com/en-tr/product/...)

    Returns:
        List[Dict]: Список товаров с TR ценами (минимальные данные для матчинга)
    """

    # Проверяем что это TR URL
    if "/en-tr/" not in url:
        print(f"parse_tr() ожидает en-tr URL, получен: {url}")
        return []

    params_price, _ = get_params(url)  # Нам нужен только params_price для цен

    counter = 0

    while counter < 2:
        try:
            # Получаем TR данные с ценами (один запрос)
            print(f"   Запрос TR данных (попытка {counter + 1}/2)...")
            async with session.get("https://web.np.playstation.com/api/graphql/v1/op", params=params_price, headers=json_headers(url)) as tr_resp:
                tr_text = await tr_resp.text()

            # Проверяем на блокировку Cloudflare
            if "You don't have permission to access" in tr_text:
                print(f"   Обнаружена блокировка Cloudflare")
                await access_controller.wait_for_access(session)
                counter = 0
                continue

            # Парсим JSON
            try:
                tr_data = loads(tr_text)
            except Exception as e:
                print(f"   Ошибка парсинга TR JSON: {type(e).__name__}")
                print(f"   Первые 200 символов: {tr_text[:200]}")
                counter += 1
                await asyncio.sleep(5)
                continue

            if "errors" in tr_data:
                print(f"   Ошибки в TR ответе: {tr_data.get('errors', [])}")
                counter += 1
                await asyncio.sleep(5)
                continue

            print(f"   TR данные получены")

            # Получаем данные из ответа
            product_retrieve = tr_data.get("data", {}).get("productRetrieve", {})
            if not product_retrieve:
                print(f"   Пустой productRetrieve")
                counter += 1
                await asyncio.sleep(5)
                continue

            # Проверяем есть ли concept с изданиями
            has_concept = False
            products_list = []
            main_name = ""
            concept_id = None

            if "concept" in product_retrieve and product_retrieve["concept"]:
                concept = product_retrieve["concept"]
                concept_id = concept.get("id")
                main_name = concept.get("name", "")

                # Проверяем есть ли products в concept
                if "products" in concept and concept["products"]:
                    has_concept = True
                    products_list = concept["products"]
                    print(f"   Тип: concept с products ({len(products_list)} изданий)")
                elif concept_id:
                    # Concept есть, но products нет - нужен доп. запрос
                    print(f"   Concept найден (id={concept_id}), получаем все издания...")

                    # Создаем URL для concept
                    tr_parts = url.split("/")
                    concept_url = "/".join(tr_parts[:4]) + f"/concept/{concept_id}"
                    concept_params_price = get_params(concept_url)  # Для concept возвращается словарь, не кортеж

                    # Запрашиваем данные concept
                    try:
                        async with session.get(
                            "https://web.np.playstation.com/api/graphql/v1/op",
                            params=concept_params_price,
                            headers=json_headers(concept_url)
                        ) as concept_resp:
                            concept_text = await concept_resp.text()

                        concept_data = loads(concept_text)
                        concept_retrieve = concept_data.get("data", {}).get("conceptRetrieve", {})

                        if concept_retrieve and "products" in concept_retrieve:
                            products_list = concept_retrieve["products"]
                            has_concept = True
                            if not main_name:
                                main_name = concept_retrieve.get("name", "")
                            print(f"   Получено {len(products_list)} изданий из concept")
                        else:
                            print(f"     Не удалось получить products из concept")
                    except Exception as e:
                        print(f"     Ошибка запроса concept: {type(e).__name__}")

            # Если concept пустой или нет products - берем сам product
            if not has_concept:
                products_list = [product_retrieve]
                if not main_name:
                    main_name = product_retrieve.get("name", "")
                print(f"    Тип: одиночный продукт (fallback)")

            # Fallback для main_name - берем invariantName из первого продукта
            if not main_name and products_list:
                # invariantName = базовое название без edition (например "Assassin's Creed Shadows")
                main_name = products_list[0].get("invariantName", "") or products_list[0].get("name", "")
                if main_name:
                    print(f"     main_name взят из первого продукта (invariantName): {main_name}")

            if not main_name:
                print(f"     Не удалось получить main_name даже из продуктов")
                counter += 1
                await asyncio.sleep(5)
                continue

            result = []

            # Обрабатываем каждый продукт
            for product in products_list:
                try:
                    # Базовые данные из API
                    product_id = product.get("id", "")
                    name = product.get("name", "")

                    if not product_id or not name:
                        print(f"     Пропуск продукта без ID или имени")
                        continue

                    # Если продукт из concept, у него может не быть webctas с ценами
                    # Делаем дополнительный запрос для получения полной информации
                    if not product.get("webctas"):
                        print(f"   Получаю цены для: {name}")
                        tr_parts = url.split("/")
                        product_url = "/".join(tr_parts[:4]) + f"/product/{product_id}"
                        product_params_price, _ = get_params(product_url)

                        try:
                            async with session.get(
                                "https://web.np.playstation.com/api/graphql/v1/op",
                                params=product_params_price,
                                headers=json_headers(product_url)
                            ) as product_resp:
                                product_text = await product_resp.text()

                            product_data = loads(product_text)
                            product_retrieve = product_data.get("data", {}).get("productRetrieve", {})

                            if product_retrieve and product_retrieve.get("webctas"):
                                # Обновляем product данными с ценами
                                product["webctas"] = product_retrieve["webctas"]
                                print(f"       Цены получены ({len(product_retrieve['webctas'])} CTA)")
                            else:
                                print(f"        Цены не найдены")
                        except Exception as e:
                            print(f"        Ошибка получения цен: {type(e).__name__}")

                        # Небольшая задержка между запросами
                        await asyncio.sleep(0.5)

                    # Edition
                    edition_data = product.get("edition")
                    edition_name = ""
                    compound = ""

                    if edition_data:
                        if edition_data.get("features"):
                            compound = dumps(edition_data["features"])
                        edition_name = edition_data.get("name", "")
                        if not edition_name:
                            edition_name = name

                    # Category
                    category = []
                    if product.get("localizedGenres"):
                        category = list(set(i["value"] for i in product["localizedGenres"]))

                    # Product type
                    product_type = "Игра"
                    if "Subscription" in name:
                        product_type = "Подписка"
                    elif product.get("skus") and len(product["skus"]) > 0:
                        sku_name = product["skus"][0].get("name", "")
                        if sku_name.lower() not in ["demo", "демоверсия", "полная ознакомительная версия игры"]:
                            product_type = sku_name
                        elif len(product["skus"]) > 1:
                            product_type = product["skus"][1].get("name", "Игра")

                    product_type = EditionTypeNormalizer.normalize_type(product_type)

                    # Image из API
                    image = ""
                    if product.get("media"):
                        for img in product["media"]:
                            if img.get("role") == "MASTER":
                                image = img.get("url", "")
                                break

                    # Tags - собираем все уникальные названия для двуязычного поиска
                    tags = [main_name, name]
                    invariant_name = product.get("invariantName", "")
                    if invariant_name and invariant_name != name:
                        tags.append(invariant_name)

                    # Удаляем дубликаты и пустые строки
                    tags = list(set([t for t in tags if t]))

                    # Цены из webctas
                    trl_price = 0
                    trl_old_price = 0
                    ps_price_tr = None
                    ea_price_tr = None
                    discount = ""
                    discount_end = None
                    ps_plus = False
                    ea_access = False
                    ps_plus_collection = None  # Определяется по CTA типу

                    webctas = product.get("webctas", [])
                    for cta in webctas:
                        cta_type = cta.get("type", "")
                        price_data = cta.get("price", {})

                        # Обновляем product_type если предзаказ
                        if cta_type == "PREORDER":
                            product_type = "Предзаказ"

                        # Основная цена
                        if cta_type in _PURCHASE_CTA_TYPES:
                            if price_data.get("discountedPrice") and not trl_price:
                                trl_price = price_data.get("discountedValue", 0) / 100
                            if price_data.get("basePrice") and not trl_old_price:
                                trl_old_price = price_data.get("basePriceValue", 0) / 100
                            if price_data.get("discountText"):
                                discount = price_data["discountText"]
                            if price_data.get("endTime"):
                                discount_end = datetime.fromtimestamp(int(price_data["endTime"]) // 1000)

                        # PS Plus цены
                        elif "PS_PLUS" in cta_type:
                            if price_data.get("discountedPrice") == "Included":
                                ps_plus = True
                                # Сначала проверяем текст CTA на наличие явного указания типа подписки
                                cta_type_from_text = detect_ps_plus_type_from_cta_text(cta)
                                
                                if cta_type_from_text:
                                    # Если найдено явное указание в тексте (Extra или Deluxe), используем его
                                    ps_plus_collection = cta_type_from_text
                                else:
                                    # Если в тексте нет явного указания, используем определение по типу CTA
                                    if cta_type == "UPSELL_PS_PLUS_GAME_CATALOG":
                                        ps_plus_collection = "Deluxe/Extra"
                                    elif cta_type == "UPSELL_PS_PLUS_FREE":
                                        ps_plus_collection = "Essential"
                                    elif cta_type == "UPSELL_PS_PLUS_CLASSICS_CATALOG":
                                        ps_plus_collection = "Deluxe/Premium"
                                    elif cta_type == "UPSELL_PS_PLUS_CLASSIC_GAME_COLLECTION":
                                        ps_plus_collection = "Deluxe/Premium"
                            elif cta_type == "UPSELL_PS_PLUS_DISCOUNT" and price_data.get("discountedValue"):
                                ps_price_tr = price_data["discountedValue"] / 100

                        # EA Access цены
                        elif "EA_ACCESS" in cta_type:
                            if price_data.get("discountedPrice") == "Included":
                                ea_access = True
                            elif cta_type == "UPSELL_EA_ACCESS_DISCOUNT" and price_data.get("discountedValue"):
                                ea_price_tr = price_data["discountedValue"] / 100

                    # Используем old_price если нет дисконта
                    if not trl_price:
                        trl_price = trl_old_price

                    # Очистка тегов от символов
                    cleaned_tags = []
                    for tag in tags:
                        for c in ['™', '®', '©', '℗', '℠', "'"]:
                            tag = tag.replace(c, "'" if c == "'" else "")
                        cleaned_tags.append(tag)

                    # Вычисляем процент скидки
                    discount_percent = 0
                    if trl_old_price and trl_old_price > trl_price > 0:
                        discount_percent = round(((trl_old_price - trl_price) / trl_old_price) * 100)

                    # Конвертируем TR цены в рубли
                    price_rub_tr = currency_converter.convert(trl_price, "TRY", "RUB")
                    ps_plus_price_rub_tr = currency_converter.convert(ps_price_tr, "TRY", "RUB") if ps_price_tr else None

                    # Парсим локализацию для TR региона
                    def get_localization_code(voice_langs: str, subs: str) -> str:
                        """
                        Определяет код локализации на основе языков озвучки и субтитров

                        Логика:
                        - Если в Voice есть Russian → "full" (полностью на русском)
                        - Иначе если в Screen Languages есть Russian → "subtitles" (русские субтитры)
                        - Иначе → "none" (нет русского)

                        Returns:
                            "full" - полностью на русском (есть озвучка)
                            "subtitles" - только русские субтитры
                            "none" - нет русского языка
                        """
                        has_russian_voice = voice_langs and ("русский" in voice_langs.lower() or "russian" in voice_langs.lower())
                        has_russian_subs = subs and ("русский" in subs.lower() or "russian" in subs.lower())

                        if has_russian_voice:
                            return "full"
                        elif has_russian_subs:
                            return "subtitles"
                        else:
                            return "none"

                    # Получаем локализацию для TR региона
                    print(f"   Парсинг локализации для {name}...")
                    voice_languages_tr, subtitles_tr = await get_localization_for_region(session, product_id, "en-tr")
                    localization_tr = get_localization_code(voice_languages_tr, subtitles_tr) if (voice_languages_tr is not None and subtitles_tr is not None) else None

                    if localization_tr:
                        print(f"       Локализация TR: {localization_tr}")

                    # Добавляем только если есть цена ИЛИ PS Plus подписка
                    if trl_price > 0 or ps_plus_collection:
                        if trl_price > 0:
                            print(f"    Добавлен: {name} ({edition_name or 'базовая'}) - TRY {trl_price} (RUB {price_rub_tr})")
                        else:
                            print(f"    Добавлен: {name} ({edition_name or 'базовая'}) - PS Plus ({ps_plus_collection}), нет цены")
                        result.append({
                            "id": product_id,
                            "category": category,
                            "region": "TR",
                            "type": product_type,
                            "name": name,
                            "main_name": main_name,
                            "name_localized": None,  # Берется из UA
                            "search_names": ",".join(set(cleaned_tags)),
                            "image": image,
                            "compound": compound,
                            "platforms": None,  # Берется из UA
                            "publisher": None,  # Берется из UA
                            "localization": localization_tr,  # Парсится из TR
                            "rating": 0.0,  # Берется из UA
                            "info": None,  # Берется из UA
                            "price_uah": 0.0,  # Только TR цены
                            "old_price_uah": 0.0,
                            "price_try": trl_price,
                            "old_price_try": trl_old_price,
                            "price_inr": 0.0,
                            "old_price_inr": 0.0,
                            "price_rub": price_rub_tr,  # TR цена в рублях
                            "price_rub_region": "TR",
                            "ps_plus_price_uah": None,
                            "ps_plus_price_try": ps_price_tr,
                            "ps_plus_price_inr": None,
                            "ps_plus_price_rub": ps_plus_price_rub_tr,
                            "ps_plus": 1 if ps_plus else 0,
                            "ps_plus_collection": ps_plus_collection,
                            "ea_access": 1 if ea_access else 0,
                            "discount": discount_percent,
                            "discount_percent": discount_percent,
                            "discount_end": discount_end.strftime("%Y-%m-%d %H:%M:%S") if discount_end else None,
                            "tags": ",".join(set(cleaned_tags)),
                            "edition": edition_name,
                            "description": None,  # Берется из UA
                            "players_min": None,  # Берется из UA
                            "players_max": None,  # Берется из UA
                            "players_online": 0,  # Берется из UA
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                    else:
                        print(f"     Пропуск: {name} ({edition_name or 'базовая'}) - нет цены и нет PS Plus")

                except Exception as e:
                    print(f"     Ошибка обработки продукта: {type(e).__name__}: {str(e)}")
                    continue

            # Итого
            print(f"    Обработано: {len(result)} товаров с TR ценами (включая PS Plus без цены)")

            # Обрабатываем издания с PS Plus без цены
            if result:
                result = process_ps_plus_only_editions(result)

            return result

        except (asyncio.CancelledError, KeyboardInterrupt):
            return []

        except (asyncio.CancelledError, KeyboardInterrupt):
            return []

        except Exception as e:
            print(f"     Ошибка парсинга TR (попытка {counter + 1}/2): {type(e).__name__}: {str(e)}")
            counter += 1
            await asyncio.sleep(5)
    else:
        print(f"    Исчерпаны попытки парсинга TR")
        return []


async def parse_in(session: aiohttp.ClientSession, url: str):
    """
    Парсит товар из IN региона (специально для режима 4)
    Возвращает товары только с IN ценами из API, БЕЗ HTML парсинга

    Для матчинга с UA используется: name + edition
    Все остальные данные (platforms, publisher, description, etc) берутся из UA

    Args:
        session: aiohttp сессия
        url: IN URL (https://store.playstation.com/en-in/product/...)

    Returns:
        List[Dict]: Список товаров с IN ценами (минимальные данные для матчинга)
    """

    # Проверяем что это IN URL
    if "/en-in/" not in url:
        print(f"parse_in() ожидает en-in URL, получен: {url}")
        return []

    params_price, _ = get_params(url)
    counter = 0

    while counter < 2:
        try:
            # Получаем IN данные с ценами
            print(f"   Запрос IN данных (попытка {counter + 1}/2)...")
            async with session.get("https://web.np.playstation.com/api/graphql/v1/op", params=params_price, headers=json_headers(url)) as in_resp:
                in_text = await in_resp.text()

            # Проверяем на блокировку
            if "You don't have permission to access" in in_text:
                print(f"   Обнаружена блокировка Cloudflare")
                await access_controller.wait_for_access(session)
                counter = 0
                continue

            # Парсим JSON
            try:
                in_data = loads(in_text)
            except Exception as e:
                print(f"   Ошибка парсинга IN JSON: {type(e).__name__}")
                counter += 1
                await asyncio.sleep(5)
                continue

            if "errors" in in_data:
                print(f"   Ошибки в IN ответе: {in_data.get('errors', [])}")
                counter += 1
                await asyncio.sleep(5)
                continue

            print(f"   IN данные получены")

            # Получаем данные из ответа
            product_retrieve = in_data.get("data", {}).get("productRetrieve", {})
            if not product_retrieve:
                print(f"   Пустой productRetrieve")
                counter += 1
                await asyncio.sleep(5)
                continue

            # Обработка concept/products аналогично parse_tr()
            has_concept = False
            products_list = []
            main_name = ""
            concept_id = None

            if "concept" in product_retrieve and product_retrieve["concept"]:
                concept = product_retrieve["concept"]
                concept_id = concept.get("id")
                main_name = concept.get("name", "")

                if "products" in concept and concept["products"]:
                    has_concept = True
                    products_list = concept["products"]
                    print(f"   Тип: concept с products ({len(products_list)} изданий)")
                elif concept_id:
                    print(f"   Concept найден (id={concept_id}), получаем все издания...")
                    in_parts = url.split("/")
                    concept_url = "/".join(in_parts[:4]) + f"/concept/{concept_id}"
                    concept_params_price = get_params(concept_url)

                    try:
                        async with session.get(
                            "https://web.np.playstation.com/api/graphql/v1/op",
                            params=concept_params_price,
                            headers=json_headers(concept_url)
                        ) as concept_resp:
                            concept_text = await concept_resp.text()

                        concept_data = loads(concept_text)
                        concept_retrieve = concept_data.get("data", {}).get("conceptRetrieve", {})

                        if concept_retrieve and "products" in concept_retrieve:
                            products_list = concept_retrieve["products"]
                            has_concept = True
                            if not main_name:
                                main_name = concept_retrieve.get("name", "")
                            print(f"   Получено {len(products_list)} изданий из concept")
                    except Exception as e:
                        print(f"     Ошибка запроса concept: {type(e).__name__}")

            if not has_concept:
                products_list = [product_retrieve]
                if not main_name:
                    main_name = product_retrieve.get("name", "")
                print(f"    Тип: одиночный продукт")

            if not main_name and products_list:
                main_name = products_list[0].get("invariantName", "") or products_list[0].get("name", "")

            if not main_name:
                print(f"     Не удалось получить main_name")
                counter += 1
                await asyncio.sleep(5)
                continue

            result = []

            # Обрабатываем каждый продукт
            for product in products_list:
                try:
                    product_id = product.get("id", "")
                    name = product.get("name", "")

                    if not product_id or not name:
                        continue

                    # Если нет webctas, запрашиваем полную информацию
                    if not product.get("webctas"):
                        print(f"   Получаю цены для: {name}")
                        in_parts = url.split("/")
                        product_url = "/".join(in_parts[:4]) + f"/product/{product_id}"
                        product_params_price, _ = get_params(product_url)

                        try:
                            async with session.get(
                                "https://web.np.playstation.com/api/graphql/v1/op",
                                params=product_params_price,
                                headers=json_headers(product_url)
                            ) as product_resp:
                                product_text = await product_resp.text()

                            product_data = loads(product_text)
                            product_retrieve = product_data.get("data", {}).get("productRetrieve", {})

                            if product_retrieve and product_retrieve.get("webctas"):
                                product["webctas"] = product_retrieve["webctas"]
                        except Exception:
                            pass

                        await asyncio.sleep(0.5)

                    # Edition
                    edition_data = product.get("edition")
                    edition_name = ""
                    compound = ""

                    if edition_data:
                        if edition_data.get("features"):
                            compound = dumps(edition_data["features"])
                        edition_name = edition_data.get("name", "")
                        if not edition_name:
                            edition_name = name

                    # Category
                    category = []
                    if product.get("localizedGenres"):
                        category = list(set(i["value"] for i in product["localizedGenres"]))

                    # Product type
                    product_type = "Игра"
                    if "Subscription" in name:
                        product_type = "Подписка"
                    elif product.get("skus") and len(product["skus"]) > 0:
                        sku_name = product["skus"][0].get("name", "")
                        if sku_name.lower() not in ["demo", "демоверсия"]:
                            product_type = sku_name
                        elif len(product["skus"]) > 1:
                            product_type = product["skus"][1].get("name", "Игра")

                    product_type = EditionTypeNormalizer.normalize_type(product_type)

                    # Image
                    image = ""
                    if product.get("media"):
                        for img in product["media"]:
                            if img.get("role") == "MASTER":
                                image = img.get("url", "")
                                break

                    # Tags - собираем все уникальные названия для двуязычного поиска
                    tags = [main_name, name]
                    invariant_name = product.get("invariantName", "")
                    if invariant_name and invariant_name != name:
                        tags.append(invariant_name)

                    # Удаляем дубликаты и пустые строки
                    tags = list(set([t for t in tags if t]))

                    # Цены
                    inr_price = 0
                    inr_old_price = 0
                    ps_price_in = None
                    discount = ""
                    discount_end = None
                    ps_plus = False
                    ea_access = False
                    ps_plus_collection = None  # Определяется по CTA типу

                    webctas = product.get("webctas", [])
                    for cta in webctas:
                        cta_type = cta.get("type", "")
                        price_data = cta.get("price", {})

                        if cta_type == "PREORDER":
                            product_type = "Предзаказ"

                        if cta_type in _PURCHASE_CTA_TYPES:
                            if price_data.get("discountedPrice") and not inr_price:
                                inr_price = parse_price_value(price_data.get("discountedValue", 0), divide_by_100=False)
                            if price_data.get("basePrice") and not inr_old_price:
                                inr_old_price = parse_price_value(price_data.get("basePriceValue", 0), divide_by_100=False)
                            if price_data.get("discountText"):
                                discount = price_data["discountText"]
                            if price_data.get("endTime"):
                                discount_end = datetime.fromtimestamp(int(price_data["endTime"]) // 1000)

                        elif "PS_PLUS" in cta_type:
                            if price_data.get("discountedPrice") == "Included":
                                ps_plus = True
                                # Определяем уровень подписки по типу CTA
                                if cta_type == "UPSELL_PS_PLUS_GAME_CATALOG":
                                    ps_plus_collection = "Deluxe/Extra"
                                elif cta_type == "UPSELL_PS_PLUS_FREE":
                                    ps_plus_collection = "Essential"
                                elif cta_type == "UPSELL_PS_PLUS_CLASSICS_CATALOG":
                                    ps_plus_collection = "Deluxe/Premium"
                                elif cta_type == "UPSELL_PS_PLUS_CLASSIC_GAME_COLLECTION":
                                    ps_plus_collection = "Deluxe/Premium"
                            elif cta_type == "UPSELL_PS_PLUS_DISCOUNT" and price_data.get("discountedValue"):
                                ps_price_in = parse_price_value(price_data.get("discountedValue"), divide_by_100=False)

                        elif "EA_ACCESS" in cta_type:
                            if price_data.get("discountedPrice") == "Included":
                                ea_access = True

                    if not inr_price:
                        inr_price = inr_old_price

                    # Очистка тегов
                    cleaned_tags = []
                    for tag in tags:
                        for c in ['™', '®', '©', '℗', '℠', "'"]:
                            tag = tag.replace(c, "'" if c == "'" else "")
                        cleaned_tags.append(tag)

                    # Вычисляем процент скидки
                    discount_percent = 0
                    if inr_old_price and inr_old_price > inr_price > 0:
                        discount_percent = round(((inr_old_price - inr_price) / inr_old_price) * 100)

                    # Конвертируем IN цены в рубли
                    price_rub_in = currency_converter.convert(inr_price, "INR", "RUB")
                    ps_plus_price_rub_in = currency_converter.convert(ps_price_in, "INR", "RUB") if ps_price_in else None

                    # Парсим локализацию для IN региона
                    def get_localization_code(voice_langs: str, subs: str) -> str:
                        """
                        Определяет код локализации на основе языков озвучки и субтитров

                        Логика:
                        - Если в Voice есть Russian → "full" (полностью на русском)
                        - Иначе если в Screen Languages есть Russian → "subtitles" (русские субтитры)
                        - Иначе → "none" (нет русского)

                        Returns:
                            "full" - полностью на русском (есть озвучка)
                            "subtitles" - только русские субтитры
                            "none" - нет русского языка
                        """
                        has_russian_voice = voice_langs and ("русский" in voice_langs.lower() or "russian" in voice_langs.lower())
                        has_russian_subs = subs and ("русский" in subs.lower() or "russian" in subs.lower())

                        if has_russian_voice:
                            return "full"
                        elif has_russian_subs:
                            return "subtitles"
                        else:
                            return "none"

                    # Получаем локализацию для IN региона
                    print(f"   Парсинг локализации для {name}...")
                    voice_languages_in, subtitles_in = await get_localization_for_region(session, product_id, "en-in")
                    localization_in = get_localization_code(voice_languages_in, subtitles_in) if (voice_languages_in is not None and subtitles_in is not None) else None

                    if localization_in:
                        print(f"       Локализация IN: {localization_in}")

                    # Добавляем только если есть цена ИЛИ PS Plus подписка
                    if inr_price > 0 or ps_plus_collection:
                        if inr_price > 0:
                            print(f"    Добавлен: {name} ({edition_name or 'базовая'}) - INR {inr_price} (RUB {price_rub_in})")
                        else:
                            print(f"    Добавлен: {name} ({edition_name or 'базовая'}) - PS Plus ({ps_plus_collection}), нет цены")
                        result.append({
                            "id": product_id,
                            "category": category,
                            "region": "IN",
                            "type": product_type,
                            "name": name,
                            "main_name": main_name,
                            "name_localized": None,
                            "search_names": ",".join(set(cleaned_tags)),
                            "image": image,
                            "compound": compound,
                            "platforms": None,
                            "publisher": None,
                            "localization": localization_in,
                            "rating": 0.0,
                            "info": None,
                            "price_uah": 0.0,
                            "old_price_uah": 0.0,
                            "price_try": 0.0,
                            "old_price_try": 0.0,
                            "price_inr": inr_price,
                            "old_price_inr": inr_old_price,
                            "price_rub": price_rub_in,
                            "price_rub_region": "IN",
                            "ps_plus_price_uah": None,
                            "ps_plus_price_try": None,
                            "ps_plus_price_inr": ps_price_in,
                            "ps_plus_price_rub": ps_plus_price_rub_in,
                            "ps_plus": 1 if ps_plus else 0,
                            "ps_plus_collection": ps_plus_collection,
                            "ea_access": 1 if ea_access else 0,
                            "discount": discount_percent,
                            "discount_percent": discount_percent,
                            "discount_end": discount_end.strftime("%Y-%m-%d %H:%M:%S") if discount_end else None,
                            "tags": ",".join(set(cleaned_tags)),
                            "edition": edition_name,
                            "description": None,
                            "players_min": None,
                            "players_max": None,
                            "players_online": 0,
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                    else:
                        print(f"     Пропуск: {name} ({edition_name or 'базовая'}) - нет цены и нет PS Plus")

                except Exception as e:
                    print(f"     Ошибка обработки продукта: {type(e).__name__}: {str(e)}")
                    continue

            print(f"    Обработано: {len(result)} товаров с IN ценами (включая PS Plus без цены)")

            # Обрабатываем издания с PS Plus без цены
            if result:
                result = process_ps_plus_only_editions(result)

            return result

        except (asyncio.CancelledError, KeyboardInterrupt):
            return []

        except Exception as e:
            print(f"     Ошибка парсинга IN (попытка {counter + 1}/2): {type(e).__name__}: {str(e)}")
            counter += 1
            await asyncio.sleep(5)
    else:
        print(f"    Исчерпаны попытки парсинга IN")
        return []


def uni(non_uni: list):
    seen = set()
    for_del = []


    for idx, ele in enumerate(non_uni):
        if (ele["name"], ele["edition"], " ".join(ele["platforms"]) if ele["platforms"] else None, ele["description"]) in seen:
            for_del.append(idx)
        else:
            seen.add((ele["name"], ele["edition"], " ".join(ele["platforms"]) if ele["platforms"] else None, ele["description"]))


    for idx in reversed(for_del):
        del non_uni[idx]

def uni(non_uni: list):
    """
    Удаляет дубликаты из списка записей по ключу (name, edition, region, description)
    Модифицирует список на месте
    """
    seen = set()
    for_del = []

    for idx, ele in enumerate(non_uni):
        # Создаем ключ для проверки дубликатов
        key = (
            ele.get("name", ""),
            ele.get("edition", "") or "",
            ele.get("region", "") or "",
            (ele.get("description", "")[:100] if ele.get("description") else "")
        )

        if key in seen:
            for_del.append(idx)
        else:
            seen.add(key)

    # Удаляем дубликаты в обратном порядке (чтобы не сбивать индексы)
    for idx in reversed(for_del):
        del non_uni[idx]

def find_in_result(result: List[Dict], name: str, edition: str = None, description: str = None, region: str = None) -> List[Tuple[int, Dict]]:
    """
    Ищет товары в result.pkl по названию, edition, описанию и региону

    Returns:
        List[Tuple[int, Dict]]: [(index, item), ...] - найденные товары с индексами
    """
    matches = []

    # Нормализуем входные данные для поиска
    name_norm = name.strip().lower()
    edition_norm = edition.strip().lower() if edition else ""
    desc_norm = (description[:100] if description else "").strip().lower()
    region_norm = region.strip().upper() if region else None

    for idx, item in enumerate(result):
        item_name = item.get("name", "").strip().lower()
        item_edition = (item.get("edition", "") or "").strip().lower()
        item_desc = (item.get("description", "")[:100] if item.get("description") else "").strip().lower()
        item_region = item.get("region", "").strip().upper() if item.get("region") else None

        # Точное совпадение по name
        name_match = item_name == name_norm

        # Edition может быть пустым
        edition_match = True
        if edition_norm and item_edition:
            edition_match = item_edition == edition_norm
        elif edition_norm or item_edition:
            # Один пустой, другой нет - не совпадение
            edition_match = False

        # Description для дополнительной проверки
        desc_match = item_desc == desc_norm if desc_norm and item_desc else True

        # Region для матчинга разных регионов
        region_match = True
        if region_norm and item_region:
            region_match = item_region == region_norm
        elif region_norm or item_region:
            # Если указан регион, проверяем точное совпадение
            region_match = False

        if name_match and edition_match and desc_match and region_match:
            matches.append((idx, item))

    return matches


def normalize_name_for_ps_plus_match(name: str) -> str:
    """
    Нормализует название для сравнения изданий PS Plus

    Убирает приписки типа "(PlayStation Plus)", лишние пробелы, регистр

    Args:
        name: Оригинальное название игры

    Returns:
        str: Нормализованное название
    """
    if not name:
        return ""

    normalized = name.strip().lower()

    # Убираем приписки PS Plus в разных форматах
    ps_plus_patterns = [
        "(playstation plus)",
        "(ps plus)",
        "(ps+)",
        "(базовая)",
        "(базовый)",
        "(base)",
    ]

    for pattern in ps_plus_patterns:
        normalized = normalized.replace(pattern, "")

    # Убираем лишние пробелы
    normalized = " ".join(normalized.split())

    return normalized


def process_ps_plus_only_editions(products_list: List[Dict]) -> List[Dict]:
    """
    Обрабатывает издания с PS Plus подписками без цены.

    Логика:
    1. Находит издания БЕЗ цены, но С PS Plus CTA (подписка)
    2. Ищет совпадающие издания С ценой (по name, description, platforms)
    3. Добавляет ps_plus_collection метку к изданию с ценой
    4. Удаляет издание без цены из результата

    ВАЖНО: Нормализует названия, убирая приписки "(PlayStation Plus)" и т.д.

    Args:
        products_list: Список спарсенных продуктов

    Returns:
        List[Dict]: Обновленный список без изданий только с подпиской
    """
    if not products_list:
        return products_list

    # Разделяем на товары с ценой и без цены (но с PS Plus)
    products_with_price = []
    products_ps_plus_only = []

    for product in products_list:
        # Проверяем наличие хотя бы одной цены
        has_price = (
            product.get("price_uah", 0) > 0 or
            product.get("price_try", 0) > 0 or
            product.get("price_inr", 0) > 0
        )

        # Проверяем наличие PS Plus подписки
        has_ps_plus_collection = product.get("ps_plus_collection") is not None

        if has_price:
            products_with_price.append(product)
        elif has_ps_plus_collection and not has_price:
            # Издание БЕЗ цены, но С подпиской
            products_ps_plus_only.append(product)

    if not products_ps_plus_only:
        # Нет изданий только с подпиской
        return products_list

    print(f"   Найдено {len(products_ps_plus_only)} изданий только с PS Plus (без цены)")

    # Матчим издания без цены с изданиями с ценой
    matched_indices = set()  # Индексы products_with_price, которые уже сматчились
    ps_plus_indices_to_remove = set()  # Индексы products_ps_plus_only для удаления

    for ps_idx, ps_product in enumerate(products_ps_plus_only):
        # НОВАЯ ЛОГИКА: Нормализуем название (убираем "(PlayStation Plus)" и т.д.)
        ps_name_original = ps_product.get("name", "")
        ps_name = normalize_name_for_ps_plus_match(ps_name_original)
        ps_desc = (ps_product.get("description", "") or "")[:100].strip().lower()
        ps_platforms = (ps_product.get("platforms") or "").strip().lower()
        ps_region = ps_product.get("region", "")
        ps_collection = ps_product.get("ps_plus_collection")

        # Ищем совпадение среди товаров с ценой
        for price_idx, price_product in enumerate(products_with_price):
            if price_idx in matched_indices:
                continue  # Уже сматчен

            # НОВАЯ ЛОГИКА: Нормализуем название товара с ценой
            price_name_original = price_product.get("name", "")
            price_name = normalize_name_for_ps_plus_match(price_name_original)
            price_desc = (price_product.get("description", "") or "")[:100].strip().lower()
            price_platforms = (price_product.get("platforms") or "").strip().lower()
            price_region = price_product.get("region", "")

            # Проверяем совпадение: name (нормализованное) + description + platforms + РЕГИОН
            name_match = ps_name == price_name
            desc_match = ps_desc == price_desc if ps_desc and price_desc else True
            platform_match = ps_platforms == price_platforms if ps_platforms and price_platforms else True
            region_match = ps_region == price_region if ps_region and price_region else True

            if name_match and desc_match and platform_match and region_match:
                # Совпадение найдено!
                print(f"     Матч [{ps_region}]: {ps_name_original} (PS Plus) → {price_name_original} (с ценой)")
                print(f"       Добавляем метку: {ps_collection}")

                # Обновляем ps_plus_collection у издания с ценой
                # Если уже есть метка, объединяем (может быть Essential + Extra например)
                existing_collection = price_product.get("ps_plus_collection")
                if existing_collection and existing_collection != ps_collection:
                    # Объединяем метки (например "Essential, Extra")
                    combined = f"{existing_collection}, {ps_collection}"
                    products_with_price[price_idx]["ps_plus_collection"] = combined
                else:
                    products_with_price[price_idx]["ps_plus_collection"] = ps_collection

                # ИСПРАВЛЕНИЕ: Обновляем ps_plus = 1 при добавлении метки
                products_with_price[price_idx]["ps_plus"] = 1

                # Помечаем для удаления
                matched_indices.add(price_idx)
                ps_plus_indices_to_remove.add(ps_idx)
                break  # Переходим к следующему PS Plus изданию

    # Формируем итоговый список
    # 1. Все товары с ценой (обновлённые)
    result = products_with_price.copy()

    # 2. PS Plus издания, которые НЕ смогли сматчиться (оставляем как есть)
    unmatched_ps_plus = [
        ps_product for ps_idx, ps_product in enumerate(products_ps_plus_only)
        if ps_idx not in ps_plus_indices_to_remove
    ]

    if unmatched_ps_plus:
        print(f"     Несовпавшие PS Plus издания: {len(unmatched_ps_plus)} (оставлены)")
        result.extend(unmatched_ps_plus)

    removed_count = len(ps_plus_indices_to_remove)
    if removed_count > 0:
        print(f"     Удалено дубликатов PS Plus изданий: {removed_count}")

    return result


async def get_promos(session: aiohttp.ClientSession, url: str):
    """
    Получает список названий промо игр из указанной категории

    Returns:
        List[str]: Список названий игр
    """
    async def _get_names(session: aiohttp.ClientSession, page_url: str):
        try:
            async with session.get(page_url, headers=page_headers()) as resp:
                html = await resp.text()

            if "You don't have permission to access" in html:
                await access_controller.wait_for_access(session)
                # Повторяем запрос после восстановления доступа
                return await _get_names(session, page_url)

            soup = bs(html, "html.parser")
            _main = soup.find("div", {"id": "__next"})
            if not _main:
                return []

            _main = _main.find("main")
            if not _main:
                return []

            section = _main.find("section", {"class": "ems-sdk-grid"})
            if not section:
                return []

            ul = section.find("ul", {"class": "psw-grid-list psw-l-grid"})
            if not ul:
                return []

            products = ul.find_all("li")
            names = []
            for product in products:
                try:
                    link = product.find("a")
                    if link and link.get("data-telemetry-meta"):
                        meta = loads(link["data-telemetry-meta"])
                        if "name" in meta:
                            names.append(meta["name"])
                except:
                    continue

            return names
        except:
            return []

    pages = await get_pages(session, url)
    if not pages:
        return []

    print("\n" + "=" * 80)
    print(" Получение промо акций")
    print("=" * 80)
    print(f" Найдено {len(pages)} страниц промо")

    games = []
    shift = parser_config.BATCH_SIZE_PAGES
    promo_start = perf_counter()

    for i in range(0, len(pages), shift):
        # Перезагружаем конфигурацию на каждой итерации
        parser_config.load_config()
        shift = parser_config.BATCH_SIZE_PAGES

        _games = await asyncio.gather(*[_get_names(session, pages[j]) for j in range(i, min(len(pages), i+shift))])
        games.extend(sum(_games, []))
        await asyncio.sleep(parser_config.SLEEP_BETWEEN_BATCHES)

        current = min(len(pages), i+shift)
        elapsed = perf_counter() - promo_start
        print_progress_bar(current, len(pages), elapsed, prefix=" Промо", suffix=f"| Получено: {len(games)}")

    print()
    print(f" Получено {len(games)} промо названий")
    return games

async def get_all_ps_plus_subscriptions(session: aiohttp.ClientSession):
    """
    Получает все игры из подписок PS Plus Extra и Deluxe отдельно

    Returns:
        dict: {
            'Extra': set(str),  # Названия игр из PS Plus Extra
            'Deluxe': set(str)  # Названия игр из PS Plus Deluxe (только уникальные для Deluxe)
        }
    """
    print("\n" + "=" * 80)
    print(" ПОЛУЧЕНИЕ ИГР ИЗ ПОДПИСОК PS PLUS")
    print("=" * 80)

    extra_games = await get_promos(session, parser_config.PS_PLUS_EXTRA_URL)
    deluxe_games = await get_promos(session, parser_config.PS_PLUS_DELUXE_URL)

    # Игры, которые есть и в Extra, и в Deluxe (Deluxe включает Extra)
    extra_set = set(extra_games)
    deluxe_set = set(deluxe_games)

    # Deluxe включает все игры из Extra, поэтому игры только в Deluxe = Deluxe - Extra
    only_deluxe = deluxe_set - extra_set

    result = {
        'Extra': extra_set,
        'Deluxe': only_deluxe,  # Только игры, которые есть в Deluxe, но не в Extra
        'All': deluxe_set  # Все игры из Deluxe (для обратной совместимости)
    }

    print(f"\n[OK] PS Plus Extra: {len(extra_set)} игр")
    print(f"[OK] PS Plus Deluxe (только Deluxe): {len(only_deluxe)} игр")
    print(f"[OK] Всего в Deluxe: {len(deluxe_set)} игр")

    return result


PRODUCT_TABLE_COLUMNS = (
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


PRODUCT_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_products_region ON products(region)",
    "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)",
    "CREATE INDEX IF NOT EXISTS idx_products_region_category ON products(region, category)",
    "CREATE INDEX IF NOT EXISTS idx_products_main_name ON products(main_name)",
    "CREATE INDEX IF NOT EXISTS idx_products_ps_plus_collection ON products(ps_plus_collection)",
    "CREATE INDEX IF NOT EXISTS idx_products_ea_access ON products(ea_access)",
)


CURRENCY_RATE_COLUMNS = (
    ("updated_at", "TIMESTAMP"),
    ("created_by", "INTEGER"),
    ("description", "TEXT"),
)


DEFAULT_CURRENCY_RATES = (
    ("UAH", "RUB", 0, 1000, 2.5, 1),
    ("UAH", "RUB", 1000, None, 2.5, 1),
    ("TRY", "RUB", 0, 1000, 3.0, 1),
    ("TRY", "RUB", 1000, None, 3.0, 1),
    ("INR", "RUB", 0, 1000, 1.2, 1),
    ("INR", "RUB", 1000, None, 1.2, 1),
)


def normalize_search_text(value: str | None) -> str:
    if not value:
        return ""

    normalized = str(value).replace("в„ў", " ").replace("В®", " ").replace("В©", " ")
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.casefold().replace("С‘", "Рµ")
    normalized = re.sub(r"[^\w\s]+", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"[_\s]+", " ", normalized)
    return normalized.strip()


async def prepare_sqlite_connection(db: aiosqlite.Connection):
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=30000")
    try:
        await db.create_function("normalize_search", 1, normalize_search_text, deterministic=True)
    except TypeError:
        await db.create_function("normalize_search", 1, normalize_search_text)


async def get_table_columns(db: aiosqlite.Connection, table_name: str) -> Set[str]:
    cursor = await db.execute(f'PRAGMA table_info("{table_name}")')
    rows = await cursor.fetchall()
    await cursor.close()
    return {row[1] for row in rows}


async def seed_missing_currency_rates(db: aiosqlite.Connection):
    for currency_from in ("UAH", "TRY", "INR"):
        cursor = await db.execute(
            """
            SELECT 1 FROM currency_rates
            WHERE currency_from = ? AND currency_to = 'RUB' AND is_active = 1
            LIMIT 1
            """,
            (currency_from,),
        )
        exists = await cursor.fetchone()
        await cursor.close()
        if exists:
            continue

        rows = [row for row in DEFAULT_CURRENCY_RATES if row[0] == currency_from]
        await db.executemany(
            """
            INSERT INTO currency_rates (
                currency_from, currency_to, price_min, price_max, rate,
                is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            rows,
        )


async def ensure_database_schema():
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        await prepare_sqlite_connection(db)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS currency_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency_from TEXT NOT NULL,
                currency_to TEXT NOT NULL,
                price_min REAL NOT NULL,
                price_max REAL,
                rate REAL NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                created_by INTEGER,
                description TEXT
            )
        """)

        existing_rate_columns = await get_table_columns(db, "currency_rates")
        for name, column_type in CURRENCY_RATE_COLUMNS:
            if name not in existing_rate_columns:
                await db.execute(f'ALTER TABLE currency_rates ADD COLUMN "{name}" {column_type}')

        await db.execute("""
            UPDATE currency_rates
            SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
            WHERE updated_at IS NULL
        """)
        await seed_missing_currency_rates(db)

        column_sql = ",\n                ".join(
            f"{name} {column_type}" for name, column_type in PRODUCT_TABLE_COLUMNS
        )
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS products (
                {column_sql},
                PRIMARY KEY (id, region)
            )
        """)

        existing_columns = await get_table_columns(db, "products")
        for name, column_type in PRODUCT_TABLE_COLUMNS:
            if name not in existing_columns:
                await db.execute(f'ALTER TABLE products ADD COLUMN "{name}" {column_type}')

        await db.execute("""
            CREATE TABLE IF NOT EXISTS update_info (
                id TEXT,
                edition_id INTEGER,
                currency INTEGER
            )
        """)

        for index_sql in PRODUCT_INDEXES:
            await db.execute(index_sql)

        await db.commit()


async def add_update_table():
    """
    Создает таблицу update_info в SQLite БД (если не существует)
    Используется для отслеживания обновлений товаров
    """
    await ensure_database_schema()

INSERT_PRODUCTS_SQL = """
    INSERT OR REPLACE INTO products (
        id, category, region, type, name, main_name, image, compound,
        platforms, publisher, localization, rating, info, price, old_price,
        ps_price, plus_types, ea_price, ps_plus, ea_access, discount,
        discount_end, tags, edition, description, price_uah, old_price_uah,
        price_try, old_price_try, price_inr, old_price_inr, price_rub,
        price_rub_region, ps_plus_price_uah, ps_plus_price_try, ps_plus_price_inr,
        players_min, players_max, players_online, name_localized, search_names,
        discount_percent, ps_plus_collection, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?)
"""


def _resolve_promo_sets(promo) -> Tuple[set, set, set]:
    if isinstance(promo, dict):
        return promo.get('Extra', set()), promo.get('Deluxe', set()), promo.get('All', set())
    all_set = set(promo) if promo else set()
    return all_set, set(), all_set


def _prepare_products_for_db(result: list, promo) -> list:
    extra_set, deluxe_set, all_set = _resolve_promo_sets(promo)
    products_to_insert = []

    for product in result:
        if not product.get("price_uah") and not product.get("price_try") and not product.get("price_inr"):
            continue

        name = product.get("name", "")
        if "Подписка PlayStation Plus" in name or "EA Play на" in name:
            continue

        ps_plus_collection = product.get("ps_plus_collection")

        old_prices_rub = []
        old_price_uah = product.get("old_price_uah", 0.0)
        old_price_try = product.get("old_price_try", 0.0)
        old_price_inr = product.get("old_price_inr", 0.0)
        if old_price_uah > 0:
            old_prices_rub.append(currency_converter.convert(old_price_uah, "UAH", "RUB"))
        if old_price_try > 0:
            old_prices_rub.append(currency_converter.convert(old_price_try, "TRY", "RUB"))
        if old_price_inr > 0:
            old_prices_rub.append(currency_converter.convert(old_price_inr, "INR", "RUB"))
        old_price_rub = min(old_prices_rub) if old_prices_rub else None

        ps_plus_prices_rub = []
        ps_plus_price_uah = product.get("ps_plus_price_uah")
        ps_plus_price_try = product.get("ps_plus_price_try")
        ps_plus_price_inr = product.get("ps_plus_price_inr")
        if ps_plus_price_uah:
            ps_plus_prices_rub.append(currency_converter.convert(ps_plus_price_uah, "UAH", "RUB"))
        if ps_plus_price_try:
            ps_plus_prices_rub.append(currency_converter.convert(ps_plus_price_try, "TRY", "RUB"))
        if ps_plus_price_inr:
            ps_plus_prices_rub.append(currency_converter.convert(ps_plus_price_inr, "INR", "RUB"))
        ps_plus_price_rub = min(ps_plus_prices_rub) if ps_plus_prices_rub else None

        prices_with_regions = []
        price_uah = product.get("price_uah", 0.0)
        price_try = product.get("price_try", 0.0)
        price_inr = product.get("price_inr", 0.0)
        if price_uah > 0:
            prices_with_regions.append((currency_converter.convert(price_uah, "UAH", "RUB"), "UA"))
        if price_try > 0:
            prices_with_regions.append((currency_converter.convert(price_try, "TRY", "RUB"), "TR"))
        if price_inr > 0:
            prices_with_regions.append((currency_converter.convert(price_inr, "INR", "RUB"), "IN"))

        price_rub = 0
        price_rub_region = None
        if prices_with_regions:
            price_rub, price_rub_region = min(prices_with_regions, key=lambda x: x[0])

        category_str = product.get("category", [])
        if isinstance(category_str, list):
            category_str = ",".join(category_str)

        products_to_insert.append((
            product.get("id"),
            category_str,
            product.get("region", "UA"),
            product.get("type"),
            product.get("name"),
            product.get("main_name"),
            product.get("image"),
            product.get("compound"),
            product.get("platforms"),
            product.get("publisher"),
            product.get("localization"),
            product.get("rating", 0.0),
            product.get("info"),
            price_rub,
            old_price_rub,
            ps_plus_price_rub,
            None,
            None,
            product.get("ps_plus", 0),
            product.get("ea_access", 0),
            product.get("discount_percent", 0),
            product.get("discount_end"),
            product.get("tags"),
            product.get("edition"),
            product.get("description"),
            product.get("price_uah", 0.0),
            product.get("old_price_uah", 0.0),
            product.get("price_try", 0.0),
            product.get("old_price_try", 0.0),
            product.get("price_inr", 0.0),
            product.get("old_price_inr", 0.0),
            price_rub,
            price_rub_region,
            product.get("ps_plus_price_uah"),
            product.get("ps_plus_price_try"),
            product.get("ps_plus_price_inr"),
            product.get("players_min"),
            product.get("players_max"),
            product.get("players_online", 0),
            product.get("name_localized"),
            product.get("search_names"),
            product.get("discount_percent", 0),
            ps_plus_collection,
            product.get("created_at"),
            product.get("updated_at")
        ))

    return products_to_insert


async def save_batch_to_db(result: list, promo, clear_db: bool = False):
    """Инкрементальное сохранение порции результатов в БД (INSERT OR REPLACE)"""
    products_to_insert = _prepare_products_for_db(result, promo)
    if not products_to_insert:
        return 0

    await ensure_database_schema()
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        await prepare_sqlite_connection(db)
        if clear_db:
            await db.execute("DELETE FROM products")
            await db.commit()
        await db.executemany(INSERT_PRODUCTS_SQL, products_to_insert)
        await db.commit()

    return len(products_to_insert)


async def process_and_save_to_db(result: list, promo: list, start_time: float, clear_db: bool = True):
    """
    Обработка спарсенных данных и сохранение в SQLite БД

    Args:
        result: Список спарсенных продуктов
        promo: Список промо названий (для обратной совместимости) ИЛИ dict с ключами 'Extra', 'Deluxe', 'All'
        start_time: Время начала парсинга (для расчета общего времени)
        clear_db: Очищать ли БД перед вставкой (по умолчанию True)
    """
    print("\n" + "=" * 80)
    print("ОБРАБОТКА И СОХРАНЕНИЕ ДАННЫХ")
    print("=" * 80)

    await ensure_database_schema()

    print(f"Обработка {len(result)} продуктов...")
    products_to_insert = _prepare_products_for_db(result, promo)
    print(f"Подготовлено {len(products_to_insert)} продуктов для вставки")

    print("\n" + "=" * 80)
    print("Сохранение в SQLite базу данных")
    print("=" * 80)

    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        await prepare_sqlite_connection(db)
        if clear_db:
            print("Очистка таблицы products...")
            await db.execute("DELETE FROM products")
            await db.commit()
            print("Таблица очищена")

        print(f"Вставка {len(products_to_insert)} продуктов...")
        await db.executemany(INSERT_PRODUCTS_SQL, products_to_insert)
        await db.commit()
        print(f"[OK] Успешно вставлено {len(products_to_insert)} продуктов")

    # Статистика
    end = perf_counter()
    total_time = end - start_time

    print("\n" + "=" * 80)
    print("ЗАГРУЗКА В БД ЗАВЕРШЕНА УСПЕШНО!")
    print("=" * 80)
    print(f"Общее время: {total_time:.2f} секунд ({total_time/60:.1f} минут)")
    print(f"Всего продуктов: {len(products_to_insert)}")
    print("=" * 80)


async def process_specific_products_to_db(parsed_products: list, promo: list, start_time: float):
    """
    Загружает только спарсенные товары в БД с проверкой существования и обновлением update_info

    Args:
        parsed_products: Список только что спарсенных продуктов
        promo: Список промо названий (для обратной совместимости) ИЛИ dict с ключами 'Extra', 'Deluxe', 'All'
        start_time: Время начала парсинга
    """
    print("\n" + "=" * 80)
    print("ЗАГРУЗКА ТОЛЬКО СПАРСЕННЫХ ТОВАРОВ В БД")
    print("=" * 80)
    print("Используется режим добавления без очистки БД")
    print("Существующие записи update_info будут обновлены")
    print("=" * 80)

    # Используем существующую логику обработки данных
    # Передаем только спарсенные товары с clear_db=False
    # update_info будет обновлен через UPSERT в process_and_save_to_db
    await process_and_save_to_db(parsed_products, promo, start_time, clear_db=False)


def get_missing_products(products: List[str], result: List[Dict]) -> Tuple[List[str], Dict]:
    """
    Определяет, какие продукты из products.pkl еще не спарсены в result.pkl

    Args:
        products: Список всех product URLs из products.pkl
        result: Список спарсенных продуктов из result.pkl

    Returns:
        Tuple[List[str], Dict]: (список недостающих URLs, статистика)
    """
    print("\n" + "=" * 80)
    print(" АНАЛИЗ НЕДОСТАЮЩИХ ТОВАРОВ")
    print("=" * 80)

    # Извлекаем ID продуктов из result.pkl
    parsed_ids = set()
    parsed_by_locale = {}

    for item in result:
        product_id = item.get("id", "")
        if product_id:
            # Извлекаем ID без локали (последняя часть URL)
            clean_id = product_id.split("-")[-1] if "-" in product_id else product_id
            parsed_ids.add(clean_id)

            # Отслеживаем по локалям
            if product_id not in parsed_by_locale:
                parsed_by_locale[product_id] = item

    print(f" Уникальных спарсенных ID: {len(parsed_ids)}")
    print(f" Всего записей в result.pkl: {len(result)}")

    # Анализируем products.pkl
    missing_products = []
    total_urls = len(products)

    # Группируем по локалям
    products_by_locale = {"ru-ua": [], "en-tr": []}

    for url in products:
        url_parts = url.strip().rstrip('/').split('/')
        if len(url_parts) >= 5:
            locale = url_parts[3]
            product_id = url_parts[-1]
            clean_id = product_id.split("-")[-1] if "-" in product_id else product_id

            if locale in products_by_locale:
                products_by_locale[locale].append(url)

            # Проверяем, есть ли этот ID в спарсенных
            if clean_id not in parsed_ids:
                missing_products.append(url)

    print(f"\n Анализ по локалям:")
    print(f"  ru-ua URLs: {len(products_by_locale['ru-ua'])}")
    print(f"  en-tr URLs: {len(products_by_locale['en-tr'])}")

    # Статистика по регионам цен
    ua_prices = sum(1 for item in result if item.get("uah_price", 0) > 0)
    tr_prices = sum(1 for item in result if item.get("trl_price", 0) > 0)

    print(f"\n Статистика цен в result.pkl:")
    print(f"  UAH цены: {ua_prices} товаров")
    print(f"  TRY цены: {tr_prices} товаров")
    print(f"    Без UAH цены: {len(result) - ua_prices} товаров")
    print(f"    Без TRY цены: {len(result) - tr_prices} товаров")

    stats = {
        "total_urls": total_urls,
        "parsed_count": len(parsed_ids),
        "missing_count": len(missing_products),
        "ua_urls": len(products_by_locale["ru-ua"]),
        "tr_urls": len(products_by_locale["en-tr"]),
        "ua_prices": ua_prices,
        "tr_prices": tr_prices,
        "no_ua_prices": len(result) - ua_prices,
        "no_tr_prices": len(result) - tr_prices
    }

    print(f"\n ИТОГО:")
    print(f"   Спарсено уникальных товаров: {len(parsed_ids)}")
    print(f"   Недостающих URLs: {len(missing_products)}")
    print(f"   Прогресс: {len(parsed_ids) / total_urls * 100:.1f}%")
    print("=" * 80)

    return missing_products, stats


def get_products_without_prices(products: List[str], result: List[Dict]) -> Tuple[List[str], List[str], Dict]:
    """
    Определяет товары без UAH или TRY цен

    Args:
        products: Список всех product URLs из products.pkl (только ru-ua)
        result: Список спарсенных продуктов из result.pkl

    Returns:
        Tuple[List[str], List[str], Dict]: (URLs без UAH, URLs без TRY, статистика)

    Примечание:
        Для TRY цен возвращаются ru-ua URLs, т.к. parse() сам создаст en-tr версию
    """
    print("\n" + "=" * 80)
    print(" АНАЛИЗ ТОВАРОВ БЕЗ ЦЕН")
    print("=" * 80)

    # Создаем словарь ID -> ru-ua URL из products.pkl
    # В products.pkl хранятся только ru-ua URLs
    product_urls_by_id = {}
    for url in products:
        url_parts = url.strip().rstrip('/').split('/')
        if len(url_parts) >= 5:
            product_id = url_parts[-1].upper()
            # Сохраняем только ru-ua URL (он будет использован для обоих регионов)
            product_urls_by_id[product_id] = url

    # Находим товары без цен
    items_without_uah = []
    items_without_try = []
    urls_without_uah = []
    urls_without_try = []

    for item in result:
        product_id = item.get("id", "")
        if not product_id:
            continue

        has_uah = item.get("uah_price", 0) > 0
        has_try = item.get("trl_price", 0) > 0

        if not has_uah:
            items_without_uah.append(item)
            # Ищем ru-ua URL для этого товара
            if product_id in product_urls_by_id:
                urls_without_uah.append(product_urls_by_id[product_id])

        if not has_try:
            items_without_try.append(item)
            # Для TRY используем тот же ru-ua URL
            # Функция parse() сама создаст en-tr версию (строки 877-879)
            if product_id in product_urls_by_id:
                urls_without_try.append(product_urls_by_id[product_id])

    print(f" Товаров без UAH цены: {len(items_without_uah)}")
    print(f"   Найдено ru-ua URLs для перепарсинга: {len(urls_without_uah)}")

    print(f"\n Товаров без TRY цены: {len(items_without_try)}")
    print(f"   Найдено ru-ua URLs для перепарсинга: {len(urls_without_try)}")
    print(f"     parse() автоматически создаст en-tr версии для получения TRY цен")

    stats = {
        "items_without_uah": len(items_without_uah),
        "items_without_try": len(items_without_try),
        "urls_without_uah": len(urls_without_uah),
        "urls_without_try": len(urls_without_try)
    }

    print("=" * 80)

    return urls_without_uah, urls_without_try, stats


# Mode 4 helper functions
def match_products_by_id(ua_products: List[Dict], other_products: List[Dict], region_name: str) -> List[Tuple[Dict, Dict]]:
    """
    Матчит UA и другие регионы (TR/IN) по ID продукта

    Args:
        ua_products: Список товаров из UA
        other_products: Список товаров из другого региона (TR или IN)
        region_name: Название региона для логирования ("TR" или "IN")

    Returns:
        List[Tuple[Dict, Dict]]: [(ua_item, other_item), ...] - пары совпадающих товаров
    """
    def normalize_product_id(product_id: str) -> str:
        """Нормализует ID для сравнения между регионами"""
        if not product_id:
            return ""
        parts = product_id.split("-")
        if len(parts) >= 3:
            return parts[-1].upper()
        return product_id.upper()

    def get_cusa_code(product_id: str) -> str:
        """Извлекает CUSA код из ID"""
        import re
        match = re.search(r'(CUSA\d{4})', product_id.upper())
        return match.group(1) if match else ""

    matches = []
    used_other_ids = set()  # Отслеживаем уже использованные TR/IN товары

    for ua_item in ua_products:
        ua_id = ua_item.get("id", "").upper()
        ua_normalized_id = normalize_product_id(ua_id)
        ua_cusa = get_cusa_code(ua_id)
        ua_name = ua_item.get("name", "").strip().lower()
        ua_edition = (ua_item.get("edition", "") or "").strip().lower()

        for other_item in other_products:
            other_id = other_item.get("id", "").upper()

            # Пропускаем уже использованные TR/IN товары
            if other_id in used_other_ids:
                continue

            other_normalized_id = normalize_product_id(other_id)
            other_cusa = get_cusa_code(other_id)
            other_name = other_item.get("name", "").strip().lower()
            other_edition = (other_item.get("edition", "") or "").strip().lower()

            matched = False
            match_method = ""

            # 1. Полное совпадение ID
            if ua_id and other_id and ua_id == other_id:
                matched = True
                match_method = "Полное совпадение ID"

            # 2. Совпадение нормализованного ID
            elif ua_normalized_id and other_normalized_id and ua_normalized_id == other_normalized_id:
                if ua_edition == other_edition or not ua_edition or not other_edition:
                    matched = True
                    match_method = f"Нормализованный ID ({ua_normalized_id})"

            # 3. Совпадение CUSA кода
            elif ua_cusa and other_cusa and ua_cusa == other_cusa:
                if ua_edition == other_edition or not ua_edition or not other_edition:
                    matched = True
                    match_method = f"CUSA код ({ua_cusa})"

            # 4. Совпадение по имени + edition (fallback)
            elif ua_name and other_name and ua_name == other_name:
                if ua_edition == other_edition or not ua_edition or not other_edition:
                    matched = True
                    match_method = "Совпадение по имени"

            if matched:
                print(f"       Матч {region_name}: {match_method}")
                print(f"         UA: {ua_item.get('name')} ({ua_edition or 'базовая'}) - {ua_id}")
                print(f"         {region_name}: {other_item.get('name')} ({other_edition or 'базовая'}) - {other_id}")
                matches.append((ua_item, other_item))
                used_other_ids.add(other_id)  # Помечаем как использованный
                break

    # Debug: показываем несовпавшие
    if ua_products and other_products:
        matched_ua_ids = {ua_item.get("id") for ua_item, _ in matches}
        matched_other_ids = {other_item.get("id") for _, other_item in matches}

        unmatched_ua = [item for item in ua_products if item.get("id") not in matched_ua_ids]
        unmatched_other = [item for item in other_products if item.get("id") not in matched_other_ids]

        if unmatched_ua:
            print(f"\n     Несовпавшие UA товары ({len(unmatched_ua)}):")
            for item in unmatched_ua[:3]:  # Показываем только первые 3
                print(f"      - {item.get('name')} ({item.get('edition') or 'базовая'}) - {item.get('id')}")

        if unmatched_other:
            print(f"\n     Несовпавшие {region_name} товары ({len(unmatched_other)}):")
            for item in unmatched_other[:3]:  # Показываем только первые 3
                print(f"      - {item.get('name')} ({item.get('edition') or 'базовая'}) - {item.get('id')}")

    return matches


def merge_region_data(ua_item: Dict, other_item: Dict, region: str) -> Dict:
    """
    Объединяет UA данные + цены другого региона

    Args:
        ua_item: Товар с UA данными (полный)
        other_item: Товар с ценами другого региона (TR или IN)
        region: Код региона ("TR" или "IN")

    Returns:
        Dict: Полная запись с UA данными + ценами региона
    """
    # Берем UA товар как базу (полные данные)
    merged = ua_item.copy()

    # Объединяем search_names из обоих регионов для двуязычного поиска
    ua_search_names = set(ua_item.get("search_names", "").split(","))
    other_search_names = set(other_item.get("search_names", "").split(","))

    # Удаляем пустые строки
    ua_search_names = {n.strip() for n in ua_search_names if n.strip()}
    other_search_names = {n.strip() for n in other_search_names if n.strip()}

    # Объединяем
    all_search_names = ua_search_names.union(other_search_names)

    # Очищаем от спецсимволов
    cleaned_names = []
    for name in all_search_names:
        for c in ['™', '®', '©', '℗', '℠', "'"]:
            name = name.replace(c, "'" if c == "'" else "")
        cleaned_names.append(name)

    # Обновляем search_names
    merged["search_names"] = ",".join(sorted(set(cleaned_names)))

    # Обновляем регион
    merged["region"] = region

    # Обновляем цены из другого региона
    if region == "TR":
        merged["price_try"] = other_item.get("price_try", 0.0)
        merged["old_price_try"] = other_item.get("old_price_try", 0.0)
        merged["ps_plus_price_try"] = other_item.get("ps_plus_price_try")
        merged["price_rub"] = other_item.get("price_rub", 0.0)
        merged["price_rub_region"] = "TR"

        # Обнуляем цены других регионов
        merged["price_uah"] = 0.0
        merged["old_price_uah"] = 0.0
        merged["ps_plus_price_uah"] = None
        merged["price_inr"] = 0.0
        merged["old_price_inr"] = 0.0
        merged["ps_plus_price_inr"] = None

    elif region == "IN":
        merged["price_inr"] = other_item.get("price_inr", 0.0)
        merged["old_price_inr"] = other_item.get("old_price_inr", 0.0)
        merged["ps_plus_price_inr"] = other_item.get("ps_plus_price_inr")
        merged["price_rub"] = other_item.get("price_rub", 0.0)
        merged["price_rub_region"] = "IN"

        # Обнуляем цены других регионов
        merged["price_uah"] = 0.0
        merged["old_price_uah"] = 0.0
        merged["ps_plus_price_uah"] = None
        merged["price_try"] = 0.0
        merged["old_price_try"] = 0.0
        merged["ps_plus_price_try"] = None

    # Обновляем локализацию из другого региона (если есть)
    other_localization = other_item.get("localization")
    if other_localization:
        merged["localization"] = other_localization

    # Обновляем ps_plus_collection из другого региона (если есть и если в UA не определен)
    other_ps_plus_collection = other_item.get("ps_plus_collection")
    if other_ps_plus_collection:
        # Берем из другого региона, если он определен
        # (приоритет у другого региона, т.к. мы обновляем UA данные)
        merged["ps_plus_collection"] = other_ps_plus_collection

    # Обновляем discount и discount_percent
    merged["discount"] = other_item.get("discount", 0)
    merged["discount_percent"] = other_item.get("discount_percent", 0)
    merged["discount_end"] = other_item.get("discount_end")

    # Обновляем ps_plus_price_rub
    merged["ps_plus_price_rub"] = other_item.get("ps_plus_price_rub")

    # Сохраняем timestamps
    merged["created_at"] = other_item.get("created_at", merged.get("created_at"))
    merged["updated_at"] = other_item.get("updated_at", merged.get("updated_at"))

    return merged


async def main():
    """Главная функция парсера"""
    print("=" * 80)
    print(" ЗАПУСК ПАРСЕРА PlayStation Store")
    print("=" * 80)

    # Загрузка курсов валют из базы данных
    print("\n" + "=" * 80)
    print(" ЗАГРУЗКА КУРСОВ ВАЛЮТ")
    print("=" * 80)
    await ensure_database_schema()
    await currency_converter.load_rates()
    print("=" * 80)

    # Проверка аргументов командной строки для очистки кеша
    if "--clear-cache" in sys.argv or "--clean" in sys.argv:
        print("\n" + "=" * 80)
        print("  ОЧИСТКА КЕША")
        print("=" * 80)
        cache_files = ["promo.pkl", "products.pkl", "result.pkl"]
        for cache_file in cache_files:
            if os.path.exists(cache_file):
                os.remove(cache_file)
                print(f" Удален {cache_file}")
            else:
                print(f"⚪ {cache_file} не найден")
        print("=" * 80)
        print("\n")

    # Показываем информацию о кеше
    cache_info = []
    if os.path.exists("promo.pkl"):
        cache_info.append("promo.pkl ")
    else:
        cache_info.append("promo.pkl ")

    if os.path.exists("products.pkl"):
        cache_info.append("products.pkl ")
    else:
        cache_info.append("products.pkl ")

    if os.path.exists("result.pkl"):
        cache_info.append("result.pkl ")
    else:
        cache_info.append("result.pkl ")

    if cache_info:
        print(f"\n Статус кеша: {' | '.join(cache_info)}")
        print(" Используйте --clear-cache для очистки кеша\n")

    # Выбор режима работы
    print("\n" + "=" * 80)
    print("ВЫБЕРИТЕ РЕЖИМ РАБОТЫ")
    print("=" * 80)
    print("1. Полный парсинг (сбор данных + загрузка в БД)")
    print("2. Загрузка result.pkl в БД (пропустить парсинг)")
    print("3. Допарсинг недостающих товаров (продолжить парсинг)")
    print("4. Ручной парсинг товара (UA + TR регионы, обновление result.pkl)")
    print("=" * 80)

    mode = input("\nВведите номер режима (1, 2, 3 или 4): ").strip()

    if mode == "2":
        # Режим загрузки из result.pkl
        if not os.path.exists("result.pkl"):
            print("\n ОШИБКА: Файл result.pkl не найден!")
            print(" Запустите полный парсинг (режим 1) сначала")
            return

        print("\n" + "=" * 80)
        print(" РЕЖИМ ЗАГРУЗКИ result.pkl")
        print("=" * 80)

        start = perf_counter()

        print(" Загрузка result.pkl...")
        with open("result.pkl", "rb") as file:
            result = pickle.load(file)
        print(f" Загружено {len(result)} записей из result.pkl")

        # Загружаем promo для коллекций
        if os.path.exists("promo.pkl"):
            with open("promo.pkl", "rb") as file:
                promo_data = pickle.load(file)

            # Проверяем формат (старый список или новый dict)
            if isinstance(promo_data, dict):
                promo = promo_data
                print(f" Загружено из promo.pkl: Extra={len(promo.get('Extra', set()))}, Deluxe={len(promo.get('Deluxe', set()))}")
            else:
                # Старый формат - конвертируем в новый
                all_set = set(promo_data) if promo_data else set()
                promo = {
                    'Extra': all_set,
                    'Deluxe': set(),
                    'All': all_set
                }
                print(f" Загружено {len(all_set)} промо из promo.pkl (старый формат, конвертировано)")
        else:
            print("  promo.pkl не найден, промо коллекции не будут добавлены")
            promo = {'Extra': set(), 'Deluxe': set(), 'All': set()}

        # Переходим к обработке данных и загрузке в БД
        await process_and_save_to_db(result, promo, start)
        return

    elif mode == "3":
        # Режим допарсинга недостающих товаров
        if not os.path.exists("products.pkl"):
            print("\n ОШИБКА: Файл products.pkl не найден!")
            print(" Запустите полный парсинг (режим 1) сначала")
            return

        if not os.path.exists("result.pkl"):
            print("\n ОШИБКА: Файл result.pkl не найден!")
            print(" Запустите полный парсинг (режим 1) сначала")
            return

        print("\n" + "=" * 80)
        print(" РЕЖИМ ДОПАРСИНГА")
        print("=" * 80)

        start = perf_counter()

        # Загружаем существующие данные
        print(" Загрузка products.pkl...")
        with open("products.pkl", "rb") as file:
            all_products = pickle.load(file)
        print(f" Загружено {len(all_products)} product URLs")

        print("\n Загрузка result.pkl...")
        with open("result.pkl", "rb") as file:
            existing_result = pickle.load(file)
        print(f" Загружено {len(existing_result)} уже спарсенных записей")

        # Определяем недостающие товары
        missing_products, missing_stats = get_missing_products(all_products, existing_result)

        # Определяем товары без цен
        urls_without_uah, urls_without_try, price_stats = get_products_without_prices(all_products, existing_result)

        # Подсчитываем общее количество для допарсинга
        total_to_reparse = len(set(missing_products + urls_without_uah + urls_without_try))

        if not missing_products and not urls_without_uah and not urls_without_try:
            print("\n" + "=" * 80)
            print(" ВСЕ ТОВАРЫ СПАРСЕНЫ И ИМЕЮТ ЦЕНЫ!")
            print("=" * 80)
            print(" Можно использовать режим 2 для загрузки в БД")
            return

        # Предлагаем выбор типа допарсинга
        print("\n" + "=" * 80)
        print(" ЧТО ДОПАРСИТЬ?")
        print("=" * 80)
        print(f"1  Недостающие товары ({len(missing_products)} URLs)")
        print(f"2  Товары без UAH цены ({len(urls_without_uah)} URLs)")
        print(f"3  Товары без TRY цены ({len(urls_without_try)} URLs)")
        print(f"4  Все вместе (~{total_to_reparse} уникальных URLs)")
        print("=" * 80)

        reparse_mode = input("\n Выберите режим (1, 2, 3 или 4): ").strip()

        products_to_parse = []
        parse_label = ""

        if reparse_mode == "1":
            products_to_parse = missing_products
            parse_label = "недостающих товаров"
        elif reparse_mode == "2":
            products_to_parse = urls_without_uah
            parse_label = "товаров без UAH цены"
        elif reparse_mode == "3":
            products_to_parse = urls_without_try
            parse_label = "товаров без TRY цены"
        elif reparse_mode == "4":
            # Объединяем все и удаляем дубликаты
            products_to_parse = list(set(missing_products + urls_without_uah + urls_without_try))
            parse_label = "всех товаров (недостающие + без цен)"
        else:
            print("\n Неверный выбор! Введите 1, 2, 3 или 4")
            return

        if not products_to_parse:
            print(f"\n  Нет {parse_label} для допарсинга")
            return

        print(f"\n Будет спарсено {len(products_to_parse)} {parse_label}")

        # Загружаем promo
        if os.path.exists("promo.pkl"):
            with open("promo.pkl", "rb") as file:
                promo_data = pickle.load(file)

            # Проверяем формат (старый список или новый dict)
            if isinstance(promo_data, dict):
                promo = promo_data
                print(f" Загружено из promo.pkl: Extra={len(promo.get('Extra', set()))}, Deluxe={len(promo.get('Deluxe', set()))}")
            else:
                # Старый формат - конвертируем в новый
                all_set = set(promo_data) if promo_data else set()
                promo = {
                    'Extra': all_set,
                    'Deluxe': set(),
                    'All': all_set
                }
                print(f" Загружено {len(all_set)} промо из promo.pkl (старый формат, конвертировано)")
        else:
            print("  promo.pkl не найден, создаем новый...")
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(120)) as session:
                promo = await get_all_ps_plus_subscriptions(session)
                with open("promo.pkl", "wb") as file:
                    pickle.dump(promo, file)
                print(f"[OK] Промо сохранено в promo.pkl")

        # Парсим товары
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(120)) as session:
            print("\n" + "=" * 80)
            print(f" ПАРСИНГ {parse_label.upper()}")
            print("=" * 80)

            shift = parser_config.BATCH_SIZE_PRODUCTS
            new_result = []
            parse_start = perf_counter()

            for i in range(0, len(products_to_parse), shift):
                # Перезагружаем конфигурацию на каждой итерации
                parser_config.load_config()
                shift = parser_config.BATCH_SIZE_PRODUCTS

                _result = sum(await asyncio.gather(*[parse(session, products_to_parse[j]) for j in range(i, min(len(products_to_parse), i+shift))]), [])
                new_result.extend(_result)
                await asyncio.sleep(parser_config.SLEEP_BETWEEN_BATCHES)

                # Удаляем дубликаты после каждого батча
                uni(new_result)

                current = min(len(products_to_parse), i+shift)
                elapsed = perf_counter() - parse_start
                print_progress_bar(current, len(products_to_parse), elapsed, prefix=" Допарсинг", suffix=f"| Спарсено: {len(new_result)}")

            print()

        end = perf_counter()
        parse_time = end - parse_start
        print(f"\n Допарсинг завершен за {parse_time:.2f} сек ({parse_time/60:.1f} мин)")
        print(f" Новых товаров спарсено: {len(new_result)}")

        # Объединяем результаты
        print("\n" + "=" * 80)
        print(" ОБЪЕДИНЕНИЕ РЕЗУЛЬТАТОВ")
        print("=" * 80)

        print(f" Старых записей: {len(existing_result)}")
        print(f" Новых записей: {len(new_result)}")

        # Если допарсиваем товары без цен (режимы 2, 3, 4), нужно обновить существующие записи
        if reparse_mode in ["2", "3", "4"]:
            print("\n Обновление существующих записей с новыми ценами...")

            # Создаем словарь ID -> новые данные
            new_data_by_id = {}
            for item in new_result:
                product_id = item.get("id", "")
                if product_id:
                    new_data_by_id[product_id] = item

            # Обновляем существующие записи
            updated_count = 0
            for i, item in enumerate(existing_result):
                product_id = item.get("id", "")
                if product_id in new_data_by_id:
                    new_item = new_data_by_id[product_id]

                    # Обновляем цены если они появились (новые названия полей)
                    if new_item.get("price_uah", 0) > 0:
                        existing_result[i]["price_uah"] = new_item["price_uah"]
                        existing_result[i]["old_price_uah"] = new_item.get("old_price_uah", 0)
                        existing_result[i]["ps_plus_price_uah"] = new_item.get("ps_plus_price_uah")
                        updated_count += 1

                    if new_item.get("price_try", 0) > 0:
                        existing_result[i]["price_try"] = new_item["price_try"]
                        existing_result[i]["old_price_try"] = new_item.get("old_price_try", 0)
                        existing_result[i]["ps_plus_price_try"] = new_item.get("ps_plus_price_try")
                        updated_count += 1

                    if new_item.get("price_inr", 0) > 0:
                        existing_result[i]["price_inr"] = new_item["price_inr"]
                        existing_result[i]["old_price_inr"] = new_item.get("old_price_inr", 0)
                        existing_result[i]["ps_plus_price_inr"] = new_item.get("ps_plus_price_inr")
                        updated_count += 1

                    # Обновляем минимальные цены в рублях
                    if new_item.get("price_rub"):
                        existing_result[i]["price_rub"] = new_item["price_rub"]
                        existing_result[i]["price_rub_region"] = new_item.get("price_rub_region")

                    if new_item.get("ps_plus_price_rub"):
                        existing_result[i]["ps_plus_price_rub"] = new_item["ps_plus_price_rub"]

                    # Удаляем из new_data_by_id, чтобы не добавить дубликат
                    del new_data_by_id[product_id]

            # Добавляем новые товары (которых не было в existing_result)
            new_items = [new_data_by_id[pid] for pid in new_data_by_id]
            combined_result = existing_result + new_items

            print(f"    Обновлено записей: {updated_count}")
            print(f"    Добавлено новых: {len(new_items)}")
        else:
            # Для режима 1 просто объединяем
            combined_result = existing_result + new_result
            initial_count = len(combined_result)
            uni(combined_result)
            duplicates_removed = initial_count - len(combined_result)

            if duplicates_removed > 0:
                print(f"  Удалено дубликатов: {duplicates_removed}")

        print(f" Итого записей: {len(combined_result)}")

        # Сохраняем обновленный result.pkl
        with open("result.pkl", "wb") as file:
            pickle.dump(combined_result, file)
        print(f" Обновленный result.pkl сохранен ({len(combined_result)} записей)")

        # Переходим к обработке данных и загрузке в БД
        print("\n" + "=" * 80)
        print(" ЗАГРУЗКА ОБНОВЛЕННЫХ ДАННЫХ В БД")
        print("=" * 80)

        await process_and_save_to_db(combined_result, promo, start)
        return

    elif mode == "4":
        # Режим ручного парсинга для каждого региона отдельно
        print("\n" + "=" * 80)
        print(" РЕЖИМ 4: РУЧНОЙ ПАРСИНГ ПО РЕГИОНАМ")
        print("=" * 80)
        print(" Этот режим позволяет:")
        print("   1. Вставить UA ссылку → parse() создаст 3 записи (UA, TR, IN)")
        print("   2. Вставить TR ссылку → parse_tr() создаст TR запись")
        print("   3. Вставить IN ссылку → parse_in() создаст IN запись")
        print("   4. Все записи сохраняются отдельно в result.pkl")
        print("=" * 80)

        start = perf_counter()

        # Загружаем promo и result.pkl
        if os.path.exists("promo.pkl"):
            with open("promo.pkl", "rb") as file:
                promo_data = pickle.load(file)

            # Проверяем формат (старый список или новый dict)
            if isinstance(promo_data, dict):
                promo = promo_data
                print(f"\n[OK] Загружено из promo.pkl: Extra={len(promo.get('Extra', set()))}, Deluxe={len(promo.get('Deluxe', set()))}")
            else:
                # Старый формат - конвертируем в новый
                all_set = set(promo_data) if promo_data else set()
                promo = {
                    'Extra': all_set,
                    'Deluxe': set(),
                    'All': all_set
                }
                print(f"\n[OK] Загружено {len(all_set)} промо из promo.pkl (старый формат, конвертировано)")
        else:
            print("\n[!] promo.pkl не найден, создаем новый...")
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(120)) as temp_session:
                promo = await get_all_ps_plus_subscriptions(temp_session)
                with open("promo.pkl", "wb") as file:
                    pickle.dump(promo, file)
                print(f"[OK] Промо сохранено в promo.pkl")

        existing_result = []
        if os.path.exists("result.pkl"):
            with open("result.pkl", "rb") as file:
                existing_result = pickle.load(file)
            print(f"[OK] Загружено {len(existing_result)} записей из result.pkl")
        else:
            print("[!] result.pkl не найден (будет создан новый)")

        all_parsed_records = []

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(120)) as session:
            # Парсинг UA
            print("\n" + "=" * 80)
            print(" ПАРСИНГ UA РЕГИОНА")
            print("=" * 80)
            ua_url = input("Введите UA URL (или Enter чтобы пропустить): ").strip()

            if ua_url:
                if "store.playstation.com" not in ua_url or "/ru-ua/" not in ua_url:
                    print("[!] Неверный формат UA URL, пропускаем...")
                else:
                    ua_url = ua_url.rstrip('/')
                    is_concept = "concept" in ua_url

                    print(f"[OK] UA URL: {ua_url}")
                    print(f"  Тип: {'concept' if is_concept else 'product'}")

                    # Разворачиваем concept если нужно
                    if is_concept:
                        print("\n  Разворачивание concept...")
                        ua_product_urls = await unquote(session, ua_url)
                        if not ua_product_urls:
                            print("  ✗ Не удалось развернуть concept")
                            ua_product_urls = []
                        else:
                            print(f"  [OK] Получено {len(ua_product_urls)} product URLs")
                    else:
                        ua_product_urls = [ua_url]

                    # Парсим UA (только UA регион, не TR и IN)
                    if ua_product_urls:
                        print("\n  Парсинг UA региона (только UA цены)...")
                        for url in ua_product_urls:
                            parsed_data = await parse(session, url, regions=["UA"])
                            if parsed_data:
                                all_parsed_records.extend(parsed_data)
                                print(f"  [OK] Спарсено: {len(parsed_data)} запись(ей)")
                                for record in parsed_data:
                                    print(f"    • {record.get('name')} - {record.get('region')} - {record.get('price_rub', 0):.2f} RUB")
                            else:
                                print(f"  ✗ Не удалось спарсить {url}")
            else:
                print("⊘ UA парсинг пропущен")

            # Парсинг TR
            print("\n" + "=" * 80)
            print(" ПАРСИНГ TR РЕГИОНА")
            print("=" * 80)
            tr_url = input("Введите TR URL (или Enter чтобы пропустить): ").strip()

            if tr_url:
                if "store.playstation.com" not in tr_url or "/en-tr/" not in tr_url:
                    print("[!] Неверный формат TR URL, пропускаем...")
                else:
                    tr_url = tr_url.rstrip('/')
                    is_tr_concept = "concept" in tr_url

                    print(f"[OK] TR URL: {tr_url}")
                    print(f"  Тип: {'concept' if is_tr_concept else 'product'}")

                    # Разворачиваем concept если нужно
                    if is_tr_concept:
                        print("\n  Разворачивание concept...")
                        tr_product_urls = await unquote(session, tr_url)
                        if not tr_product_urls:
                            print("  ✗ Не удалось развернуть concept")
                            tr_product_urls = []
                        else:
                            print(f"  [OK] Получено {len(tr_product_urls)} product URLs")
                    else:
                        tr_product_urls = [tr_url]

                    # Парсим TR
                    if tr_product_urls:
                        print("\n  Парсинг...")
                        for url in tr_product_urls:
                            parsed_data = await parse_tr(session, url)
                            if parsed_data:
                                all_parsed_records.extend(parsed_data)
                                print(f"  [OK] Спарсено: {len(parsed_data)} запись(ей)")
                                for record in parsed_data:
                                    print(f"    • {record.get('name')} - TR - {record.get('price_rub', 0):.2f} RUB")
                            else:
                                print(f"  ✗ Не удалось спарсить {url}")
            else:
                print("⊘ TR парсинг пропущен")

            # Парсинг IN
            print("\n" + "=" * 80)
            print(" ПАРСИНГ IN РЕГИОНА")
            print("=" * 80)
            in_url = input("Введите IN URL (или Enter чтобы пропустить): ").strip()

            if in_url:
                if "store.playstation.com" not in in_url or "/en-in/" not in in_url:
                    print("[!] Неверный формат IN URL, пропускаем...")
                else:
                    in_url = in_url.rstrip('/')
                    is_in_concept = "concept" in in_url

                    print(f"[OK] IN URL: {in_url}")
                    print(f"  Тип: {'concept' if is_in_concept else 'product'}")

                    # Разворачиваем concept если нужно
                    if is_in_concept:
                        print("\n  Разворачивание concept...")
                        in_product_urls = await unquote(session, in_url)
                        if not in_product_urls:
                            print("  ✗ Не удалось развернуть concept")
                            in_product_urls = []
                        else:
                            print(f"  [OK] Получено {len(in_product_urls)} product URLs")
                    else:
                        in_product_urls = [in_url]

                    # Парсим IN
                    if in_product_urls:
                        print("\n  Парсинг...")
                        for url in in_product_urls:
                            parsed_data = await parse_in(session, url)
                            if parsed_data:
                                all_parsed_records.extend(parsed_data)
                                print(f"  [OK] Спарсено: {len(parsed_data)} запись(ей)")
                                for record in parsed_data:
                                    print(f"    • {record.get('name')} - IN - {record.get('price_rub', 0):.2f} RUB")
                            else:
                                print(f"  ✗ Не удалось спарсить {url}")
            else:
                print("⊘ IN парсинг пропущен")

            # Итого
            print("\n" + "=" * 80)
            print(" ИТОГО СПАРСЕНО")
            print("=" * 80)
            if not all_parsed_records:
                print("✗ Ничего не спарсено!")
                return

            # Разделяем записи по регионам
            ua_records = [r for r in all_parsed_records if r.get("region") == "UA"]
            tr_records = [r for r in all_parsed_records if r.get("region") == "TR"]
            in_records = [r for r in all_parsed_records if r.get("region") == "IN"]

            print(f"[OK] UA записей: {len(ua_records)}")
            print(f"[OK] TR записей: {len(tr_records)}")
            print(f"[OK] IN записей: {len(in_records)}")

            # Матчинг и объединение
            print("\n" + "=" * 80)
            print(" МАТЧИНГ И ОБЪЕДИНЕНИЕ ДАННЫХ")
            print("=" * 80)

            final_records = []

            # 1. Добавляем UA записи как есть (они полные)
            final_records.extend(ua_records)
            print(f"[OK] Добавлено {len(ua_records)} UA записей")

            # 2. Матчим и объединяем TR записи с UA данными
            if tr_records and ua_records:
                print(f"\n Матчинг TR записей ({len(tr_records)}) с UA...")
                tr_matches = match_products_by_id(ua_records, tr_records, "TR")

                for ua_item, tr_item in tr_matches:
                    merged_tr = merge_region_data(ua_item, tr_item, "TR")
                    final_records.append(merged_tr)

                print(f"[OK] Создано {len(tr_matches)} полных TR записей")

                # Добавляем несовпавшие TR записи как есть (неполные, но хоть что-то)
                matched_tr_ids = {tr_item.get("id") for _, tr_item in tr_matches}
                unmatched_tr = [item for item in tr_records if item.get("id") not in matched_tr_ids]
                if unmatched_tr:
                    print(f"[!] {len(unmatched_tr)} TR записей не смогли сматчиться (добавлены как есть)")
                    final_records.extend(unmatched_tr)
            elif tr_records:
                print(f"\n[!] TR записи ({len(tr_records)}) добавлены без матчинга (нет UA данных)")
                final_records.extend(tr_records)

            # 3. Матчим и объединяем IN записи с UA данными
            if in_records and ua_records:
                print(f"\n Матчинг IN записей ({len(in_records)}) с UA...")
                in_matches = match_products_by_id(ua_records, in_records, "IN")

                for ua_item, in_item in in_matches:
                    merged_in = merge_region_data(ua_item, in_item, "IN")
                    final_records.append(merged_in)

                print(f"[OK] Создано {len(in_matches)} полных IN записей")

                # Добавляем несовпавшие IN записи как есть
                matched_in_ids = {in_item.get("id") for _, in_item in in_matches}
                unmatched_in = [item for item in in_records if item.get("id") not in matched_in_ids]
                if unmatched_in:
                    print(f"[!] {len(unmatched_in)} IN записей не смогли сматчиться (добавлены как есть)")
                    final_records.extend(unmatched_in)
            elif in_records:
                print(f"\n[!] IN записи ({len(in_records)}) добавлены без матчинга (нет UA данных)")
                final_records.extend(in_records)

            print("\n" + "=" * 80)
            print(" ИТОГО ФИНАЛЬНЫХ ЗАПИСЕЙ")
            print("=" * 80)
            print(f"[OK] Всего: {len(final_records)} записей")
            for record in final_records:
                print(f"  • {record.get('name')} ({record.get('edition') or 'базовая'}) - {record.get('region')} - {record.get('price_rub', 0):.2f} RUB")

            # Обрабатываем издания с PS Plus без цены (после объединения всех регионов)
            print("\n" + "=" * 80)
            print(" ОБРАБОТКА PS PLUS ИЗДАНИЙ БЕЗ ЦЕНЫ")
            print("=" * 80)
            initial_count = len(final_records)
            final_records = process_ps_plus_only_editions(final_records)
            if len(final_records) != initial_count:
                print(f"[OK] Обработано: было {initial_count}, стало {len(final_records)} записей")
            else:
                print("[OK] Все издания имеют цены или не требуют обработки")

            # Проверяем и обновляем result.pkl
            print("\n" + "=" * 80)
            print(" ОБНОВЛЕНИЕ result.pkl")
            print("=" * 80)

            found_items = []
            new_items = []

            # Проверяем каждую запись на существование
            for record in final_records:
                matches = find_in_result(
                    existing_result,
                    record.get("name", ""),
                    record.get("edition"),
                    record.get("description"),
                    record.get("region")
                )

                if matches:
                    # Товар уже есть - обновляем
                    found_items.append((record, matches[0]))
                else:
                    # Новый товар
                    new_items.append(record)

            # Обновляем существующие товары
            if found_items:
                print(f"\n Обновление существующих товаров ({len(found_items)}):")
                for record, (idx, existing_item) in found_items:
                    # Обновляем существующую запись
                    existing_result[idx].update({
                        'price_rub': record.get('price_rub', existing_item.get('price_rub', 0)),
                        'price_old_rub': record.get('price_old_rub', existing_item.get('price_old_rub', 0)),
                        'ps_plus_price': record.get('ps_plus_price', existing_item.get('ps_plus_price')),
                        'ea_play_price': record.get('ea_play_price', existing_item.get('ea_play_price')),
                        'discount': record.get('discount', existing_item.get('discount', '')),
                        'discount_end': record.get('discount_end', existing_item.get('discount_end')),
                        'rating': record.get('rating', existing_item.get('rating', 0.0)),
                        'image': record.get('image', existing_item.get('image', '')),
                    })
                    print(f"  [OK] Обновлен: {record.get('name')} - {record.get('region')}")

            # Добавляем новые товары
            if new_items:
                print(f"\n➕ Добавление новых товаров ({len(new_items)}):")
                for record in new_items:
                    existing_result.append(record)
                    print(f"  [OK] Добавлен: {record.get('name')} - {record.get('region')}")

            # Удаляем возможные дубликаты (дополнительная защита)
            initial_count = len(existing_result)
            uni(existing_result)
            duplicates_removed = initial_count - len(existing_result)

            if duplicates_removed > 0:
                print(f"\n🧹 Удалено дубликатов: {duplicates_removed}")

            # Сохраняем
            with open("result.pkl", "wb") as file:
                pickle.dump(existing_result, file)
            print(f"\n[OK] result.pkl обновлен ({len(existing_result)} записей)")
            print(f"  • Обновлено: {len(found_items)}")
            print(f"  • Добавлено: {len(new_items)}")
            if duplicates_removed > 0:
                print(f"  • Удалено дубликатов: {duplicates_removed}")

            # Выбор действия
            print("\n" + "=" * 80)
            print(" ЧТО ДЕЛАТЬ ДАЛЬШЕ?")
            print("=" * 80)
            print("1. Только сохранить в result.pkl (уже сохранено)")
            print("2. Загрузить только спарсенные записи в БД")
            print("3. Загрузить весь result.pkl в БД")
            print("=" * 80)
            action = input("\nВыберите действие (1, 2 или 3): ").strip()

            if action == "1":
                print("\n[OK] Готово! Изменения сохранены в result.pkl")
                return
            elif action == "2":
                print("\n" + "=" * 80)
                print(" ЗАГРУЗКА СПАРСЕННЫХ ЗАПИСЕЙ В БД")
                print("=" * 80)
                print(f"[OK] Будет загружено {len(final_records)} записей")
                await process_specific_products_to_db(final_records, promo, start)
                return
            elif action == "3":
                print("\n" + "=" * 80)
                print(" РЕЖИМ ОЧИСТКИ БД")
                print("=" * 80)
                print("1. Очистить БД перед вставкой")
                print("2. Добавить без очистки")
                print("=" * 80)
                clear_mode = input("\nВыберите режим (1 или 2): ").strip()
                clear_db = clear_mode == "1"
                await process_and_save_to_db(existing_result, promo, start, clear_db=clear_db)
                return
            else:
                print("\n✗ Неверный выбор!")
                return

        return

    elif mode != "1":
        print("\n Неверный выбор! Введите 1, 2, 3 или 4")
        return

    # Режим 1 - полный парсинг или ограниченный (для тестов)
    # Сначала спрашиваем тип парсинга
    print("\n" + "=" * 80)
    print(" РЕЖИМ 1 - ПАРСИНГ ТОВАРОВ")
    print("=" * 80)
    print("\n Выберите тип парсинга:")
    print(" 1 - Полный парсинг (все товары)")
    print(" 2 - Тестовый парсинг (500 товаров)")
    print("=" * 80)

    parse_type = input("\n Введите номер (1 или 2): ").strip()

    if parse_type == "2":
        print("\n" + "=" * 80)
        print(" РЕЖИМ ТЕСТОВОГО ПАРСИНГА (500 товаров)")
        print("=" * 80)
        limit_products = 500
    elif parse_type == "1" or parse_type == "":
        # По умолчанию полный парсинг
        print("\n" + "=" * 80)
        print(" РЕЖИМ ПОЛНОГО ПАРСИНГА")
        print("=" * 80)
        limit_products = None  # Без ограничений
    else:
        print("\n[!] Неверный выбор! Используется полный парсинг по умолчанию")
        print("=" * 80)
        print(" РЕЖИМ ПОЛНОГО ПАРСИНГА")
        print("=" * 80)
        limit_products = None  # Без ограничений

    start = perf_counter()
    await add_update_table()

    connector = aiohttp.TCPConnector(
        limit=30,
        limit_per_host=10,
        keepalive_timeout=30,
        enable_cleanup_closed=True,
        force_close=False,
    )
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120, connect=30), connector=connector) as session:
        # Get promo (подписки PS Plus)
        if os.path.exists("promo.pkl"):
            print("\n" + "=" * 80)
            print(" НАЙДЕН promo.pkl - ПРОПУСКАЕМ ПОЛУЧЕНИЕ ПРОМО")
            print("=" * 80)
            with open("promo.pkl", "rb") as file:
                promo_data = pickle.load(file)

            # Проверяем формат (старый список или новый dict)
            if isinstance(promo_data, dict):
                promo = promo_data
                print(f" Загружено из кеша: Extra={len(promo.get('Extra', set()))}, Deluxe={len(promo.get('Deluxe', set()))}")
            else:
                # Старый формат - конвертируем в новый
                all_set = set(promo_data) if promo_data else set()
                promo = {
                    'Extra': all_set,
                    'Deluxe': set(),
                    'All': all_set
                }
                print(f" Загружено {len(all_set)} промо из кеша (старый формат, конвертировано)")
            print(f" Экономия времени: ~2-3 минуты")
        else:
            promo = await get_all_ps_plus_subscriptions(session)
            with open("promo.pkl", "wb") as file:
                pickle.dump(promo, file)
            print(f"[OK] Промо сохранено в promo.pkl")

        # Get products URLs (with cache)
        if os.path.exists("products.pkl"):
            print("\n" + "=" * 80)
            print(" НАЙДЕН products.pkl - ПРОПУСКАЕМ ПОЛУЧЕНИЕ И РАЗВОРАЧИВАНИЕ URL")
            print("=" * 80)
            with open("products.pkl", "rb") as file:
                products = pickle.load(file)
            print(f" Загружено {len(products)} product URLs из кеша")
            print(f" Экономия времени: ~5-10 минут")
            print(" Переход к парсингу продуктов...")
        else:
            # Get page URLs
            print("\n" + "=" * 80)
            print(" Получение URL страниц")
            print("=" * 80)

            base_categories = [
                "https://store.playstation.com/ru-ua/pages/browse",
                "https://store.playstation.com/ru-ua/category/51c9aa7a-c0c7-4b68-90b4-328ad11bf42e",  # Addons
                "https://store.playstation.com/ru-ua/category/3c49d223-9344-4009-b296-08e168854749",  # Items
            ]

            extra_categories = parser_config.EXTRA_CATEGORIES

            print(f" Парсинг основных категорий: {len(base_categories)}")
            pages_tasks = [get_pages(session, url) for url in base_categories]
            pages_results = await asyncio.gather(*pages_tasks)
            pages = sum(pages_results, [])

            print(f" Получено {len(pages)} страниц из основных категорий")

            # Get extra category pages
            print(f"\n Парсинг дополнительных категорий: {len(extra_categories)}")
            extra_pages_tasks = [get_pages(session, url) for url in extra_categories]
            extra_pages_results = await asyncio.gather(*extra_pages_tasks)
            extra_pages = sum(extra_pages_results, [])

            print(f" Получено {len(extra_pages)} страниц из дополнительных категорий")
            print(f" Всего страниц: {len(pages) + len(extra_pages)}")

            # Объединяем все страницы
            all_pages = pages + extra_pages

            # Get product URLs
            print("\n" + "=" * 80)
            print(" Получение URL продуктов")
            print("=" * 80)

            urls = []
            shift = parser_config.BATCH_SIZE_PAGES
            products_start = perf_counter()

            for i in range(0, len(all_pages), shift):
                # Перезагружаем конфигурацию на каждой итерации
                parser_config.load_config()
                shift = parser_config.BATCH_SIZE_PAGES

                _urls = await asyncio.gather(*[get_products(session, all_pages[j]) for j in range(i, min(len(all_pages), i+shift))])
                urls.extend(sum(_urls, []))
                await asyncio.sleep(parser_config.SLEEP_BETWEEN_BATCHES)

                current = min(len(all_pages), i+shift)
                elapsed = perf_counter() - products_start
                print_progress_bar(current, len(all_pages), elapsed, prefix=" Получение URL", suffix=f"| Найдено: {len(urls)}")

            print()
            print(f" Получено {len(urls)} URL продуктов")
            # Add special products
            special_products = [
                "https://store.playstation.com/ru-ua/concept/10004507",
                "https://store.playstation.com/ru-ua/concept/10010783"
            ]
            urls.extend(special_products)

            urls = urls[::-1]  # Reverse for newest first

            # Unquote URLs
            print("\n" + "=" * 80)
            print(" Разворачивание concept URLs")
            print("=" * 80)

            products = []
            shift = parser_config.BATCH_SIZE_UNQUOTE
            unquote_start = perf_counter()

            for i in range(0, len(urls), shift):
                # Перезагружаем конфигурацию на каждой итерации
                parser_config.load_config()
                shift = parser_config.BATCH_SIZE_UNQUOTE

                _products = sum(await asyncio.gather(*[unquote(session, urls[j]) for j in range(i, min(len(urls), i+shift))]), [])
                products.extend(_products)
                await asyncio.sleep(parser_config.SLEEP_BETWEEN_BATCHES)

                current = min(len(urls), i+shift)
                elapsed = perf_counter() - unquote_start
                print_progress_bar(current, len(urls), elapsed, prefix=" Разворачивание", suffix=f"| Развернуто: {len(products)}")

            print()
            print(f" Получено {len(products)} развернутых URLs")

            # Remove duplicates
            print("\n" + "=" * 80)
            print(" Удаление дубликатов product URLs")
            print("=" * 80)

            initial_count = len(products)

            # Используем умную нормализацию для удаления дубликатов
            # Ключ - (локаль, ID продукта), значение - оригинальный URL
            # Это позволит сохранить один и тот же продукт для разных локалей
            seen_products = {}
            unique_products = []
            duplicates_removed = 0

            for product_url in products:
                # Извлекаем локаль и ID продукта из URL
                # Формат: https://store.playstation.com/ru-ua/product/EP0001-CUSA05848_00-FARCRY5GAME00000
                url_parts = product_url.strip().rstrip('/').split('/')

                if len(url_parts) >= 5:
                    locale = url_parts[3]  # ru-ua, en-tr и т.д.
                    product_id = url_parts[-1].upper()  # EP0001-CUSA05848_00-FARCRY5GAME00000

                    # Ключ - комбинация локали и ID продукта
                    product_key = (locale, product_id)

                    if product_key not in seen_products:
                        seen_products[product_key] = product_url
                        unique_products.append(product_url)
                    else:
                        duplicates_removed += 1
                else:
                    # Если URL нестандартный, добавляем как есть
                    unique_products.append(product_url)

            products = unique_products

            print(f" Исходных URLs: {initial_count}")
            print(f" Дубликатов удалено: {duplicates_removed}")
            print(f" Уникальных URLs: {len(products)}")
            print(f" Экономия парсинга: ~{duplicates_removed} товаров (~{duplicates_removed * 5:.0f} сек)")
            print("=" * 80)

            with open("products.pkl", "wb") as file:
                pickle.dump(products, file)
            print(f" Product URLs сохранены в products.pkl")

        # Ограничиваем количество товаров для тестового режима
        if limit_products is not None and len(products) > limit_products:
            print(f"\n[!] Тестовый режим: ограничиваем парсинг до {limit_products} товаров")
            print(f"  Было: {len(products)} товаров")
            products = products[:limit_products]
            print(f"  Стало: {len(products)} товаров")

        # --- Checkpoint / Resume ---
        start_index = 0
        result = []
        db_cleared = False
        resuming = False
        checkpoint = load_checkpoint()

        if checkpoint and checkpoint.get("phase") == "parsing":
            cp_total = checkpoint.get("total_products", 0)
            cp_index = checkpoint.get("parsed_index", 0)
            cp_results = checkpoint.get("results_count", 0)
            cp_started = checkpoint.get("started_at", "?")
            cp_db_cleared = checkpoint.get("db_cleared", False)

            print("\n" + "=" * 80)
            print(" НАЙДЕН CHECKPOINT")
            print("=" * 80)
            print(f" Начат: {cp_started}")
            print(f" Прогресс: {cp_index}/{cp_total} товаров ({cp_results} записей)")
            print(f" БД уже очищена: {'да' if cp_db_cleared else 'нет'}")
            print("=" * 80)

            resume_choice = input("\n Продолжить с места остановки? (y/n, по умолчанию y): ").strip().lower()
            if resume_choice in ("", "y", "д", "yes", "да"):
                if os.path.exists("result.pkl"):
                    with open("result.pkl", "rb") as file:
                        result = pickle.load(file)
                    print(f" Загружено {len(result)} записей из result.pkl")
                start_index = cp_index
                db_cleared = cp_db_cleared
                resuming = True
                print(f" Продолжаем с позиции {start_index}/{len(products)}")
            else:
                print(" Начинаем заново...")
                remove_checkpoint()
        else:
            remove_checkpoint()

        # При свежем старте (не resume) — сразу очищаем БД и удаляем старый result.pkl
        if not resuming:
            print("\n Очистка БД перед новым парсингом...")
            await ensure_database_schema()
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                await prepare_sqlite_connection(db)
                await db.execute("DELETE FROM products")
                await db.commit()
            db_cleared = True
            if os.path.exists("result.pkl"):
                os.remove("result.pkl")
                print(" Старый result.pkl удален")
            print(" БД очищена, начинаем с чистого листа")

        started_at = datetime.now().isoformat()

        # --- Parse products ---
        print("\n" + "=" * 80)
        print(" Парсинг продуктов")
        if limit_products is not None:
            print(f" (Ограничение: {limit_products} товаров)")
        if start_index > 0:
            print(f" (Продолжение с позиции {start_index})")
        print("=" * 80)

        parse_logger = ParseLogger()
        shift = parser_config.BATCH_SIZE_PRODUCTS
        parse_start = perf_counter()

        total_products = len(products)
        save_interval = max(1, total_products // 100)
        next_save_threshold = start_index + save_interval
        current = start_index

        _interrupted = False

        try:
            for i in range(start_index, total_products, shift):
                parser_config.load_config()
                shift = parser_config.BATCH_SIZE_PRODUCTS

                batch_end = min(total_products, i + shift)
                _result = sum(await asyncio.gather(
                    *[parse(session, products[j], logger=parse_logger) for j in range(i, batch_end)]
                ), [])
                result.extend(_result)
                await asyncio.sleep(parser_config.SLEEP_BETWEEN_BATCHES)

                uni(result)

                current = batch_end
                elapsed = perf_counter() - parse_start
                print_progress_bar(current, total_products, elapsed, prefix=" Парсинг", suffix=f"| Спарсено: {len(result)}")

                # Сохраняем result.pkl и checkpoint после каждого батча
                with open("result.pkl", "wb") as file:
                    pickle.dump(result, file)
                save_checkpoint(started_at, total_products, current, len(result), db_cleared)

                # Инкрементальное сохранение в БД каждый 1%
                if current >= next_save_threshold or current >= total_products:
                    pct = round(current / total_products * 100)
                    print(f"\n  [{pct}%] Сохранение {len(result)} записей в БД...")
                    saved = await save_batch_to_db(result, promo, clear_db=(not db_cleared))
                    if not db_cleared:
                        db_cleared = True
                        save_checkpoint(started_at, total_products, current, len(result), db_cleared)
                    print(f"  [{pct}%] Сохранено {saved} продуктов в БД")
                    next_save_threshold = current + save_interval

        except (asyncio.CancelledError, KeyboardInterrupt):
            _interrupted = True
            print("\n\n  Парсинг прерван!")
            print(f"  Сохраняем прогресс: {len(result)} записей...")
            with open("result.pkl", "wb") as file:
                pickle.dump(result, file)
            save_checkpoint(started_at, total_products, current, len(result), db_cleared)
            print(f"  Checkpoint сохранен ({current}/{total_products}). При следующем запуске можно продолжить.")

        print()

    if not _interrupted:
        end = perf_counter()
        total_time = end - start
        print(f"\n Парсинг продуктов завершен за {total_time:.2f} сек ({total_time/60:.1f} мин)")

        with open("result.pkl", "wb") as file:
            pickle.dump(result, file)
        print(f" Результаты сохранены в result.pkl")

        # Финальное сохранение в БД
        await process_and_save_to_db(result, promo, start, clear_db=False)

        remove_checkpoint()
        print(" Checkpoint удален (парсинг завершен)")

    parse_logger.log_summary(total_products=total_products, parsed_count=len(result))


if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n  Парсинг прерван пользователем")
    finally:
        print("\n До свидания!")
