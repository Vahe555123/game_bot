from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.connection import Base

class CurrencyRate(Base):
    """Модель курсов валют с диапазонами цен"""
    __tablename__ = 'currency_rates'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    currency_from = Column(String(10), nullable=False, comment='Исходная валюта (UAH, TRL)')
    currency_to = Column(String(10), default='RUB', comment='Целевая валюта (всегда RUB)')
    
    # Диапазон цен для применения курса
    price_min = Column(Float, nullable=False, comment='Минимальная цена диапазона')
    price_max = Column(Float, nullable=True, comment='Максимальная цена диапазона (NULL = без ограничений)')
    
    # Курс конвертации
    rate = Column(Float, nullable=False, comment='Курс конвертации')
    
    # Метаданные
    is_active = Column(Boolean, default=True, comment='Активен ли курс')
    created_at = Column(DateTime, default=datetime.utcnow, comment='Дата создания')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='Дата обновления')
    created_by = Column(Integer, nullable=True, comment='ID администратора, создавшего курс')
    
    # Дополнительная информация
    description = Column(Text, nullable=True, comment='Описание курса')
    
    def __repr__(self):
        price_range = f"{self.price_min}-{self.price_max or '∞'}"
        return f"<CurrencyRate({self.currency_from}→{self.currency_to}, {price_range}: {self.rate})>"
    
    @classmethod
    def get_rate_for_price(cls, db, currency_from: str, price: float, currency_to: str = 'RUB'):
        """Получить курс для конкретной цены"""
        currency_aliases = {
            'TRY': ['TRY', 'TRL'],
            'TRL': ['TRL', 'TRY'],
        }

        currency_from_candidates = currency_aliases.get(currency_from, [currency_from])

        rate = db.query(cls).filter(
            cls.currency_from.in_(currency_from_candidates),
            cls.currency_to == currency_to,
            cls.is_active == True,
            cls.price_min <= price,
            (cls.price_max >= price) | (cls.price_max.is_(None))
        ).order_by(cls.price_min.desc()).first()
        
        return rate.rate if rate else 1.0
    
    @property
    def price_range_display(self):
        """Отображение диапазона цен"""
        if self.price_max:
            return f"{self.price_min:.0f} - {self.price_max:.0f}"
        else:
            return f"{self.price_min:.0f}+"
    
    def convert_price(self, price: float) -> float:
        """Конвертировать цену по этому курсу"""
        return price * self.rate