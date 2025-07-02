"""
@file: handlers/admin_handlers.py
@description: Middleware проверки прав доступа администратора
@dependencies: config.py
@created: 2025-01-20
"""

import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.dispatcher.middlewares.base import BaseMiddleware

from config import ADMIN_IDS

logger = logging.getLogger(__name__)

# ─────────── Middleware проверки администратора ───────────
class AdminCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Проверяем, что это Message или CallbackQuery
        if hasattr(event, 'from_user') and event.from_user:
            user_id = event.from_user.id
            
            logger.info(f"Проверка доступа: user_id={user_id}, admin_ids={ADMIN_IDS}")
            
            if user_id not in ADMIN_IDS:
                logger.warning(f"Отказано в доступе для пользователя {user_id}")
                # Для CallbackQuery отвечаем
                if isinstance(event, CallbackQuery):
                    await event.answer("❌ У вас нет доступа к этому боту")
                # Для Message отвечаем
                elif isinstance(event, Message):
                    await event.answer("❌ У вас нет доступа к этому боту")
                return
            
            logger.info(f"Доступ разрешен для администратора {user_id}")
        
        return await handler(event, data)