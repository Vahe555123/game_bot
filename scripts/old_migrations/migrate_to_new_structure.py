#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт миграции базы данных на новую структуру товаров PlayStation Store

Этот скрипт:
1. Создает резервную копию текущей базы данных
2. Удаляет старые таблицы
3. Создает новые таблицы с обновленной структурой
4. Готовит базу для загрузки новых данных
"""

import os
import sys
import sqlite3
import shutil
from datetime import datetime
import logging

# Добавляем корневую папку проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import engine, create_tables
from app.models.product import Product
from app.models.user import User
from app.models.favorite import UserFavoriteProduct

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_backup():
    """Создает резервную копию текущей базы данных"""
    db_file = "products.db"
    if not os.path.exists(db_file):
        logger.warning(f"База данных {db_file} не найдена, резервная копия не создана")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"products_backup_{timestamp}.db"
    
    try:
        shutil.copy2(db_file, backup_file)
        logger.info(f"Резервная копия создана: {backup_file}")
        return backup_file
    except Exception as e:
        logger.error(f"Ошибка при создании резервной копии: {e}")
        return None

def get_database_info():
    """Получает информацию о текущей базе данных"""
    db_file = "products.db"
    if not os.path.exists(db_file):
        logger.info("База данных не существует")
        return None
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        info = {"tables": {}}
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            info["tables"][table_name] = count
            
        conn.close()
        return info
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о базе данных: {e}")
        return None

def drop_old_tables():
    """Удаляет старые таблицы"""
    db_file = "products.db"
    if not os.path.exists(db_file):
        logger.info("База данных не существует, нечего удалять")
        return True
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Получаем список всех таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        # Удаляем каждую таблицу
        for table in tables:
            table_name = table[0]
            logger.info(f"Удаляем таблицу: {table_name}")
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        
        conn.commit()
        conn.close()
        logger.info("Все старые таблицы удалены")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при удалении старых таблиц: {e}")
        return False

def create_new_tables():
    """Создает новые таблицы с обновленной структурой"""
    try:
        logger.info("Создаем новые таблицы...")
        create_tables()
        logger.info("Новые таблицы успешно созданы")
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании новых таблиц: {e}")
        return False

def verify_new_structure():
    """Проверяет структуру новых таблиц"""
    try:
        conn = sqlite3.connect("products.db")
        cursor = conn.cursor()
        
        # Проверяем структуру таблицы products
        cursor.execute("PRAGMA table_info(products)")
        columns = cursor.fetchall()
        
        logger.info("Структура новой таблицы products:")
        for col in columns:
            logger.info(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")
        
        # Проверяем структуру таблицы user_favorite_products
        cursor.execute("PRAGMA table_info(user_favorite_products)")
        columns = cursor.fetchall()
        
        logger.info("Структура таблицы user_favorite_products:")
        for col in columns:
            logger.info(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при проверке структуры: {e}")
        return False

def main():
    """Главная функция миграции"""
    logger.info("=" * 60)
    logger.info("НАЧАЛО МИГРАЦИИ БАЗЫ ДАННЫХ")
    logger.info("=" * 60)
    
    # Шаг 1: Получаем информацию о текущей базе
    logger.info("Шаг 1: Анализ текущей базы данных")
    db_info = get_database_info()
    if db_info:
        logger.info("Текущие таблицы:")
        for table, count in db_info["tables"].items():
            logger.info(f"  {table}: {count} записей")
    
    # Шаг 2: Создаем резервную копию
    logger.info("\nШаг 2: Создание резервной копии")
    backup_file = create_backup()
    if not backup_file and os.path.exists("products.db"):
        logger.error("Не удалось создать резервную копию!")
        response = input("Продолжить без резервной копии? (y/N): ")
        if response.lower() != 'y':
            logger.info("Миграция отменена")
            return False
    
    # Шаг 3: Удаляем старые таблицы
    logger.info("\nШаг 3: Удаление старых таблиц")
    if not drop_old_tables():
        logger.error("Не удалось удалить старые таблицы!")
        return False
    
    # Шаг 4: Создаем новые таблицы
    logger.info("\nШаг 4: Создание новых таблиц")
    if not create_new_tables():
        logger.error("Не удалось создать новые таблицы!")
        return False
    
    # Шаг 5: Проверяем структуру
    logger.info("\nШаг 5: Проверка новой структуры")
    if not verify_new_structure():
        logger.error("Ошибка при проверке структуры!")
        return False
    
    logger.info("\n" + "=" * 60)
    logger.info("МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
    logger.info("=" * 60)
    logger.info("Следующие шаги:")
    logger.info("1. Запустите скрипт загрузки новых данных")
    logger.info("2. Проверьте работу API")
    if backup_file:
        logger.info(f"3. При необходимости восстановите из резервной копии: {backup_file}")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nМиграция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        sys.exit(1)