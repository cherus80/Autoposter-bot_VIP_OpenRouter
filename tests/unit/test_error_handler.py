"""
@file: tests/unit/test_error_handler.py
@description: Модульные тесты для системы обработки ошибок
@dependencies: pytest, unittest.mock
@created: 2025-01-21
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from utils.error_handler import ErrorHandler, ErrorSeverity, handle_errors


@pytest.mark.unit
class TestErrorHandler:
    """Тестирование системы обработки ошибок"""
    
    @pytest.fixture
    def error_handler(self, mock_bot):
        """Создание экземпляра ErrorHandler для тестов"""
        handler = ErrorHandler(mock_bot)
        return handler
    
    @pytest.mark.asyncio
    async def test_handle_error_low_severity(self, error_handler):
        """Тест обработки ошибки низкого уровня"""
        error = ValueError("Test error")
        
        await error_handler.handle_error(
            error, 
            "test_context", 
            ErrorSeverity.LOW,
            user_id=123456
        )
        
        # Для низкого уровня не должно быть уведомлений админу
        assert not error_handler.bot.send_message.called
    
    @pytest.mark.asyncio
    async def test_handle_error_critical_severity(self, error_handler):
        """Тест обработки критической ошибки"""
        error = Exception("Critical error")
        
        with patch('config.ADMIN_IDS', [123456]):
            await error_handler.handle_error(
                error,
                "critical_context",
                ErrorSeverity.CRITICAL,
                user_id=789012
            )
        
        # Для критического уровня должно быть уведомление
        error_handler.bot.send_message.assert_called_once()
        call_args = error_handler.bot.send_message.call_args[0]
        assert "🚨" in call_args[1]  # Проверяем критический emoji
        assert "Critical error" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_handle_error_high_severity(self, error_handler):
        """Тест обработки ошибки высокого уровня"""
        error = RuntimeError("High severity error")
        
        with patch('config.ADMIN_IDS', [123456]):
            await error_handler.handle_error(
                error,
                "high_context",
                ErrorSeverity.HIGH,
                additional_info={"component": "test"}
            )
        
        error_handler.bot.send_message.assert_called_once()
        call_args = error_handler.bot.send_message.call_args[0]
        assert "⚠️" in call_args[1]  # Проверяем warning emoji
        assert "component: test" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, error_handler):
        """Тест ограничения частоты уведомлений"""
        error = Exception("Repeated error")
        
        with patch('config.ADMIN_IDS', [123456]):
            # Первый вызов должен отправить уведомление
            await error_handler.handle_error(
                error, "test_context", ErrorSeverity.HIGH
            )
            
            # Второй вызов в течение 5 минут не должен отправлять уведомление
            await error_handler.handle_error(
                error, "test_context", ErrorSeverity.HIGH
            )
        
        # Должен быть только один вызов send_message
        assert error_handler.bot.send_message.call_count == 1
    
    @pytest.mark.asyncio
    async def test_rate_limiting_expired(self, error_handler):
        """Тест истечения времени ограничения"""
        error = Exception("Repeated error")
        error_key = f"{type(error).__name__}_test_context"
        
        # Устанавливаем время последнего уведомления в прошлом
        error_handler.last_notification[error_key] = datetime.now() - timedelta(minutes=10)
        
        with patch('config.ADMIN_IDS', [123456]):
            await error_handler.handle_error(
                error, "test_context", ErrorSeverity.HIGH
            )
        
        # Должно отправить уведомление, так как время истекло
        error_handler.bot.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_multiple_admins_notification(self, error_handler):
        """Тест уведомления нескольких администраторов"""
        error = Exception("Multi admin error")
        admin_ids = [123456, 789012, 555777]
        
        with patch('config.ADMIN_IDS', admin_ids):
            await error_handler.handle_error(
                error, "multi_admin", ErrorSeverity.CRITICAL
            )
        
        # Должно быть отправлено уведомление всем админам
        assert error_handler.bot.send_message.call_count == len(admin_ids)
    
    @pytest.mark.asyncio
    async def test_telegram_api_error_during_notification(self, error_handler):
        """Тест обработки ошибки Telegram API при отправке уведомления"""
        from aiogram.exceptions import TelegramAPIError
        
        error = Exception("Original error")
        error_handler.bot.send_message.side_effect = TelegramAPIError("API Error")
        
        with patch('config.ADMIN_IDS', [123456]):
            # Не должно вызывать исключение
            await error_handler.handle_error(
                error, "telegram_error", ErrorSeverity.HIGH
            )
        
        # Проверяем, что была попытка отправить сообщение
        error_handler.bot.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_no_bot_instance(self):
        """Тест обработки ошибки без экземпляра бота"""
        handler = ErrorHandler()  # Без бота
        error = Exception("No bot error")
        
        # Не должно вызывать исключение
        await handler.handle_error(error, "no_bot", ErrorSeverity.HIGH)
        
        # Проверяем, что обработчик не упал
        assert True
    
    @pytest.mark.asyncio
    async def test_no_admin_ids(self, error_handler):
        """Тест обработки при отсутствии ID администраторов"""
        error = Exception("No admins error")
        
        with patch('config.ADMIN_IDS', []):
            await error_handler.handle_error(
                error, "no_admins", ErrorSeverity.CRITICAL
            )
        
        # Не должно быть попыток отправить сообщение
        assert not error_handler.bot.send_message.called


@pytest.mark.unit
class TestHandleErrorsDecorator:
    """Тестирование декоратора handle_errors"""
    
    @pytest.mark.asyncio
    async def test_successful_function_execution(self):
        """Тест успешного выполнения функции с декоратором"""
        @handle_errors(context="test_success", severity=ErrorSeverity.MEDIUM)
        async def test_function():
            return "success"
        
        result = await test_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_function_with_exception(self, error_handler_mock):
        """Тест функции с исключением"""
        @handle_errors(
            context="test_exception", 
            severity=ErrorSeverity.HIGH,
            fallback_return="fallback"
        )
        async def failing_function():
            raise ValueError("Test exception")
        
        with patch('utils.error_handler.error_handler', error_handler_mock):
            result = await failing_function()
        
        assert result == "fallback"
        error_handler_mock.handle_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_decorator_with_message_object(self, mock_message, error_handler_mock):
        """Тест декоратора с объектом сообщения для уведомления пользователя"""
        @handle_errors(
            context="test_message",
            severity=ErrorSeverity.MEDIUM,
            notify_user=True
        )
        async def handler_function(message):
            raise RuntimeError("Handler error")
        
        with patch('utils.error_handler.error_handler', error_handler_mock):
            result = await handler_function(mock_message)
        
        assert result is None
        mock_message.answer.assert_called_once()
        error_text = mock_message.answer.call_args[0][0]
        assert "ошибка" in error_text.lower()
    
    @pytest.mark.asyncio
    async def test_decorator_critical_error_notification(self, mock_message, error_handler_mock):
        """Тест уведомления пользователя о критической ошибке"""
        @handle_errors(
            context="test_critical",
            severity=ErrorSeverity.CRITICAL,
            notify_user=True
        )
        async def critical_function(message):
            raise Exception("Critical failure")
        
        with patch('utils.error_handler.error_handler', error_handler_mock):
            await critical_function(mock_message)
        
        mock_message.answer.assert_called_once()
        error_text = mock_message.answer.call_args[0][0]
        assert "критическая ошибка" in error_text.lower()
    
    @pytest.mark.asyncio
    async def test_decorator_without_user_notification(self, mock_message, error_handler_mock):
        """Тест декоратора без уведомления пользователя"""
        @handle_errors(
            context="test_no_notify",
            severity=ErrorSeverity.HIGH,
            notify_user=False
        )
        async def silent_function(message):
            raise ValueError("Silent error")
        
        with patch('utils.error_handler.error_handler', error_handler_mock):
            await silent_function(mock_message)
        
        # Пользователь не должен получить уведомление
        mock_message.answer.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_decorator_user_id_extraction(self, error_handler_mock):
        """Тест извлечения user_id из аргументов функции"""
        class MockObject:
            def __init__(self, user_id):
                self.from_user = Mock()
                self.from_user.id = user_id
        
        @handle_errors(context="test_user_id", severity=ErrorSeverity.HIGH)
        async def function_with_user_id(obj):
            raise Exception("Error with user")
        
        mock_obj = MockObject(123456)
        
        with patch('utils.error_handler.error_handler', error_handler_mock):
            await function_with_user_id(mock_obj)
        
        # Проверяем, что user_id был передан в обработчик ошибок
        error_handler_mock.handle_error.assert_called_once()
        call_kwargs = error_handler_mock.handle_error.call_args[1]
        assert call_kwargs['user_id'] == 123456
    
    @pytest.mark.asyncio
    async def test_decorator_additional_info(self, error_handler_mock):
        """Тест передачи дополнительной информации в обработчик ошибок"""
        @handle_errors(context="test_info", severity=ErrorSeverity.MEDIUM)
        async def test_function():
            raise ValueError("Error with info")
        
        with patch('utils.error_handler.error_handler', error_handler_mock):
            await test_function()
        
        error_handler_mock.handle_error.assert_called_once()
        call_kwargs = error_handler_mock.handle_error.call_args[1]
        
        assert 'additional_info' in call_kwargs
        additional_info = call_kwargs['additional_info']
        assert 'function' in additional_info
        assert 'module' in additional_info
        assert additional_info['function'] == 'test_function'
    
    @pytest.mark.asyncio
    async def test_decorator_with_callback_query(self, mock_callback_query, error_handler_mock):
        """Тест декоратора с callback query"""
        @handle_errors(
            context="test_callback",
            severity=ErrorSeverity.MEDIUM,
            notify_user=True
        )
        async def callback_handler(callback):
            raise RuntimeError("Callback error")
        
        # У callback query нет метода answer, но есть message
        mock_callback_query.message.answer = AsyncMock()
        
        with patch('utils.error_handler.error_handler', error_handler_mock):
            await callback_handler(mock_callback_query)
        
        # В этом случае пользователь не получит уведомление,
        # так как нет прямого метода answer у callback
        error_handler_mock.handle_error.assert_called_once()
    
    def test_decorator_parameters(self):
        """Тест правильности параметров декоратора"""
        @handle_errors(
            context="test_params",
            severity=ErrorSeverity.LOW,
            fallback_return="default",
            notify_user=False
        )
        async def decorated_function():
            pass
        
        # Проверяем, что функция была обернута корректно
        assert hasattr(decorated_function, '__wrapped__')
        assert decorated_function.__name__ == 'decorated_function' 