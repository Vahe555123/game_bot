from __future__ import annotations

import json
from typing import Iterable, Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.auth.security import hash_password, verify_password
from app.database.connection import Base
from app.utils.encryption import decrypt_password, encrypt_password
from app.utils.time import utcnow


class User(Base):
    """Unified user account stored in SQLite."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    telegram_id = Column(Integer, unique=True, nullable=True, index=True)
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    vk_id = Column(String(255), unique=True, nullable=True, index=True)

    email = Column(String(255), unique=True, nullable=True, index=True)
    email_normalized = Column(String(255), unique=True, nullable=True, index=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    password_hash = Column(Text, nullable=True)

    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    preferred_region = Column(String(10), default="UA", nullable=False)
    show_ukraine_prices = Column(Boolean, default=False, nullable=False)
    show_turkey_prices = Column(Boolean, default=True, nullable=False)
    show_india_prices = Column(Boolean, default=False, nullable=False)
    payment_email = Column(String(255), nullable=True)
    platform = Column(String(50), nullable=True)
    psn_email = Column(String(255), nullable=True)
    psn_password_hash = Column(Text, nullable=True)
    psn_password_salt = Column(String(32), nullable=True)

    role = Column(String(32), default="client", nullable=False, index=True)
    auth_providers_json = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_registration_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    registration_user_agent = Column(String(255), nullable=True)
    registration_ip_address = Column(String(64), nullable=True)
    login_user_agent = Column(String(255), nullable=True)
    login_ip_address = Column(String(64), nullable=True)

    favorite_products = relationship("UserFavoriteProduct", back_populates="user", cascade="all, delete-orphan")
    psn_accounts = relationship("PSNAccount", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, email={self.email!r})>"

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.last_name]
        return " ".join(part for part in parts if part) or self.username or self.email or f"User {self.id}"

    @property
    def auth_providers(self) -> list[str]:
        return self.get_auth_providers()

    @auth_providers.setter
    def auth_providers(self, value: Iterable[str] | None) -> None:
        self.set_auth_providers(value)

    def get_auth_providers(self) -> list[str]:
        if not self.auth_providers_json:
            return []
        try:
            data = json.loads(self.auth_providers_json)
        except (TypeError, ValueError):
            return []
        if isinstance(data, list):
            return [str(item) for item in data if str(item).strip()]
        return []

    def set_auth_providers(self, value: Iterable[str] | None) -> None:
        if not value:
            self.auth_providers_json = json.dumps([], ensure_ascii=False)
            return
        normalized = []
        seen = set()
        for item in value:
            provider = str(item).strip().lower()
            if not provider or provider in seen:
                continue
            seen.add(provider)
            normalized.append(provider)
        self.auth_providers_json = json.dumps(normalized, ensure_ascii=False)

    def set_password(self, password: Optional[str]) -> None:
        if not password:
            self.password_hash = None
            return
        self.password_hash = hash_password(password)

    def verify_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return verify_password(password, self.password_hash)

    @property
    def has_password(self) -> bool:
        return bool(self.password_hash)

    def get_enabled_regions(self) -> list[str]:
        regions = []
        if self.show_ukraine_prices:
            regions.append("UA")
        if self.show_turkey_prices:
            regions.append("TR")
        if self.show_india_prices:
            regions.append("IN")
        return regions or ["TR"]

    def get_preferred_region_info(self) -> dict[str, str]:
        region_map = {
            "TR": {"code": "TRY", "symbol": "₺", "flag": "🇹🇷", "name": "Турция"},
            "UA": {"code": "UAH", "symbol": "₴", "flag": "🇺🇦", "name": "Украина"},
            "IN": {"code": "INR", "symbol": "₹", "flag": "🇮🇳", "name": "Индия"},
        }
        return region_map.get((self.preferred_region or "UA").upper(), region_map["UA"])

    def set_psn_password(self, password: Optional[str]) -> None:
        if not password:
            self.psn_password_hash = None
            self.psn_password_salt = None
            return
        encrypted_password, salt = encrypt_password(password)
        self.psn_password_hash = encrypted_password
        self.psn_password_salt = salt

    def verify_psn_password(self, password: str) -> bool:
        if not self.psn_password_hash or not self.psn_password_salt:
            return False
        return verify_password(password, self.psn_password_hash, self.psn_password_salt)

    def get_psn_password(self) -> str:
        if not self.psn_password_hash or not self.psn_password_salt:
            return ""
        return decrypt_password(self.psn_password_hash, self.psn_password_salt)

    @property
    def has_psn_credentials(self) -> bool:
        return bool(self.psn_email and self.psn_password_hash)

    def get_psn_account_for_region(self, region: str):
        normalized_region = (region or "").upper()
        for account in self.psn_accounts:
            if account.region == normalized_region and account.is_active:
                return account
        return None

    def has_psn_credentials_for_region(self, region: str) -> bool:
        account = self.get_psn_account_for_region(region)
        return bool(account and account.has_credentials)

    def get_all_psn_accounts(self) -> list:
        return [account for account in self.psn_accounts if account.is_active]
