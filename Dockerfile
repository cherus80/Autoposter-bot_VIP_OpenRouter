# Используем официальный Python образ
FROM python:3.12-slim

# Аргумент для принудительной пересборки (используется в docker-compose.yml)
ARG REBUILD_CACHE
LABEL rebuild_cache=${REBUILD_CACHE}

# Объявляем переменные окружения
ENV BOT_TOKEN=""
ENV ADMIN_IDS=""
ENV CHANNEL_ID=""
ENV OPENROUTER_API_KEY=""
ENV OPENROUTER_POST_MODEL="anthropic/claude-3-opus-20240229"
ENV OPENROUTER_MAX_RETRIES="5"
ENV FAL_AI_KEY=""
ENV VK_ACCESS_TOKEN=""
ENV VK_GROUP_ID=""
ENV VK_CTA_TEXT="🔔 Подписывайтесь на нашу группу!"
ENV PROXY_URL=""
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаем необходимые директории
RUN mkdir -p temp backups data logs database

# Копируем весь код приложения
COPY . .

# Устанавливаем права доступа
RUN chmod +x bot.py

# Создаем пользователя для безопасности  
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app && \
    chmod -R 755 /app

USER botuser

# Проверяем структуру проекта
RUN ls -la /app/

# Метка версии для отслеживания
LABEL version="v2.1-fixes"
LABEL description="Autoposter Bot with OpenRouter.ai integration and improved security"

# Открываем порт (если потребуется для webhook)
EXPOSE 8000

# Команда для запуска бота
CMD ["python", "bot.py"] 