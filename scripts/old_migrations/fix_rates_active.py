#!/usr/bin/env python3
"""
Исправление поля is_active в курсах валют
"""

import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import SessionLocal
from app.models.currency_rate import CurrencyRate

def fix_active_rates():
    """Исправить поле is_active для курсов валют"""
    
    print("🔧 Исправление поля is_active для курсов валют...")
    
    db = SessionLocal()
    try:
        # Найти все курсы с is_active = None
        rates = db.query(CurrencyRate).filter(CurrencyRate.is_active.is_(None)).all()
        print(f"📊 Найдено курсов с is_active = None: {len(rates)}")
        
        # Исправить их
        for rate in rates:
            rate.is_active = True
            print(f"  Исправлен курс: {rate.currency_from} {rate.price_min}-{rate.price_max or '∞'}")
        
        db.commit()
        print("✅ Все курсы исправлены")
        
        # Проверяем теперь
        print("\n🧪 Тестирование после исправления:")
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
    fix_active_rates()