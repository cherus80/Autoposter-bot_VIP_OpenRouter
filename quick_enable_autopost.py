#!/usr/bin/env python3
"""
Быстрое включение автопостинга
Простой скрипт без интерактивности для включения автопостинга
"""

import asyncio
import logging
from database.settings_db import update_setting, get_setting
from managers.publishing_manager import PublishingManager
from config import ADMIN_ID

async def quick_enable():
    """Быстро включает автопостинг с минимальными настройками"""
    print("⚡ БЫСТРОЕ ВКЛЮЧЕНИЕ АВТОПОСТИНГА")
    print("=" * 40)
    
    try:
        # 1. Включаем автопостинг
        await update_setting('auto_mode_status', 'on')
        await update_setting('auto_posting_enabled', '1')
        print("✅ Автопостинг включен")
        
        # 2. Устанавливаем тестовый интервал 5 минут
        await update_setting('post_interval_minutes', '5')
        await update_setting('posting_interval_hours', '1')
        print("✅ Интервал: 5 минут (для тестирования)")
        
        # 3. Включаем публикацию в Telegram
        publishing_manager = PublishingManager()
        await publishing_manager.update_settings(
            user_id=int(ADMIN_ID),
            publish_to_tg=True
        )
        print("✅ Публикация в Telegram включена")
        
        # 4. Включаем изображения
        await update_setting('autofeed_with_image', 'on')
        await update_setting('autofeed_image_style', 'fantasy')
        print("✅ Изображения включены")
        
        print("\n🎯 ГОТОВО! Автопостинг запустится через 1-2 минуты.")
        print("🔍 Проверьте логи бота:")
        print("   docker logs -f --tail=20 [container_name]")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(quick_enable()) 