import pandas as pd
from datetime import datetime
import logging
import sys
import os

# Добавляем корневую папку проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.product import Product
from app.database.connection import engine, SessionLocal, create_tables

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_date(date_str):
    """Парсит дату из различных форматов"""
    if pd.isna(date_str) or date_str == '' or date_str is None:
        return None
    
    # Если это уже datetime объект
    if isinstance(date_str, datetime):
        return date_str.date()
    
    # Попробуем различные форматы дат
    date_formats = [
        '%Y-%m-%d',
        '%d.%m.%Y',
        '%d/%m/%Y',
        '%m/%d/%Y',
        '%Y.%m.%d'
    ]
    
    date_str = str(date_str).strip()
    
    for date_format in date_formats:
        try:
            return datetime.strptime(date_str, date_format).date()
        except ValueError:
            continue
    
    logger.warning(f"Не удалось распарсить дату: {date_str}")
    return None

def parse_float(value):
    """Парсит числовое значение"""
    if pd.isna(value) or value == '' or value is None:
        return None
    
    try:
        # Убираем возможные лишние символы
        if isinstance(value, str):
            value = value.replace(',', '.').replace(' ', '').replace('₴', '').replace('₺', '').replace('%', '')
        return float(value)
    except (ValueError, TypeError):
        logger.warning(f"Не удалось преобразовать в число: {value}")
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
            
            # Обрабатываем каждую строку
            for index, row in df.iterrows():
                try:
                    # Создаем объект Product
                    product = Product(
                        category=str(row.get('Category', '')).strip() if pd.notna(row.get('Category')) else None,
                        name=str(row.get('Name', '')).strip() if pd.notna(row.get('Name')) else None,
                        image=str(row.get('Image', '')).strip() if pd.notna(row.get('Image')) else None,
                        trl_price_old=parse_float(row.get('TRL Price Old')),
                        trl_price=parse_float(row.get('TRL Price')),
                        uah_price_old=parse_float(row.get('UAH Price Old')),
                        uah_price=parse_float(row.get('UAH Price')),
                        discount_percent=parse_float(row.get('Discount Percent')),
                        publisher=str(row.get('Publisher', '')).strip() if pd.notna(row.get('Publisher')) else None,
                        discount_end_date=parse_date(row.get('Discount End Date')),
                        edition_release_date=parse_date(row.get('Edition Release Date')),
                        description=str(row.get('Description', '')).strip() if pd.notna(row.get('Description')) else None,
                        is_active=True
                    )
                    
                    session.add(product)
                    products_added += 1
                    
                    # Коммитим каждые 100 записей
                    if products_added % 100 == 0:
                        session.commit()
                        logger.info(f"Добавлено {products_added} товаров...")
                        
                except Exception as e:
                    logger.error(f"Ошибка при обработке строки {index + 1}: {e}")
                    continue
            
            # Финальный коммит
            session.commit()
            logger.info(f"Загрузка завершена! Добавлено {products_added} товаров в базу данных")
            
        finally:
            session.close()
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных: {e}")
        raise

def main():
    """Главная функция"""
    xlsx_file = "ps_ru-ua.xlsx"
    
    if not os.path.exists(xlsx_file):
        logger.error(f"Файл {xlsx_file} не найден!")
        return
    
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
            logger.info(f"  - {product.name} (Категория: {product.category}, Цена UAH: {product.uah_price})")
    finally:
        session.close()

if __name__ == "__main__":
    main() 