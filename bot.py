"""bot.py — точка входа Telegram‑бота автопостера
=================================================
Совместимо с aiogram 3.7 (Python 3.12).

Основное:
* Устанавливает slash‑меню.
* Выводит приветствие с inline‑клавиатурой.
* Запускает планировщик (`PostScheduler`).
* Подключает админ‑роутеры + middleware проверки ADMIN_ID.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import List

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram_sqlite_storage.sqlitestore import SQLStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    InlineKeyboardMarkup,
    MenuButtonCommands,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import text

from config import BOT_TOKEN, ADMIN_IDS
from database.database import init_db, async_session_maker
from handlers import admin_handlers
from handlers import menu, stats, auto_mode, generate_post, settings, prompts, content_plan, backup
from services.scheduler import PostScheduler
from services.backup_scheduler import backup_scheduler
from utils.error_handler import init_error_handler, ErrorSeverity, error_handler

# ---------------------------------------------------------------------------
# Логирование с улучшенным форматированием и записью в файл
# ---------------------------------------------------------------------------
import logging.handlers

# Создаем корневой логгер
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Очищаем существующие обработчики
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Создаем форматтер
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 1. Консольный обработчик (для отладки)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

# 2. Файловый обработчик с ротацией (основные логи)
file_handler = logging.handlers.RotatingFileHandler(
    'bot.log',
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5,          # Хранить 5 старых файлов
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

# 3. Отдельный файл для ошибок
error_handler = logging.handlers.RotatingFileHandler(
    'bot_errors.log',
    maxBytes=5*1024*1024,   # 5 MB
    backupCount=3,          # Хранить 3 старых файла
    encoding='utf-8'
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)
root_logger.addHandler(error_handler)

# Настраиваем логи для всех ключевых модулей
logger = logging.getLogger(__name__)
logging.getLogger('services.ai_service').setLevel(logging.INFO)
logging.getLogger('services.openrouter_service').setLevel(logging.INFO)
logging.getLogger('services.scheduler').setLevel(logging.INFO)
logging.getLogger('services.image_service').setLevel(logging.INFO)
logging.getLogger('handlers').setLevel(logging.INFO)
logging.getLogger('managers').setLevel(logging.INFO)

# Уменьшаем шум от aiogram и httpx
logging.getLogger('aiogram').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

logger.info("🚀 Система логирования инициализирована: консоль + файлы (bot.log, bot_errors.log)")

# ---------------------------------------------------------------------------
# Bot / Dispatcher
# ---------------------------------------------------------------------------
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

# Настройка персистентного хранилища FSM
# В Docker используем директорию /app/database, локально - корень проекта
if os.path.exists('/app/database'):
    storage_path = '/app/database/fsm_storage.db'
else:
    storage_path = 'fsm_storage.db'
storage = SQLStorage(storage_path, serializing_method="pickle")
dp = Dispatcher(storage=storage)

# Глобальный планировщик (инициализируется в main)
scheduler: PostScheduler | None = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_inline_main_menu() -> InlineKeyboardMarkup:
    """Клавиатура главного меню с улучшенной группировкой и UX"""
    builder = InlineKeyboardBuilder()

    # 🎯 ОСНОВНЫЕ ДЕЙСТВИЯ (1-2 строки)
    builder.button(text="✍️ Создать пост", callback_data="menu:generate_post")
    builder.button(text="🤖 Автопостинг", callback_data="menu:auto_mode")
    builder.adjust(1, 1)  # Каждая кнопка на отдельной строке для акцента

    # 📊 УПРАВЛЕНИЕ (3 строка)
    builder.button(text="📊 Статистика", callback_data="menu:stats")
    builder.adjust(1)
    
    builder.button(text="📅 Контент-план", callback_data="content:show")
    builder.adjust(1)

    # ⚙️ НАСТРОЙКИ (4-5 строки)
    builder.button(text="📝 Промпт текста", callback_data="menu:set_content_prompt")
    builder.button(text="🖼️ Промпт изображений", callback_data="menu:set_image_prompt")
    builder.adjust(2)
    
    builder.button(text="📤 Настройки публикации", callback_data="menu:publishing_settings")
    builder.adjust(1)

    # 📋 КОНТЕНТ (6 строка)
    builder.button(text="📂 Загрузить план", callback_data="menu:upload_content_plan")
    builder.adjust(1)

    # 💾 РЕЗЕРВНОЕ КОПИРОВАНИЕ (7 строка)
    builder.button(text="💾 Резервное копирование", callback_data="backup:main")
    builder.adjust(1)

    # ❓ ПОМОЩЬ (8 строка)
    builder.button(text="❓ Справка", callback_data="menu:help")
    builder.adjust(1)

    return builder.as_markup()


async def set_main_menu(bot: Bot) -> None:
    """Создаёт глобальное slash‑меню и кнопку «Меню» в UI Telegram."""
    logger.info("Начинаю установку главного меню…")
    main_menu_commands: List[BotCommand] = [
        BotCommand(command="start", description="🔄 Перезапустить бота"),
        BotCommand(command="menu", description="▶️ Главное интерактивное меню"),
    ]
    await bot.set_my_commands(main_menu_commands, scope=BotCommandScopeAllPrivateChats())
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("Главное меню и кнопка успешно установлены.")


async def run_migration() -> None:
    """Добавляет колонки, если их ещё нет."""
    async with async_session_maker() as session:
        async with session.begin():
            # Миграция для таблицы posts
            res = await session.execute(text("PRAGMA table_info(posts);"))
            cols = [row[1] for row in res.fetchall()]
            
            if "with_image" not in cols:
                logger.info("Добавляю колонку 'with_image' в posts…")
                await session.execute(
                    text("ALTER TABLE posts ADD COLUMN with_image BOOLEAN DEFAULT FALSE;")
                )
                logger.info("Колонка 'with_image' добавлена в posts.")
            else:
                logger.info("Колонка 'with_image' уже есть в posts.")
            
            # Добавляем колонки для ID постов в соцсетях
            if "telegram_message_id" not in cols:
                logger.info("Добавляю колонку 'telegram_message_id' в posts…")
                await session.execute(
                    text("ALTER TABLE posts ADD COLUMN telegram_message_id TEXT;")
                )
                logger.info("Колонка 'telegram_message_id' добавлена в posts.")
            else:
                logger.info("Колонка 'telegram_message_id' уже есть в posts.")
            
            if "vk_post_id" not in cols:
                logger.info("Добавляю колонку 'vk_post_id' в posts…")
                await session.execute(
                    text("ALTER TABLE posts ADD COLUMN vk_post_id TEXT;")
                )
                logger.info("Колонка 'vk_post_id' добавлена в posts.")
            else:
                logger.info("Колонка 'vk_post_id' уже есть в posts.")
            
            # Миграция для таблицы content_plan
            try:
                res = await session.execute(text("PRAGMA table_info(content_plan);"))
                content_cols = [row[1] for row in res.fetchall()]
                if "with_image" not in content_cols:
                    logger.info("Добавляю колонку 'with_image' в content_plan…")
                    await session.execute(
                        text("ALTER TABLE content_plan ADD COLUMN with_image BOOLEAN DEFAULT TRUE;")
                    )
                    logger.info("Колонка 'with_image' добавлена в content_plan.")
                else:
                    logger.info("Колонка 'with_image' уже есть в content_plan.")
            except Exception:
                # Таблица content_plan может еще не существовать
                logger.info("Таблица content_plan еще не создана.")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


@dp.message(Command("start"))
async def start_command(message: Message):
    logger.info(f"Команда /start от пользователя {message.from_user.id} (@{message.from_user.username})")
    if message.from_user.id in ADMIN_IDS:
        logger.info(f"✅ Доступ разрешен для администратора {message.from_user.id}")
        await message.answer(
            "🤖 <b>Добро пожаловать в Autoposter Bot!</b>\n\n"
            "📱 <b>Основные возможности:</b>\n"
            "• Генерация постов с помощью ИИ\n"
            "• Автоматическая публикация по расписанию\n"
            "• Создание изображений для постов\n"
            "• Работа с контент-планом\n\n"
            "🎯 <b>Выберите действие:</b>",
            reply_markup=build_inline_main_menu(),
        )
    else:
        logger.warning(f"❌ Отказ в доступе для пользователя {message.from_user.id} (@{message.from_user.username})")
        await message.answer(
            "❌ <b>Доступ запрещен</b>\n\n"
            "У вас нет прав для использования этого бота.\n"
            "Обратитесь к администратору для получения доступа."
        )

@dp.message(Command("menu"))
async def menu_command(message: Message):
    """Команда /menu - главное меню"""
    logger.info(f"Команда /menu от пользователя {message.from_user.id} (@{message.from_user.username})")
    if message.from_user.id in ADMIN_IDS:
        logger.info(f"✅ Показываю главное меню для администратора {message.from_user.id}")
        await message.answer(
            "🎯 <b>Главное меню Autoposter Bot</b>\n\n"
            "Выберите нужное действие из меню ниже:",
            reply_markup=build_inline_main_menu(),
        )
    else:
        logger.warning(f"❌ Отказ в доступе к меню для пользователя {message.from_user.id}")
        await message.answer("❌ Доступ запрещен")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    logger.info("🚀 Запуск Autoposter Bot...")
    
    # 1. Init DB & migrations
    logger.info("📊 Инициализация базы данных...")
    await init_db()
    logger.info("✅ База данных инициализирована.")
    
    logger.info("🔄 Запуск миграций базы данных...")
    await run_migration()
    logger.info("✅ Миграции завершены.")

    # 2. Инициализация обработчика ошибок
    logger.info("🛡️ Инициализация системы обработки ошибок...")
    init_error_handler(bot)
    logger.info("✅ Система обработки ошибок инициализирована.")

    # 3. Slash‑menu
    logger.info("📋 Настройка меню бота...")
    await set_main_menu(bot)
    logger.info("✅ Меню бота настроено.")

    # 4. Scheduler
    logger.info("⏰ Запуск планировщика автопостинга...")
    global scheduler
    scheduler = PostScheduler(bot)
    asyncio.create_task(scheduler.start())
    logger.info("✅ Планировщик автопостинга запущен.")

    # 4.1 Backup Scheduler
    logger.info("💾 Запуск планировщика резервного копирования...")
    backup_scheduler.bot = bot
    asyncio.create_task(backup_scheduler.start())
    logger.info("✅ Планировщик резервного копирования запущен.")

    # 5. Dispatcher context
    dp["scheduler"] = scheduler

    # 5. Routers / middleware - ИСПРАВЛЕНО
    logger.info("🔧 Подключение middleware и роутеров...")
    # Сначала подключаем middleware
    dp.message.middleware(admin_handlers.AdminCheckMiddleware())
    dp.callback_query.middleware(admin_handlers.AdminCheckMiddleware())
    
    # Затем подключаем роутеры
    routers = [
        ("menu", menu.router),
        ("stats", stats.router), 
        ("auto_mode", auto_mode.router),
        ("generate_post", generate_post.router),
        ("settings", settings.router),
        ("prompts", prompts.router),
        ("content_plan", content_plan.router),
        ("backup", backup.router)
    ]
    
    for name, router in routers:
        dp.include_router(router)
        logger.info(f"  ✅ Роутер {name} подключен")

    # 6. Polling
    logger.info("🌐 Удаление webhook и запуск polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🎯 БОТ ГОТОВ К РАБОТЕ! Начинаю прием сообщений...")
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except KeyboardInterrupt:
        logger.info("⏹️ Получен сигнал остановки...")
    finally:
        logger.info("🔄 Закрытие соединений...")
        await bot.session.close()
        logger.info("✅ Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())