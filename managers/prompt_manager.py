# managers/prompt_manager.py - Управление промптами AI
import logging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.database import async_session_maker
from database.models import AiPrompts

class PromptManager:
    def __init__(self, session_maker=async_session_maker):
        self.session_maker = session_maker

    async def set_prompt(self, prompt_type: str, prompt_text: str):
        """
        Устанавливает или обновляет промпт указанного типа.
        Возвращает (True, None) при успехе или (False, error_message) при ошибке.
        """
        try:
            async with self.session_maker() as session:
                # Проверяем, существует ли уже промпт такого типа
                stmt = select(AiPrompts).where(AiPrompts.prompt_type == prompt_type)
                result = await session.execute(stmt)
                existing_prompt = result.scalar_one_or_none()
                
                if existing_prompt:
                    # Обновляем существующий
                    stmt_update = (
                        update(AiPrompts)
                        .where(AiPrompts.prompt_type == prompt_type)
                        .values(prompt_text=prompt_text)
                    )
                    await session.execute(stmt_update)
                else:
                    # Создаем новый
                    new_prompt = AiPrompts(prompt_type=prompt_type, prompt_text=prompt_text)
                    session.add(new_prompt)
                
                await session.commit()
            return True, None
        except Exception as e:
            logging.error(f"Ошибка в prompt_manager.set_prompt: {e}")
            return False, str(e)

    async def get_prompt(self, prompt_type: str) -> str | None:
        """
        Получает текст промпта по его типу.
        """
        async with self.session_maker() as session:
            stmt = select(AiPrompts.prompt_text).where(AiPrompts.prompt_type == prompt_type)
            result = await session.execute(stmt)
            prompt_text = result.scalar_one_or_none()
            return prompt_text 