from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "PlayStation Store SQLite WebApp"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./products.db")

    # If true, skip syncing the FTS5 table on startup (instant boot; catalog search may be stale until rebuild).
    SQLITE_SKIP_FTS_REBUILD_ON_STARTUP: bool = os.getenv(
        "SQLITE_SKIP_FTS_REBUILD_ON_STARTUP", "false"
    ).lower() in ("1", "true", "yes")
    PRODUCTS_REBUILD_ON_STARTUP: bool = os.getenv("PRODUCTS_REBUILD_ON_STARTUP", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    PRODUCTS_REBUILD_ALWAYS: bool = os.getenv("PRODUCTS_REBUILD_ALWAYS", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    PRODUCTS_REBUILD_DELETE_STALE: bool = os.getenv("PRODUCTS_REBUILD_DELETE_STALE", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    PRODUCTS_RESULT_CACHE_PATH: str = os.getenv("PRODUCTS_RESULT_CACHE_PATH", "result.pkl")
    PRODUCTS_PROMO_CACHE_PATH: str = os.getenv("PRODUCTS_PROMO_CACHE_PATH", "promo.pkl")
    PRODUCTS_REBUILD_BATCH_SIZE: int = int(os.getenv("PRODUCTS_REBUILD_BATCH_SIZE", 1000))

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_URL: str = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "")
    MANAGER_TELEGRAM_URL: str = os.getenv("MANAGER_TELEGRAM_URL", "")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    CORS_ALLOW_ALL: bool = os.getenv("CORS_ALLOW_ALL", "true").lower() == "true"

    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        origins = [
            "https://web.telegram.org",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]

        extra_origins = os.getenv("CORS_ORIGINS", "")
        if extra_origins:
            for raw_origin in extra_origins.split(","):
                origin = raw_origin.strip()
                if origin and origin not in origins:
                    origins.append(origin)

        if self.WEBAPP_URL:
            webapp_origin = self.WEBAPP_URL.replace("/webapp", "")
            if webapp_origin not in origins:
                origins.append(webapp_origin)
        return origins

    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024

    AUTH_PASSWORD_MIN_LENGTH: int = int(os.getenv("AUTH_PASSWORD_MIN_LENGTH", 8))
    AUTH_EMAIL_CODE_LENGTH: int = int(os.getenv("AUTH_EMAIL_CODE_LENGTH", 6))
    AUTH_EMAIL_CODE_TTL_MINUTES: int = int(os.getenv("AUTH_EMAIL_CODE_TTL_MINUTES", 10))
    AUTH_EMAIL_RESEND_COOLDOWN_SECONDS: int = int(os.getenv("AUTH_EMAIL_RESEND_COOLDOWN_SECONDS", 60))
    AUTH_EMAIL_MAX_ATTEMPTS: int = int(os.getenv("AUTH_EMAIL_MAX_ATTEMPTS", 5))
    AUTH_SESSION_TTL_DAYS: int = int(os.getenv("AUTH_SESSION_TTL_DAYS", 30))
    AUTH_SESSION_COOKIE_NAME: str = os.getenv("AUTH_SESSION_COOKIE_NAME", "site_session")
    AUTH_COOKIE_SECURE: bool = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
    AUTH_COOKIE_SAMESITE: str = os.getenv("AUTH_COOKIE_SAMESITE", "lax")
    AUTH_OAUTH_STATE_SECRET: str = os.getenv("AUTH_OAUTH_STATE_SECRET", os.getenv("ADMIN_SECRET_KEY", "oauth-state-secret"))
    AUTH_OAUTH_STATE_TTL_SECONDS: int = int(os.getenv("AUTH_OAUTH_STATE_TTL_SECONDS", 600))
    AUTH_TELEGRAM_LOGIN_TTL_SECONDS: int = int(os.getenv("AUTH_TELEGRAM_LOGIN_TTL_SECONDS", 300))
    PUBLIC_APP_URL: str = os.getenv("PUBLIC_APP_URL", "http://localhost:5173").rstrip("/")
    DIGISELLER_FAILPAGE_URL: str = os.getenv("DIGISELLER_FAILPAGE_URL", "").rstrip("/")
    AUTH_DEFAULT_REDIRECT_PATH: str = os.getenv("AUTH_DEFAULT_REDIRECT_PATH", "/profile")

    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_APP_PASSWORD: str = os.getenv("SMTP_APP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", os.getenv("SMTP_USERNAME", ""))
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "PlayStation Store")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    VK_CLIENT_ID: str = os.getenv("VK_CLIENT_ID", "")
    VK_CLIENT_SECRET: str = os.getenv("VK_CLIENT_SECRET", "")
    TELEGRAM_BOT_USERNAME: str = os.getenv("TELEGRAM_BOT_USERNAME", "")

    DEFAULT_CURRENCY: str = "RUB"
    SUPPORTED_CURRENCIES: list[str] = ["UAH", "TRL", "INR", "RUB"]

    @property
    def ADMIN_TELEGRAM_IDS(self) -> list[int]:
        admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "") or os.getenv("ADMIN_TELEGRAM_ID", "")
        if not admin_ids_str:
            return []

        admin_ids: list[int] = []
        seen_ids: set[int] = set()
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

    @property
    def GOOGLE_REDIRECT_URI(self) -> str:
        return f"{self.PUBLIC_APP_URL}/api/auth/oauth/google/callback"

    @property
    def VK_REDIRECT_URI(self) -> str:
        return f"{self.PUBLIC_APP_URL}/api/auth/oauth/vk/callback"

    class Config:
        case_sensitive = True


settings = Settings()
