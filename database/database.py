# database/database.py - Настройка подключения к БД
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from .models import Base

# Определяем путь к базе данных
# В Docker используем директорию /app/database, локально - корень проекта
if os.path.exists('/app/database'):
    # Запуск в Docker контейнере
    db_path = '/app/database/autoposting_bot.db'
else:
    # Локальный запуск
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'autoposting_bot.db')

db_url = f'sqlite+aiosqlite:///{db_path}'

# Создаем асинхронный "движок" для SQLAlchemy
engine = create_async_engine(db_url, echo=False)

# Создаем фабрику асинхронных сессий
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    """
    Инициализирует базу данных: создает все необходимые таблицы.
    """
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Раскомментировать для удаления всех таблиц при перезапуске
        await conn.run_sync(Base.metadata.create_all) 