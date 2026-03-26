#!/usr/bin/env python3
"""
Скрипт миграции базы данных для добавления поддержки индийских цен и настроек регионов
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from config.settings import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Выполнить миграцию базы данных"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Начинаем транзакцию
        trans = conn.begin()
        
        try:
            logger.info("Начинаем миграцию базы данных...")
            
            # Добавляем поля для индийских цен в таблицу products
            logger.info("Добавляем поля для индийских цен...")
            conn.execute(text("""
                ALTER TABLE products 
                ADD COLUMN inr_price REAL DEFAULT NULL
            """))
            
            conn.execute(text("""
                ALTER TABLE products 
                ADD COLUMN inr_price_old REAL DEFAULT NULL
            """))
            
            # Добавляем поля настроек регионов в таблицу users
            logger.info("Добавляем поля настроек регионов...")
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN show_ukraine_prices BOOLEAN DEFAULT TRUE
            """))
            
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN show_turkey_prices BOOLEAN DEFAULT TRUE
            """))
            
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN show_india_prices BOOLEAN DEFAULT TRUE
            """))
            
            # Обновляем существующих пользователей, чтобы у них были включены все регионы по умолчанию
            logger.info("Обновляем настройки существующих пользователей...")
            conn.execute(text("""
                UPDATE users 
                SET show_ukraine_prices = TRUE,
                    show_turkey_prices = TRUE,
                    show_india_prices = TRUE
                WHERE show_ukraine_prices IS NULL
            """))
            
            # SQLite не поддерживает изменение комментариев к столбцам после создания
            logger.info("Миграция полей завершена (комментарии будут добавлены при пересоздании таблиц)")
            
            # Коммитим транзакцию
            trans.commit()
            logger.info("Миграция успешно завершена!")
            
        except Exception as e:
            # Откатываем транзакцию в случае ошибки
            trans.rollback()
            logger.error(f"Ошибка при выполнении миграции: {e}")
            raise
            
def check_migration_needed():
    """Проверить, нужна ли миграция"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            # Проверяем наличие новых полей
            result = conn.execute(text("PRAGMA table_info(products)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'inr_price' not in columns:
                return True
                
            result = conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'show_ukraine_prices' not in columns:
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при проверке миграции: {e}")
            return True
            
    return False

if __name__ == "__main__":
    if check_migration_needed():
        logger.info("Миграция необходима, запускаем...")
        run_migration()
    else:
        logger.info("Миграция не требуется, база данных уже обновлена.") 