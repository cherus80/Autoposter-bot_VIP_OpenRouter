# config.py - Конфигурация
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Поддержка нескольких администраторов
# Поддерживаем как ADMIN_ID, так и ADMIN_IDS для Docker развертывания
_admin_id_str = os.getenv("ADMIN_IDS") or os.getenv("ADMIN_ID", "")

# Отладочная информация для диагностики
print(f"DEBUG: ADMIN_IDS env var = '{os.getenv('ADMIN_IDS')}'")
print(f"DEBUG: ADMIN_ID env var = '{os.getenv('ADMIN_ID')}'")
print(f"DEBUG: _admin_id_str = '{_admin_id_str}'")

if "," in _admin_id_str:
    # Список администраторов через запятую
    ADMIN_IDS = [int(id.strip()) for id in _admin_id_str.split(",") if id.strip().isdigit()]
else:
    # Один администратор (обратная совместимость)
    ADMIN_IDS = [int(_admin_id_str)] if _admin_id_str.isdigit() else []

print(f"DEBUG: Итоговый ADMIN_IDS = {ADMIN_IDS}")

# Для обратной совместимости оставляем ADMIN_ID как первый в списке
ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else None

CHANNEL_ID = os.getenv("CHANNEL_ID")

# OpenRouter.ai
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PROXY_URL = os.getenv("PROXY_URL")  # Опционально: "socks5://user:pass@host:port" или "http://user:pass@host:port"

# Модели OpenRouter для разных задач
OPENROUTER_POST_MODEL = os.getenv("OPENROUTER_POST_MODEL", "deepseek/deepseek-r1:free")  # Модель для генерации постов
OPENROUTER_IMAGE_PROMPT_MODEL = os.getenv("OPENROUTER_IMAGE_PROMPT_MODEL", "deepseek/deepseek-r1:free")  # Модель для промптов изображений

# OpenAI (для транскрибации голосовых сообщений)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Ключ OpenAI для работы с Whisper (whisper-1)

# Настройки retry для OpenRouter API (устойчивость к сбоям)
OPENROUTER_MAX_RETRIES = int(os.getenv("OPENROUTER_MAX_RETRIES", "3"))  # Максимальное количество попыток
OPENROUTER_RETRY_DELAYS = [1, 2, 4]  # Задержки между попытками в секундах (экспоненциальный backoff)

# Отладочная информация для OpenRouter
print(f"DEBUG: OPENROUTER_API_KEY найден = {'Да' if OPENROUTER_API_KEY else 'Нет'}")
if OPENROUTER_API_KEY:
    print(f"DEBUG: OPENROUTER_API_KEY начинается с = '{OPENROUTER_API_KEY[:10]}...'")
print(f"DEBUG: OPENROUTER_POST_MODEL = '{OPENROUTER_POST_MODEL}'")
print(f"DEBUG: OPENROUTER_IMAGE_PROMPT_MODEL = '{OPENROUTER_IMAGE_PROMPT_MODEL}'")
print(f"DEBUG: OPENAI_API_KEY найден = {'Да' if OPENAI_API_KEY else 'Нет'}")
print(f"DEBUG: Текущая рабочая директория = '{os.getcwd()}'")
print(f"DEBUG: .env файл существует = {os.path.exists('.env')}")

# VK
VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")

# Fal.ai
FAL_AI_KEY = os.getenv("FAL_AI_KEY")

# Call To Action  
VK_CTA_TEXT = os.getenv("VK_CTA_TEXT", "\n\n🔔 Подписывайтесь на нашу группу, чтобы быть в курсе всех новостей!")
