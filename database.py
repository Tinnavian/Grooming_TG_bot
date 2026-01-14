import os
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, create_engine, Text, Boolean, JSON
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

DATABASE_URL = "sqlite+aiosqlite:///./db/database.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False}
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


# Модели
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    tg_user_id = Column(Integer, unique=True, nullable=False)
    first_name = Column(String)
    phone = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    requests = relationship("Request", back_populates="user")


class Master(Base):
    __tablename__ = "masters"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    specialty = Column(String)  # "стрижка", "мытьё", "все"
    phone = Column(String)
    is_active = Column(Boolean, default=True)
    schedule = Column(JSON, default={})  # {"пн": ["10:00-14:00", "15:00-20:00"], ...}
    created_at = Column(DateTime, default=datetime.utcnow)
    
    requests = relationship("Request", back_populates="master")


class Request(Base):
    __tablename__ = "requests"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=True)
    service = Column(String, nullable=False)
    desired_date = Column(String, nullable=False)
    desired_time = Column(String, nullable=False)
    pet_name = Column(String, nullable=False)
    comment = Column(String)
    status = Column(String, default="new")  # new, approved, rejected, canceled, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="requests")
    master = relationship("Master", back_populates="requests")


class FAQLog(Base):
    __tablename__ = "faq_logs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    question = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConfigItem(Base):
    __tablename__ = "config"
    
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


async def init_db():
    """Инициализация БД"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    """Получить сессию"""
    async with async_session() as session:
        yield session
