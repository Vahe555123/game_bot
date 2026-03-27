from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, text
from typing import Optional, List, Dict
from app.models import User, Product, UserFavoriteProduct, Localization
from app.models.currency_rate import CurrencyRate
from app.api.schemas import UserCreate, UserUpdate, ProductFilter, PaginationParams, CurrencyRateCreate, CurrencyRateUpdate

class UserCRUD:
    @staticmethod
    def get_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID"""
        return db.query(User).filter(User.telegram_id == telegram_id).first()

    @staticmethod
    def create(db: Session, user_data: UserCreate) -> User:
        """Создать нового пользователя"""
        user = User(**user_data.model_dump())
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update(db: Session, user: User, update_data: UserUpdate) -> User:
        """Обновить данные пользователя"""
        update_fields = update_data.model_dump(exclude_unset=True)

        # Обрабатываем специальные поля
        psn_password = update_fields.pop('psn_password', None)

        # Обычные поля
        for field, value in update_fields.items():
            setattr(user, field, value)

        # Специальная обработка PSN пароля
        if psn_password is not None:
            user.set_psn_password(psn_password)

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_or_create(db: Session, user_data: UserCreate) -> tuple[User, bool]:
        """Получить пользователя или создать, если не существует"""
        user = UserCRUD.get_by_telegram_id(db, user_data.telegram_id)
        if user:
            return user, False
        return UserCRUD.create(db, user_data), True

class ProductCRUD:
    @staticmethod
    def get_by_id(db: Session, product_id: str, region: Optional[str] = None) -> Optional[Product]:
        """Получить товар по ID с учетом региона"""
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"🔎 get_by_id called: product_id={product_id}, region={region}")

        query = db.query(Product).filter(Product.id == product_id)

        # Если указан регион, фильтруем по нему
        if region:
            query = query.filter(Product.region == region)
            logger.info(f"   Filtering by region: {region}")
        else:
            logger.warning(f"⚠️ Region NOT specified!")

        product = query.first()

        if product:
            logger.info(f"✅ Found product: region={product.region}, localization={product.localization}, name={product.name[:50]}")
        else:
            logger.error(f"❌ Product NOT found!")

        return product

    @staticmethod
    def get_by_id_all_regions(db: Session, product_id: str) -> List[Product]:
        """Получить товар во всех регионах"""
        return db.query(Product).filter(Product.id == product_id).all()

    @staticmethod
    def get_localization_name(db: Session, localization_code: Optional[str]) -> Optional[str]:
        """Получить название локализации по коду"""
        if not localization_code:
            return None

        localization = db.query(Localization).filter(Localization.code == localization_code).first()
        if localization:
            return localization.name_ru

        return None

    @staticmethod
    def get_list(
        db: Session,
        filters: ProductFilter,
        pagination: PaginationParams,
        user: Optional[User] = None
    ) -> tuple[List[Product], int]:
        """Получить список товаров с фильтрацией и пагинацией"""
        query = db.query(Product)

        # Фильтр по регионам пользователя
        if user:
            enabled_regions = user.get_enabled_regions()
            if enabled_regions:
                query = query.filter(Product.region.in_(enabled_regions))

        # Применяем фильтры
        if filters.category:
            query = query.filter(Product.category.ilike(f"%{filters.category}%"))

        if filters.region:
            query = query.filter(Product.region == filters.region)

        if filters.search:
            # Поиск только по названию товара (main_name), без учета регистра
            # Используем Python для нормализации строк для надежной работы с кириллицей
            def _normalize_search_text(value: str) -> str:
                return value.strip().lower().replace('ё', 'е')

            search_term = _normalize_search_text(filters.search)
            if search_term:
                # Создаем базовый запрос для получения товаров с примененными фильтрами
                # Используем тот же query объект, но получаем только нужные поля
                base_query = query.with_entities(
                    Product.id,
                    Product.region,
                    Product.main_name,
                    Product.name,
                    Product.search_names,
                    Product.tags,
                )
                
                # Загружаем только ID, регионы и названия одним запросом, затем фильтруем в Python
                product_data = base_query.all()
                matching_ids = [
                    (pid, rid) for pid, rid, main_name, name, search_names, tags in product_data
                    if (
                        (main_name and search_term in _normalize_search_text(main_name))
                        or (name and search_term in _normalize_search_text(name))
                        or (search_names and search_term in _normalize_search_text(search_names))
                        or (tags and search_term in _normalize_search_text(tags))
                    )
                ]
                
                if matching_ids:
                    # Фильтруем по найденным ID и регионам
                    conditions = [
                        and_(Product.id == pid, Product.region == rid) 
                        for pid, rid in matching_ids
                    ]
                    query = query.filter(or_(*conditions))
                else:
                    # Если ничего не найдено, возвращаем пустой результат
                    query = query.filter(Product.id == None)

        if filters.has_discount is not None:
            if filters.has_discount:
                query = query.filter(
                    and_(
                        Product.discount.isnot(None),
                        Product.discount > 0
                    )
                )
            else:
                query = query.filter(
                    or_(
                        Product.discount.is_(None),
                        Product.discount <= 0
                    )
                )

        if filters.has_ps_plus is not None:
            if filters.has_ps_plus:
                # Фильтр "Доступно в PS Plus" = игры ВХОДЯТ в подписку (Extra/Deluxe)
                query = query.filter(
                    and_(
                        Product.ps_plus_collection.isnot(None),
                        Product.ps_plus_collection != '',
                        Product.ps_plus_collection != '0'
                    )
                )

        if filters.has_ea_access is not None:
            if filters.has_ea_access:
                # Фильтр "Доступно в EA Access" = игры ВХОДЯТ в подписку EA Play
                query = query.filter(
                    and_(
                        Product.ea_access.isnot(None),
                        or_(
                            Product.ea_access == '1',
                            Product.ea_access == 1,
                            Product.ea_access == True
                        )
                    )
                )

        # Фильтр по цене
        if filters.min_price is not None:
            query = query.filter(Product.price >= filters.min_price)

        if filters.max_price is not None:
            query = query.filter(Product.price <= filters.max_price)

        # Подсчет общего количества
        total = query.count()

        # Применяем пагинацию
        offset = (pagination.page - 1) * pagination.limit
        products = query.offset(offset).limit(pagination.limit).all()

        return products, total

    @staticmethod
    def get_categories(db: Session) -> List[str]:
        """Получить список всех категорий товаров"""
        categories = db.query(Product.category).filter(
            Product.category.isnot(None)
        ).distinct().all()
        return sorted([cat[0] for cat in categories if cat[0]])

    @staticmethod
    def get_regions(db: Session) -> List[str]:
        """Получить список всех доступных регионов"""
        regions = db.query(Product.region).filter(
            Product.region.isnot(None)
        ).distinct().all()
        return sorted([reg[0] for reg in regions if reg[0]])

    @staticmethod
    def prepare_product_with_prices(product: Product, db: Session = None) -> dict:
        """Подготовить товар с информацией о ценах"""
        region_info = product.get_region_info()

        product_dict = {
            'id': product.id,
            'name': product.name,
            'main_name': product.get_display_name(),
            'category': product.category,
            'region': product.region,
            'type': product.type,
            'image': product.image,
            'publisher': product.publisher,
            'description': product.description,
            'discount': product.discount,
            'discount_end': product.discount_end,
            'has_discount': product.has_discount,
            'ps_plus': product.ps_plus,
            'has_ps_plus': product.has_ps_plus,
            'has_ea_access': product.has_ea_access,
            'ea_access': product.ea_access,
            'ps_plus_collection': product.ps_plus_collection,
            'has_ps_plus_extra_deluxe': product.has_ps_plus_extra_deluxe,
            'rating': product.rating,
            'edition': product.edition,
            'platforms': product.platforms,
            'localization': product.localization,
            'region_info': region_info,
            # Оригинальные цены в валюте региона
            'price': product.price,
            'old_price': product.old_price,
            'ps_price': product.ps_price,
            'ea_price': product.ea_price,
            'current_price': product.get_current_price(),
            'price_with_currency': product.get_price_with_currency(),
            'all_prices': product.get_all_prices(),
            # Цены в рублях (если есть доступ к БД)
            'rub_price': product.get_rub_price(db) if db else None,
            'rub_price_old': product.get_rub_old_price(db) if db else None,
            'rub_ps_price': product.get_rub_ps_price(db) if db else None,
            'rub_ea_price': product.get_rub_ea_price(db) if db else None,
            # Прочее
            'compound': product.get_compound_list(),
            'info': product.get_info_list(),
            'tags': product.get_tags_list()
        }

        return product_dict

    @staticmethod
    def prepare_product_with_multi_region_prices(product: Product, db: Session, user: Optional[User] = None, filter_region: Optional[str] = None) -> dict:
        """
        Подготовить товар с ценами из всех регионов для карточек на главной странице и похожих товаров

        Находит все варианты товара с тем же ID из разных регионов
        и показывает цены всех 3 регионов для ознакомления

        Args:
            product: базовый Product объект
            db: сессия БД
            user: пользователь для фильтрации регионов
            filter_region: конкретный регион из фильтра

        Returns:
            dict с данными товара и ценами из всех 3 регионов
        """
        # Находим ВСЕ варианты ЭТОГО КОНКРЕТНОГО товара (с тем же ID) из разных регионов
        # ID у товаров одинаковый для всех регионов, отличается только поле region
        regional_products = db.query(Product).filter(Product.id == product.id).all()

        # Маппинг регионов
        region_mapping = {
            'UA': {'flag': '🇺🇦', 'name': 'Украина', 'code': 'UAH', 'price_field': 'price_uah', 'old_price_field': 'old_price_uah'},
            'TR': {'flag': '🇹🇷', 'name': 'Турция', 'code': 'TRY', 'price_field': 'price_try', 'old_price_field': 'old_price_try'},
            'IN': {'flag': '🇮🇳', 'name': 'Индия', 'code': 'INR', 'price_field': 'price_inr', 'old_price_field': 'old_price_inr'}
        }

        # Собираем цены из всех регионов
        regional_prices = []
        min_price = None
        min_price_old = None

        # Определяем какие регионы показывать
        # На главной странице и в похожих товарах ВСЕГДА показываем все 3 региона для ознакомления
        # Порядок: Турция, Индия, Украина
        enabled_regions = ['TR', 'IN', 'UA']

        for region_code in enabled_regions:
            # Ищем товар для этого региона
            regional_product = next((p for p in regional_products if p.region == region_code), None)

            if regional_product and region_code in region_mapping:
                region_info = region_mapping[region_code]

                # Получаем цену из регионального поля
                price_field = None
                old_price_field = None
                if region_code == 'UA':
                    price_field = 'price_uah'
                    old_price_field = 'old_price_uah'
                elif region_code == 'TR':
                    price_field = 'price_try'
                    old_price_field = 'old_price_try'
                elif region_code == 'IN':
                    price_field = 'price_inr'
                    old_price_field = 'old_price_inr'

                price = getattr(regional_product, price_field, None) if price_field else None
                old_price = getattr(regional_product, old_price_field, None) if old_price_field else None

                # Получаем PS Plus цену для этого региона
                ps_plus_price_field_map = {
                    'UA': 'ps_plus_price_uah',
                    'TR': 'ps_plus_price_try',
                    'IN': 'ps_plus_price_inr'
                }
                ps_plus_price = getattr(regional_product, ps_plus_price_field_map.get(region_code), None)

                if price and price > 0:
                    # Конвертируем в рубли
                    from app.models.currency_rate import CurrencyRate
                    rate = CurrencyRate.get_rate_for_price(db, region_info['code'], price)
                    price_rub = round(price * rate, 2)
                    old_price_rub = round(old_price * rate, 2) if old_price and old_price > 0 else None
                    ps_plus_price_rub = round(ps_plus_price * rate, 2) if ps_plus_price and ps_plus_price > 0 else None

                    # Вычисляем скидку
                    has_discount = False
                    discount_percent = None
                    if old_price and old_price > price:
                        has_discount = True
                        discount_percent = int(((old_price - price) / old_price) * 100)

                    # Вычисляем дополнительную скидку PS Plus (если есть)
                    # ВАЖНО: считаем от оригинальной цены (old_price_rub), а не от текущей!
                    ps_plus_discount_percent = None
                    if ps_plus_price_rub and old_price_rub and ps_plus_price_rub < old_price_rub:
                        ps_plus_discount_percent = int(((old_price_rub - ps_plus_price_rub) / old_price_rub) * 100)

                    # Получаем локализацию
                    localization_code = regional_product.localization
                    localization_name = ProductCRUD.get_localization_name(db, localization_code) if localization_code else None

                    regional_prices.append({
                        'region': region_code,
                        'flag': region_info['flag'],
                        'name': region_info['name'],
                        'currency_code': region_info['code'],
                        'price_rub': price_rub,
                        'old_price_rub': old_price_rub,
                        'ps_plus_price_rub': ps_plus_price_rub,
                        'has_discount': has_discount,
                        'discount_percent': discount_percent,
                        'ps_plus_discount_percent': ps_plus_discount_percent,
                        'localization_code': localization_code,
                        'localization_name': localization_name
                    })

                    # Обновляем минимальную цену
                    if min_price is None or price_rub < min_price:
                        min_price = price_rub
                        min_price_old = old_price_rub

        # Получаем локализацию из основного поля
        localization_name = ProductCRUD.get_localization_name(db, product.localization)

        # Находим максимальный discount_percent из всех регионов
        max_discount_percent = None
        if regional_prices:
            discounts = [p.get('discount_percent') for p in regional_prices if p.get('discount_percent')]
            if discounts:
                max_discount_percent = max(discounts)

        product_dict = {
            'id': product.id,
            'name': product.name,
            'main_name': product.get_display_name(),
            'category': product.category,
            'type': product.type,
            'region': product.region,  # Регион товара
            'image': product.image,
            'publisher': product.publisher,
            'description': product.description,
            'rating': product.rating,
            'edition': product.edition,
            'platforms': product.platforms,
            'localization': product.localization,
            'localization_name': localization_name,
            'has_discount': any(p['has_discount'] for p in regional_prices),
            'discount': product.discount,
            'discount_end': product.discount_end,
            'discount_percent': max_discount_percent,
            'ps_plus': product.ps_plus,
            'has_ps_plus': product.has_ps_plus,
            'ps_price': product.ps_price,
            'has_ea_access': product.has_ea_access,
            'ea_access': product.ea_access,
            'ps_plus_collection': product.ps_plus_collection,
            'has_ps_plus_extra_deluxe': product.has_ps_plus_extra_deluxe,
            # Прочее
            'compound': product.get_compound_list(),
            'info': product.get_info_list(),
            'tags': product.get_tags_list(),
            # Цены из всех регионов
            'regional_prices': regional_prices,
            'min_price_rub': min_price,
            # Оригинальные цены в валютах регионов
            'price_try': product.price_try,
            'old_price_try': product.old_price_try,
            'price_inr': product.price_inr,
            'old_price_inr': product.old_price_inr,
            'price_uah': product.price_uah,
            'old_price_uah': product.old_price_uah,
            # Цена в рублях (минимальная)
            'rub_price': min_price,
            'rub_price_old': min_price_old
        }

        return product_dict

    @staticmethod
    def prepare_product_with_all_regions(product: Product, db: Session, user: Optional[User] = None) -> dict:
        """
        Подготовить товар с ценами из всех регионов для детальной страницы

        Находит все варианты товара с тем же main_name из разных регионов
        и показывает цены всех регионов для сравнения

        Args:
            product: базовый Product объект
            db: сессия БД
            user: пользователь для фильтрации регионов

        Returns:
            dict с данными товара и ценами из всех регионов
        """
        # Получаем main_name товара
        main_name = product.get_display_name()

        # Находим ВСЕ варианты ЭТОГО КОНКРЕТНОГО товара (с тем же ID) из разных регионов
        # ID у товаров одинаковый для всех регионов, отличается только поле region
        regional_products = db.query(Product).filter(Product.id == product.id).all()

        # Маппинг регионов
        region_mapping = {
            'UA': {'flag': '🇺🇦', 'name': 'Украина', 'code': 'UAH', 'price_field': 'price_uah', 'old_price_field': 'old_price_uah'},
            'TR': {'flag': '🇹🇷', 'name': 'Турция', 'code': 'TRY', 'price_field': 'price_try', 'old_price_field': 'old_price_try'},
            'IN': {'flag': '🇮🇳', 'name': 'Индия', 'code': 'INR', 'price_field': 'price_inr', 'old_price_field': 'old_price_inr'}
        }

        # Собираем цены из всех регионов
        regional_prices = []
        min_price = None
        min_price_old = None

        # Определяем какие регионы показывать
        # На детальной странице товара ВСЕГДА показываем все 3 региона для ознакомления
        # Порядок: Турция, Индия, Украина
        enabled_regions = ['TR', 'IN', 'UA']

        for region_code in enabled_regions:
            # Ищем товар для этого региона
            regional_product = next((p for p in regional_products if p.region == region_code), None)

            if regional_product and region_code in region_mapping:
                region_info = region_mapping[region_code]

                # ИСПРАВЛЕНО: Получаем цену из регионального поля, а не из price (которое уже в рублях!)
                # Определяем поле региональной цены
                price_field = None
                old_price_field = None
                if region_code == 'UA':
                    price_field = 'price_uah'
                    old_price_field = 'old_price_uah'
                elif region_code == 'TR':
                    price_field = 'price_try'
                    old_price_field = 'old_price_try'
                elif region_code == 'IN':
                    price_field = 'price_inr'
                    old_price_field = 'old_price_inr'

                price = getattr(regional_product, price_field, None) if price_field else None
                old_price = getattr(regional_product, old_price_field, None) if old_price_field else None

                # Получаем PS Plus цену для этого региона
                ps_plus_price_field_map = {
                    'UA': 'ps_plus_price_uah',
                    'TR': 'ps_plus_price_try',
                    'IN': 'ps_plus_price_inr'
                }
                ps_plus_price = getattr(regional_product, ps_plus_price_field_map.get(region_code), None)

                if price and price > 0:
                    # Конвертируем в рубли
                    from app.models.currency_rate import CurrencyRate
                    rate = CurrencyRate.get_rate_for_price(db, region_info['code'], price)
                    price_rub = round(price * rate, 2)
                    old_price_rub = round(old_price * rate, 2) if old_price and old_price > 0 else None
                    ps_plus_price_rub = round(ps_plus_price * rate, 2) if ps_plus_price and ps_plus_price > 0 else None

                    # Вычисляем скидку
                    has_discount = False
                    discount_percent = None
                    if old_price and old_price > price:
                        has_discount = True
                        discount_percent = int(((old_price - price) / old_price) * 100)

                    # Вычисляем дополнительную скидку PS Plus (если есть)
                    # ВАЖНО: считаем от оригинальной цены (old_price_rub), а не от текущей!
                    ps_plus_discount_percent = None
                    if ps_plus_price_rub and old_price_rub and ps_plus_price_rub < old_price_rub:
                        ps_plus_discount_percent = int(((old_price_rub - ps_plus_price_rub) / old_price_rub) * 100)

                    # Получаем локализацию
                    localization_code = regional_product.localization
                    localization_name = ProductCRUD.get_localization_name(db, localization_code) if localization_code else None

                    regional_prices.append({
                        'region': region_code,
                        'flag': region_info['flag'],
                        'name': region_info['name'],
                        'currency_code': region_info['code'],
                        'price_rub': price_rub,
                        'old_price_rub': old_price_rub,
                        'ps_plus_price_rub': ps_plus_price_rub,
                        'has_discount': has_discount,
                        'discount_percent': discount_percent,
                        'ps_plus_discount_percent': ps_plus_discount_percent,
                        'localization_code': localization_code,
                        'localization_name': localization_name
                    })

                    # Обновляем минимальную цену
                    if min_price is None or price_rub < min_price:
                        min_price = price_rub
                        min_price_old = old_price_rub

        # Получаем локализацию из основного товара
        localization_name = ProductCRUD.get_localization_name(db, product.localization)

        # Регион товара уже в правильном формате (UA, TR, IN)
        normalized_region = product.region

        product_dict = {
            'id': product.id,
            'name': product.name,
            'main_name': product.get_display_name(),
            'category': product.category,
            'type': product.type,
            'region': normalized_region,
            'image': product.image,
            'publisher': product.publisher,
            'description': product.description,
            'rating': product.rating,
            'edition': product.edition,
            'platforms': product.platforms,
            'localization': product.localization,
            'localization_name': localization_name,
            'has_discount': any(p['has_discount'] for p in regional_prices),
            'discount': product.discount,
            'discount_end': product.discount_end,
            'ps_plus': product.ps_plus,
            'has_ps_plus': product.has_ps_plus,
            'ps_price': product.ps_price,
            'has_ea_access': product.has_ea_access,
            'ea_access': product.ea_access,
            'ps_plus_collection': product.ps_plus_collection,
            'has_ps_plus_extra_deluxe': product.has_ps_plus_extra_deluxe,
            'compound': product.get_compound_list(),
            'info': product.get_info_list(),
            'tags': product.get_tags_list(),
            'regional_prices': regional_prices,
            'min_price': min_price,
            'min_price_old': min_price_old
        }

        return product_dict

    @staticmethod
    def get_unique_products_by_main_name(
        db: Session,
        filters: ProductFilter,
        pagination: PaginationParams,
        user: Optional[User] = None
    ) -> tuple[List[Dict], int]:
        """
        Получить уникальные товары (без дубликатов по main_name),
        выбирая лучшую цену из всех регионов
        """
        query = db.query(Product)

        # Фильтр по регионам пользователя
        enabled_regions = ['UA', 'TR', 'IN']
        if user:
            enabled_regions = user.get_enabled_regions()

        if enabled_regions:
            query = query.filter(Product.region.in_(enabled_regions))

        # Применяем остальные фильтры
        if filters.category:
            query = query.filter(Product.category.ilike(f"%{filters.category}%"))

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Product.search_names.ilike(search_term),
                    Product.main_name.ilike(search_term),
                    Product.description.ilike(search_term),
                    Product.publisher.ilike(search_term)
                )
            )

        # Получаем все товары
        all_products = query.all()

        # Группируем по main_name и выбираем лучшую цену
        unique_products = {}
        for product in all_products:
            main_name = product.get_display_name()

            if main_name not in unique_products:
                unique_products[main_name] = product
            else:
                # Сравниваем цены и оставляем дешевле
                existing = unique_products[main_name]
                existing_price = existing.get_current_price() or float('inf')
                current_price = product.get_current_price() or float('inf')

                if current_price < existing_price:
                    unique_products[main_name] = product

        # Применяем фильтры скидок после группировки
        filtered_products = []
        for product in unique_products.values():
            if filters.has_discount is not None:
                if filters.has_discount and not product.has_discount:
                    continue
                if not filters.has_discount and product.has_discount:
                    continue

            if filters.min_price is not None:
                if not product.price or product.price < filters.min_price:
                    continue

            if filters.max_price is not None:
                if not product.price or product.price > filters.max_price:
                    continue

            filtered_products.append(product)

        # Сортируем по английскому алфавиту (без учета регистра)
        filtered_products.sort(key=lambda p: (p.name or '').lower())

        total = len(filtered_products)

        # Применяем пагинацию
        offset = (pagination.page - 1) * pagination.limit
        paginated_products = filtered_products[offset:offset + pagination.limit]

        # Подготавливаем продукты с ценами
        result = [ProductCRUD.prepare_product_with_prices(p) for p in paginated_products]

        return result, total

    @staticmethod
    def get_products_grouped_by_name(
        db: Session,
        filters: ProductFilter,
        pagination: PaginationParams,
        user: Optional[User] = None
    ) -> tuple[List[Dict], int]:
        """
        Получить список товаров с ценами в рублях

        В новой структуре БД каждый товар создается отдельно для каждого региона.
        Фильтруем товары по региону и показываем только цену соответствующего региона.
        """
        query = db.query(Product)

        # Сохраняем filter_region для передачи в prepare_product
        filter_region = filters.region

        # Фильтруем по региону если указан
        if filter_region:
            query = query.filter(Product.region == filter_region)
        else:
            # Если регион не указан, берем настройки пользователя или все регионы
            if user:
                enabled_regions = user.get_enabled_regions()
            else:
                enabled_regions = ['UA', 'TR', 'IN']
            query = query.filter(Product.region.in_(enabled_regions))

        # Применяем фильтры
        if filters.category:
            query = query.filter(Product.category.ilike(f"%{filters.category}%"))

        if filters.platform:
            # Фильтр по платформе: PS4, PS5 или обе
            platform_filter = filters.platform.upper()
            if platform_filter == 'PS4_ALL':
                query = query.filter(Product.platforms.ilike('%PS4%'))
            elif platform_filter == 'PS5_ALL':
                query = query.filter(Product.platforms.ilike('%PS5%'))
            elif platform_filter in ('PS4_ONLY', 'PS4'):
                # Только игры ЭКСКЛЮЗИВНО для PS4 (без PS5)
                query = query.filter(
                    and_(
                        Product.platforms.ilike('%PS4%'),
                        ~Product.platforms.ilike('%PS5%')
                    )
                )
            elif platform_filter in ('PS5_ONLY', 'PS5'):
                # Только игры ЭКСКЛЮЗИВНО для PS5 (без PS4)
                query = query.filter(
                    and_(
                        Product.platforms.ilike('%PS5%'),
                        ~Product.platforms.ilike('%PS4%')
                    )
                )
            elif platform_filter == 'BOTH':
                # Игры доступные на обеих платформах
                query = query.filter(
                    and_(
                        Product.platforms.ilike('%PS4%'),
                        Product.platforms.ilike('%PS5%')
                    )
                )

        if filters.players:
            # Фильтр по количеству игроков - ищем в поле info (дополнительная информация)
            # В базе формат: "Игроки: 1 - 2" в Unicode escape
            players_filter = filters.players.lower()
            if players_filter == 'singleplayer':
                # Одиночные игры - ищем "1 игрок" НО исключаем "Игроки: 1 - 2" (это кооп)
                query = query.filter(
                    and_(
                        or_(
                            Product.info.ilike('%1 \\u0438\\u0433\\u0440\\u043e\\u043a%'),  # "1 игрок"
                            Product.info.ilike('%1 игрок%')  # обычный текст
                        ),
                        # Исключаем кооператив - формат "Игроки: X - Y"
                        ~Product.info.ilike('%\\u0418\\u0433\\u0440\\u043e\\u043a\\u0438:%'),  # НЕТ "Игроки:"
                        ~Product.info.ilike('%Игроки:%')
                    )
                )
            elif players_filter == 'coop':
                # Кооперативные игры - ищем "Игроки: 1 - 2", "Игроки: 2 - 4" и т.д.
                query = query.filter(
                    or_(
                        # Формат "Игроки: X - Y" в Unicode
                        Product.info.ilike('%\\u0418\\u0433\\u0440\\u043e\\u043a\\u0438: 1 - 2%'),  # "Игроки: 1 - 2"
                        Product.info.ilike('%\\u0418\\u0433\\u0440\\u043e\\u043a\\u0438: 2 - 4%'),  # "Игроки: 2 - 4"
                        Product.info.ilike('%\\u0418\\u0433\\u0440\\u043e\\u043a\\u0438: 1 - 4%'),  # "Игроки: 1 - 4"
                        Product.info.ilike('%\\u0418\\u0433\\u0440\\u043e\\u043a\\u0438: 2 - 8%'),  # "Игроки: 2 - 8"
                        # Обычный текст (на всякий случай)
                        Product.info.ilike('%Игроки: 1 - 2%'),
                        Product.info.ilike('%Игроки: 2 - 4%'),
                        Product.info.ilike('%Игроки: 1 - 4%')
                    )
                )

        if filters.search:
            # Поиск только по названию товара (main_name), без учета регистра
            # Используем Python для нормализации строк для надежной работы с кириллицей
            def _normalize_search_text(value: str) -> str:
                return value.strip().lower().replace('ё', 'е')

            search_term = _normalize_search_text(filters.search)
            if search_term:
                # Создаем базовый запрос для получения товаров с примененными фильтрами
                # Используем тот же query объект, но получаем только нужные поля
                base_query = query.with_entities(
                    Product.id,
                    Product.region,
                    Product.main_name,
                    Product.name,
                    Product.search_names,
                    Product.tags,
                )
                
                # Загружаем только ID, регионы и названия одним запросом, затем фильтруем в Python
                product_data = base_query.all()
                matching_ids = [
                    (pid, rid) for pid, rid, main_name, name, search_names, tags in product_data
                    if (
                        (main_name and search_term in _normalize_search_text(main_name))
                        or (name and search_term in _normalize_search_text(name))
                        or (search_names and search_term in _normalize_search_text(search_names))
                        or (tags and search_term in _normalize_search_text(tags))
                    )
                ]
                
                if matching_ids:
                    # Фильтруем по найденным ID и регионам
                    conditions = [
                        and_(Product.id == pid, Product.region == rid) 
                        for pid, rid in matching_ids
                    ]
                    query = query.filter(or_(*conditions))
                else:
                    # Если ничего не найдено, возвращаем пустой результат
                    query = query.filter(Product.id == None)

        if filters.has_discount is not None and filters.has_discount:
            # Фильтр по скидкам - проверяем только регион товара
            discount_conditions = []
            if not filter_region or filter_region in ['UA', 'uah']:
                discount_conditions.append(
                    and_(
                        Product.region == 'UA',
                        Product.old_price_uah.isnot(None),
                        Product.old_price_uah > Product.price_uah
                    )
                )
            if not filter_region or filter_region in ['TR', 'try']:
                discount_conditions.append(
                    and_(
                        Product.region == 'TR',
                        Product.old_price_try.isnot(None),
                        Product.old_price_try > Product.price_try
                    )
                )
            if not filter_region or filter_region in ['IN', 'inr']:
                discount_conditions.append(
                    and_(
                        Product.region == 'IN',
                        Product.old_price_inr.isnot(None),
                        Product.old_price_inr > Product.price_inr
                    )
                )
            if discount_conditions:
                query = query.filter(or_(*discount_conditions))

        if filters.has_ps_plus is not None and filters.has_ps_plus:
            # Фильтр "Доступно в PS Plus" = игры ВХОДЯТ в подписку (Extra/Deluxe)
            # НЕ путать с ps_price (это скидка для подписчиков, а не бесплатные игры)
            query = query.filter(
                and_(
                    Product.ps_plus_collection.isnot(None),
                    Product.ps_plus_collection != '',
                    Product.ps_plus_collection != '0'
                )
            )

        if filters.has_ea_access is not None and filters.has_ea_access:
            # Фильтр "Доступно в EA Access" = игры ВХОДЯТ в подписку EA Play
            query = query.filter(
                and_(
                    Product.ea_access.isnot(None),
                    or_(
                        Product.ea_access == '1',
                        Product.ea_access == 1,
                        Product.ea_access == True
                    )
                )
            )

        from app.models.currency_rate import CurrencyRate

        # ОПТИМИЗАЦИЯ: Если есть фильтры по цене - нужно загрузить все товары
        # Если нет - применяем пагинацию на уровне БД (LIMIT/OFFSET)
        has_price_filter = filters.min_price is not None or filters.max_price is not None

        if has_price_filter:
            # Загружаем все товары для фильтрации по цене
            all_products = query.all()

            # Применяем фильтр по цене (проверяем цену соответствующего региона)
            filtered_products = []
            region_price_map = {
                'UA': ('price_uah', 'UAH'),
                'TR': ('price_try', 'TRY'),
                'IN': ('price_inr', 'INR')
            }

            for product in all_products:
                price_rub = None

                if product.region and product.region in region_price_map:
                    price_field, currency_code = region_price_map[product.region]
                    price_value = getattr(product, price_field, None)

                    if price_value and price_value > 0:
                        rate = CurrencyRate.get_rate_for_price(db, currency_code, price_value)
                        price_rub = price_value * rate

                # Применяем фильтры по цене
                if filters.min_price is not None:
                    if price_rub is None or price_rub < filters.min_price:
                        continue

                if filters.max_price is not None:
                    if price_rub is None or price_rub > filters.max_price:
                        continue

                filtered_products.append((product, price_rub))

            # Сортируем только по алфавиту (английский алфавит, без учета регистра)
            filtered_products.sort(key=lambda x: (x[0].name or '').lower())

            total = len(filtered_products)

            # Применяем пагинацию в памяти
            offset = (pagination.page - 1) * pagination.limit
            paginated_products = filtered_products[offset:offset + pagination.limit]
        else:
            # ⚡ ОПТИМИЗАЦИЯ: Пагинация на уровне БД - загружаем только нужные товары
            total = query.count()

            # Сортировка на уровне БД по английскому алфавиту (без учета регистра)
            query = query.order_by(func.lower(Product.name))

            # Применяем LIMIT и OFFSET на уровне SQL
            offset = (pagination.page - 1) * pagination.limit
            products = query.offset(offset).limit(pagination.limit).all()

            # Создаем список для совместимости с кодом ниже
            paginated_products = [(product, None) for product in products]

        # Подготавливаем продукты с мультирегиональными ценами
        result = []
        for product, min_price in paginated_products:
            product_dict = ProductCRUD.prepare_product_with_multi_region_prices(
                product, db, user, filter_region
            )
            result.append(product_dict)

        return result, total

class FavoriteCRUD:
    @staticmethod
    def add_to_favorites(db: Session, user_id: int, product_id: str, region: Optional[str] = None) -> Optional[UserFavoriteProduct]:
        """Добавить товар в избранное"""
        # Проверяем, что товар не уже в избранном
        existing = db.query(UserFavoriteProduct).filter(
            and_(
                UserFavoriteProduct.user_id == user_id,
                UserFavoriteProduct.product_id == product_id
            )
        ).first()

        if existing:
            # Обновляем регион, если передан
            if region:
                existing.region = region
                db.commit()
                db.refresh(existing)
            return existing

        favorite = UserFavoriteProduct(user_id=user_id, product_id=product_id, region=region)
        db.add(favorite)
        db.commit()
        db.refresh(favorite)
        return favorite

    @staticmethod
    def remove_from_favorites(db: Session, user_id: int, product_id: str) -> bool:
        """Удалить товар из избранного"""
        favorite = db.query(UserFavoriteProduct).filter(
            and_(
                UserFavoriteProduct.user_id == user_id,
                UserFavoriteProduct.product_id == product_id
            )
        ).first()

        if favorite:
            db.delete(favorite)
            db.commit()
            return True
        return False

    @staticmethod
    def get_user_favorites(db: Session, user_id: int) -> List[UserFavoriteProduct]:
        """Получить все избранные товары пользователя"""
        return db.query(UserFavoriteProduct).options(
            joinedload(UserFavoriteProduct.product)
        ).filter(UserFavoriteProduct.user_id == user_id).all()

    @staticmethod
    def is_favorite(db: Session, user_id: int, product_id: str) -> bool:
        """Проверить, находится ли товар в избранном у пользователя"""
        return db.query(UserFavoriteProduct).filter(
            and_(
                UserFavoriteProduct.user_id == user_id,
                UserFavoriteProduct.product_id == product_id
            )
        ).first() is not None

class CurrencyRateCRUD:
    """CRUD для курсов валют - оставлен для обратной совместимости"""
    @staticmethod
    def get_all(db: Session) -> List[CurrencyRate]:
        """Получить все курсы валют"""
        return db.query(CurrencyRate).order_by(
            CurrencyRate.currency_from,
            CurrencyRate.price_min
        ).all()

    @staticmethod
    def get_active(db: Session) -> List[CurrencyRate]:
        """Получить активные курсы валют"""
        return db.query(CurrencyRate).filter(
            CurrencyRate.is_active == True
        ).order_by(
            CurrencyRate.currency_from,
            CurrencyRate.price_min
        ).all()

    @staticmethod
    def get_by_id(db: Session, rate_id: int) -> Optional[CurrencyRate]:
        """Получить курс по ID"""
        return db.query(CurrencyRate).filter(CurrencyRate.id == rate_id).first()

    @staticmethod
    def create(db: Session, rate_data: CurrencyRateCreate, created_by: int = None) -> CurrencyRate:
        """Создать новый курс валют"""
        rate = CurrencyRate(**rate_data.model_dump(), created_by=created_by)
        db.add(rate)
        db.commit()
        db.refresh(rate)
        return rate

    @staticmethod
    def update(db: Session, rate: CurrencyRate, update_data: CurrencyRateUpdate) -> CurrencyRate:
        """Обновить курс валют"""
        update_fields = update_data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(rate, field, value)
        db.commit()
        db.refresh(rate)
        return rate

    @staticmethod
    def delete(db: Session, rate: CurrencyRate) -> bool:
        """Удалить курс валют"""
        db.delete(rate)
        db.commit()
        return True

    @staticmethod
    def get_by_currency(db: Session, currency_from: str) -> List[CurrencyRate]:
        """Получить курсы для конкретной валюты"""
        return db.query(CurrencyRate).filter(
            and_(
                CurrencyRate.currency_from == currency_from,
                CurrencyRate.is_active == True
            )
        ).order_by(CurrencyRate.price_min).all()

class AdminCRUD:
    @staticmethod
    def get_stats(db: Session) -> dict:
        """Получить статистику для админки"""
        from datetime import datetime

        # Статистика товаров
        total_products = db.query(Product).count()

        # Уникальные товары (по названию)
        unique_products = db.query(Product.main_name).distinct().count()

        # Товары по регионам
        products_by_region = {}
        regions = db.query(Product.region, func.count(Product.id)).group_by(Product.region).all()
        for region, count in regions:
            products_by_region[region or 'unknown'] = count

        # Статистика пользователей
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()

        # Статистика избранного
        total_favorites = db.query(UserFavoriteProduct).count()

        # Статистика курсов валют
        currency_rates_count = db.query(CurrencyRate).filter(CurrencyRate.is_active == True).count()
        products_with_rub_prices = 0  # Заглушка, так как цены конвертируются динамически

        return {
            'total_products': total_products,
            'active_products': unique_products,
            'total_users': total_users,
            'active_users': active_users,
            'total_favorites': total_favorites,
            'products_by_region': products_by_region,
            'currency_rates_count': currency_rates_count,
            'products_with_rub_prices': total_products,
            'last_db_check': datetime.now()
        }

    @staticmethod
    def get_users_with_stats(db: Session, limit: int = 50) -> List[dict]:
        """Получить пользователей со статистикой"""
        users_query = db.query(User).order_by(User.created_at.desc()).limit(limit)
        users = []

        for user in users_query:
            favorites_count = db.query(UserFavoriteProduct).filter(
                UserFavoriteProduct.user_id == user.id
            ).count()

            user_data = {
                'id': user.id,
                'telegram_id': user.telegram_id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': user.full_name,
                'is_active': user.is_active,
                'created_at': user.created_at,
                'favorites_count': favorites_count,
                'has_psn_credentials': user.has_psn_credentials
            }
            users.append(user_data)

        return users

# Создаем экземпляры для использования
user_crud = UserCRUD()
product_crud = ProductCRUD()
favorite_crud = FavoriteCRUD()
currency_rate_crud = CurrencyRateCRUD()
admin_crud = AdminCRUD()
