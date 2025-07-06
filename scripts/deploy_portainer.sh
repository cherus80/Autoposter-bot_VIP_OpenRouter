#!/bin/bash

# ============================================================================
# Скрипт развертывания Autoposter Bot v2.1 через Portainer
# ============================================================================

set -e  # Остановка при ошибке

echo "🚀 Autoposter Bot v2.1 - Развертывание через Portainer"
echo "==========================================================="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка наличия docker и docker-compose
print_step "Проверка зависимостей..."

if ! command -v docker &> /dev/null; then
    print_error "Docker не установлен!"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose не установлен!"
    exit 1
fi

print_success "Docker и Docker Compose установлены"

# Проверка репозитория
print_step "Проверка GitHub репозитория..."

REPO_URL="https://github.com/cherus80/Autoposter-bot_VIP_OpenRouter.git"
if curl -s --head "$REPO_URL" | head -n 1 | grep -q "200 OK"; then
    print_success "Репозиторий доступен"
else
    print_warning "Не удается проверить доступность репозитория"
fi

# Подготовка переменных окружения
print_step "Настройка переменных окружения..."

cat << 'EOF'

📋 ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ для Portainer:

В Portainer Stack создайте следующие Environment Variables:

ОБЯЗАТЕЛЬНЫЕ:
-----------
BOT_TOKEN=ваш_telegram_bot_token
ADMIN_IDS=ваш_telegram_user_id  
CHANNEL_ID=id_вашего_канала
OPENROUTER_API_KEY=ваш_openrouter_api_key

РЕКОМЕНДУЕМЫЕ:
--------------
OPENROUTER_POST_MODEL=deepseek/deepseek-r1:free
OPENROUTER_IMAGE_PROMPT_MODEL=deepseek/deepseek-r1:free
OPENROUTER_MAX_RETRIES=5

ДОПОЛНИТЕЛЬНЫЕ (для полной функциональности):
--------------------------------------------
FAL_AI_KEY=ваш_fal_ai_key                    # Генерация изображений
OPENAI_API_KEY=ваш_openai_key               # Голосовые сообщения
VK_ACCESS_TOKEN=ваш_vk_token                # Публикация в VK
VK_GROUP_ID=id_vашей_vk_группы              # ID VK группы

EOF

print_warning "⚠️  Убедитесь, что все переменные настроены в Portainer!"

# Инструкции для Portainer
print_step "Инструкции для развертывания в Portainer..."

cat << 'EOF'

🔧 ИНСТРУКЦИЯ ПО РАЗВЕРТЫВАНИЮ:

1. Войдите в Portainer веб-интерфейс
2. Перейдите в Stacks → Add stack
3. Название стека: autoposter-bot-v2-1
4. Выберите источник: Repository
5. Repository URL: https://github.com/cherus80/Autoposter-bot_VIP_OpenRouter.git
6. Reference: refs/heads/main
7. Compose path: docker-compose.yml
8. Добавьте переменные окружения (см. выше)
9. Нажмите "Deploy the stack"

📊 МОНИТОРИНГ:

- Логи: Containers → autoposter-bot-v2-1 → Logs  
- Статус: Containers → autoposter-bot-v2-1 → Stats
- Перезапуск: Containers → autoposter-bot-v2-1 → Restart

🔄 ОБНОВЛЕНИЕ:

- Загрузите изменения в GitHub
- В Portainer: Stacks → autoposter-bot-v2-1 → Editor
- Нажмите "Pull and redeploy"

EOF

print_success "✅ Бот готов к развертыванию!"

# Генерация docker-compose.yml для ручного запуска (если нужно)
print_step "Создание локального docker-compose.yml..."

cat > docker-compose.local.yml << 'EOF'
version: '3.8'

services:
  autoposter-bot:
    image: autoposter-bot:latest
    build: .
    container_name: autoposter-bot-v2-1
    restart: unless-stopped
    
    environment:
      # Замените значения на реальные
      - BOT_TOKEN=${BOT_TOKEN:-your_bot_token_here}
      - ADMIN_IDS=${ADMIN_IDS:-your_admin_id_here}
      - CHANNEL_ID=${CHANNEL_ID:-your_channel_id_here}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-your_openrouter_key_here}
      - OPENROUTER_POST_MODEL=${OPENROUTER_POST_MODEL:-deepseek/deepseek-r1:free}
      - OPENROUTER_IMAGE_PROMPT_MODEL=${OPENROUTER_IMAGE_PROMPT_MODEL:-deepseek/deepseek-r1:free}
      - OPENROUTER_MAX_RETRIES=${OPENROUTER_MAX_RETRIES:-5}
      - FAL_AI_KEY=${FAL_AI_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - VK_ACCESS_TOKEN=${VK_ACCESS_TOKEN}
      - VK_GROUP_ID=${VK_GROUP_ID}
      - PYTHONUNBUFFERED=1
      - PYTHONPATH=/app
    
    volumes:
      - bot_database:/app/database
      - bot_backups:/app/backups
      - bot_temp:/app/temp
      - bot_logs:/app/logs
    
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  bot_database:
  bot_backups:
  bot_temp:
  bot_logs:
EOF

print_success "Создан docker-compose.local.yml для локального тестирования"

echo ""
print_success "🎉 ПОДГОТОВКА ЗАВЕРШЕНА!"
echo ""
print_warning "📝 Следующие шаги:"
echo "   1. Загрузите код в GitHub репозиторий"
echo "   2. Настройте переменные окружения в Portainer"  
echo "   3. Разверните Stack в Portainer по инструкции выше"
echo "   4. Проверьте логи и статус контейнера"
echo ""
print_success "✅ Бот готов к production развертыванию!" 