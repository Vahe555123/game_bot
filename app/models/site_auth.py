from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database.connection import Base
from app.utils.time import utcnow


class SiteAuthCode(Base):
    __tablename__ = "site_auth_codes"
    __table_args__ = (UniqueConstraint("email_normalized", "purpose", name="uix_site_auth_codes_email_purpose"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email_normalized = Column(String(255), nullable=False, index=True)
    purpose = Column(String(32), nullable=False, index=True)
    salt = Column(String(32), nullable=False)
    code_hash = Column(String(128), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_sent_at = Column(DateTime, nullable=False)
    resend_available_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User")


class SiteAuthSession(Base):
    __tablename__ = "site_auth_sessions"
    __table_args__ = (UniqueConstraint("session_token_hash", name="uix_site_auth_sessions_token_hash"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token_hash = Column(String(128), nullable=False, unique=True, index=True)
    provider = Column(String(32), nullable=False, default="email")
    user_agent = Column(String(255), nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User")

    @property
    def is_active(self) -> bool:
        now = utcnow()
        return self.revoked_at is None and self.expires_at > now


class SiteContent(Base):
    __tablename__ = "site_content"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_key = Column(String(64), nullable=False, unique=True, index=True)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def get_payload(self) -> dict[str, Any]:
        try:
            data = json.loads(self.payload_json)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def set_payload(self, payload: dict[str, Any]) -> None:
        self.payload_json = json.dumps(payload, ensure_ascii=False)
