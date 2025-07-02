"""
@file: handlers/generate_post.py
@description: Обработчики генерации постов с FSM
@dependencies: services/ai_service.py, managers/publishing_manager.py, services/vk_service.py
@created: 2025-01-20
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.ai_service import AIService
from services.vk_service import VKService
from managers.publishing_manager import (
    publish_to_telegram,
    get_publishing_settings,
    publish_to_vk,
)
from database.posts_db import save_post
from config import FAL_AI_KEY, OPENAI_API_KEY

logger = logging.getLogger(__name__)
router = Router()
ai_service = AIService()

# ──────────────────────────── FSM ────────────────────────────
class GeneratePost(StatesGroup):
    waiting_for_type = State()
    waiting_for_style = State()
    waiting_for_topic = State()
    waiting_for_edit = State()
    waiting_for_confirm = State()

def _post_type_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🖼️ С картинкой", callback_data="ptype:image"),
                InlineKeyboardButton(text="✍️ Только текст", callback_data="ptype:text"),
            ]
        ]
    )

def _style_kb(prefix: str = "style:") -> InlineKeyboardMarkup:
    styles = {
        "photo": "📷 Фото",
        "digital_art": "🎨 Digital Art",
        "anime": "🌸 Аниме",
        "cyberpunk": "🤖 Киберпанк",
        "none": "🚫 Без стиля",
    }
    buttons = [
        InlineKeyboardButton(text=v, callback_data=f"{prefix}{k}") for k, v in styles.items()
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.callback_query(F.data == "menu:generate_post")
async def cb_menu_generate_post(cb: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Создать пост'"""
    logger.info(f"Callback menu:generate_post от пользователя {cb.from_user.id}")
    await state.set_state(GeneratePost.waiting_for_type)
    await cb.message.edit_text("Выберите тип поста:", reply_markup=_post_type_kb())
    await cb.answer()



# ─────────────────── выбор типа / стиля ───────────────────
@router.callback_query(GeneratePost.waiting_for_type, F.data.startswith("ptype:"))
async def cb_post_type(cb: CallbackQuery, state: FSMContext):
    ptype = cb.data.split(":")[1]
    logger.info(f"Выбран тип поста: {ptype}")
    
    # Проверяем наличие токена Fal.ai при выборе поста с изображением
    if ptype == "image" and not FAL_AI_KEY:
        await cb.message.edit_text(
            "❌ <b>Fal.ai токен НЕ настроен!</b>\n\n"
            "🖼️ Для генерации изображений необходимо настроить FAL_AI_KEY в переменных окружения.\n\n"
            "💡 <i>Обратитесь к администратору или добавьте FAL_AI_KEY в .env файл.</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✍️ Создать текстовый пост", callback_data="ptype:text")],
                [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="menu:main")]
            ])
        )
        await cb.answer("❌ Fal.ai токен не настроен!")
        return
    
    await state.update_data(with_image=(ptype == "image"))
    if ptype == "image":
        await state.set_state(GeneratePost.waiting_for_style)
        await cb.message.edit_text("Выберите стиль изображения:", reply_markup=_style_kb())
    else:
        await state.set_state(GeneratePost.waiting_for_topic)
        await cb.message.edit_text("Введите тему поста текстом или отправьте голосовое сообщение 🎤:")
    await cb.answer()

@router.callback_query(GeneratePost.waiting_for_style, F.data.startswith("style:"))
async def cb_style(cb: CallbackQuery, state: FSMContext):
    style = cb.data.split(":")[1]
    logger.info(f"Выбран стиль: {style}")
    await state.update_data(image_style=style)
    await state.set_state(GeneratePost.waiting_for_topic)
    await cb.message.edit_text("Введите тему поста текстом или отправьте голосовое сообщение 🎤:")
    await cb.answer()

# ─────────────────── получение темы / генерация ───────────────────
@router.message(GeneratePost.waiting_for_topic)
async def msg_topic(msg: Message, state: FSMContext):
    data = await state.get_data()
    topic = None
    
    # Проверяем тип сообщения и извлекаем тему
    if msg.text:
        topic = msg.text.strip()
    elif msg.voice:
        # Проверяем доступность OpenAI API ключа для транскрипции
        if not OPENAI_API_KEY:
            await msg.answer(
                "❌ <b>OpenAI API ключ НЕ настроен!</b>\n\n"
                "🎤 Для распознавания голосовых сообщений необходимо настроить OPENAI_API_KEY в переменных окружения.\n\n"
                "💡 <i>Обратитесь к администратору или добавьте OPENAI_API_KEY в .env файл.</i>\n\n"
                "✍️ Пожалуйста, введите тему поста текстом."
            )
            return
        
        # Обрабатываем голосовое сообщение
        await msg.answer("🎤 Распознаю голосовое сообщение...")
        
        try:
            from utils.text_utils import transcribe_voice_message
            transcribed_text = await transcribe_voice_message(msg.bot, msg.voice)
            
            if transcribed_text:
                topic = transcribed_text.strip()
                await msg.answer(f"✅ Распознано: \"{topic}\"\n\n⏳ Генерирую пост...")
            else:
                await msg.answer("❌ Не удалось распознать голосовое сообщение. Попробуйте еще раз или введите тему текстом.")
                return
        except Exception as e:
            logger.error(f"Ошибка при обработке голосового сообщения: {e}")
            await msg.answer("❌ Произошла ошибка при распознавании голосового сообщения. Пожалуйста, введите тему текстом.")
            return
    elif msg.caption:
        topic = msg.caption.strip()
    else:
        await msg.answer("❌ Пожалуйста, введите тему поста текстом или голосовым сообщением.")
        return
    
    if not topic:
        await msg.answer("❌ Тема не может быть пустой. Введите тему поста:")
        return
        
    logger.info(f"Тема поста: {topic}")
    
    # Если это не голосовое сообщение, показываем стандартное сообщение
    if not msg.voice:
        await msg.answer("⏳ Генерирую пост…")
    
    try:
        # Получаем правильный системный промпт из менеджера промптов
        system_prompt = await ai_service.prompt_manager.get_prompt('content_generation')
        
        # Генерируем пост через OpenRouter
        result = await ai_service.generate_post(
            topic=topic,
            with_image=data.get("with_image", False),
            image_style=data.get("image_style", "none"),
            system_prompt=system_prompt
        )
        
        # Проверяем результат генерации
        if not result or not result.get("text"):
            # OpenRouter API недоступен или вернул пустой результат
            await msg.answer(
                "⚠️ <b>Временные проблемы с генерацией постов</b>\n\n"
                "🔄 Сервис OpenRouter.ai временно недоступен. Было выполнено несколько попыток подключения.\n\n"
                "💡 <i>Попробуйте еще раз через 1-2 минуты или обратитесь к администратору.</i>\n\n"
                "🔧 Для администратора: проверьте логи бота и статус OpenRouter.ai"
            )
            await state.clear()
            return
        
        # Улучшаем качество поста
        from utils.text_utils import TextUtils
        improved_text = TextUtils.improve_post_quality(result["text"])
        
        await state.update_data(
            post_text=improved_text, 
            image_url=result.get("image_url"),
            topic=topic  # Сохраняем тему для последующего использования
        )

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Опубликовать", callback_data="post:publish"),
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data="post:edit"),
                ]
            ]
        )
        await msg.answer(improved_text, reply_markup=kb, disable_web_page_preview=True)
        await state.set_state(GeneratePost.waiting_for_confirm)
    except Exception as e:
        logger.error(f"Ошибка генерации поста: {e}")
        
        # Проверяем, связана ли ошибка с OpenRouter API
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['openrouter', 'connection', 'timeout', 'api']):
            await msg.answer(
                "⚠️ <b>Проблемы с подключением к AI сервису</b>\n\n"
                "🔄 Не удалось подключиться к OpenRouter.ai после нескольких попыток.\n\n"
                "💡 <i>Проверьте подключение к интернету и попробуйте еще раз через минуту.</i>\n\n"
                "🆘 Если проблема повторяется, обратитесь к администратору."
            )
        else:
            await msg.answer(
                "❌ <b>Ошибка при генерации поста</b>\n\n"
                "🔧 Произошла техническая ошибка. Попробуйте еще раз.\n\n"
                "💡 <i>Если проблема повторяется, обратитесь к администратору.</i>"
            )
        await state.clear()

# ─────────────────── редактирование / публикация ───────────────────
@router.callback_query(GeneratePost.waiting_for_confirm, F.data == "post:edit")
async def cb_edit_post(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Отправьте скорректированный текст:")
    await state.set_state(GeneratePost.waiting_for_edit)
    await cb.answer()

@router.message(GeneratePost.waiting_for_edit)
async def msg_edited(msg: Message, state: FSMContext):
    # Проверяем тип сообщения и извлекаем текст
    if msg.text:
        edited_text = msg.text
    elif msg.caption:
        edited_text = msg.caption
    else:
        await msg.answer("❌ Пожалуйста, отправьте текст для редактирования поста.")
        return
    
    if not edited_text.strip():
        await msg.answer("❌ Текст поста не может быть пустым.")
        return
        
    await state.update_data(post_text=edited_text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Опубликовать", callback_data="post:publish")]])
    await msg.answer("Готово:")
    await msg.answer(edited_text, reply_markup=kb, disable_web_page_preview=True)
    await state.set_state(GeneratePost.waiting_for_confirm)

@router.callback_query(GeneratePost.waiting_for_confirm, F.data == "post:publish")
async def cb_publish(cb: CallbackQuery, state: FSMContext):
    """Публикация поста в соответствии с настройками пользователя"""
    try:
        data = await state.get_data()
        post_text = data["post_text"]
        image_url = data.get("image_url")
        
        # Получаем настройки публикации
        settings = await get_publishing_settings(user_id=cb.from_user.id)
        
        published_platforms = []
        errors = []
        
        # Публикация в Telegram
        if settings.publish_to_tg:
            try:
                # Используем chat_id из конфигурации, а не текущий чат
                from config import CHANNEL_ID
                if CHANNEL_ID:
                    # Форматируем текст специально для Telegram
                    from utils.text_utils import TextUtils
                    tg_formatted_text = TextUtils.format_for_platform(post_text, "telegram")
                    await publish_to_telegram(cb.bot, CHANNEL_ID, tg_formatted_text, image_url)
                    published_platforms.append("Telegram")
                else:
                    logger.warning("CHANNEL_ID не настроен")
                    errors.append("Telegram (не настроен канал)")
            except Exception as e:
                logger.error(f"Ошибка публикации в Telegram: {e}")
                errors.append(f"Telegram ({str(e)})")
        
        # Публикация в VK
        if settings.publish_to_vk:
            try:
                vk_service = VKService()
                # Проверяем что VK сервис настроен
                if vk_service.is_configured:
                    # Форматируем текст специально для VK
                    from utils.text_utils import TextUtils
                    vk_formatted_text = TextUtils.format_for_platform(post_text, "vk")
                    success = await publish_to_vk(vk_service, vk_formatted_text, image_url)
                    if success:
                        published_platforms.append("VK")
                    else:
                        errors.append("VK (ошибка публикации)")
                else:
                    errors.append("VK (не настроен - отсутствуют токены)")
            except Exception as e:
                logger.error(f"Ошибка публикации в VK: {e}")
                errors.append(f"VK ({str(e)})")
        
        # Сохраняем пост в базу данных при успешной публикации
        if published_platforms:
            try:
                # Определяем какие платформы опубликованы
                platforms = {
                    'telegram': 'Telegram' in published_platforms,
                    'vk': 'VK' in published_platforms
                }
                
                # Определяем тему из FSM или используем начало текста
                topic = data.get("topic", post_text[:50] + "..." if len(post_text) > 50 else post_text)
                
                # Сохраняем в БД
                await save_post(
                    content=post_text,
                    with_image=bool(image_url),
                    image_url=image_url,
                    platforms=platforms,
                    topic=topic,
                    post_type="Ручной"
                )
                
                logger.info(f"Пост сохранен в базу данных. Платформы: {published_platforms}")
                
            except Exception as e:
                logger.error(f"Ошибка сохранения поста в БД: {e}")
                # Не прерываем выполнение, только логируем ошибку
        
        # Формируем ответ
        if published_platforms:
            success_msg = f"✅ Пост опубликован в: {', '.join(published_platforms)}"
            if errors:
                success_msg += f"\n⚠️ Ошибки: {', '.join(errors)}"
            await cb.message.answer(success_msg)
        else:
            if errors:
                await cb.message.answer(f"❌ Ошибки публикации:\n{chr(10).join(errors)}")
            else:
                await cb.message.answer("⚠️ Ни одна платформа не настроена для публикации")
        
        await state.clear()
        await cb.answer()
        
    except Exception as e:
        logger.error(f"Критическая ошибка публикации: {e}")
        await cb.answer("❌ Критическая ошибка при публикации") 