"""
@file: handlers/backup.py
@description: Обработчики команд для управления резервным копированием
@dependencies: aiogram, backup_service, backup_scheduler
@created: 2025-01-21
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.backup_service import backup_service, create_backup, restore_backup, get_backups, create_project_export
from services.backup_scheduler import backup_scheduler
from utils.error_handler import error_handler, ErrorSeverity

logger = logging.getLogger(__name__)
router = Router()


class BackupStates(StatesGroup):
    """Состояния FSM для настройки резервного копирования"""
    waiting_for_interval = State()
    waiting_for_max_backups = State()
    waiting_for_backup_file = State()


def build_backup_main_menu() -> InlineKeyboardMarkup:
    """Главное меню резервного копирования"""
    builder = InlineKeyboardBuilder()
    
    # Основные действия
    builder.button(text="📊 Статус бэкапов", callback_data="backup:status")
    builder.button(text="💾 Создать бэкап", callback_data="backup:create")
    builder.adjust(2)
    
    builder.button(text="📋 Список бэкапов", callback_data="backup:list")
    builder.button(text="🔄 Восстановить", callback_data="backup:restore_menu")
    builder.adjust(2)
    
    # Экспорт проекта  
    builder.button(text="📦 Экспорт проекта", callback_data="backup:export_project")
    builder.adjust(1)
    
    # Настройки
    builder.button(text="⚙️ Настройки", callback_data="backup:settings")
    builder.adjust(1)
    
    # Назад
    builder.button(text="◀️ Назад в меню", callback_data="back_to_menu")
    builder.adjust(1)
    
    return builder.as_markup()


def build_backup_settings_menu() -> InlineKeyboardMarkup:
    """Меню настроек резервного копирования"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🔄 Включить/Выключить", callback_data="backup_settings:toggle_enabled")
    builder.button(text="⏰ Интервал", callback_data="backup_settings:set_interval")
    builder.adjust(2)
    
    builder.button(text="📦 Макс. бэкапов", callback_data="backup_settings:set_max_backups")
    builder.button(text="📧 Уведомления", callback_data="backup_settings:toggle_notifications")
    builder.adjust(2)
    
    builder.button(text="🗜️ Сжатие", callback_data="backup_settings:toggle_compression")
    builder.button(text="📄 Настройки", callback_data="backup_settings:toggle_settings_backup")
    builder.adjust(2)
    
    builder.button(text="💾 База данных", callback_data="backup_settings:toggle_db_backup")
    builder.adjust(1)
    
    builder.button(text="◀️ Назад", callback_data="backup:main")
    builder.adjust(1)
    
    return builder.as_markup()


async def build_backup_list_menu(backups: list, page: int = 0, page_size: int = 5) -> InlineKeyboardMarkup:
    """Меню списка резервных копий с пагинацией"""
    builder = InlineKeyboardBuilder()
    
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(backups))
    
    # Добавляем кнопки бэкапов
    for i in range(start_idx, end_idx):
        backup = backups[i]
        created = await format_time_with_timezone(backup["created"])
        created_short = created[0:5] + " " + created[11:16]  # DD.MM HH:MM
        size = format_file_size(backup["size"])
        text = f"{created_short} | {backup['type']} | {size}"
        builder.button(text=text, callback_data=f"backup:detail:{i}")
        builder.adjust(1)
    
    # Пагинация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(("◀️ Пред", f"backup:list:{page-1}"))
    if end_idx < len(backups):
        nav_buttons.append(("След ▶️", f"backup:list:{page+1}"))
    
    if nav_buttons:
        for text, callback in nav_buttons:
            builder.button(text=text, callback_data=callback)
        builder.adjust(len(nav_buttons))
    
    # Назад
    builder.button(text="◀️ Назад", callback_data="backup:main")
    builder.adjust(1)
    
    return builder.as_markup()


def build_backup_detail_menu(backup_idx: int) -> InlineKeyboardMarkup:
    """Меню деталей резервной копии"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🔄 Восстановить", callback_data=f"backup:restore:{backup_idx}")
    builder.button(text="📥 Скачать", callback_data=f"backup:download:{backup_idx}")
    builder.adjust(2)
    
    builder.button(text="🗑️ Удалить", callback_data=f"backup:delete:{backup_idx}")
    builder.adjust(1)
    
    builder.button(text="◀️ К списку", callback_data="backup:list")
    builder.adjust(1)
    
    return builder.as_markup()


def format_file_size(size_bytes: int) -> str:
    """Форматировать размер файла"""
    for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} ТБ"


async def format_time_with_timezone(dt: datetime) -> str:
    """Форматировать время с учетом часового пояса пользователя"""
    try:
        from database.settings_db import get_setting
        
        # Получаем часовой пояс пользователя
        user_timezone = await get_setting("user_timezone", "+3")
        
        # Парсим часовой пояс
        if user_timezone.startswith('+'):
            tz_offset = int(user_timezone[1:])
        elif user_timezone.startswith('-'):
            tz_offset = -int(user_timezone[1:])
        else:
            tz_offset = 3  # По умолчанию +3
        
        # Применяем смещение часового пояса
        adjusted_time = dt + timedelta(hours=tz_offset)
        
        return adjusted_time.strftime("%d.%m.%Y %H:%M:%S")
        
    except Exception as e:
        logger.error(f"Ошибка форматирования времени: {e}")
        return dt.strftime("%d.%m.%Y %H:%M:%S")


@router.callback_query(F.data == "backup:main")
async def backup_main_menu(callback: CallbackQuery):
    """Показать главное меню резервного копирования"""
    await callback.answer()  # Отвечаем сразу, чтобы избежать повторных нажатий
    await callback.message.edit_text(
        "💾 <b>Управление резервным копированием</b>\n\n"
        "Здесь вы можете настроить автоматическое резервное копирование, "
        "создавать ручные бэкапы и восстанавливать данные из существующих копий.",
        reply_markup=build_backup_main_menu()
    )


@router.callback_query(F.data == "backup:status")
async def backup_status(callback: CallbackQuery):
    """Показать статус системы резервного копирования"""
    try:
        status = await backup_scheduler.get_backup_status()
        
        # Добавляем метку времени обновления для уникальности
        current_time = await format_time_with_timezone(datetime.now())
        
        if "error" in status:
            text = (
                f"❌ <b>Ошибка получения статуса</b>\n\n{status['error']}\n\n"
                f"🔄 <i>Обновлено: {current_time}</i>"
            )
        else:
            # Формируем статусное сообщение
            enabled_emoji = "✅" if status.get("backup_enabled", False) else "❌"
            scheduler_emoji = "🟢" if status.get("scheduler_running", False) else "🔴"
            
            text = (
                f"📊 <b>Статус резервного копирования</b>\n\n"
                f"{enabled_emoji} <b>Статус:</b> {'Включено' if status.get('backup_enabled') else 'Отключено'}\n"
                f"{scheduler_emoji} <b>Планировщик:</b> {'Работает' if status.get('scheduler_running') else 'Остановлен'}\n"
                f"⏰ <b>Интервал:</b> {status.get('backup_interval_hours', 'Н/Д')} часов\n"
                f"📦 <b>Макс. бэкапов:</b> {status.get('max_backups', 'Н/Д')}\n"
                f"💾 <b>Всего бэкапов:</b> {status.get('total_backups', 0)}\n"
            )
            
            # Последний бэкап
            last_backup = status.get("last_backup")
            if last_backup:
                time_str = await format_time_with_timezone(last_backup["created"])
                text += f"📅 <b>Последний бэкап:</b> {time_str}\n"
                text += f"📁 <b>Тип:</b> {last_backup['type']}\n"
                text += f"💾 <b>Размер:</b> {format_file_size(last_backup['size'])}\n"
            else:
                text += "📅 <b>Последний бэкап:</b> Не найден\n"
            
            # Следующий бэкап
            next_backup = status.get("next_backup_in_hours")
            if next_backup is not None:
                if next_backup == 0:
                    text += "⏳ <b>Следующий бэкап:</b> Сейчас\n"
                else:
                    text += f"⏳ <b>Следующий бэкап:</b> через {next_backup} ч.\n"
            
            # Добавляем метку времени обновления
            text += f"\n🔄 <i>Обновлено: {current_time}</i>"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Обновить", callback_data="backup:status")
        builder.button(text="◀️ Назад", callback_data="backup:main")
        builder.adjust(2)
        
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
        except Exception as edit_error:
            # Если сообщение не изменилось, просто игнорируем ошибку
            if "message is not modified" in str(edit_error):
                logger.debug("Сообщение не изменилось, пропускаем обновление")
            else:
                # Если другая ошибка, перебрасываем исключение
                raise edit_error
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса бэкапов: {e}")
        await callback.answer("❌ Ошибка получения статуса", show_alert=True)


@router.callback_query(F.data == "backup:create")
async def backup_create(callback: CallbackQuery):
    """Создать резервную копию"""
    try:
        await callback.message.edit_text(
            "⏳ <b>Создание резервной копии...</b>\n\n"
            "Пожалуйста, подождите. Это может занять несколько минут."
        )
        
        # Создаем резервную копию
        backup_path = await backup_scheduler.force_backup()
        
        if backup_path:
            backup_name = Path(backup_path).name
            size = format_file_size(Path(backup_path).stat().st_size)
            
            text = (
                "✅ <b>Резервная копия создана успешно!</b>\n\n"
                f"📁 <b>Файл:</b> <code>{backup_name}</code>\n"
                f"💾 <b>Размер:</b> {size}\n"
                f"🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            )
        else:
            text = (
                "❌ <b>Ошибка создания резервной копии!</b>\n\n"
                "Проверьте логи для получения подробной информации."
            )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="◀️ Назад в меню", callback_data="back_to_menu")
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка создания бэкапа: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка создания резервной копии!</b>\n\n"
            f"Детали: <code>{str(e)}</code>",
            reply_markup=InlineKeyboardBuilder().button(
                text="◀️ Назад", callback_data="backup:main"
            ).as_markup()
        )
        await callback.answer()


@router.callback_query(F.data.startswith("backup:list"))
async def backup_list(callback: CallbackQuery):
    """Показать список резервных копий"""
    try:
        # Парсим страницу из callback_data
        parts = callback.data.split(":")
        page = int(parts[2]) if len(parts) > 2 else 0
        
        backups = await get_backups()
        
        if not backups:
            text = (
                "📦 <b>Список резервных копий</b>\n\n"
                "❌ Резервные копии не найдены.\n"
                "Создайте первую резервную копию, используя кнопку 'Создать бэкап'."
            )
            builder = InlineKeyboardBuilder()
            builder.button(text="◀️ Назад", callback_data="backup:main")
            markup = builder.as_markup()
        else:
            total_size = sum(backup["size"] for backup in backups)
            text = (
                f"📦 <b>Список резервных копий</b>\n\n"
                f"💾 <b>Всего:</b> {len(backups)} файлов\n"
                f"📊 <b>Общий размер:</b> {format_file_size(total_size)}\n\n"
                f"<i>Выберите резервную копию для просмотра деталей:</i>"
            )
            markup = await build_backup_list_menu(backups, page)
        
        await callback.message.edit_text(text, reply_markup=markup)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка получения списка бэкапов: {e}")
        await callback.answer("❌ Ошибка получения списка", show_alert=True)


@router.callback_query(F.data.startswith("backup:detail:"))
async def backup_detail(callback: CallbackQuery):
    """Показать детали резервной копии"""
    try:
        backup_idx = int(callback.data.split(":")[2])
        backups = await get_backups()
        
        if backup_idx >= len(backups):
            await callback.answer("❌ Резервная копия не найдена", show_alert=True)
            return
        
        backup = backups[backup_idx]
        
        formatted_time = await format_time_with_timezone(backup['created'])
        text = (
            f"📋 <b>Детали резервной копии</b>\n\n"
            f"📁 <b>Имя файла:</b> <code>{backup['name']}</code>\n"
            f"📊 <b>Тип:</b> {backup['type']}\n"
            f"💾 <b>Размер:</b> {format_file_size(backup['size'])}\n"
            f"🕐 <b>Создан:</b> {formatted_time}\n"
            f"📂 <b>Путь:</b> <code>{backup['path']}</code>"
        )
        
        await callback.message.edit_text(
            text, 
            reply_markup=build_backup_detail_menu(backup_idx)
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка получения деталей бэкапа: {e}")
        await callback.answer("❌ Ошибка получения деталей", show_alert=True)


@router.callback_query(F.data.startswith("backup:download:"))
async def backup_download(callback: CallbackQuery):
    """Скачать резервную копию"""
    try:
        backup_idx = int(callback.data.split(":")[2])
        backups = await get_backups()
        
        if backup_idx >= len(backups):
            await callback.answer("❌ Резервная копия не найдена", show_alert=True)
            return
        
        backup = backups[backup_idx]
        backup_path = Path(backup["path"])
        
        if not backup_path.exists():
            await callback.answer("❌ Файл резервной копии не найден", show_alert=True)
            return
        
        # Проверяем размер файла (ограничение Telegram - 50MB)
        if backup["size"] > 50 * 1024 * 1024:
            await callback.answer(
                "❌ Файл слишком большой для отправки через Telegram (>50MB)", 
                show_alert=True
            )
            return
        
        await callback.message.edit_text("⏳ Подготовка файла для скачивания...")
        
        # Читаем файл и отправляем
        with open(backup_path, 'rb') as file:
            file_data = file.read()
        
        document = BufferedInputFile(file_data, filename=backup["name"])
        
        formatted_time = await format_time_with_timezone(backup['created'])
        await callback.message.answer_document(
            document,
            caption=f"📦 Резервная копия: {backup['name']}\n"
                   f"📊 Размер: {format_file_size(backup['size'])}\n"
                   f"🕐 Создана: {formatted_time}"
        )
        
        # Возвращаемся к деталям
        await backup_detail(callback)
        
    except Exception as e:
        logger.error(f"Ошибка скачивания бэкапа: {e}")
        await callback.answer("❌ Ошибка скачивания файла", show_alert=True)


@router.callback_query(F.data == "backup:restore_menu")
async def backup_restore_menu(callback: CallbackQuery):
    """Показать меню восстановления (список бэкапов для восстановления)"""
    try:
        await callback.answer()
        
        # Перенаправляем на список бэкапов с дополнительной информацией
        backups = await get_backups()
        
        if not backups:
            await callback.message.edit_text(
                "📋 <b>Восстановление данных</b>\n\n"
                "❌ Резервные копии не найдены.\n"
                "Создайте резервную копию перед восстановлением.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(text="💾 Создать бэкап", callback_data="backup:create"),
                        InlineKeyboardButton(text="◀️ Назад", callback_data="backup:main")
                    ]]
                )
            )
            return
        
        text = (
            "🔄 <b>Восстановление данных</b>\n\n"
            "Выберите резервную копию для восстановления:\n"
            "⚠️ <i>Текущие данные будут заменены!</i>\n\n"
            f"📦 Найдено резервных копий: {len(backups)}"
        )
        
        await callback.message.edit_text(text, reply_markup=await build_backup_list_menu(backups))
        
    except Exception as e:
        logger.error(f"Ошибка меню восстановления: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("backup:restore:"))
async def backup_restore_confirm(callback: CallbackQuery):
    """Подтверждение восстановления из резервной копии"""
    try:
        backup_idx = int(callback.data.split(":")[2])
        backups = await get_backups()
        
        if backup_idx >= len(backups):
            await callback.answer("❌ Резервная копия не найдена", show_alert=True)
            return
        
        backup = backups[backup_idx]
        
        formatted_time = await format_time_with_timezone(backup['created'])
        text = (
            "⚠️ <b>ВНИМАНИЕ! Восстановление данных</b>\n\n"
            f"Вы собираетесь восстановить данные из резервной копии:\n"
            f"📁 <b>Файл:</b> {backup['name']}\n"
            f"🕐 <b>Создан:</b> {formatted_time}\n\n"
            f"🚨 <b>Это действие заменит текущие данные!</b>\n"
            f"Текущая база данных будет сохранена как резервная копия.\n\n"
            f"Продолжить восстановление?"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Да, восстановить", callback_data=f"backup:restore_confirm:{backup_idx}")
        builder.button(text="❌ Отмена", callback_data=f"backup:detail:{backup_idx}")
        builder.adjust(2)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка подтверждения восстановления: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("backup:restore_confirm:"))
async def backup_restore_execute(callback: CallbackQuery):
    """Выполнить восстановление из резервной копии"""
    try:
        backup_idx = int(callback.data.split(":")[2])
        backups = await get_backups()
        
        if backup_idx >= len(backups):
            await callback.answer("❌ Резервная копия не найдена", show_alert=True)
            return
        
        backup = backups[backup_idx]
        
        await callback.message.edit_text(
            "⏳ <b>Восстановление данных...</b>\n\n"
            "Пожалуйста, подождите. Это может занять несколько минут.\n"
            "НЕ перезапускайте бота во время восстановления!"
        )
        
        # Выполняем восстановление
        success = await restore_backup(backup["path"])
        
        if success:
            current_time = await format_time_with_timezone(datetime.now())
            text = (
                "✅ <b>Восстановление завершено успешно!</b>\n\n"
                f"📁 Данные восстановлены из: {backup['name']}\n"
                f"🕐 Время восстановления: {current_time}\n\n"
                f"⚠️ <b>Рекомендуется перезапустить бота для применения всех изменений.</b>"
            )
        else:
            text = (
                "❌ <b>Ошибка восстановления!</b>\n\n"
                "Восстановление не удалось. Проверьте логи для получения подробной информации.\n"
                "Текущие данные остались без изменений."
            )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="◀️ К списку", callback_data="backup:list")
        builder.button(text="🏠 Главное меню", callback_data="menu:main")
        builder.adjust(2)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка восстановления: {e}")
        await callback.message.edit_text(
            f"❌ <b>Критическая ошибка восстановления!</b>\n\n"
            f"Детали: <code>{str(e)}</code>\n\n"
            f"Обратитесь к администратору.",
            reply_markup=InlineKeyboardBuilder().button(
                text="◀️ Назад", callback_data="backup:main"
            ).as_markup()
        )
        await callback.answer()


@router.callback_query(F.data.startswith("backup:delete:"))
async def backup_delete_confirm(callback: CallbackQuery):
    """Подтверждение удаления резервной копии"""
    try:
        backup_idx = int(callback.data.split(":")[2])
        backups = await get_backups()
        
        if backup_idx >= len(backups):
            await callback.answer("❌ Резервная копия не найдена", show_alert=True)
            return
        
        backup = backups[backup_idx]
        formatted_time = await format_time_with_timezone(backup['created'])
        
        text = (
            "⚠️ <b>ВНИМАНИЕ! Удаление резервной копии</b>\n\n"
            f"Вы собираетесь удалить резервную копию:\n"
            f"📁 <b>Файл:</b> {backup['name']}\n"
            f"📊 <b>Тип:</b> {backup['type']}\n"
            f"🕐 <b>Создан:</b> {formatted_time}\n"
            f"💾 <b>Размер:</b> {format_file_size(backup['size'])}\n\n"
            f"🚨 <b>Это действие необратимо!</b>\n"
            f"Удаленную резервную копию восстановить будет невозможно.\n\n"
            f"Продолжить удаление?"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🗑️ Да, удалить", callback_data=f"backup:delete_confirm:{backup_idx}")
        builder.button(text="❌ Отмена", callback_data=f"backup:detail:{backup_idx}")
        builder.adjust(2)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка подтверждения удаления: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("backup:delete_confirm:"))
async def backup_delete_execute(callback: CallbackQuery):
    """Выполнить удаление резервной копии"""
    try:
        backup_idx = int(callback.data.split(":")[2])
        backups = await get_backups()
        
        if backup_idx >= len(backups):
            await callback.answer("❌ Резервная копия не найдена", show_alert=True)
            return
        
        backup = backups[backup_idx]
        
        await callback.message.edit_text(
            "⏳ <b>Удаление резервной копии...</b>\n\n"
            "Пожалуйста, подождите."
        )
        
        # Выполняем удаление
        from services.backup_service import delete_backup
        success = await delete_backup(backup["path"])
        
        if success:
            current_time = await format_time_with_timezone(datetime.now())
            text = (
                "✅ <b>Резервная копия удалена успешно!</b>\n\n"
                f"📁 Удален файл: {backup['name']}\n"
                f"💾 Освобождено места: {format_file_size(backup['size'])}\n"
                f"🕐 Время удаления: {current_time}"
            )
        else:
            text = (
                "❌ <b>Ошибка удаления!</b>\n\n"
                "Удаление не удалось. Проверьте логи для получения подробной информации.\n"
                "Файл остался без изменений."
            )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="◀️ К списку", callback_data="backup:list")
        builder.button(text="🏠 Главное меню", callback_data="menu:main")
        builder.adjust(2)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        await callback.message.edit_text(
            f"❌ <b>Критическая ошибка удаления!</b>\n\n"
            f"Детали: <code>{str(e)}</code>\n\n"
            f"Обратитесь к администратору.",
            reply_markup=InlineKeyboardBuilder().button(
                text="◀️ Назад", callback_data="backup:main"
            ).as_markup()
        )
        await callback.answer()


@router.callback_query(F.data == "backup:settings")
async def backup_settings_menu(callback: CallbackQuery):
    """Показать меню настроек резервного копирования"""
    try:
        await callback.answer()  # Отвечаем сразу, чтобы избежать повторных нажатий
        
        settings = await backup_service.get_backup_settings()
        
        enabled = "✅ Включено" if settings.get("backup_enabled") else "❌ Отключено"
        notifications = "✅ Включены" if settings.get("notify_admin") else "❌ Отключены"
        compression = "✅ Включено" if settings.get("compress_backups") else "❌ Отключено"
        db_backup = "✅ Включено" if settings.get("backup_database") else "❌ Отключено"
        settings_backup = "✅ Включено" if settings.get("backup_settings") else "❌ Отключено"
        
        text = (
            f"⚙️ <b>Настройки резервного копирования</b>\n\n"
            f"🔄 <b>Автобэкап:</b> {enabled}\n"
            f"⏰ <b>Интервал:</b> {settings.get('backup_interval_hours', 24)} часов\n"
            f"📦 <b>Макс. бэкапов:</b> {settings.get('max_backups', 7)}\n"
            f"📧 <b>Уведомления:</b> {notifications}\n"
            f"🗜️ <b>Сжатие:</b> {compression}\n"
            f"💾 <b>База данных:</b> {db_backup}\n"
            f"📄 <b>Настройки:</b> {settings_backup}\n\n"
            f"<i>Выберите параметр для изменения:</i>"
        )
        
        await callback.message.edit_text(text, reply_markup=build_backup_settings_menu())
        
    except Exception as e:
        logger.error(f"Ошибка получения настроек бэкапа: {e}")
        await callback.answer("❌ Ошибка получения настроек", show_alert=True)


@router.callback_query(F.data.startswith("backup_settings:toggle_"))
async def backup_settings_toggle(callback: CallbackQuery):
    """Переключить boolean настройку"""
    try:
        # Немедленно отвечаем на callback чтобы предотвратить повторные нажатия
        await callback.answer()
        
        setting_name = callback.data.split(":")[-1].replace("toggle_", "")
        
        # Маппинг названий
        setting_map = {
            "enabled": "backup_enabled",
            "notifications": "notify_admin", 
            "compression": "compress_backups",
            "db_backup": "backup_database",
            "settings_backup": "backup_settings"
        }
        
        if setting_name not in setting_map:
            logger.warning(f"Неизвестная настройка: {setting_name}")
            return
        
        actual_setting = setting_map[setting_name]
        
        # Получаем текущие настройки
        settings = await backup_service.get_backup_settings()
        
        # Переключаем значение
        current_value = settings.get(actual_setting, True)
        new_value = not current_value
        
        # Обновляем настройку
        success = await backup_service.update_backup_settings({actual_setting: new_value})
        
        if not success:
            logger.error(f"Не удалось обновить настройку {actual_setting}")
            return
        
        setting_labels = {
            "enabled": "Автоматическое резервное копирование",
            "notifications": "Уведомления администратора",
            "compression": "Сжатие архивов",
            "db_backup": "Резервное копирование базы данных",
            "settings_backup": "Резервное копирование настроек"
        }
        
        status = "включено" if new_value else "отключено"
        logger.info(f"Настройка '{setting_labels[setting_name]}' {status}")
        
        # Обновляем меню без рекурсивного вызова
        updated_settings = await backup_service.get_backup_settings()
        
        enabled = "✅ Включено" if updated_settings.get("backup_enabled") else "❌ Отключено"
        notifications = "✅ Включены" if updated_settings.get("notify_admin") else "❌ Отключены"
        compression = "✅ Включено" if updated_settings.get("compress_backups") else "❌ Отключено"
        db_backup = "✅ Включено" if updated_settings.get("backup_database") else "❌ Отключено"
        settings_backup = "✅ Включено" if updated_settings.get("backup_settings") else "❌ Отключено"
        
        text = (
            f"⚙️ <b>Настройки резервного копирования</b>\n\n"
            f"🔄 <b>Автобэкап:</b> {enabled}\n"
            f"⏰ <b>Интервал:</b> {updated_settings.get('backup_interval_hours', 24)} часов\n"
            f"📦 <b>Макс. бэкапов:</b> {updated_settings.get('max_backups', 7)}\n"
            f"📧 <b>Уведомления:</b> {notifications}\n"
            f"🗜️ <b>Сжатие:</b> {compression}\n"
            f"💾 <b>База данных:</b> {db_backup}\n"
            f"📄 <b>Настройки:</b> {settings_backup}\n\n"
            f"<i>Выберите параметр для изменения:</i>"
        )
        
        await callback.message.edit_text(text, reply_markup=build_backup_settings_menu())
        
    except Exception as e:
        logger.error(f"Ошибка переключения настройки: {e}")
        await callback.answer("❌ Ошибка изменения настройки", show_alert=True)


@router.callback_query(F.data == "backup_settings:set_interval")
async def backup_settings_set_interval(callback: CallbackQuery, state: FSMContext):
    """Установить интервал резервного копирования"""
    await callback.message.edit_text(
        "⏰ <b>Настройка интервала резервного копирования</b>\n\n"
        "Введите интервал в часах (от 1 до 168):\n"
        "• 1 = каждый час\n"
        "• 6 = каждые 6 часов\n"
        "• 24 = раз в день (по умолчанию)\n"
        "• 168 = раз в неделю\n\n"
        "<i>Отправьте число от 1 до 168:</i>"
    )
    await state.set_state(BackupStates.waiting_for_interval)
    await callback.answer()


@router.message(BackupStates.waiting_for_interval)
async def backup_process_interval(message: Message, state: FSMContext):
    """Обработать ввод интервала"""
    try:
        interval = int(message.text.strip())
        
        if not 1 <= interval <= 168:
            await message.answer(
                "❌ Неверное значение!\n"
                "Интервал должен быть от 1 до 168 часов."
            )
            return
        
        # Обновляем настройку
        await backup_service.update_backup_settings({"backup_interval_hours": interval})
        
        await message.answer(
            f"✅ Интервал резервного копирования установлен: {interval} часов",
            reply_markup=InlineKeyboardBuilder().button(
                text="◀️ К настройкам", callback_data="backup:settings"
            ).as_markup()
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат!\n"
            "Введите число от 1 до 168."
        )
    except Exception as e:
        logger.error(f"Ошибка установки интервала: {e}")
        await message.answer("❌ Ошибка сохранения настройки")
        await state.clear()


@router.callback_query(F.data == "backup_settings:set_max_backups")
async def backup_settings_set_max_backups(callback: CallbackQuery, state: FSMContext):
    """Установить максимальное количество бэкапов"""
    await callback.message.edit_text(
        "📦 <b>Настройка количества хранимых бэкапов</b>\n\n"
        "Введите максимальное количество резервных копий для хранения (от 1 до 50):\n"
        "• 3 = хранить только 3 последних бэкапа\n"
        "• 7 = хранить неделю бэкапов (по умолчанию)\n"
        "• 30 = хранить месяц бэкапов\n\n"
        "<i>Отправьте число от 1 до 50:</i>"
    )
    await state.set_state(BackupStates.waiting_for_max_backups)
    await callback.answer()


@router.message(BackupStates.waiting_for_max_backups)
async def backup_process_max_backups(message: Message, state: FSMContext):
    """Обработать ввод максимального количества бэкапов"""
    try:
        max_backups = int(message.text.strip())
        
        if not 1 <= max_backups <= 50:
            await message.answer(
                "❌ Неверное значение!\n"
                "Количество должно быть от 1 до 50."
            )
            return
        
        # Обновляем настройку
        await backup_service.update_backup_settings({"max_backups": max_backups})
        
        await message.answer(
            f"✅ Максимальное количество бэкапов установлено: {max_backups}",
            reply_markup=InlineKeyboardBuilder().button(
                text="◀️ К настройкам", callback_data="backup:settings"
            ).as_markup()
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат!\n"
            "Введите число от 1 до 50."
        )
    except Exception as e:
        logger.error(f"Ошибка установки max_backups: {e}")
        await message.answer("❌ Ошибка сохранения настройки")
        await state.clear()


@router.callback_query(F.data == "backup:export_project")
async def backup_export_project(callback: CallbackQuery):
    """Создать полный экспорт проекта"""
    try:
        await callback.message.edit_text(
            "📦 <b>Создание экспорта проекта...</b>\n\n"
            "⏳ Создается полный архив проекта со всем исходным кодом, данными и настройками.\n"
            "Это может занять несколько минут...",
        )
        
        # Создаем экспорт проекта
        export_path = await create_project_export()
        
        if export_path:
            export_name = Path(export_path).name
            size = format_file_size(Path(export_path).stat().st_size)
            
            text = (
                "✅ <b>Экспорт проекта создан успешно!</b>\n\n"
                f"📁 <b>Файл:</b> <code>{export_name}</code>\n"
                f"💾 <b>Размер:</b> {size}\n"
                f"🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
                f"📋 <b>Содержит:</b>\n"
                f"• Полный исходный код проекта\n"
                f"• База данных с постами и настройками\n"
                f"• Конфигурационные файлы\n"
                f"• Документация и инструкции\n\n"
                f"🎯 <b>Назначение:</b> Полное восстановление проекта на новом сервере"
            )
            
            builder = InlineKeyboardBuilder()
            # Извлекаем полный timestamp из имени файла (YYYYMMDD_HHMMSS)
            timestamp = export_name.replace("project_export_", "").replace(".zip", "")
            builder.button(text="📥 Скачать экспорт", callback_data=f"backup:dl_export:{timestamp}")
            builder.button(text="◀️ Назад в меню", callback_data="backup:main")
            builder.adjust(1)
            
        else:
            text = (
                "❌ <b>Ошибка создания экспорта проекта!</b>\n\n"
                "Проверьте логи для получения подробной информации."
            )
            
            builder = InlineKeyboardBuilder()
            builder.button(text="◀️ Назад в меню", callback_data="backup:main")
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка создания экспорта проекта: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка создания экспорта проекта!</b>\n\n"
            f"Детали: <code>{str(e)}</code>",
            reply_markup=InlineKeyboardBuilder().button(
                text="◀️ Назад", callback_data="backup:main"
            ).as_markup()
        )
        await callback.answer()


@router.callback_query(F.data.startswith("backup:dl_export:"))
async def backup_download_export(callback: CallbackQuery):
    """Скачать экспорт проекта"""
    try:
        timestamp = callback.data.split(":", 2)[2]
        # Ищем файл экспорта по timestamp
        backup_dir = Path("backups")
        search_pattern = f"project_export_{timestamp}.zip"
        logger.info(f"Поиск экспорта: паттерн={search_pattern}, timestamp={timestamp}")
        export_files = list(backup_dir.glob(search_pattern))
        
        if not export_files:
            # Показываем все файлы экспортов для отладки
            all_exports = list(backup_dir.glob("project_export_*.zip"))
            logger.error(f"Экспорт не найден! Ожидали: {search_pattern}, найденные экспорты: {[f.name for f in all_exports]}")
            await callback.answer("❌ Файл экспорта не найден", show_alert=True)
            return
            
        export_path = export_files[0]
        export_name = export_path.name
        
        # Отправляем файл
        document = FSInputFile(str(export_path), filename=export_name)
        
        formatted_time = await format_time_with_timezone(datetime.fromtimestamp(export_path.stat().st_mtime))
        caption = (
            f"📦 <b>Экспорт проекта Autoposter Bot</b>\n\n"
            f"📁 <b>Файл:</b> <code>{export_name}</code>\n"
            f"💾 <b>Размер:</b> {format_file_size(export_path.stat().st_size)}\n"
            f"🕐 <b>Создан:</b> {formatted_time}\n\n"
            f"📋 <b>Содержит:</b> Полный исходный код + данные + настройки\n"
            f"🎯 <b>Для:</b> Восстановления проекта на новом сервере"
        )
        
        await callback.message.answer_document(
            document=document,
            caption=caption
        )
        
        await callback.answer("✅ Экспорт отправлен!")
        
    except Exception as e:
        logger.error(f"Ошибка скачивания экспорта: {e}")
        await callback.answer("❌ Ошибка отправки файла", show_alert=True)