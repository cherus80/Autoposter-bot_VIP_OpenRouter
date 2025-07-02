# database/models.py - Модели базы данных
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from typing import Optional

Base = declarative_base()

class Post(Base):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    topic = Column(String(255))
    post_type = Column(String(50))
    image_url = Column(String(500))
    with_image = Column(Boolean, default=False, nullable=False)
    
    # Статусы публикации
    telegram_published = Column(Boolean, default=False)
    vk_published = Column(Boolean, default=False)
    
    # ID постов в социальных сетях для получения статистики
    telegram_message_id = Column(String(100))  # ID сообщения в Telegram
    vk_post_id = Column(String(100))           # ID поста в VK
    
    # Планирование
    scheduled_for = Column(DateTime)
    published_at = Column(DateTime)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Settings(Base):
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    description = Column(String(255))
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class PostStats(Base):
    __tablename__ = 'post_stats'
    
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer)
    platform = Column(String(50))  # telegram, vk
    
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    
    recorded_at = Column(DateTime, default=func.now())

# --- НОВЫЕ ТАБЛИЦЫ ---

class ContentPlan(Base):
    __tablename__ = 'content_plan'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(Text)
    theme = Column(Text)
    post_description = Column(Text)
    with_image = Column(Boolean, default=True)  # Для совместимости, но не используется в новом формате
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

class AiPrompts(Base):
    __tablename__ = 'ai_prompts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    prompt_type = Column(Text, unique=True) # 'content' или 'image'
    prompt_text = Column(Text)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class PublishingSettings(Base):
    __tablename__ = 'publishing_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    publish_to_tg = Column(Boolean, default=True)
    publish_to_vk = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
