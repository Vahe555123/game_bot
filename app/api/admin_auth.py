"""
Модуль авторизации администраторов
"""
from fastapi import HTTPException, Depends, Request
from sqlalchemy.orm import Session
from typing import Optional
from config.settings import settings
from app.database.connection import get_db
from app.api.crud import user_crud

def get_telegram_user_id(request: Request) -> Optional[int]:
    """Получить Telegram ID из заголовков запроса"""
    # В реальном Telegram WebApp ID передается в заголовке
    telegram_id = request.headers.get('X-Telegram-User-Id')
    if telegram_id:
        try:
            return int(telegram_id)
        except ValueError:
            pass
    
    # Альтернативные заголовки Telegram WebApp
    tg_user = request.headers.get('Tg-User-Id')
    if tg_user:
        try:
            return int(tg_user)
        except ValueError:
            pass
    
    # Получаем из query параметров (для WebApp)
    if hasattr(request, 'query_params'):
        # Основной параметр от WebApp
        tg_user_id = request.query_params.get('tg_user_id')
        if tg_user_id:
            try:
                return int(tg_user_id)
            except ValueError:
                pass
        
        # Для тестирования
        test_user_id = request.query_params.get('test_admin_id')
        if test_user_id:
            try:
                return int(test_user_id)
            except ValueError:
                pass
    
    return None

def verify_admin_access(request: Request, db: Session = Depends(get_db)) -> int:
    """Проверить, что пользователь является администратором"""
    telegram_id = get_telegram_user_id(request)
    
    if not telegram_id:
        raise HTTPException(
            status_code=401, 
            detail="Не удалось определить Telegram ID пользователя"
        )
    
    # Проверяем, что пользователь в списке админов
    admin_ids = settings.ADMIN_TELEGRAM_IDS
    if telegram_id not in admin_ids:
        raise HTTPException(
            status_code=403, 
            detail="Доступ запрещен. Только для администраторов."
        )
    
    # Проверяем, что пользователь существует в базе данных
    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(
            status_code=404, 
            detail="Пользователь не найден в системе"
        )
    
    return telegram_id

def check_admin_access(telegram_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    return telegram_id in settings.ADMIN_TELEGRAM_IDS