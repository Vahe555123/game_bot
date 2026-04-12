from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.connection import Base
from app.utils.time import utcnow

class UserFavoriteProduct(Base):
    """Модель избранных товаров пользователя"""
    __tablename__ = 'user_favorite_products'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    product_id = Column(String(100), ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    region = Column(String(10), nullable=True, comment='Регион товара (UA, TR, IN)')
    created_at = Column(DateTime, default=utcnow, comment='Дата добавления в избранное')

    # Связи с другими таблицами
    user = relationship("User", back_populates="favorite_products")
    product = relationship(
        "Product",
        back_populates="favorited_by",
        primaryjoin="and_(UserFavoriteProduct.product_id == Product.id, UserFavoriteProduct.region == Product.region)",
    )

    # Уникальное ограничение: один пользователь может добавить товар в избранное только один раз
    __table_args__ = (UniqueConstraint('user_id', 'product_id', name='unique_user_product_favorite'),)

    def __repr__(self):
        return f"<UserFavoriteProduct(user_id={self.user_id}, product_id={self.product_id})>"
