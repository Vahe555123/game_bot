from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.auth.schemas import (
    SiteUserPublic,
    normalize_email,
    normalize_optional_text,
    normalize_platform,
    normalize_region,
    normalize_site_user_role,
)
from app.site_orders.schemas import DeliveryItem
from config.settings import settings

ADMIN_PURCHASE_STATUSES = {
    "payment_pending",
    "payment_review",
    "fulfilled",
    "cancelled",
}


def normalize_optional_email(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None
    return normalize_email(cleaned)


def normalize_optional_status(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    normalized = value.strip().lower()
    if not normalized:
        return None

    if normalized not in ADMIN_PURCHASE_STATUSES:
        raise ValueError("Недопустимый статус заказа")

    return normalized


def normalize_optional_bool_flag(value: Optional[bool]) -> Optional[bool]:
    if value is None:
        return None
    return bool(value)


class AdminUserRecord(SiteUserPublic):
    is_env_admin: bool = False
    purchase_count: int = 0
    total_spent_rub: float = 0.0


class AdminUserListResponse(BaseModel):
    users: list[AdminUserRecord] = Field(default_factory=list)
    total: int
    page: int
    limit: int


class AdminUserCreateRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=settings.AUTH_PASSWORD_MIN_LENGTH)
    email_verified: bool = False
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    telegram_id: Optional[int] = None
    preferred_region: str = "TR"
    payment_email: Optional[str] = None
    platform: Optional[str] = None
    psn_email: Optional[str] = None
    role: str = "client"
    is_active: bool = True

    @field_validator("email", "payment_email", "psn_email")
    @classmethod
    def validate_optional_emails(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_email(value)

    @field_validator("username", "first_name", "last_name")
    @classmethod
    def validate_optional_text_fields(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_text(value)

    @field_validator("preferred_region")
    @classmethod
    def validate_region(cls, value: str) -> str:
        return normalize_region(value)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: Optional[str]) -> Optional[str]:
        return normalize_platform(value)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        return normalize_site_user_role(value)

    @model_validator(mode="after")
    def validate_identity(self) -> "AdminUserCreateRequest":
        if not self.email and self.telegram_id is None:
            raise ValueError("Укажите email или Telegram ID пользователя")

        if self.email and not self.password and not self.telegram_id:
            raise ValueError("Для пользователя с email укажите пароль или Telegram ID")

        return self


class AdminUserUpdateRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=settings.AUTH_PASSWORD_MIN_LENGTH)
    email_verified: Optional[bool] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    telegram_id: Optional[int] = None
    preferred_region: Optional[str] = None
    payment_email: Optional[str] = None
    platform: Optional[str] = None
    psn_email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("email", "payment_email", "psn_email")
    @classmethod
    def validate_optional_emails(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_email(value)

    @field_validator("username", "first_name", "last_name", "password")
    @classmethod
    def validate_optional_text_fields(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_text(value)

    @field_validator("preferred_region")
    @classmethod
    def validate_region(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_region(value)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: Optional[str]) -> Optional[str]:
        return normalize_platform(value)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_site_user_role(value)

    @field_validator("is_active", "email_verified")
    @classmethod
    def validate_flags(cls, value: Optional[bool]) -> Optional[bool]:
        return normalize_optional_bool_flag(value)


class AdminActionResponse(BaseModel):
    message: str


class AdminProductRecord(BaseModel):
    id: str
    region: str
    display_name: str
    name: Optional[str] = None
    main_name: Optional[str] = None
    category: Optional[str] = None
    type: Optional[str] = None
    image: Optional[str] = None
    search_names: Optional[str] = None
    platforms: Optional[str] = None
    publisher: Optional[str] = None
    localization: Optional[str] = None
    rating: Optional[float] = None
    edition: Optional[str] = None
    price: Optional[float] = None
    old_price: Optional[float] = None
    ps_price: Optional[float] = None
    ea_price: Optional[float] = None
    price_uah: Optional[float] = None
    old_price_uah: Optional[float] = None
    price_try: Optional[float] = None
    old_price_try: Optional[float] = None
    price_inr: Optional[float] = None
    old_price_inr: Optional[float] = None
    ps_plus_price_uah: Optional[float] = None
    ps_plus_price_try: Optional[float] = None
    ps_plus_price_inr: Optional[float] = None
    plus_types: Optional[str] = None
    ps_plus: bool = False
    ea_access: Optional[str] = None
    ps_plus_collection: Optional[str] = None
    discount: Optional[float] = None
    discount_end: Optional[str] = None
    tags: Optional[str] = None
    description: Optional[str] = None
    compound: Optional[str] = None
    info: Optional[str] = None
    players_min: Optional[int] = None
    players_max: Optional[int] = None
    players_online: bool = False
    has_discount: bool = False
    has_ps_plus: bool = False
    has_ea_access: bool = False


class AdminProductListResponse(BaseModel):
    products: list[AdminProductRecord] = Field(default_factory=list)
    total: int
    page: int
    limit: int


class AdminProductBasePayload(BaseModel):
    category: Optional[str] = None
    type: Optional[str] = None
    name: Optional[str] = None
    main_name: Optional[str] = None
    search_names: Optional[str] = None
    image: Optional[str] = None
    compound: Optional[str] = None
    platforms: Optional[str] = None
    publisher: Optional[str] = None
    localization: Optional[str] = None
    rating: Optional[float] = None
    info: Optional[str] = None
    edition: Optional[str] = None
    price: Optional[float] = None
    old_price: Optional[float] = None
    ps_price: Optional[float] = None
    ea_price: Optional[float] = None
    price_uah: Optional[float] = None
    old_price_uah: Optional[float] = None
    price_try: Optional[float] = None
    old_price_try: Optional[float] = None
    price_inr: Optional[float] = None
    old_price_inr: Optional[float] = None
    ps_plus_price_uah: Optional[float] = None
    ps_plus_price_try: Optional[float] = None
    ps_plus_price_inr: Optional[float] = None
    plus_types: Optional[str] = None
    ps_plus: Optional[bool] = None
    ea_access: Optional[str] = None
    ps_plus_collection: Optional[str] = None
    discount: Optional[float] = None
    discount_end: Optional[str] = None
    tags: Optional[str] = None
    description: Optional[str] = None
    players_min: Optional[int] = None
    players_max: Optional[int] = None
    players_online: Optional[bool] = None

    @field_validator(
        "category",
        "type",
        "name",
        "main_name",
        "search_names",
        "image",
        "compound",
        "platforms",
        "publisher",
        "localization",
        "info",
        "edition",
        "plus_types",
        "ea_access",
        "ps_plus_collection",
        "discount_end",
        "tags",
        "description",
        mode="before",
    )
    @classmethod
    def normalize_text_fields(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_text(value)

    @field_validator("ps_plus", "players_online")
    @classmethod
    def normalize_boolean_fields(cls, value: Optional[bool]) -> Optional[bool]:
        return normalize_optional_bool_flag(value)


class AdminProductCreateRequest(AdminProductBasePayload):
    id: str = Field(..., min_length=1)
    region: str

    @field_validator("id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Укажите ID товара")
        return cleaned

    @field_validator("region")
    @classmethod
    def validate_region(cls, value: str) -> str:
        return normalize_region(value)


class AdminProductUpdateRequest(AdminProductBasePayload):
    pass


class AdminPurchaseRecord(BaseModel):
    order_number: str
    status: str
    status_label: str
    site_user_id: str
    user_email: Optional[str] = None
    user_display_name: Optional[str] = None
    product_id: str
    product_name: str
    product_region: str
    product_image: Optional[str] = None
    product_platforms: Optional[str] = None
    currency_code: str
    local_price: float
    price_rub: float
    use_ps_plus: bool
    payment_email: Optional[str] = None
    psn_email: Optional[str] = None
    platform: Optional[str] = None
    payment_provider: str
    payment_type: str
    payment_url: Optional[str] = None
    payment_metadata: dict = Field(default_factory=dict)
    manager_contact_url: Optional[str] = None
    status_note: Optional[str] = None
    delivery: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    payment_submitted_at: Optional[datetime] = None
    fulfilled_at: Optional[datetime] = None


class AdminPurchaseListResponse(BaseModel):
    orders: list[AdminPurchaseRecord] = Field(default_factory=list)
    total: int
    page: int
    limit: int


class AdminPurchaseUpdateRequest(BaseModel):
    status: Optional[str] = None
    status_note: Optional[str] = None
    manager_contact_url: Optional[str] = None
    payment_url: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_status(value)

    @field_validator("status_note", "manager_contact_url", "payment_url")
    @classmethod
    def validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_text(value)


class AdminPurchaseFulfillRequest(BaseModel):
    delivery_title: Optional[str] = Field(None, max_length=255)
    delivery_message: Optional[str] = Field(None, max_length=10000)
    delivery_items: list[DeliveryItem] = Field(default_factory=list)
    status_note: Optional[str] = Field(None, max_length=2000)
    send_email: bool = True

    @field_validator("delivery_title", "delivery_message", "status_note")
    @classmethod
    def validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_text(value)


class AdminUserSummary(BaseModel):
    total: int
    active: int
    verified: int
    admins: int
    clients: int


class AdminProductSummary(BaseModel):
    total_rows: int
    unique_products: int
    discounted: int
    with_ps_plus: int
    regions: dict[str, int] = Field(default_factory=dict)


class AdminPurchaseSummary(BaseModel):
    total: int
    total_revenue_rub: float
    fulfilled_revenue_rub: float
    statuses: dict[str, int] = Field(default_factory=dict)


class AdminDashboardResponse(BaseModel):
    users: AdminUserSummary
    products: AdminProductSummary
    purchases: AdminPurchaseSummary
    recent_users: list[AdminUserRecord] = Field(default_factory=list)
    recent_orders: list[AdminPurchaseRecord] = Field(default_factory=list)
