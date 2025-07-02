"""
@file: utils/error_handler.py
@description: Централизованная система обработки ошибок
@dependencies: config.py, logging
@created: 2025-01-21
"""

import logging
import traceback
import asyncio
from functools import wraps
from typing import Any, Callable, Optional, Dict, List
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import ADMIN_IDS

logger = logging.getLogger(__name__)

class ErrorSeverity:
    """Уровни критичности ошибок"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ErrorHandler:
    """Централизованный обработчик ошибок"""
    
    def __init__(self, bot: Optional[Bot] = None):
        self.bot = bot
        self.error_counts = {}  # Счетчик ошибок для rate limiting
        self.last_notification = {}  # Время последнего уведомления
        
    async def handle_error(
        self,
        error: Exception,
        context: str = "Unknown",
        severity: str = ErrorSeverity.MEDIUM,
        user_id: Optional[int] = None,
        additional_info: Optional[Dict] = None
    ) -> None:
        """
        Основной метод обработки ошибок
        
        Args:
            error: Исключение
            context: Контекст возникновения ошибки
            severity: Уровень критичности
            user_id: ID пользователя (если применимо)
            additional_info: Дополнительная информация
        """
        
        # Логирование
        error_msg = f"[{severity}] {context}: {str(error)}"
        
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(error_msg, exc_info=True)
        elif severity == ErrorSeverity.HIGH:
            logger.error(error_msg, exc_info=True)
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(error_msg)
        else:
            logger.info(error_msg)
        
        # Уведомление администратора (с rate limiting)
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            await self._notify_admin(error, context, severity, user_id, additional_info)
    
    async def _notify_admin(
        self,
        error: Exception,
        context: str,
        severity: str,
        user_id: Optional[int],
        additional_info: Optional[Dict]
    ) -> None:
        """Отправка уведомления администратору"""
        
        if not self.bot or not ADMIN_IDS:
            return
        
        # Rate limiting - не более 1 уведомления в 5 минут для одного типа ошибки
        error_key = f"{type(error).__name__}_{context}"
        now = datetime.now()
        
        if error_key in self.last_notification:
            if now - self.last_notification[error_key] < timedelta(minutes=5):
                return
        
        self.last_notification[error_key] = now
        
        # Формирование сообщения
        emoji = "🚨" if severity == ErrorSeverity.CRITICAL else "⚠️"
        message = f"{emoji} <b>Ошибка в боте</b>\n\n"
        message += f"<b>Уровень:</b> {severity}\n"
        message += f"<b>Контекст:</b> {context}\n"
        message += f"<b>Ошибка:</b> <code>{str(error)}</code>\n"
        
        if user_id:
            message += f"<b>Пользователь:</b> {user_id}\n"
        
        if additional_info:
            message += f"<b>Доп. информация:</b>\n"
            for key, value in additional_info.items():
                message += f"• {key}: {value}\n"
        
        message += f"<b>Время:</b> {now.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Отправка всем администраторам
        for admin_id in ADMIN_IDS:
            try:
                await self.bot.send_message(admin_id, message, parse_mode="HTML", disable_web_page_preview=True)
            except TelegramAPIError as e:
                logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

# Глобальный экземпляр обработчика ошибок
error_handler = ErrorHandler()

def init_error_handler(bot: Bot) -> None:
    """Инициализация обработчика ошибок с ботом"""
    global error_handler
    error_handler.bot = bot

def handle_errors(
    context: str = "Unknown",
    severity: str = ErrorSeverity.MEDIUM,
    fallback_return: Any = None,
    notify_user: bool = True
):
    """
    Декоратор для автоматической обработки ошибок в функциях
    
    Args:
        context: Контекст выполнения
        severity: Уровень критичности
        fallback_return: Значение для возврата при ошибке
        notify_user: Уведомлять ли пользователя об ошибке
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Определяем user_id если возможно
                user_id = None
                for arg in args:
                    if hasattr(arg, 'from_user') and hasattr(arg.from_user, 'id'):
                        user_id = arg.from_user.id
                        break
                
                # Обрабатываем ошибку
                await error_handler.handle_error(
                    error=e,
                    context=f"{func.__name__} ({context})",
                    severity=severity,
                    user_id=user_id,
                    additional_info={
                        "function": func.__name__,
                        "module": func.__module__
                    }
                )
                
                # Уведомляем пользователя если нужно
                if notify_user and user_id:
                    try:
                        # Ищем объект для ответа пользователю
                        message_obj = None
                        for arg in args:
                            if hasattr(arg, 'answer'):
                                message_obj = arg
                                break
                        
                        if message_obj:
                            if severity == ErrorSeverity.CRITICAL:
                                await message_obj.answer("❌ Произошла критическая ошибка. Администратор уведомлен.")
                            else:
                                await message_obj.answer("⚠️ Произошла ошибка. Попробуйте позже.")
                    except Exception:
                        pass  # Если не удалось уведомить пользователя, не критично
                
                return fallback_return
        
        return wrapper
    return decorator

class APIWrapper:
    """Обертка для безопасной работы с внешними API"""
    
    @staticmethod
    async def safe_api_call(
        api_func: Callable,
        context: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        fallback_value: Any = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Безопасный вызов API с повторными попытками
        
        Args:
            api_func: Функция API для вызова
            context: Контекст вызова
            max_retries: Максимальное количество попыток
            retry_delay: Задержка между попытками
            fallback_value: Значение по умолчанию при неудаче
            *args, **kwargs: Аргументы для API функции
        """
        
        for attempt in range(max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(api_func):
                    return await api_func(*args, **kwargs)
                else:
                    return api_func(*args, **kwargs)
                    
            except Exception as e:
                is_last_attempt = attempt == max_retries
                
                # Определяем уровень критичности
                if "rate limit" in str(e).lower():
                    severity = ErrorSeverity.LOW
                elif is_last_attempt:
                    severity = ErrorSeverity.HIGH
                else:
                    severity = ErrorSeverity.MEDIUM
                
                await error_handler.handle_error(
                    error=e,
                    context=f"{context} (попытка {attempt + 1}/{max_retries + 1})",
                    severity=severity,
                    additional_info={
                        "api_function": api_func.__name__ if hasattr(api_func, '__name__') else str(api_func),
                        "attempt": attempt + 1,
                        "max_retries": max_retries + 1
                    }
                )
                
                if is_last_attempt:
                    logger.error(f"API вызов {context} окончательно неудачен после {max_retries + 1} попыток")
                    return fallback_value
                
                # Экспоненциальная задержка
                await asyncio.sleep(retry_delay * (2 ** attempt))
        
        return fallback_value

def graceful_degradation(fallback_function: Optional[Callable] = None):
    """
    Декоратор для graceful degradation - плавной деградации функциональности
    
    Args:
        fallback_function: Резервная функция для выполнения при ошибке
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await error_handler.handle_error(
                    error=e,
                    context=f"Graceful degradation in {func.__name__}",
                    severity=ErrorSeverity.MEDIUM
                )
                
                if fallback_function:
                    try:
                        if asyncio.iscoroutinefunction(fallback_function):
                            return await fallback_function(*args, **kwargs)
                        else:
                            return fallback_function(*args, **kwargs)
                    except Exception as fallback_error:
                        await error_handler.handle_error(
                            error=fallback_error,
                            context=f"Fallback function {fallback_function.__name__}",
                            severity=ErrorSeverity.HIGH
                        )
                
                return None
        
        return wrapper
    return decorator 