#!/bin/bash

# Скрипт быстрого развертывания Autoposter Bot
# Использование: ./scripts/deploy.sh

set -e

echo "🚀 Развертывание Autoposter Bot v2.0"
echo "=================================="

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    exit 1
fi

# Проверка docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен!"
    exit 1
fi

# Проверка .env файла
if [ ! -f .env ]; then
    echo "⚠️  Файл .env не найден!"
    echo "Создайте файл .env с необходимыми переменными окружения:"
    echo ""
    echo "BOT_TOKEN=ваш_токен"
    echo "OPENAI_API_KEY=ваш_ключ"
    echo "FAL_AI_KEY=ваш_ключ"
    echo "VK_ACCESS_TOKEN=ваш_токен"
    echo "VK_GROUP_ID=ваш_id"
    echo "CHANNEL_ID=ваш_канал"
    echo "ADMIN_IDS=ваш_id"
    echo "PROXY_URL=ваш_прокси"
    echo ""
    exit 1
fi

echo "✅ Предварительные проверки пройдены"

# Остановка старого контейнера (если есть)
echo "🛑 Остановка старых контейнеров..."
docker-compose down --remove-orphans || true

# Сборка нового образа
echo "🔨 Сборка Docker образа..."
docker-compose build --no-cache

# Запуск нового контейнера
echo "▶️  Запуск контейнера..."
docker-compose up -d

# Проверка статуса
echo "📊 Проверка статуса..."
sleep 5
docker-compose ps

# Показ логов
echo "📋 Последние логи:"
docker-compose logs --tail=20

echo ""
echo "✅ Развертывание завершено!"
echo "📋 Для просмотра логов: docker-compose logs -f"
echo "🛑 Для остановки: docker-compose down"
echo "🔄 Для перезапуска: docker-compose restart" 