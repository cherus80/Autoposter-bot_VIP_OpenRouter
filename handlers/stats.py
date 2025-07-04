"""
@file: handlers/stats.py
@description: Обработчики статистики бота
@dependencies: database/posts_db.py, database/settings_db.py
@created: 2025-01-20
"""

import logging
from datetime import datetime, timedelta, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.settings_db import get_setting
from database.posts_db import count_posts, get_last_post_time

logger = logging.getLogger(__name__)
router = Router()

def format_time_with_timezone(dt: datetime, user_timezone: str) -> str:
    """Форматирует время с учетом пользовательского часового пояса"""
    if dt is None:
        return None
    
    try:
        # Парсим часовой пояс пользователя
        if user_timezone.startswith('+'):
            tz_offset = int(user_timezone[1:])
        elif user_timezone.startswith('-'):
            tz_offset = -int(user_timezone[1:])
        else:
            tz_offset = 3  # По умолчанию UTC+3 (Москва)
        
        # Все новые посты сохраняются в UTC, поэтому интерпретируем время как UTC
        if dt.tzinfo is None:
            # Интерпретируем время из БД как UTC
            dt = dt.replace(tzinfo=timezone.utc)
        
        # Конвертируем в пользовательский часовой пояс
        user_tz = timezone(timedelta(hours=tz_offset))
        local_time = dt.astimezone(user_tz)
        
        return local_time.strftime('%d.%m.%Y %H:%M')
        
    except (ValueError, TypeError) as e:
        logger.warning(f"Ошибка конвертации времени: {e}")
        # Fallback - возвращаем исходное время
        return dt.strftime('%d.%m.%Y %H:%M')

@router.callback_query(F.data == "menu:stats")
async def cb_menu_stats(cb: CallbackQuery):
    """Обработчик кнопки 'Статистика'"""
    logger.info(f"Callback menu:stats от пользователя {cb.from_user.id}")
    try:
        # Получаем данные о постах
        total_posts = await count_posts()
        last_post_time = await get_last_post_time()
        
        # Получаем пользовательский часовой пояс
        user_timezone = await get_setting("user_timezone", "+3")
        
        # Получаем настройки автопостинга (используем ту же логику, что и в auto_mode)
        auto_enabled_raw = await get_setting("auto_posting_enabled", False)
        auto_mode_status = await get_setting("auto_mode_status", "off")
        
        # Приводим к булевому типу с учетом разных форматов
        if isinstance(auto_enabled_raw, str):
            auto_enabled = auto_enabled_raw.lower() in ['true', '1', 'on', 'yes']
        else:
            auto_enabled = bool(auto_enabled_raw)
            
        # Дополнительная проверка через auto_mode_status
        auto_enabled = auto_enabled and (auto_mode_status == "on")
        
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
        
        stats_text = f"📊 <b>Статистика бота</b>\n\n"
        
        # Информация о постах
        stats_text += f"📝 <b>Публикации:</b>\n"
        stats_text += f"• Всего постов: {total_posts}\n"
        
        if last_post_time:
            formatted_time = format_time_with_timezone(last_post_time, user_timezone)
            stats_text += f"• Последний пост: {formatted_time}\n"
        else:
            stats_text += f"• Постов еще не было\n"
        
        # Информация об автопостинге
        stats_text += f"\n🤖 <b>Автопостинг:</b>\n"
        if auto_enabled:
            stats_text += f"• Статус: ✅ <b>Включен</b>\n"
            stats_text += f"• Интервал: <b>{interval_display}</b>\n"
            
            # Вычисляем время до следующего поста
            if last_post_time:
                next_post_time = last_post_time + timedelta(minutes=interval_minutes)
                now = datetime.utcnow()
                
                if next_post_time > now:
                    time_diff = next_post_time - now
                    hours_left = int(time_diff.total_seconds() // 3600)
                    minutes_left = int((time_diff.total_seconds() % 3600) // 60)
                    
                    if hours_left > 0:
                        stats_text += f"• До следующего поста: {hours_left}ч {minutes_left}мин\n"
                    else:
                        stats_text += f"• До следующего поста: {minutes_left}мин\n"
                    
                    # Показываем время следующего поста в пользовательском часовом поясе
                    formatted_next_time = format_time_with_timezone(next_post_time, user_timezone)
                    stats_text += f"• Следующий пост: {formatted_next_time}\n"
                else:
                    stats_text += f"• Следующий пост: готов к публикации\n"
            else:
                stats_text += f"• Следующий пост: готов к публикации\n"
        else:
            stats_text += f"• Статус: ❌ Выключен\n"
            stats_text += f"• Интервал: {interval_display} (настроен, но не активен)\n"
        
        # Добавляем информацию о часовом поясе
        stats_text += f"\n🕒 <b>Часовой пояс:</b> UTC{user_timezone}\n"
        
        # Кнопка "Назад"
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]]
        )
        
        try:
            await cb.message.edit_text(stats_text, reply_markup=back_kb)
        except Exception as edit_error:
            # Если не удалось отредактировать (например, сообщение уже изменено), отправляем новое
            logger.warning(f"Не удалось отредактировать сообщение: {edit_error}")
            await cb.message.answer(stats_text, reply_markup=back_kb)
        
        await cb.answer()
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        await cb.answer("❌ Ошибка при получении статистики") 