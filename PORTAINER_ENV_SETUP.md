# Настройка переменных окружения в Portainer

## Обязательные переменные

В Portainer при создании или редактировании стека нужно настроить следующие переменные окружения:

### 1. Telegram Bot
```
BOT_TOKEN=ваш_токен_бота_от_BotFather
```

### 2. Администраторы (КРИТИЧЕСКИ ВАЖНО!)
```
ADMIN_IDS=252006447
```
**ВАЖНО**: Замените `252006447` на ваш реальный Telegram User ID!

Для получения вашего User ID:
1. Напишите боту @userinfobot в Telegram
2. Он пришлет ваш ID
3. Используйте этот ID в переменной ADMIN_IDS

Для нескольких администраторов используйте запятую:
```
ADMIN_IDS=252006447,123456789,987654321
```

### 3. OpenRouter.ai API (для генерации контента)
```
OPENROUTER_API_KEY=ваш_ключ_openrouter
```

### 4. Модели OpenRouter (опционально)
```
OPENROUTER_POST_MODEL=deepseek/deepseek-r1:free
OPENROUTER_IMAGE_PROMPT_MODEL=deepseek/deepseek-r1:free
```

### 5. Fal.ai (для генерации изображений)
```
FAL_AI_KEY=ваш_ключ_fal_ai
```

### 6. Telegram канал
```
CHANNEL_ID=-1001234567890
```

## Опциональные переменные

### VK (если планируете публикацию в VK)
```
VK_ACCESS_TOKEN=ваш_токен_vk
VK_GROUP_ID=-123456789
```

### Прокси (если нужен)
```
PROXY_URL=socks5://user:pass@host:port
```

## Как настроить в Portainer

1. Зайдите в Portainer
2. Перейдите в Stacks → ваш стек (autoposter-bot)
3. Нажмите "Editor"
4. Прокрутите вниз до секции "Environment variables"
5. Добавьте все необходимые переменные
6. Нажмите "Update the stack"

## Проверка настройки

После обновления стека проверьте логи контейнера. Вы должны увидеть:
```
DEBUG: ADMIN_IDS env var = '252006447'
DEBUG: Итоговый ADMIN_IDS = [252006447]
```

Если видите `ADMIN_IDS = []`, значит переменная не передается в контейнер.

## Устранение проблем

Если бот говорит "нет доступа":
1. Проверьте, что ADMIN_IDS правильно настроена в Portainer
2. Убедитесь, что используете правильный User ID
3. Перезапустите стек после изменения переменных
4. Проверьте логи на наличие DEBUG сообщений 