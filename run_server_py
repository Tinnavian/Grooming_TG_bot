import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import Server, Config
import threading

from web_app import app as web_app
from config import BOT_TOKEN, ADMIN_IDS
from database import init_db
from handlers.user_handlers import user_router
from handlers.admin_handlers import admin_router
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация БД
async def init():
    await init_db()
    logger.info("✅ База данных инициализирована")

# CORS для web-панели
web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Бот
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
dp.include_router(user_router)
dp.include_router(admin_router)

async def run_bot():
    """Запуск бота"""
    try:
        logger.info("🚀 Бот слушает обновления...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

async def run_web():
    """Запуск веб-панели"""
    config = Config(
        app=web_app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = Server(config)
    await server.serve()

async def main():
    """Главная функция"""
    await init()
    logger.info(f"✅ Админы: {ADMIN_IDS}")
    logger.info("📱 Бот: Telegram @botname")
    logger.info("🌐 Web-панель: http://localhost:8000")
    
    # Запуск бота и веб-панели одновременно
    await asyncio.gather(
        run_bot(),
        run_web()
    )

if __name__ == "__main__":
    asyncio.run(main())
