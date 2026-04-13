import sqlite3

# Подключение к БД
conn = sqlite3.connect('products.db')
cursor = conn.cursor()

# Создание таблицы currency_rates
cursor.execute("""
    CREATE TABLE IF NOT EXISTS currency_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        currency_from TEXT NOT NULL,
        currency_to TEXT NOT NULL,
        price_min REAL NOT NULL,
        price_max REAL,
        rate REAL NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# Вставка базовых курсов валют (примерные значения)
# UAH -> RUB
cursor.execute("""
    INSERT INTO currency_rates (currency_from, currency_to, price_min, price_max, rate, is_active)
    VALUES
        ('UAH', 'RUB', 0, 1000, 2.5, 1),
        ('UAH', 'RUB', 1000, NULL, 2.5, 1)
""")

# TRY -> RUB
cursor.execute("""
    INSERT INTO currency_rates (currency_from, currency_to, price_min, price_max, rate, is_active)
    VALUES
        ('TRY', 'RUB', 0, 1000, 3.0, 1),
        ('TRY', 'RUB', 1000, NULL, 3.0, 1)
""")

# INR -> RUB
cursor.execute("""
    INSERT INTO currency_rates (currency_from, currency_to, price_min, price_max, rate, is_active)
    VALUES
        ('INR', 'RUB', 0, 1000, 1.2, 1),
        ('INR', 'RUB', 1000, NULL, 1.2, 1)
""")

conn.commit()
conn.close()

print("База данных инициализирована успешно!")
print("Таблица currency_rates создана")
print("Базовые курсы валют добавлены")
