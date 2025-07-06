#!/usr/bin/env python3
"""
🚨 ЭКСТРЕННОЕ ИСПРАВЛЕНИЕ АВТОПОСТИНГА
Решает проблему с географическими ограничениями OpenAI
"""

import asyncio
import logging
import os
from database.settings_db import update_setting, get_setting

logging.basicConfig(level=logging.INFO)

async def emergency_fix():
    """Экстренное исправление критической ошибки автопостинга"""
    print("🚨 ЭКСТРЕННОЕ ИСПРАВЛЕНИЕ АВТОПОСТИНГА")
    print("=" * 50)
    print("❌ Проблема: OpenAI заблокирован в вашем регионе")
    print("🔧 Решение: Переключаемся на бесплатную модель без ограничений")
    print()
    
    try:
        # 1. СРОЧНО отключаем автопостинг для остановки зацикливания
        print("🛑 Отключаем автопостинг для остановки зацикливания...")
        await update_setting('auto_mode_status', 'off')
        await update_setting('auto_posting_enabled', '0')
        print("✅ Автопостинг отключен")
        
        # 2. Проверяем текущие модели в переменных окружения
        print("\n🔍 Проверяем текущие настройки...")
        current_post_model = os.getenv("OPENROUTER_POST_MODEL", "НЕ УСТАНОВЛЕНО")
        current_image_model = os.getenv("OPENROUTER_IMAGE_PROMPT_MODEL", "НЕ УСТАНОВЛЕНО")
        
        print(f"• Текущая модель для постов: {current_post_model}")
        print(f"• Текущая модель для изображений: {current_image_model}")
        
        # 3. Обновляем переменные окружения на безопасные модели
        print("\n🔄 Переключаемся на безопасные модели...")
        
        # Устанавливаем безопасные модели без географических ограничений
        safe_models = {
            "OPENROUTER_POST_MODEL": "deepseek/deepseek-r1:free",
            "OPENROUTER_IMAGE_PROMPT_MODEL": "deepseek/deepseek-r1:free"
        }
        
        for key, value in safe_models.items():
            os.environ[key] = value
            print(f"✅ {key} = {value}")
        
        # 4. Создаем/обновляем .env файл с безопасными настройками
        print("\n📝 Обновляем .env файл...")
        
        env_lines = []
        env_file_exists = os.path.exists('.env')
        
        if env_file_exists:
            with open('.env', 'r', encoding='utf-8') as f:
                env_lines = f.readlines()
        
        # Обновляем или добавляем настройки модели
        model_settings = {
            "OPENROUTER_POST_MODEL": "deepseek/deepseek-r1:free",
            "OPENROUTER_IMAGE_PROMPT_MODEL": "deepseek/deepseek-r1:free"
        }
        
        updated_lines = []
        updated_keys = set()
        
        for line in env_lines:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key = line.split('=')[0].strip()
                if key in model_settings:
                    updated_lines.append(f"{key}={model_settings[key]}\n")
                    updated_keys.add(key)
                else:
                    updated_lines.append(line + '\n')
            else:
                updated_lines.append(line + '\n')
        
        # Добавляем новые настройки, если их не было
        for key, value in model_settings.items():
            if key not in updated_keys:
                updated_lines.append(f"{key}={value}\n")
        
        # Записываем обновленный .env
        with open('.env', 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        
        print("✅ .env файл обновлен")
        
        # 5. Показываем инструкции по перезапуску
        print("\n🔄 ТРЕБУЕТСЯ ПЕРЕЗАПУСК БОТА!")
        print("Выполните одну из команд:")
        print("• Docker Compose: docker-compose restart")
        print("• Docker: docker restart <container_name>")
        print("• Python: перезапустите main.py")
        print()
        print("⚠️ После перезапуска модель изменится на deepseek/deepseek-r1:free")
        print("✅ Эта модель работает без географических ограничений")
        
        # 6. Создаем скрипт для включения автопостинга после перезапуска
        restart_script = """#!/usr/bin/env python3
import asyncio
from database.settings_db import update_setting

async def enable_autopost():
    await update_setting('auto_mode_status', 'on')
    await update_setting('auto_posting_enabled', '1')
    print("✅ Автопостинг включен с безопасной моделью")

if __name__ == "__main__":
    asyncio.run(enable_autopost())
"""
        
        with open('enable_autopost_after_restart.py', 'w', encoding='utf-8') as f:
            f.write(restart_script)
        
        print("\n📝 Создан скрипт enable_autopost_after_restart.py")
        print("Запустите его после перезапуска бота для включения автопостинга")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при экстренном исправлении: {e}")
        logging.error(f"Ошибка при экстренном исправлении: {e}", exc_info=True)
        return False

async def check_status():
    """Проверяем статус после исправления"""
    print("\n📊 СТАТУС ПОСЛЕ ИСПРАВЛЕНИЯ:")
    
    auto_mode = await get_setting("auto_mode_status", "off")
    auto_enabled = await get_setting("auto_posting_enabled", "0")
    
    print(f"• Автопостинг: {auto_mode}")
    print(f"• Автопостинг активен: {auto_enabled}")
    print(f"• Модель для постов: {os.getenv('OPENROUTER_POST_MODEL', 'НЕ УСТАНОВЛЕНО')}")
    print(f"• Модель для изображений: {os.getenv('OPENROUTER_IMAGE_PROMPT_MODEL', 'НЕ УСТАНОВЛЕНО')}")

if __name__ == "__main__":
    asyncio.run(emergency_fix())
    asyncio.run(check_status()) 