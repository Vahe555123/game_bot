from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse

from config.settings import settings

from app.auth.dependencies import get_current_site_user, get_session_token_from_request
from app.auth.exceptions import AuthServiceError
from app.auth.oauth_service import build_public_redirect_url, get_oauth_service
from app.auth.schemas import (
    AuthActionResponse,
    AuthProvidersResponse,
    AuthUserResponse,
    LoginRequest,
    PasswordResetConfirmRequest,
    RegisterRequest,
    ResendCodeRequest,
    SiteProfilePreferencesUpdateRequest,
    SiteProfileResponse,
    SitePSNAccountUpdateRequest,
    SiteUserPublic,
    TelegramAuthRequest,
    VerifyEmailRequest,
)
from app.auth.service import AuthService, get_auth_service

router = APIRouter(prefix="/auth", tags=["Site Auth"])
logger = logging.getLogger(__name__)


def _raise_http_auth_error(error: AuthServiceError) -> None:
    detail = {"message": error.message}
    detail.update(error.extra)
    raise HTTPException(status_code=error.status_code, detail=detail)


def _get_client_ip(request: Request) -> Optional[str]:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    return request.client.host if request.client else None


def _set_session_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE.lower(),
        max_age=settings.AUTH_SESSION_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE.lower(),
        path="/",
    )


def _oauth_error_redirect(message: str, *, next_path: Optional[str] = None) -> RedirectResponse:
    redirect_url = build_public_redirect_url(
        next_path or "/login",
        auth_error=message,
    )
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/providers", response_model=AuthProvidersResponse, summary="Доступные способы входа")
async def get_auth_providers():
    return AuthProvidersResponse(
        google_enabled=bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
        vk_enabled=bool(settings.VK_CLIENT_ID),
        telegram_enabled=bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_BOT_USERNAME),
        telegram_bot_username=settings.TELEGRAM_BOT_USERNAME or None,
    )


@router.post("/register", response_model=AuthActionResponse, summary="Регистрация по email")
async def register(
    payload: RegisterRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        return await run_in_threadpool(
            auth_service.start_registration,
            payload,
            user_agent=request.headers.get("user-agent"),
            ip_address=_get_client_ip(request),
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/resend-code", response_model=AuthActionResponse, summary="Повторная отправка кода регистрации")
async def resend_code(
    payload: ResendCodeRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        return await run_in_threadpool(auth_service.resend_registration_code, payload.email)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/password-reset/request", response_model=AuthActionResponse, summary="Запросить код для восстановления пароля")
async def request_password_reset(
    payload: ResendCodeRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        return await run_in_threadpool(auth_service.start_password_reset, payload.email)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/password-reset/resend", response_model=AuthActionResponse, summary="Повторно отправить код для восстановления пароля")
async def resend_password_reset_code(
    payload: ResendCodeRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        return await run_in_threadpool(auth_service.resend_password_reset_code, payload.email)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/password-reset/confirm", response_model=AuthUserResponse, summary="Подтвердить код и сохранить новый пароль")
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        user, session_token = await run_in_threadpool(
            auth_service.confirm_password_reset,
            email=payload.email,
            code=payload.code,
            new_password=payload.new_password,
            user_agent=request.headers.get("user-agent"),
            ip_address=_get_client_ip(request),
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)

    _set_session_cookie(response, session_token)
    return AuthUserResponse(user=user)


@router.post("/verify-email", response_model=AuthUserResponse, summary="Подтвердить email кодом")
async def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        user, session_token = await run_in_threadpool(
            auth_service.verify_registration_code,
            email=payload.email,
            code=payload.code,
            user_agent=request.headers.get("user-agent"),
            ip_address=_get_client_ip(request),
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)

    _set_session_cookie(response, session_token)
    return AuthUserResponse(user=user)


@router.post("/login", response_model=AuthUserResponse, summary="Логин по email и паролю")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        user, session_token = await run_in_threadpool(
            auth_service.login,
            email=payload.email,
            password=payload.password,
            user_agent=request.headers.get("user-agent"),
            ip_address=_get_client_ip(request),
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)

    _set_session_cookie(response, session_token)
    return AuthUserResponse(user=user)


@router.post("/oauth/telegram", response_model=AuthUserResponse, summary="Вход через Telegram")
async def telegram_login(
    payload: TelegramAuthRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    oauth_service = get_oauth_service()

    try:
        user, session_token = await run_in_threadpool(
            oauth_service.handle_telegram_login,
            payload=payload,
            user_agent=request.headers.get("user-agent"),
            ip_address=_get_client_ip(request),
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)

    _set_session_cookie(response, session_token)
    return AuthUserResponse(user=user)


@router.get("/oauth/google/start", summary="Начать вход через Google")
async def start_google_oauth(next: Optional[str] = Query(None)):
    oauth_service = get_oauth_service()

    try:
        authorization_url = await run_in_threadpool(oauth_service.build_google_authorization_url, next)
    except AuthServiceError as error:
        _raise_http_auth_error(error)

    return RedirectResponse(url=authorization_url, status_code=302)


@router.get("/oauth/google/callback", summary="Callback Google OAuth")
async def google_oauth_callback(
    request: Request,
    response: Response,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    if error:
        return _oauth_error_redirect("Вход через Google был отменен.")

    if not code or not state:
        return _oauth_error_redirect("Google не вернул код авторизации.")

    oauth_service = get_oauth_service()

    try:
        result = await run_in_threadpool(
            oauth_service.handle_google_callback,
            code=code,
            state=state,
            user_agent=request.headers.get("user-agent"),
            ip_address=_get_client_ip(request),
        )
    except AuthServiceError as auth_error:
        logger.warning("Google OAuth callback failed: %s", auth_error.message)
        return _oauth_error_redirect(auth_error.message)

    redirect_response = RedirectResponse(
        url=build_public_redirect_url(result.next_path, auth_provider="google"),
        status_code=302,
    )
    _set_session_cookie(redirect_response, result.session_token)
    return redirect_response


@router.get("/oauth/vk/start", summary="Начать вход через VK")
async def start_vk_oauth(next: Optional[str] = Query(None)):
    oauth_service = get_oauth_service()

    try:
        authorization_url = await run_in_threadpool(oauth_service.build_vk_authorization_url, next)
    except AuthServiceError as error:
        _raise_http_auth_error(error)

    return RedirectResponse(url=authorization_url, status_code=302)


@router.get("/oauth/vk/callback", summary="Callback VK OAuth")
async def vk_oauth_callback(
    request: Request,
    response: Response,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    redirect_state: Optional[str] = Query(None),
    device_id: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    if error:
        return _oauth_error_redirect("Вход через VK был отменен.")

    state_value = state or redirect_state

    if not code or not state_value:
        return _oauth_error_redirect("VK не вернул код авторизации.")

    oauth_service = get_oauth_service()

    try:
        result = await run_in_threadpool(
            oauth_service.handle_vk_callback,
            code=code,
            state=state_value,
            device_id=device_id,
            user_agent=request.headers.get("user-agent"),
            ip_address=_get_client_ip(request),
        )
    except AuthServiceError as auth_error:
        logger.warning("VK OAuth callback failed: %s", auth_error.message)
        return _oauth_error_redirect(auth_error.message)

    redirect_response = RedirectResponse(
        url=build_public_redirect_url(result.next_path, auth_provider="vk"),
        status_code=302,
    )
    _set_session_cookie(redirect_response, result.session_token)
    return redirect_response


@router.post("/logout", response_model=AuthActionResponse, summary="Выйти из аккаунта")
async def logout(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    session_token = get_session_token_from_request(request)

    try:
        await run_in_threadpool(auth_service.logout, session_token)
    except AuthServiceError as error:
        _raise_http_auth_error(error)

    _clear_session_cookie(response)
    return AuthActionResponse(message="Вы вышли из аккаунта.")


@router.get("/me", response_model=AuthUserResponse, summary="Текущий пользователь сайта")
async def get_me(
    current_user: SiteUserPublic = Depends(get_current_site_user),
):
    return AuthUserResponse(user=current_user)


@router.get("/profile", response_model=SiteProfileResponse, summary="Профиль сайта")
async def get_profile(
    current_user: SiteUserPublic = Depends(get_current_site_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        return await run_in_threadpool(auth_service.get_profile, current_user.id)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.put("/profile/preferences", response_model=SiteProfileResponse, summary="Обновить регион и email покупок")
async def update_profile_preferences(
    payload: SiteProfilePreferencesUpdateRequest,
    current_user: SiteUserPublic = Depends(get_current_site_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        return await run_in_threadpool(
            auth_service.update_profile_preferences,
            current_user.id,
            payload,
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.put("/profile/psn/{region}", response_model=SiteProfileResponse, summary="Обновить PSN аккаунт региона")
async def update_psn_account(
    region: str,
    payload: SitePSNAccountUpdateRequest,
    current_user: SiteUserPublic = Depends(get_current_site_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    try:
        return await run_in_threadpool(
            auth_service.update_psn_account,
            current_user.id,
            region=region,
            payload=payload,
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)
