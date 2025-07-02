# Руководство по устранению неполадок

## 🚨 Автопостинг не работает

### Симптомы
- В логах видны сообщения "Следующая публикация через X мин."
- Но фактические публикации не происходят
- Нет сообщений "Время публикации! Запускаю auto_post_cycle…"

### Быстрое решение

#### 1. Диагностика проблемы
```bash
python debug_autoposting.py
```

Этот скрипт покажет:
- ✅ Что работает правильно
- ❌ Какие проблемы обнаружены
- 📊 Полную информацию о состоянии системы

#### 2. Автоматическое исправление
```bash
python fix_autoposting.py
```

Скрипт автоматически:
- Включит автопостинг
- Настроит интервал публикации
- Активирует публикацию в Telegram
- Включит изображения для автопостов

#### 3. Перезапуск бота (если нужно)
```bash
# В Docker
docker-compose restart
# Или только бот
docker-compose restart bot
```

### Частые причины проблем

#### ❌ Автопостинг выключен
**Проблема:** `auto_mode_status: off` или `auto_posting_enabled: 0`

**Решение:**
```python
await update_setting('auto_mode_status', 'on')
await update_setting('auto_posting_enabled', '1')
```

#### ❌ Не настроены платформы публикации
**Проблема:** `publish_to_tg: False` и `publish_to_vk: False`

**Решение:** Включить хотя бы одну платформу через бота или вручную:
```python
publishing_manager = PublishingManager()
await publishing_manager.update_settings(
    user_id=int(ADMIN_ID),
    publish_to_tg=True
)
```

#### ❌ Пустой контент-план
**Проблема:** Нет неиспользованных тем для публикации

**Решение:** Загрузить новые темы через меню "Контент-план"

#### ❌ Отсутствуют промпты
**Проблема:** Не настроен промпт для генерации контента

**Решение:** Настроить промпты через меню "Промпты"

### Ручная проверка настроек

#### Проверка базы данных
```python
from database.settings_db import get_setting

# Проверяем основные настройки
auto_mode = await get_setting("auto_mode_status", "off")
auto_enabled = await get_setting("auto_posting_enabled", "0")
interval = await get_setting("post_interval_minutes", "240")

print(f"Автопостинг: {auto_mode}")
print(f"Активен: {auto_enabled}")
print(f"Интервал: {interval} мин")
```

#### Проверка последнего поста
```python
from database.posts_db import get_last_post_time
from datetime import datetime, timedelta

last_time = await get_last_post_time()
if last_time:
    interval_min = int(await get_setting("post_interval_minutes", "240"))
    next_time = last_time + timedelta(minutes=interval_min)
    now = datetime.now()
    
    if next_time <= now:
        print("⚠️ Готов к публикации!")
    else:
        diff = next_time - now
        print(f"⏰ До публикации: {diff}")
```

### Логи для мониторинга

#### Успешная работа автопостинга:
```
INFO:root:Следующая публикация через X.X мин.
INFO:root:Время публикации! Запускаю auto_post_cycle…
INFO:[Auto-Post] Новый цикл.
INFO:[Auto-Post] Проверяем контент-план...
INFO:[Auto-Post] Найдена тема: ID=X, theme='...', category='...'
INFO:[Auto-Post] Генерируем пост для темы: ...
INFO:[Publisher] Начало публикации поста на тему: ...
INFO:[Publisher] Пост опубликован в Telegram.
```

#### Проблемы:
- Нет сообщения "Время публикации!" → проблема с расчетом времени
- Нет сообщения "Новый цикл" → не запускается auto_post_cycle
- Ошибки генерации → проблемы с AI сервисом или промптами
- Ошибки публикации → проблемы с токенами или настройками платформ

### Экстренное восстановление

Если ничего не помогает:

1. **Сбросить все настройки автопостинга:**
```python
await update_setting('auto_mode_status', 'off')
await update_setting('auto_posting_enabled', '0')
# Подождать 1 минуту
await update_setting('auto_mode_status', 'on')
await update_setting('auto_posting_enabled', '1')
```

2. **Перезапустить планировщик:**
```bash
docker-compose restart
```

3. **Проверить логи после перезапуска:**
```bash
docker-compose logs -f --tail=50
```

## 🔧 Другие проблемы

### База данных заблокирована
```bash
# Проверить процессы
ps aux | grep python
# Остановить все
docker-compose down
# Запустить заново
docker-compose up -d
```

### Ошибки AI сервиса
- Проверить токены API в переменных окружения
- Проверить лимиты запросов
- Проверить настройки модели OpenRouter в .env файле

### Проблемы с VK
- Проверить токен VK API
- Проверить права доступа к группе
- VK может временно блокировать частые запросы 