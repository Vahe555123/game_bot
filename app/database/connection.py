from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import settings

# Создание движка базы данных
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    } if "sqlite" in settings.DATABASE_URL else {},
)

if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

# Создание сессии
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()

def get_db():
    """Зависимость для получения сессии базы данных"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session():
    """Получение сессии базы данных как контекстный менеджер"""
    from contextlib import contextmanager
    
    @contextmanager
    def session_context():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    return session_context()

def create_tables():
    """Создание всех таблиц в базе данных"""
    # Импортируем все модели чтобы они были зарегистрированы
    from app.models.user import User
    from app.models.product import Product
    from app.models.favorite import UserFavoriteProduct
    from app.models.currency_rate import CurrencyRate
    
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы базы данных созданы/обновлены")

def init_database():
    """Инициализация базы данных с начальными данными"""
    create_tables() 