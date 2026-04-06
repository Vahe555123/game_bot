import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.admin_routes import router as admin_router
from app.api.routes import router as api_router
from app.api.site_admin_routes import router as site_admin_router
from app.api.site_auth_routes import router as site_auth_router
from app.api.site_content_routes import router as site_content_router
from app.api.site_purchase_routes import router as site_purchase_router
from app.auth.mongo import init_mongo_indexes
from app.bot.main import setup_bot, shutdown_bot
from app.webapp.routes import router as webapp_router
from config.settings import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing application...")

    from app.database.connection import init_database

    init_database()
    init_mongo_indexes()

    if settings.TELEGRAM_BOT_TOKEN:
        await setup_bot(app)
    else:
        logger.warning("TELEGRAM_BOT_TOKEN is not set. Bot startup skipped.")

    logger.info("=" * 60)
    logger.info("%s v%s started", settings.PROJECT_NAME, settings.VERSION)
    logger.info("API docs: http://%s:%s/api/docs", settings.HOST, settings.PORT)
    logger.info("WebApp: http://%s:%s/", settings.HOST, settings.PORT)
    logger.info("=" * 60)

    yield

    logger.info("Shutting down application...")
    if settings.TELEGRAM_BOT_TOKEN:
        await shutdown_bot()
    logger.info("Application stopped")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API for the PlayStation Store Telegram bot and website",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Users", "description": "Telegram user operations"},
        {"name": "Products", "description": "PlayStation Store catalog"},
        {"name": "Favorites", "description": "Favorite products management"},
        {"name": "WebApp", "description": "Telegram WebApp pages"},
        {"name": "Admin", "description": "Administration endpoints"},
        {"name": "Site Auth", "description": "Website authentication endpoints"},
        {"name": "Site Admin", "description": "Website administration endpoints"},
        {"name": "Site Orders", "description": "Website purchase and delivery endpoints"},
        {"name": "System", "description": "System endpoints"},
    ],
)

cors_middleware_kwargs = {
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}

if settings.CORS_ALLOW_ALL:
    cors_middleware_kwargs["allow_origin_regex"] = ".*"
else:
    cors_middleware_kwargs["allow_origins"] = settings.ALLOWED_ORIGINS

app.add_middleware(CORSMiddleware, **cors_middleware_kwargs)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(api_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(site_auth_router, prefix="/api")
app.include_router(site_admin_router, prefix="/api")
app.include_router(site_content_router, prefix="/api")
app.include_router(site_purchase_router, prefix="/api")
app.include_router(webapp_router, prefix="", tags=["WebApp"])


@app.get("/", tags=["System"], summary="Root endpoint")
async def root():
    return RedirectResponse(url="/webapp", status_code=302)


@app.get("/health", tags=["System"], summary="Health check")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
