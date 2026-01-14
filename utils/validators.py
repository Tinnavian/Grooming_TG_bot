import re
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import Request, User, async_session
from config import SPAM_TIMEOUT

async def validate_phone(phone: str) -> bool:
    """Проверка формата телефона"""
    pattern = r'^\+?7\d{10}$'
    return bool(re.match(pattern, phone.replace(" ", "").replace("-", "")))


async def validate_date(date_str: str) -> bool:
    """Проверка формата даты ДД.ММ.ГГГГ и что она в будущем"""
    try:
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        return date_obj > datetime.now()
    except ValueError:
        return False


async def validate_time(time_str: str) -> bool:
    """Проверка формата времени ЧЧ:ММ"""
    try:
        datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False


async def check_spam(user_id: int) -> bool:
    """Проверка спама: есть ли новая заявка меньше N минут назад"""
    async with async_session() as session:
        stmt = select(Request).where(
            Request.user_id == user_id,
            Request.status == "new"
        ).order_by(Request.created_at.desc()).limit(1)
        
        result = await session.execute(stmt)
        last_request = result.scalar()
        
        if not last_request:
            return False
        
        time_diff = (datetime.utcnow() - last_request.created_at).total_seconds() / 60
        return time_diff < SPAM_TIMEOUT


async def get_or_create_user(tg_user_id: int, first_name: str = None):
    """Получить или создать пользователя"""
    async with async_session() as session:
        stmt = select(User).where(User.tg_user_id == tg_user_id)
        result = await session.execute(stmt)
        user = result.scalar()
        
        if not user:
            user = User(tg_user_id=tg_user_id, first_name=first_name)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        
        return user
