# Используем официальный Python образ
FROM python:3.12-slim

# Аргумент для принудительной пересборки (используется в docker-compose.yml)
ARG REBUILD_CACHE
LABEL rebuild_cache=${REBUILD_CACHE}

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

# Копируем весь код приложения
COPY . .

# Создаем необходимые директории
RUN mkdir -p temp backups data logs database

# Устанавливаем права доступа
RUN chmod +x bot.py

# Создаем пользователя для безопасности  
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Проверяем структуру проекта
RUN ls -la /app/

# Метка версии для отслеживания
LABEL version="v2.1-fixes"
LABEL description="Autoposter Bot with prompt fixes and web preview disabled"

# Открываем порт (если потребуется для webhook)
EXPOSE 8000

# Команда для запуска бота
CMD ["python", "bot.py"] 