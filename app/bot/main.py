import logging
import asyncio
import sys
import os

# Добавляем корневую папку проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo, ErrorEvent
from config.settings import settings
from app.database.connection import get_db_session
from app.api.crud import user_crud
from app.api.schemas import UserCreate

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

async def create_or_update_user(tg_user: types.User) -> None:
    """Создать или обновить пользователя в базе данных"""
    try:
        with get_db_session() as db:
            user_data = UserCreate(
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                language_code=tg_user.language_code or 'ru'
            )
            
            user, created = user_crud.get_or_create(db, user_data)
            
            if created:
                logger.info(f"Создан новый пользователь: {tg_user.id} (@{tg_user.username})")
            else:
                logger.info(f"Пользователь найден: {tg_user.id} (@{tg_user.username})")
                
    except Exception as e:
        logger.error(f"Ошибка при создании пользователя {tg_user.id}: {e}")

@dp.message(CommandStart())
async def start_command(message: types.Message) -> None:
    """Обработчик команды /start"""
    user = message.from_user
    
    # Логируем получение команды
    logger.info("=" * 60)
    logger.info(f"📥 Получена команда /start от пользователя:")
    logger.info(f"  • ID: {user.id}")
    logger.info(f"  • Username: @{user.username if user.username else 'не указан'}")
    logger.info(f"  • Имя: {user.first_name} {user.last_name or ''}")
    logger.info(f"  • Язык: {user.language_code or 'не указан'}")
    logger.info("=" * 60)
    
    # Создание пользователя в базе данных
    await create_or_update_user(user)
    
    # URL для WebApp (должен быть HTTPS для Telegram)
    if settings.WEBAPP_URL:
        webapp_url = settings.WEBAPP_URL
        logger.info(f"Используется настроенный WEBAPP_URL: {webapp_url}")
    else:
        # Используем ваш текущий tunnel URL
        webapp_url = "https://soundlessly-pioneering-springtail.cloudpub.ru/webapp"
        logger.warning(f"WEBAPP_URL не настроен, используется tunnel URL: {webapp_url}")
        logger.warning("Настройте WEBAPP_URL в .env файле для продакшена")
    
    # Создаем кнопку с WebApp
    webapp_button = KeyboardButton(
        text="🎮 Открыть магазин PlayStation",
        web_app=WebAppInfo(url=webapp_url)
    )
    
    # Логируем для отладки
    logger.info(f"Создана WebApp кнопка с URL: {webapp_url}")
    logger.info(f"Пользователь: {user.id} (@{user.username}) - {user.first_name}")
    
    # Создаем клавиатуру
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[webapp_button]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    welcome_message = f"""
🎮 Добро пожаловать в PlayStation Store, {user.first_name}!

Здесь вы можете23:
• Просматривать каталог игр PlayStation
• Фильтровать товары по категориям и ценам
• Добавлять игры в избранное
• Отслеживать скидки и акции

Нажмите кнопку ниже, чтобы открыть магазин:
    """
    
    await message.reply(
        welcome_message,
        reply_markup=keyboard
    )

@dp.message(Command("help"))
async def help_command(message: types.Message) -> None:
    """Обработчик команды /help"""
    help_text = """
🆘 Помощь по использованию бота:

/start - Запустить бота и открыть магазин
/help - Показать это сообщение
/settings - Настройки профиля

🎮 Функции магазина:
• Просмотр каталога игр
• Поиск по названию
• Фильтрация по категориям
• Сортировка по цене
• Добавление в избранное
• Просмотр скидок

💰 Поддерживаемые валюты:
• UAH (Украинские гривны)
• TRL (Турецкие лиры)

🌍 Поддерживаемые регионы:
• Украина (UA)
• Турция (TR)
    """
    
    await message.reply(help_text)

@dp.message(Command("settings"))
async def settings_command(message: types.Message) -> None:
    """Обработчик команды /settings"""
    settings_text = """
⚙️ Настройки профиля:

Для изменения настроек (валюта, регион) используйте WebApp магазина.
Ваши предпочтения сохраняются автоматически.

Текущие настройки можно посмотреть в разделе "Профиль" в магазине.
    """
    
    await message.reply(settings_text)

@dp.error()
async def error_handler(event: ErrorEvent):
    """Обработчик ошибок"""
    logger.error(f"Произошла ошибка: {event.exception}")
    logger.error(f"Update: {event.update}")
    return True

async def setup_bot(app=None) -> None:
    """Настройка и запуск Telegram бота"""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("⚠️  TELEGRAM_BOT_TOKEN не установлен. Бот не будет запущен.")
        logger.warning("   Получите токен у @BotFather и добавьте в .env файл")
        return
    
    # Получаем информацию о боте
    logger.info("🔍 Проверка подключения к Telegram API...")
    try:
        import asyncio
        # Добавляем timeout чтобы не зависать
        bot_info = await asyncio.wait_for(bot.get_me(), timeout=10.0)
        logger.info("=" * 60)
        logger.info("📱 ИНФОРМАЦИЯ О TELEGRAM БОТЕ:")
        logger.info(f"  • Имя: {bot_info.first_name}")
        logger.info(f"  • Username: @{bot_info.username}")
        logger.info(f"  • ID: {bot_info.id}")
        logger.info("=" * 60)
    except asyncio.TimeoutError:
        logger.error("❌ Timeout при подключении к Telegram API (10 сек)")
        logger.error("   Проверьте интернет-соединение или используйте VPN/прокси")
        logger.warning("⚠️  Бот не будет запущен")
        return
    except Exception as e:
        logger.error(f"❌ Не удалось получить информацию о боте: {e}")
        logger.error(f"   Тип ошибки: {type(e).__name__}")
        logger.error("   Проверьте корректность TELEGRAM_BOT_TOKEN и доступ к Telegram API")
        logger.warning("⚠️  Бот не будет запущен")
        return
    
    # Запуск бота в режиме polling (для разработки)
    if settings.DEBUG:
        logger.info("🔄 Запуск бота в режиме polling (режим разработки)...")
        
        async def start_polling():
            try:
                logger.info("✅ Бот готов к приему команд!")
                await dp.start_polling(bot)
            except Exception as e:
                logger.error(f"❌ Ошибка при polling: {e}")
        
        # Запускаем в отдельной задаче
        asyncio.create_task(start_polling())
    else:
        # Настройка webhook для продакшена
        if settings.TELEGRAM_WEBHOOK_URL:
            logger.info(f"🌐 Настройка webhook: {settings.TELEGRAM_WEBHOOK_URL}")
            await bot.set_webhook(url=settings.TELEGRAM_WEBHOOK_URL)
            logger.info("✅ Webhook настроен успешно!")
        else:
            logger.warning("⚠️  TELEGRAM_WEBHOOK_URL не установлен для продакшена")
    
    logger.info("🚀 Telegram бот настроен и запущен!")

async def shutdown_bot():
    """Завершение работы бота"""
    logger.info("Завершение работы Telegram бота...")
    await bot.session.close()

def main():
    """Запуск бота в standalone режиме (через run_bot.py)"""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен в .env файле!")
        logger.error("Получите токен у @BotFather в Telegram и добавьте в .env файл")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("🤖 Запуск Telegram бота в standalone режиме...")
    logger.info(f"📋 Проект: {settings.PROJECT_NAME}")
    logger.info(f"🔧 Режим отладки: {settings.DEBUG}")
    
    # Инициализация базы данных
    from app.database.connection import init_database
    init_database()
    logger.info("✅ База данных инициализирована")
    
    # Запуск бота
    async def start():
        try:
            # Получаем информацию о боте
            bot_info = await bot.get_me()
            logger.info("=" * 60)
            logger.info("📱 ИНФОРМАЦИЯ О БОТЕ:")
            logger.info(f"  • Имя: {bot_info.first_name}")
            logger.info(f"  • Username: @{bot_info.username}")
            logger.info(f"  • ID: {bot_info.id}")
            logger.info(f"  • Может присоединяться к группам: {bot_info.can_join_groups}")
            logger.info(f"  • Может читать все сообщения: {bot_info.can_read_all_group_messages}")
            logger.info(f"  • Поддерживает inline: {bot_info.supports_inline_queries}")
            logger.info("=" * 60)
            logger.info("🚀 Бот успешно запущен и ожидает команды /start")
            logger.info("💡 Откройте Telegram и напишите боту /start")
            logger.info("=" * 60)
            
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске бота: {e}")
            raise
        finally:
            await bot.session.close()
    
    # Запуск асинхронного цикла
    asyncio.run(start()) 