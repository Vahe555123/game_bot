"""
Скрипт для детальной проверки подписок в базе данных
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_subscription_details():
    """Проверить детали подписок в базе данных"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'products.db')
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        return
    
    print(f"📊 Детальная проверка подписок в базе данных")
    print("=" * 80)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Товары с ps_plus = 1
    print("\n1. Товары с ps_plus = 1 (в подписке по API):")
    cursor.execute("""
        SELECT id, name, region, ps_plus, ps_plus_collection, ps_price
        FROM products
        WHERE ps_plus = 1
        LIMIT 10
    """)
    ps_plus_items = cursor.fetchall()
    
    if ps_plus_items:
        for item in ps_plus_items:
            print(f"   - ID: {item[0]}")
            print(f"     Name: {item[1][:60] if item[1] else 'N/A'}")
            print(f"     Region: {item[2]}, PS Plus: {item[3]}, Collection: {item[4]}, PS Price: {item[5]}")
            print()
    else:
        print("   - Нет товаров с ps_plus = 1")
    
    # 2. Товары с ps_plus_collection, но ps_plus = 0
    print("\n2. Товары с ps_plus_collection, но ps_plus = 0 (НЕПРАВИЛЬНО!):")
    cursor.execute("""
        SELECT id, name, region, ps_plus, ps_plus_collection
        FROM products
        WHERE ps_plus_collection IS NOT NULL AND ps_plus = 0
        LIMIT 10
    """)
    wrong_items = cursor.fetchall()
    
    if wrong_items:
        for item in wrong_items:
            print(f"   - ID: {item[0]}")
            print(f"     Name: {item[1][:60] if item[1] else 'N/A'}")
            print(f"     Region: {item[2]}, PS Plus: {item[3]}, Collection: {item[4]}")
            print()
    else:
        print("   - Нет таких товаров (хорошо!)")
    
    # 3. Товары с ps_plus = 1, но без ps_plus_collection
    print("\n3. Товары с ps_plus = 1, но без ps_plus_collection (обычный PS Plus?):")
    cursor.execute("""
        SELECT id, name, region, ps_plus, ps_plus_collection, ps_price
        FROM products
        WHERE ps_plus = 1 AND (ps_plus_collection IS NULL OR ps_plus_collection = '')
        LIMIT 10
    """)
    ps_plus_no_collection = cursor.fetchall()
    
    if ps_plus_no_collection:
        for item in ps_plus_no_collection:
            print(f"   - ID: {item[0]}")
            print(f"     Name: {item[1][:60] if item[1] else 'N/A'}")
            print(f"     Region: {item[2]}, PS Plus: {item[3]}, Collection: {item[4]}, PS Price: {item[5]}")
            print()
    else:
        print("   - Нет таких товаров")
    
    # 4. Статистика по ps_price
    print("\n4. Статистика по ps_price (скидка для PS Plus):")
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN ps_price IS NOT NULL AND ps_price > 0 THEN 1 ELSE 0 END) as with_ps_price
        FROM products
    """)
    stats = cursor.fetchone()
    print(f"   - Всего товаров: {stats[0]}")
    print(f"   - С PS Plus скидкой: {stats[1]}")
    
    conn.close()
    print("\n" + "=" * 80)
    print("✅ Проверка завершена")

if __name__ == "__main__":
    check_subscription_details()

