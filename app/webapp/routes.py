from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import logging
import json
import time
import asyncio
from app.database.connection import get_db
from config.settings import settings
from app.api.admin_auth import check_admin_access, get_telegram_user_id
from app.api.crud import product_crud
from app.api.schemas import ProductFilter, PaginationParams

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.globals["manager_telegram_url"] = settings.MANAGER_TELEGRAM_URL

@router.get("/webapp", response_class=HTMLResponse)
async def webapp_main(request: Request, db: Session = Depends(get_db)):
    """Главная страница WebApp с Server-Side Rendering товаров"""
    # Определяем API base URL
    api_base_url = settings.WEBAPP_URL.replace('/webapp', '') if settings.WEBAPP_URL else str(request.url).replace('/webapp', '')

    # SSR: Предзагружаем первые товары на сервере с таймаутом
    async def load_products_with_timeout():
        try:
            filters = ProductFilter()
            pagination = PaginationParams(page=1, limit=12)

            # Запускаем загрузку в отдельном потоке
            loop = asyncio.get_event_loop()
            products_data, total = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: product_crud.get_products_grouped_by_name(db, filters, pagination, user=None)
                ),
                timeout=0.05  # Таймаут 50мс - если не успели, отдаём пустую страницу
            )

            logger.info(f" SSR: Предзагружено {len(products_data)} товаров из {total}")
            return products_data, total
        except asyncio.TimeoutError:
            logger.warning(f" SSR Timeout: Товары не загрузились за 50мс, отдаём пустую страницу")
            return [], 0
        except Exception as e:
            logger.error(f" SSR Error: {e}")
            return [], 0

    products_data, total = await load_products_with_timeout()

    return templates.TemplateResponse(
        "webapp/index.html",
        {
            "request": request,
            "title": "PlayStation Store",
            "api_base_url": api_base_url,
            "initial_products": json.dumps(products_data),  # Передаем товары в JSON
            "initial_products_count": len(products_data),
            "total_products": total,
            "cache_buster": int(time.time())  # Антикеш для CSS/JS
        }
    )

@router.get("/webapp/product/{product_id}", response_class=HTMLResponse)
async def webapp_product_detail(request: Request, product_id: str, db: Session = Depends(get_db)):
    """Страница детального просмотра товара"""
    # Определяем API base URL
    api_base_url = settings.WEBAPP_URL.replace('/webapp', '') if settings.WEBAPP_URL else str(request.url).replace(f'/webapp/product/{product_id}', '')

    return templates.TemplateResponse(
        "webapp/product_detail.html",
        {
            "request": request,
            "product_id": product_id,
            "title": "Детали товара",
            "api_base_url": api_base_url,
            "cache_buster": int(time.time())
        }
    )

@router.get("/webapp/favorites", response_class=HTMLResponse)
async def webapp_favorites(request: Request, db: Session = Depends(get_db)):
    """Страница избранных товаров"""
    # Определяем API base URL
    api_base_url = settings.WEBAPP_URL.replace('/webapp', '') if settings.WEBAPP_URL else str(request.url).replace('/webapp/favorites', '')

    return templates.TemplateResponse(
        "webapp/favorites.html",
        {
            "request": request,
            "title": "Избранное",
            "api_base_url": api_base_url,
            "cache_buster": int(time.time())
        }
    )

@router.get("/webapp/profile", response_class=HTMLResponse)
async def webapp_profile(request: Request, db: Session = Depends(get_db)):
    """Страница профиля пользователя"""
    # Определяем API base URL
    api_base_url = settings.WEBAPP_URL.replace('/webapp', '') if settings.WEBAPP_URL else str(request.url).replace('/webapp/profile', '')

    return templates.TemplateResponse(
        "webapp/profile.html",
        {
            "request": request,
            "title": "Профиль",
            "api_base_url": api_base_url,
            "cache_buster": int(time.time())
        }
    )

@router.get("/webapp/favorites-test", response_class=HTMLResponse)
async def webapp_favorites_test(request: Request, db: Session = Depends(get_db)):
    """Тестовая страница избранных товаров"""
    # Определяем API base URL
    api_base_url = settings.WEBAPP_URL.replace('/webapp', '') if settings.WEBAPP_URL else str(request.url).replace('/webapp/favorites-test', '')

    return templates.TemplateResponse(
        "webapp/favorites_test.html",
        {
            "request": request,
            "title": "Тест избранного",
            "api_base_url": api_base_url,
            "cache_buster": int(time.time())
        }
    )

@router.get("/webapp/faq", response_class=HTMLResponse)
async def webapp_faq(request: Request, db: Session = Depends(get_db)):
    """Страница FAQ и техподдержки"""
    # Определяем API base URL
    api_base_url = settings.WEBAPP_URL.replace('/webapp', '') if settings.WEBAPP_URL else str(request.url).replace('/webapp/faq', '')

    return templates.TemplateResponse(
        "webapp/faq.html",
        {
            "request": request,
            "title": "Часто задаваемые вопросы",
            "api_base_url": api_base_url,
            "cache_buster": int(time.time())
        }
    )

@router.get("/webapp/admin", response_class=HTMLResponse)
async def webapp_admin(request: Request, db: Session = Depends(get_db)):
    """Страница администрирования"""
    # Проверяем права админа
    telegram_id = get_telegram_user_id(request)

    # Для отладки: логируем все заголовки
    print(f"Admin access attempt:")
    print(f"  Telegram ID from headers: {telegram_id}")
    print(f"  All headers: {dict(request.headers)}")
    print(f"  Query params: {dict(request.query_params)}")

    if not telegram_id or not check_admin_access(telegram_id):
        return templates.TemplateResponse(
            "webapp/admin_access_denied.html",
            {
                "request": request,
                "title": "Доступ запрещен",
                "debug_info": {
                    "telegram_id": telegram_id,
                    "headers": dict(request.headers),
                    "query_params": dict(request.query_params)
                },
                "cache_buster": int(time.time())
            }
        )

    # Определяем API base URL
    if settings.WEBAPP_URL:
        api_base_url = settings.WEBAPP_URL.replace('/webapp', '').rstrip('/')
    else:
        api_base_url = str(request.url).replace('/webapp/admin', '').rstrip('/')
        # Убираем query параметры из URL
        if '?' in api_base_url:
            api_base_url = api_base_url.split('?')[0]

    return templates.TemplateResponse(
        "webapp/admin.html",
        {
            "request": request,
            "title": "Админ-панель",
            "api_base_url": api_base_url,
            "admin_telegram_id": telegram_id,
            "cache_buster": int(time.time())
        }
    )
