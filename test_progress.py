"""
Тестовый скрипт для проверки системы прогресса
"""
import json
import os

PROGRESS_FILE = "progress.json"

def show_progress():
    """Показывает текущий прогресс"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print("\n" + "=" * 60)
            print(" ТЕКУЩИЙ ПРОГРЕСС ПАРСИНГА")
            print("=" * 60)
            print(f" Всего товаров: {data['total_items']}")
            print(f" Обработано: {data['processed_items']}")
            print(f" Прогресс: {data['last_saved_percent']}%")
            print(f" Следующая позиция: {data['start_index']}")
            print(f" Время сохранения: {data['timestamp']}")
            print("=" * 60)
    else:
        print("\n⚠ Файл прогресса не найден")

def clear_progress():
    """Очищает прогресс"""
    files = ["progress.json", "checkpoint.pkl"]
    for f in files:
        if os.path.exists(f):
            os.remove(f)
            print(f"✓ Удален {f}")
    print("\n✓ Прогресс очищен")

if __name__ == "__main__":
    print("\n1. Показать прогресс")
    print("2. Очистить прогресс")
    choice = input("\nВыберите действие: ").strip()

    if choice == "1":
        show_progress()
    elif choice == "2":
        clear_progress()
    else:
        print("Неверный выбор")
