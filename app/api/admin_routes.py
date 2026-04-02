"""
API роуты для административной панели
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.database.connection import get_db
from app.api.admin_auth import verify_admin_access
from app.api.schemas import (
    CurrencyRate, CurrencyRateCreate, CurrencyRateUpdate,
    AdminStats, AdminUser
)
from app.api.crud import currency_rate_crud, admin_crud
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Статистика
@router.get("/admin/stats", response_model=AdminStats, tags=["Admin"], summary="Получить статистику")
async def get_admin_stats(
    request: Request,
    db: Session = Depends(get_db),
    admin_id: int = Depends(verify_admin_access)
):
    """Получить общую статистику для админки"""
    try:
        stats = admin_crud.get_stats(db)
        return AdminStats(**stats)
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики")

# Пользователи
@router.get("/admin/users", response_model=List[AdminUser], tags=["Admin"], summary="Список пользователей")
async def get_admin_users(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="Количество пользователей"),
    db: Session = Depends(get_db),
    admin_id: int = Depends(verify_admin_access)
):
    """Получить список пользователей со статистикой"""
    try:
        users = admin_crud.get_users_with_stats(db, limit)
        return [AdminUser(**user) for user in users]
    except Exception as e:
        logger.error(f"Error getting admin users: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения пользователей")

# Курсы валют
@router.delete("/admin/users/{user_id}", response_model=dict, tags=["Admin"], summary="Удалить пользователя")
async def delete_admin_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_id: int = Depends(verify_admin_access)
):
    """Delete a user from the admin panel."""
    try:
        user = admin_crud.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        if user.telegram_id in settings.ADMIN_TELEGRAM_IDS:
            raise HTTPException(
                status_code=400,
                detail="Нельзя удалить admin-пользователя из .env",
            )

        if user.telegram_id == admin_id:
            raise HTTPException(
                status_code=400,
                detail="Нельзя удалить собственный admin-аккаунт",
            )

        user_name = user.full_name
        admin_crud.delete_user(db, user)
        return {"message": f"Пользователь {user_name} удален"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления пользователя")

@router.get("/admin/currency-rates", response_model=List[CurrencyRate], tags=["Admin"], summary="Список курсов валют")
async def get_currency_rates(
    request: Request,
    active_only: bool = Query(False, description="Только активные курсы"),
    currency: Optional[str] = Query(None, description="Фильтр по валюте"),
    db: Session = Depends(get_db),
    admin_id: int = Depends(verify_admin_access)
):
    """Получить список курсов валют"""
    try:
        if currency:
            rates = currency_rate_crud.get_by_currency(db, currency)
        elif active_only:
            rates = currency_rate_crud.get_active(db)
        else:
            rates = currency_rate_crud.get_all(db)
        
        return rates
    except Exception as e:
        logger.error(f"Error getting currency rates: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения курсов валют")

@router.post("/admin/currency-rates", response_model=CurrencyRate, tags=["Admin"], summary="Создать курс валют")
async def create_currency_rate(
    request: Request,
    rate_data: CurrencyRateCreate,
    db: Session = Depends(get_db),
    admin_id: int = Depends(verify_admin_access)
):
    """Создать новый курс валют"""
    try:
        # Проверяем, нет ли пересечения диапазонов
        existing_rates = currency_rate_crud.get_by_currency(db, rate_data.currency_from)
        
        for existing_rate in existing_rates:
            # Проверяем пересечение диапазонов
            if (rate_data.price_min <= (existing_rate.price_max or float('inf')) and 
                (rate_data.price_max or float('inf')) >= existing_rate.price_min):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Диапазон цен пересекается с существующим курсом ID {existing_rate.id}"
                )
        
        rate = currency_rate_crud.create(db, rate_data, admin_id)
        return rate
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating currency rate: {e}")
        raise HTTPException(status_code=500, detail="Ошибка создания курса валют")

@router.put("/admin/currency-rates/{rate_id}", response_model=CurrencyRate, tags=["Admin"], summary="Обновить курс валют")
async def update_currency_rate(
    rate_id: int,
    request: Request,
    rate_data: CurrencyRateUpdate,
    db: Session = Depends(get_db),
    admin_id: int = Depends(verify_admin_access)
):
    """Обновить курс валют"""
    try:
        rate = currency_rate_crud.get_by_id(db, rate_id)
        if not rate:
            raise HTTPException(status_code=404, detail="Курс валют не найден")
        
        updated_rate = currency_rate_crud.update(db, rate, rate_data)
        return updated_rate
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating currency rate: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обновления курса валют")

@router.delete("/admin/currency-rates/{rate_id}", response_model=dict, tags=["Admin"], summary="Удалить курс валют")
async def delete_currency_rate(
    rate_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_id: int = Depends(verify_admin_access)
):
    """Удалить курс валют"""
    try:
        rate = currency_rate_crud.get_by_id(db, rate_id)
        if not rate:
            raise HTTPException(status_code=404, detail="Курс валют не найден")
        
        currency_rate_crud.delete(db, rate)
        return {"message": "Курс валют удален успешно"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting currency rate: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления курса валют")

# Обновление цен
@router.post("/admin/update-prices", response_model=dict, tags=["Admin"], summary="Обновить рублевые цены")
async def update_ruble_prices(
    request: Request,
    db: Session = Depends(get_db),
    admin_id: int = Depends(verify_admin_access)
):
    """Обновить рублевые цены для всех товаров"""
    try:
        updated_count = admin_crud.update_all_ruble_prices(db)
        return {
            "message": "Цены обновлены успешно",
            "updated_products": updated_count
        }
    except Exception as e:
        logger.error(f"Error updating prices: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обновления цен")

# Проверка доступа
@router.get("/admin/check-access", response_model=dict, tags=["Admin"], summary="Проверить права админа")
async def check_admin_access(
    request: Request,
    admin_id: int = Depends(verify_admin_access)
):
    """Проверить права администратора"""
    return {
        "admin": True,
        "telegram_id": admin_id,
        "message": "Доступ разрешен"
    }
