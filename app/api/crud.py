from collections import defaultdict
import re
import unicodedata
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, case, func, literal, text, Table, Column, Integer, MetaData, Text, inspect
from typing import Optional, List, Dict, Any
from app.models import User, Product, UserFavoriteProduct, Localization
from app.models.currency_rate import CurrencyRate
from app.api.schemas import UserCreate, UserUpdate, ProductFilter, PaginationParams, CurrencyRateCreate, CurrencyRateUpdate
from config.settings import settings


PRODUCT_SEARCH_INDEX_TABLE = Table(
    "product_search_fts",
    MetaData(),
    Column("rowid", Integer, primary_key=True),
    Column("product_id", Text),
    Column("region", Text),
    Column("search_text", Text),
)

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
    def _normalize_sort_mode(sort_value: Optional[str]) -> str:
        normalized = (sort_value or '').strip().lower()

        if normalized in {'alphabet', 'alpha', 'name', 'title'}:
            return 'alphabet'

        if normalized in {'price', 'price_asc', 'cheap', 'asc'}:
            return 'price_asc'

        if normalized in {'price_desc', 'expensive', 'desc'}:
            return 'price_desc'

        return 'popular'

    @staticmethod
    def _normalize_product_id_token(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        normalized = str(value).strip()
        if not normalized:
            return None

        normalized = normalized.split('?', 1)[0].split('#', 1)[0].strip()
        return normalized or None

    @staticmethod
    def _normalize_search_text(value: Optional[str]) -> str:
        if not value:
            return ''

        normalized = str(value).replace('™', ' ').replace('®', ' ').replace('©', ' ')
        normalized = unicodedata.normalize('NFKD', normalized)
        normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.casefold().replace('ё', 'е')
        normalized = re.sub(r'[^\w\s]+', ' ', normalized, flags=re.UNICODE)
        normalized = re.sub(r'[_\s]+', ' ', normalized)
        return normalized.strip()

    @staticmethod
    def _apply_product_kind_filter(query, product_kind: Optional[str]):
        normalized = (product_kind or '').strip().lower()

        if normalized == 'games':
            return query.filter(
                or_(
                    Product.type.ilike('%Игра%'),
                    Product.type.ilike('%Game%'),
                    Product.type.ilike('%Bundle%'),
                    Product.type.ilike('%Набор%'),
                    Product.type.ilike('%Предзаказ%'),
                )
            )

        if normalized == 'dlc':
            return query.filter(
                or_(
                    Product.type.ilike('%Дополнение%'),
                    Product.type.ilike('%DLC%'),
                    Product.category.ilike('%Дополнение%'),
                )
            )

        return query

    @staticmethod
    def _apply_search_filter(query, search: Optional[str]):
        search_term = ProductCRUD._normalize_search_text(search)
        if not search_term:
            return query

        session = getattr(query, "session", None)
        bind = session.get_bind() if session is not None else None
        if bind is not None and getattr(bind, "dialect", None) and bind.dialect.name == "sqlite":
            try:
                if inspect(bind).has_table("product_search_fts"):
                    fts_query = " ".join(f"{token}*" for token in search_term.split() if token)
                    if fts_query:
                        return query.join(
                            PRODUCT_SEARCH_INDEX_TABLE,
                            and_(
                                PRODUCT_SEARCH_INDEX_TABLE.c.product_id == Product.id,
                                PRODUCT_SEARCH_INDEX_TABLE.c.region == Product.region,
                            )
                        ).filter(PRODUCT_SEARCH_INDEX_TABLE.c.search_text.match(fts_query))
            except Exception:
                pass

        search_pattern = f"%{search_term}%"
        return query.filter(
            or_(
                func.normalize_search(Product.id).like(search_pattern),
                func.normalize_search(Product.main_name).like(search_pattern),
                func.normalize_search(Product.name).like(search_pattern),
                func.normalize_search(Product.description).like(search_pattern),
                func.normalize_search(Product.publisher).like(search_pattern),
                func.normalize_search(Product.search_names).like(search_pattern),
                func.normalize_search(Product.tags).like(search_pattern),
            )
        )

    @staticmethod
    def _get_localization_priority(localization_code: Optional[str]) -> int:
        priorities = {
            'full': 0,
            'subtitles': 1,
            'interface': 2,
            'none': 3,
        }
        normalized = (localization_code or '').strip().lower()
        return priorities.get(normalized, 4)

    @staticmethod
    def _candidate_selection_score(
        product: Product,
        region_priority: Dict[str, int],
        exact_product_id: Optional[str] = None,
    ) -> tuple[int, int, int, str, str]:
        region = ProductCRUD.normalize_product_region(getattr(product, 'region', None))
        if not region:
            region = (str(getattr(product, 'region', '')).strip().upper() or None)

        exact_id_rank = 1
        normalized_product_id = ProductCRUD._normalize_product_id_token(getattr(product, 'id', None))
        if exact_product_id and normalized_product_id == exact_product_id:
            exact_id_rank = 0

        return (
            ProductCRUD._get_localization_priority(getattr(product, 'localization', None)),
            region_priority.get(region, len(region_priority)) if region else len(region_priority),
            exact_id_rank,
            ProductCRUD._normalize_search_text(ProductCRUD._get_product_sort_name(product)),
            normalized_product_id or '',
        )

    @staticmethod
    def _collect_product_candidates_by_identifier(db: Session, product_id: str) -> List[Product]:
        normalized_product_id = ProductCRUD._normalize_product_id_token(product_id)
        if not normalized_product_id:
            return []

        return db.query(Product).filter(
            or_(
                Product.id == normalized_product_id,
                Product.search_names.ilike(f"%{normalized_product_id}%"),
            )
        ).all()

    @staticmethod
    def _normalize_product_identity_name(value: Optional[str]) -> str:
        return ProductCRUD._normalize_search_text(value)

    @staticmethod
    def _get_product_identity_names(product: Product) -> set[str]:
        names = {
            ProductCRUD._normalize_product_identity_name(getattr(product, 'main_name', None)),
            ProductCRUD._normalize_product_identity_name(getattr(product, 'name', None)),
        }

        search_names = getattr(product, 'search_names', None)
        if search_names:
            names.update(
                ProductCRUD._normalize_product_identity_name(part)
                for part in str(search_names).split(',')
            )
        names.discard('')
        return {name for name in names if len(name) >= 4}

    @staticmethod
    def _has_region_price(product: Product, region_code: str) -> bool:
        price_field_by_region = {
            'UA': 'price_uah',
            'TR': 'price_try',
            'IN': 'price_inr',
        }
        price_field = price_field_by_region.get(region_code)
        if price_field is None:
            return False

        price = getattr(product, price_field, None)
        return bool(price and price > 0)

    @staticmethod
    def _augment_regional_products_with_equivalents(
        db: Session,
        product: Product,
        regional_products: List[Product],
        visible_regions: Optional[List[str]] = None,
    ) -> List[Product]:
        regional_by_code: Dict[str, Product] = {}
        for item in regional_products:
            region = ProductCRUD.normalize_product_region(getattr(item, 'region', None))
            if region:
                regional_by_code[region] = item

        existing_regions = {
            region
            for region, item in regional_by_code.items()
            if ProductCRUD._has_region_price(item, region)
        }
        target_regions = visible_regions or ['TR', 'IN', 'UA']
        missing_regions = [
            region
            for region in target_regions
            if region not in existing_regions
        ]

        if not missing_regions:
            return regional_products

        identity_names = ProductCRUD._get_product_identity_names(product)
        if not identity_names:
            return regional_products

        candidates_query = db.query(Product).filter(
            Product.region.in_(missing_regions),
            Product.type == product.type,
        )

        candidates = candidates_query.all()
        for candidate in candidates:
            candidate_region = ProductCRUD.normalize_product_region(getattr(candidate, 'region', None))
            if not candidate_region:
                continue

            if not ProductCRUD._has_region_price(candidate, candidate_region):
                continue

            current = regional_by_code.get(candidate_region)
            if current is not None and ProductCRUD._has_region_price(current, candidate_region):
                continue

            candidate_names = ProductCRUD._get_product_identity_names(candidate)
            if identity_names.isdisjoint(candidate_names):
                continue

            regional_by_code[candidate_region] = candidate

        return [item for item in regional_by_code.values() if item is not None]

    @staticmethod
    def normalize_product_region(region: Optional[str]) -> Optional[str]:
        """Привести значение region из БД к каноническому TR / UA / IN."""
        if region is None or str(region).strip() == '':
            return None
        r = str(region).strip().upper()
        if r in ('TR', 'UA', 'IN'):
            return r
        aliases = {
            'EN-TR': 'TR',
            'EN-UA': 'UA',
            'EN-IN': 'IN',
            'RU-TR': 'TR',
            'RU-UA': 'UA',
            'RU-IN': 'IN',
        }
        return aliases.get(r)

    @staticmethod
    def _get_favorites_count_subquery(db: Session):
        return (
            db.query(
                UserFavoriteProduct.product_id.label('product_id'),
                func.count(UserFavoriteProduct.id).label('favorites_count'),
            )
            .group_by(UserFavoriteProduct.product_id)
            .subquery()
        )

    @staticmethod
    def _get_region_priority(user: Optional[User] = None, filter_region: Optional[str] = None) -> Dict[str, int]:
        """Вернуть приоритет регионов для выбора базовой записи товара."""
        default_order = ['TR', 'IN', 'UA']

        if filter_region and filter_region in default_order:
            ordered_regions = [filter_region] + [region for region in default_order if region != filter_region]
        else:
            preferred_region = getattr(user, 'preferred_region', None)
            if preferred_region in default_order:
                ordered_regions = [preferred_region] + [region for region in default_order if region != preferred_region]
            else:
                ordered_regions = default_order

        return {region: index for index, region in enumerate(ordered_regions)}

    @staticmethod
    def _get_product_sort_name(product: Product) -> str:
        """Получить безопасное имя товара для сортировки и группировки."""
        return ProductCRUD._normalize_search_text(
            getattr(product, 'main_name', None)
            or getattr(product, 'name', None)
            or ''
        )

    @staticmethod
    def _group_product_rows(
        rows: List[tuple[Product, Optional[float]]],
        user: Optional[User] = None,
        filter_region: Optional[str] = None
    ) -> List[tuple[Product, Optional[float]]]:
        """
        Сгруппировать товары по ID, оставив одну базовую запись на товар.

        В БД один и тот же товар хранится отдельной строкой для каждого региона.
        Для каталога и главной страницы нужна одна карточка товара с мультирегиональными ценами,
        поэтому здесь выбирается только одна представительная строка на `product.id`.
        """
        region_priority = ProductCRUD._get_region_priority(user, filter_region)
        grouped_rows: Dict[str, tuple[Product, Optional[float]]] = {}

        for product, price_rub in rows:
            current = grouped_rows.get(product.id)
            if current is None:
                grouped_rows[product.id] = (product, price_rub)
                continue

            current_product, _ = current
            current_score = ProductCRUD._candidate_selection_score(current_product, region_priority)
            next_score = ProductCRUD._candidate_selection_score(product, region_priority)

            if next_score < current_score:
                grouped_rows[product.id] = (product, price_rub)

        return sorted(
            grouped_rows.values(),
            key=lambda item: (ProductCRUD._get_product_sort_name(item[0]), item[0].id),
        )

    @staticmethod
    def _choose_representative_products(
        products: List[Product],
        user: Optional[User] = None,
        filter_region: Optional[str] = None,
    ) -> Dict[str, Product]:
        region_priority = ProductCRUD._get_region_priority(user, filter_region)
        representatives: Dict[str, Product] = {}

        for product in products:
            current = representatives.get(product.id)
            if current is None:
                representatives[product.id] = product
                continue

            current_score = ProductCRUD._candidate_selection_score(current, region_priority)
            next_score = ProductCRUD._candidate_selection_score(product, region_priority)

            if next_score < current_score:
                representatives[product.id] = product

        return representatives

    @staticmethod
    def _get_localization_name_cached(
        db: Session,
        localization_code: Optional[str],
        localization_cache: Optional[Dict[str, Optional[str]]] = None,
    ) -> Optional[str]:
        if not localization_code:
            return None

        if localization_cache is not None and localization_code in localization_cache:
            return localization_cache[localization_code]

        localization_name = ProductCRUD.get_localization_name(db, localization_code)

        if localization_cache is not None:
            localization_cache[localization_code] = localization_name

        return localization_name

    @staticmethod
    def _collect_regional_price_data(
        regional_products: List[Product],
        db: Session,
        localization_cache: Optional[Dict[str, Optional[str]]] = None,
    ) -> Dict[str, Any]:
        region_mapping = {
            'UA': {
                'flag': '🇺🇦',
                'name': 'Украина',
                'code': 'UAH',
                'price_field': 'price_uah',
                'old_price_field': 'old_price_uah',
                'ps_plus_price_field': 'ps_plus_price_uah',
            },
            'TR': {
                'flag': '🇹🇷',
                'name': 'Турция',
                'code': 'TRY',
                'price_field': 'price_try',
                'old_price_field': 'old_price_try',
                'ps_plus_price_field': 'ps_plus_price_try',
            },
            'IN': {
                'flag': '🇮🇳',
                'name': 'Индия',
                'code': 'INR',
                'price_field': 'price_inr',
                'old_price_field': 'old_price_inr',
                'ps_plus_price_field': 'ps_plus_price_inr',
            },
        }

        regional_by_code: Dict[str, Product] = {}
        for rp in regional_products:
            code = ProductCRUD.normalize_product_region(getattr(rp, 'region', None))
            if code:
                regional_by_code[code] = rp

        regional_prices: List[Dict[str, Any]] = []
        min_price_rub: Optional[float] = None
        min_old_price_rub: Optional[float] = None

        from app.models.currency_rate import CurrencyRate

        for region_code in ('TR', 'IN', 'UA'):
            regional_product = regional_by_code.get(region_code)
            region_info = region_mapping.get(region_code)

            if regional_product is None or region_info is None:
                continue

            price = getattr(regional_product, region_info['price_field'], None)
            old_price = getattr(regional_product, region_info['old_price_field'], None)
            ps_plus_price = getattr(regional_product, region_info['ps_plus_price_field'], None)

            if price is None or price <= 0:
                continue

            rate = CurrencyRate.get_rate_for_price(db, region_info['code'], price)
            price_rub = round(price * rate, 2)
            old_price_rub = round(old_price * rate, 2) if old_price and old_price > 0 else None
            ps_plus_price_rub = round(ps_plus_price * rate, 2) if ps_plus_price and ps_plus_price > 0 else None

            has_discount = bool(old_price and old_price > price)
            discount_percent = int(((old_price - price) / old_price) * 100) if has_discount else None

            ps_plus_discount_percent = None
            if ps_plus_price_rub and old_price_rub and ps_plus_price_rub < old_price_rub:
                ps_plus_discount_percent = int(((old_price_rub - ps_plus_price_rub) / old_price_rub) * 100)

            localization_code = regional_product.localization
            localization_name = ProductCRUD._get_localization_name_cached(
                db,
                localization_code,
                localization_cache,
            )

            regional_prices.append(
                {
                    'region': region_code,
                    'flag': region_info['flag'],
                    'name': region_info['name'],
                    'currency_code': region_info['code'],
                    'price_local': price,
                    'old_price_local': old_price if old_price and old_price > 0 else None,
                    'ps_plus_price_local': ps_plus_price if ps_plus_price and ps_plus_price > 0 else None,
                    'price_rub': price_rub,
                    'old_price_rub': old_price_rub,
                    'ps_plus_price_rub': ps_plus_price_rub,
                    'has_discount': has_discount,
                    'discount_percent': discount_percent,
                    'ps_plus_discount_percent': ps_plus_discount_percent,
                    'localization_code': localization_code,
                    'localization_name': localization_name,
                }
            )

            if min_price_rub is None or price_rub < min_price_rub:
                min_price_rub = price_rub
                min_old_price_rub = old_price_rub

        max_discount_percent = None
        discounts = [price.get('discount_percent') for price in regional_prices if price.get('discount_percent')]
        if discounts:
            max_discount_percent = max(discounts)

        return {
            'regional_prices': regional_prices,
            'min_price_rub': min_price_rub,
            'min_old_price_rub': min_old_price_rub,
            'max_discount_percent': max_discount_percent,
        }

    @staticmethod
    def _get_active_currency_rates_by_region(db: Session) -> Dict[str, List[CurrencyRate]]:
        rates_by_region: Dict[str, List[CurrencyRate]] = {
            'TR': [],
            'IN': [],
            'UA': [],
        }

        active_rates = (
            db.query(CurrencyRate)
            .filter(
                CurrencyRate.is_active == True,
                CurrencyRate.currency_to == 'RUB',
            )
            .order_by(
                CurrencyRate.currency_from.asc(),
                CurrencyRate.price_min.asc(),
            )
            .all()
        )

        for rate in active_rates:
            currency_from = (rate.currency_from or '').upper()
            if currency_from in {'TRY', 'TRL'}:
                rates_by_region['TR'].append(rate)
            elif currency_from == 'INR':
                rates_by_region['IN'].append(rate)
            elif currency_from == 'UAH':
                rates_by_region['UA'].append(rate)

        return rates_by_region

    @staticmethod
    def _build_rate_case_for_price(price_column, rates: List[CurrencyRate]):
        if not rates:
            return literal(1.0)

        whens = []
        for rate in rates:
            condition = price_column >= rate.price_min
            if rate.price_max is not None:
                condition = and_(condition, price_column <= rate.price_max)
            whens.append((condition, literal(float(rate.rate))))

        return case(*whens, else_=literal(1.0))

    @staticmethod
    def _build_row_price_rub_expression(db: Session):
        rates_by_region = ProductCRUD._get_active_currency_rates_by_region(db)

        tr_rate_case = ProductCRUD._build_rate_case_for_price(Product.price_try, rates_by_region['TR'])
        in_rate_case = ProductCRUD._build_rate_case_for_price(Product.price_inr, rates_by_region['IN'])
        ua_rate_case = ProductCRUD._build_rate_case_for_price(Product.price_uah, rates_by_region['UA'])

        return case(
            (
                and_(
                    Product.region == 'TR',
                    Product.price_try.isnot(None),
                    Product.price_try > 0,
                ),
                Product.price_try * tr_rate_case,
            ),
            (
                and_(
                    Product.region == 'IN',
                    Product.price_inr.isnot(None),
                    Product.price_inr > 0,
                ),
                Product.price_inr * in_rate_case,
            ),
            (
                and_(
                    Product.region == 'UA',
                    Product.price_uah.isnot(None),
                    Product.price_uah > 0,
                ),
                Product.price_uah * ua_rate_case,
            ),
            else_=None,
        )

    @staticmethod
    def _build_row_price_expression(db: Session, price_currency: Optional[str]):
        normalized_currency = (price_currency or 'RUB').upper()
        if normalized_currency == 'RUB':
            return ProductCRUD._build_row_price_rub_expression(db)

        currency_region_map = {
            'TRY': ('TR', Product.price_try),
            'TRL': ('TR', Product.price_try),
            'INR': ('IN', Product.price_inr),
            'UAH': ('UA', Product.price_uah),
        }
        region_code, price_column = currency_region_map.get(normalized_currency, (None, None))
        if region_code is None or price_column is None:
            return ProductCRUD._build_row_price_rub_expression(db)

        return case(
            (
                and_(
                    Product.region == region_code,
                    price_column.isnot(None),
                    price_column > 0,
                ),
                price_column,
            ),
            else_=None,
        )

    @staticmethod
    def _select_product_variant(
        candidates: List[Product],
        requested_region: Optional[str] = None,
        *,
        exact_product_id: Optional[str] = None,
        allow_region_fallback: bool = False,
    ) -> Optional[Product]:
        if not candidates:
            return None

        region_code = ProductCRUD.normalize_product_region(requested_region) if requested_region else None
        if not region_code and requested_region:
            region_code = str(requested_region).strip().upper() or None

        if region_code:
            region_candidates = [
                product
                for product in candidates
                if (ProductCRUD.normalize_product_region(getattr(product, 'region', None))
                    or (str(getattr(product, 'region', '')).strip().upper() or None)) == region_code
            ]
            if region_candidates:
                candidates = region_candidates
            elif not allow_region_fallback:
                return None

        region_priority = ProductCRUD._get_region_priority(None, region_code)
        return min(
            candidates,
            key=lambda product: ProductCRUD._candidate_selection_score(
                product,
                region_priority,
                exact_product_id=exact_product_id,
            ),
        )

    @staticmethod
    def get_by_id(db: Session, product_id: str, region: Optional[str] = None) -> Optional[Product]:
        """Получить товар по ID с учетом региона"""
        import logging
        logger = logging.getLogger(__name__)

        normalized_product_id = ProductCRUD._normalize_product_id_token(product_id)
        logger.info(f"🔎 get_by_id called: product_id={normalized_product_id}, region={region}")

        if not normalized_product_id:
            logger.error("❌ Product NOT found: empty product_id")
            return None

        candidates = ProductCRUD._collect_product_candidates_by_identifier(db, normalized_product_id)
        if not candidates:
            logger.error("❌ Product NOT found!")
            return None

        product = ProductCRUD._select_product_variant(
            candidates,
            region,
            exact_product_id=normalized_product_id,
            allow_region_fallback=False,
        )

        if product:
            logger.info(
                "✅ Found product: region=%s, localization=%s, name=%s",
                product.region,
                product.localization,
                (product.name or '')[:50],
            )
        else:
            logger.error("❌ Product NOT found in requested region!")

        return product

    @staticmethod
    def get_by_id_with_fallback(db: Session, product_id: str, region: Optional[str] = None) -> Optional[Product]:
        """Получить товар по ID с мягким фолбэком на другой регион, если запрошенный отсутствует."""
        normalized_product_id = ProductCRUD._normalize_product_id_token(product_id)
        if not normalized_product_id:
            return None

        candidates = ProductCRUD._collect_product_candidates_by_identifier(db, normalized_product_id)
        return ProductCRUD._select_product_variant(
            candidates,
            region,
            exact_product_id=normalized_product_id,
            allow_region_fallback=True,
        )

    @staticmethod
    def get_by_id_all_regions(db: Session, product_id: str) -> List[Product]:
        """Получить товар во всех регионах"""
        product = ProductCRUD.get_by_id_with_fallback(db, product_id)
        if not product:
            return []
        return db.query(Product).filter(Product.id == product.id).all()

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

        query = ProductCRUD._apply_product_kind_filter(query, getattr(filters, 'product_kind', None))

        if filters.region:
            query = query.filter(Product.region == filters.region)

        if filters.search:
            query = ProductCRUD._apply_search_filter(query, filters.search)

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
        top_level_categories = set()
        for category_value, in categories:
            if not category_value:
                continue
            top_level = category_value.split(',', 1)[0].strip()
            if top_level:
                top_level_categories.add(top_level)
        return sorted(top_level_categories)

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
    def prepare_product_with_multi_region_prices(
        product: Product,
        db: Session,
        user: Optional[User] = None,
        filter_region: Optional[str] = None,
        regional_products: Optional[List[Product]] = None,
        localization_cache: Optional[Dict[str, Optional[str]]] = None,
        favorites_count: int = 0,
    ) -> dict:
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
        regional_products = regional_products or db.query(Product).filter(Product.id == product.id).all()
        regional_products = ProductCRUD._augment_regional_products_with_equivalents(
            db,
            product,
            regional_products,
            visible_regions=['TR', 'IN', 'UA'],
        )
        regional_price_data = ProductCRUD._collect_regional_price_data(
            regional_products,
            db,
            localization_cache,
        )
        regional_prices = regional_price_data['regional_prices']
        min_price = regional_price_data['min_price_rub']
        min_price_old = regional_price_data['min_old_price_rub']
        localization_name = ProductCRUD._get_localization_name_cached(
            db,
            product.localization,
            localization_cache,
        )

        product_dict = {
            'id': product.id,
            'name': product.name,
            'main_name': product.get_display_name(),
            'category': product.category,
            'type': product.type,
            'region': product.region,
            'image': product.image,
            'publisher': product.publisher,
            'description': product.description,
            'rating': product.rating,
            'edition': product.edition,
            'platforms': product.platforms,
            'localization': product.localization,
            'localization_name': localization_name,
            'has_discount': any(price['has_discount'] for price in regional_prices),
            'discount': product.discount,
            'discount_end': product.discount_end,
            'discount_percent': regional_price_data['max_discount_percent'],
            'ps_plus': product.ps_plus,
            'has_ps_plus': product.has_ps_plus,
            'ps_price': product.ps_price,
            'has_ea_access': product.has_ea_access,
            'ea_access': product.ea_access,
            'ps_plus_collection': product.ps_plus_collection,
            'has_ps_plus_extra_deluxe': product.has_ps_plus_extra_deluxe,
            'favorites_count': int(favorites_count or 0),
            'compound': product.get_compound_list(),
            'info': product.get_info_list(),
            'tags': product.get_tags_list(),
            'players_min': product.players_min,
            'players_max': product.players_max,
            'players_online': bool(product.players_online),
            'regional_prices': regional_prices,
            'min_price_rub': min_price,
            'price_try': product.price_try,
            'old_price_try': product.old_price_try,
            'price_inr': product.price_inr,
            'old_price_inr': product.old_price_inr,
            'price_uah': product.price_uah,
            'old_price_uah': product.old_price_uah,
            'rub_price': min_price,
            'rub_price_old': min_price_old,
        }

        return product_dict

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
                        'price_local': price,
                        'old_price_local': old_price if old_price and old_price > 0 else None,
                        'ps_plus_price_local': ps_plus_price if ps_plus_price and ps_plus_price > 0 else None,
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
            'players_min': product.players_min,
            'players_max': product.players_max,
            'players_online': bool(product.players_online),
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
        # Все варианты товара по id; цены по регионам — единая логика с каталогом
        regional_products = db.query(Product).filter(Product.id == product.id).all()
        regional_products = ProductCRUD._augment_regional_products_with_equivalents(
            db,
            product,
            regional_products,
            visible_regions=['TR', 'IN', 'UA'],
        )
        regional_price_data = ProductCRUD._collect_regional_price_data(regional_products, db)
        regional_prices = regional_price_data['regional_prices']
        min_price = regional_price_data['min_price_rub']
        min_price_old = regional_price_data['min_old_price_rub']

        localization_name = ProductCRUD.get_localization_name(db, product.localization)
        canon_region = ProductCRUD.normalize_product_region(product.region)
        display_region = canon_region if canon_region else product.region

        return {
            'id': product.id,
            'name': product.name,
            'main_name': product.get_display_name(),
            'category': product.category,
            'type': product.type,
            'region': display_region,
            'image': product.image,
            'publisher': product.publisher,
            'description': product.description,
            'rating': product.rating,
            'edition': product.edition,
            'platforms': product.platforms,
            'localization': product.localization,
            'localization_name': localization_name,
            'has_discount': any(p['has_discount'] for p in regional_prices) if regional_prices else False,
            'discount': product.discount,
            'discount_end': product.discount_end,
            'discount_percent': regional_price_data.get('max_discount_percent'),
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
            'players_min': product.players_min,
            'players_max': product.players_max,
            'players_online': bool(product.players_online),
            'regional_prices': regional_prices,
            'min_price': min_price,
            'min_price_old': min_price_old,
            'min_price_rub': min_price,
            'rub_price': min_price,
            'rub_price_old': min_price_old,
        }

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

        query = ProductCRUD._apply_product_kind_filter(query, getattr(filters, 'product_kind', None))

        if filters.search:
            query = ProductCRUD._apply_search_filter(query, filters.search)

        # Получаем все товары уже после применения фильтров
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
            visible_regions = [filter_region]
            query = query.filter(Product.region == filter_region)
        else:
            # Если регион не указан, берем настройки пользователя или все регионы
            if user:
                visible_regions = user.get_enabled_regions()
            else:
                visible_regions = ['UA', 'TR', 'IN']
            query = query.filter(Product.region.in_(visible_regions))

        # Применяем фильтры
        if filters.category:
            query = query.filter(Product.category.ilike(f"%{filters.category}%"))

        query = ProductCRUD._apply_product_kind_filter(query, getattr(filters, 'product_kind', None))

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
            elif platform_filter in ('PSVR2', 'PLAYSTATION_VR2'):
                query = query.filter(Product.info.ilike('%VR2%'))
            elif platform_filter in ('PSVR1', 'PSVR', 'PLAYSTATION_VR1'):
                query = query.filter(
                    and_(
                        or_(
                            Product.info.ilike('%PS VR%'),
                            Product.info.ilike('%PSVR%'),
                            Product.info.ilike('%PlayStation%VR%'),
                            Product.info.ilike('%PS Camera%')
                        ),
                        ~Product.info.ilike('%VR2%')
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
            query = ProductCRUD._apply_search_filter(query, filters.search)

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

        game_language = (getattr(filters, 'game_language', None) or '').strip().lower()
        if game_language in ('full_ru', 'partial_ru', 'no_ru'):
            query = query.outerjoin(Localization, Localization.code == Product.localization)
            if game_language == 'full_ru':
                query = query.filter(
                    or_(
                        Localization.name_ru.ilike('%полностью%рус%'),
                        Localization.name_ru.ilike('%полностью на русском%'),
                    )
                )
            elif game_language == 'partial_ru':
                query = query.filter(
                    or_(
                        Localization.name_ru.ilike('%субтитр%рус%'),
                        Localization.name_ru.ilike('%русск%интерфейс%'),
                        Localization.name_ru.ilike('%русские субтитры%'),
                    )
                )
            else:
                query = query.filter(
                    or_(
                        Localization.name_ru.ilike('%без русского%'),
                        Localization.name_ru.ilike('%нет русского%'),
                        Localization.name_ru.ilike('%английский%'),
                        Localization.name_ru.ilike('%только англ%'),
                    )
                )

        sort_mode = ProductCRUD._normalize_sort_mode(getattr(filters, 'sort', None))
        favorites_subquery = ProductCRUD._get_favorites_count_subquery(db)
        localization_cache: Dict[str, Optional[str]] = {}
        product_id_column = Product.id.label('product_id')
        sort_name_column = func.min(
            func.lower(func.coalesce(Product.main_name, Product.name, Product.id))
        ).label('sort_name')
        favorites_count_column = func.coalesce(favorites_subquery.c.favorites_count, 0).label('favorites_count')
        price_filter_currency = (getattr(filters, 'price_currency', None) or 'RUB').upper()
        row_price_column = ProductCRUD._build_row_price_expression(db, price_filter_currency)
        min_price_filter_column = func.min(row_price_column).label('min_price_filter')
        null_prices_last_column = case((min_price_filter_column.is_(None), 1), else_=0)

        grouped_query = (
            query.outerjoin(favorites_subquery, favorites_subquery.c.product_id == Product.id)
            .with_entities(
                product_id_column,
                sort_name_column,
                favorites_count_column,
                min_price_filter_column,
            )
            .group_by(Product.id, favorites_subquery.c.favorites_count)
        )

        if filters.min_price is not None:
            grouped_query = grouped_query.having(min_price_filter_column >= filters.min_price)

        if filters.max_price is not None:
            grouped_query = grouped_query.having(min_price_filter_column <= filters.max_price)

        total = db.query(func.count()).select_from(grouped_query.order_by(None).subquery()).scalar() or 0

        if sort_mode == 'price_desc':
            grouped_query = grouped_query.order_by(
                null_prices_last_column.asc(),
                min_price_filter_column.desc(),
                sort_name_column.asc(),
                product_id_column.asc(),
            )
        elif sort_mode == 'price_asc':
            grouped_query = grouped_query.order_by(
                null_prices_last_column.asc(),
                min_price_filter_column.asc(),
                sort_name_column.asc(),
                product_id_column.asc(),
            )
        elif sort_mode == 'alphabet':
            grouped_query = grouped_query.order_by(sort_name_column.asc(), product_id_column.asc())
        else:
            grouped_query = grouped_query.order_by(
                favorites_count_column.desc(),
                sort_name_column.asc(),
                product_id_column.asc(),
            )

        page_rows = (
            grouped_query
            .offset(max(pagination.page - 1, 0) * pagination.limit)
            .limit(pagination.limit)
            .all()
        )

        page_ids = [row.product_id for row in page_rows]
        if not page_ids:
            return [], total

        page_favorites_map = {
            row.product_id: int(row.favorites_count or 0)
            for row in page_rows
        }

        page_products = (
            db.query(Product)
            .filter(
                Product.id.in_(page_ids),
                Product.region.in_(visible_regions),
            )
            .all()
        )
        regional_products_by_id: Dict[str, List[Product]] = defaultdict(list)
        for product in page_products:
            regional_products_by_id[product.id].append(product)

        representative_map = ProductCRUD._choose_representative_products(
            page_products,
            user=user,
            filter_region=filter_region,
        )

        result = []
        for product_id in page_ids:
            representative = representative_map.get(product_id)
            if representative is None:
                continue

            result.append(
                ProductCRUD.prepare_product_with_multi_region_prices(
                    representative,
                    db,
                    user,
                    filter_region,
                    regional_products=regional_products_by_id.get(product_id, [representative]),
                    localization_cache=localization_cache,
                    favorites_count=page_favorites_map.get(product_id, 0),
                )
            )

        return result, total

class FavoriteCRUD:
    @staticmethod
    def _resolve_favorite_product_candidates(
        db: Session,
        product_id: str,
        region: Optional[str] = None,
    ) -> tuple[List[str], Optional[Product], Optional[str]]:
        normalized_product_id = ProductCRUD._normalize_product_id_token(product_id)
        if not normalized_product_id:
            return [], None, None

        resolved_product = ProductCRUD.get_by_id_with_fallback(db, normalized_product_id, region)
        candidate_ids = [normalized_product_id]
        if resolved_product and resolved_product.id:
            candidate_ids.insert(0, resolved_product.id)

        candidate_ids = list(dict.fromkeys(candidate_ids))
        resolved_region = None
        if resolved_product and resolved_product.region:
            resolved_region = (
                ProductCRUD.normalize_product_region(resolved_product.region)
                or str(resolved_product.region).strip().upper()
                or None
            )
        elif region:
            resolved_region = ProductCRUD.normalize_product_region(region) or str(region).strip().upper() or None

        return candidate_ids, resolved_product, resolved_region

    @staticmethod
    def add_to_favorites(db: Session, user_id: int, product_id: str, region: Optional[str] = None) -> Optional[UserFavoriteProduct]:
        """Добавить товар в избранное"""
        product_ids, product, resolved_region = FavoriteCRUD._resolve_favorite_product_candidates(db, product_id, region)
        if not product_ids or not product:
            return None

        product_id = product.id
        region = resolved_region

        # Проверяем, что товар не уже в избранном
        existing = db.query(UserFavoriteProduct).filter(
            and_(
                UserFavoriteProduct.user_id == user_id,
                UserFavoriteProduct.product_id.in_(product_ids)
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
        product_ids, _, _ = FavoriteCRUD._resolve_favorite_product_candidates(db, product_id)
        if not product_ids:
            return False

        favorite = db.query(UserFavoriteProduct).filter(
            and_(
                UserFavoriteProduct.user_id == user_id,
                UserFavoriteProduct.product_id.in_(product_ids)
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
        product_ids, _, _ = FavoriteCRUD._resolve_favorite_product_candidates(db, product_id)
        if not product_ids:
            return False

        return db.query(UserFavoriteProduct).filter(
            and_(
                UserFavoriteProduct.user_id == user_id,
                UserFavoriteProduct.product_id.in_(product_ids)
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
                'has_psn_credentials': user.has_psn_credentials,
                'is_admin': user.telegram_id in settings.ADMIN_TELEGRAM_IDS
            }
            users.append(user_data)

        return users

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def delete_user(db: Session, user: User) -> bool:
        db.delete(user)
        db.commit()
        return True

# Создаем экземпляры для использования
user_crud = UserCRUD()
product_crud = ProductCRUD()
favorite_crud = FavoriteCRUD()
currency_rate_crud = CurrencyRateCRUD()
admin_crud = AdminCRUD()
