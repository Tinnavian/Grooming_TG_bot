from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select
from datetime import datetime
import logging

from database import Request, User, async_session
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
admin_router = Router()


async def get_request_card(request: Request) -> str:
    """Форматирование карточки заявки для админа"""
    async with async_session() as session:
        stmt = select(User).where(User.id == request.user_id)
        result = await session.execute(stmt)
        user = result.scalar()
    
    card = (
        f"📋 НОВАЯ ЗАЯВКА\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Услуга: {request.service}\n"
        f"📅 Дата: {request.desired_date}\n"
        f"⏰ Время: {request.desired_time}\n"
        f"🐕 Питомец: {request.pet_name}\n"
        f"☎️ Телефон: {user.phone or 'не указан'}\n"
        f"💬 Комментарий: {request.comment or 'нет'}\n"
        f"👤 Клиент: {user.first_name} (@{user.tg_user_id})\n"
        f"🆔 ID заявки: {request.id}"
    )
    return card


async def send_request_to_admins(bot, request: Request):
    """Отправка заявки всем админам"""
    card = await get_request_card(request)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve:{request.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{request.id}")
        ],
        [InlineKeyboardButton(text="🤔 Уточнить", callback_data=f"clarify:{request.id}")]
    ])
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, card, reply_markup=kb)
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")


# Подтверждение заявки (админ)
@admin_router.callback_query(F.data.startswith("approve:"))
async def approve_request(query: CallbackQuery, bot):
    """Подтвердить заявку"""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    request_id = int(query.data.split(":")[1])
    
    async with async_session() as session:
        stmt = select(Request).where(Request.id == request_id)
        result = await session.execute(stmt)
        request = result.scalar()
        
        if not request:
            await query.answer("❌ Заявка не найдена", show_alert=True)
            return
        
        request.status = "approved"
        await session.commit()
    
    # Уведомление клиенту
    async with async_session() as session:
        stmt = select(User).where(User.id == request.user_id)
        result = await session.execute(stmt)
        user = result.scalar()
    
    try:
        await bot.send_message(
            user.tg_user_id,
            f"✅ Ваша заявка подтверждена!\n"
            f"📅 {request.desired_date}\n"
            f"⏰ {request.desired_time}\n"
            f"🐕 {request.pet_name}\n\n"
            f"До скорого встречи! 🐕"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления клиенту {user.tg_user_id}: {e}")
    
    await query.message.edit_text(
        f"✅ Заявка #{request_id} подтверждена. Клиент уведомлен."
    )
    await query.answer("✅ Заявка подтверждена")


# Отклонение заявки (админ)
@admin_router.callback_query(F.data.startswith("reject:"))
async def reject_request(query: CallbackQuery, bot):
    """Отклонить заявку"""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    request_id = int(query.data.split(":")[1])
    
    async with async_session() as session:
        stmt = select(Request).where(Request.id == request_id)
        result = await session.execute(stmt)
        request = result.scalar()
        
        if not request:
            await query.answer("❌ Заявка не найдена", show_alert=True)
            return
        
        request.status = "rejected"
        await session.commit()
    
    # Уведомление клиенту
    async with async_session() as session:
        stmt = select(User).where(User.id == request.user_id)
        result = await session.execute(stmt)
        user = result.scalar()
    
    try:
        from handlers.user_handlers import get_main_keyboard
        
        await bot.send_message(
            user.tg_user_id,
            f"❌ К сожалению, на выбранное время {request.desired_date} {request.desired_time} нет мест.\n\n"
            f"Выбери другое время или задай вопрос админу:",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка отправки отклонения клиенту {user.tg_user_id}: {e}")
    
    await query.message.edit_text(
        f"❌ Заявка #{request_id} отклонена. Клиент уведомлен."
    )
    await query.answer("❌ Заявка отклонена")


# Уточнение (админ просто отвечает в чат)
@admin_router.callback_query(F.data.startswith("clarify:"))
async def clarify_request(query: CallbackQuery):
    """Админ отмечает, что уточняет"""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    request_id = int(query.data.split(":")[1])
    
    await query.answer(
        f"📌 Заявка #{request_id} помечена на уточнение.\n"
        f"Ответь клиенту в этом чате (переходи на чат с клиентом).",
        show_alert=True
    )
