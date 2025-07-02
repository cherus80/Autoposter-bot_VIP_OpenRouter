"""
@file: tests/functional/test_post_creation.py
@description: Функциональные тесты для процесса создания постов
@dependencies: pytest, aiogram
@created: 2025-01-21
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from handlers.generate_post import generate_post_handler, PostCreationStates
from services.ai_service import AIService
from services.vk_service import VKService


@pytest.mark.functional
class TestPostCreationFlow:
    """Функциональные тесты для полного процесса создания постов"""
    
    @pytest.fixture
    def mock_state(self):
        """Мокированное состояние FSM"""
        storage = MemoryStorage()
        context = FSMContext(storage=storage, key="test_key")
        return context
    
    @pytest.fixture
    def mock_ai_service(self):
        """Мокированный AI сервис"""
        service = Mock(spec=AIService)
        service.generate_post = AsyncMock(return_value="Сгенерированный пост")
        service.generate_contextual_image_with_character = AsyncMock(
            return_value="https://example.com/generated_image.jpg"
        )
        return service
    
    @pytest.fixture
    def mock_vk_service(self):
        """Мокированный VK сервис"""
        service = Mock(spec=VKService)
        service.create_post = AsyncMock(return_value={"post_id": 123})
        return service
    
    @pytest.mark.asyncio
    async def test_manual_post_creation_text_only(
        self, 
        mock_message, 
        mock_state, 
        mock_ai_service
    ):
        """Тест создания поста вручную (только текст)"""
        # Настройка
        mock_message.text = "Тестовая тема для поста"
        
        # Мокируем генерацию поста
        with patch('handlers.generate_post.ai_service', mock_ai_service):
            # Имитируем ввод темы
            await mock_state.set_state(PostCreationStates.waiting_for_topic)
            
            # Имитируем обработку темы
            result = await generate_post_handler(mock_message, mock_state)
            
            # Проверяем, что AI сервис был вызван
            mock_ai_service.generate_post.assert_called_once()
            
            # Проверяем ответ пользователю
            assert mock_message.answer.called
            answer_text = mock_message.answer.call_args[0][0]
            assert "Сгенерированный пост" in answer_text
    
    @pytest.mark.asyncio
    async def test_manual_post_creation_with_image(
        self, 
        mock_message, 
        mock_state, 
        mock_ai_service
    ):
        """Тест создания поста вручную с изображением"""
        mock_message.text = "Тема поста с изображением"
        
        with patch('handlers.generate_post.ai_service', mock_ai_service):
            await mock_state.set_state(PostCreationStates.waiting_for_topic)
            await mock_state.update_data(with_image=True)
            
            result = await generate_post_handler(mock_message, mock_state)
            
            # Проверяем, что была вызвана генерация и текста, и изображения
            mock_ai_service.generate_post.assert_called_once()
            mock_ai_service.generate_contextual_image_with_character.assert_called_once()
            
            # Проверяем, что пост отправлен с изображением
            assert mock_message.answer_photo.called
    
    @pytest.mark.asyncio
    async def test_post_creation_from_content_plan(
        self, 
        mock_message, 
        mock_state, 
        mock_ai_service,
        sample_content_plan
    ):
        """Тест создания поста из контент-плана"""
        topic_data = sample_content_plan[0]  # Первая тема из плана
        
        with patch('handlers.generate_post.ai_service', mock_ai_service), \
             patch('database.content_plan_db.get_unused_topic', return_value=topic_data):
            
            mock_ai_service.generate_post_from_plan = AsyncMock(return_value={
                "content": "Пост из контент-плана",
                "image_url": "https://example.com/plan_image.jpg"
            })
            
            # Имитируем запрос создания поста из плана
            await mock_state.set_state(PostCreationStates.creating_from_plan)
            
            result = await generate_post_handler(mock_message, mock_state)
            
            mock_ai_service.generate_post_from_plan.assert_called_once_with(topic_data)
            assert mock_message.answer.called or mock_message.answer_photo.called
    
    @pytest.mark.asyncio
    async def test_post_preview_and_approval(
        self, 
        mock_message, 
        mock_callback_query, 
        mock_state
    ):
        """Тест предпросмотра и подтверждения поста"""
        # Подготовка данных поста
        post_data = {
            "topic": "Тестовая тема",
            "content": "Тестовый контент поста",
            "with_image": True,
            "image_url": "https://example.com/test.jpg"
        }
        
        await mock_state.update_data(**post_data)
        
        # Имитируем callback для предпросмотра
        mock_callback_query.data = "preview_post"
        
        with patch('handlers.generate_post.show_post_preview') as mock_preview:
            mock_preview.return_value = AsyncMock()
            
            # Вызываем обработчик предпросмотра
            result = await generate_post_handler(mock_callback_query, mock_state)
            
            mock_preview.assert_called_once()
            mock_callback_query.answer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_post_publication_telegram_only(
        self, 
        mock_callback_query, 
        mock_state,
        mock_bot
    ):
        """Тест публикации поста только в Telegram"""
        post_data = {
            "topic": "Публикация в TG",
            "content": "Контент для Telegram",
            "with_image": False
        }
        
        await mock_state.update_data(**post_data)
        mock_callback_query.data = "publish_telegram"
        
        with patch('config.TELEGRAM_CHANNEL_ID', '@test_channel'), \
             patch('handlers.generate_post.bot', mock_bot):
            
            result = await generate_post_handler(mock_callback_query, mock_state)
            
            # Проверяем, что сообщение отправлено в канал
            mock_bot.send_message.assert_called_once()
            call_args = mock_bot.send_message.call_args
            assert call_args[1]['chat_id'] == '@test_channel'
            assert "Контент для Telegram" in call_args[1]['text']
    
    @pytest.mark.asyncio
    async def test_post_publication_vk_only(
        self, 
        mock_callback_query, 
        mock_state,
        mock_vk_service
    ):
        """Тест публикации поста только в VK"""
        post_data = {
            "topic": "Публикация в VK",
            "content": "Контент для VK",
            "with_image": True,
            "image_url": "https://example.com/vk_image.jpg"
        }
        
        await mock_state.update_data(**post_data)
        mock_callback_query.data = "publish_vk"
        
        with patch('handlers.generate_post.vk_service', mock_vk_service):
            
            result = await generate_post_handler(mock_callback_query, mock_state)
            
            # Проверяем, что пост создан в VK
            mock_vk_service.create_post.assert_called_once()
            call_args = mock_vk_service.create_post.call_args[0]
            assert "Контент для VK" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_post_publication_both_platforms(
        self, 
        mock_callback_query, 
        mock_state,
        mock_bot,
        mock_vk_service
    ):
        """Тест публикации поста на обе платформы"""
        post_data = {
            "topic": "Публикация везде",
            "content": "Контент для всех платформ",
            "with_image": True,
            "image_url": "https://example.com/universal_image.jpg"
        }
        
        await mock_state.update_data(**post_data)
        mock_callback_query.data = "publish_both"
        
        with patch('config.TELEGRAM_CHANNEL_ID', '@test_channel'), \
             patch('handlers.generate_post.bot', mock_bot), \
             patch('handlers.generate_post.vk_service', mock_vk_service):
            
            result = await generate_post_handler(mock_callback_query, mock_state)
            
            # Проверяем публикацию в Telegram
            mock_bot.send_photo.assert_called_once()
            
            # Проверяем публикацию в VK
            mock_vk_service.create_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_post_editing_flow(
        self, 
        mock_callback_query, 
        mock_state
    ):
        """Тест процесса редактирования поста"""
        post_data = {
            "topic": "Редактируемый пост",
            "content": "Исходный контент",
            "with_image": False
        }
        
        await mock_state.update_data(**post_data)
        
        # Имитируем callback для редактирования
        mock_callback_query.data = "edit_post"
        
        with patch('handlers.generate_post.show_edit_options') as mock_edit:
            mock_edit.return_value = AsyncMock()
            
            result = await generate_post_handler(mock_callback_query, mock_state)
            
            mock_edit.assert_called_once()
            mock_callback_query.answer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_post_regeneration(
        self, 
        mock_callback_query, 
        mock_state,
        mock_ai_service
    ):
        """Тест регенерации поста"""
        await mock_state.update_data(topic="Регенерация поста")
        mock_callback_query.data = "regenerate_post"
        
        with patch('handlers.generate_post.ai_service', mock_ai_service):
            mock_ai_service.generate_post.return_value = "Новый сгенерированный пост"
            
            result = await generate_post_handler(mock_callback_query, mock_state)
            
            # Проверяем, что пост был регенерирован
            mock_ai_service.generate_post.assert_called_once()
            mock_callback_query.edit_message_text.assert_called_once()
            
            # Проверяем, что новый контент отличается
            call_args = mock_callback_query.edit_message_text.call_args
            assert "Новый сгенерированный пост" in call_args[1]['text']
    
    @pytest.mark.asyncio
    async def test_post_cancellation(
        self, 
        mock_callback_query, 
        mock_state
    ):
        """Тест отмены создания поста"""
        await mock_state.update_data(topic="Отменяемый пост")
        mock_callback_query.data = "cancel_post"
        
        result = await generate_post_handler(mock_callback_query, mock_state)
        
        # Проверяем, что состояние очищено
        state_data = await mock_state.get_data()
        assert state_data == {}
        
        # Проверяем ответ пользователю
        mock_callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_query.edit_message_text.call_args
        assert "отменено" in call_args[1]['text'].lower()
    
    @pytest.mark.asyncio
    async def test_error_handling_during_generation(
        self, 
        mock_message, 
        mock_state,
        mock_ai_service
    ):
        """Тест обработки ошибок при генерации поста"""
        mock_message.text = "Проблемная тема"
        mock_ai_service.generate_post.side_effect = Exception("API Error")
        
        with patch('handlers.generate_post.ai_service', mock_ai_service), \
             patch('utils.error_handler.error_handler') as mock_error_handler:
            
            mock_error_handler.handle_error = AsyncMock()
            
            await mock_state.set_state(PostCreationStates.waiting_for_topic)
            
            result = await generate_post_handler(mock_message, mock_state)
            
            # Проверяем, что ошибка была обработана
            mock_error_handler.handle_error.assert_called_once()
            
            # Проверяем, что пользователь получил уведомление об ошибке
            mock_message.answer.assert_called()
            answer_text = mock_message.answer.call_args[0][0]
            assert "ошибка" in answer_text.lower()
    
    @pytest.mark.asyncio
    async def test_image_generation_failure(
        self, 
        mock_message, 
        mock_state,
        mock_ai_service
    ):
        """Тест обработки ошибки генерации изображения"""
        mock_message.text = "Тема с проблемным изображением"
        mock_ai_service.generate_post.return_value = "Текст поста"
        mock_ai_service.generate_contextual_image_with_character.return_value = None
        
        with patch('handlers.generate_post.ai_service', mock_ai_service):
            await mock_state.set_state(PostCreationStates.waiting_for_topic)
            await mock_state.update_data(with_image=True)
            
            result = await generate_post_handler(mock_message, mock_state)
            
            # Проверяем, что пост опубликован без изображения
            mock_message.answer.assert_called()
            
            # Проверяем, что пользователь уведомлен о проблеме с изображением
            answer_text = mock_message.answer.call_args[0][0]
            assert "изображение" in answer_text.lower()
    
    @pytest.mark.asyncio
    async def test_long_topic_handling(
        self, 
        mock_message, 
        mock_state,
        mock_ai_service
    ):
        """Тест обработки очень длинной темы"""
        long_topic = "Очень длинная тема поста " * 50  # 1500+ символов
        mock_message.text = long_topic
        
        with patch('handlers.generate_post.ai_service', mock_ai_service):
            await mock_state.set_state(PostCreationStates.waiting_for_topic)
            
            result = await generate_post_handler(mock_message, mock_state)
            
            # Проверяем, что длинная тема была обработана корректно
            mock_ai_service.generate_post.assert_called_once()
            call_args = mock_ai_service.generate_post.call_args
            
            # Тема должна быть обрезана или обработана
            assert len(call_args[0][0]) <= 1000  # Максимальная длина темы
    
    @pytest.mark.asyncio
    async def test_concurrent_post_creation(
        self, 
        mock_ai_service,
        async_session_maker_fixture
    ):
        """Тест конкурентного создания постов"""
        import asyncio
        
        async def create_post_task(topic):
            # Имитируем создание поста
            content = await mock_ai_service.generate_post(topic, "professional")
            
            # Сохраняем в базу данных
            async with async_session_maker_fixture() as session:
                from database.models import Post
                post = Post(topic=topic, content=content, source="concurrent_test")
                session.add(post)
                await session.commit()
                return post.id
        
        # Создаем несколько постов одновременно
        topics = [f"Concurrent Topic {i}" for i in range(5)]
        mock_ai_service.generate_post.return_value = "Generated content"
        
        tasks = [create_post_task(topic) for topic in topics]
        post_ids = await asyncio.gather(*tasks)
        
        # Проверяем, что все посты созданы
        assert len(post_ids) == 5
        assert all(post_id is not None for post_id in post_ids)
        assert len(set(post_ids)) == 5  # Все ID уникальны 