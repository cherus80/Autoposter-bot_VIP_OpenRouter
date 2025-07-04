"""services/scheduler.py – Планировщик автопостинга
---------------------------------------------------
Исправляет три замеченные проблемы:
1. Настройка «пост без картинки» игнорировалась.
   Теперь берём флаг `autofeed_with_image` из settings и
   учитываем его при решении генерировать картинку.
2. Планировщик читает настройки публикации (Telegram / VK)
   из той же записи пользователя, что и обработчики меню
   (`user_id = int(ADMIN_ID)`), поэтому VK‑флажок сохраняется.
3. Команда выключения автопостинга сразу останавливает
   текущий цикл ожидания, без необходимости перезапуска бота.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict

from aiogram import Bot

from config import CHANNEL_ID, ADMIN_ID
from database.posts_db import get_last_post_time, save_post
from database.settings_db import get_setting, update_setting
from managers.content_plan_manager import ContentPlanManager
from managers.prompt_manager import PromptManager
from managers.publishing_manager import PublishingManager
from services.ai_service import AIService
from services.image_service import ImageService
from services.vk_service import VKService
from utils.error_handler import handle_errors, ErrorSeverity, error_handler
from utils.text_utils import TextUtils


class PostScheduler:
    """Отвечает за автосоздание и публикацию контента."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.is_running = False

        # Сервисы / менеджеры
        self.ai_service = AIService()
        self.image_service = ImageService()
        self.vk_service = VKService()
        self.prompt_manager = PromptManager()
        self.content_plan_manager = ContentPlanManager()
        self.publishing_manager = PublishingManager()

    # -------------------------------------------------------------
    # Универсальная публикация (TG + VK)
    # -------------------------------------------------------------
    async def publish_post(
        self,
        content: str,
        image_url: str | None = None,
        topic: str = "Ручная генерация",
        category: str = "Пост",
    ) -> Dict[str, bool]:
        logging.info("[Publisher] Начало публикации поста на тему: %s", topic)

        # ❗ читаем настройки того же пользователя, что кликает галочки
        pub_settings = await self.publishing_manager.get_settings(user_id=int(ADMIN_ID))

        tg_ok = vk_ok = False

        # ---------- Telegram ----------
        if pub_settings.publish_to_tg:
            logging.info("[Publisher] Попытка публикации в Telegram…")
            # Форматируем текст специально для Telegram (Markdown)
            tg_content = TextUtils.format_for_platform(content, "telegram")

            if image_url and len(tg_content) > 1000:
                await self.bot.send_photo(CHANNEL_ID, photo=image_url, parse_mode='HTML')
                await self.bot.send_message(CHANNEL_ID, tg_content, parse_mode='HTML', disable_web_page_preview=True)
            elif image_url:
                await self.bot.send_photo(CHANNEL_ID, photo=image_url, caption=tg_content, parse_mode='HTML')
            else:
                await self.bot.send_message(CHANNEL_ID, tg_content, parse_mode='HTML', disable_web_page_preview=True)

            logging.info("[Publisher] Пост опубликован в Telegram.")
            tg_ok = True

        # ---------- VK ----------
        if pub_settings.publish_to_vk:
            logging.info("[Publisher] Попытка публикации в VK…")
            await asyncio.sleep(random.randint(5, 15))  # анти‑спам
            
            # Проверяем что VK сервис настроен
            if self.vk_service.is_configured:
                # Форматируем текст специально для VK (простой текст)
                vk_content = TextUtils.format_for_platform(content, "vk")
                success = await self.vk_service.post_to_group(vk_content, image_url=image_url)
                if success:
                    logging.info("[Publisher] Пост опубликован в VK.")
                    vk_ok = True
                else:
                    logging.warning("[Publisher] Ошибка публикации в VK.")
            else:
                logging.warning("[Publisher] VK не настроен - отсутствуют токены. Пропускаем публикацию.")

        # Save to DB if any platform succeeded
        if tg_ok or vk_ok:
            await save_post(
                content=content,
                with_image=bool(image_url),
                image_url=image_url,
                platforms={"telegram": tg_ok, "vk": vk_ok},
                topic=topic,
                post_type=category,
                published_at=datetime.utcnow(),
            )
            logging.info("[Publisher] Данные поста сохранены в БД.")
        else:
            logging.info("[Publisher] Пост не опубликован — платформы выключены.")

        return {"telegram": tg_ok, "vk": vk_ok}

    # -------------------------------------------------------------
    # Основной цикл планировщика
    # -------------------------------------------------------------
    async def start(self):
        self.is_running = True
        logging.info("Планировщик запущен. Ожидает включения режима автопостинга.")

        while self.is_running:
            try:
                auto_mode = await get_setting("auto_mode_status", "off")
                if auto_mode != "on":
                    await asyncio.sleep(60)
                    continue

                interval_min = int(await get_setting("post_interval_minutes", "240"))
                last_time = await get_last_post_time()
                
                # Если постов нет - публикуем сразу, иначе рассчитываем время ожидания
                if not last_time:
                    sleep_sec = 0  # Публикуем сразу, если это первый пост
                    logging.info("[Scheduler] Постов в БД нет. Публикуем первый пост сразу.")
                else:
                    sleep_sec = (last_time + timedelta(minutes=interval_min) - datetime.utcnow()).total_seconds()
                    if sleep_sec <= 0:
                        logging.info("[Scheduler] Время публикации пришло! Интервал прошел.")
                    else:
                        logging.info("[Scheduler] До следующей публикации: %.1f мин.", sleep_sec / 60)
                
                if sleep_sec > 0:
                    # проверяем каждые 30 с, не выключили ли автопостинг
                    while sleep_sec > 0 and (await get_setting("auto_mode_status", "off")) == "on":
                        await asyncio.sleep(min(30, sleep_sec))
                        sleep_sec -= 30
                    continue  # начнём цикл заново, чтобы пересчитать

                # --- запускаем публикацию ---
                logging.info("Время публикации! Запускаю auto_post_cycle…")
                await self.auto_post_cycle()

            except Exception as exc:
                logging.error("[Scheduler] Ошибка: %s", exc, exc_info=True)
                await asyncio.sleep(300)  # 5 мин откат при ошибке

    # -------------------------------------------------------------
    # Генерация + публикация одного поста
    # -------------------------------------------------------------
    async def auto_post_cycle(self):
        logging.info("[Auto-Post] Новый цикл.")

        # Добавляем подробное логирование
        logging.info("[Auto-Post] Проверяем контент-план...")
        topic = await self.content_plan_manager.get_next_topic()
        
        if not topic:
            logging.warning("[Auto-Post] Контент‑план пуст. Останавливаю автопостинг.")
            await update_setting("auto_mode_status", "off")
            await update_setting("auto_posting_enabled", 0)
            logging.info("[Auto-Post] Настройки автопостинга обновлены: выключен.")
            return
        
        logging.info(f"[Auto-Post] Найдена тема: ID={topic.id}, theme='{topic.theme}', category='{topic.category}'")

        # --- настройки картинок ---
        with_image_setting = await get_setting("autofeed_with_image", "off")
        image_prompt_template = await self.prompt_manager.get_prompt("image")
        with_image = with_image_setting == "on" and bool(image_prompt_template)
        
        logging.info(f"[Auto-Post] Настройки изображений: with_image_setting={with_image_setting}, with_image={with_image}")
        
        # --- получаем стиль изображения ---
        image_style = None
        if with_image:
            image_style = await get_setting("autofeed_image_style", "fantasy")
            logging.info(f"[Auto-Post] Используется стиль изображения: {image_style}")

        # --- генерируем пост (текст + изображение) ---
        content_prompt = await self.prompt_manager.get_prompt("content_generation")
        logging.info(f"[Auto-Post] Генерируем пост для темы: {topic.theme}")
        
        try:
            result = await self.ai_service.generate_post_from_plan(
                content_prompt,
                topic,
                with_image=with_image,
                image_style=image_style
            )
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: если генерация не удалась - НЕ публикуем!
            if not result or not result.get("text"):
                logging.error(f"[Auto-Post] ❌ Генерация поста провалилась для темы: {topic.theme}")
                logging.error("[Auto-Post] Пост НЕ будет опубликован в канал!")
                
                # Уведомляем администратора о проблеме с OpenRouter
                try:
                    await self.bot.send_message(
                        ADMIN_ID,
                        f"⚠️ <b>Проблемы с автопостингом</b>\n\n"
                        f"🔄 OpenRouter.ai не ответил на запрос генерации поста после нескольких попыток.\n\n"
                        f"📝 <b>Тема:</b> {topic.theme}\n"
                        f"🏷️ <b>Категория:</b> {topic.category}\n\n"
                        f"💡 <i>Возможные причины:</i>\n"
                        f"• Временные проблемы с OpenRouter.ai\n"
                        f"• Превышен лимит API\n"
                        f"• Проблемы с интернет-соединением\n\n"
                        f"🔧 <b>Что делать:</b>\n"
                        f"• Проверьте статус OpenRouter.ai\n"
                        f"• Убедитесь что API ключ действителен\n"
                        f"• Автопостинг продолжит работу при следующем цикле",
                        parse_mode='HTML'
                    )
                except Exception as notify_error:
                    logging.error(f"[Auto-Post] Не удалось отправить уведомление администратору: {notify_error}")
                return
                
        except Exception as e:
            logging.error(f"[Auto-Post] ❌ КРИТИЧЕСКАЯ ОШИБКА генерации поста для темы: {topic.theme}")
            logging.error(f"[Auto-Post] Ошибка: {e}")
            logging.error("[Auto-Post] Пост НЕ будет опубликован в канал!")
            
            # Определяем тип ошибки и уведомляем администратора
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['openrouter', 'connection', 'timeout', 'api']):
                # Ошибка связана с OpenRouter API
                try:
                    await self.bot.send_message(
                        ADMIN_ID,
                        f"🚨 <b>Критическая ошибка автопостинга</b>\n\n"
                        f"🔄 Не удалось подключиться к OpenRouter.ai после нескольких попыток.\n\n"
                        f"📝 <b>Тема:</b> {topic.theme}\n"
                        f"🏷️ <b>Категория:</b> {topic.category}\n"
                        f"❌ <b>Ошибка:</b> {str(e)[:200]}...\n\n"
                        f"💡 <i>Требуется проверка:</i>\n"
                        f"• Статус сервиса OpenRouter.ai\n"
                        f"• Интернет-соединение сервера\n"
                        f"• Валидность API ключа\n"
                        f"• Остаток средств на аккаунте\n\n"
                        f"🔧 Автопостинг продолжит работу при следующем цикле.",
                        parse_mode='HTML'
                    )
                except Exception as notify_error:
                    logging.error(f"[Auto-Post] Не удалось отправить уведомление администратору: {notify_error}")
            else:
                # Другие типы ошибок
                try:
                    await self.bot.send_message(
                        ADMIN_ID,
                        f"🚨 <b>Техническая ошибка автопостинга</b>\n\n"
                        f"⚠️ Произошла непредвиденная ошибка при генерации поста.\n\n"
                        f"📝 <b>Тема:</b> {topic.theme}\n"
                        f"🏷️ <b>Категория:</b> {topic.category}\n"
                        f"❌ <b>Ошибка:</b> {str(e)[:200]}...\n\n"
                        f"🔧 Рекомендуется проверить логи бота для диагностики.",
                        parse_mode='HTML'
                    )
                except Exception as notify_error:
                    logging.error(f"[Auto-Post] Не удалось отправить уведомление администратору: {notify_error}")
            return
        
        post_text = result["text"]
        image_url = result.get("image_url")
        
        logging.info(f"[Auto-Post] ✅ Пост сгенерирован успешно. Длина текста: {len(post_text)}, есть изображение: {bool(image_url)}")

        # --- улучшаем качество поста ---
        logging.info("[Auto-Post] Применяем улучшения качества поста...")
        post_text = TextUtils.improve_post_quality(post_text)
        logging.info(f"[Auto-Post] Качество поста улучшено. Финальная длина: {len(post_text)}")

        # --- публикуем ---
        await self.publish_post(
            content=post_text,
            image_url=image_url,
            topic=topic.theme,
            category=topic.category,
        )

        # отмечаем тему использованной
        logging.info(f"[Auto-Post] Помечаем тему ID={topic.id} как использованную")
        await self.content_plan_manager.mark_topic_as_used(topic.id)
        logging.info(f"[Auto-Post] Тема ID={topic.id} помечена как использованная")

    # -------------------------------------------------------------
    def stop(self):
        self.is_running = False
        logging.info("Планировщик остановлен.") 