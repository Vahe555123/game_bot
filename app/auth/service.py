from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import lru_cache
from math import ceil
from typing import Any, Callable, Optional

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth.email_service import EmailDeliveryError, send_verification_email
from app.auth.exceptions import AuthServiceError
from app.auth.schemas import (
    AuthActionResponse,
    RegisterRequest,
    SitePSNAccountPublic,
    SitePSNAccountUpdateRequest,
    SiteProfilePreferencesUpdateRequest,
    SiteProfileResponse,
    SiteUserPublic,
    normalize_site_user_role,
)
from app.auth.security import (
    generate_session_token,
    generate_verification_code,
    generate_verification_salt,
    hash_session_token,
    hash_verification_code,
    verify_password,
    verify_verification_code,
)
from app.database.connection import SessionLocal
from app.models import PSNAccount, SiteAuthCode, SiteAuthSession, User
from app.utils.encryption import decrypt_password, encrypt_password
from app.utils.time import utcnow as shared_utcnow
from config.settings import settings

REGISTER_PURPOSE = "register"
RESET_PASSWORD_PURPOSE = "password_reset"
SITE_ROLE_CLIENT = "client"
SITE_ROLE_ADMIN = "admin"


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def omit_none_fields(payload: dict[str, Any], *, fields: Optional[set[str]] = None) -> dict[str, Any]:
    target_fields = fields or set(payload.keys())
    return {key: value for key, value in payload.items() if key not in target_fields or value is not None}


def utcnow() -> datetime:
    return shared_utcnow()


def seconds_until(moment: Optional[datetime], *, now: Optional[datetime] = None) -> int:
    if moment is None:
        return 0
    diff = (moment - (now or utcnow())).total_seconds()
    return max(int(ceil(diff)), 0)


def seconds_until_resend(verification_doc: Optional[Any], *, now: Optional[datetime] = None) -> int:
    return seconds_until(_get_value(verification_doc, "resend_available_at"), now=now) if verification_doc else 0


def create_verification_document(
    *,
    user_id: Any,
    email_normalized: str,
    purpose: str,
    now: Optional[datetime] = None,
) -> tuple[str, dict[str, Any]]:
    current_time = now or utcnow()
    code = generate_verification_code(settings.AUTH_EMAIL_CODE_LENGTH)
    salt = generate_verification_salt()
    doc = {
        "user_id": user_id,
        "email_normalized": email_normalized,
        "purpose": purpose,
        "salt": salt,
        "code_hash": hash_verification_code(code, salt),
        "attempts": 0,
        "max_attempts": settings.AUTH_EMAIL_MAX_ATTEMPTS,
        "created_at": current_time,
        "updated_at": current_time,
        "last_sent_at": current_time,
        "resend_available_at": current_time + timedelta(seconds=settings.AUTH_EMAIL_RESEND_COOLDOWN_SECONDS),
        "expires_at": current_time + timedelta(minutes=settings.AUTH_EMAIL_CODE_TTL_MINUTES),
    }
    return code, doc


def is_env_admin_telegram_id(telegram_id: Optional[int]) -> bool:
    return telegram_id is not None and telegram_id in settings.ADMIN_TELEGRAM_IDS


def resolve_site_user_role(raw_role: Optional[str], *, telegram_id: Optional[int] = None) -> str:
    if is_env_admin_telegram_id(telegram_id):
        return SITE_ROLE_ADMIN
    try:
        return normalize_site_user_role(raw_role)
    except ValueError:
        return SITE_ROLE_CLIENT


def is_admin_user_doc(user_doc: Optional[Any]) -> bool:
    return bool(
        user_doc
        and resolve_site_user_role(_get_value(user_doc, "role"), telegram_id=_get_value(user_doc, "telegram_id"))
        == SITE_ROLE_ADMIN
    )


def _extract_auth_providers(source: Any) -> list[str]:
    raw = _get_value(source, "auth_providers", None)
    if isinstance(raw, list):
        return [str(item).strip().lower() for item in raw if str(item).strip()]
    raw_json = _get_value(source, "auth_providers_json", None)
    if not raw_json:
        return []
    try:
        import json

        data = json.loads(raw_json)
    except (TypeError, ValueError):
        return []
    return [str(item).strip().lower() for item in data] if isinstance(data, list) else []


def build_public_user(user_doc: Any) -> SiteUserPublic:
    created_at = _get_value(user_doc, "created_at") or utcnow()
    updated_at = _get_value(user_doc, "updated_at") or created_at
    telegram_id = _get_value(user_doc, "telegram_id")
    role = resolve_site_user_role(_get_value(user_doc, "role"), telegram_id=telegram_id)
    email = _get_value(user_doc, "email") or _get_value(user_doc, "email_normalized")
    return SiteUserPublic(
        id=str(_get_value(user_doc, "id") or _get_value(user_doc, "_id") or ""),
        email=email,
        email_verified=bool(_get_value(user_doc, "email_verified", False)),
        username=_get_value(user_doc, "username"),
        first_name=_get_value(user_doc, "first_name"),
        last_name=_get_value(user_doc, "last_name"),
        telegram_id=telegram_id,
        preferred_region=_get_value(user_doc, "preferred_region", "UA"),
        show_ukraine_prices=bool(_get_value(user_doc, "show_ukraine_prices", False)),
        show_turkey_prices=bool(_get_value(user_doc, "show_turkey_prices", True)),
        show_india_prices=bool(_get_value(user_doc, "show_india_prices", False)),
        payment_email=_get_value(user_doc, "payment_email"),
        platform=_get_value(user_doc, "platform"),
        psn_email=_get_value(user_doc, "psn_email"),
        role=role,
        is_admin=role == SITE_ROLE_ADMIN,
        is_active=bool(_get_value(user_doc, "is_active", True)),
        auth_providers=_extract_auth_providers(user_doc),
        created_at=created_at,
        updated_at=updated_at,
        last_login_at=_get_value(user_doc, "last_login_at"),
    )


def build_public_psn_account(region: str, account_doc: Optional[Any] = None) -> SitePSNAccountPublic:
    encrypted_password = _get_value(account_doc, "psn_password_hash")
    password_salt = _get_value(account_doc, "psn_password_salt")
    psn_password = ""
    if encrypted_password and password_salt:
        try:
            psn_password = decrypt_password(encrypted_password, password_salt)
        except Exception:
            psn_password = ""
    return SitePSNAccountPublic(
        region=(region or "").upper(),
        platform=_get_value(account_doc, "platform"),
        psn_email=_get_value(account_doc, "psn_email"),
        psn_password=psn_password or None,
        has_password=bool(encrypted_password and password_salt),
        has_backup_code=bool(_get_value(account_doc, "twofa_backup_code")),
        updated_at=_get_value(account_doc, "updated_at"),
    )


def build_public_profile(user_doc: Any) -> SiteProfileResponse:
    psn_accounts: dict[str, Any] = {}
    raw_accounts = _get_value(user_doc, "psn_accounts")
    if isinstance(raw_accounts, dict):
        psn_accounts.update(raw_accounts)
    elif raw_accounts:
        for account in raw_accounts:
            region = (_get_value(account, "region") or "").upper()
            if region:
                psn_accounts[region] = account
    if "UA" not in psn_accounts and (_get_value(user_doc, "psn_email") or _get_value(user_doc, "psn_password_hash")):
        psn_accounts["UA"] = {
            "platform": _get_value(user_doc, "platform"),
            "psn_email": _get_value(user_doc, "psn_email"),
            "psn_password_hash": _get_value(user_doc, "psn_password_hash"),
            "psn_password_salt": _get_value(user_doc, "psn_password_salt"),
            "updated_at": _get_value(user_doc, "updated_at"),
        }
    return SiteProfileResponse(
        user=build_public_user(user_doc),
        psn_accounts={
            "UA": build_public_psn_account("UA", psn_accounts.get("UA")),
            "TR": build_public_psn_account("TR", psn_accounts.get("TR")),
        },
    )


def resolve_user_identifier(user_id: Any) -> Any:
    if isinstance(user_id, str):
        normalized = user_id.strip()
        if not normalized:
            return user_id
        return int(normalized) if normalized.isdigit() else normalized
    return user_id


def _map_integrity_error(error: IntegrityError) -> AuthServiceError:
    error_text = str(error).lower()
    if "users.telegram_id" in error_text:
        return AuthServiceError(409, "Этот Telegram ID уже привязан к другому аккаунту.")
    if "users.google_id" in error_text:
        return AuthServiceError(409, "Этот Google аккаунт уже привязан к другому профилю.")
    if "users.vk_id" in error_text:
        return AuthServiceError(409, "Этот VK аккаунт уже привязан к другому профилю.")
    if "users.email" in error_text:
        return AuthServiceError(409, "Пользователь с таким email уже существует.")
    return AuthServiceError(409, "Пользователь с такими данными уже существует.")


class AuthService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
        email_sender: Optional[Callable[..., None]] = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.session_factory = session_factory or SessionLocal
        self.email_sender = email_sender or send_verification_email
        self.clock = clock

    @contextmanager
    def _session(self):
        db = self.session_factory()
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    def _get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        normalized = self._normalize_email(email)
        return db.query(User).filter(or_(User.email_normalized == normalized, User.email == normalized)).first()

    def _get_user_by_id(self, db: Session, user_id: Any) -> Optional[User]:
        return db.query(User).options(selectinload(User.psn_accounts)).filter(User.id == resolve_user_identifier(user_id)).first()

    def _get_code(self, db: Session, email: str, purpose: str) -> Optional[SiteAuthCode]:
        normalized = self._normalize_email(email)
        return (
            db.query(SiteAuthCode)
            .filter(SiteAuthCode.email_normalized == normalized, SiteAuthCode.purpose == purpose)
            .first()
        )

    def _save_code(self, db: Session, *, user: User, email: str, purpose: str) -> tuple[str, SiteAuthCode]:
        current_time = self.clock()
        email_normalized = self._normalize_email(email)
        code, data = create_verification_document(user_id=user.id, email_normalized=email_normalized, purpose=purpose, now=current_time)
        code_row = self._get_code(db, email, purpose) or SiteAuthCode(user_id=user.id, email_normalized=email_normalized, purpose=purpose)
        code_row.user_id = user.id
        code_row.email_normalized = email_normalized
        code_row.purpose = purpose
        code_row.salt = data["salt"]
        code_row.code_hash = data["code_hash"]
        code_row.attempts = 0
        code_row.max_attempts = settings.AUTH_EMAIL_MAX_ATTEMPTS
        code_row.created_at = code_row.created_at or current_time
        code_row.updated_at = current_time
        code_row.last_sent_at = current_time
        code_row.resend_available_at = data["resend_available_at"]
        code_row.expires_at = data["expires_at"]
        db.add(code_row)
        db.commit()
        return code, code_row

    def _send_code(self, email: str, code: str, *, purpose: str) -> None:
        try:
            self.email_sender(email, code, purpose=purpose)
        except EmailDeliveryError as error:
            raise AuthServiceError(503, str(error)) from error

    def _create_session(self, db: Session, *, user: User, provider: str, user_agent: Optional[str], ip_address: Optional[str]) -> str:
        current_time = self.clock()
        token = generate_session_token()
        session_row = SiteAuthSession(
            user_id=user.id,
            session_token_hash=hash_session_token(token),
            provider=provider,
            user_agent=user_agent,
            ip_address=ip_address,
            created_at=current_time,
            expires_at=current_time + timedelta(days=settings.AUTH_SESSION_TTL_DAYS),
            last_used_at=current_time,
        )
        db.add(session_row)
        db.commit()
        return token

    def _check_and_consume_code(self, db: Session, *, email: str, code: str, purpose: str) -> tuple[User, SiteAuthCode]:
        user = self._get_user_by_email(db, email)
        if not user:
            raise AuthServiceError(404, "Пользователь с таким email не найден.")
        verification = self._get_code(db, email, purpose)
        if not verification:
            raise AuthServiceError(400, "Сначала запросите код подтверждения.")
        now = self.clock()
        if verification.expires_at <= now:
            db.delete(verification)
            db.commit()
            raise AuthServiceError(400, "Срок действия кода истек. Запросите новый код.")
        if int(verification.attempts or 0) >= int(verification.max_attempts or settings.AUTH_EMAIL_MAX_ATTEMPTS):
            db.delete(verification)
            db.commit()
            raise AuthServiceError(429, "Лимит попыток исчерпан. Запросите новый код.")
        if not verify_verification_code(code, verification.salt, verification.code_hash):
            verification.attempts = int(verification.attempts or 0) + 1
            verification.updated_at = now
            db.add(verification)
            db.commit()
            raise AuthServiceError(
                400,
                "Неверный код подтверждения.",
                extra={"attempts_left": max(int(verification.max_attempts) - int(verification.attempts), 0)},
            )
        return user, verification

    def _sync_region_flags(self, user: User) -> None:
        user.show_ukraine_prices = user.preferred_region == "UA"
        user.show_turkey_prices = user.preferred_region == "TR"
        user.show_india_prices = user.preferred_region == "IN"

    def start_registration(self, payload: RegisterRequest, *, user_agent: Optional[str] = None, ip_address: Optional[str] = None) -> AuthActionResponse:
        now = self.clock()
        if len(payload.password) < settings.AUTH_PASSWORD_MIN_LENGTH:
            raise AuthServiceError(422, f"Пароль должен быть не короче {settings.AUTH_PASSWORD_MIN_LENGTH} символов.")
        with self._session() as db:
            try:
                user = self._get_user_by_email(db, payload.email)
                if user and user.email_verified:
                    raise AuthServiceError(409, "Пользователь с таким email уже зарегистрирован.")
                if not user:
                    user = User(email=self._normalize_email(payload.email), email_normalized=self._normalize_email(payload.email), created_at=now, updated_at=now)
                    db.add(user)
                    db.flush()
                if payload.telegram_id is not None and user.telegram_id not in (None, payload.telegram_id):
                    raise AuthServiceError(409, "Этот Telegram ID уже привязан к другому аккаунту.")
                user.telegram_id = payload.telegram_id or user.telegram_id
                user.username = payload.username
                user.first_name = payload.first_name
                user.last_name = payload.last_name
                user.preferred_region = payload.preferred_region
                self._sync_region_flags(user)
                user.payment_email = payload.payment_email
                user.platform = payload.platform
                user.psn_email = payload.psn_email
                user.set_password(payload.password)
                user.email_verified = False
                user.is_active = False
                user.last_registration_at = now
                user.registration_user_agent = user_agent
                user.registration_ip_address = ip_address
                user.updated_at = now
                db.add(user)
                db.commit()
                db.refresh(user)
                code, _ = self._save_code(db, user=user, email=payload.email, purpose=REGISTER_PURPOSE)
                self._send_code(payload.email, code, purpose=REGISTER_PURPOSE)
            except IntegrityError as error:
                db.rollback()
                raise _map_integrity_error(error) from error
        return AuthActionResponse(message="Код подтверждения отправлен на email.", resend_available_in=settings.AUTH_EMAIL_RESEND_COOLDOWN_SECONDS)

    def resend_registration_code(self, email: str) -> AuthActionResponse:
        with self._session() as db:
            user = self._get_user_by_email(db, email)
            if not user:
                raise AuthServiceError(404, "Пользователь с таким email не найден.")
            if user.email_verified:
                raise AuthServiceError(409, "Email уже подтвержден.")
            existing = self._get_code(db, email, REGISTER_PURPOSE)
            resend_in = seconds_until_resend(existing, now=self.clock())
            if resend_in > 0:
                raise AuthServiceError(429, "Повторная отправка пока недоступна.", extra={"resend_available_in": resend_in})
            code, _ = self._save_code(db, user=user, email=email, purpose=REGISTER_PURPOSE)
            self._send_code(email, code, purpose=REGISTER_PURPOSE)
        return AuthActionResponse(message="Новый код подтверждения отправлен на email.", resend_available_in=settings.AUTH_EMAIL_RESEND_COOLDOWN_SECONDS)

    def start_password_reset(self, email: str) -> AuthActionResponse:
        with self._session() as db:
            user = self._get_user_by_email(db, email)
            if not user:
                raise AuthServiceError(404, "Пользователь с таким email не найден.")
            existing = self._get_code(db, email, RESET_PASSWORD_PURPOSE)
            resend_in = seconds_until_resend(existing, now=self.clock())
            if resend_in > 0:
                raise AuthServiceError(429, "Код уже отправлен. Попробуйте чуть позже.", extra={"resend_available_in": resend_in})
            code, _ = self._save_code(db, user=user, email=email, purpose=RESET_PASSWORD_PURPOSE)
            self._send_code(email, code, purpose=RESET_PASSWORD_PURPOSE)
        return AuthActionResponse(message="Код для восстановления пароля отправлен на email.", resend_available_in=settings.AUTH_EMAIL_RESEND_COOLDOWN_SECONDS)

    def resend_password_reset_code(self, email: str) -> AuthActionResponse:
        with self._session() as db:
            user = self._get_user_by_email(db, email)
            if not user:
                raise AuthServiceError(404, "Пользователь с таким email не найден.")
            existing = self._get_code(db, email, RESET_PASSWORD_PURPOSE)
            resend_in = seconds_until_resend(existing, now=self.clock())
            if resend_in > 0:
                raise AuthServiceError(429, "Повторная отправка пока недоступна.", extra={"resend_available_in": resend_in})
            code, _ = self._save_code(db, user=user, email=email, purpose=RESET_PASSWORD_PURPOSE)
            self._send_code(email, code, purpose=RESET_PASSWORD_PURPOSE)
        return AuthActionResponse(message="Новый код для восстановления пароля отправлен на email.", resend_available_in=settings.AUTH_EMAIL_RESEND_COOLDOWN_SECONDS)

    def verify_registration_code(self, *, email: str, code: str, user_agent: Optional[str] = None, ip_address: Optional[str] = None) -> tuple[SiteUserPublic, str]:
        now = self.clock()
        with self._session() as db:
            user, verification = self._check_and_consume_code(db, email=email, code=code, purpose=REGISTER_PURPOSE)
            if user.email_verified:
                raise AuthServiceError(409, "Email уже подтвержден.")
            user.email_verified = True
            user.is_active = True
            user.last_login_at = now
            user.login_user_agent = user_agent
            user.login_ip_address = ip_address
            user.updated_at = now
            db.delete(verification)
            db.add(user)
            db.commit()
            db.refresh(user)
            token = self._create_session(db, user=user, provider="email", user_agent=user_agent, ip_address=ip_address)
            return build_public_user(user), token

    def login(self, *, email: str, password: str, user_agent: Optional[str] = None, ip_address: Optional[str] = None) -> tuple[SiteUserPublic, str]:
        now = self.clock()
        with self._session() as db:
            user = self._get_user_by_email(db, email)
            if not user or not user.email_verified:
                raise AuthServiceError(403, "Сначала подтвердите email.")
            if not user.is_active:
                raise AuthServiceError(403, "Пользователь деактивирован.")
            if not user.password_hash or not verify_password(password, user.password_hash):
                raise AuthServiceError(401, "Неверный email или пароль.")
            user.last_login_at = now
            user.login_user_agent = user_agent
            user.login_ip_address = ip_address
            user.updated_at = now
            db.add(user)
            db.commit()
            db.refresh(user)
            token = self._create_session(db, user=user, provider="email", user_agent=user_agent, ip_address=ip_address)
            return build_public_user(user), token

    def confirm_password_reset(self, *, email: str, code: str, new_password: str, user_agent: Optional[str] = None, ip_address: Optional[str] = None) -> tuple[SiteUserPublic, str]:
        if len(new_password) < settings.AUTH_PASSWORD_MIN_LENGTH:
            raise AuthServiceError(422, f"Пароль должен быть не короче {settings.AUTH_PASSWORD_MIN_LENGTH} символов.")
        now = self.clock()
        with self._session() as db:
            user, verification = self._check_and_consume_code(db, email=email, code=code, purpose=RESET_PASSWORD_PURPOSE)
            user.set_password(new_password)
            user.is_active = True
            user.last_login_at = now
            user.login_user_agent = user_agent
            user.login_ip_address = ip_address
            user.updated_at = now
            db.delete(verification)
            db.add(user)
            db.commit()
            db.refresh(user)
            token = self._create_session(db, user=user, provider="email", user_agent=user_agent, ip_address=ip_address)
            return build_public_user(user), token

    def authenticate_social_user(
        self,
        *,
        provider: str,
        provider_id: str,
        email: Optional[str] = None,
        email_verified: bool = False,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        telegram_id: Optional[int] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> tuple[SiteUserPublic, str]:
        provider = (provider or "").strip().lower()
        provider_id = (provider_id or "").strip()
        if provider not in {"google", "vk", "telegram"}:
            raise AuthServiceError(422, "Недопустимый provider.")
        if provider != "telegram" and not provider_id:
            raise AuthServiceError(422, "Недопустимый provider_id.")

        now = self.clock()
        with self._session() as db:
            user = None
            if provider == "telegram" and telegram_id is not None:
                user = db.query(User).filter(User.telegram_id == telegram_id).first()
            elif provider == "google":
                user = db.query(User).filter(User.google_id == provider_id).first()
            elif provider == "vk":
                user = db.query(User).filter(User.vk_id == provider_id).first()
            if not user and email:
                user = self._get_user_by_email(db, email)
            if not user:
                user = User(
                    email=self._normalize_email(email) if email else None,
                    email_normalized=self._normalize_email(email) if email else None,
                    email_verified=bool(email_verified or provider == "telegram"),
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    telegram_id=telegram_id,
                    google_id=provider_id if provider == "google" else None,
                    vk_id=provider_id if provider == "vk" else None,
                    preferred_region="UA",
                    show_turkey_prices=True,
                    is_active=True,
                    role=SITE_ROLE_CLIENT,
                    last_login_at=now,
                    updated_at=now,
                )
                user.auth_providers = [provider]
                db.add(user)
                db.flush()
            else:
                if email:
                    normalized = self._normalize_email(email)
                    user.email = normalized
                    user.email_normalized = normalized
                if provider == "telegram" and telegram_id is not None:
                    user.telegram_id = telegram_id
                if provider == "google":
                    user.google_id = provider_id
                if provider == "vk":
                    user.vk_id = provider_id
                if username is not None:
                    user.username = username
                if first_name is not None:
                    user.first_name = first_name
                if last_name is not None:
                    user.last_name = last_name
                if email_verified:
                    user.email_verified = True
                user.is_active = True
                user.last_login_at = now
                user.updated_at = now
                providers = set(user.auth_providers)
                providers.add(provider)
                user.auth_providers = sorted(providers)
                db.add(user)
            try:
                db.commit()
                db.refresh(user)
            except IntegrityError as error:
                db.rollback()
                raise _map_integrity_error(error) from error
            token = self._create_session(db, user=user, provider=provider, user_agent=user_agent, ip_address=ip_address)
            return build_public_user(user), token

    def logout(self, session_token: Optional[str]) -> None:
        if not session_token:
            return
        with self._session() as db:
            token_hash = hash_session_token(session_token)
            session_row = db.query(SiteAuthSession).filter(SiteAuthSession.session_token_hash == token_hash).first()
            if session_row:
                db.delete(session_row)
                db.commit()

    def get_user_by_session_token(self, session_token: Optional[str]) -> Optional[SiteUserPublic]:
        if not session_token:
            return None
        with self._session() as db:
            token_hash = hash_session_token(session_token)
            session_row = (
                db.query(SiteAuthSession)
                .options(selectinload(SiteAuthSession.user).selectinload(User.psn_accounts))
                .filter(
                    SiteAuthSession.session_token_hash == token_hash,
                    SiteAuthSession.revoked_at.is_(None),
                    SiteAuthSession.expires_at > self.clock(),
                )
                .first()
            )
            if not session_row or not session_row.user or not session_row.user.is_active:
                return None
            session_row.last_used_at = self.clock()
            db.add(session_row)
            db.commit()
            return build_public_user(session_row.user)

    def get_profile(self, user_id: Any) -> SiteProfileResponse:
        with self._session() as db:
            user = self._get_user_by_id(db, user_id)
            if not user:
                raise AuthServiceError(404, "Профиль пользователя не найден.")
            return build_public_profile(user)

    def update_profile_preferences(self, user_id: Any, payload: SiteProfilePreferencesUpdateRequest) -> SiteProfileResponse:
        now = self.clock()
        with self._session() as db:
            user = self._get_user_by_id(db, user_id)
            if not user:
                raise AuthServiceError(404, "Профиль пользователя не найден.")
            user.preferred_region = payload.preferred_region
            self._sync_region_flags(user)
            if payload.payment_email is not None:
                user.payment_email = payload.payment_email
            user.updated_at = now
            db.add(user)
            db.commit()
            db.refresh(user)
            return build_public_profile(user)

    def update_psn_account(self, user_id: Any, *, region: str, payload: SitePSNAccountUpdateRequest) -> SiteProfileResponse:
        now = self.clock()
        normalized_region = (region or "").strip().upper()
        with self._session() as db:
            user = self._get_user_by_id(db, user_id)
            if not user:
                raise AuthServiceError(404, "Профиль пользователя не найден.")
            account = user.get_psn_account_for_region(normalized_region)
            if account is None:
                account = PSNAccount(user_id=user.id, region=normalized_region)
                db.add(account)
            if payload.platform is not None:
                account.platform = payload.platform
                if normalized_region == "UA":
                    user.platform = payload.platform
            if payload.psn_email is not None:
                account.psn_email = payload.psn_email
                if normalized_region == "UA":
                    user.psn_email = payload.psn_email
            if payload.psn_password is not None:
                account.set_psn_password(payload.psn_password)
                if normalized_region == "UA":
                    user.set_psn_password(payload.psn_password)
            if payload.backup_code is not None:
                account.set_twofa_code(payload.backup_code)
            account.updated_at = now
            user.updated_at = now
            db.add(user)
            db.add(account)
            db.commit()
            db.refresh(user)
            return build_public_profile(user)


@lru_cache(maxsize=1)
def get_auth_service() -> AuthService:
    return AuthService()
