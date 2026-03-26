from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Product(Base):
    """Модель товара"""
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(255), nullable=True, comment='Категория товара')
    name = Column(String(500), nullable=True, comment='Название товара')
    image = Column(String(500), nullable=True, comment='Ссылка на изображение')
    trl_price_old = Column(Float, nullable=True, comment='Старая цена в лирах')
    trl_price = Column(Float, nullable=True, comment='Текущая цена в лирах')
    uah_price_old = Column(Float, nullable=True, comment='Старая цена в гривнах')
    uah_price = Column(Float, nullable=True, comment='Текущая цена в гривнах')
    discount_percent = Column(Float, nullable=True, comment='Процент скидки')
    publisher = Column(String(255), nullable=True, comment='Издатель')
    discount_end_date = Column(Date, nullable=True, comment='Дата окончания скидки')
    edition_release_date = Column(Date, nullable=True, comment='Дата выхода издания')
    description = Column(Text, nullable=True, comment='Описание товара')
    
    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', category='{self.category}')>"

# Функция для создания базы данных
def create_database(db_path='products.db'):
    """Создает базу данных SQLite"""
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)
    return engine

# Функция для создания сессии
def create_session(engine):
    """Создает сессию для работы с базой данных"""
    Session = sessionmaker(bind=engine)
    return Session() 