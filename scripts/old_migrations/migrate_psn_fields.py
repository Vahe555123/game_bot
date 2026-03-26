#!/usr/bin/env python3
"""
Миграция базы данных для добавления полей PSN в таблицу users
"""

import sqlite3
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from app.database.connection import create_tables
from app.models.user import User
from app.models.product import Product
from app.models.favorite import UserFavoriteProduct

def run_migration():
    """Выполнить миграцию базы данных"""
    
    print("🔄 Начинаем миграцию базы данных для добавления PSN полей...")
    
    # Получаем путь к базе данных
    db_path = settings.DATABASE_URL.replace('sqlite:///', '')
    
    if not os.path.exists(db_path):
        print(f"❌ Файл базы данных не найден: {db_path}")
        sys.exit(1)
    
    # Создаем подключение к базе данных
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Проверяем, существуют ли уже новые колонки
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        new_columns = ['platform', 'psn_email', 'psn_password_hash', 'psn_password_salt']
        existing_columns = [col for col in new_columns if col in columns]
        
        if existing_columns:
            print(f"⚠️  Колонки уже существуют: {existing_columns}")
            print("Пропускаем миграцию.")
            return
        
        print("📝 Добавляем новые колонки в таблицу users...")
        
        # Добавляем новые колонки
        migrations = [
            "ALTER TABLE users ADD COLUMN platform VARCHAR(50)",
            "ALTER TABLE users ADD COLUMN psn_email VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN psn_password_hash TEXT",
            "ALTER TABLE users ADD COLUMN psn_password_salt VARCHAR(32)"
        ]
        
        for migration_sql in migrations:
            try:
                cursor.execute(migration_sql)
                column_name = migration_sql.split('ADD COLUMN ')[1].split()[0]
                print(f"✅ Добавлена колонка: {column_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    column_name = migration_sql.split('ADD COLUMN ')[1].split()[0]
                    print(f"⚠️  Колонка {column_name} уже существует")
                else:
                    raise e
        
        # Коммитим изменения
        conn.commit()
        print("✅ Миграция выполнена успешно!")
        
        # Проверяем результат
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"📋 Текущие колонки в таблице users: {columns}")
        
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
        
        # Проверяем, что можно создать пользователя с новыми полями
        from app.database.connection import SessionLocal
        from app.models.user import User
        
        db = SessionLocal()
        try:
            # Создаем тестового пользователя
            test_user = User(
                telegram_id=999999999,
                username="test_psn_migration",
                platform="PS5",
                psn_email="test@example.com"
            )
            test_user.set_psn_password("test_password")
            
            db.add(test_user)
            db.commit()
            
            # Проверяем, что данные сохранились
            saved_user = db.query(User).filter(User.telegram_id == 999999999).first()
            if saved_user:
                print("✅ Тестовый пользователь создан успешно")
                print(f"   Platform: {saved_user.platform}")
                print(f"   PSN Email: {saved_user.psn_email}")
                print(f"   Has PSN Password: {saved_user.has_psn_credentials}")
                
                # Удаляем тестового пользователя
                db.delete(saved_user)
                db.commit()
                print("✅ Тестовые данные очищены")
            else:
                print("❌ Не удалось создать тестового пользователя")
                
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Ошибка при проверке миграции: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
    verify_migration()
    print("\n🎉 Миграция PSN полей завершена успешно!")