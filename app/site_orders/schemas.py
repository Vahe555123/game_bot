from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.auth.schemas import normalize_email, normalize_optional_text


ALLOWED_PURCHASE_REGIONS = {"UA", "TR", "IN"}


def normalize_purchase_region(value: str) -> str:
    normalized = (value or "").strip().upper()
    aliases = {
        "EN-UA": "UA",
        "UAH": "UA",
        "EN-TR": "TR",
        "TRY": "TR",
        "EN-IN": "IN",
        "INR": "IN",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in ALLOWED_PURCHASE_REGIONS:
        raise ValueError("Недопустимый регион покупки")
    return normalized


class DeliveryItem(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    value: str = Field(..., min_length=1, max_length=4000)

    @field_validator("label", "value")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Поле не может быть пустым")
        return cleaned


class PurchaseCheckoutRequest(BaseModel):
    product_id: str = Field(..., min_length=1)
    region: str = Field(..., description="UA, TR или IN")
    use_ps_plus: bool = Field(False, description="Использовать цену PS Plus")
    purchase_email: Optional[str] = Field(None, description="Email для покупки, если он не заполнен в профиле")
    psn_email: Optional[str] = Field(None, description="PSN Email для UA-региона")
    psn_password: Optional[str] = Field(None, description="PSN пароль для UA-региона")
    backup_code: Optional[str] = Field(None, description="Резервный код 2FA для UA-региона")

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Не указан product_id")
        return cleaned

    @field_validator("region")
    @classmethod
    def validate_region(cls, value: str) -> str:
        return normalize_purchase_region(value)

    @field_validator("purchase_email", "psn_email")
    @classmethod
    def validate_optional_emails(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        return normalize_email(cleaned)

    @field_validator("psn_password", "backup_code")
    @classmethod
    def validate_optional_text_fields(cls, value: Optional[str]) -> Optional[str]:
        return normalize_optional_text(value)


class PurchaseActionResponse(BaseModel):
    message: str


class PurchaseDeliveryResponse(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    items: list[DeliveryItem] = Field(default_factory=list)


class PurchaseOrderResponse(BaseModel):
    order_number: str
    status: str
    status_label: str
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
    delivery: Optional[PurchaseDeliveryResponse] = None
    created_at: datetime
    updated_at: datetime
    payment_submitted_at: Optional[datetime] = None
    fulfilled_at: Optional[datetime] = None


class PurchaseListResponse(BaseModel):
    orders: list[PurchaseOrderResponse] = Field(default_factory=list)


class AdminFulfillPurchaseRequest(BaseModel):
    delivery_title: Optional[str] = Field(None, max_length=255)
    delivery_message: Optional[str] = Field(None, max_length=10000)
    delivery_items: list[DeliveryItem] = Field(default_factory=list)
    status_note: Optional[str] = Field(None, max_length=2000)
    send_email: bool = True

    @field_validator("delivery_title", "delivery_message", "status_note")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class AdminPurchaseListResponse(BaseModel):
    orders: list[PurchaseOrderResponse] = Field(default_factory=list)
    total: int
