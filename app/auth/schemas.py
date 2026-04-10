import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from config.settings import settings

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ALLOWED_REGIONS = {"UA", "TR", "IN"}
ALLOWED_PLATFORMS = {"PS4", "PS5"}
ALLOWED_SITE_USER_ROLES = {"client", "admin"}


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized or not EMAIL_PATTERN.match(normalized):
        raise ValueError("Введите корректный email")
    return normalized


def normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_region(value: Optional[str]) -> str:
    normalized = (value or "UA").strip().upper()
    if normalized not in ALLOWED_REGIONS:
        raise ValueError("Недопустимый регион")
    return normalized


def normalize_platform(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    normalized = value.strip().upper()
    if not normalized:
        return None

    if normalized not in ALLOWED_PLATFORMS:
        raise ValueError("Недопустимая платформа")

    return normalized


def normalize_site_user_role(value: Optional[str]) -> str:
    normalized = (value or "client").strip().lower()
    if normalized not in ALLOWED_SITE_USER_ROLES:
        raise ValueError("Недопустимая роль пользователя")
    return normalized


class RegisterRequest(BaseModel):
    email: str = Field(..., description="Email пользователя")
    password: str = Field(
        ...,
        min_length=settings.AUTH_PASSWORD_MIN_LENGTH,
        description="Пароль пользователя",
    )
    username: Optional[str] = Field(None, description="Username пользователя")
    first_name: Optional[str] = Field(None, description="Имя пользователя")
    last_name: Optional[str] = Field(None, description="Фамилия пользователя")
    telegram_id: Optional[int] = Field(None, description="Telegram ID для будущей привязки")
    preferred_region: str = Field("UA", description="Предпочитаемый регион")
    show_ukraine_prices: bool = Field(False, description="Показывать цены Украины")
    show_turkey_prices: bool = Field(True, description="Показывать цены Турции")
    show_india_prices: bool = Field(False, description="Показывать цены Индии")
    payment_email: Optional[str] = Field(None, description="Email для покупок")
    platform: Optional[str] = Field(None, description="PlayStation платформа")
    psn_email: Optional[str] = Field(None, description="Email для PSN аккаунта")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("payment_email", "psn_email")
    @classmethod
    def validate_optional_emails(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_email(value)

    @field_validator("username", "first_name", "last_name")
    @classmethod
    def normalize_text_fields(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_text(value)

    @field_validator("preferred_region")
    @classmethod
    def validate_region(cls, value: str) -> str:
        return normalize_region(value)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: Optional[str]) -> Optional[str]:
        return normalize_platform(value)


class VerifyEmailRequest(BaseModel):
    email: str = Field(..., description="Email пользователя")
    code: str = Field(..., min_length=6, max_length=6, description="Код подтверждения")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        code = value.strip()
        if not code.isdigit():
            raise ValueError("Код должен состоять из 6 цифр")
        return code


class ResendCodeRequest(BaseModel):
    email: str = Field(..., description="Email пользователя")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class PasswordResetConfirmRequest(BaseModel):
    email: str = Field(..., description="Email пользователя")
    code: str = Field(..., min_length=6, max_length=6, description="Код подтверждения")
    new_password: str = Field(
        ...,
        min_length=settings.AUTH_PASSWORD_MIN_LENGTH,
        description="Новый пароль пользователя",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        code = value.strip()
        if not code.isdigit():
            raise ValueError("Код должен состоять из 6 цифр")
        return code


class LoginRequest(BaseModel):
    email: str = Field(..., description="Email пользователя")
    password: str = Field(..., min_length=1, description="Пароль пользователя")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class AuthActionResponse(BaseModel):
    message: str
    resend_available_in: Optional[int] = None


class AuthProvidersResponse(BaseModel):
    google_enabled: bool
    vk_enabled: bool
    telegram_enabled: bool
    telegram_bot_username: Optional[str] = None


class SiteUserPublic(BaseModel):
    id: str
    email: Optional[str] = None
    email_verified: bool
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    telegram_id: Optional[int] = None
    preferred_region: str
    show_ukraine_prices: bool
    show_turkey_prices: bool
    show_india_prices: bool
    payment_email: Optional[str] = None
    platform: Optional[str] = None
    psn_email: Optional[str] = None
    role: str = "client"
    is_admin: bool = False
    is_active: bool
    auth_providers: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None


class SitePSNAccountPublic(BaseModel):
    region: str
    platform: Optional[str] = None
    psn_email: Optional[str] = None
    has_password: bool = False
    has_backup_code: bool = False
    updated_at: Optional[datetime] = None


class SiteProfileResponse(BaseModel):
    user: SiteUserPublic
    psn_accounts: dict[str, SitePSNAccountPublic] = Field(default_factory=dict)


class SiteProfilePreferencesUpdateRequest(BaseModel):
    preferred_region: str = Field(..., description="Выбранный регион каталога")
    payment_email: Optional[str] = Field(None, description="Email для покупки")

    @field_validator("preferred_region")
    @classmethod
    def validate_region(cls, value: str) -> str:
        return normalize_region(value)

    @field_validator("payment_email")
    @classmethod
    def validate_payment_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_email(value)


class SitePSNAccountUpdateRequest(BaseModel):
    platform: Optional[str] = Field(None, description="Платформа PlayStation")
    psn_email: Optional[str] = Field(None, description="PSN email")
    psn_password: Optional[str] = Field(None, description="PSN пароль")
    backup_code: Optional[str] = Field(None, description="Резервный код 2FA")

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: Optional[str]) -> Optional[str]:
        return normalize_platform(value)

    @field_validator("psn_email")
    @classmethod
    def validate_psn_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_email(value)

    @field_validator("psn_password", "backup_code")
    @classmethod
    def normalize_sensitive_values(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_text(value)


class TelegramAuthRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    allows_write_to_pm: Optional[bool] = None
    auth_date: int
    hash: str

    @field_validator("first_name", "last_name", "username", "photo_url")
    @classmethod
    def normalize_optional_strings(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_text(value)


class AuthUserResponse(BaseModel):
    user: SiteUserPublic
