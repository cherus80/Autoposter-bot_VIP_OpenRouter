"""
@file: handlers/menu.py
@description: Обработчики главного меню и навигации с улучшенным UX
@dependencies: config.py, handlers/admin_handlers.AdminCheckMiddleware
@created: 2025-01-20
@updated: 2025-01-20 - Улучшение UX интерфейса
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)
router = Router()

def build_main_menu_keyboard():
    """Создает клавиатуру главного меню с улучшенной группировкой и UX"""
    builder = InlineKeyboardBuilder()

    # 🎯 ОСНОВНЫЕ ДЕЙСТВИЯ (1-2 строки)
    builder.button(text="✍️ Создать пост", callback_data="menu:generate_post")
    builder.button(text="🤖 Автопостинг", callback_data="menu:auto_mode")
    builder.adjust(1, 1)  # Каждая кнопка на отдельной строке для акцента

    # 📊 УПРАВЛЕНИЕ И АНАЛИТИКА (3 строка)
    builder.button(text="📊 Статистика", callback_data="menu:stats")
    builder.button(text="📅 Контент-план", callback_data="content:show")
    builder.adjust(2)

    # ⚙️ НАСТРОЙКИ (4-5 строки)
    builder.button(text="📝 Промпт текста", callback_data="menu:set_content_prompt")
    builder.button(text="🖼️ Промпт изображений", callback_data="menu:set_image_prompt")
    builder.adjust(2)
    
    builder.button(text="📤 Настройки публикации", callback_data="menu:publishing_settings")
    builder.adjust(1)

    # 📋 КОНТЕНТ (6 строка)
    builder.button(text="📂 Загрузить план", callback_data="menu:upload_content_plan")
    builder.adjust(1)

    # 💾 СИСТЕМНЫЕ ФУНКЦИИ (7 строка)
    builder.button(text="💾 Управление резервным копированием", callback_data="backup:main")
    builder.adjust(1)

    # ❓ ПОМОЩЬ (8 строка)
    builder.button(text="❓ Справка", callback_data="menu:help")
    builder.adjust(1)

    return builder.as_markup()

def build_breadcrumb_keyboard(current_page: str, parent_callback: str = "back_to_menu"):
    """Создает клавиатуру с breadcrumbs для навигации"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data=parent_callback)
        ]]
    )

@router.message(Command("menu"))
async def cmd_menu(msg: Message):
    """Команда /menu с улучшенным описанием"""
    logger.info(f"Команда /menu от пользователя {msg.from_user.id}")
    await msg.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "🎯 Выберите нужное действие из категорий ниже:",
        reply_markup=build_main_menu_keyboard()
    )

@router.message(Command("start"))
async def cmd_start(msg: Message):
    """Команда /start - приветствие и главное меню"""
    logger.info(f"Команда /start от пользователя {msg.from_user.id}")
    await msg.answer(
        "🤖 <b>Добро пожаловать в Autoposter Bot!</b>\n\n"
        "🎯 Этот бот поможет вам автоматизировать публикацию контента в Telegram и VK.\n\n"
        "✨ <b>Основные возможности:</b>\n"
        "• Генерация постов с помощью ИИ\n"
        "• Автоматическая публикация по расписанию\n"
        "• Создание изображений\n"
        "• Управление контент-планом\n\n"
        "🚀 Выберите действие из меню ниже:",
        reply_markup=build_main_menu_keyboard()
    )

@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(cb: CallbackQuery, state: FSMContext):
    """Возврат в главное меню с breadcrumbs"""
    # Очищаем любое состояние FSM при возврате в главное меню
    await state.clear()
    
    await cb.message.edit_text(
        "🏠 <b>Главное меню</b>\n\n"
        "🎯 Выберите нужное действие из категорий ниже:",
        reply_markup=build_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await cb.answer()

@router.callback_query(F.data == "menu:help")
async def cb_menu_help(cb: CallbackQuery):
    """Обработчик кнопки 'Справка' с улучшенным контентом"""
    logger.info(f"Callback menu:help от пользователя {cb.from_user.id}")
    
    help_text = """❓ <b>Справка по Autoposter Bot v2.0</b>

🎯 <b>Главное меню и функции:</b>

📝 <b>СОЗДАНИЕ ПОСТОВ</b>
• <b>✍️ Создать пост</b> - Ручное создание с выбором типа:
  → Пост с картинкой (текст + изображение)  
  → Только текст (без изображения)
• <b>Стили изображений:</b> 📷 Фото, 🎨 Digital Art, 🌸 Аниме, 🤖 Киберпанк, 🧙‍♂️ Фэнтези

🤖 <b>АВТОПОСТИНГ</b>
• <b>Включение/выключение</b> автоматической публикации
• <b>Настройка интервалов (в часах):</b> 1, 4, 12, 24, 72 часа
• <b>Настройка интервалов (в минутах):</b> 5, 15, 30, 60, 120, 240 минут
• <b>Диапазон интервалов:</b> от 1 минуты до 168 часов (7 дней)
• <b>Настройки изображений:</b> включение/отключение и выбор стиля для автопостов

📊 <b>СТАТИСТИКА И УПРАВЛЕНИЕ</b>
• <b>📊 Статистика</b> - количество постов, время последнего поста, статус автопостинга
• <b>📅 Контент-план</b> - просмотр списка тем, фильтрация (все/неиспользованные/использованные)
• <b>Управление контент-планом:</b> просмотр, очистка, восстановление тем

⚙️ <b>НАСТРОЙКИ</b>
• <b>📝 Промпт текста</b> - инструкции для ИИ по созданию контента (включая примеры стилей)
• <b>🖼️ Промпт изображений</b> - описание стиля генерируемых изображений  
• <b>📤 Настройки публикации</b> - включение/отключение Telegram/VK, часовой пояс
• <b>📂 Загрузить план</b> - контент-план в JSON/CSV формате

💾 <b>РЕЗЕРВНОЕ КОПИРОВАНИЕ</b>
• <b>Создание бэкапов:</b> ручное создание резервных копий
• <b>Управление:</b> просмотр списка, загрузка, удаление бэкапов
• <b>Восстановление:</b> восстановление из выбранного бэкапа
• <b>Планировщик:</b> настройка автоматических бэкапов
• <b>Экспорт проекта:</b> полный экспорт для переноса

━━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 <b>ПОШАГОВАЯ НАСТРОЙКА:</b>

<b>1️⃣ Настройка публикации:</b>
• Нажмите "📤 Настройки публикации"
• Включите "📱 Telegram" и/или "🔵 VK"
• Установите свой часовой пояс (например: +7)
• Настройте часовой пояс в настройках публикации

<b>2️⃣ Настройка ИИ:</b>
• "📝 Промпт текста" - опишите желаемый стиль постов и добавьте примеры постов прямо в промпт
• "🖼️ Промпт изображений" - опишите стиль изображений (если нужны)

<b>3️⃣ Создание контента:</b>
• "✍️ Создать пост" → выберите тип (с картинкой/только текст)
• Введите тему поста
• Выберите стиль изображения (если выбрали "с картинкой")
• Проверьте результат и опубликуйте

<b>4️⃣ Автопостинг:</b>
• "📂 Загрузить план" - загрузите JSON/CSV файл с темами
• "🤖 Автопостинг" → включите автопостинг
• Настройте интервал: выберите единицу (часы/минуты) и значение
• При необходимости настройте изображения для автопостов

━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 <b>ФОРМАТЫ ФАЙЛОВ:</b>

<b>Контент-план (JSON):</b>
<code>[
  {"category": "ai_tools", "theme": "Тема поста", "post_description": "Описание"},
  {"category": "news", "theme": "Новости ИИ", "post_description": "Описание"}
]</code>

<b>Примеры стилей (в промпте):</b>
Теперь примеры стилей добавляются прямо в "📝 Промпт текста". Включите в промпт 2-3 лучших поста как образцы для ИИ.

💡 <b>ПОЛЕЗНЫЕ СОВЕТЫ:</b>

• <b>Качественные промпты с примерами</b> - основа хороших постов
• <b>Включите примеры в промпт</b> - ИИ лучше поймет ваш стиль  
• <b>Проверяйте статистику</b> - отслеживайте работу бота
• <b>Настройте резервное копирование</b> - защитите данные
• <b>ИИ на базе OpenRouter</b> - доступ к множеству моделей ИИ

🆘 <b>КОМАНДЫ БОТА:</b>
• <code>/start</code> - запуск и главное меню
• <code>/menu</code> - быстрый доступ к меню

⚠️ <b>ВАЖНО:</b> Все функции доступны только через инлайн-кнопки!"""

    breadcrumb_kb = build_breadcrumb_keyboard("help")
    
    await cb.message.edit_text(help_text, reply_markup=breadcrumb_kb)
    await cb.answer()

 