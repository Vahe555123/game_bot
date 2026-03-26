#!/usr/bin/env python3
"""
Массовое обновление рублевых цен для всех товаров
"""

import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import get_db
from app.models.product import Product
from app.models.currency_rate import CurrencyRate

def update_all_ruble_prices():
    """Обновить рублевые цены для всех товаров"""
    
    db = next(get_db())
    
    try:
        # Получаем все активные товары без рублевых цен или с устаревшими ценами
        products = db.query(Product).filter(
            Product.is_active == True,
            (Product.rub_price.is_(None)) | (Product.rub_price_updated_at.is_(None))
        ).all()
        
        print(f"Найдено {len(products)} товаров для обновления рублевых цен")
        
        # Проверяем наличие курсов валют
        currency_rates = db.query(CurrencyRate).filter(CurrencyRate.is_active == True).all()
        print(f"Активных курсов валют: {len(currency_rates)}")
        
        if not currency_rates:
            print("❌ Нет активных курсов валют! Сначала настройте курсы в админке.")
            return
        
        updated_count = 0
        error_count = 0
        
        for i, product in enumerate(products, 1):
            try:
                print(f"[{i}/{len(products)}] Обновляем товар: {product.name[:50]}...")
                
                # Проверяем наличие цен в исходных валютах
                uah_price = product.get_price('UAH')
                trl_price = product.get_price('TRL')
                inr_price = product.get_price('INR')
                
                if not any([uah_price, trl_price, inr_price]):
                    print(f"  ⚠️ Пропускаем - нет цен в исходных валютах")
                    continue
                
                # Обновляем рублевые цены
                product.update_ruble_prices(db)
                
                if product.rub_price:
                    print(f"  ✅ Установлена цена: {product.rub_price} ₽")
                    updated_count += 1
                else:
                    print(f"  ⚠️ Не удалось рассчитать рублевую цену")
                    
            except Exception as e:
                print(f"  ❌ Ошибка: {e}")
                error_count += 1
        
        # Сохраняем изменения
        db.commit()
        
        print(f"\n📊 Результаты обновления:")
        print(f"  ✅ Обновлено товаров: {updated_count}")
        print(f"  ❌ Ошибок: {error_count}")
        print(f"  🔄 Всего обработано: {len(products)}")
        
        # Проверяем результат
        total_with_rub_prices = db.query(Product).filter(
            Product.is_active == True,
            Product.rub_price.isnot(None)
        ).count()
        
        total_active = db.query(Product).filter(Product.is_active == True).count()
        
        print(f"\n📈 Итоговая статистика:")
        print(f"  Всего активных товаров: {total_active}")
        print(f"  Товаров с рублевыми ценами: {total_with_rub_prices}")
        print(f"  Процент покрытия: {(total_with_rub_prices/total_active*100):.1f}%")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_all_ruble_prices()