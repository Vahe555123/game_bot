"""Проверка скидок в базе данных"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database.connection import SessionLocal
from app.models.product import Product

db = SessionLocal()

# Ищем игру Vikings Pinball
products = db.query(Product).filter(Product.name.like('%Vikings Pinball%')).all()

print(f"Найдено товаров: {len(products)}")
print("=" * 80)

for p in products:
    print(f"\nID: {p.id}")
    print(f"Name: {p.name}")
    print(f"Region: {p.region}")
    print(f"Price UAH: {p.price_uah}")
    print(f"Old Price UAH: {p.old_price_uah}")
    print(f"Price TRY: {p.price_try}")
    print(f"Old Price TRY: {p.old_price_try}")
    print(f"Price INR: {p.price_inr}")
    print(f"Old Price INR: {p.old_price_inr}")
    print(f"Discount: {p.discount}")
    print(f"Has Discount: {p.has_discount}")
    print(f"Price (общее): {p.price}")
    print(f"Old Price (общее): {p.old_price}")
    print("-" * 80)

db.close()

