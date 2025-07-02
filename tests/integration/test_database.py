"""
@file: tests/integration/test_database.py
@description: Интеграционные тесты для работы с базой данных
@dependencies: pytest, sqlalchemy
@created: 2025-01-21
"""

import pytest
from datetime import datetime
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from database.models import Post, ContentPlan, Setting, PublishingSettings
from database.posts_db import create_post, get_posts, get_post_stats
from database.settings_db import get_setting, update_setting, add_setting
from database.database import init_db


@pytest.mark.integration
@pytest.mark.database
class TestDatabaseOperations:
    """Интеграционные тесты для операций с базой данных"""
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, test_db_engine):
        """Тест инициализации базы данных"""
        # Проверяем, что все таблицы созданы
        async with test_db_engine.connect() as conn:
            # Проверяем существование основных таблиц
            result = await conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ))
            tables = [row[0] for row in result.fetchall()]
            
            assert 'posts' in tables
            assert 'content_plan' in tables
            assert 'settings' in tables
            assert 'publishing_settings' in tables
    
    @pytest.mark.asyncio
    async def test_post_crud_operations(self, test_session):
        """Тест CRUD операций для постов"""
        # Create
        post = Post(
            topic="Тестовый пост",
            content="Контент тестового поста",
            with_image=True,
            source="manual",
            image_url="https://example.com/image.jpg"
        )
        test_session.add(post)
        await test_session.commit()
        await test_session.refresh(post)
        
        assert post.id is not None
        assert post.created_at is not None
        
        # Read
        result = await test_session.execute(
            select(Post).where(Post.id == post.id)
        )
        found_post = result.scalar_one()
        
        assert found_post.topic == "Тестовый пост"
        assert found_post.with_image is True
        
        # Update
        found_post.topic = "Обновленный пост"
        await test_session.commit()
        
        result = await test_session.execute(
            select(Post).where(Post.id == post.id)
        )
        updated_post = result.scalar_one()
        assert updated_post.topic == "Обновленный пост"
        
        # Delete
        await test_session.delete(updated_post)
        await test_session.commit()
        
        result = await test_session.execute(
            select(Post).where(Post.id == post.id)
        )
        assert result.scalar_one_or_none() is None
    
    @pytest.mark.asyncio
    async def test_content_plan_operations(self, test_session):
        """Тест операций с контент-планом"""
        # Создаем несколько записей контент-плана
        topics = [
            ContentPlan(topic="Тема 1", with_image=True, is_used=False),
            ContentPlan(topic="Тема 2", with_image=False, is_used=False),
            ContentPlan(topic="Тема 3", with_image=True, is_used=True)
        ]
        
        for topic in topics:
            test_session.add(topic)
        await test_session.commit()
        
        # Получаем неиспользованные темы
        result = await test_session.execute(
            select(ContentPlan).where(ContentPlan.is_used == False)
        )
        unused_topics = result.scalars().all()
        
        assert len(unused_topics) == 2
        assert all(not topic.is_used for topic in unused_topics)
        
        # Отмечаем тему как использованную
        unused_topics[0].is_used = True
        await test_session.commit()
        
        # Проверяем обновление
        result = await test_session.execute(
            select(ContentPlan).where(ContentPlan.is_used == False)
        )
        remaining_unused = result.scalars().all()
        assert len(remaining_unused) == 1
    
    @pytest.mark.asyncio
    async def test_settings_operations(self, test_session):
        """Тест операций с настройками"""
        # Создаем настройку
        setting = Setting(
            key="test_setting",
            value="test_value",
            description="Тестовая настройка"
        )
        test_session.add(setting)
        await test_session.commit()
        
        # Читаем настройку
        result = await test_session.execute(
            select(Setting).where(Setting.key == "test_setting")
        )
        found_setting = result.scalar_one()
        
        assert found_setting.value == "test_value"
        assert found_setting.description == "Тестовая настройка"
        
        # Обновляем значение
        found_setting.value = "updated_value"
        await test_session.commit()
        
        # Проверяем обновление
        result = await test_session.execute(
            select(Setting).where(Setting.key == "test_setting")
        )
        updated_setting = result.scalar_one()
        assert updated_setting.value == "updated_value"
    
    @pytest.mark.asyncio
    async def test_publishing_settings_operations(self, test_session):
        """Тест операций с настройками публикации"""
        # Создаем настройки публикации
        pub_setting = PublishingSettings(
            chat_id=123456789,
            telegram_enabled=True,
            vk_enabled=False
        )
        test_session.add(pub_setting)
        await test_session.commit()
        
        # Читаем настройки
        result = await test_session.execute(
            select(PublishingSettings).where(PublishingSettings.chat_id == 123456789)
        )
        found_setting = result.scalar_one()
        
        assert found_setting.telegram_enabled is True
        assert found_setting.vk_enabled is False
        
        # Обновляем настройки
        found_setting.vk_enabled = True
        await test_session.commit()
        
        # Проверяем обновление
        result = await test_session.execute(
            select(PublishingSettings).where(PublishingSettings.chat_id == 123456789)
        )
        updated_setting = result.scalar_one()
        assert updated_setting.vk_enabled is True
    
    @pytest.mark.asyncio
    async def test_foreign_key_constraints(self, test_session):
        """Тест ограничений внешних ключей"""
        # Эта функциональность может быть добавлена в будущем
        # Например, связи между постами и пользователями
        pass
    
    @pytest.mark.asyncio
    async def test_unique_constraints(self, test_session):
        """Тест уникальных ограничений"""
        # Создаем настройку
        setting1 = Setting(key="unique_key", value="value1")
        test_session.add(setting1)
        await test_session.commit()
        
        # Пытаемся создать настройку с тем же ключом
        setting2 = Setting(key="unique_key", value="value2")
        test_session.add(setting2)
        
        with pytest.raises(IntegrityError):
            await test_session.commit()
        
        await test_session.rollback()
    
    @pytest.mark.asyncio
    async def test_date_fields(self, test_session):
        """Тест полей с датами"""
        post = Post(
            topic="Тест даты",
            content="Контент с проверкой даты",
            source="test"
        )
        test_session.add(post)
        await test_session.commit()
        await test_session.refresh(post)
        
        # Проверяем, что дата создания установлена
        assert post.created_at is not None
        assert isinstance(post.created_at, datetime)
        
        # Проверяем, что дата близка к текущему времени (в пределах минуты)
        time_diff = abs((datetime.now() - post.created_at).total_seconds())
        assert time_diff < 60
    
    @pytest.mark.asyncio
    async def test_bulk_operations(self, test_session):
        """Тест массовых операций"""
        # Создаем множество постов
        posts = []
        for i in range(10):
            post = Post(
                topic=f"Пост {i}",
                content=f"Контент поста {i}",
                source="bulk_test",
                with_image=i % 2 == 0  # Каждый второй с изображением
            )
            posts.append(post)
        
        test_session.add_all(posts)
        await test_session.commit()
        
        # Проверяем, что все посты созданы
        result = await test_session.execute(
            select(Post).where(Post.source == "bulk_test")
        )
        created_posts = result.scalars().all()
        
        assert len(created_posts) == 10
        
        # Проверяем фильтрацию по with_image
        result = await test_session.execute(
            select(Post).where(
                Post.source == "bulk_test",
                Post.with_image == True
            )
        )
        posts_with_image = result.scalars().all()
        assert len(posts_with_image) == 5
    
    @pytest.mark.asyncio
    async def test_complex_queries(self, test_session):
        """Тест сложных запросов"""
        # Создаем тестовые данные
        posts = [
            Post(topic="Python", content="О Python", source="auto", with_image=True),
            Post(topic="JavaScript", content="О JS", source="manual", with_image=False),
            Post(topic="Python advanced", content="Продвинутый Python", source="auto", with_image=True)
        ]
        
        for post in posts:
            test_session.add(post)
        await test_session.commit()
        
        # Запрос с фильтрацией и подсчетом
        result = await test_session.execute(
            select(Post).where(
                Post.topic.like("%Python%"),
                Post.source == "auto"
            )
        )
        python_auto_posts = result.scalars().all()
        
        assert len(python_auto_posts) == 2
        assert all("Python" in post.topic for post in python_auto_posts)
        assert all(post.source == "auto" for post in python_auto_posts)
        
        # Агрегационный запрос
        result = await test_session.execute(
            text("SELECT COUNT(*) FROM posts WHERE with_image = 1")
        )
        posts_with_image_count = result.scalar()
        assert posts_with_image_count == 2
    
    @pytest.mark.asyncio
    async def test_transaction_rollback(self, test_session):
        """Тест отката транзакций"""
        # Создаем пост
        post = Post(topic="Тест отката", content="Контент", source="test")
        test_session.add(post)
        await test_session.commit()
        
        # Начинаем новую транзакцию
        post.topic = "Измененный заголовок"
        
        # Имитируем ошибку и откатываем
        await test_session.rollback()
        
        # Проверяем, что изменения не сохранились
        await test_session.refresh(post)
        assert post.topic == "Тест отката"
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, async_session_maker_fixture):
        """Тест конкурентного доступа к базе данных"""
        async def create_post_task(session_maker, topic):
            async with session_maker() as session:
                post = Post(topic=topic, content=f"Контент {topic}", source="concurrent")
                session.add(post)
                await session.commit()
                return post.id
        
        # Создаем несколько параллельных задач
        import asyncio
        tasks = [
            create_post_task(async_session_maker_fixture, f"Concurrent Post {i}")
            for i in range(5)
        ]
        
        post_ids = await asyncio.gather(*tasks)
        
        # Проверяем, что все посты созданы
        assert len(post_ids) == 5
        assert all(post_id is not None for post_id in post_ids)
        assert len(set(post_ids)) == 5  # Все ID уникальны


@pytest.mark.integration
@pytest.mark.database
class TestDatabaseHelpers:
    """Тестирование вспомогательных функций базы данных"""
    
    @pytest.mark.asyncio
    async def test_create_post_function(self, populated_test_db):
        """Тест функции создания поста"""
        post_data = {
            "topic": "Функциональный тест",
            "content": "Контент функционального теста",
            "with_image": True,
            "image_url": "https://example.com/test.jpg",
            "source": "function_test"
        }
        
        # Эта функция должна существовать в posts_db.py
        # Если её нет, тест покажет, что нужно её реализовать
        try:
            post_id = await create_post(post_data)
            assert post_id is not None
        except NameError:
            pytest.skip("Функция create_post не реализована")
    
    @pytest.mark.asyncio
    async def test_get_posts_function(self, populated_test_db):
        """Тест функции получения постов"""
        try:
            posts = await get_posts(limit=10)
            assert isinstance(posts, list)
            assert len(posts) <= 10
        except NameError:
            pytest.skip("Функция get_posts не реализована")
    
    @pytest.mark.asyncio
    async def test_get_setting_function(self, populated_test_db):
        """Тест функции получения настройки"""
        try:
            value = await get_setting("auto_mode_enabled", "false")
            assert value in ["true", "false"]
        except NameError:
            pytest.skip("Функция get_setting не реализована")
    
    @pytest.mark.asyncio
    async def test_update_setting_function(self, populated_test_db):
        """Тест функции обновления настройки"""
        try:
            result = await update_setting("test_update_setting", "test_value")
            assert result is not None
        except NameError:
            pytest.skip("Функция update_setting не реализована") 