"""
Скрипт для исправления данных о подписках в базе данных
Удаляет ps_plus_collection у товаров, где ps_plus = 0
"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_subscription_data():
    """Исправить данные о подписках в базе данных"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'products.db')
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        return
    
    print(f"🔧 Исправление данных о подписках в базе данных")
    print("=" * 80)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Находим товары с ps_plus_collection, но ps_plus = 0
    cursor.execute("""
        SELECT COUNT(*) 
        FROM products 
        WHERE ps_plus_collection IS NOT NULL 
        AND ps_plus = 0
    """)
    count = cursor.fetchone()[0]
    
    if count > 0:
        print(f"\nНайдено {count} товаров с неправильными данными о подписках")
        print("Исправление...")
        
        # Удаляем ps_plus_collection у товаров, где ps_plus = 0
        cursor.execute("""
            UPDATE products 
            SET ps_plus_collection = NULL 
            WHERE ps_plus_collection IS NOT NULL 
            AND ps_plus = 0
        """)
        
        conn.commit()
        print(f"✓ Исправлено {count} записей")
    else:
        print("\n✓ Нет товаров с неправильными данными о подписках")
    
    # Показываем статистику после исправления
    print("\nСтатистика после исправления:")
    cursor.execute("""
        SELECT 
            ps_plus,
            COUNT(*) as count,
            COUNT(CASE WHEN ps_plus_collection IS NOT NULL THEN 1 END) as with_collection
        FROM products
        GROUP BY ps_plus
    """)
    results = cursor.fetchall()
    
    for row in results:
        ps_plus = row[0] if row[0] is not None else 'NULL'
        total = row[1]
        with_collection = row[2]
        print(f"  - ps_plus = {ps_plus}: {total} товаров, из них с collection: {with_collection}")
    
    conn.close()
    print("\n" + "=" * 80)
    print("✅ Исправление завершено")

if __name__ == "__main__":
    fix_subscription_data()

