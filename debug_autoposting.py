#!/usr/bin/env python3
"""
Диагностический скрипт для автопостинга
Проверяет все настройки и состояние системы
"""

import asyncio
import logging
from datetime import datetime, timedelta
from database.settings_db import get_setting
from database.posts_db import get_last_post_time, count_posts, get_recent_posts
from managers.content_plan_manager import ContentPlanManager
from managers.prompt_manager import PromptManager
from managers.publishing_manager import PublishingManager
from config import ADMIN_ID

logging.basicConfig(level=logging.INFO)

async def diagnose_autoposting():
    """Полная диагностика автопостинга"""
    print("🔍 ДИАГНОСТИКА АВТОПОСТИНГА")
    print("=" * 50)
    
    # 1. Проверяем основные настройки
    print("\n📊 ОСНОВНЫЕ НАСТРОЙКИ:")
    auto_mode = await get_setting("auto_mode_status", "off")
    auto_enabled = await get_setting("auto_posting_enabled", "0")
    interval_min = await get_setting("post_interval_minutes", "240")
    
    print(f"• auto_mode_status: {auto_mode}")
    print(f"• auto_posting_enabled: {auto_enabled}")
    print(f"• post_interval_minutes: {interval_min}")
    
    # 2. Проверяем настройки публикации
    print("\n📤 НАСТРОЙКИ ПУБЛИКАЦИИ:")
    publishing_manager = PublishingManager()
    pub_settings = await publishing_manager.get_settings(user_id=int(ADMIN_ID))
    print(f"• publish_to_tg: {pub_settings.publish_to_tg}")
    print(f"• publish_to_vk: {pub_settings.publish_to_vk}")
    
    # 3. Проверяем контент-план
    print("\n📝 КОНТЕНТ-ПЛАН:")
    content_manager = ContentPlanManager()
    total_topics = await content_manager.count_all_items()
    unused_topics = await content_manager.count_unused_items()
    next_topic = await content_manager.get_next_topic()
    
    print(f"• Всего тем: {total_topics}")
    print(f"• Неиспользованных: {unused_topics}")
    print(f"• Следующая тема: {next_topic.theme if next_topic else 'Нет доступных тем'}")
    
    # 4. Проверяем промпты
    print("\n💬 ПРОМПТЫ:")
    prompt_manager = PromptManager()
    content_prompt = await prompt_manager.get_prompt("content_generation")
    image_prompt = await prompt_manager.get_prompt("image")
    
    print(f"• Промпт контента: {'✅ Настроен' if content_prompt else '❌ Отсутствует'}")
    if content_prompt:
        print(f"  Длина: {len(content_prompt)} символов")
    
    print(f"• Промпт изображений: {'✅ Настроен' if image_prompt else '❌ Отсутствует'}")
    if image_prompt:
        print(f"  Длина: {len(image_prompt)} символов")
    
    # 5. Проверяем последние посты
    print("\n📋 ИСТОРИЯ ПОСТОВ:")
    total_posts = await count_posts()
    last_post_time = await get_last_post_time()
    
    print(f"• Всего постов: {total_posts}")
    print(f"• Последний пост: {last_post_time if last_post_time else 'Постов нет'}")
    
    if last_post_time:
        # Вычисляем время до следующего поста
        interval_minutes = int(interval_min)
        next_post_time = last_post_time + timedelta(minutes=interval_minutes)
        now = datetime.now()
        
        if next_post_time > now:
            time_diff = next_post_time - now
            hours_left = int(time_diff.total_seconds() // 3600)
            minutes_left = int((time_diff.total_seconds() % 3600) // 60)
            print(f"• До следующего поста: {hours_left}ч {minutes_left}мин")
        else:
            print("• До следующего поста: ⚠️ ГОТОВ К ПУБЛИКАЦИИ!")
    
    # 6. Показываем последние несколько постов
    recent_posts = await get_recent_posts(limit=3)
    if recent_posts:
        print(f"\n📌 ПОСЛЕДНИЕ {len(recent_posts)} ПОСТА:")
        for i, post in enumerate(recent_posts, 1):
            print(f"  {i}. {post.topic[:40]}...")
            print(f"     Время: {post.published_at}")
            print(f"     Тип: {post.post_type}")
            print(f"     TG: {'✅' if post.telegram_published else '❌'}, VK: {'✅' if post.vk_published else '❌'}")
    
    # 7. Проверяем настройки изображений
    print("\n🖼️ НАСТРОЙКИ ИЗОБРАЖЕНИЙ:")
    with_image_setting = await get_setting("autofeed_with_image", "off")
    image_style = await get_setting("autofeed_image_style", "fantasy")
    
    print(f"• Изображения в автопостах: {with_image_setting}")
    print(f"• Стиль изображений: {image_style}")
    
    # 8. Итоговая проверка готовности к автопостингу
    print("\n🎯 ПРОВЕРКА ГОТОВНОСТИ:")
    ready_for_autopost = True
    issues = []
    
    if auto_mode != "on":
        ready_for_autopost = False
        issues.append("Автопостинг выключен")
    
    if auto_enabled not in ["1", "true", "on"]:
        ready_for_autopost = False
        issues.append("Автопостинг не активирован")
    
    if not pub_settings.publish_to_tg and not pub_settings.publish_to_vk:
        ready_for_autopost = False
        issues.append("Не выбрана ни одна платформа для публикации")
    
    if unused_topics == 0:
        ready_for_autopost = False
        issues.append("Контент-план пуст")
    
    if not content_prompt:
        ready_for_autopost = False
        issues.append("Не настроен промпт для генерации контента")
    
    if ready_for_autopost:
        print("✅ ВСЕ ГОТОВО ДЛЯ АВТОПОСТИНГА!")
    else:
        print("❌ ПРОБЛЕМЫ С АВТОПОСТИНГОМ:")
        for issue in issues:
            print(f"  • {issue}")
    
    print("\n" + "=" * 50)
    return ready_for_autopost, issues

if __name__ == "__main__":
    asyncio.run(diagnose_autoposting()) 