from handlers.admin_handlers import send_request_to_admins
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from datetime import datetime
import logging

from database import User, Request, async_session, FAQLog
from config import FAQ, SERVICES
from utils.validators import (
    validate_phone, validate_date, validate_time, 
    check_spam, get_or_create_user
)

logger = logging.getLogger(__name__)
user_router = Router()


# FSM для записи
class BookingStates(StatesGroup):
    service = State()
    date = State()
    time = State()
    pet_name = State()
    phone = State()
    comment = State()


class FAQStates(StatesGroup):
    waiting_question = State()


# Главное меню
def get_main_keyboard():
    """Главное меню"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Записаться", callback_data="book")],
        [InlineKeyboardButton(text="💰 Прайс", callback_data="faq:price")],
        [InlineKeyboardButton(text="📍 Адрес и график", callback_data="faq:address")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="show_faq")],
        [InlineKeyboardButton(text="💬 Задать вопрос", callback_data="ask_question")],
        [InlineKeyboardButton(text="📋 Мои заявки", callback_data="my_requests")]
    ])
    return kb


# /start
@user_router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработка /start"""
    user = await get_or_create_user(message.from_user.id, message.from_user.first_name)
    await message.answer(
        f"🐕 Привет, {message.from_user.first_name}!\n"
        f"Добро пожаловать в груминг-салон! Выбери действие:",
        reply_markup=get_main_keyboard()
    )


# Запись на услугу
@user_router.callback_query(F.data == "book")
async def book_start(query: CallbackQuery, state: FSMContext):
    """Начало записи"""
    # Проверка спама
    if await check_spam(query.from_user.id):
        await query.answer("⏳ Подождите 3 минуты перед новой заявкой", show_alert=True)
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=service_name, callback_data=f"service:{code}")]
        for code, service_name in SERVICES.items()
    ] + [[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]])
    
    await query.message.edit_text("Выбери услугу:", reply_markup=kb)
    await state.set_state(BookingStates.service)


# Выбор услуги
@user_router.callback_query(F.data.startswith("service:"), BookingStates.service)
async def book_service(query: CallbackQuery, state: FSMContext):
    """Выбор услуги"""
    service_code = query.data.split(":")[1]
    await state.update_data(service=service_code)
    
    await query.message.edit_text(
        "Дата в формате ДД.ММ.ГГГГ (например, 15.01.2026):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
    )
    await state.set_state(BookingStates.date)


# Дата
@user_router.message(BookingStates.date)
async def book_date(message: Message, state: FSMContext):
    """Ввод даты"""
    if not await validate_date(message.text):
        await message.answer("❌ Неверный формат. Используй ДД.ММ.ГГГГ (будущая дата):")
        return
    
    await state.update_data(date=message.text)
    await message.answer(
        "Время в формате ЧЧ:ММ (например, 10:30):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
    )
    await state.set_state(BookingStates.time)


# Время
@user_router.message(BookingStates.time)
async def book_time(message: Message, state: FSMContext):
    """Ввод времени"""
    if not await validate_time(message.text):
        await message.answer("❌ Неверный формат. Используй ЧЧ:ММ (10:30):")
        return
    
    await state.update_data(time=message.text)
    await message.answer(
        "Кличка питомца:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
    )
    await state.set_state(BookingStates.pet_name)


# Кличка
@user_router.message(BookingStates.pet_name)
async def book_pet(message: Message, state: FSMContext):
    """Ввод клички"""
    await state.update_data(pet_name=message.text)
    await message.answer(
        "Телефон (+7...):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
    )
    await state.set_state(BookingStates.phone)


# Телефон
@user_router.message(BookingStates.phone)
async def book_phone(message: Message, state: FSMContext):
    """Ввод телефона"""
    if not await validate_phone(message.text):
        await message.answer("❌ Неверный формат. Используй +7XXXXXXXXXX:")
        return
    
    await state.update_data(phone=message.text)
    await message.answer(
        "Комментарий (или напиши 'нет'):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
    )
    await state.set_state(BookingStates.comment)


# Комментарий
@user_router.message(BookingStates.comment)
async def book_comment(message: Message, state: FSMContext):
    """Ввод комментария и сохранение"""
    comment = message.text if message.text.lower() != "нет" else None
    
    data = await state.get_data()
    user = await get_or_create_user(message.from_user.id, message.from_user.first_name)
    
    # Сохранение в БД
    async with async_session() as session:
        request = Request(
            user_id=user.id,
            service=data["service"],
            desired_date=data["date"],
            desired_time=data["time"],
            pet_name=data["pet_name"],
            comment=comment,
            status="new"
        )
        session.add(request)
        await session.commit()
        await session.refresh(request)  # Добавили обновление объекта
    
    # Обновление телефона пользователя
    async with async_session() as session:
        stmt = select(User).where(User.tg_user_id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar()
        user.phone = data["phone"]
        await session.commit()
    
    # 🟢 ОТПРАВКА АДМИНУ (НОВОЕ)
    async with async_session() as session:
        stmt = select(Request).where(Request.id == request.id)
        result = await session.execute(stmt)
        req_to_send = result.scalar()
        await send_request_to_admins(message.bot, req_to_send)
    
    await message.answer(
        "✅ Заявка отправлена админу!\n"
        "Скоро мы подтвердим запись. Спасибо! 🐕",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()


# FAQ меню
@user_router.callback_query(F.data == "show_faq")
async def show_faq_menu(query: CallbackQuery):
    """Меню FAQ"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=faq_item["question"], callback_data=f"faq:{code}")]
        for code, faq_item in FAQ.items()
    ] + [[InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]])
    
    await query.message.edit_text("❓ Выбери вопрос:", reply_markup=kb)


# Ответ на FAQ
@user_router.callback_query(F.data.startswith("faq:"))
async def faq_answer(query: CallbackQuery):
    """Ответ из FAQ"""
    faq_code = query.data.split(":")[1]
    
    if faq_code not in FAQ:
        await query.answer("❌ Вопрос не найден", show_alert=True)
        return
    
    faq_item = FAQ[faq_code]
    
    # Логирование
    async with async_session() as session:
        user = await get_or_create_user(query.from_user.id, query.from_user.first_name)
        log = FAQLog(user_id=user.id, question=faq_item["question"])
        session.add(log)
        await session.commit()
    
    await query.message.edit_text(
        f"❓ {faq_item['question']}\n\n{faq_item['answer']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="show_faq")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_menu")]
        ])
    )


# Задать вопрос
@user_router.callback_query(F.data == "ask_question")
async def ask_question_start(query: CallbackQuery, state: FSMContext):
    """Начало диалога "Задать вопрос" """
    await query.message.edit_text(
        "💬 Напиши свой вопрос (админ скоро ответит):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
    )
    await state.set_state(FAQStates.waiting_question)


@user_router.message(FAQStates.waiting_question)
async def ask_question_handler(message: Message, state: FSMContext):
    """Получение вопроса и отправка админу"""
    user = await get_or_create_user(message.from_user.id, message.from_user.first_name)
    
    # Логирование
    async with async_session() as session:
        log = FAQLog(user_id=user.id, question=message.text)
        session.add(log)
        await session.commit()
    
    await message.answer(
        "✅ Вопрос отправлен!\n"
        "Админ ответит тебе в этом чате в ближайшее время.",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()


# Мои заявки
@user_router.callback_query(F.data == "my_requests")
async def my_requests(query: CallbackQuery):
    """Показать последние 5 заявок"""
    user = await get_or_create_user(query.from_user.id, query.from_user.first_name)
    
    async with async_session() as session:
        stmt = select(Request).where(
            Request.user_id == user.id
        ).order_by(Request.created_at.desc()).limit(5)
        
        result = await session.execute(stmt)
        requests = result.scalars().all()
    
    if not requests:
        await query.answer("У тебя еще нет заявок", show_alert=True)
        return
    
    text = "📋 Твои заявки:\n\n"
    for i, req in enumerate(requests, 1):
        status_emoji = {
            "new": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "canceled": "🚫"
        }.get(req.status, "❓")
        
        text += f"{i}. {status_emoji} {req.service}\n"
        text += f"   📅 {req.desired_date} {req.desired_time}\n"
        text += f"   🐕 {req.pet_name}\n"
        text += f"   Статус: {req.status}\n\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_menu")]
    ])
    
    await query.message.edit_text(text, reply_markup=kb)


# Отмена (универсальная)
@user_router.callback_query(F.data == "cancel")
async def cancel_handler(query: CallbackQuery, state: FSMContext):
    """Отмена в процессе"""
    await state.clear()
    await query.message.delete()
    await query.message.answer("❌ Отменено", reply_markup=get_main_keyboard())


# Назад в меню
@user_router.callback_query(F.data == "back_menu")
async def back_to_menu(query: CallbackQuery):
    """Назад в главное меню"""
    await query.message.edit_text(
        "🏠 Главное меню",
        reply_markup=get_main_keyboard()
    )
