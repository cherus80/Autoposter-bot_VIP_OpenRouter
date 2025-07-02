# Развертывание Autoposter Bot на VPS через Portainer

## Подготовка к развертыванию

### 1. Обновление репозитория GitHub
Убедитесь, что все изменения загружены в ваш GitHub репозиторий:

```bash
git add .
git commit -m "Добавлена поддержка голосовых сообщений и Docker конфигурация"
git push origin main
```

### 2. Переменные окружения
Подготовьте следующие переменные окружения для настройки в Portainer:

```env
BOT_TOKEN=ваш_токен_telegram_бота
OPENROUTER_API_KEY=ваш_ключ_openrouter
OPENROUTER_POST_MODEL=deepseek/deepseek-r1:free
OPENROUTER_IMAGE_PROMPT_MODEL=deepseek/deepseek-r1:free
FAL_AI_KEY=ваш_ключ_fal_ai
VK_ACCESS_TOKEN=токен_доступа_vk
VK_GROUP_ID=id_группы_vk
CHANNEL_ID=id_telegram_канала
ADMIN_IDS=ваш_telegram_id
PROXY_URL=прокси_если_нужен
```

## Развертывание через Portainer

### Вариант 1: Через Git Repository (Рекомендуется)

1. **Войдите в Portainer**
   - Откройте веб-интерфейс Portainer
   - Выберите ваш Docker environment

2. **Создайте новый Stack**
   - Перейдите в "Stacks" → "Add stack"
   - Название: `autoposter-bot-v2`

3. **Настройте Git Repository**
   - Выберите "Repository" как источник
   - Repository URL: `https://github.com/ваш_username/ваш_репозиторий.git`
   - Reference: `refs/heads/main`
   - Compose path: `docker-compose.yml`

4. **Настройте Environment Variables**
   В разделе "Environment variables" добавьте:
   ```
   BOT_TOKEN=ваш_токен
   OPENROUTER_API_KEY=ваш_ключ_openrouter
   FAL_AI_KEY=ваш_ключ
   VK_ACCESS_TOKEN=ваш_токен
   VK_GROUP_ID=ваш_id
   CHANNEL_ID=ваш_канал
   ADMIN_IDS=ваш_id
   PROXY_URL=ваш_прокси
   ```

5. **Запустите Stack**
   - Нажмите "Deploy the stack"
   - Дождитесь завершения развертывания

### Вариант 2: Через Web Editor

1. **Создайте новый Stack**
   - Название: `autoposter-bot-v2`
   - Выберите "Web editor"

2. **Вставьте docker-compose.yml**
   Скопируйте содержимое файла `docker-compose.yml` в редактор

3. **Настройте переменные окружения** (как в варианте 1)

4. **Запустите Stack**

## Обновление существующего развертывания

### Если у вас уже запущена старая версия:

1. **Остановите старый контейнер**
   - В Portainer перейдите в "Containers"
   - Найдите старый контейнер бота
   - Остановите и удалите его

2. **Сохраните данные** (если нужно)
   - Скопируйте базу данных из старого контейнера
   - Сохраните настройки и резервные копии

3. **Разверните новую версию** по инструкции выше

## Мониторинг и управление

### Проверка логов
```bash
# В Portainer перейдите в:
Containers → autoposter-bot-v2 → Logs
```

### Проверка статуса
```bash
# Убедитесь что контейнер запущен:
Containers → autoposter-bot-v2 → Quick actions → Stats
```

### Перезапуск бота
```bash
# В случае проблем:
Containers → autoposter-bot-v2 → Quick actions → Restart
```

## Резервное копирование

Бот автоматически создает резервные копии в директории `/app/backups` внутри контейнера.
Данные сохраняются в именованном томе `bot_backups`.

### Доступ к резервным копиям:
1. В Portainer: Volumes → bot_backups → Browse
2. Скачайте нужные файлы через веб-интерфейс

## Обновление бота

### Автоматическое обновление через Git:
1. Загрузите изменения в GitHub репозиторий
2. В Portainer: Stacks → autoposter-bot-v2 → Editor
3. Нажмите "Pull and redeploy"

### Ручное обновление:
1. Остановите текущий stack
2. Обновите код в репозитории
3. Запустите stack заново

## Troubleshooting

### Проблемы с запуском:
- Проверьте логи контейнера
- Убедитесь в правильности переменных окружения
- Проверьте доступность внешних API (OpenRouter, Fal.ai, VK)

### Проблемы с базой данных:
- База данных создается автоматически при первом запуске
- Данные сохраняются в именованном томе `bot_data`

### Проблемы с голосовыми сообщениями:
- Убедитесь что в контейнере создана директория `/app/temp`
- Проверьте права доступа к временным файлам

## Особенности новой версии

### Новые возможности:
- ✅ Распознавание голосовых сообщений через OpenRouter
- ✅ Улучшенная система резервного копирования
- ✅ Исправлена обработка хэштегов
- ✅ Комплексная система тестирования
- ✅ Централизованная обработка ошибок

### Требования к ресурсам:
- **RAM**: минимум 512MB, рекомендуется 1GB
- **CPU**: 1 vCPU достаточно
- **Диск**: 2GB для системы + место для резервных копий
- **Сеть**: доступ к внешним API (OpenRouter, Fal.ai, VK, Telegram) 