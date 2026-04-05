from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from config.settings import settings

from .schemas import SiteUserPublic
from .service import get_auth_service


def get_session_token_from_request(request: Request) -> Optional[str]:
    return request.cookies.get(settings.AUTH_SESSION_COOKIE_NAME)


async def get_current_site_user(request: Request) -> SiteUserPublic:
    session_token = get_session_token_from_request(request)
    if not session_token:
        raise HTTPException(status_code=401, detail="Требуется авторизация.")

    user = await run_in_threadpool(get_auth_service().get_user_by_session_token, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Сессия недействительна или истекла.")

    return user


async def get_current_admin_site_user(request: Request) -> SiteUserPublic:
    user = await get_current_site_user(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Требуются права администратора.")
    return user
