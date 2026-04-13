"""
Тестовый скрипт для проверки создания таблиц в БД
"""
import asyncio
import aiosqlite

async def check_tables():
    """Проверяет наличие таблиц в БД"""
    db_path = "products.db"

    async with aiosqlite.connect(db_path) as db:
        # Получаем список таблиц
        cursor = await db.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)
        tables = await cursor.fetchall()

        print("\n" + "=" * 60)
        print(" ТАБЛИЦЫ В БД")
        print("=" * 60)

        if tables:
            for table in tables:
                table_name = table[0]
                print(f"\n✓ Таблица: {table_name}")

                # Получаем количество записей
                cursor = await db.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = (await cursor.fetchone())[0]
                print(f"  Записей: {count}")

                # Показываем структуру таблицы
                cursor = await db.execute(f"PRAGMA table_info({table_name})")
                columns = await cursor.fetchall()
                print(f"  Колонок: {len(columns)}")
        else:
            print("⚠ Таблицы не найдены!")

        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(check_tables())
