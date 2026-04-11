import aiohttp
from typing import Dict, Optional
import logging
from config.settings import settings
from app.api.payment_utils import resolve_payment_return_url

logger = logging.getLogger(__name__)

# Константы для API
PAYMENT_URL = "https://digiseller.market/asp2/pay.asp"
BASE_URL = "https://digiseller.market"

# Константы платформ PlayStation
PS4_PLATFORM_ID = "297502"
PS5_PLATFORM_ID = "297503"

# Заголовки для имитации браузера
BROWSER_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "ru,en;q=0.9,ka;q=0.8",
    "cache-control": "no-cache",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://plati.market",
    "pragma": "no-cache",
    "priority": "u=0, i",
    "referer": "https://plati.market/",
    "sec-ch-ua": '"Chromium";v="136", "YaBrowser";v="25.6", "Not.A/Brand";v="99", "Yowser";v="2.5"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "cross-site",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 YaBrowser/25.6.0.0 Safari/537.36",
}


class PaymentAPIError(Exception):
    """Исключение для ошибок API оплаты"""
    pass


class PlatiMarketAPI:
    """API для генерации ссылок оплаты с plati.market"""

    def __init__(self):
        """Инициализация API клиента"""
        pass

    def _get_fail_page_url(self) -> str:
        return resolve_payment_return_url(settings.PUBLIC_APP_URL, settings.DIGISELLER_FAILPAGE_URL)

    def _get_unit_cnt_for_trl_price(self, trl_price: float) -> str:
        """
        Определяет unit_cnt (курс конвертации) в зависимости от цены в турецких лирах
        
        Тарифы:
        от 250 TL: 3.45 ₽ за 1 TL
        от 300 TL: 3.35 ₽ за 1 TL  
        от 1000 TL: 3.32 ₽ за 1 TL
        от 2000 TL: 3.28 ₽ за 1 TL
        """
        if trl_price >= 2000:
            return "328"  # 3.28 * 100
        elif trl_price >= 1000:
            return "332"  # 3.32 * 100
        elif trl_price >= 300:
            return "335"  # 3.35 * 100
        elif trl_price >= 250:
            return "345"  # 3.45 * 100
        else:
            # Для цен меньше 250 TL используем базовый курс
            return "250"  # Базовый курс 2.50

    def _create_payment_data(
        self,
        platform_id: str,
        game: str,
        email: str,
        password: str,
        price: float,
        trl_price: Optional[float] = None,
        twofa_code: str = "",
    ) -> Dict[str, str]:
        """Создает данные для POST запроса к API оплаты"""
        
        # Определяем курс конвертации на основе цены в турецких лирах
        if trl_price is not None:
            unit_cnt = self._get_unit_cnt_for_trl_price(trl_price)
            logger.info(f"📊 TRL price: {trl_price} TL → unit_cnt: {unit_cnt} (rate: {float(unit_cnt)/100:.2f} ₽/TL)")
        else:
            unit_cnt = "250"  # Базовый курс для товаров без TRL цены
            logger.info(f"📊 No TRL price provided → using default unit_cnt: {unit_cnt}")
        
        fail_page_url = self._get_fail_page_url()

        return {
            # Пользовательские данные
            "Option_radio_209425": platform_id,  # ID платформы (PS4/PS5)
            "Option_text_209426": game,  # Название игры
            "Option_text_212008": email,  # PSN почта
            "Option_text_212009": password,  # PSN пароль
            "Option_text_596424": twofa_code,  # 2FA код (опционально)
            # Фиксированные поля для конкретного товара на plati.market
            "ID_D": "3401037",  # ID товара
            "Agent": "605064",  # ID агента/партнера
            "FailPage": fail_page_url,
            "failpage": fail_page_url,
            "customerid": "1eb247c2d64a4f59ab729e24d9131fcb",  # ID сессии покупателя
            "vz": "d92d1031-a719-4670-8947-1e28cb40670f",  # Идентификатор визита
            "promocode": "",
            "lang": "ru-RU",
            "product_id": "3401037",
            "_ow": "1",
            "TypeCurr": "RUR",
            "Email": "",
            "unit_amount": str(int(price)),
            "unit_cnt": unit_cnt,
        }

    def _build_full_url(self, redirect_url: str) -> str:
        """Преобразует относительный URL в абсолютный"""
        if redirect_url.startswith("/"):
            return f"{BASE_URL}{redirect_url}"
        elif redirect_url.startswith("http"):
            return redirect_url
        else:
            return f"{BASE_URL}/asp2/{redirect_url}"

    async def _send_payment_request(self, payment_data: Dict[str, str]) -> str:
        """Отправляет POST запрос и возвращает URL редиректа"""
        try:
            # Логируем данные запроса для отладки
            game_name = payment_data.get("Option_text_209426", "Unknown")
            price = payment_data.get("unit_amount", "Unknown")
            platform_id = payment_data.get("Option_radio_209425", "Unknown")
            
            logger.info(f"💰 DigitalSeller payment request: game='{game_name}', price={price} RUB, platform_id={platform_id}")
            logger.debug(f"Full payment data: {payment_data}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url=PAYMENT_URL,
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
                            raise PaymentAPIError("Редирект не найден в ответе сервера")
                    else:
                        response_text = await response.text()
                        logger.error(f"Unexpected payment API response status: {response.status}, body: {response_text}")
                        raise PaymentAPIError(f"Неожиданный статус ответа: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Payment API request failed: {str(e)}")
            raise PaymentAPIError(f"Ошибка соединения с API оплаты: {str(e)}")

    async def get_payment_url(
        self, 
        platform: str, 
        game: str, 
        email: str, 
        password: str, 
        price: float,
        trl_price: Optional[float] = None,
        twofa_code: str = ""
    ) -> str:
        """
        Получает ссылку для оплаты игры

        Args:
            platform: Платформа PlayStation ('PS4' или 'PS5')
            game: Название игры для покупки
            email: PSN почта
            password: PSN пароль
            price: Цена товара в рублях
            trl_price: Цена товара в турецких лирах (для определения курса)
            twofa_code: Код двухфакторной аутентификации (если есть)

        Returns:
            Полная ссылка для перехода к оплате
            
        Raises:
            PaymentAPIError: При ошибке генерации ссылки
        """
        # Определяем ID платформы
        if platform.upper() == 'PS4':
            platform_id = PS4_PLATFORM_ID
        elif platform.upper() == 'PS5':
            platform_id = PS5_PLATFORM_ID
        else:
            raise PaymentAPIError(f"Неподдерживаемая платформа: {platform}")

        # Логируем параметры запроса
        logger.info(f"🎮 Generating payment URL: game='{game}', platform={platform}, price={price} RUB")

        # Создаем данные для запроса
        payment_data = self._create_payment_data(
            platform_id=platform_id,
            game=game,
            email=email,
            password=password,
            price=price,
            trl_price=trl_price,
            twofa_code=twofa_code,
        )

        # Отправляем запрос и получаем ссылку
        payment_url = await self._send_payment_request(payment_data)

        # Проверяем, что получили правильную ссылку
        if "pay_api.asp" in payment_url:
            logger.info(f"Payment URL generated successfully for game: {game}")
            return payment_url
        else:
            logger.error(f"Invalid payment URL received: {payment_url}")
            raise PaymentAPIError(f"Получена неверная ссылка оплаты")


# Глобальный экземпляр API
payment_api = PlatiMarketAPI()
