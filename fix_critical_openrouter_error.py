#!/usr/bin/env python3
"""
🚨 КОМПЛЕКСНОЕ ИСПРАВЛЕНИЕ КРИТИЧЕСКИХ ОШИБОК OPENROUTER
Решает проблемы с географическими ограничениями, зацикливанием и устаревшими настройками
"""

import asyncio
import logging
from database.settings_db import get_setting, update_setting

logging.basicConfig(level=logging.INFO)

async def fix_critical_openrouter_issues():
    """Комплексное исправление критических проблем OpenRouter"""
    print("🚨 КОМПЛЕКСНОЕ ИСПРАВЛЕНИЕ КРИТИЧЕСКИХ ОШИБОК OPENROUTER")
    print("=" * 65)
    
    # 1. Отключаем автопостинг если еще не отключен
    print("\n🛑 Шаг 1: Отключение автопостинга...")
    await update_setting('auto_mode_status', 'off')
    await update_setting('auto_posting_enabled', '0')
    print("✅ Автопостинг отключен")
    
    # 2. Удаляем устаревшие настройки
    print("\n🧹 Шаг 2: Очистка устаревших настроек...")
    
    # Удаляем старую настройку провайдера
    old_provider = await get_setting('ai_provider', None)
    if old_provider:
        print(f"🗑️ Удаляем устаревшую настройку ai_provider: {old_provider}")
        await update_setting('ai_provider', '')  # Устанавливаем пустое значение
    
    # 3. Устанавливаем безопасные модели через БД
    print("\n🔧 Шаг 3: Установка безопасных моделей...")
    await update_setting('openrouter_post_model', 'deepseek/deepseek-r1:free')
    await update_setting('openrouter_image_prompt_model', 'deepseek/deepseek-r1:free')
    print("✅ Установлены безопасные модели deepseek/deepseek-r1:free")
    
    # 4. Корректируем интервал постинга
    print("\n⏰ Шаг 4: Корректировка интервала постинга...")
    current_interval = await get_setting('post_interval_minutes', '3')
    if int(current_interval) < 60:  # Если менее часа
        await update_setting('post_interval_minutes', '60')  # Устанавливаем 1 час
        print(f"✅ Интервал постинга изменен с {current_interval} мин на 60 мин")
    else:
        print(f"✅ Интервал постинга уже корректный: {current_interval} мин")
    
    # 5. Проверяем статус
    print("\n📊 Шаг 5: Проверка статуса после исправления...")
    
    status = {
        'auto_mode_status': await get_setting('auto_mode_status', 'unknown'),
        'auto_posting_enabled': await get_setting('auto_posting_enabled', 'unknown'),
        'openrouter_post_model': await get_setting('openrouter_post_model', 'unknown'),
        'openrouter_image_prompt_model': await get_setting('openrouter_image_prompt_model', 'unknown'),
        'post_interval_minutes': await get_setting('post_interval_minutes', 'unknown'),
        'ai_provider': await get_setting('ai_provider', 'unknown')
    }
    
    print("📋 Текущий статус:")
    for key, value in status.items():
        status_emoji = "✅" if value not in ['unknown', 'perplexity'] else "⚠️"
        print(f"{status_emoji} {key}: {value}")
    
    # 6. Создаем инструкции для пользователя
    print("\n🎯 СЛЕДУЮЩИЕ ШАГИ:")
    print("1. 🔄 Перезапустите бота:")
    print("   • Docker: docker-compose restart")
    print("   • Python: Ctrl+C и запустите заново")
    print("2. 📊 Проверьте логи на отсутствие ошибок OpenAI")
    print("3. ✅ Используйте enable_autopost_after_restart.py для включения автопостинга")
    print("4. 🔍 Модель deepseek/deepseek-r1:free работает без географических ограничений")
    
    return status

if __name__ == "__main__":
    asyncio.run(fix_critical_openrouter_issues()) 