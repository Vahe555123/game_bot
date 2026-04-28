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


def normalize_required_text(value: str, *, field_name: str) -> str:
    cleaned = normalize_optional_text(value)
    if not cleaned:
        raise ValueError(f"Укажите {field_name}")
    return cleaned


class HelpContentSection(BaseModel):
    title: str = Field(..., max_length=160)
    body: str = Field(..., max_length=4000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return normalize_required_text(value, field_name="заголовок блока")

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        return normalize_required_text(value, field_name="описание блока")


class HelpContentFaqItem(BaseModel):
    question: str = Field(..., max_length=240)
    answer: str = Field(..., max_length=4000)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        return normalize_required_text(value, field_name="вопрос")

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        return normalize_required_text(value, field_name="ответ")


class HelpSocialLink(BaseModel):
    label: str = Field(..., max_length=80)
    url: str = Field(..., max_length=500)

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        return normalize_required_text(value, field_name="название ссылки")

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return normalize_required_text(value, field_name="ссылку")


class HelpContentBase(BaseModel):
    eyebrow: str = Field("Помощь", max_length=40)
    title: str = Field(..., max_length=160)
    subtitle: str = Field(..., max_length=1200)
    support_title: str = Field(..., max_length=120)
    support_description: str = Field(..., max_length=1000)
    support_button_label: str = Field(..., max_length=80)
    support_button_url: Optional[str] = Field(None, max_length=500)
    purchases_title: str = Field(..., max_length=120)
    purchases_description: str = Field(..., max_length=1000)
    purchases_button_label: str = Field(..., max_length=80)
    purchases_button_url: Optional[str] = Field(None, max_length=500)
    social_links: list[HelpSocialLink] = Field(default_factory=list, max_length=8)
    sections: list[HelpContentSection] = Field(default_factory=list, max_length=12)
    faq_items: list[HelpContentFaqItem] = Field(default_factory=list, max_length=24)

    @field_validator(
        "eyebrow",
        "title",
        "subtitle",
        "support_title",
        "support_description",
        "support_button_label",
        "purchases_title",
        "purchases_description",
        "purchases_button_label",
    )
    @classmethod
    def validate_required_text_fields(cls, value: str) -> str:
        return normalize_required_text(value, field_name="текст")

    @field_validator("support_button_url", "purchases_button_url")
    @classmethod
    def validate_optional_url_fields(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_text(value)


class AdminHelpContentUpdateRequest(HelpContentBase):
    pass


class AdminHelpContentResponse(HelpContentBase):
    updated_at: Optional[datetime] = None


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
    favorites_count: int = 0
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


class AdminProductFavoriteRecord(BaseModel):
    id: int
    user_id: int
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    preferred_region: Optional[str] = None
    payment_email: Optional[str] = None
    platform: Optional[str] = None
    psn_email: Optional[str] = None
    region: Optional[str] = None
    is_active: bool = False
    favorited_at: Optional[datetime] = None


class AdminProductDetailsResponse(AdminProductRecord):
    regional_products: list[AdminProductRecord] = Field(default_factory=list)
    favorites: list[AdminProductFavoriteRecord] = Field(default_factory=list)
    available_regions: list[str] = Field(default_factory=list)
    missing_regions: list[str] = Field(default_factory=list)
    favorites_by_region: dict[str, int] = Field(default_factory=dict)
    regional_rows_total: int = 0
    favorite_users_total: int = 0


class AdminProductListResponse(BaseModel):
    products: list[AdminProductRecord] = Field(default_factory=list)
    total: int
    page: int
    limit: int


class AdminFavoriteDiscountNotificationSummary(BaseModel):
    candidates: int = 0
    sent: int = 0
    email_sent: int = 0
    telegram_sent: int = 0
    skipped_existing: int = 0
    no_recipient: int = 0
    failed: int = 0


class AdminFavoriteDiscountNotificationResponse(BaseModel):
    message: str
    discounted_products: int = 0
    force_resend: bool = False
    summary: AdminFavoriteDiscountNotificationSummary = Field(
        default_factory=AdminFavoriteDiscountNotificationSummary
    )


class AdminProductManualParseRequest(BaseModel):
    ua_url: Optional[str] = Field(None, max_length=1000)
    tr_url: Optional[str] = Field(None, max_length=1000)
    in_url: Optional[str] = Field(None, max_length=1000)
    save_to_db: bool = True

    @field_validator("ua_url", "tr_url", "in_url")
    @classmethod
    def normalize_urls(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_any_url(self) -> "AdminProductManualParseRequest":
        if not self.ua_url and not self.tr_url and not self.in_url:
            raise ValueError("Укажите хотя бы одну ссылку")
        return self


class AdminProductManualParseRecord(BaseModel):
    id: Optional[str] = None
    region: Optional[str] = None
    name: Optional[str] = None
    main_name: Optional[str] = None
    edition: Optional[str] = None
    price_rub: Optional[float] = None
    price_rub_region: Optional[str] = None
    localization: Optional[str] = None


class AdminProductManualParseResponse(BaseModel):
    message: str
    parsed_total: int
    final_total: int
    updated_count: int
    added_count: int
    duplicates_removed: int
    result_count: int
    db_updated: bool
    errors: list[str] = Field(default_factory=list)
    records: list[AdminProductManualParseRecord] = Field(default_factory=list)


class AdminProductManualParseStartResponse(BaseModel):
    task_id: str
    status: str
    message: str


class AdminProductManualParseStatusResponse(BaseModel):
    task_id: str
    status: str
    message: str
    result: Optional[AdminProductManualParseResponse] = None


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
