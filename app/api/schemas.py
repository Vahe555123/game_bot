import re
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class RegionEnum(str, Enum):
    UA = "UA"
    TR = "TR"
    IN = "IN"

class PlatformEnum(str, Enum):
    PS4 = "PS4"
    PS5 = "PS5"


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validate_email_value(value: Optional[str], *, required: bool = False) -> Optional[str]:
    if value is None:
        if required:
            raise ValueError("Укажите email")
        return None

    normalized = value.strip()
    if not normalized:
        if required:
            raise ValueError("Укажите email")
        return None

    if not EMAIL_PATTERN.match(normalized):
        raise ValueError("Введите корректный email")

    return normalized

# Схемы для пользователя
class UserBase(BaseModel):
    telegram_id: int = Field(..., description="ID пользователя в Telegram")
    username: Optional[str] = Field(None, description="Username пользователя")
    first_name: Optional[str] = Field(None, description="Имя пользователя")
    last_name: Optional[str] = Field(None, description="Фамилия пользователя")
    preferred_region: RegionEnum = Field(RegionEnum.UA, description="Предпочитаемый регион")
    show_ukraine_prices: bool = Field(False, description="Показывать цены Украины")
    show_turkey_prices: bool = Field(True, description="Показывать цены Турции")
    show_india_prices: bool = Field(False, description="Показывать цены Индии")
    platform: Optional[PlatformEnum] = Field(None, description="PlayStation платформа")
    psn_email: Optional[str] = Field(None, description="Email для PSN аккаунта")

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    preferred_region: Optional[RegionEnum] = None
    show_ukraine_prices: Optional[bool] = None
    show_turkey_prices: Optional[bool] = None
    show_india_prices: Optional[bool] = None
    platform: Optional[PlatformEnum] = None
    psn_email: Optional[str] = None
    psn_password: Optional[str] = Field(None, description="PSN пароль (будет хеширован)")

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    has_psn_credentials: bool = Field(default=False, description="Наличие PSN данных")

    class Config:
        from_attributes = True

# Схемы для товара
class ProductBase(BaseModel):
    id: str = Field(..., description="ID товара из PlayStation Store")
    name: Optional[str] = Field(None, description="Полное название товара")
    main_name: Optional[str] = Field(None, description="Основное название товара")
    category: Optional[str] = Field(None, description="Категория товара")
    region: Optional[str] = Field(None, description="Регион (TR, UA, IN)")
    type: Optional[str] = Field(None, description="Тип продукта (Game, DLC, Bundle)")
    image: Optional[str] = Field(None, description="Ссылка на изображение")
    platforms: Optional[str] = Field(None, description="Поддерживаемые платформы")
    publisher: Optional[str] = Field(None, description="Издатель")
    rating: Optional[float] = Field(None, description="Рейтинг товара")
    edition: Optional[str] = Field(None, description="Издание игры")
    description: Optional[str] = Field(None, description="Описание товара")

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    # Состав и дополнительная информация
    compound: Optional[List[str]] = Field(None, description="Состав товара")
    info: Optional[List[str]] = Field(None, description="Дополнительная информация")
    tags: Optional[List[str]] = Field(None, description="Теги товара")

    # Цены
    price: Optional[float] = Field(None, description="Текущая цена")
    old_price: Optional[float] = Field(None, description="Старая цена")
    ps_price: Optional[float] = Field(None, description="Цена для PS Plus")
    ea_price: Optional[float] = Field(None, description="Цена для EA Access")

    # Подписки
    plus_types: Optional[str] = Field(None, description="Типы PS Plus доступа")
    ps_plus: Optional[int] = Field(None, description="Доступно в PS Plus")
    ea_access: Optional[str] = Field(None, description="Доступно в EA Access")
    ps_plus_collection: Optional[str] = Field(None, description="PS Plus коллекция (Extra/Deluxe)")

    # Скидки
    discount: Optional[float] = Field(None, description="Размер скидки в процентах")
    discount_end: Optional[str] = Field(None, description="Дата окончания скидки")

    # Локализация
    localization: Optional[str] = Field(None, description="Уровень локализации")

    # Статусы
    has_discount: bool = Field(False, description="Есть ли скидка")
    has_ps_plus: bool = Field(False, description="Доступно в PS Plus")
    has_ea_access: bool = Field(False, description="Доступно в EA Access")
    has_ps_plus_extra_deluxe: bool = Field(False, description="Доступно в PS Plus Extra/Deluxe")

    # Информация о регионе
    region_info: Optional[Dict[str, str]] = Field(None, description="Информация о регионе")
    current_price: Optional[float] = Field(None, description="Лучшая текущая цена")
    price_with_currency: Optional[str] = Field(None, description="Цена с валютой")

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj):
        """Кастомный метод для преобразования из ORM объекта"""
        if hasattr(obj, 'get_display_name'):
            data = {
                'id': obj.id,
                'name': obj.name,
                'main_name': obj.get_display_name(),
                'category': obj.category,
                'region': obj.region,
                'type': obj.type,
                'image': obj.image,
                'platforms': obj.platforms,
                'publisher': obj.publisher,
                'rating': obj.rating,
                'edition': obj.edition,
                'description': obj.description,
                'compound': obj.get_compound_list(),
                'info': obj.get_info_list(),
                'tags': obj.get_tags_list(),
                'price': obj.price,
                'old_price': obj.old_price,
                'ps_price': obj.ps_price,
                'ea_price': obj.ea_price,
                'plus_types': obj.plus_types,
                'ps_plus': obj.ps_plus,
                'ea_access': obj.ea_access,
                'ps_plus_collection': obj.ps_plus_collection,
                'discount': obj.discount,
                'discount_end': obj.discount_end,
                'localization': obj.localization,
                'has_discount': obj.has_discount,
                'has_ps_plus': obj.has_ps_plus,
                'has_ea_access': obj.has_ea_access,
                'has_ps_plus_extra_deluxe': obj.has_ps_plus_extra_deluxe,
                'region_info': obj.get_region_info(),
                'current_price': obj.get_current_price(),
                'price_with_currency': obj.get_price_with_currency()
            }
            return cls(**data)
        return super().model_validate(obj)

# Схемы для избранного
class FavoriteCreate(BaseModel):
    product_id: str = Field(..., description="ID товара")
    region: Optional[str] = Field(None, description="Регион товара (UA, TR, IN)")

class FavoriteProduct(BaseModel):
    """Упрощенная схема продукта для избранного"""
    id: str
    name: Optional[str] = None
    main_name: Optional[str] = None
    category: Optional[str] = None
    region: Optional[str] = None
    type: Optional[str] = None
    image: Optional[str] = None
    publisher: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    old_price: Optional[float] = None
    ps_price: Optional[float] = None
    discount: Optional[float] = None
    discount_end: Optional[str] = None
    rating: Optional[float] = None
    edition: Optional[str] = None
    has_discount: bool = False
    region_info: Optional[Dict[str, str]] = None
    current_price: Optional[float] = None

    class Config:
        from_attributes = True

class Favorite(BaseModel):
    id: int
    user_id: int
    product_id: str
    created_at: datetime
    product: FavoriteProduct

    class Config:
        from_attributes = True

# Схемы для ответов API
class ProductListResponse(BaseModel):
    products: List[Product]
    total: int
    page: int
    limit: int
    has_next: bool

class UserWithFavorites(User):
    favorite_products: List[Favorite] = []

# Схемы для фильтрации
class ProductFilter(BaseModel):
    category: Optional[str] = None
    region: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    has_discount: Optional[bool] = None
    has_ps_plus: Optional[bool] = None
    has_ea_access: Optional[bool] = None
    search: Optional[str] = None
    platform: Optional[str] = Field(None, description="Платформа (PS4, PS5, или обе)")
    players: Optional[str] = Field(None, description="Количество игроков (singleplayer, multiplayer, coop)")

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Номер страницы")
    limit: int = Field(20, ge=1, le=100, description="Количество элементов на странице")

# Схемы для настроек регионов
class RegionSettings(BaseModel):
    show_ukraine_prices: bool = Field(True, description="Показывать цены Украины")
    show_turkey_prices: bool = Field(True, description="Показывать цены Турции")
    show_india_prices: bool = Field(True, description="Показывать цены Индии")

# Схемы для PSN данных
class PSNCredentials(BaseModel):
    platform: Optional[PlatformEnum] = Field(None, description="PlayStation платформа")
    psn_email: Optional[str] = Field(None, description="Email для PSN аккаунта")
    psn_password: Optional[str] = Field(None, description="PSN пароль")

class PSNCredentialsResponse(BaseModel):
    platform: Optional[PlatformEnum] = Field(None, description="PlayStation платформа")
    psn_email: Optional[str] = Field(None, description="Email для PSN аккаунта")
    has_password: bool = Field(False, description="Установлен ли пароль")

# Схемы для курсов валют (оставляем для совместимости, но они теперь не используются)
class CurrencyRateBase(BaseModel):
    currency_from: str = Field(..., description="Исходная валюта")
    currency_to: str = Field("RUB", description="Целевая валюта")
    price_min: float = Field(..., ge=0, description="Минимальная цена диапазона")
    price_max: Optional[float] = Field(None, ge=0, description="Максимальная цена диапазона")
    rate: float = Field(..., gt=0, description="Курс конвертации")
    description: Optional[str] = Field(None, description="Описание курса")

class CurrencyRateCreate(CurrencyRateBase):
    pass

class CurrencyRateUpdate(BaseModel):
    rate: Optional[float] = Field(None, gt=0, description="Курс конвертации")
    description: Optional[str] = Field(None, description="Описание курса")
    is_active: Optional[bool] = Field(None, description="Активность курса")

class CurrencyRate(CurrencyRateBase):
    id: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    price_range_display: str

    class Config:
        from_attributes = True

# Схемы для админки
class AdminStats(BaseModel):
    total_products: int = Field(..., description="Общее количество товаров")
    active_products: int = Field(..., description="Активных товаров")
    total_users: int = Field(..., description="Общее количество пользователей")
    active_users: int = Field(..., description="Активных пользователей")
    total_favorites: int = Field(..., description="Общее количество избранного")
    products_by_region: Dict[str, int] = Field(default_factory=dict, description="Товаров по регионам")
    currency_rates_count: int = Field(0, description="Количество активных курсов валют")
    products_with_rub_prices: int = Field(0, description="Товаров с рублевыми ценами")
    last_db_check: Optional[datetime] = Field(None, description="Последняя проверка БД")

class AdminUser(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    is_active: bool
    created_at: datetime
    favorites_count: int
    has_psn_credentials: bool

    class Config:
        from_attributes = True

# Схема для отображения цен с флагами
class PriceInfo(BaseModel):
    type: str = Field(..., description="Тип цены (regular, ps_plus, ea_access)")
    value: float = Field(..., description="Значение цены")
    label: str = Field(..., description="Подпись цены")
    region: Optional[str] = Field(None, description="Регион")
    currency_symbol: Optional[str] = Field(None, description="Символ валюты")

class ProductWithPrices(Product):
    all_prices: Optional[Dict[str, Any]] = Field(None, description="Все доступные цены")


# ========================================
# Схемы для региональных PSN аккаунтов
# ========================================

class PSNAccountBase(BaseModel):
    """Базовая схема PSN аккаунта"""
    region: str = Field(..., description="Регион аккаунта (UA, TR)")
    psn_email: Optional[str] = Field(None, description="Email для PSN аккаунта")
    platform: Optional[PlatformEnum] = Field(None, description="PlayStation платформа")

    @field_validator('psn_email')
    @classmethod
    def validate_psn_email(cls, value: Optional[str]) -> Optional[str]:
        return validate_email_value(value)


class PSNAccountCreate(PSNAccountBase):
    """Схема для создания PSN аккаунта"""
    psn_password: str = Field(..., description="PSN пароль")
    twofa_code: Optional[str] = Field(None, description="Резервный код 2FA")


class PSNAccountUpdate(BaseModel):
    """Схема для обновления PSN аккаунта"""
    psn_email: Optional[str] = Field(None, description="Email для PSN аккаунта")
    psn_password: Optional[str] = Field(None, description="PSN пароль")
    platform: Optional[PlatformEnum] = Field(None, description="PlayStation платформа")
    twofa_code: Optional[str] = Field(None, description="Резервный код 2FA")

    @field_validator('psn_email')
    @classmethod
    def validate_psn_email(cls, value: Optional[str]) -> Optional[str]:
        return validate_email_value(value)


class PSNAccountResponse(BaseModel):
    """Схема ответа PSN аккаунта (без пароля)"""
    id: int
    region: str = Field(..., description="Регион аккаунта (UA, TR)")
    psn_email: Optional[str] = Field(None, description="Email для PSN аккаунта")
    platform: Optional[str] = Field(None, description="PlayStation платформа")
    has_password: bool = Field(False, description="Установлен ли пароль")
    has_twofa: bool = Field(False, description="Установлен ли код 2FA")
    is_active: bool = Field(True, description="Активен ли аккаунт")
    region_info: Optional[Dict[str, str]] = Field(None, description="Информация о регионе")

    class Config:
        from_attributes = True


class PSNAccountsListResponse(BaseModel):
    """Список всех PSN аккаунтов пользователя"""
    accounts: List[PSNAccountResponse] = Field(default_factory=list)
    total: int = Field(0, description="Общее количество аккаунтов")


class RegionalPSNCredentials(BaseModel):
    """
    Схема для получения PSN данных для конкретного региона.
    Используется при генерации ссылки оплаты.
    """
    region: str = Field(..., description="Регион (UA, TR)")
    psn_email: Optional[str] = Field(None, description="Email для PSN")
    platform: Optional[str] = Field(None, description="Платформа")
    has_credentials: bool = Field(False, description="Есть ли полные данные")


class RegionalPSNCredentialsWithPassword(RegionalPSNCredentials):
    """
    Расширенная схема с паролем (для внутреннего использования).
    НЕ отдавать клиенту напрямую!
    """
    psn_password: Optional[str] = Field(None, description="PSN пароль (расшифрованный)")
    twofa_code: Optional[str] = Field(None, description="Код 2FA (расшифрованный)")


# ========================================
# Схемы для Email привязки покупки
# ========================================

class PaymentEmailUpdate(BaseModel):
    """Схема для обновления email привязки покупки"""
    payment_email: str = Field(..., description="Email для привязки покупки на oplata.info")

    @field_validator('payment_email')
    @classmethod
    def validate_payment_email(cls, value: str) -> str:
        validated = validate_email_value(value, required=True)
        return validated or ""


class PaymentEmailResponse(BaseModel):
    """Схема ответа с email привязки покупки"""
    payment_email: Optional[str] = Field(None, description="Email для привязки покупки")
