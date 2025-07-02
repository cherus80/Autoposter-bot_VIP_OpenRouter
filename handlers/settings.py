"""
@file: handlers/settings.py
@description: Обработчики настроек публикации с улучшенным UX
@dependencies: managers/publishing_manager.py
@created: 2025-01-20
@updated: 2025-01-20 - Улучшение UX интерфейса
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from managers.publishing_manager import get_publishing_settings, update_publishing_settings
from database.settings_db import get_setting, update_setting
from config import VK_ACCESS_TOKEN, VK_GROUP_ID, OPENROUTER_POST_MODEL, OPENROUTER_IMAGE_PROMPT_MODEL

logger = logging.getLogger(__name__)
router = Router()

# FSM для настройки часового пояса
class TimezoneSettings(StatesGroup):
    waiting_for_timezone = State()

def build_settings_breadcrumbs():
    """Breadcrumbs для настроек публикации"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")
        ]]
    )

@router.callback_query(F.data == "menu:publishing_settings")
async def cb_menu_publishing_settings(cb: CallbackQuery):
    """Настройки публикации с улучшенным интерфейсом"""
    try:
        settings = await get_publishing_settings(user_id=cb.from_user.id)
        
        # Получаем текущий часовой пояс
        current_timezone = await get_setting("user_timezone", "+3")
        
        # Иконки и статусы
        tg_icon = "✅" if settings.publish_to_tg else "❌"
        vk_icon = "✅" if settings.publish_to_vk else "❌"
        tg_status = "Включен" if settings.publish_to_tg else "Выключен"
        vk_status = "Включен" if settings.publish_to_vk else "Выключен"
        
        settings_text = f"📤 <b>Настройки публикации</b>\n\n"
        settings_text += f"🎯 <b>Платформы для автопостинга:</b>\n\n"
        settings_text += f"📱 <b>Telegram:</b> {tg_icon} <b>{tg_status}</b>\n"
        if settings.publish_to_tg:
            settings_text += f"   💡 <i>Посты публикуются в текущий чат</i>\n\n"
        else:
            settings_text += f"   💡 <i>Публикация в Telegram отключена</i>\n\n"
            
        # Статус VK токенов
        vk_token_status = "🔑 Токены настроены" if all([VK_ACCESS_TOKEN, VK_GROUP_ID]) else "❌ Токены НЕ настроены"
        
        settings_text += f"🔵 <b>VKontakte:</b> {vk_icon} <b>{vk_status}</b>\n"
        if settings.publish_to_vk:
            settings_text += f"   💡 <i>Публикация в VK группу активна</i>\n"
            settings_text += f"   {vk_token_status}\n\n"
        else:
            settings_text += f"   💡 <i>Публикация в VK отключена</i>\n"
            settings_text += f"   {vk_token_status}\n\n"
        
        settings_text += f"🕒 <b>Часовой пояс:</b> UTC{current_timezone}\n"
        settings_text += f"   💡 <i>Влияет на отображение времени в статистике</i>\n\n"
        
        # AI модели OpenRouter - берем из переменных окружения
        post_model = OPENROUTER_POST_MODEL or "Не настроена"
        image_model = OPENROUTER_IMAGE_PROMPT_MODEL or "Не настроена"
        
        settings_text += f"🤖 <b>OpenRouter модели:</b>\n"
        settings_text += f"   📝 <i>Посты:</i> {post_model}\n"
        settings_text += f"   🎨 <i>Изображения:</i> {image_model}\n\n"
        
        # Предупреждения
        if not settings.publish_to_tg and not settings.publish_to_vk:
            settings_text += f"⚠️ <b>ВНИМАНИЕ:</b> Все платформы отключены!\n"
            settings_text += f"   <i>Включите хотя бы одну для автопостинга.</i>\n\n"
        
        settings_text += f"🎯 <b>Выберите платформу для настройки:</b>"
        
        # Кнопки управления
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📱 Telegram", 
                    callback_data="settings:toggle_telegram"
                ),
                InlineKeyboardButton(
                    text="🔵 VK", 
                    callback_data="settings:toggle_vk"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🕒 Часовой пояс", 
                    callback_data="settings:timezone"
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")
            ]
        ])
        
        await cb.message.edit_text(settings_text, reply_markup=kb)
        await cb.answer()
    except Exception as e:
        logger.error(f"Ошибка при получении настроек публикации: {e}")
        await cb.answer("❌ Ошибка при получении настроек")

@router.callback_query(F.data == "settings:timezone")
async def cb_settings_timezone(cb: CallbackQuery, state: FSMContext):
    """Настройка часового пояса"""
    current_timezone = await get_setting("user_timezone", "+3")
    
    await state.set_state(TimezoneSettings.waiting_for_timezone)
    
    await cb.message.edit_text(
        f"🕒 <b>Настройка часового пояса</b>\n\n"
        f"📊 <b>Текущий часовой пояс:</b> UTC{current_timezone}\n\n"
        f"🌍 <b>Примеры часовых поясов:</b>\n"
        f"• <code>+3</code> - Москва (MSK)\n"
        f"• <code>+7</code> - Новосибирск, Красноярск\n"
        f"• <code>+5</code> - Екатеринбург (YEKT)\n"
        f"• <code>+2</code> - Калининград\n"
        f"• <code>+0</code> - Лондон (GMT)\n"
        f"• <code>-5</code> - Нью-Йорк (EST)\n\n"
        f"💡 <b>Введите ваш часовой пояс</b> в формате:\n"
        f"<code>+7</code> или <code>-5</code> (со знаком + или -)",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="settings:cancel_timezone")
            ]]
        )
    )
    await cb.answer()

@router.message(TimezoneSettings.waiting_for_timezone)
async def process_timezone(message: Message, state: FSMContext):
    """Обработка введенного часового пояса"""
    try:
        timezone_text = message.text.strip()
        
        # Валидация формата
        if not timezone_text.startswith(('+', '-')) or len(timezone_text) < 2:
            await message.answer(
                "❌ <b>Неверный формат!</b>\n\n"
                "Введите часовой пояс в формате <code>+7</code> или <code>-5</code>"
            )
            return
        
        # Проверяем что после знака идут только цифры
        timezone_value = timezone_text[1:]
        if not timezone_value.isdigit():
            await message.answer(
                "❌ <b>Неверный формат!</b>\n\n"
                "После знака + или - должны быть только цифры. Например: <code>+7</code>"
            )
            return
        
        # Проверяем диапазон (от -12 до +14)
        tz_int = int(timezone_value)
        if timezone_text.startswith('-'):
            tz_int = -tz_int
        
        if tz_int < -12 or tz_int > 14:
            await message.answer(
                "❌ <b>Неверный часовой пояс!</b>\n\n"
                "Часовой пояс должен быть от <code>-12</code> до <code>+14</code>"
            )
            return
        
        # Сохраняем настройку
        await update_setting("user_timezone", timezone_text)
        
        await state.clear()
        
        await message.answer(
            f"✅ <b>Часовой пояс установлен!</b>\n\n"
            f"🕒 <b>Новый часовой пояс:</b> UTC{timezone_text}\n\n"
            f"📊 Время в статистике теперь будет отображаться "
            f"с учетом вашего часового пояса.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(text="📤 К настройкам", callback_data="menu:publishing_settings"),
                    InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")
                ]]
            )
        )
        
        logger.info(f"Часовой пояс установлен: UTC{timezone_text} для пользователя {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке часового пояса: {e}")
        await message.answer("❌ Ошибка при сохранении часового пояса")
        await state.clear()

@router.callback_query(F.data == "settings:cancel_timezone")
async def cb_cancel_timezone(cb: CallbackQuery, state: FSMContext):
    """Отмена настройки часового пояса"""
    await state.clear()
    await cb.answer("❌ Настройка отменена")
    # Возвращаемся к настройкам публикации
    await cb_menu_publishing_settings(cb)

@router.callback_query(F.data == "settings:toggle_telegram")
async def cb_toggle_telegram(cb: CallbackQuery):
    """Переключение публикации в Telegram"""
    try:
        settings = await get_publishing_settings(user_id=cb.from_user.id)
        new_state = not settings.publish_to_tg
        
        await update_publishing_settings(
            user_id=cb.from_user.id,
            publish_to_tg=new_state,
            publish_to_vk=settings.publish_to_vk
        )
        
        # Уведомление о изменении
        status_text = "включен" if new_state else "отключен"
        await cb.answer(f"✅ Telegram {status_text}!")
        
        # Обновляем меню настроек публикации
        await cb_menu_publishing_settings(cb)
        
    except Exception as e:
        logger.error(f"Ошибка при переключении Telegram: {e}")
        await cb.answer("❌ Ошибка при сохранении настроек")

@router.callback_query(F.data == "settings:toggle_vk")
async def cb_toggle_vk(cb: CallbackQuery):
    """Переключение публикации в VK"""
    try:
        settings = await get_publishing_settings(user_id=cb.from_user.id)
        new_state = not settings.publish_to_vk
        
        # Проверяем наличие VK токенов при включении
        if new_state and not all([VK_ACCESS_TOKEN, VK_GROUP_ID]):
            await cb.answer(
                "❌ VK токены не настроены!\n"
                "Укажите VK_ACCESS_TOKEN и VK_GROUP_ID в .env файле",
                show_alert=True
            )
            return
        
        await update_publishing_settings(
            user_id=cb.from_user.id,
            publish_to_tg=settings.publish_to_tg,
            publish_to_vk=new_state
        )
        
        # Уведомление о изменении
        if new_state:
            if all([VK_ACCESS_TOKEN, VK_GROUP_ID]):
                await cb.answer("✅ VKontakte включен! Посты будут публиковаться в VK.")
            else:
                await cb.answer("⚠️ VK включен, но токены не настроены!", show_alert=True)
        else:
            await cb.answer("✅ VKontakte отключен!")
        
        # Обновляем меню настроек публикации
        await cb_menu_publishing_settings(cb)
        
    except Exception as e:
        logger.error(f"Ошибка при переключении VK: {e}")
        await cb.answer("❌ Ошибка при сохранении настроек")



 