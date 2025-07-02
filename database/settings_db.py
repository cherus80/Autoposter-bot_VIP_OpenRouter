# database/settings_db.py - Функции для работы с настройками

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from .database import async_session_maker
from .models import Settings

async def get_setting(key: str, default: str = None) -> str:
    """
    Получает значение настройки по ключу.
    Если ключ не найден, возвращает значение по умолчанию.
    """
    async with async_session_maker() as session:
        try:
            query = select(Settings.value).where(Settings.key == key)
            result = await session.execute(query)
            value = result.scalar_one()
            return value
        except NoResultFound:
            return default

async def update_setting(key: str, value: str):
    """
    Обновляет или создает настройку.
    """
    async with async_session_maker() as session:
        # Проверяем, существует ли настройка
        query = select(Settings).where(Settings.key == key)
        result = await session.execute(query)
        setting = result.scalar_one_or_none()
        
        if setting:
            # Обновляем, если существует
            setting.value = value
        else:
            # Создаем, если не существует
            setting = Settings(key=key, value=value)
            session.add(setting)
            
        await session.commit() 