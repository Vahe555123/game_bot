from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from config.settings import settings
from app.database.connection import create_tables
from app.api.routes import router as api_router
from app.api.admin_routes import router as admin_router
from app.webapp.routes import router as webapp_router
from app.bot.main import setup_bot, shutdown_bot
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

# Lifespan event handler для управления запуском и остановкой
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("🔄 Инициализация приложения...")

    # Инициализация базы данных
    from app.database.connection import init_database
    init_database()

    # Настройка Telegram бота
    if settings.TELEGRAM_BOT_TOKEN:
        await setup_bot(app)
    else:
        logger.warning("⚠️  TELEGRAM_BOT_TOKEN не установлен. Бот не будет запущен.")

    logger.info("=" * 60)
    logger.info(f"🚀 {settings.PROJECT_NAME} v{settings.VERSION} запущен!")
    logger.info(f"📊 API документация: http://{settings.HOST}:{settings.PORT}/api/docs")
    logger.info(f"🌐 WebApp: http://{settings.HOST}:{settings.PORT}/")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("🛑 Остановка приложения...")
    if settings.TELEGRAM_BOT_TOKEN:
        await shutdown_bot()
    logger.info("👋 Приложение остановлено")

# Создание FastAPI приложения
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API для Telegram WebApp магазина PlayStation Store",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Users",
            "description": "Операции с пользователями Telegram",
        },
        {
            "name": "Products",
            "description": "Каталог товаров PlayStation Store",
        },
        {
            "name": "Favorites",
            "description": "Управление избранными товарами пользователей",
        },
        {
            "name": "WebApp",
            "description": "HTML страницы Telegram WebApp",
        },
        {
            "name": "Admin",
            "description": "Административная панель",
        },
        {
            "name": "System",
            "description": "Системные эндпоинты",
        }
    ]
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключение роутов
app.include_router(api_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(webapp_router, prefix="", tags=["WebApp"])

# Главная страница - перенаправление на WebApp
@app.get("/", tags=["System"], summary="Корневой эндпоинт")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/webapp", status_code=302)

# Проверка здоровья приложения
@app.get("/health", tags=["System"], summary="Проверка состояния")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
