#!/usr/bin/env python3
"""
Исправление курсов валют - проверка и корректировка
"""

import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import SessionLocal
from app.models.currency_rate import CurrencyRate

def fix_currency_rates():
    """Проверить и исправить курсы валют"""
    
    print("🔧 Проверка и исправление курсов валют...")
    
    db = SessionLocal()
    try:
        # Проверяем текущие курсы
        rates = db.query(CurrencyRate).all()
        print(f"📊 Найдено курсов в базе: {len(rates)}")
        
        for rate in rates:
            print(f"  {rate.currency_from}: {rate.price_min}-{rate.price_max or '∞'} = {rate.rate} (активен: {rate.is_active})")
        
        if len(rates) == 0:
            print("❌ Курсы не найдены! Добавляем базовые курсы...")
            
            # Добавляем правильные курсы
            default_rates = [
                # UAH курсы (приблизительно 2.5 рубля за гривну)
                ('UAH', 'RUB', 0, 99, 2.5, 'Бюджетные игры'),
                ('UAH', 'RUB', 100, 499, 2.3, 'Средние игры'),
                ('UAH', 'RUB', 500, 999, 2.1, 'Премиум игры'),
                ('UAH', 'RUB', 1000, None, 2.0, 'AAA игры'),
                
                # TRL курсы (приблизительно 3 рубля за лиру)
                ('TRL', 'RUB', 0, 29, 3.2, 'Бюджетные игры'),
                ('TRL', 'RUB', 30, 149, 3.0, 'Средние игры'),
                ('TRL', 'RUB', 150, 299, 2.8, 'Премиум игры'),
                ('TRL', 'RUB', 300, None, 2.6, 'AAA игры'),
                
                # INR курсы (приблизительно 1.2 рубля за рупию)
                ('INR', 'RUB', 0, 499, 1.3, 'Бюджетные игры'),
                ('INR', 'RUB', 500, 1999, 1.2, 'Средние игры'),
                ('INR', 'RUB', 2000, 3999, 1.1, 'Премиум игры'),
                ('INR', 'RUB', 4000, None, 1.0, 'AAA игры'),
            ]
            
            for rate_data in default_rates:
                rate = CurrencyRate(
                    currency_from=rate_data[0],
                    currency_to=rate_data[1],
                    price_min=rate_data[2],
                    price_max=rate_data[3],
                    rate=rate_data[4],
                    description=rate_data[5]
                )
                db.add(rate)
            
            db.commit()
            print("✅ Добавлены базовые курсы валют")
        
        # Проверяем работу получения курса
        print("\n🧪 Тестирование получения курсов:")
        test_cases = [
            ('UAH', 150),
            ('TRL', 100),
            ('INR', 1000)
        ]
        
        for currency, price in test_cases:
            rate = CurrencyRate.get_rate_for_price(db, currency, price)
            print(f"  {currency} {price} → курс {rate}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_currency_rates()