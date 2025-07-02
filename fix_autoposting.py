#!/usr/bin/env python3
"""
Скрипт для исправления проблем с автопостингом
Автоматически включает и настраивает автопостинг
"""

import asyncio
import logging
from database.settings_db import update_setting, get_setting
from managers.publishing_manager import PublishingManager
from config import ADMIN_ID

logging.basicConfig(level=logging.INFO)

async def fix_autoposting():
    """Исправляет основные проблемы с автопостингом"""
    print("🔧 ИСПРАВЛЕНИЕ АВТОПОСТИНГА")
    print("=" * 50)
    
    try:
        # 1. Включаем автопостинг
        print("\n🚀 Включаем автопостинг...")
        await update_setting('auto_mode_status', 'on')
        await update_setting('auto_posting_enabled', '1')
        print("✅ Автопостинг включен")
        
        # 2. Устанавливаем тестовый интервал для быстрой проверки
        print("\n⏰ Устанавливаем интервал публикации...")
        current_interval = await get_setting('post_interval_minutes', '240')
        print(f"  Текущий интервал: {current_interval} минут")
        
        # Предлагаем установить тестовый интервал
        response = input("  Установить тестовый интервал 5 минут? (y/n): ").lower()
        if response in ['y', 'yes', 'да']:
            await update_setting('post_interval_minutes', '5')
            await update_setting('posting_interval_hours', '1')  # обновляем и часы для совместимости
            print("✅ Установлен тестовый интервал: 5 минут")
        else:
            # Устанавливаем разумный интервал по умолчанию
            await update_setting('post_interval_minutes', '30')
            await update_setting('posting_interval_hours', '1')
            print("✅ Установлен интервал: 30 минут")
        
        # 3. Проверяем и включаем публикацию в платформы
        print("\n📤 Настраиваем публикацию в платформы...")
        publishing_manager = PublishingManager()
        pub_settings = await publishing_manager.get_settings(user_id=int(ADMIN_ID))
        
        print(f"  Telegram: {'✅' if pub_settings.publish_to_tg else '❌'}")
        print(f"  VK: {'✅' if pub_settings.publish_to_vk else '❌'}")
        
        if not pub_settings.publish_to_tg:
            await publishing_manager.update_settings(
                user_id=int(ADMIN_ID),
                publish_to_tg=True
            )
            print("✅ Включена публикация в Telegram")
        
        # VK оставляем как есть, так как может не быть настроен
        
        # 4. Проверяем настройки изображений
        print("\n🖼️ Настраиваем изображения...")
        with_image = await get_setting('autofeed_with_image', 'off')
        if with_image == 'off':
            await update_setting('autofeed_with_image', 'on')
            print("✅ Включены изображения для автопостов")
        else:
            print("✅ Изображения уже включены")
        
        # Устанавливаем стиль изображений
        style = await get_setting('autofeed_image_style', 'fantasy')
        print(f"  Стиль изображений: {style}")
        
        print("\n🎯 НАСТРОЙКИ ЗАВЕРШЕНЫ!")
        print("Автопостинг должен заработать в течение следующих 1-2 минут.")
        print("Проверьте логи бота на предмет сообщений о публикации.")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при исправлении автопостинга: {e}")
        logging.error(f"Ошибка при исправлении автопостинга: {e}", exc_info=True)
        return False

async def show_current_status():
    """Показывает текущее состояние после исправления"""
    print("\n📊 ТЕКУЩЕЕ СОСТОЯНИЕ:")
    
    auto_mode = await get_setting("auto_mode_status", "off")
    auto_enabled = await get_setting("auto_posting_enabled", "0")
    interval_min = await get_setting("post_interval_minutes", "240")
    with_image = await get_setting("autofeed_with_image", "off")
    
    print(f"• Режим автопостинга: {auto_mode}")
    print(f"• Автопостинг активен: {auto_enabled}")
    print(f"• Интервал: {interval_min} минут")
    print(f"• Изображения: {with_image}")
    
    publishing_manager = PublishingManager()
    pub_settings = await publishing_manager.get_settings(user_id=int(ADMIN_ID))
    print(f"• Публикация в Telegram: {'✅' if pub_settings.publish_to_tg else '❌'}")
    print(f"• Публикация в VK: {'✅' if pub_settings.publish_to_vk else '❌'}")

if __name__ == "__main__":
    async def main():
        success = await fix_autoposting()
        if success:
            await show_current_status()
        print("\n" + "=" * 50)
    
    asyncio.run(main()) 