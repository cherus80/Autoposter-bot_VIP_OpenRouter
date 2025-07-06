# 🤖 Autoposter Bot v2.1 - AI Content Master

> **Умный Telegram бот для автоматического создания и публикации постов в Telegram и VK с использованием ИИ**

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://docker.com)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-AI-green?logo=openai)](https://openrouter.ai)
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## ✨ Ключевые возможности

### 🤖 **AI-Генерация контента**
- Создание качественных постов через **OpenRouter.ai**
- Поддержка голосовых сообщений с **OpenAI Whisper**
- Генерация изображений через **Fal.ai** с fallback защитой
- Умные промпты с контекстом и стилизацией

### 📱 **Мультиплатформенная публикация**  
- **Telegram каналы** - основная платформа
- **VK группы** - дополнительная аудитория
- Graceful degradation при отсутствии токенов
- Кастомизируемые призывы к действию

### ⚙️ **Автоматизация и планирование**
- Автопостинг по расписанию
- Интеллектуальный контент-план
- Резервное копирование данных
- Система мониторинга и уведомлений

### 🛡️ **Надёжность и безопасность**
- Устойчивость к сбоям API с retry механизмом
- Comprehensive error handling
- Docker контейнеризация
- Health checks и автоперезапуск

## 🚀 Быстрый старт

### 📋 Требования
- **Docker** и **Docker Compose**
- **Portainer** (для удобного управления)
- API ключи (минимум: Telegram Bot + OpenRouter)

### 🔧 Развертывание через Portainer

1. **Клонируйте репозиторий в Portainer:**
   ```
   Repository URL: https://github.com/cherus80/Autoposter-bot_VIP_OpenRouter.git
   Compose path: docker-compose.yml
   ```

2. **Настройте обязательные переменные:**
   ```env
   BOT_TOKEN=ваш_telegram_bot_token
   ADMIN_IDS=ваш_telegram_user_id
   CHANNEL_ID=id_вашего_канала  
   OPENROUTER_API_KEY=ваш_openrouter_api_key
   ```

3. **Разверните Stack** и проверьте логи!

> 📚 **Подробная инструкция:** [DEPLOYMENT.md](DEPLOYMENT.md)  
> 🛠️ **Автоматический скрипт:** `bash scripts/deploy_portainer.sh`

## 🔑 Конфигурация API сервисов

### 🤖 **OpenRouter.ai** (обязательно)
```env
OPENROUTER_API_KEY=your_key_here
OPENROUTER_POST_MODEL=deepseek/deepseek-r1:free      # Бесплатная модель!
OPENROUTER_IMAGE_PROMPT_MODEL=deepseek/deepseek-r1:free
```

### 🖼️ **Fal.ai** (для изображений)
```env
FAL_AI_KEY=your_fal_ai_key
```

### 🎤 **OpenAI** (для голосовых сообщений)
```env
OPENAI_API_KEY=your_openai_key
```

### 📱 **VK API** (для публикации в VK)
```env
VK_ACCESS_TOKEN=your_vk_token
VK_GROUP_ID=your_vk_group_id
```

> 💡 **Бот работает в минимальной конфигурации** с только Telegram + OpenRouter!

## 📊 Архитектура и функциональность

### 🏗️ **Модульная архитектура**
```
├── 🤖 AI Services (OpenRouter, OpenAI, Fal.ai)
├── 📱 Platform Managers (Telegram, VK)  
├── 📋 Content Planning & Scheduling
├── 💾 Database & Backup System
├── 🔧 Configuration & Error Handling
└── 🧪 Comprehensive Testing Suite
```

### 📈 **Возможности управления контентом**
- **Ручное создание** постов с пользовательскими темами
- **Автоматический контент-план** с различными категориями
- **Гибкие настройки стилей** изображений (anime, digital_art, fantasy, etc.)
- **Graceful degradation** - работа даже при недоступности некоторых API

### 🎛️ **Интерфейс управления**
- Интуитивное Telegram меню
- Статистика публикаций
- Настройки промптов и стилей
- Система резервного копирования
- Мониторинг состояния сервисов

## 🛠️ Последние обновления (v2.1)

### ✅ **Критические исправления (07.07.2025)**
- 🛠️ **ИСПРАВЛЕНА генерация изображений**: Fallback промпты корректно передаются в fal.ai
- 🚫 **УСТРАНЕНА ошибка Telegram**: "wrong remote file identifier specified"
- 🔧 **Улучшена логика обработки**: Правильное выполнение fallback сценариев

### 🚀 **Новые возможности**
- ✅ Поддержка голосовых сообщений через OpenAI Whisper
- ✅ Генерация изображений с улучшенной стабильностью
- ✅ Централизованная система обработки ошибок
- ✅ Graceful degradation для всех API сервисов
- ✅ Улучшенные Docker конфигурации для production

## 📖 Документация

| Документ | Описание |
|----------|----------|
| [📋 DEPLOYMENT.md](DEPLOYMENT.md) | Инструкции по развертыванию |
| [🔧 Environment Guide](docs/Environment_Variables_Guide.md) | Настройка переменных окружения |
| [📊 Troubleshooting](docs/Troubleshooting.md) | Решение проблем |
| [📝 Development Diary](docs/Diary.md) | Журнал разработки |
| [✅ Task Tracker](docs/Tasktracker.md) | Трекер задач |

## 🧪 Тестирование

Проект включает comprehensive test suite:
```bash
# Запуск всех тестов
python -m pytest tests/ -v

# Тесты с покрытием
python tests/run_tests.py
```

**Test Coverage:** 33%+ с автоматическими отчетами

## 🤝 Поддержка

### 🐛 **Сообщение об ошибках**
Создайте issue с детальным описанием проблемы

### 💡 **Предложения**
Мы открыты для улучшений и новых идей!

### 📧 **Контакты**
- GitHub: [@cherus80](https://github.com/cherus80)
- Repository: [Autoposter-bot_VIP_OpenRouter](https://github.com/cherus80/Autoposter-bot_VIP_OpenRouter)

## 📄 Лицензия

MIT License - используйте свободно для личных и коммерческих проектов.

---

⭐ **Поставьте звезду, если проект был полезен!** 