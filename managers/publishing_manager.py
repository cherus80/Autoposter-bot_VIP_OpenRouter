"""managers/publishing_manager.py
=================================================
Хранение настроек публикации и совместимость со старым кодом
-----------------------------------------------------------

• Таблица `PublishingSettings` (user_id, publish_to_tg, publish_to_vk).
• Класс `PublishingManager` — CRUD + helper `publish_telegram()` (учёт
  лимита подписи 1000 символов).
• Прокси‑функции для старого импорта:
    - `get_publishing_settings`
    - `publish_to_telegram`
    - `publish_to_vk`
Все они делегируют внутрь нового класса.
"""
from __future__ import annotations

from typing import Optional

from aiogram import Bot
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import async_session_maker
from database.models import PublishingSettings
from services.vk_service import VKService

MAX_TG_CAPTION_LEN = 1000  # запас от лимита 1024 символа


class PublishingManager:
    """Работа с таблицей PublishingSettings и утилиты отправки."""

    def __init__(self, session_maker=async_session_maker):
        self.session_maker = session_maker

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------
    async def _get_or_create_settings(self, session: AsyncSession, user_id: int):
        stmt = select(PublishingSettings).where(PublishingSettings.user_id == user_id)
        res = await session.execute(stmt)
        settings = res.scalar_one_or_none()

        if not settings:
            settings = PublishingSettings(user_id=user_id)
            session.add(settings)
            await session.commit()
            await session.refresh(settings)

        return settings

    async def get_settings(self, user_id: int = 1):
        async with self.session_maker() as session:
            return await self._get_or_create_settings(session, user_id)

    async def update_settings(
        self,
        user_id: int = 1,
        *,
        publish_to_tg: Optional[bool] = None,
        publish_to_vk: Optional[bool] = None,
    ):
        async with self.session_maker() as session:
            settings = await self._get_or_create_settings(session, user_id)

            values: dict[str, bool] = {}
            if publish_to_tg is not None:
                values["publish_to_tg"] = publish_to_tg
            if publish_to_vk is not None:
                values["publish_to_vk"] = publish_to_vk

            if values:
                stmt = (
                    update(PublishingSettings)
                    .where(PublishingSettings.user_id == user_id)
                    .values(**values)
                )
                await session.execute(stmt)
                await session.commit()
                await session.refresh(settings)

            return settings

    # ------------------------------------------------------------------
    # Telegram helper
    # ------------------------------------------------------------------
    async def publish_telegram(
        self,
        bot: Bot,
        chat_id: int,
        text: str,
        image_url: Optional[str] = None,
        parse_mode: str = "HTML",
    ) -> None:
        """Публикует пост в Telegram с учётом лимита подписи."""

        if image_url and len(text) > MAX_TG_CAPTION_LEN:
            # 1) Длинная подпись → разбиваем
            await bot.send_photo(chat_id=chat_id, photo=image_url)
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, disable_web_page_preview=True)
        elif image_url:
            # 2) Короткая подпись
            await bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=text,
                parse_mode=parse_mode,
            )
        else:
            # 3) Только текст
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, disable_web_page_preview=True)


# ----------------------------------------------------------------------
# ️🔄  Функции‑обёртки для старого кода
# ----------------------------------------------------------------------
_default_manager = PublishingManager()


async def get_publishing_settings(user_id: int = 1):  # noqa: D401
    """Совместимость: возвращает PublishingSettings для указанного user_id."""
    return await _default_manager.get_settings(user_id)


async def publish_to_telegram(*args, **kwargs):  # noqa: D401, ANN001
    """Обёртка старой сигнатуры. Делегирует в `PublishingManager.publish_telegram`."""
    await _default_manager.publish_telegram(*args, **kwargs)


async def publish_to_vk(vk_service: VKService, text: str, image_url: Optional[str] = None):  # noqa: D401
    """Упрощённый прокси: вызывает VKService.post_to_group()."""
    return await vk_service.post_to_group(text, image_url=image_url)

# ------------------------------------------------------------------
# update_publishing_settings — ещё одна совместимая обёртка
# ------------------------------------------------------------------
async def update_publishing_settings(  # noqa: D401
    user_id: int = 1,
    *,
    publish_to_tg: Optional[bool] = None,
    publish_to_vk: Optional[bool] = None,
):
    """Совместимость: старая функция вызывала именно update_publishing_settings."""
    return await _default_manager.update_settings(
        user_id=user_id,
        publish_to_tg=publish_to_tg,
        publish_to_vk=publish_to_vk,
    )


__all__ = [
    "PublishingManager",
    "publish_to_telegram",
    "publish_to_vk",
    "get_publishing_settings",
    "update_publishing_settings",
]
