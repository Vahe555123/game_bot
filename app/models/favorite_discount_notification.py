from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.connection import Base
from app.utils.time import utcnow


class FavoriteDiscountNotification(Base):
    """Delivery history for favorite-product discount alerts."""

    __tablename__ = "favorite_discount_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String(100), nullable=False, index=True)
    region = Column(String(10), nullable=True, index=True)
    discount_signature = Column(String(128), nullable=False, index=True)
    channel = Column(String(32), nullable=False)
    recipient = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="sent", index=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    user = relationship("User")

    __table_args__ = (
        Index(
            "idx_favorite_discount_sent_lookup",
            "user_id",
            "product_id",
            "discount_signature",
            "status",
        ),
    )
