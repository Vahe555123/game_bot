from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional
from urllib.parse import urlencode, urljoin, urlparse, urlunparse

import httpx

from config.settings import settings

from .exceptions import AuthServiceError
from .schemas import SiteUserPublic, TelegramAuthRequest
from .security import create_signed_oauth_state, verify_signed_oauth_state
from .service import AuthService, get_auth_service

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

VK_AUTHORIZE_URL = "https://oauth.vk.com/authorize"
VK_TOKEN_URL = "https://oauth.vk.com/access_token"
VK_USERINFO_URL = "https://api.vk.com/method/users.get"
VK_ID_AUTHORIZE_URL = "https://id.vk.com/authorize"
VK_ID_TOKEN_URL = "https://id.vk.com/oauth2/auth"
VK_ID_USERINFO_URL = "https://id.vk.com/oauth2/user_info"
VK_API_VERSION = "5.199"


@dataclass
class OAuthLoginResult:
    user: SiteUserPublic
    session_token: str
    next_path: str


def normalize_next_path(next_path: Optional[str]) -> str:
    candidate = (next_path or settings.AUTH_DEFAULT_REDIRECT_PATH).strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return settings.AUTH_DEFAULT_REDIRECT_PATH
    return candidate


def build_public_redirect_url(path: str, **query: str) -> str:
    base_url = urljoin(f"{settings.PUBLIC_APP_URL}/", path.lstrip("/"))
    parsed = urlparse(base_url)
    existing_params = dict()
    if parsed.query:
        for part in parsed.query.split("&"):
            if "=" in part:
                key, value = part.split("=", 1)
                existing_params[key] = value
    existing_params.update({key: value for key, value in query.items() if value})
    return urlunparse(parsed._replace(query=urlencode(existing_params)))


def _base64_urlsafe_no_padding(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _create_pkce_verifier() -> str:
    return secrets.token_urlsafe(64)[:128]


def _create_pkce_challenge(verifier: str) -> str:
    return _base64_urlsafe_no_padding(hashlib.sha256(verifier.encode("ascii")).digest())


def _has_configured_vk_secret() -> bool:
    secret = (settings.VK_CLIENT_SECRET or "").strip()
    if not secret:
        return False

    lowered = secret.casefold()
    placeholder_markers = ("replace", "your_", "ваш", "секрет", "ключ")
    mojibake_markers = ("р’р", "рљ", "р®")
    return not any(marker in lowered for marker in (*placeholder_markers, *mojibake_markers))


def _extract_vk_id_profile(profile_payload: dict[str, Any]) -> dict[str, Any] | None:
    profile = profile_payload.get("user") or profile_payload.get("response")
    if isinstance(profile, list):
        profile = profile[0] if profile else None
    if not isinstance(profile, dict):
        return None

    user_id = profile.get("user_id") or profile.get("id")
    return {
        "id": user_id,
        "screen_name": profile.get("screen_name") or profile.get("domain"),
        "first_name": profile.get("first_name"),
        "last_name": profile.get("last_name"),
    }


class OAuthService:
    def __init__(self, auth_service: Optional[AuthService] = None) -> None:
        self.auth_service = auth_service or get_auth_service()

    @staticmethod
    def _serialize_telegram_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _build_telegram_data_check_string(self, payload: TelegramAuthRequest) -> str:
        payload_data = payload.model_dump(exclude_none=True, exclude={"hash"})
        extra_payload = getattr(payload, "__pydantic_extra__", None) or {}

        for key, value in extra_payload.items():
            if key == "hash" or value is None:
                continue
            payload_data[key] = value

        return "\n".join(
            f"{key}={self._serialize_telegram_value(value)}"
            for key, value in sorted(payload_data.items())
        )

    def build_google_authorization_url(self, next_path: Optional[str] = None) -> str:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise AuthServiceError(503, "Google OAuth не настроен на сервере.")

        safe_next_path = normalize_next_path(next_path)
        state = create_signed_oauth_state(
            {
                "provider": "google",
                "next_path": safe_next_path,
                "iat": int(time.time()),
            },
            settings.AUTH_OAUTH_STATE_SECRET,
        )
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"

    def build_vk_authorization_url(self, next_path: Optional[str] = None) -> str:
        if not settings.VK_CLIENT_ID:
            raise AuthServiceError(503, "VK OAuth не настроен на сервере.")

        safe_next_path = normalize_next_path(next_path)
        code_verifier = _create_pkce_verifier()
        state = create_signed_oauth_state(
            {
                "provider": "vk",
                "next_path": safe_next_path,
                "code_verifier": code_verifier,
                "iat": int(time.time()),
            },
            settings.AUTH_OAUTH_STATE_SECRET,
        )
        params = {
            "client_id": settings.VK_CLIENT_ID,
            "redirect_uri": settings.VK_REDIRECT_URI,
            "response_type": "code",
            "scope": "email",
            "state": state,
            "code_challenge": _create_pkce_challenge(code_verifier),
            "code_challenge_method": "S256",
        }
        return f"{VK_ID_AUTHORIZE_URL}?{urlencode(params)}"

    def handle_google_callback(
        self,
        *,
        code: str,
        state: str,
        user_agent: Optional[str],
        ip_address: Optional[str],
    ) -> OAuthLoginResult:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise AuthServiceError(503, "Google OAuth не настроен на сервере.")

        state_payload = self._parse_state(state, expected_provider="google")

        try:
            with httpx.Client(timeout=20.0) as client:
                token_response = client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "code": code,
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                        "grant_type": "authorization_code",
                    },
                )
                if token_response.status_code >= 400:
                    raise AuthServiceError(400, "Не удалось завершить вход через Google.")

                token_payload = token_response.json()
                access_token = token_payload.get("access_token")
                if not access_token:
                    raise AuthServiceError(400, "Google не вернул access token.")

                userinfo_response = client.get(
                    GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if userinfo_response.status_code >= 400:
                    raise AuthServiceError(400, "Не удалось получить профиль Google.")

                profile = userinfo_response.json()
        except httpx.HTTPError as error:
            raise AuthServiceError(503, "Google OAuth временно недоступен.") from error
        except ValueError as error:
            raise AuthServiceError(400, "Google вернул некорректный ответ.") from error

        provider_id = str(profile.get("sub") or "")
        if not provider_id:
            raise AuthServiceError(400, "Google не вернул идентификатор пользователя.")

        user, session_token = self.auth_service.authenticate_social_user(
            provider="google",
            provider_id=provider_id,
            email=profile.get("email"),
            email_verified=bool(profile.get("email_verified")),
            username=profile.get("email"),
            first_name=profile.get("given_name"),
            last_name=profile.get("family_name"),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return OAuthLoginResult(user=user, session_token=session_token, next_path=state_payload["next_path"])

    def handle_vk_callback(
        self,
        *,
        code: str,
        state: str,
        device_id: Optional[str],
        user_agent: Optional[str],
        ip_address: Optional[str],
    ) -> OAuthLoginResult:
        if not settings.VK_CLIENT_ID:
            raise AuthServiceError(503, "VK OAuth не настроен на сервере.")

        state_payload = self._parse_state(state, expected_provider="vk")
        code_verifier = str(state_payload.get("code_verifier") or "")
        if not code_verifier:
            raise AuthServiceError(400, "VK OAuth state не содержит PKCE проверку.")
        if not device_id:
            raise AuthServiceError(400, "VK не вернул device_id для завершения входа.")

        try:
            with httpx.Client(timeout=20.0) as client:
                token_params = {
                    "client_id": settings.VK_CLIENT_ID,
                    "redirect_uri": settings.VK_REDIRECT_URI,
                    "grant_type": "authorization_code",
                    "code": code,
                    "code_verifier": code_verifier,
                    "device_id": device_id,
                    "state": state,
                }
                if _has_configured_vk_secret():
                    token_params["client_secret"] = settings.VK_CLIENT_SECRET

                token_response = client.post(
                    VK_ID_TOKEN_URL,
                    data=token_params,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if token_response.status_code >= 400:
                    raise AuthServiceError(400, "Не удалось завершить вход через VK.")

                token_payload = token_response.json()
                if token_payload.get("error"):
                    raise AuthServiceError(400, "Не удалось завершить вход через VK.")
                access_token = token_payload.get("access_token")
                user_id = token_payload.get("user_id")
                email = token_payload.get("email")
                if not access_token or not user_id:
                    raise AuthServiceError(400, "VK не вернул access token или user_id.")

                profile_response = client.get(
                    VK_USERINFO_URL,
                    params={
                        "access_token": access_token,
                        "v": VK_API_VERSION,
                        "user_ids": user_id,
                        "fields": "screen_name,photo_200",
                    },
                )
                if profile_response.status_code >= 400:
                    raise AuthServiceError(400, "Не удалось получить профиль VK.")

                profile_payload = profile_response.json()
                if profile_payload.get("error"):
                    vk_id_profile_response = client.get(
                        VK_ID_USERINFO_URL,
                        params={
                            "access_token": access_token,
                            "client_id": settings.VK_CLIENT_ID,
                        },
                    )
                    if vk_id_profile_response.status_code >= 400:
                        raise AuthServiceError(400, "Не удалось получить профиль VK.")
                    profile_payload = vk_id_profile_response.json()
                    if profile_payload.get("error"):
                        raise AuthServiceError(400, "Не удалось получить профиль VK.")

                profile_items = profile_payload.get("response") or []
                if profile_items:
                    profile = profile_items[0]
                else:
                    profile = _extract_vk_id_profile(profile_payload)
                if not profile:
                    raise AuthServiceError(400, "VK не вернул данные профиля.")
        except httpx.HTTPError as error:
            raise AuthServiceError(503, "VK OAuth временно недоступен.") from error
        except ValueError as error:
            raise AuthServiceError(400, "VK вернул некорректный ответ.") from error

        user, session_token = self.auth_service.authenticate_social_user(
            provider="vk",
            provider_id=str(user_id),
            email=email,
            email_verified=bool(email),
            username=profile.get("screen_name"),
            first_name=profile.get("first_name"),
            last_name=profile.get("last_name"),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return OAuthLoginResult(user=user, session_token=session_token, next_path=state_payload["next_path"])

    def handle_telegram_login(
        self,
        *,
        payload: TelegramAuthRequest,
        user_agent: Optional[str],
        ip_address: Optional[str],
    ) -> tuple[SiteUserPublic, str]:
        if not settings.TELEGRAM_BOT_TOKEN:
            raise AuthServiceError(503, "Telegram авторизация не настроена на сервере.")

        current_time = int(time.time())
        if current_time - payload.auth_date > settings.AUTH_TELEGRAM_LOGIN_TTL_SECONDS:
            raise AuthServiceError(400, "Telegram данные входа устарели. Попробуйте снова.")

        data_check_string = self._build_telegram_data_check_string(payload)
        secret_key = hashlib.sha256(settings.TELEGRAM_BOT_TOKEN.encode("utf-8")).digest()
        expected_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_hash, payload.hash):
            raise AuthServiceError(400, "Не удалось подтвердить Telegram авторизацию.")

        return self.auth_service.authenticate_social_user(
            provider="telegram",
            provider_id=str(payload.id),
            telegram_id=payload.id,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    def _parse_state(self, state: str, *, expected_provider: str) -> dict[str, Any]:
        payload = verify_signed_oauth_state(state, settings.AUTH_OAUTH_STATE_SECRET)
        if not payload:
            raise AuthServiceError(400, "OAuth state недействителен.")

        provider = payload.get("provider")
        issued_at = payload.get("iat")
        if provider != expected_provider or not isinstance(issued_at, int):
            raise AuthServiceError(400, "OAuth state недействителен.")

        if int(time.time()) - issued_at > settings.AUTH_OAUTH_STATE_TTL_SECONDS:
            raise AuthServiceError(400, "Сессия входа истекла. Попробуйте снова.")

        return {
            "provider": provider,
            "next_path": normalize_next_path(payload.get("next_path")),
            "code_verifier": payload.get("code_verifier"),
        }


@lru_cache(maxsize=1)
def get_oauth_service() -> OAuthService:
    return OAuthService()
