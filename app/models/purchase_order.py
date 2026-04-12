from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.database.connection import Base
from app.utils.time import utcnow


class SitePurchaseOrder(Base):
    __tablename__ = "site_purchase_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_number = Column(String(32), unique=True, nullable=False, index=True)

    site_user_id = Column(String(64), nullable=False, index=True)
    user_email = Column(String(255), nullable=True, index=True)
    user_display_name = Column(String(255), nullable=True)

    product_id = Column(Text, nullable=False, index=True)
    product_region = Column(String(10), nullable=False, index=True)
    product_name = Column(Text, nullable=False)
    product_image = Column(Text, nullable=True)
    product_platforms = Column(String(255), nullable=True)

    currency_code = Column(String(16), nullable=False)
    local_price = Column(Float, nullable=False)
    price_rub = Column(Float, nullable=False)
    use_ps_plus = Column(Boolean, default=False, nullable=False)

    payment_email = Column(String(255), nullable=True)
    psn_email = Column(String(255), nullable=True)
    platform = Column(String(32), nullable=True)

    payment_provider = Column(String(32), nullable=False)
    payment_type = Column(String(32), nullable=False)
    payment_url = Column(Text, nullable=False)
    payment_metadata_json = Column(Text, nullable=True)

    status = Column(String(32), default="payment_pending", nullable=False, index=True)
    status_note = Column(Text, nullable=True)
    manager_contact_url = Column(Text, nullable=True)

    delivery_title = Column(String(255), nullable=True)
    delivery_message = Column(Text, nullable=True)
    delivery_items_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    payment_submitted_at = Column(DateTime, nullable=True)
    fulfilled_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<SitePurchaseOrder(order_number={self.order_number}, product_id={self.product_id}, status={self.status})>"

    @staticmethod
    def _loads(value: str | None, *, default: Any) -> Any:
        if not value:
            return default

        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _dumps(value: Any) -> str | None:
        if value in (None, "", [], {}):
            return None
        return json.dumps(value, ensure_ascii=False)

    def get_payment_metadata(self) -> dict[str, Any]:
        return self._loads(self.payment_metadata_json, default={})

    def set_payment_metadata(self, value: dict[str, Any] | None) -> None:
        self.payment_metadata_json = self._dumps(value)

    def get_delivery_items(self) -> list[dict[str, str]]:
        return self._loads(self.delivery_items_json, default=[])

    def set_delivery_items(self, value: list[dict[str, str]] | None) -> None:
        self.delivery_items_json = self._dumps(value)
