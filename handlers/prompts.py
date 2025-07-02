"""
@file: handlers/prompts_simple.py
@description: Упрощенные обработчики настройки промптов для ИИ без проблемных символов
@dependencies: managers/prompt_manager.py
@created: 2025-01-21
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from managers.prompt_manager import PromptManager

logger = logging.getLogger(__name__)
router = Router()
prompt_manager = PromptManager()

def escape_html(text: str) -> str:
    """Экранирует HTML теги для безопасного отображения в Telegram"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# FSM для настройки промптов
class SetPrompt(StatesGroup):
    waiting_for_content_prompt = State()
    waiting_for_image_prompt = State()

@router.callback_query(F.data == "menu:set_content_prompt")
async def cb_set_content_prompt(cb: CallbackQuery, state: FSMContext):
    """Настройка промпта для генерации текста"""
    await state.set_state(SetPrompt.waiting_for_content_prompt)
    
    # Очищаем накопленный промпт при начале новой сессии
    await state.update_data(accumulated_prompt="", prompt_parts_count=0)
    
    message_text = (
        "📝 <b>Настройка промпта для генерации текста</b>\n\n"
        "Отправьте новый промпт обычным сообщением.\n\n"
        "💡 <b>Советы:</b>\n"
        "• Укажите роль AI\n"
        "• Опишите целевую аудиторию\n"
        "• Задайте тон общения\n"
        "• Определите структуру поста\n\n"
        "⚠️ <b>Важно:</b> Если промпт длинный (>4000 символов), Telegram может разбить его на части. "
        "Не волнуйтесь - бот соберет все части автоматически!"
    )
    
    await cb.message.edit_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📄 Показать полный промпт", callback_data="prompt:show_content")],
                [InlineKeyboardButton(text="💡 Пример хорошего промпта", callback_data="prompt:example_content")],
                [InlineKeyboardButton(text="📚 Полный гайд по настройке", callback_data="prompts:help_guide")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="prompt:cancel")]
            ]
        ),
        disable_web_page_preview=True,
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data == "menu:set_image_prompt")
async def cb_set_image_prompt(cb: CallbackQuery, state: FSMContext):
    """Настройка промпта для генерации изображений"""
    await state.set_state(SetPrompt.waiting_for_image_prompt)
    
    message_text = (
        "Настройка промпта для генерации изображений\n\n"
        "Отправьте новый промпт обычным сообщением.\n\n"
        "Советы\n"
        "Укажите роль для AI художника\n"
        "Опишите желаемый стиль\n"
        "Задайте композицию\n"
        "Используйте плейсхолдер post_text"
    )
    
    await cb.message.edit_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📄 Показать полный промпт", callback_data="prompt:show_image")],
                [InlineKeyboardButton(text="💡 Пример хорошего промпта", callback_data="prompt:example_image")],
                [InlineKeyboardButton(text="📚 Полный гайд по настройке", callback_data="prompts:help_guide")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="prompt:cancel")]
            ]
        ),
        disable_web_page_preview=True
    )
    await cb.answer()

@router.message(SetPrompt.waiting_for_content_prompt)
async def process_content_prompt(msg: Message, state: FSMContext):
    """Обработка ввода промпта для текста с накоплением частей"""
    if not msg.text:
        await msg.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с промптом.",
            disable_web_page_preview=True
        )
        return
    
    # Получаем данные состояния
    state_data = await state.get_data()
    accumulated_prompt = state_data.get("accumulated_prompt", "")
    parts_count = state_data.get("prompt_parts_count", 0)
    
    # Добавляем текущую часть к накопленному промпту
    current_part = msg.text.strip()
    if accumulated_prompt:
        # Добавляем пробел между частями если накопленный промпт не пустой
        accumulated_prompt += " " + current_part
    else:
        accumulated_prompt = current_part
    
    parts_count += 1
    
    logging.info(f"Получена часть {parts_count} промпта длиной {len(current_part)} символов. Общая длина: {len(accumulated_prompt)}")
    
    # Обновляем состояние
    await state.update_data(
        accumulated_prompt=accumulated_prompt,
        prompt_parts_count=parts_count
    )
    
    # Проверяем лимиты
    if len(accumulated_prompt) < 10:
        await msg.answer(
            "⚠️ Промпт слишком короткий! Минимум 10 символов.",
            disable_web_page_preview=True
        )
        return
    
    if len(accumulated_prompt) > 8000:
        await msg.answer(
            f"⚠️ Промпт слишком длинный! Максимум 8000 символов.\n\n"
            f"📏 Текущая длина: <b>{len(accumulated_prompt)}</b> символов\n"
            f"🔄 Сократите на <b>{len(accumulated_prompt) - 8000}</b> символов\n"
            f"📦 Частей получено: <b>{parts_count}</b>",
            disable_web_page_preview=True,
            parse_mode="HTML"
        )
        # Сбрасываем состояние при превышении лимита
        await state.update_data(accumulated_prompt="", prompt_parts_count=0)
        return
    
    # Даем пользователю время отправить дополнительные части (ждем 3 секунды)
    import asyncio
    await asyncio.sleep(3)
    
    # Проверяем, не изменилось ли состояние за это время (новая часть не пришла)
    updated_state_data = await state.get_data()
    updated_accumulated = updated_state_data.get("accumulated_prompt", "")
    updated_parts_count = updated_state_data.get("prompt_parts_count", 0)
    
    # Если состояние изменилось (пришла еще одна часть), выходим и ждем следующую
    if updated_parts_count > parts_count or len(updated_accumulated) > len(accumulated_prompt):
        logging.info(f"Обнаружена новая часть промпта, ждем завершения...")
        return
    
    # Если за 3 секунды новых частей не поступило - считаем промпт полным
    final_prompt = updated_accumulated
    final_parts_count = updated_parts_count
    
    logging.info(f"Промпт считается завершенным. Частей: {final_parts_count}, длина: {len(final_prompt)} символов")
    
    # Сохраняем полный промпт
    success, error = await prompt_manager.set_prompt("content_generation", final_prompt)
    
    if success:
        await msg.answer(
            f"✅ <b>Промпт для генерации текста обновлен!</b>\n\n"
            f"📏 Общая длина: <b>{len(final_prompt)}</b> символов\n"
            f"📦 Частей обработано: <b>{final_parts_count}</b>\n"
            f"💾 Сохранен в базу данных",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="📋 Назад в меню", callback_data="back_to_menu")]]
            ),
            disable_web_page_preview=True,
            parse_mode="HTML"
        )
        logging.info(f"Полный промпт успешно сохранен в БД: {final_parts_count} частей, {len(final_prompt)} символов")
    else:
        await msg.answer(
            f"❌ <b>Ошибка сохранения промпта:</b> {error}",
            disable_web_page_preview=True,
            parse_mode="HTML"
        )
        logging.error(f"Ошибка сохранения полного промпта: {error}")
    
    # Очищаем состояние после успешного сохранения
    await state.clear()

@router.message(SetPrompt.waiting_for_image_prompt)
async def process_image_prompt(msg: Message, state: FSMContext):
    """Обработка ввода промпта для изображений"""
    if not msg.text:
        await msg.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с промптом.",
            disable_web_page_preview=True
        )
        return
    
    prompt_text = msg.text.strip()
    
    if len(prompt_text) < 10:
        await msg.answer(
            "⚠️ Промпт слишком короткий! Минимум 10 символов.",
            disable_web_page_preview=True
        )
        return
    
    if len(prompt_text) > 8000:
        await msg.answer(
            f"⚠️ Промпт слишком длинный! Максимум 8000 символов.\n\n"
            f"📏 Ваш промпт: <b>{len(prompt_text)}</b> символов.\n"
            f"🔄 Сократите на <b>{len(prompt_text) - 8000}</b> символов.",
            disable_web_page_preview=True,
            parse_mode="HTML"
        )
        return
    
    # Логируем попытку сохранения
    logging.info(f"Попытка сохранения промпта изображений длиной {len(prompt_text)} символов")
    
    # Сохраняем промпт
    success, error = await prompt_manager.set_prompt("image", prompt_text)
    
    if success:
        await msg.answer(
            f"✅ <b>Промпт для генерации изображений обновлен!</b>\n\n"
            f"📏 Длина: <b>{len(prompt_text)}</b> символов\n"
            f"💾 Сохранен в базу данных",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="📋 Назад в меню", callback_data="back_to_menu")]]
            ),
            disable_web_page_preview=True,
            parse_mode="HTML"
        )
        logging.info(f"Промпт изображений успешно сохранен в БД, длина: {len(prompt_text)} символов")
    else:
        await msg.answer(
            f"❌ <b>Ошибка сохранения промпта:</b> {error}",
            disable_web_page_preview=True,
            parse_mode="HTML"
        )
        logging.error(f"Ошибка сохранения промпта изображений: {error}")
    
    await state.clear()

@router.callback_query(F.data == "prompt:show_content")
async def cb_show_content_prompt(cb: CallbackQuery):
    """Показать полный промпт для текста"""
    current_prompt = await prompt_manager.get_prompt("content_generation")
    
    if current_prompt:
        # Экранируем HTML теги в промпте для безопасного отображения
        escaped_prompt = escape_html(current_prompt)
        
        # Разбиваем длинные промпты на части (лимит Telegram 4096 символов)
        max_length = 4000  # Оставляем запас для заголовка и разметки
        
        if len(escaped_prompt) <= max_length:
            # Короткий промпт - отправляем одним сообщением
            await cb.message.answer(
                f"📄 <b>Полный промпт для генерации текста:</b>\n\n<code>{escaped_prompt}</code>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:set_content_prompt")]]
                ),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        else:
            # Длинный промпт - разбиваем на части
            parts = []
            current_part = ""
            
            for line in escaped_prompt.split('\n'):
                if len(current_part + line + '\n') > max_length:
                    if current_part:
                        parts.append(current_part.strip())
                        current_part = line + '\n'
                    else:
                        # Строка слишком длинная, разбиваем принудительно
                        parts.append(line[:max_length])
                        current_part = line[max_length:] + '\n'
                else:
                    current_part += line + '\n'
            
            if current_part:
                parts.append(current_part.strip())
            
            # Отправляем первую часть с заголовком
            await cb.message.answer(
                f"📄 <b>Полный промпт для генерации текста (часть 1/{len(parts)}):</b>\n\n<code>{parts[0]}</code>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            
            # Отправляем остальные части
            for i, part in enumerate(parts[1:], 2):
                await cb.message.answer(
                    f"📄 <b>Продолжение (часть {i}/{len(parts)}):</b>\n\n<code>{part}</code>",
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            
            # Отправляем кнопку "Назад" отдельным сообщением
            await cb.message.answer(
                "📄 <b>Промпт полностью отображен выше</b>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:set_content_prompt")]]
                ),
                disable_web_page_preview=True,
                parse_mode="HTML"
            )
    else:
        await cb.answer("❌ Промпт не установлен", show_alert=True)
    
    await cb.answer()

@router.callback_query(F.data == "prompt:show_image")
async def cb_show_image_prompt(cb: CallbackQuery):
    """Показать полный промпт для изображений"""
    current_prompt = await prompt_manager.get_prompt("image")
    
    if current_prompt:
        # Экранируем HTML теги в промпте для безопасного отображения
        escaped_prompt = escape_html(current_prompt)
        
        # Разбиваем длинные промпты на части (лимит Telegram 4096 символов)
        max_length = 4000  # Оставляем запас для заголовка и разметки
        
        if len(escaped_prompt) <= max_length:
            # Короткий промпт - отправляем одним сообщением
            await cb.message.answer(
                f"🖼️ <b>Полный промпт для генерации изображений:</b>\n\n<code>{escaped_prompt}</code>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:set_image_prompt")]]
                ),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        else:
            # Длинный промпт - разбиваем на части
            parts = []
            current_part = ""
            
            for line in escaped_prompt.split('\n'):
                if len(current_part + line + '\n') > max_length:
                    if current_part:
                        parts.append(current_part.strip())
                        current_part = line + '\n'
                    else:
                        # Строка слишком длинная, разбиваем принудительно
                        parts.append(line[:max_length])
                        current_part = line[max_length:] + '\n'
                else:
                    current_part += line + '\n'
            
            if current_part:
                parts.append(current_part.strip())
            
            # Отправляем первую часть с заголовком
            await cb.message.answer(
                f"🖼️ <b>Полный промпт для генерации изображений (часть 1/{len(parts)}):</b>\n\n<code>{parts[0]}</code>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            
            # Отправляем остальные части
            for i, part in enumerate(parts[1:], 2):
                await cb.message.answer(
                    f"🖼️ <b>Продолжение (часть {i}/{len(parts)}):</b>\n\n<code>{part}</code>",
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            
            # Отправляем кнопку "Назад" отдельным сообщением
            await cb.message.answer(
                "🖼️ <b>Промпт полностью отображен выше</b>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:set_image_prompt")]]
                ),
                disable_web_page_preview=True,
                parse_mode="HTML"
            )
    else:
        await cb.answer("❌ Промпт не установлен", show_alert=True)
    
    await cb.answer()

@router.callback_query(F.data == "prompt:example_content")
async def cb_example_content_prompt(cb: CallbackQuery):
    """Показать пример хорошего промпта для текста"""
    example_prompt = """Ты эксперт и блогер по AI и автоматизации. Пиши ТОЛЬКО по-русски посты для подписчиков Telegram-канала про AI от первого лица.

КРИТИЧЕСКИ ВАЖНО! Строго соблюдай структуру:

ОБЯЗАТЕЛЬНАЯ СТРУКТУРА:
1. <b>Конкретный результат/цифра: краткое описание</b>
2. Пустая строка  
3. 🎯 Эмодзи + первый абзац (1-2 предложения)
4. 🚀 Эмодзи + второй абзац (1-2 предложения)  
5. 📊 Эмодзи + третий абзац с цифрами (1-2 предложения)
6. 💡 Эмодзи + четвертый абзац (1-2 предложения)
7. ⚡ Эмодзи + пятый абзац (1-2 предложения)
8. 🔥 Эмодзи + шестой абзац (1-2 предложения)
9. Пустая строка
10. Призыв к действию с подпиской на канал (указать ссылку)
11. Пустая строка
12. 3-5 хэштегов через пробел

ФОРМАТИРОВАНИЕ БЕЗ ИСКЛЮЧЕНИЙ:
• ТОЛЬКО HTML-теги: <b></b> и <i></i>
• НИКАКИХ ** или __ символов!
• Цифры и ключевые термины ВСЕГДА в <b></b>
• Инструменты/технологии в <i></i>
• Один эмодзи в начале каждого абзаца

ОБЯЗАТЕЛЬНЫЕ ЭЛЕМЕНТЫ:
• Конкретные цифры в каждом посте
• Временные рамки ("за 3 недели", "месяц назад")
• Названия инструментов/технологий
• Сравнения "до/после"
• Личный опыт от первого лица

ЗАПРЕЩЕНО:
• Вводные фразы "честно говоря", "по опыту"
• Водянистые обобщения
• Символы ** или __
• Заголовки типа "Заголовок:" или "Тема:"

СТИЛЬ: дерзко, уверенно, без воды, сразу к результату. Пиши как успешный эксперт, который делится конкретными достижениями.

Тема для поста: {theme}
Описание поста:  {post_description}

Сгенерируй готовый пост строго по структуре БЕЗ пояснений."""
    
    # Экранируем пример промпта для безопасного отображения
    escaped_example = escape_html(example_prompt)
    
    await cb.message.answer(
        f"💡 <b>Пример хорошего промпта для генерации текста:</b>\n\n<code>{escaped_example}</code>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:set_content_prompt")]]
        ),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await cb.answer()

@router.callback_query(F.data == "prompt:example_image")
async def cb_example_image_prompt(cb: CallbackQuery):
    """Показать пример хорошего промпта для изображений"""
    example_prompt = """You are an AI prompt generator for Flux.1 image generation model. Your task is to create a detailed English prompt based on the provided text content.

Analyze the post text and create a concise but detailed prompt (max 100 words) that captures:
- Main subject/theme from the post
- Professional, modern tech environment
- Appropriate mood and atmosphere
- Relevant objects and setting
- High-quality photography style

Style requirements:
- Photorealistic, professional photography
- Modern tech workspace aesthetic
- Clean, minimalist composition
- Soft, natural lighting
- Focus on technology and innovation themes

Post content to analyze: {post_text}

Generate only the English prompt for image generation, no explanations."""
    
    await cb.message.answer(
        f"🖼️ <b>Пример хорошего промпта для генерации изображений:</b>\n\n<code>{example_prompt}</code>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:set_image_prompt")]]
        ),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await cb.answer()

@router.callback_query(F.data == "prompt:cancel")
async def cb_prompt_cancel(cb: CallbackQuery, state: FSMContext):
    """Отмена настройки промпта"""
    await state.clear()
    await cb.answer("Настройка отменена")
    
    # Возвращаемся в главное меню
    from handlers.menu import build_main_menu_keyboard
    await cb.message.edit_text(
        "🎯 <b>Главное меню бота</b>\n\nВыберите нужное действие:",
        reply_markup=build_main_menu_keyboard(),
        disable_web_page_preview=True,
        parse_mode="HTML"
    ) 

@router.callback_query(F.data == "menu:content_prompts")
async def cb_content_prompts_menu(cb: CallbackQuery):
    """Меню выбора типа промпта для настройки"""
    
    menu_text = """⚙️ <b>НАСТРОЙКА ПРОМПТОВ</b>

Выберите тип промпта, который хотите настроить:

📝 <b>Промпт для текста</b> - инструкции для ИИ по созданию контента постов
🖼️ <b>Промпт для изображений</b> - описание стиля генерируемых изображений

💡 <b>Совет:</b> Начните с настройки промпта для текста - это основа качественных постов!"""

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Промпт для текста", callback_data="menu:set_content_prompt")
            ],
            [
                InlineKeyboardButton(text="🖼️ Промпт для изображений", callback_data="menu:set_image_prompt")
            ],
            [
                InlineKeyboardButton(text="📚 Полный гайд по настройке", callback_data="prompts:help_guide")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")
            ]
        ]
    )
    
    await cb.message.edit_text(
        menu_text, 
        reply_markup=kb, 
        disable_web_page_preview=True,
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data == "prompts:help_guide")
async def cb_prompts_help_guide(cb: CallbackQuery):
    """Подробное руководство по составлению промптов и примеров"""
    
    guide_text = """📚 <b>ПОЛНОЕ РУКОВОДСТВО ПО НАСТРОЙКЕ БОТА</b>

🎯 <b>НОВАЯ ПРОСТАЯ СИСТЕМА:</b>

<b>Всё теперь настраивается в одном месте - "📝 Промпт текста"!</b>

• <b>Кастомный промпт</b> → используется как есть
• <b>Нет промпта</b> → используется наша дефолтная система с примерами
• <b>Никаких отдельных файлов!</b> Включайте примеры прямо в промпт

---

📝 <b>КАК СОСТАВИТЬ КАСТОМНЫЙ ПРОМПТ:</b>

<b>✅ ОБЯЗАТЕЛЬНО УКАЖИТЕ:</b>
• <b>Роль ИИ:</b> "Ты эксперт по...", "Ты блогер..."
• <b>Стиль:</b> деловой/дружеский/экспертный
• <b>Структуру:</b> сколько абзацев, с эмодзи или без
• <b>Длину:</b> 200-500 слов / короткие посты до 280 символов
• <b>Призыв к действию:</b> полную ссылку на ваш канал
• <b>Примеры постов:</b> включите 2-3 лучших поста как образцы

<b>📋 ПРИМЕР КАСТОМНОГО ПРОМПТА:</b>
<code>Ты блогер-маркетолог. Пиши короткие посты до 200 слов для бизнес-аудитории. 

Структура:
1. Заголовок с конкретной цифрой
2. 2-3 абзаца с фактами 
3. Призыв: "Больше инсайтов в моем канале https://t.me/+abc123"

Стиль: профессиональный, без эмодзи, только факты.

ПРИМЕРЫ СТИЛЯ:

Пример 1:
Увеличил конверсию лендинга на 67% за неделю

Заменил длинную форму на одно поле "email". Убрал все лишние кнопки. Добавил социальные доказательства.

Результат: конверсия выросла с 2.3% до 3.8%. За неделю получили на 45 лидов больше.

Все кейсы в канале: https://t.me/+abc123

Пример 2:
A/B тест показал: красная кнопка работает на 23% лучше

Тестировал 5 цветов кнопки CTA. Красный обошел синий, зеленый и оранжевый.

Статистически значимый результат через 2000 посетителей.

Больше тестов: https://t.me/+abc123</code>

---

🔗 <b>ПРО ССЫЛКИ НА КАНАЛ:</b>

<b>✅ ПРАВИЛЬНО:</b>
• <code>https://t.me/+abc123</code>
• <code>https://t.me/your_channel</code>
• <code>t.me/+abc123</code>

<b>❌ НЕПРАВИЛЬНО:</b>
• <code>@your_channel</code> (не работает в VK)
• <code>telegram.me/channel</code> (устаревший формат)

<b>💡 ЛАЙФХАК:</b> Полная ссылка работает везде - и в Telegram, и в VK!

---

🎯 <b>РЕКОМЕНДАЦИИ ПО СТРАТЕГИИ:</b>

<b>🔰 Новичкам:</b> 
Не настраивайте ничего! Наша система уже оптимизирована с встроенными примерами.

<b>⚙️ Опытным:</b>
1. Сначала протестируйте дефолтную систему
2. Затем создайте кастомный промпт с 2-3 своими лучшими постами как примеры
3. Укажите свой стиль и структуру

<b>🚀 Профи:</b>
Создайте детальный промпт с примерами, инструкциями по стилю и структуре для полного контроля.

---

❓ <b>ЧАСТЫЕ ВОПРОСЫ:</b>

<b>В:</b> Где загрузить примеры стилей?
<b>О:</b> Никуда! Включайте примеры прямо в текст промпта.

<b>В:</b> Как добавить свой стиль?
<b>О:</b> Добавьте 2-3 своих лучших поста в конец промпта как "ПРИМЕРЫ СТИЛЯ:"

<b>В:</b> Что если не настрою промпт?
<b>О:</b> Будет работать наша дефолтная система с качественными примерами.

<b>В:</b> Как вернуть дефолтные настройки?
<b>О:</b> Просто удалите кастомный промпт - система вернется к дефолтным настройкам.

---

💡 <b>ИСПОЛЬЗОВАНИЕ ДАННЫХ ИЗ КОНТЕНТ-ПЛАНА:</b>

Бот автоматически подставляет в ваш промпт данные из контент-плана:

• <b>{theme}</b> - тема поста из контент-плана
• <b>{post_description}</b> - описание поста из контент-плана  
• <b>{category}</b> - категория поста из контент-плана

<b>📋 ПРИМЕР ПРОМПТА С КОНТЕНТ-ПЛАНОМ:</b>
<code>Напиши пост на тему: {theme}

Используй это описание как основу: {post_description}

Категория контента: {category}

Сделай пост экспертным и интересным...</code>

---

🚀 <b>ИТОГО: ПРОСТАЯ ФОРМУЛА УСПЕХА</b>

1. <b>Основа:</b> "Ты [роль]. Пиши [стиль] посты для [аудитория]"
2. <b>Тема:</b> "Пост на тему: {theme}" или "Описание: {post_description}"
3. <b>Структура:</b> Опишите желаемую структуру постов
4. <b>CTA:</b> "Призыв с ссылкой https://t.me/+ваш_канал"
5. <b>Примеры:</b> Добавьте 2-3 лучших поста как образцы
6. <b>Готово!</b> ИИ будет генерировать в вашем стиле"""

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Настроить промпт", callback_data="menu:content_prompts")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")
            ]
        ]
    )
    
    await cb.message.edit_text(
        guide_text, 
        reply_markup=kb, 
        disable_web_page_preview=True,
        parse_mode="HTML"
    )
    await cb.answer() 