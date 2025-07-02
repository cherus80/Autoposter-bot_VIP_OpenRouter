"""
@file: tests/conftest.py
@description: Общие фикстуры и конфигурация для тестирования
@dependencies: pytest, aiogram, sqlalchemy
@created: 2025-01-21
"""

import asyncio
import os
import tempfile
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Импорты проекта
from database.database import Base
from database.models import Post, ContentPlan, Settings
from services.ai_service import AIService
from services.backup_service import BackupService
from services.scheduler import PostScheduler
from utils.error_handler import ErrorHandler


@pytest.fixture(scope="session")
def event_loop():
    """Создание event loop для всех тестов"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_db_path():
    """Временная база данных для тестов"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
async def test_db_engine(temp_db_path):
    """Создание тестового движка базы данных"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{temp_db_path}")
    
    # Создаем таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session_maker_fixture(test_db_engine):
    """Фабрика асинхронных сессий для тестов"""
    async_session_maker = async_sessionmaker(
        test_db_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    return async_session_maker


@pytest.fixture
async def test_session(async_session_maker_fixture):
    """Тестовая сессия базы данных"""
    async with async_session_maker_fixture() as session:
        yield session


@pytest.fixture
def mock_bot():
    """Мокированный Telegram бот"""
    bot = Mock(spec=Bot)
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.send_document = AsyncMock()
    bot.delete_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    bot.answer_callback_query = AsyncMock()
    return bot


@pytest.fixture
def mock_dispatcher():
    """Мокированный диспетчер"""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    return dp


@pytest.fixture
def mock_message():
    """Мокированное сообщение Telegram"""
    message = Mock()
    message.from_user = Mock()
    message.from_user.id = 123456789
    message.from_user.username = "test_user"
    message.chat = Mock()
    message.chat.id = 123456789
    message.message_id = 1
    message.text = "test message"
    message.answer = AsyncMock()
    message.reply = AsyncMock()
    message.edit_text = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query():
    """Мокированный callback query"""
    callback = Mock()
    callback.from_user = Mock()
    callback.from_user.id = 123456789
    callback.data = "test_callback"
    callback.message = Mock()
    callback.message.chat = Mock()
    callback.message.chat.id = 123456789
    callback.answer = AsyncMock()
    callback.edit_message_text = AsyncMock()
    return callback


@pytest.fixture
def mock_openai_response():
    """Мокированный ответ OpenAI API"""
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message = Mock()
    response.choices[0].message.content = "Test generated content"
    return response


@pytest.fixture
def mock_fal_response():
    """Мокированный ответ Fal.ai API"""
    return {
        "images": [
            {
                "url": "https://example.com/test_image.jpg",
                "width": 512,
                "height": 512
            }
        ]
    }


@pytest.fixture
def mock_vk_api():
    """Мокированный VK API"""
    vk_mock = Mock()
    vk_mock.wall = Mock()
    vk_mock.wall.post = Mock(return_value={'post_id': 123})
    vk_mock.stats = Mock()
    vk_mock.stats.get = Mock(return_value=[{
        'views': 1000,
        'likes': 50,
        'comments': 10,
        'shares': 5
    }])
    return vk_mock


@pytest.fixture
async def sample_post_data():
    """Образец данных поста для тестов"""
    return {
        "topic": "Тест топик",
        "content": "Тестовый контент поста",
        "with_image": True,
        "image_url": "https://example.com/test.jpg",
        "source": "manual"
    }


@pytest.fixture
async def sample_content_plan():
    """Образец контент-плана для тестов"""
    return [
        {"topic": "Тестовая тема 1", "with_image": True},
        {"topic": "Тестовая тема 2", "with_image": False},
        {"topic": "Тестовая тема 3", "with_image": True}
    ]


@pytest.fixture
def temp_backup_dir():
    """Временная директория для бэкапов"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
async def ai_service_mock():
    """Мокированный AI сервис"""
    service = Mock(spec=AIService)
    service.generate_post = AsyncMock(return_value="Generated post content")
    service.generate_post_from_plan = AsyncMock(return_value={
        "content": "Generated content",
        "image_url": "https://example.com/image.jpg"
    })
    service.extract_visual_elements = AsyncMock(return_value="Visual elements")
    service.generate_contextual_image_with_character = AsyncMock(
        return_value="https://example.com/generated.jpg"
    )
    return service


@pytest.fixture
async def backup_service_mock():
    """Мокированный сервис резервного копирования"""
    service = Mock(spec=BackupService)
    service.create_database_backup = AsyncMock(return_value="/path/to/backup.db")
    service.create_settings_backup = AsyncMock(return_value="/path/to/settings.json")
    service.create_full_backup = AsyncMock(return_value="/path/to/full_backup.zip")
    service.restore_from_backup = AsyncMock(return_value=True)
    service.get_backup_list = AsyncMock(return_value=[])
    return service


@pytest.fixture
async def scheduler_mock():
    """Мокированный планировщик"""
    scheduler = Mock(spec=PostScheduler)
    scheduler.start = AsyncMock()
    scheduler.stop = AsyncMock()
    scheduler.is_running = False
    scheduler.schedule_next_post = AsyncMock()
    return scheduler


@pytest.fixture
def error_handler_mock():
    """Мокированный обработчик ошибок"""
    handler = Mock(spec=ErrorHandler)
    handler.handle_error = AsyncMock()
    return handler


@pytest.fixture
def mock_admin_ids():
    """Мокированные ID администраторов"""
    return [123456789, 987654321]


@pytest.fixture
async def populated_test_db(test_session):
    """База данных с тестовыми данными"""
    # Добавляем тестовые посты
    test_posts = [
        Post(
            topic="Тест 1",
            content="Контент теста 1",
            with_image=True,
            source="manual"
        ),
        Post(
            topic="Тест 2", 
            content="Контент теста 2",
            with_image=False,
            source="auto"
        )
    ]
    
    # Добавляем тестовый контент-план
    test_topics = [
        ContentPlan(topic="Тестовая тема 1", with_image=True, is_used=False),
        ContentPlan(topic="Тестовая тема 2", with_image=False, is_used=True)
    ]
    
    # Добавляем тестовые настройки
    test_settings = [
        Settings(key="auto_mode_enabled", value="true"),
        Settings(key="auto_mode_interval", value="24"),
        Settings(key="backup_enabled", value="true")
    ]
    
    for post in test_posts:
        test_session.add(post)
    for topic in test_topics:
        test_session.add(topic)
    for setting in test_settings:
        test_session.add(setting)
    
    await test_session.commit()
    yield test_session


# Патчи для внешних зависимостей
@pytest.fixture
def patch_openai():
    """Патч для OpenAI API"""
    with patch('openai.ChatCompletion.acreate') as mock:
        mock.return_value = Mock()
        mock.return_value.choices = [Mock()]
        mock.return_value.choices[0].message = Mock()
        mock.return_value.choices[0].message.content = "Test response"
        yield mock


@pytest.fixture
def patch_fal_api():
    """Патч для Fal.ai API"""
    with patch('fal_client.submit') as mock:
        mock.return_value.get.return_value = {
            "images": [{"url": "https://example.com/test.jpg"}]
        }
        yield mock


@pytest.fixture
def patch_vk_api():
    """Патч для VK API"""
    with patch('vk_api.VkApi') as mock:
        vk_instance = Mock()
        vk_instance.wall.post.return_value = {'post_id': 123}
        mock.return_value = vk_instance
        yield mock 