from sqlalchemy import Column, Integer, String, Float, Text, Boolean
from sqlalchemy.orm import relationship
from app.database.connection import Base
import json

class Product(Base):
    """Модель товара PlayStation Store из новой базы данных"""
    __tablename__ = 'products'

    # Составной первичный ключ (ID + регион), так как один товар может быть в разных регионах
    id = Column(Text, primary_key=True, comment='ID товара из PlayStation Store')
    region = Column(Text, primary_key=True, index=True, comment='Регион (TR, UA, IN)')

    # Основная информация
    category = Column(Text, nullable=True, index=True, comment='Категория товара')
    type = Column(Text, nullable=True, comment='Тип продукта (Game, DLC, Bundle и т.д.)')
    name = Column(Text, nullable=True, comment='Полное название товара')
    main_name = Column(Text, nullable=True, comment='Основное название товара')
    search_names = Column(Text, nullable=True, index=True, comment='Все варианты названий через запятую для поиска')
    image = Column(Text, nullable=True, comment='Ссылка на изображение')

    # Дополнительная информация о товаре
    compound = Column(Text, nullable=True, comment='Состав товара (JSON строка)')
    platforms = Column(Text, nullable=True, comment='Поддерживаемые платформы')
    publisher = Column(Text, nullable=True, comment='Издатель')
    localization = Column(Text, nullable=True, comment='Уровень локализации')
    rating = Column(Float, nullable=True, comment='Рейтинг товара')
    info = Column(Text, nullable=True, comment='Дополнительная информация (JSON строка)')
    edition = Column(Text, nullable=True, comment='Издание игры')

    # Цены
    price = Column(Float, nullable=True, comment='Текущая цена')
    old_price = Column(Float, nullable=True, comment='Старая цена')
    ps_price = Column(Float, nullable=True, comment='Цена для PS Plus')
    ea_price = Column(Float, nullable=True, comment='Цена для EA Access')

    # Региональные цены
    price_uah = Column(Float, nullable=True, comment='Цена в украинских гривнах')
    old_price_uah = Column(Float, nullable=True, comment='Старая цена в UAH')
    price_try = Column(Float, nullable=True, comment='Цена в турецких лирах')
    old_price_try = Column(Float, nullable=True, comment='Старая цена в TRY')
    price_inr = Column(Float, nullable=True, comment='Цена в индийских рупиях')
    old_price_inr = Column(Float, nullable=True, comment='Старая цена в INR')

    # PS Plus региональные цены
    ps_plus_price_uah = Column(Float, nullable=True, comment='PS Plus цена в украинских гривнах')
    ps_plus_price_try = Column(Float, nullable=True, comment='PS Plus цена в турецких лирах')
    ps_plus_price_inr = Column(Float, nullable=True, comment='PS Plus цена в индийских рупиях')

    # Подписки и доступы
    plus_types = Column(Text, nullable=True, comment='Типы PS Plus доступа')
    ps_plus = Column(Integer, nullable=True, comment='Доступно в PS Plus (0/1)')
    ea_access = Column(Text, nullable=True, comment='Доступно в EA Access')
    ps_plus_collection = Column(Text, nullable=True, comment='PS Plus коллекция (Extra/Deluxe)')

    # Информация о скидке
    discount = Column(Float, nullable=True, comment='Размер скидки в процентах')
    discount_end = Column(Text, nullable=True, comment='Дата окончания скидки')

    # Теги и описание
    tags = Column(Text, nullable=True, comment='Теги товара')
    description = Column(Text, nullable=True, comment='Описание товара')

    # Информация об игроках
    players_min = Column(Integer, nullable=True, comment='Минимальное количество игроков')
    players_max = Column(Integer, nullable=True, comment='Максимальное количество игроков')
    players_online = Column(Integer, nullable=True, comment='Поддержка онлайн игры (0/1)')

    # Связь с избранными товарами пользователей
    favorited_by = relationship(
        "UserFavoriteProduct",
        back_populates="product",
        cascade="all, delete-orphan",
        primaryjoin="and_(Product.id == UserFavoriteProduct.product_id, Product.region == UserFavoriteProduct.region)",
    )

    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.get_display_name()}', region='{self.region}')>"

    def get_display_name(self):
        """Получить название для отображения"""
        return self.main_name or self.name or "Без названия"

    def get_compound_list(self):
        """Получить список составных частей товара"""
        if not self.compound:
            return []
        try:
            return json.loads(self.compound) if isinstance(self.compound, str) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def get_info_list(self):
        """Получить список дополнительной информации"""
        if not self.info:
            return []
        try:
            return json.loads(self.info) if isinstance(self.info, str) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def get_tags_list(self):
        """Получить список тегов"""
        if not self.tags:
            return []
        # Теги могут быть строкой через запятую
        if isinstance(self.tags, str):
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []

    def get_region_info(self):
        """Получить информацию о регионе"""
        region_map = {
            'TR': {'code': 'TRY', 'symbol': '₺', 'flag': '🇹🇷', 'name': 'Турция'},
            'UA': {'code': 'UAH', 'symbol': '₴', 'flag': '🇺🇦', 'name': 'Украина'},
            'IN': {'code': 'INR', 'symbol': '₹', 'flag': '🇮🇳', 'name': 'Индия'}
        }
        return region_map.get(self.region, {'code': 'Unknown', 'symbol': '', 'flag': '', 'name': 'Неизвестно'})

    def get_current_price(self):
        """Получить текущую цену в валюте региона (с учетом PS Plus и EA Access)"""
        # Определяем какое поле цены использовать в зависимости от региона
        region_price_map = {
            'TR': 'price_try',
            'UA': 'price_uah',
            'IN': 'price_inr'
        }

        # Получаем название поля цены для текущего региона
        price_field = region_price_map.get(self.region)

        if price_field:
            # Получаем региональную цену
            regional_price = getattr(self, price_field, None)
            if regional_price and regional_price > 0:
                return regional_price

        # Fallback на старое поле price (для обратной совместимости)
        prices = [p for p in [self.price, self.ps_price, self.ea_price] if p and p > 0]
        return min(prices) if prices else self.price

    def get_price_with_currency(self):
        """Получить цену с символом валюты"""
        region_info = self.get_region_info()
        current_price = self.get_current_price()
        if current_price and current_price > 0:
            return f"{region_info['symbol']}{current_price:.2f}"
        return "Цена не указана"

    def get_discount_percent(self):
        """Получить процент скидки"""
        if not self.discount:
            return None
        try:
            discount_value = float(self.discount)
            return int(discount_value) if discount_value > 0 else None
        except (ValueError, TypeError):
            return None

    def get_discount_info(self):
        """Получить полную информацию о скидке"""
        if not self.has_discount:
            return None

        return {
            'percent': self.get_discount_percent(),
            'end_date': self.discount_end,
            'old_price': self.old_price,
            'new_price': self.get_current_price()
        }

    @property
    def has_discount(self):
        """Проверить, есть ли скидка на товар"""
        discount = self.get_discount_percent()
        return bool(discount and discount > 0)

    @property
    def has_ps_plus(self):
        """Проверить, доступно ли в PS Plus"""
        return bool(self.ps_plus == 1 or (self.ps_price and self.ps_price > 0))

    @property
    def has_ea_access(self):
        """Проверить, доступно ли в EA Access"""
        return bool(self.ea_access and self.ea_access != '0')

    @property
    def has_ps_plus_extra_deluxe(self):
        """Проверить, доступно ли в PS Plus Extra/Deluxe"""
        return bool(self.ps_plus_collection == 'Extra/Deluxe')

    def get_all_prices(self):
        """Получить все доступные цены для товара"""
        region_info = self.get_region_info()
        result = {
            'region': self.region,
            'currency': region_info['code'],
            'symbol': region_info['symbol'],
            'prices': []
        }

        if self.price and self.price > 0:
            result['prices'].append({
                'type': 'regular',
                'value': self.price,
                'label': 'Обычная цена'
            })

        if self.old_price and self.old_price > 0:
            result['prices'].append({
                'type': 'old',
                'value': self.old_price,
                'label': 'Старая цена'
            })

        if self.ps_price and self.ps_price > 0:
            result['prices'].append({
                'type': 'ps_plus',
                'value': self.ps_price,
                'label': 'PS Plus'
            })

        if self.ea_price and self.ea_price > 0:
            result['prices'].append({
                'type': 'ea_access',
                'value': self.ea_price,
                'label': 'EA Access'
            })

        return result

    def get_localization_level(self):
        """Получить уровень локализации (число от 0 до 5)"""
        try:
            return int(self.localization) if self.localization else 0
        except (ValueError, TypeError):
            return 0

    def get_currency_code(self):
        """Получить код валюты региона"""
        currency_map = {
            'TR': 'TRY',   # Турецкая лира
            'UA': 'UAH',   # Украинская гривна
            'IN': 'INR'    # Индийская рупия
        }
        return currency_map.get(self.region, 'USD')

    def convert_to_rub(self, price, db):
        """
        Конвертировать цену в рубли используя курсы из базы данных

        Args:
            price: цена для конвертации
            db: сессия базы данных

        Returns:
            Сконвертированная цена в рублях или None
        """
        if not price or price <= 0:
            return None

        # Импортируем модель здесь, чтобы избежать циклических импортов
        from app.models.currency_rate import CurrencyRate

        currency_code = self.get_currency_code()
        rate = CurrencyRate.get_rate_for_price(db, currency_code, price)

        return round(price * rate, 2)

    def get_rub_price(self, db):
        """Получить текущую цену в рублях"""
        return self.convert_to_rub(self.price, db)

    def get_rub_old_price(self, db):
        """Получить старую цену в рублях"""
        return self.convert_to_rub(self.old_price, db)

    def get_rub_ps_price(self, db):
        """Получить PS Plus цену в рублях"""
        return self.convert_to_rub(self.ps_price, db)

    def get_rub_ea_price(self, db):
        """Получить EA Access цену в рублях"""
        return self.convert_to_rub(self.ea_price, db)
