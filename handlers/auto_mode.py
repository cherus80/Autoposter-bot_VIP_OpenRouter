"""
@file: handlers/auto_mode.py
@description: Обработчики настроек автопостинга с улучшенным UX
@dependencies: database/settings_db.py
@created: 2025-01-20
@updated: 2025-01-21 - Добавлены настройки изображений для автопостинга
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from database.settings_db import get_setting, update_setting
from config import FAL_AI_KEY

logger = logging.getLogger(__name__)
router = Router()

async def safe_edit_message(cb: CallbackQuery, text: str, reply_markup=None):
    """Безопасное редактирование сообщения с fallback на отправку нового"""
    try:
        await cb.message.edit_text(text, reply_markup=reply_markup)
    except Exception as edit_error:
        logger.warning(f"Не удалось отредактировать сообщение: {edit_error}")
        await cb.message.answer(text, reply_markup=reply_markup)

# FSM для настройки интервала
class SetInterval(StatesGroup):
    waiting_for_unit_choice = State()  # Выбор минуты/часы
    waiting_for_interval = State()     # Ввод значения

def build_auto_mode_breadcrumbs():
    """Breadcrumbs для автопостинга"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")
        ]]
    )

def _style_kb(prefix: str = "auto_style:") -> InlineKeyboardMarkup:
    """Клавиатура выбора стиля изображения для автопостинга"""
    styles = {
        "photo": "📷 Фото",
        "digital_art": "🎨 Digital Art", 
        "anime": "🌸 Аниме",
        "cyberpunk": "🤖 Киберпанк",
        "fantasy": "🧙‍♂️ Фэнтези",
        "none": "🚫 Без стиля",
    }
    buttons = [
        InlineKeyboardButton(text=v, callback_data=f"{prefix}{k}") for k, v in styles.items()
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="auto:image_settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.callback_query(F.data == "menu:auto_mode")
async def cb_menu_auto_mode(cb: CallbackQuery):
    """Обработчик кнопки 'Автопостинг' с улучшенным интерфейсом"""
    logger.info(f"Callback menu:auto_mode от пользователя {cb.from_user.id}")
    
    try:
        # Получаем настройки автопостинга (проверяем обе настройки для точности)
        auto_enabled_raw = await get_setting("auto_posting_enabled", False)
        auto_mode_status = await get_setting("auto_mode_status", "off")
        
        # Приводим к булевому типу с учетом разных форматов
        if isinstance(auto_enabled_raw, str):
            auto_enabled = auto_enabled_raw.lower() in ['true', '1', 'on', 'yes']
        else:
            auto_enabled = bool(auto_enabled_raw)
            
        # Дополнительная проверка через auto_mode_status
        auto_enabled = auto_enabled and (auto_mode_status == "on")
        
        interval_hours_raw = await get_setting("posting_interval_hours", 24)
        interval_hours = int(interval_hours_raw)  # Преобразуем в int
        interval_minutes_raw = await get_setting("post_interval_minutes", 240)
        
        # Преобразуем в int для корректного сравнения
        interval_minutes = int(interval_minutes_raw)
        
        status_icon = "✅" if auto_enabled else "❌"
        status_text = "Включен" if auto_enabled else "Выключен"
        
        # Определяем лучший способ отображения интервала
        if interval_minutes < 60:
            interval_display = f"{interval_minutes} минут(ы)"
        elif interval_minutes % 60 == 0:
            hours = interval_minutes // 60
            interval_display = f"{hours} час(ов)"
        else:
            hours = interval_minutes // 60
            minutes = interval_minutes % 60
            interval_display = f"{hours}ч {minutes}мин"
        
        info_text = f"🤖 <b>Управление автопостингом</b>\n\n"
        info_text += f"📊 <b>Текущее состояние:</b>\n"
        info_text += f"• Статус: {status_icon} <b>{status_text}</b>\n"
        info_text += f"• Интервал: <b>{interval_display}</b>\n\n"
        
        if auto_enabled:
            info_text += f"⚠️ <i>Автопостинг активен. Новые посты будут " \
                        f"публиковаться каждые {interval_display}.</i>\n\n"
        else:
            info_text += f"💡 <i>Автопостинг отключен. Включите для автоматической " \
                        f"публикации по расписанию.</i>\n\n"
        
        info_text += f"🎯 <b>Выберите действие:</b>"
        
        # Кнопки управления с улучшенным дизайном
        toggle_text = "❌ Выключить" if auto_enabled else "✅ Включить"
        toggle_icon = "⚠️" if auto_enabled else "🚀"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{toggle_icon} {toggle_text}",
                callback_data="auto:confirm_toggle" if auto_enabled else "auto:toggle"
            )],
            [InlineKeyboardButton(text="⏱️ Настроить интервал", callback_data="auto:interval")],
            [InlineKeyboardButton(text="🖼️ Настройки изображений", callback_data="auto:image_settings")],
            [
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")
            ]
        ])
        
        await safe_edit_message(cb, info_text, reply_markup=kb)
        await cb.answer()
    except Exception as e:
        logger.error(f"Ошибка при получении настроек автопостинга: {e}")
        await cb.answer("❌ Ошибка при получении настроек")

@router.callback_query(F.data == "auto:confirm_toggle")
async def cb_auto_confirm_toggle(cb: CallbackQuery):
    """Подтверждение отключения автопостинга"""
    await safe_edit_message(cb,
        "⚠️ <b>Подтверждение отключения</b>\n\n"
        "Вы уверены, что хотите отключить автопостинг?\n"
        "Автоматическая публикация постов будет остановлена.\n\n"
        "🔄 <i>Вы сможете включить автопостинг в любой момент.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, отключить", callback_data="auto:toggle"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="menu:auto_mode")
            ]
        ])
    )
    await cb.answer()

@router.callback_query(F.data == "auto:toggle")
async def cb_auto_toggle(cb: CallbackQuery):
    """Переключение автопостинга с подтверждением"""
    try:
        # Получаем текущий статус с той же логикой, что и в главном меню
        auto_enabled_raw = await get_setting("auto_posting_enabled", False)
        auto_mode_status = await get_setting("auto_mode_status", "off")
        
        # Приводим к булевому типу с учетом разных форматов
        if isinstance(auto_enabled_raw, str):
            current_state = auto_enabled_raw.lower() in ['true', '1', 'on', 'yes']
        else:
            current_state = bool(auto_enabled_raw)
            
        # Дополнительная проверка через auto_mode_status
        current_state = current_state and (auto_mode_status == "on")
        
        new_state = not current_state
        
        # Проверяем контент-план перед включением автопостинга
        if new_state:
            from managers.content_plan_manager import ContentPlanManager
            content_manager = ContentPlanManager()
            unused_topics = await content_manager.count_unused_items()
            
            if unused_topics == 0:
                await safe_edit_message(cb,
                    "⚠️ <b>Невозможно включить автопостинг</b>\n\n"
                    "📝 <b>Контент-план пуст!</b>\n"
                    "Нет доступных тем для публикации.\n\n"
                    "🎯 <b>Что нужно сделать:</b>\n"
                    "1. Перейти в <b>Контент-план</b>\n"
                    "2. Загрузить темы для постов\n"
                    "3. Вернуться к настройкам автопостинга\n\n"
                    "💡 <i>Рекомендуется загрузить минимум 10-20 тем для стабильной работы.</i>",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📝 Перейти к контент-плану", callback_data="menu:content_plan")],
                        [InlineKeyboardButton(text="🔧 Настройки автопостинга", callback_data="menu:auto_mode")]
                    ])
                )
                await cb.answer("❌ Сначала загрузите контент-план!")
                return
        
        # Обновляем обе настройки для синхронизации
        await update_setting("auto_posting_enabled", 1 if new_state else 0)
        await update_setting("auto_mode_status", "on" if new_state else "off")
        
        if new_state:
            interval_minutes_raw = await get_setting("post_interval_minutes", 240)
            interval_minutes = int(interval_minutes_raw)  # Преобразуем в int
            
            # Определяем лучший способ отображения интервала
            if interval_minutes < 60:
                interval_display = f"{interval_minutes} минут(ы)"
            elif interval_minutes % 60 == 0:
                hours = interval_minutes // 60
                interval_display = f"{hours} час(ов)"
            else:
                hours = interval_minutes // 60
                minutes = interval_minutes % 60
                interval_display = f"{hours}ч {minutes}мин"
            
            success_text = f"✅ <b>Автопостинг включен!</b>\n\n" \
                          f"🚀 Посты будут публиковаться каждые <b>{interval_display}</b>.\n" \
                          f"📊 Следите за статистикой в главном меню."
        else:
            success_text = f"❌ <b>Автопостинг отключен</b>\n\n" \
                          f"🔄 Автоматическая публикация остановлена.\n" \
                          f"💡 Включите снова, когда будете готовы."
        
        await cb.message.edit_text(
            success_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔧 Настройки автопостинга", callback_data="menu:auto_mode")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
            ])
        )
        await cb.answer("✅ Настройки сохранены!")
        
    except Exception as e:
        logger.error(f"Ошибка при переключении автопостинга: {e}")
        await cb.answer("❌ Ошибка при сохранении настроек")

@router.callback_query(F.data == "auto:interval")
async def cb_auto_interval(cb: CallbackQuery, state: FSMContext):
    """Настройка интервала автопостинга с улучшенным интерфейсом"""
    await state.set_state(SetInterval.waiting_for_unit_choice)
    
    current_interval_raw = await get_setting("posting_interval_hours", 24)
    current_interval = int(current_interval_raw)  # Преобразуем в int
    
    await cb.message.edit_text(
        f"⏱️ <b>Настройка интервала публикации</b>\n\n"
        f"📊 <b>Текущий интервал:</b> {current_interval} час(ов)\n\n"
        f"🎯 <b>Выберите единицу измерения:</b>\n"
        f"• <b>Часы</b>\n"
        f"• <b>Минуты</b>\n\n"
        f"💡 <i>Отправьте выбор:</i>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Часы", callback_data="interval:hours")],
                [InlineKeyboardButton(text="Минуты", callback_data="interval:minutes")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="auto:cancel")]
            ]
        )
    )
    await cb.answer()

# Выбор единицы измерения
@router.callback_query(F.data == "interval:hours")
async def cb_select_hours(cb: CallbackQuery, state: FSMContext):
    """Выбор настройки в часах"""
    await state.update_data(unit="hours")
    await state.set_state(SetInterval.waiting_for_interval)
    
    current_hours_raw = await get_setting("posting_interval_hours", 24)
    current_hours = int(current_hours_raw)  # Преобразуем в int
    
    await cb.message.edit_text(
        f"⏰ <b>Настройка интервала в часах</b>\n\n"
        f"📊 <b>Текущий интервал:</b> {current_hours} час(ов)\n\n"
        f"🎯 <b>Введите новый интервал в часах:</b>\n"
        f"• Минимум: <b>1</b> час\n"
        f"• Максимум: <b>168</b> часов (7 дней)\n"
        f"• Рекомендуемые: 1, 2, 4, 6, 12, 24 часа\n\n"
        f"💡 <i>Отправьте число от 1 до 168 или выберите быстрый вариант:</i>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="⚡ 1 час", callback_data="quick:hours:1"),
                    InlineKeyboardButton(text="🕐 4 часа", callback_data="quick:hours:4"),
                    InlineKeyboardButton(text="🕕 12 часов", callback_data="quick:hours:12")
                ],
                [
                    InlineKeyboardButton(text="📅 24 часа", callback_data="quick:hours:24"),
                    InlineKeyboardButton(text="📆 72 часа", callback_data="quick:hours:72")
                ],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="auto:cancel")]
            ]
        )
    )
    await cb.answer()

@router.callback_query(F.data == "interval:minutes")
async def cb_select_minutes(cb: CallbackQuery, state: FSMContext):
    """Выбор настройки в минутах"""
    await state.update_data(unit="minutes")
    await state.set_state(SetInterval.waiting_for_interval)
    
    current_minutes_raw = await get_setting("post_interval_minutes", 240)  # 4 часа по умолчанию
    current_minutes = int(current_minutes_raw)  # Преобразуем в int
    
    await cb.message.edit_text(
        f"⏱️ <b>Настройка интервала в минутах</b>\n\n"
        f"📊 <b>Текущий интервал:</b> {current_minutes} минут(ы)\n\n"
        f"🎯 <b>Введите новый интервал в минутах:</b>\n"
        f"• Минимум: <b>1</b> минута\n"
        f"• Максимум: <b>10080</b> минут (7 дней)\n"
        f"• Рекомендуемые: 5, 15, 30, 60, 120, 240 минут\n\n"
        f"💡 <i>Отправьте число от 1 до 10080 или выберите быстрый вариант:</i>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="⚡ 5 мин", callback_data="quick:minutes:5"),
                    InlineKeyboardButton(text="🕐 15 мин", callback_data="quick:minutes:15"),
                    InlineKeyboardButton(text="🕕 30 мин", callback_data="quick:minutes:30")
                ],
                [
                    InlineKeyboardButton(text="⏰ 1 час", callback_data="quick:minutes:60"),
                    InlineKeyboardButton(text="⏰ 2 часа", callback_data="quick:minutes:120"),
                    InlineKeyboardButton(text="⏰ 4 часа", callback_data="quick:minutes:240")
                ],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="auto:cancel")]
            ]
        )
    )
    await cb.answer()

# Быстрая установка интервала (обновленная версия)
@router.callback_query(F.data.startswith("quick:"))
async def cb_set_quick_interval_new(cb: CallbackQuery, state: FSMContext):
    """Быстрая установка интервала с поддержкой минут и часов"""
    parts = cb.data.split(":")
    unit = parts[1]  # hours или minutes
    value = int(parts[2])
    
    try:
        if unit == "hours":
            await update_setting("posting_interval_hours", value)
            # Также обновляем минуты для совместимости с планировщиком
            await update_setting("post_interval_minutes", value * 60)
            interval_text = f"{value} час(ов)"
        else:  # minutes
            await update_setting("post_interval_minutes", value)
            # Также обновляем часы для отображения
            await update_setting("posting_interval_hours", max(1, value // 60))
            interval_text = f"{value} минут(ы)"
        
        await state.clear()
        
        await cb.message.edit_text(
            f"✅ <b>Интервал обновлен!</b>\n\n"
            f"⏱️ Новый интервал: <b>{interval_text}</b>\n"
            f"🔄 Изменения вступят в силу при следующей публикации.\n\n"
            f"💡 <i>Планировщик использует интервал в минутах для точности.</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔧 Настройки автопостинга", callback_data="menu:auto_mode")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
            ])
        )
        await cb.answer("✅ Интервал сохранен!")
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении интервала: {e}")
        await cb.answer("❌ Ошибка при сохранении")

@router.message(SetInterval.waiting_for_interval)
async def msg_set_interval(msg: Message, state: FSMContext):
    """Обработка ввода интервала с поддержкой минут и часов"""
    if not msg.text:
        await msg.answer("❌ Пожалуйста, отправьте текстовое сообщение с числом.")
        return
    
    try:
        data = await state.get_data()
        unit = data.get("unit", "hours")
        interval = int(msg.text.strip())
        
        if unit == "hours":
            if not (1 <= interval <= 168):
                await msg.answer(
                    "❌ <b>Некорректный интервал!</b>\n\n"
                    "🎯 Введите число от <b>1</b> до <b>168</b> часов.\n"
                    "💡 Например: 4, 12, 24"
                )
                return
            
            await update_setting("posting_interval_hours", interval)
            await update_setting("post_interval_minutes", interval * 60)
            interval_text = f"{interval} час(ов)"
            
        else:  # minutes
            if not (1 <= interval <= 10080):  # 7 дней = 10080 минут
                await msg.answer(
                    "❌ <b>Некорректный интервал!</b>\n\n"
                    "🎯 Введите число от <b>1</b> до <b>10080</b> минут.\n"
                    "💡 Например: 5, 15, 30, 60, 240"
                )
                return
            
            await update_setting("post_interval_minutes", interval)
            await update_setting("posting_interval_hours", max(1, interval // 60))
            interval_text = f"{interval} минут(ы)"
        
        await state.clear()
        
        await msg.answer(
            f"✅ <b>Интервал успешно установлен!</b>\n\n"
            f"⏱️ Новый интервал: <b>{interval_text}</b>\n"
            f"🔄 Автопостинг будет публиковать посты каждые {interval_text}.\n\n"
            f"💡 <i>Планировщик использует интервал в минутах для точности.</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔧 Настройки автопостинга", callback_data="menu:auto_mode")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
            ])
        )
        
    except ValueError:
        await msg.answer(
            "❌ <b>Ошибка ввода!</b>\n\n"
            "🎯 Введите <b>число</b>.\n"
            "💡 Например: <code>30</code> (для 30 минут) или <code>2</code> (для 2 часов)"
        )
    except Exception as e:
        logger.error(f"Ошибка при сохранении интервала: {e}")
        await msg.answer("❌ Ошибка при сохранении настроек")

@router.callback_query(F.data == "auto:cancel")
async def cb_auto_cancel(cb: CallbackQuery, state: FSMContext):
    """Отмена настройки с возвратом в меню"""
    await state.clear()
    await cb.answer("❌ Настройка отменена")
    # Возвращаемся к настройкам автопостинга
    await cb_menu_auto_mode(cb)

@router.callback_query(F.data == "auto:image_settings")
async def cb_auto_image_settings(cb: CallbackQuery):
    """Настройки изображений для автопостинга"""
    try:
        # Получаем текущие настройки
        with_image = await get_setting("autofeed_with_image", "off")
        image_style = await get_setting("autofeed_image_style", "fantasy")
        
        # Переводим стили на русский для отображения
        style_names = {
            "photo": "📷 Фото",
            "digital_art": "🎨 Digital Art", 
            "anime": "🌸 Аниме",
            "cyberpunk": "🤖 Киберпанк",
            "fantasy": "🧙‍♂️ Фэнтези",
            "none": "🚫 Без стиля",
        }
        
        with_image_status = "✅ Включены" if with_image == "on" else "❌ Отключены"
        style_display = style_names.get(image_style, image_style)
        
        # Проверяем статус Fal.ai токена
        fal_status = "🔑 Токен настроен" if FAL_AI_KEY else "❌ Токен НЕ настроен"
        
        info_text = f"🖼️ <b>Настройки изображений для автопостинга</b>\n\n"
        info_text += f"📊 <b>Текущие настройки:</b>\n"
        info_text += f"• Fal.ai: <b>{fal_status}</b>\n"
        info_text += f"• Изображения: <b>{with_image_status}</b>\n"
        if with_image == "on":
            info_text += f"• Стиль: <b>{style_display}</b>\n"
        info_text += f"\n💡 <i>Настройки применяются только к автоматически генерируемым постам.</i>\n\n"
        info_text += f"🎯 <b>Выберите действие:</b>"
        
        # Кнопка переключения изображений
        toggle_text = "❌ Отключить изображения" if with_image == "on" else "✅ Включить изображения"
        
        kb_buttons = [
            [InlineKeyboardButton(text=toggle_text, callback_data="auto:toggle_images")]
        ]
        
        # Если изображения включены, добавляем кнопку выбора стиля
        if with_image == "on":
            kb_buttons.append([InlineKeyboardButton(text="🎨 Выбрать стиль", callback_data="auto:choose_style")])
        
        kb_buttons.append([InlineKeyboardButton(text="⬅️ Назад к автопостингу", callback_data="menu:auto_mode")])
        
        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
        
        await cb.message.edit_text(info_text, reply_markup=kb)
        await cb.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при получении настроек изображений: {e}")
        await cb.answer("❌ Ошибка при получении настроек")

@router.callback_query(F.data == "auto:toggle_images")
async def cb_auto_toggle_images(cb: CallbackQuery):
    """Переключение включения/отключения изображений в автопостинге"""
    try:
        current_state = await get_setting("autofeed_with_image", "off")
        new_state = "off" if current_state == "on" else "on"
        
        # Проверяем наличие токена Fal.ai при включении изображений
        if new_state == "on" and not FAL_AI_KEY:
            await cb.message.edit_text(
                "❌ <b>Fal.ai токен НЕ настроен!</b>\n\n"
                "🖼️ Для генерации изображений в автопостинге необходимо настроить FAL_AI_KEY в переменных окружения.\n\n"
                "💡 <i>Обратитесь к администратору или добавьте FAL_AI_KEY в .env файл.</i>\n\n"
                "🔧 <b>После настройки токена вы сможете включить изображения.</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к настройкам", callback_data="auto:image_settings")],
                    [InlineKeyboardButton(text="🤖 К автопостингу", callback_data="menu:auto_mode")]
                ])
            )
            await cb.answer("❌ Fal.ai токен не настроен!")
            return
        
        await update_setting("autofeed_with_image", new_state)
        
        if new_state == "on":
            success_text = f"✅ <b>Изображения включены!</b>\n\n" \
                          f"🖼️ Автоматически генерируемые посты будут содержать изображения.\n" \
                          f"🎨 Не забудьте настроить стиль изображений и промпт для изображений в главном меню."
        else:
            success_text = f"❌ <b>Изображения отключены</b>\n\n" \
                          f"📝 Автоматически генерируемые посты будут содержать только текст.\n" \
                          f"💡 Включите снова, если хотите добавить изображения к постам."
        
        await cb.message.edit_text(
            success_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🖼️ Настройки изображений", callback_data="auto:image_settings")],
                [InlineKeyboardButton(text="🤖 К автопостингу", callback_data="menu:auto_mode")]
            ])
        )
        await cb.answer("✅ Настройки сохранены!")
        
    except Exception as e:
        logger.error(f"Ошибка при переключении изображений: {e}")
        await cb.answer("❌ Ошибка при сохранении настроек")

@router.callback_query(F.data == "auto:choose_style")
async def cb_auto_choose_style(cb: CallbackQuery):
    """Выбор стиля изображения для автопостинга"""
    current_style = await get_setting("autofeed_image_style", "fantasy")
    
    # Переводим стили на русский для отображения
    style_names = {
        "photo": "📷 Фото",
        "digital_art": "🎨 Digital Art", 
        "anime": "🌸 Аниме",
        "cyberpunk": "🤖 Киберпанк",
        "fantasy": "🧙‍♂️ Фэнтези",
        "none": "🚫 Без стиля",
    }
    
    current_style_display = style_names.get(current_style, current_style)
    
    info_text = f"🎨 <b>Выбор стиля изображений</b>\n\n"
    info_text += f"📊 <b>Текущий стиль:</b> <b>{current_style_display}</b>\n\n"
    info_text += f"💡 <i>Выберите стиль для автоматически генерируемых изображений:</i>"
    
    await cb.message.edit_text(info_text, reply_markup=_style_kb())
    await cb.answer()

@router.callback_query(F.data.startswith("auto_style:"))
async def cb_auto_set_style(cb: CallbackQuery):
    """Установка стиля изображения для автопостинга"""
    try:
        style = cb.data.split(":")[1]
        await update_setting("autofeed_image_style", style)
        
        # Переводим стили на русский для отображения
        style_names = {
            "photo": "📷 Фото",
            "digital_art": "🎨 Digital Art", 
            "anime": "🌸 Аниме",
            "cyberpunk": "🤖 Киберпанк",
            "fantasy": "🧙‍♂️ Фэнтези",
            "none": "🚫 Без стиля",
        }
        
        style_display = style_names.get(style, style)
        
        success_text = f"✅ <b>Стиль изображений установлен!</b>\n\n" \
                      f"🎨 <b>Выбранный стиль:</b> {style_display}\n\n" \
                      f"🖼️ Все автоматически генерируемые изображения будут создаваться в этом стиле."
        
        await cb.message.edit_text(
            success_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎨 Изменить стиль", callback_data="auto:choose_style")],
                [InlineKeyboardButton(text="🖼️ Настройки изображений", callback_data="auto:image_settings")],
                [InlineKeyboardButton(text="🤖 К автопостингу", callback_data="menu:auto_mode")]
            ])
        )
        await cb.answer("✅ Стиль сохранен!")
        
    except Exception as e:
        logger.error(f"Ошибка при установке стиля: {e}")
        await cb.answer("❌ Ошибка при сохранении стиля") 