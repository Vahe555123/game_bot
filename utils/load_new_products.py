#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт загрузки новых данных PlayStation Store из Excel файла

Этот скрипт загружает данные из файла playstation_store_products_20250802_011123.xlsx
в обновленную структуру базы данных.
"""

import pandas as pd
import json
import ast
from datetime import datetime
import logging
import sys
import os

# Добавляем корневую папку проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.product import Product
from app.database.connection import engine, SessionLocal, create_tables

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('load_products.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def safe_eval_json(value):
    """Безопасно преобразует строку в JSON/Python объект"""
    if pd.isna(value) or value == '' or value is None:
        return None
    
    if isinstance(value, (dict, list)):
        return value
    
    try:
        # Сначала пробуем как JSON
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        try:
            # Затем пробуем как Python literal
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            # Если не получается, возвращаем как строку
            return str(value)

def clean_html_description(description):
    """Очищает HTML описание от лишних тегов"""
    if not description or pd.isna(description):
        return None
    
    # Простая очистка HTML - можно расширить при необходимости
    import re
    # Удаляем HTML теги
    clean_desc = re.sub(r'<[^>]+>', '', str(description))
    # Убираем лишние пробелы
    clean_desc = ' '.join(clean_desc.split())
    
    return clean_desc if clean_desc else None

def parse_compound(compound_data):
    """Парсит данные о составе товара"""
    if not compound_data or pd.isna(compound_data):
        return None
    
    parsed = safe_eval_json(compound_data)
    if isinstance(parsed, list):
        return parsed
    elif isinstance(parsed, str):
        return [parsed]
    return None

def parse_name(name_data):
    """Парсит название товара"""
    if not name_data or pd.isna(name_data):
        return "Без названия"
    
    parsed = safe_eval_json(name_data)
    if isinstance(parsed, list) and parsed:
        return json.dumps(parsed)  # Сохраняем как JSON строку
    elif isinstance(parsed, str):
        return parsed
    return str(name_data)

def parse_stars(stars_data):
    """Парсит данные о рейтинге"""
    if not stars_data or pd.isna(stars_data):
        return None
    
    parsed = safe_eval_json(stars_data)
    if isinstance(parsed, list):
        return parsed
    return None

def parse_ext_info(ext_info_data):
    """Парсит дополнительную информацию"""
    if not ext_info_data or pd.isna(ext_info_data):
        return None
    
    parsed = safe_eval_json(ext_info_data)
    if isinstance(parsed, list):
        return parsed
    return None

def parse_price_json(price_data):
    """Парсит JSON данные о цене"""
    if not price_data or pd.isna(price_data):
        return None
    
    parsed = safe_eval_json(price_data)
    if isinstance(parsed, dict):
        return parsed
    return None

def load_xlsx_to_database(xlsx_file_path):
    """Загружает данные из xlsx файла в базу данных"""
    try:
        # Создаем таблицы если их нет
        create_tables()
        
        # Читаем xlsx файл
        logger.info(f"Читаем файл: {xlsx_file_path}")
        df = pd.read_excel(xlsx_file_path)
        
        logger.info(f"Найдено {len(df)} строк в файле")
        logger.info(f"Колонки: {list(df.columns)}")
        
        # Создаем сессию
        session = SessionLocal()
        
        try:
            # Очищаем таблицу перед загрузкой
            session.query(Product).delete()
            session.commit()
            logger.info("Таблица товаров очищена")
            
            products_added = 0
            products_skipped = 0
            
            # Обрабатываем каждую строку
            for index, row in df.iterrows():
                try:
                    # Проверяем обязательные поля
                    product_id = str(row.get('id', '')).strip()
                    if not product_id:
                        logger.warning(f"Строка {index + 1}: отсутствует ID товара, пропускаем")
                        products_skipped += 1
                        continue
                    
                    # Создаем объект Product
                    product = Product(
                        id=product_id,
                        category=str(row.get('category', '')).strip() if pd.notna(row.get('category')) else None,
                        product_type=str(row.get('product_type', '')).strip() if pd.notna(row.get('product_type')) else None,
                        name=parse_name(row.get('name')),
                        image=str(row.get('image', '')).strip() if pd.notna(row.get('image')) else None,
                        compound=parse_compound(row.get('compound')),
                        platforms=clean_html_description(row.get('platforms')),
                        publisher=str(row.get('publisher', '')).strip() if pd.notna(row.get('publisher')) else None,
                        voice_languages=str(row.get('voice_languages', '')).strip() if pd.notna(row.get('voice_languages')) else None,
                        subtitles=str(row.get('subtitles', '')).strip() if pd.notna(row.get('subtitles')) else None,
                        stars=parse_stars(row.get('stars')),
                        ext_info=parse_ext_info(row.get('ext_info')),
                        edition=str(row.get('edition', '')).strip() if pd.notna(row.get('edition')) else None,
                        uah_price=parse_price_json(row.get('uah_price')),
                        uah_price_old=parse_price_json(row.get('uah_old_price')),
                        trl_price=parse_price_json(row.get('trl_price')),
                        trl_price_old=parse_price_json(row.get('trl_old_price')),
                        discount=parse_price_json(row.get('discount')),
                        discount_end=parse_price_json(row.get('discount_end')),
                        description=clean_html_description(row.get('description')),
                        is_active=True
                    )
                    
                    session.add(product)
                    products_added += 1
                    
                    # Коммитим каждые 100 записей
                    if products_added % 100 == 0:
                        session.commit()
                        logger.info(f"Добавлено {products_added} товаров...")
                        
                except Exception as e:
                    logger.error(f"Ошибка при обработке строки {index + 1} (ID: {product_id}): {e}")
                    products_skipped += 1
                    continue
            
            # Финальный коммит
            session.commit()
            logger.info(f"Загрузка завершена! Добавлено {products_added} товаров, пропущено {products_skipped}")
            
        finally:
            session.close()
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных: {e}")
        raise

def analyze_sample_data(xlsx_file_path, sample_size=5):
    """Анализирует образцы данных из файла"""
    try:
        df = pd.read_excel(xlsx_file_path)
        logger.info(f"Анализ образцов данных из {sample_size} строк:")
        
        for index, row in df.head(sample_size).iterrows():
            logger.info(f"\n--- Строка {index + 1} ---")
            logger.info(f"ID: {row.get('id')}")
            logger.info(f"Name: {parse_name(row.get('name'))}")
            logger.info(f"Category: {row.get('category')}")
            logger.info(f"Publisher: {row.get('publisher')}")
            
            # Анализ цен
            uah_price = parse_price_json(row.get('uah_price'))
            trl_price = parse_price_json(row.get('trl_price'))
            discount = parse_price_json(row.get('discount'))
            
            logger.info(f"UAH Price: {uah_price}")
            logger.info(f"TRL Price: {trl_price}")
            logger.info(f"Discount: {discount}")
            
    except Exception as e:
        logger.error(f"Ошибка при анализе данных: {e}")

def main():
    """Главная функция"""
    xlsx_file = "playstation_store_products_20250802_011123.xlsx"
    
    if not os.path.exists(xlsx_file):
        logger.error(f"Файл {xlsx_file} не найден!")
        # Показываем доступные xlsx файлы
        xlsx_files = [f for f in os.listdir('.') if f.endswith('.xlsx')]
        if xlsx_files:
            logger.info("Доступные .xlsx файлы:")
            for f in xlsx_files:
                logger.info(f"  - {f}")
        return False
    
    logger.info("=" * 60)
    logger.info("ЗАГРУЗКА НОВЫХ ДАННЫХ PLAYSTATION STORE")
    logger.info("=" * 60)
    
    # Сначала анализируем образцы данных
    logger.info("Анализ образцов данных...")
    analyze_sample_data(xlsx_file)
    
    # Подтверждение загрузки
    response = input("\nПродолжить загрузку данных? (y/N): ")
    if response.lower() != 'y':
        logger.info("Загрузка отменена")
        return False
    
    logger.info("Начинаем загрузку данных из xlsx в базу данных...")
    load_xlsx_to_database(xlsx_file)
    
    # Проверяем результат
    session = SessionLocal()
    try:
        total_products = session.query(Product).count()
        logger.info(f"Всего товаров в базе данных: {total_products}")
        
        # Показываем несколько примеров
        sample_products = session.query(Product).limit(3).all()
        logger.info("Примеры загруженных товаров:")
        for product in sample_products:
            logger.info(f"  - {product.get_display_name()} (Категория: {product.category})")
            logger.info(f"    UAH: {product.get_price('UAH')}, TRL: {product.get_price('TRL')}")
            logger.info(f"    Скидка: {product.get_discount_percent()}%")
            
    finally:
        session.close()
    
    logger.info("\n" + "=" * 60)
    logger.info("ЗАГРУЗКА ЗАВЕРШЕНА!")
    logger.info("=" * 60)
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nЗагрузка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        sys.exit(1)