#!/usr/bin/env python3
"""
Тестирование системы курсов валют
"""

import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import SessionLocal
from app.models.currency_rate import CurrencyRate
from app.models.product import Product
from app.api.crud import admin_crud

def test_currency_rates():
    """Тестирование работы курсов валют"""
    
    print("🧪 Тестирование системы курсов валют...")
    
    db = SessionLocal()
    try:
        # Тестируем получение курса для конкретной цены
        test_cases = [
            ('UAH', 50, 'Бюджетная игра'),
            ('UAH', 150, 'Средняя игра'),
            ('UAH', 750, 'Премиум игра'),
            ('UAH', 1500, 'AAA игра'),
            ('TRL', 25, 'Бюджетная игра'),
            ('TRL', 100, 'Средняя игра'),
            ('TRL', 200, 'Премиум игра'),
            ('TRL', 500, 'AAA игра'),
            ('INR', 200, 'Бюджетная игра'),
            ('INR', 1000, 'Средняя игра'),
            ('INR', 3000, 'Премиум игра'),
            ('INR', 5000, 'AAA игра')
        ]
        
        print("\n📊 Тест курсов валют:")
        for currency, price, description in test_cases:
            rate = CurrencyRate.get_rate_for_price(db, currency, price)
            rub_price = price * rate
            print(f"  {currency} {price:6.0f} → RUB {rub_price:7.2f} (курс: {rate:4.2f}) - {description}")
        
        # Тестируем обновление рублевых цен для товара
        print("\n🎮 Тест обновления цен товаров:")
        products = db.query(Product).filter(Product.is_active == True).limit(5).all()
        
        updated_count = 0
        for product in products:
            old_rub_price = product.rub_price
            product.update_ruble_prices(db)
            
            if product.rub_price != old_rub_price:
                updated_count += 1
                
            print(f"  {product.get_display_name()[:50]:<50} → {product.rub_price:>8.2f} ₽")
        
        db.commit()
        print(f"\n✅ Обновлено цен у {updated_count} из {len(products)} товаров")
        
        # Тестируем массовое обновление цен
        print("\n🔄 Тест массового обновления цен...")
        total_updated = admin_crud.update_all_ruble_prices(db)
        print(f"✅ Массово обновлено {total_updated} товаров")
        
        # Получаем статистику
        print("\n📈 Статистика системы:")
        stats = admin_crud.get_stats(db)
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        db.rollback()
    finally:
        db.close()

def test_original_prices():
    """Тестирование отображения оригинальных цен"""
    
    print("\n🏷️ Тестирование оригинальных цен...")
    
    db = SessionLocal()
    try:
        # Берем первый товар с ценами
        product = db.query(Product).filter(
            Product.is_active == True,
            Product.uah_price.isnot(None)
        ).first()
        
        if not product:
            print("❌ Не найден товар с ценами для тестирования")
            return
        
        print(f"\n📦 Товар: {product.get_display_name()}")
        
        # Показываем оригинальные цены
        original_prices = product.get_original_prices_info()
        print("🌍 Оригинальные цены:")
        for price_info in original_prices:
            old_price_str = f" (было {price_info['old_price']}{price_info['symbol']})" if price_info['old_price'] else ""
            print(f"  {price_info['flag']} {price_info['name']}: {price_info['current_price']}{price_info['symbol']}{old_price_str}")
        
        # Показываем рублевую цену
        if product.rub_price:
            old_rub_str = f" (было {product.rub_price_old} ₽)" if product.rub_price_old else ""
            print(f"💰 Цена в рублях: {product.rub_price} ₽{old_rub_str}")
        else:
            print("💰 Цена в рублях: не установлена")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании оригинальных цен: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_currency_rates()
    test_original_prices()
    print("\n🎉 Тестирование завершено!")