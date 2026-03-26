import sqlite3
import json

# Подключаемся к БД
conn = sqlite3.connect('products.db')
cursor = conn.cursor()

# Получаем список таблиц
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("=== ТАБЛИЦЫ В БАЗЕ ДАННЫХ ===")
for table in tables:
    table_name = table[0]
    print(f"\n\nТаблица: {table_name}")
    print("=" * 80)
    
    # Получаем структуру таблицы
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    
    print("\nСтруктура таблицы:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]}) {'PRIMARY KEY' if col[5] else ''} {'NOT NULL' if col[3] else 'NULL'}")
    
    # Получаем количество записей
    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
    count = cursor.fetchone()[0]
    print(f"\nКоличество записей: {count}")
    
    # Показываем примеры данных (первые 3 записи)
    if count > 0:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
        rows = cursor.fetchall()
        
        print(f"\nПримеры данных (первые 3 записи):")
        col_names = [col[1] for col in columns]
        
        for i, row in enumerate(rows, 1):
            print(f"\n  Запись {i}:")
            for col_name, value in zip(col_names, row):
                # Ограничиваем длину для больших значений
                if value and isinstance(value, str) and len(str(value)) > 100:
                    value_str = str(value)[:100] + "..."
                else:
                    value_str = value
                print(f"    {col_name}: {value_str}")

conn.close()
print("\n\n=== АНАЛИЗ ЗАВЕРШЕН ===")

