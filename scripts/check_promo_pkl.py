"""
Скрипт для проверки содержимого promo.pkl
"""
import pickle
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_promo_pkl():
    """Проверить содержимое promo.pkl"""
    promo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'promo.pkl')
    
    if not os.path.exists(promo_path):
        print(f"❌ Файл promo.pkl не найден: {promo_path}")
        return
    
    print(f"📊 Проверка promo.pkl: {promo_path}")
    print("=" * 80)
    
    with open(promo_path, "rb") as file:
        promo_data = pickle.load(file)
    
    # Проверяем формат
    if isinstance(promo_data, dict):
        print("\n✓ Формат: dict (новый формат)")
        print(f"  - Extra: {len(promo_data.get('Extra', set()))} игр")
        print(f"  - Deluxe: {len(promo_data.get('Deluxe', set()))} игр")
        print(f"  - All: {len(promo_data.get('All', set()))} игр")
        
        # Показываем примеры
        extra_set = promo_data.get('Extra', set())
        deluxe_set = promo_data.get('Deluxe', set())
        
        if extra_set:
            print(f"\nПримеры игр из Extra (первые 5):")
            for i, game in enumerate(list(extra_set)[:5]):
                print(f"  {i+1}. {game}")
        
        if deluxe_set:
            print(f"\nПримеры игр из Deluxe (только Deluxe, первые 5):")
            for i, game in enumerate(list(deluxe_set)[:5]):
                print(f"  {i+1}. {game}")
    elif isinstance(promo_data, list):
        print("\n⚠ Формат: list (старый формат)")
        print(f"  - Всего игр: {len(promo_data)}")
        print(f"\nПримеры игр (первые 5):")
        for i, game in enumerate(promo_data[:5]):
            print(f"  {i+1}. {game}")
    else:
        print(f"\n❌ Неизвестный формат: {type(promo_data)}")
    
    print("\n" + "=" * 80)
    print("✅ Проверка завершена")

if __name__ == "__main__":
    check_promo_pkl()

