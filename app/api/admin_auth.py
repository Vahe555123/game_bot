"""Admin access helpers."""

import hashlib
import hmac
import json
import time
from typing import Optional
from urllib.parse import parse_qsl

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.crud import user_crud
from app.database.connection import get_db
from config.settings import settings


def _get_telegram_init_data(request: Request) -> Optional[str]:
    init_data = request.headers.get("X-Telegram-Init-Data")
    if init_data:
        return init_data

    if hasattr(request, "query_params"):
        for key in ("tg_init_data", "tgWebAppData", "initData"):
            value = request.query_params.get(key)
            if value:
                return value

    return None


def _verify_telegram_init_data(init_data: str) -> Optional[dict]:
    if not init_data or not settings.TELEGRAM_BOT_TOKEN:
        return None

    try:
        data = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = data.pop("hash", None)
        if not received_hash:
            return None

        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(data.items())
        )
        secret_key = hmac.new(
            b"WebAppData",
            settings.TELEGRAM_BOT_TOKEN.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        auth_date_raw = data.get("auth_date")
        if auth_date_raw:
            auth_timestamp = int(auth_date_raw)
            max_age = max(settings.ADMIN_INIT_DATA_MAX_AGE_SECONDS, 0)
            if max_age and time.time() - auth_timestamp > max_age:
                return None

        user_payload = json.loads(data.get("user", "{}"))
        user_id = int(user_payload.get("id", 0))
        if not user_id:
            return None

        return user_payload
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def get_telegram_user_id(request: Request) -> Optional[int]:
    """Return a verified Telegram user id from Telegram WebApp initData."""
    init_data = _get_telegram_init_data(request)
    user_payload = _verify_telegram_init_data(init_data) if init_data else None
    if not user_payload:
        return None
    return int(user_payload["id"])


def verify_admin_access(request: Request, db: Session = Depends(get_db)) -> int:
    """Ensure the request belongs to an admin from ADMIN_TELEGRAM_IDS."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="На сервере не настроен TELEGRAM_BOT_TOKEN",
        )

    telegram_id = get_telegram_user_id(request)
    if not telegram_id:
        raise HTTPException(
            status_code=401,
            detail="Не удалось проверить Telegram WebApp initData",
        )

    if telegram_id not in settings.ADMIN_TELEGRAM_IDS:
        raise HTTPException(
            status_code=403,
            detail="Доступ запрещен. Разрешены только ID из ADMIN_TELEGRAM_IDS",
        )

    user = user_crud.get_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Администратор не найден в базе данных",
        )

    return telegram_id


def check_admin_access(telegram_id: int) -> bool:
    return telegram_id in settings.ADMIN_TELEGRAM_IDS
