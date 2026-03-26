from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database.connection import Base
from datetime import datetime

class Localization(Base):
    """Модель для уровней локализации"""
    __tablename__ = 'localizations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, comment='Код локализации (full, interface, subtitles, none)')
    name_ru = Column(String(255), nullable=False, comment='Название на русском')
    name_en = Column(String(255), nullable=False, comment='Название на английском')
    description = Column(Text, nullable=True, comment='Описание уровня локализации')
    created_at = Column(DateTime, default=datetime.utcnow, comment='Дата создания')

    def to_dict(self):
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'code': self.code,
            'name_ru': self.name_ru,
            'name_en': self.name_en,
            'description': self.description
        }
