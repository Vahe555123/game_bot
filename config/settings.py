import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Настройки приложения
    PROJECT_NAME: str = "PlayStation Store Telegram WebApp"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Настройки базы данных
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./products.db")
    
    # Настройки Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_URL: str = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "")
    MANAGER_TELEGRAM_URL: str = os.getenv("MANAGER_TELEGRAM_URL", "")
    
    # Настройки FastAPI
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    
    # Настройки CORS
    @property
    def ALLOWED_ORIGINS(self) -> list:
        origins = [
            "https://web.telegram.org",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
        # Добавляем WEBAPP_URL если он задан
        if self.WEBAPP_URL:
            webapp_origin = self.WEBAPP_URL.replace('/webapp', '')
            if webapp_origin not in origins:
                origins.append(webapp_origin)
        return origins
    
    # Настройки файлов
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # Настройки валют
    DEFAULT_CURRENCY: str = "RUB"
    SUPPORTED_CURRENCIES: list = ["UAH", "TRL", "INR", "RUB"]
    
    # Настройки администрирования
    @property
    def ADMIN_TELEGRAM_IDS(self) -> list:
        """Список Telegram ID администраторов"""
        admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "") or os.getenv("ADMIN_TELEGRAM_ID", "")
        if not admin_ids_str:
            return []

        admin_ids = []
        seen_ids = set()

        for raw_user_id in admin_ids_str.split(","):
            user_id = raw_user_id.strip()
            if not user_id:
                continue

            try:
                parsed_id = int(user_id)
            except ValueError:
                continue

            if parsed_id in seen_ids:
                continue

            seen_ids.add(parsed_id)
            admin_ids.append(parsed_id)

        return admin_ids
    
    ADMIN_SECRET_KEY: str = os.getenv("ADMIN_SECRET_KEY", "your-secret-admin-key-here")
    
    class Config:
        case_sensitive = True

settings = Settings() 
