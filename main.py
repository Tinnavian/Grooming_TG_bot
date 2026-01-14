import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_IDS
from database import init_db
from handlers.user_handlers import user_router
from handlers.admin_handlers import admin_router

# Создаём папку логов если её нет
os.makedirs("logs", exist_ok=True)

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Боты и диспетчер
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Регистрация роутеров
dp.include_router(user_router)
dp.include_router(admin_router)


async def on_startup():
    """Инициализация при запуске"""
    await init_db()
    logger.info(f"✅ Бот запущен. Админы: {ADMIN_IDS}")


async def main():
    """Главная функция"""
    await on_startup()
    
    try:
        logger.info("🚀 Бот слушает обновления...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
