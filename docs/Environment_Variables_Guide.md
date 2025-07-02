# Руководство по настройке переменных окружения

## Обзор

Autoposter Bot V2.0 использует различные AI сервисы для разных задач. Данное руководство поможет правильно настроить переменные окружения в файле `.env`.

## Обязательные переменные

### Telegram Bot
```env
BOT_TOKEN=your_telegram_bot_token_here
CHANNEL_ID=your_telegram_channel_id_here  # @your_channel или -1001234567890
ADMIN_IDS=your_telegram_user_id_here      # 123456789 или 123456789,987654321
```

### OpenRouter.ai (основной AI провайдер)
```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_POST_MODEL=deepseek/deepseek-r1:free
OPENROUTER_IMAGE_PROMPT_MODEL=deepseek/deepseek-r1:free

# Настройки устойчивости к сбоям (опционально)
OPENROUTER_MAX_RETRIES=3  # Количество попыток при ошибках (по умолчанию: 3)
```

**Устойчивость к сбоям:**
- При временных проблемах с OpenRouter.ai бот автоматически повторяет запросы
- Интервалы между попытками: 1, 2, 4 секунды (экспоненциальный backoff)
- Пользователи получают информативные сообщения о проблемах
- Администратор получает уведомления о сбоях в автопостинге

## Дополнительные сервисы

### OpenAI (для транскрипции голосовых сообщений)

**Зачем нужен:**
- Распознавание голосовых сообщений пользователей
- Преобразование речи в текст для генерации постов

**Настройка:**
```env
OPENAI_API_KEY=your_openai_api_key_here
```

**Модель:** Автоматически используется `whisper-1` (оптимальная для русского языка)

**Стоимость:** ~$0.006 за минуту аудио

**Что происходит без ключа:**
- Бот работает нормально с текстовыми сообщениями
- При попытке отправить голосовое сообщение показывается предупреждение
- Пользователю предлагается ввести тему текстом

### Fal.ai (для генерации изображений)

```env
FAL_AI_KEY=your_fal_ai_key_here
```

### VK API (для публикации ВКонтакте)

```env
VK_ACCESS_TOKEN=your_vk_access_token_here
VK_GROUP_ID=your_vk_group_id_here
VK_CTA_TEXT=\n\n🔔 Подписывайтесь на нашу группу!
```

### Proxy (при необходимости)

```env
PROXY_URL=socks5://user:pass@host:port
# или
PROXY_URL=http://user:pass@host:port
```

## Рекомендуемые конфигурации

### 🚀 Минимальная настройка (только текстовые посты)
```env
BOT_TOKEN=...
CHANNEL_ID=...
ADMIN_IDS=...
OPENROUTER_API_KEY=...
OPENROUTER_POST_MODEL=deepseek/deepseek-r1:free
OPENROUTER_IMAGE_PROMPT_MODEL=deepseek/deepseek-r1:free
```

### 🎤 С поддержкой голосовых сообщений
```env
# Минимальная настройка +
OPENAI_API_KEY=...
```

### 🖼️ С генерацией изображений
```env
# Минимальная настройка +
FAL_AI_KEY=...
```

### 📱 С публикацией в VK
```env
# Любая из предыдущих +
VK_ACCESS_TOKEN=...
VK_GROUP_ID=...
```

## Альтернативные модели OpenRouter

### Для улучшенного качества постов:
```env
OPENROUTER_POST_MODEL=qwen/qwen-2.5-72b-instruct
# или
OPENROUTER_POST_MODEL=anthropic/claude-3.5-sonnet
```

### Для лучших промптов изображений:
```env
OPENROUTER_IMAGE_PROMPT_MODEL=anthropic/claude-3.5-sonnet
# или
OPENROUTER_IMAGE_PROMPT_MODEL=openai/gpt-4-turbo
```

## Безопасность

⚠️ **ВАЖНО:**
- НЕ делитесь файлом `.env` публично
- Добавьте `.env` в `.gitignore`
- Используйте переменные окружения в продакшене
- Регулярно обновляйте API ключи

## Troubleshooting

### Голосовые сообщения не работают
1. Проверьте наличие `OPENAI_API_KEY` в `.env`
2. Убедитесь что ключ действующий
3. Проверьте баланс OpenAI аккаунта

### Изображения не генерируются
1. Проверьте `FAL_AI_KEY`
2. Убедитесь что промпт для изображений настроен в боте

### Ошибки OpenRouter
1. Проверьте `OPENROUTER_API_KEY`
2. Убедитесь что выбранные модели доступны
3. Проверьте лимиты и баланс

## Получение API ключей

### OpenRouter.ai
1. Зарегистрируйтесь на https://openrouter.ai
2. Создайте API ключ в настройках
3. Пополните баланс или используйте бесплатные модели

### OpenAI
1. Зарегистрируйтесь на https://platform.openai.com
2. Создайте API ключ
3. Пополните баланс (~$5 достаточно на месяц)

### Fal.ai
1. Зарегистрируйтесь на https://fal.ai
2. Создайте API ключ
3. Пополните баланс

### VK API
1. Создайте приложение на https://vk.com/apps?act=manage
2. Получите токен доступа с правами на управление сообществом
3. Получите ID группы 