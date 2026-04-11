"""
API для оплаты через покупку игр на PlayStation UA Украина
Использует oplata.info для обработки платежей в UAH
"""

import aiohttp
from typing import Dict, Optional, Tuple
import logging
from dataclasses import dataclass
import re
from config.settings import settings
from app.api.payment_utils import resolve_payment_return_url

logger = logging.getLogger(__name__)

# Константы для API
OPLATA_URL = "https://www.oplata.info/asp2/pay.asp"
BASE_URL = "https://www.oplata.info"

# ID товара на oplata.info для покупки игр в Украине
UKRAINE_PRODUCT_ID = "3593163"
AGENT_ID = "605064"

# Лимиты суммы
MIN_UAH_AMOUNT = 250  # Минимальная сумма пополнения
MAX_UAH_AMOUNT = 7000  # Максимальная сумма пополнения

# Заголовки для имитации браузера
BROWSER_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "ru,en;q=0.9",
    "cache-control": "no-cache",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.oplata.info",
    "pragma": "no-cache",
    "referer": "https://www.oplata.info/asp2/pay_wm.asp?id_d=3593163&ai=605064&_ow=0",
    "sec-ch-ua": '"Chromium";v="136", "YaBrowser";v="25.6", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
}


def get_fail_page_url() -> str:
    return resolve_payment_return_url(settings.PUBLIC_APP_URL, settings.DIGISELLER_FAILPAGE_URL)


class UkrainePaymentAPIError(Exception):
    """Исключение для ошибок API оплаты Украины"""
    pass


@dataclass
class UkrainePaymentInfo:
    """Информация о платеже для Украины"""
    game_price: float  # Реальная цена игры в UAH
    topup_amount: float  # Сумма пополнения (может быть больше цены игры из-за минимума)
    remaining_balance: float  # Сколько останется на кошельке после покупки

    def get_description_ru(self) -> str:
        """Описание платежа на русском"""
        if self.remaining_balance > 0:
            return (
                f"Цена игры: {self.game_price:.0f} UAH. "
                f"Минимальная сумма пополнения: {MIN_UAH_AMOUNT} UAH. "
                f"После покупки на кошельке останется: {self.remaining_balance:.0f} UAH"
            )
        return f"Цена игры: {self.game_price:.0f} UAH"

    def get_description_en(self) -> str:
        """Описание платежа на английском"""
        if self.remaining_balance > 0:
            return (
                f"Game price: {self.game_price:.0f} UAH. "
                f"Minimum top-up: {MIN_UAH_AMOUNT} UAH. "
                f"Balance after purchase: {self.remaining_balance:.0f} UAH"
            )
        return f"Game price: {self.game_price:.0f} UAH"


class UkrainePaymentAPI:
    """API для покупки игр на PlayStation Store Ukraine через oplata.info"""

    def __init__(self):
        """Инициализация API клиента"""
        pass

    def _calculate_topup_amount(self, game_price: float) -> Tuple[float, float]:
        """
        Рассчитывает сумму пополнения с учетом минимума

        Args:
            game_price: Цена игры в UAH

        Returns:
            Tuple[сумма пополнения, остаток на кошельке]
        """
        if game_price < MIN_UAH_AMOUNT:
            # Если цена меньше минимума, пополняем на минимум
            topup_amount = MIN_UAH_AMOUNT
            remaining = topup_amount - game_price
            logger.info(f"💰 Game price {game_price} UAH < minimum {MIN_UAH_AMOUNT} UAH, will topup {topup_amount} UAH (remaining: {remaining} UAH)")
            return topup_amount, remaining
        else:
            # Если цена больше или равна минимуму, пополняем на цену игры
            return game_price, 0.0

    def _create_payment_data(
        self,
        game: str,
        email: str,
        password: str,
        uah_amount: float,
        twofa_code: str = "",
    ) -> Dict[str, str]:
        """
        Создает данные для POST запроса к API оплаты Украины

        Поля формы (ID получены с https://www.oplata.info/asp2/pay_wm.asp?id_d=3593163):
        - Option_text_277928: название игры
        - Option_text_277929: PSN Email (required)
        - Option_text_277932: PSN Password (required)
        - Option_text_2254506: 2FA backup code
        - Option_checkbox_3344172: согласие с риском блокировки (value=13242692)
        """

        fail_page_url = get_fail_page_url()

        data = {
            # Фиксированные поля для товара
            "ID_D": UKRAINE_PRODUCT_ID,
            "Agent": AGENT_ID,
            "FailPage": fail_page_url,
            "failpage": fail_page_url,
            "Lang": "ru-RU",
            "TypeCurr": "RUR",  # Валюта оплаты - рубли
            "_ow": "0",
            "product_cnt": "1",
            "unit_cnt": str(int(uah_amount)),  # Количество UAH

            # Пользовательские данные
            "Option_text_277928": game,  # Название игры
            "Option_text_277929": email,  # PSN Email
            "Option_text_277932": password,  # PSN Password
            "Option_text_2254506": twofa_code,  # 2FA backup code
            "Option_checkbox_3344172": "13242692",  # Согласие с риском блокировки
        }

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
            game_name = payment_data.get("Option_text_277928", "Unknown")
            uah_amount = payment_data.get("unit_cnt", "Unknown")

            logger.info(f"💰 Ukraine payment request: game='{game_name}', amount={uah_amount} UAH")
            logger.debug(f"Full payment data: {payment_data}")

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
                            raise UkrainePaymentAPIError("Редирект не найден в ответе сервера")
                    else:
                        response_text = await response.text()
                        logger.error(f"Unexpected API response status: {response.status}, body: {response_text[:500]}")
                        raise UkrainePaymentAPIError(f"Неожиданный статус ответа: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Payment API request failed: {str(e)}")
            raise UkrainePaymentAPIError(f"Ошибка соединения с API оплаты: {str(e)}")

    async def get_payment_price_rub_from_url(self, payment_url: str) -> Optional[int]:
        """
        Получить итоговую цену оплаты в рублях, распарсив страницу oplata.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(payment_url, headers=BROWSER_HEADERS) as response:
                    if response.status != 200:
                        logger.warning(
                            f"Unable to fetch Ukraine payment page for RUB price: status={response.status}"
                        )
                        return None

                    html = await response.text()

                    match = re.search(r'<span[^>]*id=["\']price_value["\'][^>]*>(\d+(?:\.\d+)?)</span>', html)
                    if match:
                        price_rub = int(float(match.group(1)))
                        logger.info(f"Parsed Ukraine payment price from page: {price_rub} RUB")
                        return price_rub

                    match = re.search(r'price:\s*(\d+(?:\.\d+)?)', html)
                    if match:
                        price_rub = int(float(match.group(1)))
                        logger.info(f"Parsed Ukraine payment price from JS: {price_rub} RUB")
                        return price_rub

                    logger.warning("Ukraine payment page does not contain a parsable RUB price")
        except Exception as e:
            logger.error(f"Error parsing Ukraine payment price from URL: {e}")

        return None

    def get_direct_payment_url(self, buyer_email: str = None) -> str:
        """
        Получить прямую ссылку на страницу оплаты
        Используется для редиректа пользователя на страницу оплаты без POST-запроса

        Args:
            buyer_email: Email покупателя для автозаполнения
        """
        url = f"https://www.oplata.info/asp2/pay_wm.asp?id_d={UKRAINE_PRODUCT_ID}&ai={AGENT_ID}&_ow=0"
        if buyer_email:
            from urllib.parse import quote
            url += f"&email={quote(buyer_email)}"
        return url

    async def get_payment_url(
        self,
        game: str,
        email: str,
        password: str,
        uah_price: float,
        twofa_code: str = ""
    ) -> Tuple[str, UkrainePaymentInfo]:
        """
        Получает ссылку для оплаты игры в Украине

        Args:
            game: Название игры для покупки
            email: PSN почта
            password: PSN пароль
            uah_price: Цена товара в гривнах (UAH)
            twofa_code: Код двухфакторной аутентификации (если есть)

        Returns:
            Tuple[payment_url, UkrainePaymentInfo] - ссылка и информация о платеже

        Raises:
            UkrainePaymentAPIError: При ошибке генерации ссылки
        """
        # Проверяем максимум
        if uah_price > MAX_UAH_AMOUNT:
            raise UkrainePaymentAPIError(f"Максимальная сумма покупки: {MAX_UAH_AMOUNT} UAH (указано: {uah_price} UAH)")

        # Рассчитываем сумму пополнения (с учетом минимума 250 UAH)
        topup_amount, remaining_balance = self._calculate_topup_amount(uah_price)

        # Создаем информацию о платеже
        payment_info = UkrainePaymentInfo(
            game_price=uah_price,
            topup_amount=topup_amount,
            remaining_balance=remaining_balance
        )

        # Логируем параметры запроса
        if remaining_balance > 0:
            logger.info(f"🇺🇦 Generating Ukraine payment URL: game='{game}', game_price={uah_price} UAH, topup={topup_amount} UAH (min), remaining={remaining_balance} UAH")
        else:
            logger.info(f"🇺🇦 Generating Ukraine payment URL: game='{game}', price={uah_price} UAH")

        # Создаем данные для запроса (используем topup_amount, а не uah_price)
        payment_data = self._create_payment_data(
            game=game,
            email=email,
            password=password,
            uah_amount=topup_amount,  # Используем сумму пополнения!
            twofa_code=twofa_code
        )

        # Отправляем запрос и получаем ссылку
        payment_url = await self._send_payment_request(payment_data)

        # Проверяем, что получили правильную ссылку
        if "pay_api.asp" in payment_url or "oplata.info" in payment_url:
            logger.info(f"✅ Ukraine payment URL generated: {payment_url}")
            return payment_url, payment_info
        else:
            logger.error(f"Invalid payment URL received: {payment_url}")
            raise UkrainePaymentAPIError(f"Получена неверная ссылка оплаты")


# Глобальный экземпляр API
ukraine_payment_api = UkrainePaymentAPI()
