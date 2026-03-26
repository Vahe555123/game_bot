#!/usr/bin/env python3
"""
Скрипт для заполнения тестовых цен в индийских рупиях
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from config.settings import settings
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def populate_inr_prices():
    """Заполнить тестовые цены в индийских рупиях"""
    engine = create_engine(settings.DATABASE_URL)
    
    # Приблизительные курсы валют (для тестирования)
    # 1 UAH ≈ 2.2 INR
    # 1 TRL ≈ 2.5 INR
    UAH_TO_INR = 2.2
    TRL_TO_INR = 2.5
    
    with engine.connect() as conn:
        trans = conn.begin()
        
        try:
            logger.info("Заполняем цены в индийских рупиях...")
            
            # Получаем все продукты
            result = conn.execute(text("""
                SELECT id, name, uah_price, uah_price_old, trl_price, trl_price_old 
                FROM products 
                WHERE is_active = 1
            """))
            
            products = result.fetchall()
            logger.info(f"Найдено {len(products)} продуктов для обновления")
            
            for product in products:
                product_id, name, uah_price, uah_price_old, trl_price, trl_price_old = product
                
                # Вычисляем цены в рупиях на основе гривны (приоритет) или лиры
                if uah_price:
                    inr_price = round(uah_price * UAH_TO_INR * random.uniform(0.9, 1.1), 2)
                elif trl_price:
                    inr_price = round(trl_price * TRL_TO_INR * random.uniform(0.9, 1.1), 2)
                else:
                    inr_price = None
                
                # Вычисляем старую цену
                inr_price_old = None
                if inr_price:
                    if uah_price_old and uah_price_old > uah_price:
                        inr_price_old = round(uah_price_old * UAH_TO_INR * random.uniform(0.9, 1.1), 2)
                    elif trl_price_old and trl_price_old > trl_price:
                        inr_price_old = round(trl_price_old * TRL_TO_INR * random.uniform(0.9, 1.1), 2)
                    else:
                        # Добавляем случайную старую цену для некоторых товаров
                        if random.random() < 0.3:  # 30% товаров будут со скидкой
                            inr_price_old = round(inr_price * random.uniform(1.2, 1.8), 2)
                
                # Обновляем продукт
                conn.execute(text("""
                    UPDATE products 
                    SET inr_price = :inr_price, inr_price_old = :inr_price_old
                    WHERE id = :product_id
                """), {
                    'inr_price': inr_price,
                    'inr_price_old': inr_price_old,
                    'product_id': product_id
                })
                
                logger.info(f"Обновлен продукт '{name}': INR {inr_price} (было {inr_price_old})")
            
            trans.commit()
            logger.info("Цены в индийских рупиях успешно добавлены!")
            
        except Exception as e:
            trans.rollback()
            logger.error(f"Ошибка при заполнении цен: {e}")
            raise

if __name__ == "__main__":
    populate_inr_prices() 