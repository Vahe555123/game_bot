"""
Утилиты для хранения PSN паролей (упрощенная версия без шифрования)

ВНИМАНИЕ: Пароли хранятся в открытом виде в base64. 
Для продакшена рекомендуется использовать полноценное шифрование.
"""
import base64
import secrets


def encrypt_password(password: str) -> tuple[str, str]:
    """
    "Шифрует" пароль (просто кодирует в base64)
    
    Args:
        password: Пароль для кодирования
        
    Returns:
        tuple: (encoded_password, salt) - закодированный пароль и соль
    """
    if not password:
        return "", ""
    
    # Генерируем соль для совместимости с интерфейсом
    salt = secrets.token_hex(16)
    
    # Кодируем пароль в base64 для "обфускации"
    encoded_password = base64.b64encode(password.encode('utf-8')).decode('utf-8')
    
    return encoded_password, salt


def decrypt_password(encoded_password: str, salt: str) -> str:
    """
    "Расшифровывает" пароль (декодирует из base64)
    
    Args:
        encoded_password: Закодированный пароль в base64
        salt: Соль (не используется, но оставлена для совместимости)
        
    Returns:
        str: Расшифрованный пароль или пустая строка в случае ошибки
    """
    if not encoded_password:
        return ""
    
    try:
        # Декодируем из base64
        password = base64.b64decode(encoded_password.encode('utf-8')).decode('utf-8')
        return password
        
    except Exception as e:
        print(f"Error decoding password: {e}")
        return ""


def verify_password(password: str, encoded_password: str, salt: str) -> bool:
    """
    Проверяет правильность пароля
    
    Args:
        password: Пароль для проверки
        encoded_password: Закодированный пароль
        salt: Соль (не используется)
        
    Returns:
        bool: True если пароль правильный
    """
    decoded = decrypt_password(encoded_password, salt)
    return decoded == password