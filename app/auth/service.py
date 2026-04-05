from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from math import ceil
from typing import Any, Callable, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, PyMongoError

from config.settings import settings
from app.utils.encryption import encrypt_password

from .email_service import EmailDeliveryError, send_verification_email
from .exceptions import AuthServiceError
from .mongo import (
    get_auth_codes_collection,
    get_auth_sessions_collection,
    get_auth_users_collection,
)
from .schemas import (
    AuthActionResponse,
    RegisterRequest,
    SitePSNAccountPublic,
    SiteProfilePreferencesUpdateRequest,
    SiteProfileResponse,
    SitePSNAccountUpdateRequest,
    SiteUserPublic,
    normalize_site_user_role,
)
from .security import (
    generate_session_token,
    generate_verification_code,
    generate_verification_salt,
    hash_password,
    hash_session_token,
    hash_verification_code,
    verify_password,
    verify_verification_code,
)

REGISTER_PURPOSE = "register"
SITE_ROLE_CLIENT = "client"
SITE_ROLE_ADMIN = "admin"


def utcnow() -> datetime:
    return datetime.utcnow()


def seconds_until(moment: Optional[datetime], *, now: Optional[datetime] = None) -> int:
    if moment is None:
        return 0

    current_time = now or utcnow()
    diff_seconds = (moment - current_time).total_seconds()
    if diff_seconds <= 0:
        return 0
    return int(ceil(diff_seconds))


def seconds_until_resend(verification_doc: Optional[dict[str, Any]], *, now: Optional[datetime] = None) -> int:
    if not verification_doc:
        return 0
    return seconds_until(verification_doc.get("resend_available_at"), now=now)


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

    verification_doc = {
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
    return code, verification_doc


def is_env_admin_telegram_id(telegram_id: Optional[int]) -> bool:
    return telegram_id is not None and telegram_id in settings.ADMIN_TELEGRAM_IDS


def resolve_site_user_role(raw_role: Optional[str], *, telegram_id: Optional[int] = None) -> str:
    if is_env_admin_telegram_id(telegram_id):
        return SITE_ROLE_ADMIN

    try:
        return normalize_site_user_role(raw_role)
    except ValueError:
        return SITE_ROLE_CLIENT


def is_admin_user_doc(user_doc: Optional[dict[str, Any]]) -> bool:
    if not user_doc:
        return False

    return resolve_site_user_role(
        user_doc.get("role"),
        telegram_id=user_doc.get("telegram_id"),
    ) == SITE_ROLE_ADMIN


def build_public_user(user_doc: dict[str, Any]) -> SiteUserPublic:
    created_at = user_doc.get("created_at") or utcnow()
    updated_at = user_doc.get("updated_at") or created_at
    role = resolve_site_user_role(
        user_doc.get("role"),
        telegram_id=user_doc.get("telegram_id"),
    )

    return SiteUserPublic(
        id=str(user_doc.get("_id", "")),
        email=user_doc.get("email"),
        email_verified=bool(user_doc.get("email_verified", False)),
        username=user_doc.get("username"),
        first_name=user_doc.get("first_name"),
        last_name=user_doc.get("last_name"),
        telegram_id=user_doc.get("telegram_id"),
        preferred_region=user_doc.get("preferred_region", "UA"),
        show_ukraine_prices=bool(user_doc.get("show_ukraine_prices", False)),
        show_turkey_prices=bool(user_doc.get("show_turkey_prices", True)),
        show_india_prices=bool(user_doc.get("show_india_prices", False)),
        payment_email=user_doc.get("payment_email"),
        platform=user_doc.get("platform"),
        psn_email=user_doc.get("psn_email"),
        role=role,
        is_admin=role == SITE_ROLE_ADMIN,
        is_active=bool(user_doc.get("is_active", True)),
        auth_providers=list(user_doc.get("auth_providers", [])),
        created_at=created_at,
        updated_at=updated_at,
        last_login_at=user_doc.get("last_login_at"),
    )


def build_public_psn_account(region: str, account_doc: Optional[dict[str, Any]] = None) -> SitePSNAccountPublic:
    region_code = (region or "").upper()
    current_account = account_doc or {}

    return SitePSNAccountPublic(
        region=region_code,
        platform=current_account.get("platform"),
        psn_email=current_account.get("psn_email"),
        has_password=bool(current_account.get("psn_password_hash")),
        has_backup_code=bool(current_account.get("backup_code_hash")),
        updated_at=current_account.get("updated_at"),
    )


def build_public_profile(user_doc: dict[str, Any]) -> SiteProfileResponse:
    psn_accounts = dict(user_doc.get("psn_accounts") or {})

    if "UA" not in psn_accounts and (user_doc.get("platform") or user_doc.get("psn_email")):
        psn_accounts["UA"] = {
            "platform": user_doc.get("platform"),
            "psn_email": user_doc.get("psn_email"),
            "updated_at": user_doc.get("updated_at"),
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
        normalized_id = user_id.strip()
        if not normalized_id:
            return user_id

        try:
            return ObjectId(normalized_id)
        except (InvalidId, TypeError):
            return normalized_id

    return user_id


class AuthService:
    def __init__(
        self,
        *,
        users: Optional[Collection] = None,
        codes: Optional[Collection] = None,
        sessions: Optional[Collection] = None,
        email_sender: Optional[Callable[[str, str], None]] = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.users = users or get_auth_users_collection()
        self.codes = codes or get_auth_codes_collection()
        self.sessions = sessions or get_auth_sessions_collection()
        self.email_sender = email_sender or send_verification_email
        self.clock = clock

    def start_registration(
        self,
        payload: RegisterRequest,
        *,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuthActionResponse:
        current_time = self.clock()

        if len(payload.password) < settings.AUTH_PASSWORD_MIN_LENGTH:
            raise AuthServiceError(
                422,
                f"Пароль должен быть не короче {settings.AUTH_PASSWORD_MIN_LENGTH} символов.",
            )

        try:
            existing_user = self.users.find_one({"email_normalized": payload.email})
            if existing_user and existing_user.get("email_verified"):
                raise AuthServiceError(409, "Пользователь с таким email уже зарегистрирован.")

            existing_verification = self.codes.find_one(
                {"email_normalized": payload.email, "purpose": REGISTER_PURPOSE}
            )
            resend_in = seconds_until_resend(existing_verification, now=current_time)
            if resend_in > 0:
                raise AuthServiceError(
                    429,
                    "Код уже отправлен. Попробуйте чуть позже.",
                    extra={"resend_available_in": resend_in},
                )

            user_id = self._upsert_registration_user(
                payload=payload,
                existing_user=existing_user,
                current_time=current_time,
                user_agent=user_agent,
                ip_address=ip_address,
            )

            code, verification_doc = create_verification_document(
                user_id=user_id,
                email_normalized=payload.email,
                purpose=REGISTER_PURPOSE,
                now=current_time,
            )
            self._save_verification_and_send_email(
                email=payload.email,
                verification_doc=verification_doc,
                code=code,
                previous_doc=existing_verification,
            )
        except AuthServiceError:
            raise
        except DuplicateKeyError as error:
            raise self._map_duplicate_key_error(error) from error
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

        return AuthActionResponse(
            message="Код подтверждения отправлен на email.",
            resend_available_in=settings.AUTH_EMAIL_RESEND_COOLDOWN_SECONDS,
        )

    def resend_registration_code(self, email: str) -> AuthActionResponse:
        current_time = self.clock()

        try:
            user_doc = self.users.find_one({"email_normalized": email})
            if not user_doc:
                raise AuthServiceError(404, "Пользователь с таким email не найден.")
            if user_doc.get("email_verified"):
                raise AuthServiceError(409, "Email уже подтвержден.")

            existing_verification = self.codes.find_one(
                {"email_normalized": email, "purpose": REGISTER_PURPOSE}
            )
            resend_in = seconds_until_resend(existing_verification, now=current_time)
            if resend_in > 0:
                raise AuthServiceError(
                    429,
                    "Повторная отправка пока недоступна.",
                    extra={"resend_available_in": resend_in},
                )

            code, verification_doc = create_verification_document(
                user_id=user_doc["_id"],
                email_normalized=email,
                purpose=REGISTER_PURPOSE,
                now=current_time,
            )
            self._save_verification_and_send_email(
                email=email,
                verification_doc=verification_doc,
                code=code,
                previous_doc=existing_verification,
            )
        except AuthServiceError:
            raise
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

        return AuthActionResponse(
            message="Новый код подтверждения отправлен на email.",
            resend_available_in=settings.AUTH_EMAIL_RESEND_COOLDOWN_SECONDS,
        )

    def verify_registration_code(
        self,
        *,
        email: str,
        code: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> tuple[SiteUserPublic, str]:
        current_time = self.clock()
        filter_query = {"email_normalized": email, "purpose": REGISTER_PURPOSE}

        try:
            user_doc = self.users.find_one({"email_normalized": email})
            if not user_doc:
                raise AuthServiceError(404, "Пользователь с таким email не найден.")
            if user_doc.get("email_verified"):
                raise AuthServiceError(409, "Email уже подтвержден.")

            verification_doc = self.codes.find_one(filter_query)
            if not verification_doc:
                raise AuthServiceError(400, "Сначала запросите код подтверждения.")

            if verification_doc.get("expires_at") and verification_doc["expires_at"] <= current_time:
                self.codes.delete_one(filter_query)
                raise AuthServiceError(400, "Срок действия кода истек. Запросите новый код.")

            max_attempts = int(verification_doc.get("max_attempts", settings.AUTH_EMAIL_MAX_ATTEMPTS))
            attempts = int(verification_doc.get("attempts", 0))
            if attempts >= max_attempts:
                self.codes.delete_one(filter_query)
                raise AuthServiceError(429, "Лимит попыток исчерпан. Запросите новый код.")

            if not verify_verification_code(
                code,
                verification_doc["salt"],
                verification_doc["code_hash"],
            ):
                attempts += 1
                self.codes.update_one(
                    filter_query,
                    {"$set": {"attempts": attempts, "updated_at": current_time}},
                )
                if attempts >= max_attempts:
                    self.codes.delete_one(filter_query)
                    raise AuthServiceError(429, "Лимит попыток исчерпан. Запросите новый код.")

                raise AuthServiceError(
                    400,
                    "Неверный код подтверждения.",
                    extra={"attempts_left": max_attempts - attempts},
                )

            self.users.update_one(
                {"_id": user_doc["_id"]},
                {
                    "$set": {
                        "email_verified": True,
                        "is_active": True,
                        "updated_at": current_time,
                        "last_login_at": current_time,
                    }
                },
            )
            self.codes.delete_one(filter_query)

            updated_user = self.users.find_one({"_id": user_doc["_id"]})
            if not updated_user:
                raise AuthServiceError(404, "Пользователь не найден после подтверждения email.")

            session_token = self._create_session(
                user_id=updated_user["_id"],
                user_agent=user_agent,
                ip_address=ip_address,
                current_time=current_time,
            )
        except AuthServiceError:
            raise
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

        return build_public_user(updated_user), session_token

    def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> tuple[SiteUserPublic, str]:
        current_time = self.clock()

        try:
            user_doc = self.users.find_one({"email_normalized": email})
            if not user_doc or not user_doc.get("password_hash"):
                raise AuthServiceError(401, "Неверный email или пароль.")

            if not verify_password(password, user_doc["password_hash"]):
                raise AuthServiceError(401, "Неверный email или пароль.")

            if not user_doc.get("email_verified"):
                raise AuthServiceError(403, "Сначала подтвердите email с помощью кода из письма.")

            if not user_doc.get("is_active", True):
                raise AuthServiceError(403, "Аккаунт отключен.")

            self.users.update_one(
                {"_id": user_doc["_id"]},
                {"$set": {"updated_at": current_time, "last_login_at": current_time}},
            )
            updated_user = self.users.find_one({"_id": user_doc["_id"]})
            if not updated_user:
                raise AuthServiceError(404, "Пользователь не найден.")

            session_token = self._create_session(
                user_id=updated_user["_id"],
                user_agent=user_agent,
                ip_address=ip_address,
                current_time=current_time,
            )
        except AuthServiceError:
            raise
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

        return build_public_user(updated_user), session_token

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
        preferred_region: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> tuple[SiteUserPublic, str]:
        current_time = self.clock()

        try:
            user_doc = self._find_social_user(
                provider=provider,
                provider_id=provider_id,
                email=email,
                telegram_id=telegram_id,
            )

            auth_providers = set(user_doc.get("auth_providers", [])) if user_doc else set()
            auth_providers.add(provider)

            update_fields = {
                "updated_at": current_time,
                "last_login_at": current_time,
                "is_active": True,
                "auth_providers": sorted(auth_providers),
                "role": resolve_site_user_role(
                    user_doc.get("role") if user_doc else None,
                    telegram_id=telegram_id if telegram_id is not None else (user_doc.get("telegram_id") if user_doc else None),
                ),
            }

            if username:
                update_fields["username"] = username
            if first_name:
                update_fields["first_name"] = first_name
            if last_name:
                update_fields["last_name"] = last_name
            if preferred_region:
                update_fields["preferred_region"] = preferred_region

            email_normalized = email.lower() if email else None
            if email_normalized:
                update_fields["email"] = email_normalized
                update_fields["email_normalized"] = email_normalized
                if email_verified:
                    update_fields["email_verified"] = True

            if provider == "google":
                update_fields["google_id"] = provider_id
            elif provider == "vk":
                update_fields["vk_id"] = provider_id
            elif provider == "telegram":
                update_fields["telegram_id"] = telegram_id

            if user_doc:
                self.users.update_one({"_id": user_doc["_id"]}, {"$set": update_fields})
                user_id = user_doc["_id"]
            else:
                user_fields = {
                    "password_hash": None,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "telegram_id": telegram_id,
                    "role": resolve_site_user_role(None, telegram_id=telegram_id),
                    "preferred_region": preferred_region or "UA",
                    "show_ukraine_prices": False,
                    "show_turkey_prices": True,
                    "show_india_prices": False,
                    "payment_email": email_normalized if email_normalized else None,
                    "platform": None,
                    "psn_email": None,
                    "psn_accounts": {},
                    "email_verified": bool(email_normalized and email_verified),
                    "is_active": True,
                    "auth_providers": sorted(auth_providers),
                    "created_at": current_time,
                    "updated_at": current_time,
                    "last_login_at": current_time,
                    "last_registration_at": current_time,
                    "registration_user_agent": user_agent,
                    "registration_ip_address": ip_address,
                }
                if email_normalized:
                    user_fields["email"] = email_normalized
                    user_fields["email_normalized"] = email_normalized
                if provider == "google":
                    user_fields["google_id"] = provider_id
                if provider == "vk":
                    user_fields["vk_id"] = provider_id
                insert_result = self.users.insert_one(user_fields)
                user_id = insert_result.inserted_id

            updated_user = self.users.find_one({"_id": user_id})
            if not updated_user:
                raise AuthServiceError(404, "Пользователь не найден после входа через провайдера.")

            session_token = self._create_session(
                user_id=user_id,
                user_agent=user_agent,
                ip_address=ip_address,
                current_time=current_time,
            )
        except AuthServiceError:
            raise
        except DuplicateKeyError as error:
            raise self._map_duplicate_key_error(error) from error
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

        return build_public_user(updated_user), session_token

    def logout(self, session_token: Optional[str]) -> None:
        if not session_token:
            return

        try:
            self.sessions.delete_one({"token_hash": hash_session_token(session_token)})
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

    def get_user_by_session_token(self, session_token: Optional[str]) -> Optional[SiteUserPublic]:
        if not session_token:
            return None

        current_time = self.clock()
        try:
            session_doc = self.sessions.find_one(
                {
                    "token_hash": hash_session_token(session_token),
                    "expires_at": {"$gt": current_time},
                }
            )
            if not session_doc:
                return None

            user_doc = self.users.find_one({"_id": session_doc["user_id"], "is_active": True})
            if not user_doc:
                self.sessions.delete_one({"_id": session_doc["_id"]})
                return None

            self.sessions.update_one(
                {"_id": session_doc["_id"]},
                {"$set": {"updated_at": current_time, "last_seen_at": current_time}},
            )
            return build_public_user(user_doc)
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

    def get_profile(self, user_id: Any) -> SiteProfileResponse:
        resolved_user_id = resolve_user_identifier(user_id)
        try:
            user_doc = self.users.find_one({"_id": resolved_user_id, "is_active": True})
            if not user_doc:
                raise AuthServiceError(404, "Профиль не найден.")
        except AuthServiceError:
            raise
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

        return build_public_profile(user_doc)

    def update_profile_preferences(
        self,
        user_id: Any,
        payload: SiteProfilePreferencesUpdateRequest,
    ) -> SiteProfileResponse:
        current_time = self.clock()
        preferred_region = payload.preferred_region
        resolved_user_id = resolve_user_identifier(user_id)

        try:
            user_doc = self.users.find_one({"_id": resolved_user_id, "is_active": True})
            if not user_doc:
                raise AuthServiceError(404, "Профиль не найден.")

            update_fields = {
                "preferred_region": preferred_region,
                "payment_email": payload.payment_email,
                "show_ukraine_prices": preferred_region == "UA",
                "show_turkey_prices": preferred_region == "TR",
                "show_india_prices": preferred_region == "IN",
                "updated_at": current_time,
            }

            self.users.update_one({"_id": resolved_user_id}, {"$set": update_fields})
            updated_user = self.users.find_one({"_id": resolved_user_id, "is_active": True})
            if not updated_user:
                raise AuthServiceError(404, "Профиль не найден после обновления.")
        except AuthServiceError:
            raise
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

        return build_public_profile(updated_user)

    def update_psn_account(
        self,
        user_id: Any,
        *,
        region: str,
        payload: SitePSNAccountUpdateRequest,
    ) -> SiteProfileResponse:
        current_time = self.clock()
        normalized_region = region.strip().upper()
        resolved_user_id = resolve_user_identifier(user_id)

        if normalized_region not in {"UA", "TR"}:
            raise AuthServiceError(422, "Допустимы только регионы UA и TR.")

        try:
            user_doc = self.users.find_one({"_id": resolved_user_id, "is_active": True})
            if not user_doc:
                raise AuthServiceError(404, "Профиль не найден.")

            existing_accounts = dict(user_doc.get("psn_accounts") or {})
            region_account = dict(existing_accounts.get(normalized_region) or {})

            if payload.platform is not None:
                region_account["platform"] = payload.platform
            if payload.psn_email is not None:
                region_account["psn_email"] = payload.psn_email

            if payload.psn_password:
                encoded_password, password_salt = encrypt_password(payload.psn_password)
                region_account["psn_password_hash"] = encoded_password
                region_account["psn_password_salt"] = password_salt

            if payload.backup_code:
                encoded_backup, backup_salt = encrypt_password(payload.backup_code)
                region_account["backup_code_hash"] = encoded_backup
                region_account["backup_code_salt"] = backup_salt

            if not region_account.get("psn_email"):
                raise AuthServiceError(422, "Введите PSN Email.")
            if not region_account.get("psn_password_hash"):
                raise AuthServiceError(422, "Введите PSN пароль.")

            region_account["updated_at"] = current_time
            existing_accounts[normalized_region] = region_account

            update_fields = {
                "psn_accounts": existing_accounts,
                "updated_at": current_time,
            }

            if normalized_region == "UA":
                update_fields["platform"] = region_account.get("platform")
                update_fields["psn_email"] = region_account.get("psn_email")

            self.users.update_one({"_id": resolved_user_id}, {"$set": update_fields})
            updated_user = self.users.find_one({"_id": resolved_user_id, "is_active": True})
            if not updated_user:
                raise AuthServiceError(404, "Профиль не найден после обновления.")
        except AuthServiceError:
            raise
        except PyMongoError as error:
            raise AuthServiceError(503, "MongoDB недоступна. Попробуйте позже.") from error

        return build_public_profile(updated_user)

    def _upsert_registration_user(
        self,
        *,
        payload: RegisterRequest,
        existing_user: Optional[dict[str, Any]],
        current_time: datetime,
        user_agent: Optional[str],
        ip_address: Optional[str],
    ) -> Any:
        fields_set = set(getattr(payload, "model_fields_set", set()))

        def pick_value(field_name: str, default: Any = None) -> Any:
            if field_name in fields_set:
                return getattr(payload, field_name)
            if existing_user is not None and field_name in existing_user:
                return existing_user.get(field_name)
            return getattr(payload, field_name, default)

        user_fields = {
            "email": payload.email,
            "email_normalized": payload.email,
            "password_hash": hash_password(payload.password),
            "username": pick_value("username"),
            "first_name": pick_value("first_name"),
            "last_name": pick_value("last_name"),
            "telegram_id": pick_value("telegram_id"),
            "role": resolve_site_user_role(
                existing_user.get("role") if existing_user else None,
                telegram_id=pick_value("telegram_id"),
            ),
            "preferred_region": pick_value("preferred_region", "UA") or "UA",
            "show_ukraine_prices": bool(pick_value("show_ukraine_prices", False)),
            "show_turkey_prices": bool(pick_value("show_turkey_prices", True)),
            "show_india_prices": bool(pick_value("show_india_prices", False)),
            "payment_email": pick_value("payment_email"),
            "platform": pick_value("platform"),
            "psn_email": pick_value("psn_email"),
            "psn_accounts": existing_user.get("psn_accounts", {}) if existing_user else {},
            "email_verified": False,
            "is_active": True,
            "updated_at": current_time,
            "last_registration_at": current_time,
            "registration_user_agent": user_agent,
            "registration_ip_address": ip_address,
        }

        if existing_user:
            self.users.update_one({"_id": existing_user["_id"]}, {"$set": user_fields})
            return existing_user["_id"]

        user_fields["created_at"] = current_time
        user_fields["last_login_at"] = None
        insert_result = self.users.insert_one(user_fields)
        return insert_result.inserted_id

    def _save_verification_and_send_email(
        self,
        *,
        email: str,
        verification_doc: dict[str, Any],
        code: str,
        previous_doc: Optional[dict[str, Any]],
    ) -> None:
        filter_query = {
            "email_normalized": verification_doc["email_normalized"],
            "purpose": verification_doc["purpose"],
        }
        self.codes.replace_one(filter_query, verification_doc, upsert=True)

        try:
            self.email_sender(email, code)
        except EmailDeliveryError as error:
            if previous_doc is not None:
                self.codes.replace_one(filter_query, previous_doc, upsert=True)
            else:
                self.codes.delete_one(filter_query)
            raise AuthServiceError(503, str(error)) from error

    def _find_social_user(
        self,
        *,
        provider: str,
        provider_id: str,
        email: Optional[str],
        telegram_id: Optional[int],
    ) -> Optional[dict[str, Any]]:
        if provider == "google":
            user_doc = self.users.find_one({"google_id": provider_id})
            if user_doc:
                return user_doc
        elif provider == "vk":
            user_doc = self.users.find_one({"vk_id": provider_id})
            if user_doc:
                return user_doc
        elif provider == "telegram" and telegram_id is not None:
            user_doc = self.users.find_one({"telegram_id": telegram_id})
            if user_doc:
                return user_doc

        if email:
            return self.users.find_one({"email_normalized": email.lower()})

        return None

    def _create_session(
        self,
        *,
        user_id: Any,
        user_agent: Optional[str],
        ip_address: Optional[str],
        current_time: datetime,
    ) -> str:
        session_token = generate_session_token()
        self.sessions.insert_one(
            {
                "user_id": user_id,
                "token_hash": hash_session_token(session_token),
                "created_at": current_time,
                "updated_at": current_time,
                "last_seen_at": current_time,
                "expires_at": current_time + timedelta(days=settings.AUTH_SESSION_TTL_DAYS),
                "user_agent": user_agent,
                "ip_address": ip_address,
            }
        )
        return session_token

    def _map_duplicate_key_error(self, error: DuplicateKeyError) -> AuthServiceError:
        error_text = str(error)
        if "telegram_id" in error_text:
            return AuthServiceError(409, "Этот Telegram ID уже привязан к другому аккаунту.")
        if "google_id" in error_text:
            return AuthServiceError(409, "Этот Google аккаунт уже привязан к другому профилю.")
        if "vk_id" in error_text:
            return AuthServiceError(409, "Этот VK аккаунт уже привязан к другому профилю.")
        return AuthServiceError(409, "Пользователь с такими данными уже существует.")


@lru_cache(maxsize=1)
def get_auth_service() -> AuthService:
    return AuthService()
