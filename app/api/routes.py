from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime
from urllib.parse import quote, urlparse, parse_qs, urlencode, urlunparse
from app.database.connection import get_db
from app.api.schemas import (
    User, UserCreate, UserUpdate, UserWithFavorites,
    Product, ProductListResponse, ProductFilter, PaginationParams,
    Favorite, FavoriteCreate, RegionEnum, RegionSettings,
    PSNCredentials, PSNCredentialsResponse,
    PSNAccountCreate, PSNAccountUpdate, PSNAccountResponse, PSNAccountsListResponse,
    PaymentEmailUpdate, PaymentEmailResponse
)
from app.api.crud import user_crud, product_crud, favorite_crud
from app.api.payment import payment_api, PaymentAPIError
from app.api.payment_india import india_payment_api, IndiaPaymentAPIError, CardPurchaseInfo
from app.api.payment_ukraine import ukraine_payment_api, UkrainePaymentAPIError, UkrainePaymentInfo
from app.api.payment_turkey import turkey_payment_api, TurkeyPaymentAPIError
from app.utils.network_check import diagnose_payment_site_issues

logger = logging.getLogger(__name__)

router = APIRouter()

# Роуты для пользователей
@router.post("/users/", response_model=User, tags=["Users"], summary="Создать пользователя")
async def create_user(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    """Создать нового пользователя или получить существующего"""
    user, created = user_crud.get_or_create(db, user_data)
    return user

@router.get("/users/{telegram_id}", response_model=UserWithFavorites, tags=["Users"], summary="Получить пользователя")
async def get_user(request: Request, telegram_id: int, db: Session = Depends(get_db)):
    """Получить пользователя по Telegram ID"""
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return user

@router.put("/users/{telegram_id}", response_model=User, tags=["Users"], summary="Обновить пользователя")
async def update_user(
    telegram_id: int,
    update_data: UserUpdate,
    db: Session = Depends(get_db)
):
    """Обновить данные пользователя"""
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return user_crud.update(db, user, update_data)

@router.put("/users/{telegram_id}/region-settings", response_model=User, tags=["Users"], summary="Обновить настройки регионов")
async def update_region_settings(
    telegram_id: int,
    region_settings: RegionSettings,
    db: Session = Depends(get_db)
):
    """Обновить настройки отображения региональных цен"""
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    update_data = UserUpdate(
        show_ukraine_prices=region_settings.show_ukraine_prices,
        show_turkey_prices=region_settings.show_turkey_prices,
        show_india_prices=region_settings.show_india_prices
    )

    return user_crud.update(db, user, update_data)

@router.get("/users/{telegram_id}/region-settings", response_model=RegionSettings, tags=["Users"], summary="Получить настройки регионов")
async def get_region_settings(telegram_id: int, db: Session = Depends(get_db)):
    """Получить настройки региональных цен пользователя"""
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return RegionSettings(
        show_ukraine_prices=user.show_ukraine_prices,
        show_turkey_prices=user.show_turkey_prices,
        show_india_prices=user.show_india_prices
    )

@router.put("/users/{telegram_id}/psn-credentials", response_model=dict, tags=["Users"], summary="Обновить PSN данные")
async def update_psn_credentials(
    telegram_id: int,
    psn_data: PSNCredentials,
    db: Session = Depends(get_db)
):
    """Обновить PSN данные пользователя"""
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Обновляем данные
    if psn_data.platform is not None:
        user.platform = psn_data.platform.value
    if psn_data.psn_email is not None:
        user.psn_email = psn_data.psn_email
    if psn_data.psn_password is not None:
        user.set_psn_password(psn_data.psn_password)

    db.commit()
    db.refresh(user)

    return {"message": "PSN данные обновлены успешно"}

@router.get("/users/{telegram_id}/psn-credentials", response_model=PSNCredentialsResponse, tags=["Users"], summary="Получить PSN данные")
async def get_psn_credentials(telegram_id: int, db: Session = Depends(get_db)):
    """Получить PSN данные пользователя (без пароля) - старый глобальный метод"""
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return PSNCredentialsResponse(
        platform=user.platform,
        psn_email=user.psn_email,
        has_password=bool(user.psn_password_hash)
    )


# ========================================
# Роуты для Email привязки покупки
# ========================================

@router.get("/users/{telegram_id}/payment-email", response_model=PaymentEmailResponse, tags=["Users"], summary="Получить email привязки покупки")
async def get_payment_email(telegram_id: int, db: Session = Depends(get_db)):
    """Получить email для привязки покупки на oplata.info"""
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return PaymentEmailResponse(payment_email=user.payment_email)


@router.put("/users/{telegram_id}/payment-email", response_model=dict, tags=["Users"], summary="Обновить email привязки покупки")
async def update_payment_email(
    telegram_id: int,
    email_data: PaymentEmailUpdate,
    db: Session = Depends(get_db)
):
    """Обновить email для привязки покупки на oplata.info (общий для всех регионов)"""
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.payment_email = email_data.payment_email
    db.commit()
    db.refresh(user)

    logger.info(f"Payment email updated for user {telegram_id}: {email_data.payment_email}")
    return {"message": "Email для привязки покупки сохранен", "payment_email": user.payment_email}


# ========================================
# Роуты для региональных PSN аккаунтов
# ========================================

@router.get("/users/{telegram_id}/psn-accounts", response_model=PSNAccountsListResponse, tags=["PSN Accounts"], summary="Список PSN аккаунтов")
async def get_psn_accounts(telegram_id: int, db: Session = Depends(get_db)):
    """Получить все PSN аккаунты пользователя по регионам"""
    from app.models.psn_account import PSNAccount

    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    accounts = []
    for acc in user.psn_accounts:
        if acc.is_active:
            accounts.append(PSNAccountResponse(
                id=acc.id,
                region=acc.region,
                psn_email=acc.psn_email,
                platform=acc.platform,
                has_password=bool(acc.psn_password_hash),
                has_twofa=bool(acc.twofa_backup_code),
                is_active=bool(acc.is_active),
                region_info=acc.region_info
            ))

    return PSNAccountsListResponse(accounts=accounts, total=len(accounts))


@router.get("/users/{telegram_id}/psn-accounts/{region}", response_model=PSNAccountResponse, tags=["PSN Accounts"], summary="Получить PSN аккаунт региона")
async def get_psn_account_for_region(telegram_id: int, region: str, db: Session = Depends(get_db)):
    """Получить PSN аккаунт для конкретного региона"""
    from app.models.psn_account import PSNAccount

    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Нормализуем регион
    region = region.upper()
    if region not in ['UA', 'TR']:
        raise HTTPException(status_code=400, detail="Недопустимый регион. Используйте UA или TR")

    account = user.get_psn_account_for_region(region)
    if not account:
        raise HTTPException(status_code=404, detail=f"PSN аккаунт для региона {region} не найден")

    return PSNAccountResponse(
        id=account.id,
        region=account.region,
        psn_email=account.psn_email,
        platform=account.platform,
        has_password=bool(account.psn_password_hash),
        has_twofa=bool(account.twofa_backup_code),
        is_active=bool(account.is_active),
        region_info=account.region_info
    )


@router.put("/users/{telegram_id}/psn-accounts/{region}", response_model=dict, tags=["PSN Accounts"], summary="Создать/обновить PSN аккаунт")
async def set_psn_account(
    telegram_id: int,
    region: str,
    account_data: PSNAccountUpdate,
    db: Session = Depends(get_db)
):
    """Создать или обновить PSN аккаунт для конкретного региона"""
    from app.models.psn_account import PSNAccount

    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Нормализуем регион
    region = region.upper()
    if region not in ['UA', 'TR']:
        raise HTTPException(status_code=400, detail="Недопустимый регион. Используйте UA или TR. Индия использует карты пополнения.")

    # Ищем существующий аккаунт
    account = user.get_psn_account_for_region(region)

    if account:
        # Обновляем существующий
        if account_data.psn_email is not None:
            account.psn_email = account_data.psn_email
        if account_data.psn_password is not None:
            account.set_psn_password(account_data.psn_password)
        if account_data.platform is not None:
            account.platform = account_data.platform.value if account_data.platform else None
        if account_data.twofa_code is not None:
            account.set_twofa_code(account_data.twofa_code)

        db.commit()
        db.refresh(account)

        logger.info(f"PSN account updated: user={telegram_id}, region={region}")
        return {"message": f"PSN аккаунт для региона {region} обновлен", "id": account.id}

    else:
        # Создаем новый
        if not account_data.psn_email:
            raise HTTPException(status_code=400, detail="Email обязателен для нового аккаунта")
        if not account_data.psn_password:
            raise HTTPException(status_code=400, detail="Пароль обязателен для нового аккаунта")

        platform_value = account_data.platform.value if account_data.platform else ('PS5' if region == 'UA' else None)

        new_account = PSNAccount(
            user_id=user.id,
            region=region,
            psn_email=account_data.psn_email,
            platform=platform_value,
            is_active=1
        )
        new_account.set_psn_password(account_data.psn_password)
        if account_data.twofa_code:
            new_account.set_twofa_code(account_data.twofa_code)

        db.add(new_account)
        db.commit()
        db.refresh(new_account)

        logger.info(f"PSN account created: user={telegram_id}, region={region}")
        return {"message": f"PSN аккаунт для региона {region} создан", "id": new_account.id}


@router.delete("/users/{telegram_id}/psn-accounts/{region}", response_model=dict, tags=["PSN Accounts"], summary="Удалить PSN аккаунт")
async def delete_psn_account(telegram_id: int, region: str, db: Session = Depends(get_db)):
    """Удалить PSN аккаунт для конкретного региона"""
    from app.models.psn_account import PSNAccount

    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    region = region.upper()
    account = user.get_psn_account_for_region(region)

    if not account:
        raise HTTPException(status_code=404, detail=f"PSN аккаунт для региона {region} не найден")

    db.delete(account)
    db.commit()

    logger.info(f"PSN account deleted: user={telegram_id}, region={region}")
    return {"message": f"PSN аккаунт для региона {region} удален"}

# Роуты для товаров
@router.get("/products/", tags=["Products"], summary="Список товаров")
async def get_products(
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(20, ge=1, le=100, description="Количество элементов на странице"),
    category: Optional[str] = Query(None, description="Фильтр по категории"),
    region: Optional[str] = Query(None, description="Фильтр по региону (UA, TR, IN)"),
    search: Optional[str] = Query(None, description="Поиск по названию, описанию, издателю"),
    min_price: Optional[float] = Query(None, ge=0, description="Минимальная цена в рублях"),
    max_price: Optional[float] = Query(None, ge=0, description="Максимальная цена в рублях"),
    has_discount: Optional[bool] = Query(None, description="Только товары со скидкой"),
    has_ps_plus: Optional[bool] = Query(None, description="Доступно в PS Plus"),
    has_ea_access: Optional[bool] = Query(None, description="Доступно в EA Access"),
    platform: Optional[str] = Query(None, description="Фильтр по платформе (PS4, PS5, BOTH)"),
    players: Optional[str] = Query(None, description="Фильтр по количеству игроков"),
    telegram_id: Optional[int] = Query(None, description="ID пользователя для настроек отображения"),
    grouped: bool = Query(True, description="Группировать товары с ценами из всех регионов"),
    db: Session = Depends(get_db)
):
    """Получить список товаров с фильтрацией и пагинацией"""
    # Нормализуем регион: en-tr -> TR, en-in -> IN, en-ua -> UA
    region_normalize_map = {
        'en-ua': 'UA',
        'en-tr': 'TR',
        'en-in': 'IN',
        'ua': 'UA',
        'tr': 'TR',
        'in': 'IN',
        'uah': 'UA',
        'try': 'TR',
        'inr': 'IN'
    }
    normalized_region = region_normalize_map.get(region.lower(), region.upper()) if region else None

    filters = ProductFilter(
        category=category,
        region=normalized_region,
        search=search,
        min_price=min_price,
        max_price=max_price,
        has_discount=has_discount,
        has_ps_plus=has_ps_plus,
        has_ea_access=has_ea_access,
        platform=platform,
        players=players
    )
    pagination = PaginationParams(page=page, limit=limit)

    # Получаем пользователя если указан telegram_id
    user = None
    if telegram_id:
        user = user_crud.get_by_telegram_id(db, telegram_id)

    # Используем новый метод группировки с мультирегиональными ценами
    if grouped:
        products_with_prices, total = product_crud.get_products_grouped_by_name(
            db, filters, pagination, user
        )
    else:
        # Старый метод для совместимости
        products, total = product_crud.get_list(db, filters, pagination, user)
        products_with_prices = []
        for product in products:
            product_dict = product_crud.prepare_product_with_prices(product, db)
            products_with_prices.append(product_dict)

    return {
        "products": products_with_prices,
        "total": total,
        "page": page,
        "limit": limit,
        "has_next": (page * limit) < total
    }

@router.get("/products/{product_id}", response_model=dict, tags=["Products"], summary="Получить товар")
async def get_product(
    product_id: str,
    region: Optional[str] = Query(None, description="Регион товара"),
    telegram_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Получить товар по ID"""
    # Нормализуем регион
    region_normalize_map = {
        'en-ua': 'UA',
        'en-tr': 'TR',
        'en-in': 'IN',
        'ua': 'UA',
        'tr': 'TR',
        'in': 'IN',
        'uah': 'UA',
        'try': 'TR',
        'inr': 'IN'
    }
    normalized_region = region_normalize_map.get(region.lower(), region.upper()) if region else None

    # ЛОГИРОВАНИЕ
    logger.info(f"🔍 get_product called:")
    logger.info(f"   product_id: {product_id}")
    logger.info(f"   region (original): {region}")
    logger.info(f"   normalized_region: {normalized_region}")

    product_orm = product_crud.get_by_id(db, product_id, normalized_region)
    if not product_orm:
        raise HTTPException(status_code=404, detail="Товар не найден")

    logger.info(f"✅ Found product: region={product_orm.region}, localization={product_orm.localization}")

    # Получаем пользователя если указан telegram_id
    user = None
    if telegram_id:
        user = user_crud.get_by_telegram_id(db, telegram_id)

    # На детальной странице показываем цены из всех регионов для сравнения
    return product_crud.prepare_product_with_all_regions(product_orm, db, user)

@router.get("/products/categories/list", response_model=List[str], tags=["Products"], summary="Список категорий")
async def get_categories(db: Session = Depends(get_db)):
    """Получить список всех категорий товаров"""
    return product_crud.get_categories(db)

@router.get("/products/regions/list", response_model=List[str], tags=["Products"], summary="Список регионов")
async def get_regions(db: Session = Depends(get_db)):
    """Получить список всех доступных регионов"""
    return product_crud.get_regions(db)

# Роуты для избранного
@router.post("/users/{telegram_id}/favorites/", response_model=dict, tags=["Favorites"], summary="Добавить в избранное")
async def add_to_favorites(
    telegram_id: int,
    favorite_data: FavoriteCreate,
    db: Session = Depends(get_db)
):
    """Добавить товар в избранное пользователя"""
    logger.info(f"⭐ Adding to favorites - telegram_id: {telegram_id}, product_id: {favorite_data.product_id}")
    logger.info(f"⭐ favorite_data type: {type(favorite_data)}, product_id type: {type(favorite_data.product_id)}")

    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        logger.error(f"❌ User not found: {telegram_id}")
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    logger.info(f"✅ User found: {user.id}, preferred_region: {user.preferred_region}")

    # Сначала пробуем найти товар без региона (любой регион)
    products = product_crud.get_by_id_all_regions(db, favorite_data.product_id)
    logger.info(f"🔍 Found {len(products)} products with id {favorite_data.product_id} across all regions")

    if not products:
        logger.error(f"❌ Product not found in any region: {favorite_data.product_id}")
        raise HTTPException(status_code=404, detail="Товар не найден")

    # Используем регион из запроса или первый найденный товар
    region = favorite_data.region
    product = None

    if region:
        # Ищем товар в указанном регионе
        product = next((p for p in products if p.region == region), None)
        if product:
            logger.info(f"✅ Using product from specified region: {product.region}, name: {product.name}")

    if not product:
        # Если регион не указан или не найден, используем первый
        product = products[0]
        region = product.region
        logger.info(f"✅ Using product from fallback region: {product.region}, name: {product.name}")

    favorite = favorite_crud.add_to_favorites(db, user.id, favorite_data.product_id, region)
    logger.info(f"✅ Favorite added successfully: {favorite.id}, region: {favorite.region}")
    return {"message": "Товар добавлен в избранное", "favorite_id": favorite.id}

@router.delete("/users/{telegram_id}/favorites/{product_id}", response_model=dict, tags=["Favorites"], summary="Удалить из избранного")
async def remove_from_favorites(
    telegram_id: int,
    product_id: str,
    db: Session = Depends(get_db)
):
    """Удалить товар из избранного пользователя"""
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    success = favorite_crud.remove_from_favorites(db, user.id, product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Товар не найден в избранном")

    return {"message": "Товар удален из избранного"}

@router.get("/users/{telegram_id}/favorites/", response_model=List[dict], tags=["Favorites"], summary="Список избранного")
async def get_user_favorites(telegram_id: int, db: Session = Depends(get_db)):
    """Получить все избранные товары пользователя"""
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    favorites = favorite_crud.get_user_favorites(db, user.id)

    # Обрабатываем каждый избранный товар
    processed_favorites = []
    for favorite in favorites:
        # Получаем товар в том регионе, в котором он был добавлен в избранное
        product_to_show = favorite.product

        # Если сохранен регион, попробуем найти товар именно в этом регионе
        if favorite.region:
            regional_product = product_crud.get_by_id(db, favorite.product_id, favorite.region)
            if regional_product:
                product_to_show = regional_product
                logger.info(f"✅ Showing favorite in saved region: {favorite.region}")
            else:
                logger.warning(f"⚠️ Saved region {favorite.region} not found for product {favorite.product_id}, using default")

        # В избранном показываем цены из всех регионов для сравнения
        product_dict = product_crud.prepare_product_with_all_regions(product_to_show, db, user)

        favorite_dict = {
            'id': favorite.id,
            'user_id': favorite.user_id,
            'product_id': favorite.product_id,
            'region': favorite.region,  # Добавляем сохраненный регион
            'created_at': favorite.created_at,
            'product': product_dict
        }
        processed_favorites.append(favorite_dict)

    return processed_favorites

@router.get("/users/{telegram_id}/favorites/{product_id}/check", response_model=dict, tags=["Favorites"], summary="Проверить избранное")
async def check_favorite(
    telegram_id: int,
    product_id: str,
    db: Session = Depends(get_db)
):
    """Проверить, находится ли товар в избранном у пользователя"""
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    is_favorite = favorite_crud.is_favorite(db, user.id, product_id)
    return {"is_favorite": is_favorite}

# Роуты для оплаты
@router.post("/users/{telegram_id}/products/{product_id}/payment-url", response_model=dict, tags=["Payment"], summary="Генерация ссылки оплаты")
async def generate_payment_url(
    telegram_id: int,
    product_id: str,
    region: Optional[str] = Query(None, description="Регион товара"),
    use_ps_plus: bool = Query(False, description="Использовать цену PS Plus"),
    db: Session = Depends(get_db)
):
    """
    Генерировать ссылку для оплаты товара через plati.market

    Требует настроенные PSN данные пользователя (платформа, email, пароль)

    NOTE: Функционал временно работает на основе цен из выбранного региона
    """
    # Получаем пользователя
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Нормализуем регион
    region_normalize_map = {
        'en-ua': 'UA',
        'en-tr': 'TR',
        'en-in': 'IN',
        'ua': 'UA',
        'tr': 'TR',
        'in': 'IN',
        'uah': 'UA',
        'try': 'TR',
        'inr': 'IN'
    }
    normalized_region = region_normalize_map.get(region.lower(), region.upper()) if region else None

    # Проверяем что регион указан
    if not normalized_region:
        raise HTTPException(status_code=400, detail="Необходимо указать регион")

    # Получаем товар С ФИЛЬТРАЦИЕЙ ПО РЕГИОНУ (теперь каждый регион - отдельная строка)
    product = product_crud.get_by_id(db, product_id, region=normalized_region)
    if not product:
        raise HTTPException(status_code=404, detail=f"Товар не найден в регионе {normalized_region}")

    # Получаем цену с учетом PS Plus
    region_price_map = {
        'TR': ('price_try', 'ps_plus_price_try'),
        'UA': ('price_uah', 'ps_plus_price_uah'),
        'IN': ('price_inr', 'ps_plus_price_inr')
    }

    price_field, ps_plus_field = region_price_map.get(normalized_region, (None, None))

    current_price = None
    if price_field:
        # Если включен PS Plus и есть PS Plus цена - используем её
        if use_ps_plus and ps_plus_field:
            ps_plus_price = getattr(product, ps_plus_field, None)
            if ps_plus_price and ps_plus_price > 0:
                current_price = ps_plus_price

        # Если PS Plus цена не найдена или не включена - используем обычную
        if not current_price:
            current_price = getattr(product, price_field, None)

    # Проверяем наличие цены
    if not current_price or current_price <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Для данного товара не установлена цена в регионе {region}"
        )

    # Получаем данные для API
    game_name = product.get_display_name()
    region_info = product.get_region_info()

    # Получаем payment_email пользователя для автозаполнения на странице оплаты
    payment_email = user.payment_email or ''

    # Для покупки нужен email для оплаты
    if not payment_email:
        raise HTTPException(
            status_code=400,
            detail="Для покупки необходимо указать Email для покупки в профиле"
        )

    # Для Турции и Индии не нужны PSN данные (используются карты пополнения)
    if normalized_region in ('TR', 'IN'):
        platform = user.platform or 'PS5'
        psn_email = user.psn_email or ''
        psn_password = ''
        twofa_code = ''
    else:
        # Для Украины используем региональные PSN аккаунты
        psn_account = user.get_psn_account_for_region(normalized_region)

        if psn_account and psn_account.has_credentials:
            # Используем региональный аккаунт
            platform = psn_account.platform or user.platform or ('PS5' if normalized_region == 'UA' else None)
            psn_email = psn_account.psn_email
            psn_password = psn_account.get_psn_password()
            twofa_code = psn_account.get_twofa_code()
            logger.info(f"📧 Using regional PSN account for {normalized_region}: {psn_email}")
        elif user.has_psn_credentials:
            # Fallback на глобальные данные (для обратной совместимости)
            platform = user.platform or ('PS5' if normalized_region == 'UA' else None)
            psn_email = user.psn_email
            psn_password = user.get_psn_password()
            twofa_code = ''
            logger.info(f"📧 Using global PSN account (fallback): {psn_email}")
        else:
            # Нет данных ни в региональном, ни в глобальном аккаунте
            raise HTTPException(
                status_code=400,
                detail="Для покупки в регионе UA необходимо настроить PSN аккаунт Украины (email и пароль) в профиле"
            )

        if normalized_region == 'UA':
            platform = platform or 'PS5'
            if not psn_email:
                raise HTTPException(
                    status_code=400,
                    detail=f"Неполные PSN данные для региона {normalized_region}. Проверьте настройки профиля"
                )
        elif not platform or not psn_email:
            raise HTTPException(
                status_code=400,
                detail=f"Неполные PSN данные для региона {normalized_region}. Проверьте настройки профиля"
            )

    # Конвертируем цену в рубли для payment API
    from app.models.currency_rate import CurrencyRate
    currency_code = region_info['code']
    rate = CurrencyRate.get_rate_for_price(db, currency_code, current_price)
    price_rub = round(current_price * rate, 2)

    try:
        # Логируем запрос на генерацию ссылки
        price_type = "PS Plus" if use_ps_plus else "Regular"
        logger.info(f"🛒 Payment request: user={telegram_id}, product='{game_name}' ({product_id}), price={current_price} {currency_code} ({price_type}) = {price_rub} RUB, region={product.region}, platform={platform}")

        # Для региона Индии используем отдельную логику с картами пополнения
        if product.region == 'IN':
            try:
                # Получаем ссылку на покупку карты пополнения
                payment_url, purchase_info = await india_payment_api.get_payment_url(
                    game_price_inr=current_price,
                    need_registration=False
                )

                logger.info(f"✅ India payment URL generated for user {telegram_id}, product {product_id}")

                # Получаем цену карты в рублях через API
                card_price_rub = await india_payment_api.get_card_price_rub(purchase_info.total_value)
                logger.info(f"💰 India card {purchase_info.total_value} Rs price: {card_price_rub} RUB")

                # Получаем прямую ссылку на покупку карты с количеством
                direct_card_url = india_payment_api.get_direct_payment_url(
                    buyer_email=payment_email,
                    quantity=purchase_info.total_cards
                )

                # Добавляем количество карт к URL
                parsed = urlparse(payment_url)
                query_params = parse_qs(parsed.query)

                quantity = purchase_info.total_cards
                if quantity > 1:
                    query_params['n'] = [str(quantity)]
                    query_params['cnt'] = [str(quantity)]
                    query_params['product_cnt'] = [str(quantity)]
                    query_params['product_cnt_set'] = [str(quantity)]
                    query_params['quantity'] = [str(quantity)]
                    logger.info(f"🔢 Added quantity to India URL: n={quantity}")

                # Добавляем email для автозаполнения
                if payment_email:
                    query_params['email'] = [payment_email]
                    logger.info(f"📧 Added payment_email to India URL: {payment_email}")

                new_query = urlencode(query_params, doseq=True)
                payment_url = urlunparse(parsed._replace(query=new_query))

                return {
                    "payment_url": payment_url,
                    "product_name": game_name,
                    "platform": platform,
                    "psn_email": psn_email,
                    "price": current_price,
                    "price_rub": price_rub,
                    "currency": region_info['code'],
                    "region": product.region,
                    # Дополнительная информация для Индии
                    "india_payment": True,
                    "card_info": {
                        "total_value": purchase_info.total_value,
                        "game_price": purchase_info.game_price,
                        "remaining_balance": purchase_info.remaining_balance,
                        "cards": purchase_info.quantity_map,
                        "total_cards": purchase_info.total_cards,
                        "message_ru": purchase_info.get_description_ru(),
                        "message_en": purchase_info.get_description_en(),
                        "card_price_rub": card_price_rub,
                        "direct_card_url": direct_card_url
                    }
                }
            except IndiaPaymentAPIError as e:
                logger.error(f"India Payment API error: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Ошибка генерации ссылки оплаты для Индии: {str(e)}")

        # Для региона Украины используем отдельную логику
        if product.region == 'UA':
            try:
                payment_url, payment_info = await ukraine_payment_api.get_payment_url(
                    game=game_name,
                    email=psn_email,
                    password=psn_password,
                    uah_price=current_price,
                    twofa_code=twofa_code
                )

                logger.info(f"✅ Ukraine payment URL generated for user {telegram_id}, product {product_id}")

                # Добавляем payment_email к URL для автозаполнения
                if payment_email:
                    parsed = urlparse(payment_url)
                    query_params = parse_qs(parsed.query)
                    query_params['email'] = [payment_email]
                    new_query = urlencode(query_params, doseq=True)
                    payment_url = urlunparse(parsed._replace(query=new_query))
                    logger.info(f"📧 Added payment_email to Ukraine URL: {payment_email}")

                # Формируем ответ с информацией о пополнении
                response_data = {
                    "payment_url": payment_url,
                    "product_name": game_name,
                    "platform": platform,
                    "psn_email": psn_email,
                    "price": current_price,
                    "price_rub": price_rub,
                    "currency": region_info['code'],
                    "region": product.region,
                    "ukraine_payment": True,
                    # Информация о пополнении
                    "topup_info": {
                        "game_price": payment_info.game_price,
                        "topup_amount": payment_info.topup_amount,
                        "remaining_balance": payment_info.remaining_balance,
                        "message_ru": payment_info.get_description_ru(),
                        "message_en": payment_info.get_description_en()
                    }
                }

                return response_data
            except UkrainePaymentAPIError as e:
                logger.error(f"Ukraine Payment API error: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Ошибка генерации ссылки оплаты для Украины: {str(e)}")

        # Для Турции используем логику с картами пополнения
        if product.region == 'TR':
            try:
                # Получаем ссылку на покупку карты пополнения
                payment_url, purchase_info = await turkey_payment_api.get_payment_url(
                    game_price_tl=current_price,
                    need_registration=False
                )

                logger.info(f"✅ Turkey payment URL generated for user {telegram_id}, product {product_id}")

                # Получаем цену карты в рублях через API
                card_price_rub = await turkey_payment_api.get_card_price_rub(purchase_info.total_value)
                logger.info(f"💰 Turkey card {purchase_info.total_value} TL price: {card_price_rub} RUB")

                # Получаем прямую ссылку на покупку карты с количеством
                direct_card_url = turkey_payment_api.get_direct_payment_url(
                    buyer_email=payment_email,
                    quantity=purchase_info.total_cards
                )

                # Добавляем payment_email и количество карт к URL для автозаполнения
                parsed = urlparse(payment_url)
                query_params = parse_qs(parsed.query)

                # Добавляем количество карт - пробуем разные варианты параметров
                quantity = purchase_info.total_cards
                if quantity > 1:
                    query_params['n'] = [str(quantity)]
                    query_params['cnt'] = [str(quantity)]
                    query_params['product_cnt'] = [str(quantity)]
                    query_params['product_cnt_set'] = [str(quantity)]
                    query_params['quantity'] = [str(quantity)]
                    logger.info(f"🔢 Added quantity to Turkey URL: n={quantity}")

                # Добавляем email для автозаполнения
                if payment_email:
                    query_params['email'] = [payment_email]
                    logger.info(f"📧 Added payment_email to Turkey URL: {payment_email}")

                new_query = urlencode(query_params, doseq=True)
                payment_url = urlunparse(parsed._replace(query=new_query))

                return {
                    "payment_url": payment_url,
                    "product_name": game_name,
                    "platform": platform,
                    "psn_email": psn_email,
                    "price": current_price,
                    "price_rub": price_rub,
                    "currency": region_info['code'],
                    "region": product.region,
                    # Дополнительная информация для Турции
                    "turkey_payment": True,
                    "card_info": {
                        "total_value": purchase_info.total_value,
                        "game_price": purchase_info.game_price,
                        "remaining_balance": purchase_info.remaining_balance,
                        "cards": purchase_info.quantity_map,
                        "total_cards": purchase_info.total_cards,
                        "message_ru": purchase_info.get_description_ru(),
                        "message_en": purchase_info.get_description_en(),
                        "card_price_rub": card_price_rub,
                        "direct_card_url": direct_card_url
                    }
                }
            except TurkeyPaymentAPIError as e:
                logger.error(f"Turkey Payment API error: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Ошибка генерации ссылки оплаты для Турции: {str(e)}")

        # Для других регионов используем стандартную логику
        payment_url = await payment_api.get_payment_url(
            platform=platform,
            game=game_name,
            email=psn_email,
            password=psn_password,
            price=price_rub,
            trl_price=current_price,
            twofa_code=""
        )

        logger.info(f"✅ Payment URL generated for user {telegram_id}, product {product_id}")

        return {
            "payment_url": payment_url,
            "product_name": game_name,
            "platform": platform,
            "psn_email": psn_email,
            "price": current_price,
            "price_rub": price_rub,
            "currency": region_info['code'],
            "region": product.region
        }

    except PaymentAPIError as e:
        logger.error(f"Payment API error for user {telegram_id}, product {product_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка генерации ссылки оплаты: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error generating payment URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Произошла неожиданная ошибка")

@router.get("/payment/diagnose", response_model=dict, tags=["Payment"], summary="Диагностика проблем с оплатой")
async def diagnose_payment_issues():
    """
    Проводит диагностику доступности сайта оплаты и возвращает рекомендации
    по решению возможных проблем
    """
    try:
        diagnosis = await diagnose_payment_site_issues()
        return {
            "status": "success",
            "diagnosis": diagnosis,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error during payment site diagnosis: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "diagnosis": {
                "issues_found": ["Ошибка проведения диагностики"],
                "recommendations": ["Обратитесь к администратору"]
            },
            "timestamp": datetime.utcnow().isoformat()
        }
