#!/usr/bin/env python3
"""
Миграция базы данных для добавления системы курсов валют и рублевых цен
"""

import sqlite3
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from app.database.connection import create_tables

def run_migration():
    """Выполнить миграцию базы данных"""
    
    print("🔄 Начинаем миграцию системы курсов валют...")
    
    # Получаем путь к базе данных
    db_path = settings.DATABASE_URL.replace('sqlite:///', '')
    
    if not os.path.exists(db_path):
        print(f"❌ Файл базы данных не найден: {db_path}")
        sys.exit(1)
    
    # Создаем подключение к базе данных
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("📝 Добавляем новые колонки в таблицу products...")
        
        # Проверяем, существуют ли уже новые колонки в products
        cursor.execute("PRAGMA table_info(products)")
        columns = [column[1] for column in cursor.fetchall()]
        
        product_migrations = [
            ("inr_price", "ALTER TABLE products ADD COLUMN inr_price TEXT"),
            ("inr_price_old", "ALTER TABLE products ADD COLUMN inr_price_old TEXT"),
            ("rub_price", "ALTER TABLE products ADD COLUMN rub_price REAL"),
            ("rub_price_old", "ALTER TABLE products ADD COLUMN rub_price_old REAL"),
            ("rub_price_updated_at", "ALTER TABLE products ADD COLUMN rub_price_updated_at TIMESTAMP")
        ]
        
        for column_name, migration_sql in product_migrations:
            if column_name not in columns:
                try:
                    cursor.execute(migration_sql)
                    print(f"✅ Добавлена колонка: {column_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e):
                        print(f"⚠️  Колонка {column_name} уже существует")
                    else:
                        raise e
            else:
                print(f"⚠️  Колонка {column_name} уже существует")
        
        # Создаем таблицу currency_rates если её нет
        print("📝 Создаем таблицу currency_rates...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS currency_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency_from VARCHAR(10) NOT NULL,
                currency_to VARCHAR(10) NOT NULL DEFAULT 'RUB',
                price_min REAL NOT NULL,
                price_max REAL,
                rate REAL NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                description TEXT
            )
        """)
        print("✅ Таблица currency_rates создана")
        
        # Добавляем тестовые курсы
        print("📝 Добавляем базовые курсы валют...")
        
        default_rates = [
            # UAH курсы
            ('UAH', 'RUB', 0, 99, 2.5, 'Бюджетные игры'),
            ('UAH', 'RUB', 100, 499, 2.3, 'Средние игры'),
            ('UAH', 'RUB', 500, 999, 2.1, 'Премиум игры'),
            ('UAH', 'RUB', 1000, None, 2.0, 'AAA игры'),
            
            # TRL курсы
            ('TRL', 'RUB', 0, 29, 3.2, 'Бюджетные игры'),
            ('TRL', 'RUB', 30, 149, 3.0, 'Средние игры'),
            ('TRL', 'RUB', 150, 299, 2.8, 'Премиум игры'),
            ('TRL', 'RUB', 300, None, 2.6, 'AAA игры'),
            
            # INR курсы
            ('INR', 'RUB', 0, 499, 1.3, 'Бюджетные игры'),
            ('INR', 'RUB', 500, 1999, 1.2, 'Средние игры'),
            ('INR', 'RUB', 2000, 3999, 1.1, 'Премиум игры'),
            ('INR', 'RUB', 4000, None, 1.0, 'AAA игры'),
        ]
        
        # Проверяем, есть ли уже курсы
        cursor.execute("SELECT COUNT(*) FROM currency_rates")
        existing_rates = cursor.fetchone()[0]
        
        if existing_rates == 0:
            for rate_data in default_rates:
                cursor.execute("""
                    INSERT INTO currency_rates 
                    (currency_from, currency_to, price_min, price_max, rate, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, rate_data)
            print("✅ Добавлены базовые курсы валют")
        else:
            print("⚠️  Курсы валют уже существуют, пропускаем добавление")
        
        # Коммитим изменения
        conn.commit()
        print("✅ Миграция выполнена успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции: {e}")
        conn.rollback()
        sys.exit(1)
    
    finally:
        conn.close()

def verify_migration():
    """Проверить успешность миграции"""
    print("\n🔍 Проверяем миграцию...")
    
    try:
        # Пытаемся создать таблицы через SQLAlchemy
        create_tables()
        print("✅ Структура базы данных соответствует моделям")
        
        # Проверяем, что можно работать с курсами валют
        from app.database.connection import SessionLocal
        from app.models.currency_rate import CurrencyRate
        
        db = SessionLocal()
        try:
            # Проверяем курсы валют
            rates_count = db.query(CurrencyRate).count()
            print(f"✅ Найдено курсов валют: {rates_count}")
            
            # Тестируем получение курса для конкретной цены
            test_rate = CurrencyRate.get_rate_for_price(db, 'UAH', 150.0)
            print(f"✅ Тестовый курс UAH для цены 150: {test_rate}")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Ошибка при проверке миграции: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
    verify_migration()
    print("\n🎉 Миграция системы курсов валют завершена успешно!")
    print("\n📋 Пример настройки .env для админов:")
    print("# Добавьте ваш Telegram ID в список админов (можно несколько через запятую)")
    print("ADMIN_TELEGRAM_IDS=123456789,987654321")
    print("ADMIN_SECRET_KEY=your-secret-admin-key-here")