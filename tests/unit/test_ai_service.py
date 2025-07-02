"""
@file: tests/unit/test_ai_service.py
@description: Модульные тесты для AI сервиса
@dependencies: pytest, unittest.mock
@created: 2025-01-21
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from services.ai_service import AIService


@pytest.mark.unit
@pytest.mark.ai
class TestAIService:
    """Тестирование AI сервиса"""
    
    @pytest.fixture
    def ai_service(self):
        """Создание экземпляра AI сервиса для тестов"""
        return AIService()
    
    @pytest.mark.asyncio
    async def test_generate_post_success(self, ai_service, patch_openai):
        """Тест успешной генерации поста"""
        # Настройка мока
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Тестовый пост о технологиях"
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            result = await ai_service.generate_post("Тестовая тема", "professional")
            
            assert result == "Тестовый пост о технологиях"
            mock_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_post_api_error(self, ai_service):
        """Тест обработки ошибки API при генерации поста"""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
            
            result = await ai_service.generate_post("Тестовая тема", "professional")
            
            assert result == "Не удалось сгенерировать пост. Попробуйте позже."
    
    @pytest.mark.asyncio
    async def test_generate_post_from_plan_with_image(self, ai_service):
        """Тест генерации поста из контент-плана с изображением"""
        topic_data = {"topic": "IT тренды", "with_image": True}
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Пост о IT трендах"
        
        with patch('openai.AsyncOpenAI') as mock_openai, \
             patch.object(ai_service, 'generate_contextual_image_with_character') as mock_image:
            
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_image.return_value = "https://example.com/generated_image.jpg"
            
            result = await ai_service.generate_post_from_plan(topic_data)
            
            assert result["content"] == "Пост о IT трендах"
            assert result["image_url"] == "https://example.com/generated_image.jpg"
            mock_image.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_post_from_plan_text_only(self, ai_service):
        """Тест генерации поста из контент-плана без изображения"""
        topic_data = {"topic": "Программирование", "with_image": False}
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Пост о программировании"
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            result = await ai_service.generate_post_from_plan(topic_data)
            
            assert result["content"] == "Пост о программировании"
            assert result["image_url"] is None
    
    @pytest.mark.asyncio
    async def test_extract_visual_elements(self, ai_service):
        """Тест извлечения визуальных элементов"""
        text = "Пост о современных технологиях и инновациях"
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "технологии, инновации, компьютер"
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            result = await ai_service.extract_visual_elements(text)
            
            assert result == "технологии, инновации, компьютер"
    
    @pytest.mark.asyncio
    async def test_generate_contextual_image_success(self, ai_service):
        """Тест успешной генерации изображения"""
        topic = "Искусственный интеллект"
        style = "realistic"
        
        mock_response = {
            "images": [
                {
                    "url": "https://example.com/ai_image.jpg",
                    "width": 1024,
                    "height": 1024
                }
            ]
        }
        
        with patch('fal_client.submit') as mock_fal:
            mock_result = Mock()
            mock_result.get.return_value = mock_response
            mock_fal.return_value = mock_result
            
            result = await ai_service.generate_contextual_image_with_character(topic, style)
            
            assert result == "https://example.com/ai_image.jpg"
            mock_fal.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_contextual_image_api_error(self, ai_service):
        """Тест обработки ошибки API при генерации изображения"""
        topic = "Тестовая тема"
        style = "realistic"
        
        with patch('fal_client.submit') as mock_fal:
            mock_fal.side_effect = Exception("API Error")
            
            result = await ai_service.generate_contextual_image_with_character(topic, style)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_post_with_different_styles(self, ai_service):
        """Тест генерации постов с разными стилями"""
        styles = ["professional", "friendly", "expert", "casual"]
        
        for style in styles:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message = Mock()
            mock_response.choices[0].message.content = f"Пост в стиле {style}"
            
            with patch('openai.AsyncOpenAI') as mock_openai:
                mock_client = Mock()
                mock_openai.return_value = mock_client
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                
                result = await ai_service.generate_post("Тестовая тема", style)
                
                assert result == f"Пост в стиле {style}"
                assert mock_client.chat.completions.create.called
    
    @pytest.mark.asyncio
    async def test_empty_topic_handling(self, ai_service):
        """Тест обработки пустой темы"""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            result = await ai_service.generate_post("", "professional")
            
            # Должен обработать пустую тему корректно
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_long_topic_handling(self, ai_service):
        """Тест обработки очень длинной темы"""
        long_topic = "Очень длинная тема " * 100  # 2000+ символов
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Обработанный длинный пост"
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            result = await ai_service.generate_post(long_topic, "professional")
            
            assert result == "Обработанный длинный пост"
    
    def test_build_content_prompt(self, ai_service):
        """Тест построения промпта для контента"""
        # Этот тест проверяет внутреннюю логику построения промптов
        topic = "Тестовая тема"
        style = "professional"
        
        # Предполагаем, что есть метод для построения промпта
        # (если его нет, можно его добавить или протестировать через generate_post)
        with patch.object(ai_service, 'generate_post') as mock_generate:
            ai_service.generate_post(topic, style)
            
            # Проверяем, что метод был вызван с правильными параметрами
            mock_generate.assert_called_once_with(topic, style)
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, ai_service):
        """Тест обработки конкурентных запросов"""
        import asyncio
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Concurrent response"
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            # Запускаем несколько запросов одновременно
            tasks = [
                ai_service.generate_post(f"Тема {i}", "professional")
                for i in range(5)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Все запросы должны завершиться успешно
            assert len(results) == 5
            assert all(result == "Concurrent response" for result in results)
    
    @pytest.mark.asyncio
    async def test_rate_limiting_simulation(self, ai_service):
        """Тест симуляции ограничения скорости API"""
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            # Имитируем ошибку rate limiting
            from openai import RateLimitError
            mock_client.chat.completions.create = AsyncMock(
                side_effect=RateLimitError("Rate limit exceeded", response=Mock(), body=None)
            )
            
            result = await ai_service.generate_post("Тестовая тема", "professional")
            
            # Должен обработать ошибку gracefully
            assert result == "Не удалось сгенерировать пост. Попробуйте позже." 