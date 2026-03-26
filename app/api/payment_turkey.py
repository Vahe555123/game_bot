"""
API для оплаты через карты пополнения PlayStation Store Turkey
Использует oplata.info для покупки карт нужного номинала
"""

import aiohttp
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Константы для API
OPLATA_URL = "https://www.oplata.info/asp2/pay.asp"
OPLATA_PAY_WM_URL = "https://www.oplata.info/asp2/pay_wm.asp"
BASE_URL = "https://www.oplata.info"

# ID товара на oplata.info для карт пополнения Турции
TURKEY_CARD_PRODUCT_ID = "4500532"
AGENT_ID = "605064"

# Карты пополнения и их option values
# Структура: номинал -> (option_value, is_available)
@dataclass
class CardDenomination:
    value: int  # Номинал в TL
    option_id: str  # ID опции в форме
    available: bool = True  # Доступна ли карта

# Номиналы карт пополнения для Турции
TURKEY_CARD_DENOMINATIONS = [
    CardDenomination(250, "4854825", True),
    CardDenomination(500, "4854826", True),
    CardDenomination(750, "4854827", True),
    CardDenomination(1000, "4854828", True),
    CardDenomination(1500, "4854829", True),
    CardDenomination(2000, "4854830", True),
    CardDenomination(2500, "4854831", False),  # out of stock
    CardDenomination(3000, "4854832", False),  # out of stock
    CardDenomination(4000, "4854833", False),  # out of stock
    CardDenomination(5000, "4854834", False),  # out of stock
]

# Заголовки для имитации браузера
BROWSER_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "ru,en;q=0.9",
    "cache-control": "no-cache",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.oplata.info",
    "referer": "https://www.oplata.info/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class TurkeyPaymentAPIError(Exception):
    """Исключение для ошибок API оплаты Турции"""
    pass


@dataclass
class CardPurchaseInfo:
    """Информация о покупке карты пополнения"""
    card: CardDenomination  # Выбранная карта
    total_value: int  # Номинал карты в TL
    game_price: int  # Цена игры в TL
    remaining_balance: int  # Остаток на кошельке после покупки игры
    quantity_map: Dict[int, int]  # Для совместимости: {номинал: 1}

    @property
    def cards(self) -> List[CardDenomination]:
        """Список карт (учитывая количестсво)"""
        # Если в quantity_map что-то есть (сейчас там только одна карта с количеством)
        # Возвращаем список [card, card, ...] столько раз, сколько quantity
        qty = self.quantity_map.get(self.card.value, 1)
        return [self.card] * qty

    @property
    def total_cards(self) -> int:
        """Общее количество карт"""
        return sum(self.quantity_map.values())

    def get_description_ru(self) -> str:
        """Получить описание покупки на русском"""
        qty = self.total_cards
        if qty > 1:
            message = f"Вы покупаете {qty} карты пополнения по {self.card.value} TL (итого {self.total_value} TL). "
        else:
            message = f"Вы покупаете карту пополнения на {self.total_value} TL. "
        message += f"Этого хватит для оплаты выбранного товара ({self.game_price} TL) в PS Store "

        if self.remaining_balance > 0:
            message += f"и {self.remaining_balance} TL останутся в Вашем кошельке на аккаунте PSN."
        else:
            message += "без остатка на кошельке."

        return message

    def get_description_en(self) -> str:
        """Получить описание покупки на английском"""
        qty = self.total_cards
        if qty > 1:
            message = f"You are purchasing {qty} top-up cards of {self.card.value} TL each (total {self.total_value} TL). "
        else:
            message = f"You are purchasing a {self.total_value} TL top-up card. "
        message += f"This will cover the cost of the selected item ({self.game_price} TL) in PS Store "

        if self.remaining_balance > 0:
            message += f"and {self.remaining_balance} TL will remain in your PSN wallet."
        else:
            message += "with no remaining balance."

        return message


class TurkeyPaymentAPI:
    """API для покупки карт пополнения PlayStation Store Turkey через oplata.info"""

    def __init__(self):
        """Инициализация API клиента"""
        self.available_cards = self._get_available_cards()

    def _get_available_cards(self) -> List[CardDenomination]:
        """Получить список доступных карт (можно обновлять динамически)"""
        return [card for card in TURKEY_CARD_DENOMINATIONS if card.available]

    async def check_card_availability(self) -> Dict[int, bool]:
        """
        Проверить доступность карт на сайте
        Парсит страницу и проверяет атрибут disabled у input элементов
        """
        try:
            from bs4 import BeautifulSoup
            async with aiohttp.ClientSession() as session:
                url = f"{OPLATA_PAY_WM_URL}?id_d={TURKEY_CARD_PRODUCT_ID}&ai={AGENT_ID}&_ow=0"
                async with session.get(url, headers=BROWSER_HEADERS) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        availability = {}

                        for card in TURKEY_CARD_DENOMINATIONS:
                            # Ищем input с нужным value
                            input_el = soup.find('input', {'value': card.option_id})
                            if input_el:
                                # Если есть атрибут disabled, значит карта недоступна
                                is_disabled = input_el.has_attr('disabled')
                                availability[card.value] = not is_disabled
                            else:
                                # Если инпута нет, считаем недоступной (или доступной по умолчанию? лучше False)
                                availability[card.value] = False

                        return availability
        except Exception as e:
            logger.error(f"Error checking card availability: {e}")

        # Возвращаем текущий статус по умолчанию
        return {card.value: card.available for card in TURKEY_CARD_DENOMINATIONS}

    def calculate_cards_needed(self, game_price_tl: float) -> CardPurchaseInfo:
        """
        Выбрать оптимальную карту и количество для покрытия цены игры.

        Алгоритм:
        1. Рассматриваем все ДОСТУПНЫЕ номиналы карт.
        2. Для каждого номинала считаем, сколько штук нужно, чтобы покрыть цену.
        3. Выбираем вариант с минимальным "хвостом" (остатком), затем с минимальным количеством карт.

        Args:
            game_price_tl: Цена игры (TL)

        Returns:
            CardPurchaseInfo
        """
        price = int(game_price_tl)

        if price <= 0:
            raise TurkeyPaymentAPIError("Цена игры должна быть больше 0")

        if not self.available_cards:
            # Попробуем обновить доступность, если список пуст (хотя это делает внешний код обычно)
            # В данном контексте просто ошибка
            raise TurkeyPaymentAPIError("Нет доступных карт пополнения")

        # Структура для выбора: (CardDenomination, quantity, remainder, total_cost)
        candidates = []

        for card in self.available_cards:
            if not card.available:
                 continue

            # Сколько карт нужно этого номинала
            import math
            quantity = math.ceil(price / card.value)

            total_value = quantity * card.value
            remainder = total_value - price

            candidates.append({
                'card': card,
                'quantity': quantity,
                'remainder': remainder,
                'total_value': total_value
            })

        if not candidates:
             raise TurkeyPaymentAPIError("Все карты пополнения недоступны")

        # Сортировка кандидатов:
        # 1. По количеству карт (quantity) - чем меньше, тем лучше (ASC)
        # 2. По остатку (remainder) - чем меньше, тем лучше (ASC)
        # 3. По номиналу (value) - чем больше, тем лучше (DESC) - для эстетики (лучше 1x2000, чем 2x1000)

        candidates.sort(key=lambda x: (x['quantity'], x['remainder'], -x['card'].value))

        best = candidates[0]
        selected_card = best['card']
        quantity = best['quantity']
        remainder = best['remainder']
        total_value = best['total_value']

        logger.info(f"🇹🇷 Smart card selection: game_price={price} TL → "
                    f"Selected: {quantity}x {selected_card.value} TL (Total: {total_value} TL, Remainder: {remainder} TL)")

        return CardPurchaseInfo(
            card=selected_card,
            total_value=total_value,
            game_price=price,
            remaining_balance=remainder,
            quantity_map={selected_card.value: quantity}
        )

    def _create_payment_data(
        self,
        card: CardDenomination,
        quantity: int = 1,
        need_registration: bool = False
    ) -> Dict[str, str]:
        """Создает данные для POST запроса к API оплаты"""
        import uuid

        data = {
            "Lang": "ru-RU",
            "ID_D": TURKEY_CARD_PRODUCT_ID,
            "product_id": TURKEY_CARD_PRODUCT_ID,
            "Agent": AGENT_ID,
            "AgentN": "",
            "FailPage": f"https://x-box-store.ru/detail/{TURKEY_CARD_PRODUCT_ID}",
            "NoClearBuyerQueryString": "NoClear",
            "digiuid": str(uuid.uuid4()).upper(),
            "Curr_add": "",
            "TypeCurr": "API_5020_RUB",
            "_subcurr": "",
            "_ow": "0",
            "firstrun": "0",
            # Пробуем разные варианты параметра количества
            "product_cnt": str(quantity),
            "product_cnt_set": str(quantity),
            "cnt": str(quantity),
            "n": str(quantity),
            "Option_radio_1583279": card.option_id,
        }

        logger.info(f"🇹🇷 Creating payment data: card={card.value} TL, option_id={card.option_id}, quantity={quantity}")

        # Добавляем опцию регистрации аккаунта если нужно
        if need_registration:
            # TODO: Добавить ID опции регистрации для Турции если есть
            pass

        return data

    def _build_full_url(self, redirect_url: str) -> str:
        """Преобразует относительный URL в абсолютный"""
        if redirect_url.startswith("/"):
            return f"{BASE_URL}{redirect_url}"
        elif redirect_url.startswith("http"):
            return redirect_url
        else:
            return f"{BASE_URL}/asp2/{redirect_url}"

    async def _send_payment_request(self, payment_data: Dict[str, str]) -> str:
        """Отправляет POST запрос и возвращает URL для оплаты"""
        try:
            logger.info(f"💳 Turkey card payment request: data={payment_data}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url=OPLATA_URL,
                    headers=BROWSER_HEADERS,
                    data=payment_data,
                    allow_redirects=False,
                ) as response:
                    if response.status in [301, 302, 303, 307, 308]:
                        redirect_url = response.headers.get("Location")
                        if redirect_url:
                            full_url = self._build_full_url(redirect_url)
                            logger.info(f"Payment redirect received: {redirect_url}")
                            return full_url
                        else:
                            raise TurkeyPaymentAPIError("Редирект не найден в ответе сервера")
                    else:
                        response_text = await response.text()
                        logger.error(f"Unexpected API response status: {response.status}, body: {response_text[:500]}")
                        raise TurkeyPaymentAPIError(f"Неожиданный статус ответа: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Payment API request failed: {str(e)}")
            raise TurkeyPaymentAPIError(f"Ошибка соединения с API оплаты: {str(e)}")

    async def get_payment_url(
        self,
        game_price_tl: float,
        need_registration: bool = False
    ) -> Tuple[str, CardPurchaseInfo]:
        """
        Получает ссылку для оплаты карты пополнения.

        Умная автоматическая выборка:
        - Выбирает ОДНУ карту минимального номинала, покрывающую цену
        - Quantity всегда = 1 (на сайте можно выбрать только одну карту)

        Args:
            game_price_tl: Цена игры в турецких лирах
            need_registration: Нужна ли регистрация аккаунта

        Returns:
            Tuple: (URL для оплаты, информация о покупке карты)

        Raises:
            TurkeyPaymentAPIError: При ошибке генерации ссылки
        """
        # Выбираем одну карту, покрывающую цену
        purchase_info = self.calculate_cards_needed(game_price_tl)

        logger.info(f"🇹🇷 Turkey payment: game_price={game_price_tl} TL → "
                    f"card={purchase_info.total_value} TL, "
                    f"remaining={purchase_info.remaining_balance} TL")

        # Создаем данные для запроса
        quantity = purchase_info.quantity_map.get(purchase_info.card.value, 1)

        payment_data = self._create_payment_data(
            card=purchase_info.card,
            quantity=quantity,
            need_registration=need_registration
        )

        # Отправляем запрос и получаем ссылку
        payment_url = await self._send_payment_request(payment_data)

        return payment_url, purchase_info

    def get_direct_payment_url(self, denomination: int = 250, buyer_email: str = None, quantity: int = 1) -> str:
        """
        Получить прямую ссылку на страницу оплаты карты определенного номинала
        (без POST-запроса, просто URL)

        Args:
            denomination: Номинал карты (не используется для прямой ссылки)
            buyer_email: Email покупателя для автозаполнения
            quantity: Количество карт для автозаполнения
        """
        url = f"{OPLATA_PAY_WM_URL}?id_d={TURKEY_CARD_PRODUCT_ID}&ai={AGENT_ID}&_ow=0"
        if quantity > 1:
            url += f"&n={quantity}&product_cnt={quantity}"
        if buyer_email:
            from urllib.parse import quote
            url += f"&email={quote(buyer_email)}"
        return url


    async def get_card_price_rub(self, card_value: int) -> Optional[int]:
        """
        Получить цену карты в рублях с oplata.info через API price_options.asp

        Args:
            card_value: Номинал карты в TL

        Returns:
            Цена карты в рублях или None если не удалось получить
        """
        # Находим option_id для данного номинала
        card = None
        for c in TURKEY_CARD_DENOMINATIONS:
            if c.value == card_value:
                card = c
                break

        if not card:
            logger.warning(f"Card denomination {card_value} TL not found")
            return None

        try:
            import random
            from urllib.parse import quote

            # Формируем XML параметр: <response><option O="1583279" V="option_id"/></response>
            # 1583279 - это data-id для radio group карт Турции
            xml_param = f'<response><option O="1583279" V="{card.option_id}"/></response>'
            encoded_xml = quote(xml_param)

            async with aiohttp.ClientSession() as session:
                url = f"https://www.oplata.info/asp2/price_options.asp?p={TURKEY_CARD_PRODUCT_ID}&n=1&c=RUB&x={encoded_xml}&rnd={random.random()}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": f"https://www.oplata.info/asp2/pay_wm.asp?id_d={TURKEY_CARD_PRODUCT_ID}",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest"
                }
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        text = await response.text()
                        try:
                            import json
                            data = json.loads(text)
                            if data.get('curr') == 'RUB' and data.get('amount'):
                                price_rub = int(float(data['amount']))
                                logger.info(f"🇹🇷 Card {card_value} TL price: {price_rub} RUB")
                                return price_rub
                        except Exception as json_err:
                            logger.warning(f"JSON parse error: {json_err}, raw response: {text[:200]}")
        except Exception as e:
            logger.error(f"Error getting card price from oplata.info: {e}")

        return None

    async def get_card_price_rub_from_payment_url(self, payment_url: str) -> Optional[int]:
        """
        Получить цену карты в рублях, парся HTML страницу оплаты.

        Args:
            payment_url: URL страницы оплаты (pay_api.asp)

        Returns:
            Цена карты в рублях или None если не удалось получить
        """
        import re

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(payment_url, headers=BROWSER_HEADERS) as response:
                    if response.status == 200:
                        html = await response.text()

                        # Ищем цену в элементе <span id="price_value">625.00</span>
                        match = re.search(r'<span[^>]*id=["\']price_value["\'][^>]*>(\d+(?:\.\d+)?)</span>', html)
                        if match:
                            price_rub = int(float(match.group(1)))
                            logger.info(f"🇹🇷 Parsed price from payment page: {price_rub} RUB")
                            return price_rub

                        # Альтернативный поиск: price: 625 в JavaScript
                        match = re.search(r'price:\s*(\d+(?:\.\d+)?)', html)
                        if match:
                            price_rub = int(float(match.group(1)))
                            logger.info(f"🇹🇷 Parsed price from JS: {price_rub} RUB")
                            return price_rub

        except Exception as e:
            logger.error(f"Error parsing price from payment URL: {e}")

        return None

    async def get_all_cards_prices_rub(self) -> Dict[int, int]:
        """
        Получить цены всех доступных карт в рублях

        Returns:
            Словарь {номинал_TL: цена_RUB}
        """
        prices = {}
        for card in self.available_cards:
            price = await self.get_card_price_rub(card.value)
            if price:
                prices[card.value] = price
        return prices


# Глобальный экземпляр API
turkey_payment_api = TurkeyPaymentAPI()
