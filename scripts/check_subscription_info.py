"""
Скрипт для проверки информации о подписках Extra/Deluxe в базе данных
"""
import sqlite3
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_database():
    """Проверить базу данных на наличие информации о подписках"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'products.db')
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        return
    
    print(f"📊 Проверка базы данных: {db_path}")
    print("=" * 80)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Проверяем структуру таблицы products
    print("\n1. Структура таблицы products:")
    cursor.execute("PRAGMA table_info(products)")
    columns = cursor.fetchall()
    
    has_ps_plus_collection = False
    has_plus_types = False
    
    for col in columns:
        col_name = col[1]
        col_type = col[2]
        print(f"   - {col_name}: {col_type}")
        if col_name == 'ps_plus_collection':
            has_ps_plus_collection = True
        if col_name == 'plus_types':
            has_plus_types = True
    
    print(f"\n   ✓ Поле ps_plus_collection: {'НАЙДЕНО' if has_ps_plus_collection else 'НЕ НАЙДЕНО'}")
    print(f"   ✓ Поле plus_types: {'НАЙДЕНО' if has_plus_types else 'НЕ НАЙДЕНО'}")
    
    # Проверяем количество товаров с ps_plus_collection
    if has_ps_plus_collection:
        print("\n2. Статистика по ps_plus_collection:")
        cursor.execute("""
            SELECT 
                ps_plus_collection,
                COUNT(*) as count
            FROM products
            WHERE ps_plus_collection IS NOT NULL
            GROUP BY ps_plus_collection
        """)
        results = cursor.fetchall()
        
        if results:
            for row in results:
                print(f"   - {row[0]}: {row[1]} товаров")
        else:
            print("   - Нет товаров с заполненным ps_plus_collection")
        
        # Показываем примеры товаров с Extra/Deluxe
        print("\n3. Примеры товаров с Extra/Deluxe (первые 10):")
        cursor.execute("""
            SELECT id, name, region, ps_plus_collection, ps_plus
            FROM products
            WHERE ps_plus_collection = 'Extra/Deluxe'
            LIMIT 10
        """)
        examples = cursor.fetchall()
        
        if examples:
            for ex in examples:
                print(f"   - ID: {ex[0]}, Name: {ex[1][:50] if ex[1] else 'N/A'}, Region: {ex[2]}, PS Plus: {ex[4]}")
        else:
            print("   - Нет товаров с Extra/Deluxe")
    
    # Проверяем plus_types
    if has_plus_types:
        print("\n4. Статистика по plus_types:")
        cursor.execute("""
            SELECT 
                plus_types,
                COUNT(*) as count
            FROM products
            WHERE plus_types IS NOT NULL AND plus_types != ''
            GROUP BY plus_types
            LIMIT 10
        """)
        results = cursor.fetchall()
        
        if results:
            for row in results:
                print(f"   - {row[0]}: {row[1]} товаров")
        else:
            print("   - Нет товаров с заполненным plus_types")
    
    # Проверяем ps_plus
    print("\n5. Статистика по ps_plus:")
    cursor.execute("""
        SELECT 
            ps_plus,
            COUNT(*) as count
        FROM products
        GROUP BY ps_plus
    """)
    results = cursor.fetchall()
    
    for row in results:
        ps_plus_value = row[0] if row[0] is not None else 'NULL'
        print(f"   - ps_plus = {ps_plus_value}: {row[1]} товаров")
    
    # Проверяем товары, которые есть в PS Plus, но не имеют метки Extra/Deluxe
    if has_ps_plus_collection:
        print("\n6. Товары в PS Plus без метки Extra/Deluxe (первые 10):")
        cursor.execute("""
            SELECT id, name, region, ps_plus, ps_plus_collection
            FROM products
            WHERE ps_plus = 1 
            AND (ps_plus_collection IS NULL OR ps_plus_collection != 'Extra/Deluxe')
            LIMIT 10
        """)
        results = cursor.fetchall()
        
        if results:
            for row in results:
                print(f"   - ID: {row[0]}, Name: {row[1][:50] if row[1] else 'N/A'}, Region: {row[2]}, Collection: {row[4]}")
        else:
            print("   - Все товары в PS Plus имеют метку Extra/Deluxe или нет товаров в PS Plus")
    
    conn.close()
    print("\n" + "=" * 80)
    print("✅ Проверка завершена")

if __name__ == "__main__":
    check_database()

