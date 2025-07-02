"""
@file: services/openrouter_service.py
@description: Сервис для работы с OpenRouter.ai API с retry механизмом
@dependencies: config.py, utils/error_handler.py
@created: 2025-01-29
"""

from openai import OpenAI
import httpx
import logging
import asyncio
from typing import Dict, Any, Optional, List
from config import OPENROUTER_API_KEY, OPENROUTER_POST_MODEL, OPENROUTER_IMAGE_PROMPT_MODEL, PROXY_URL, OPENROUTER_MAX_RETRIES, OPENROUTER_RETRY_DELAYS
from utils.error_handler import handle_errors, ErrorSeverity, graceful_degradation

logger = logging.getLogger(__name__)

# Настройки retry механизма (из конфигурации)
MAX_RETRIES = OPENROUTER_MAX_RETRIES
RETRY_DELAYS = OPENROUTER_RETRY_DELAYS
RETRYABLE_ERRORS = [
    "Connection error",
    "Timeout",
    "HTTP 429",  # Rate limit
    "HTTP 502",  # Bad Gateway
    "HTTP 503",  # Service Unavailable
    "HTTP 504",  # Gateway Timeout
]

class OpenRouterService:
    """Сервис для работы с OpenRouter.ai API"""
    
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.post_model = OPENROUTER_POST_MODEL
        self.image_prompt_model = OPENROUTER_IMAGE_PROMPT_MODEL
        
        # Настройка клиента OpenRouter
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY не найден в конфигурации. OpenRouter сервис недоступен.")
            self.client = None
            return
        
        # Настройка HTTP клиента с прокси (если нужно)
        if PROXY_URL:
            http_client = httpx.Client(proxies=PROXY_URL)
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                http_client=http_client
            )
        else:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key
            )
        
        logger.info(f"OpenRouter сервис инициализирован с моделями: posts={self.post_model}, image_prompts={self.image_prompt_model}")

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Проверяет, является ли ошибка retryable
        
        Args:
            error: Исключение для проверки
            
        Returns:
            True если ошибку стоит повторить, False иначе
        """
        error_str = str(error).lower()
        
        # Проверяем специфичные retryable ошибки
        for retryable_error in RETRYABLE_ERRORS:
            if retryable_error.lower() in error_str:
                return True
        
        # Проверяем HTTPStatusError от httpx
        if hasattr(error, 'response'):
            status_code = error.response.status_code
            if status_code in [429, 502, 503, 504]:
                return True
        
        # Проверяем timeout ошибки
        if any(keyword in error_str for keyword in ['timeout', 'timed out', 'connection']):
            return True
            
        return False

    @handle_errors(context="OpenRouter API генерация", severity=ErrorSeverity.HIGH, fallback_return=None)
    async def generate_content(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 800,
        use_for_posts: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Генерирует контент через OpenRouter API с retry механизмом
        
        Args:
            messages: Список сообщений в формате [{"role": "user/system", "content": "..."}]
            model: Модель для использования (если None, выбирается автоматически)
            temperature: Температура генерации (0.0-2.0)
            max_tokens: Максимальное количество токенов
            use_for_posts: Если True, использует модель для постов, иначе для промптов изображений
        
        Returns:
            Словарь с результатом или None в случае ошибки
        """
        if not self.client:
            logger.error("OpenRouter клиент не инициализирован")
            return None
        
        # Выбираем модель автоматически если не указана
        if not model:
            model = self.post_model if use_for_posts else self.image_prompt_model
        
        last_error = None
        
        # Retry логика
        for attempt in range(MAX_RETRIES):
            try:
                if attempt > 0:
                    delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
                    logger.info(f"OpenRouter retry попытка {attempt + 1}/{MAX_RETRIES} через {delay} сек. для модели {model}")
                    await asyncio.sleep(delay)
                else:
                    logger.info(f"Отправка запроса в OpenRouter API: модель={model}, сообщений={len(messages)}")
                
                completion = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                # Преобразуем ответ в формат, совместимый с остальной системой
                result = {
                    "choices": [{
                        "message": {
                            "content": completion.choices[0].message.content
                        }
                    }],
                    "usage": {
                        "prompt_tokens": completion.usage.prompt_tokens if completion.usage else 0,
                        "completion_tokens": completion.usage.completion_tokens if completion.usage else 0,
                        "total_tokens": completion.usage.total_tokens if completion.usage else 0
                    },
                    "model": model
                }
                
                if attempt > 0:
                    logger.info(f"✅ OpenRouter API успешно ответил на попытке {attempt + 1}: модель={model}")
                else:
                    logger.info(f"Успешный ответ от OpenRouter API: модель={model}")
                return result
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                # Проверяем, стоит ли повторять запрос
                if attempt < MAX_RETRIES - 1 and self._is_retryable_error(e):
                    logger.warning(f"⚠️ OpenRouter API ошибка (попытка {attempt + 1}/{MAX_RETRIES}): {error_msg}")
                    continue
                else:
                    # Это последняя попытка или не retryable ошибка
                    if self._is_retryable_error(e):
                        logger.error(f"❌ OpenRouter API недоступен после {MAX_RETRIES} попыток: {error_msg}")
                    else:
                        logger.error(f"❌ OpenRouter API критическая ошибка: {error_msg}")
                    break
        
        # Если дошли до сюда, значит все попытки исчерпаны
        logger.error(f"Все {MAX_RETRIES} попытки обращения к OpenRouter API исчерпаны. Последняя ошибка: {last_error}")
        return None

    @graceful_degradation(fallback_function=None)
    async def generate_post(
        self,
        topic: str,
        system_prompt: str,
        model: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Генерирует пост через OpenRouter
        
        Args:
            topic: Тема поста
            system_prompt: Системный промпт с инструкциями
            model: Модель для использования (если None, использует OPENROUTER_POST_MODEL)
        
        Returns:
            Словарь с результатом генерации
        """
        # Формируем сообщения
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"""Напиши информативный пост для социальных сетей на тему: "{topic}"

СТРОГИЕ ТРЕБОВАНИЯ:
- Формат: HTML с тегами <b>, <i> для форматирования
- Длина: максимум 400-600 слов
- Стиль: дерзко, уверенно, без воды, сразу к результату
- Структура: строго следуй системному промпту
- НЕ добавляй заголовки типа "Заголовок:" или "Тема:"
- Используй ТОЛЬКО HTML теги <b> и <i>, НЕ используй ** или __

Тема: {topic}"""
            }
        ]
        
        result = await self.generate_content(
            messages=messages,
            model=model,
            temperature=0.7,
            max_tokens=800,
            use_for_posts=True
        )
        
        if not result:
            return None
        
        # Извлекаем данные из ответа
        choices = result.get("choices", [])
        if not choices:
            logger.error("OpenRouter API вернул пустой ответ")
            return None
        
        content = choices[0]["message"]["content"]
        
        # Валидация и исправление HTML тегов
        content = self._fix_html_tags(content)
        
        return {
            "text": content,
            "usage": result.get("usage", {}),
            "model": result.get("model", model or self.post_model)
        }

    @graceful_degradation(fallback_function=None)
    async def generate_image_prompt(
        self,
        post_text: str,
        model: str = None
    ) -> Optional[str]:
        """
        Генерирует промпт для изображения на основе текста поста
        
        Args:
            post_text: Текст поста
            model: Модель для использования (если None, использует OPENROUTER_IMAGE_PROMPT_MODEL)
        
        Returns:
            Промпт для генерации изображения или None в случае ошибки
        """
        messages = [
            {
                "role": "system",
                "content": """Ты эксперт по созданию промптов для генерации изображений. 
Проанализируй пост и создай краткий, но детальный промпт для создания изображения.

ТРЕБОВАНИЯ К ПРОМПТУ:
- Краткость: максимум 100-150 слов
- Детальность: конкретные визуальные элементы
- Стиль: профессиональный, современный
- Язык: английский для лучшей генерации
- Фокус: на ключевой идее поста

Верни ТОЛЬКО текст промпта без дополнительных объяснений."""
            },
            {
                "role": "user",
                "content": f"Создай промпт для изображения к этому посту:\n\n{post_text}"
            }
        ]
        
        result = await self.generate_content(
            messages=messages,
            model=model,
            temperature=0.5,
            max_tokens=200,
            use_for_posts=False
        )
        
        if not result:
            return None
        
        choices = result.get("choices", [])
        if not choices:
            return None
        
        prompt = choices[0]["message"]["content"].strip()
        logger.info(f"Сгенерирован промпт для изображения: {prompt[:50]}...")
        
        return prompt

    def _fix_html_tags(self, text: str) -> str:
        """Исправляет незакрытые HTML теги в тексте"""
        import re
        
        # Удаляем неподдерживаемые теги
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</?(?:p|div|span)[^>]*>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'</?(?:em|strong|h[1-6]|ul|ol|li)[^>]*>', '', text, flags=re.IGNORECASE)
        
        # Исправляем незакрытые теги <b> и <i>
        open_b = text.count('<b>') - text.count('</b>')
        if open_b > 0:
            text += '</b>' * open_b
        
        open_i = text.count('<i>') - text.count('</i>')
        if open_i > 0:
            text += '</i>' * open_i
        
        return text.strip()

    def get_available_models(self) -> Dict[str, str]:
        """Возвращает доступные модели OpenRouter"""
        return {
            # Бесплатные модели
            "deepseek/deepseek-r1:free": "DeepSeek R1 (Бесплатная)",
            "google/gemini-flash-1.5": "Google Gemini Flash 1.5",
            
            # Claude модели (Anthropic)
            "anthropic/claude-3.5-sonnet": "Claude 3.5 Sonnet",
            "anthropic/claude-3.7-sonnet": "Claude 3.7 Sonnet",
            "anthropic/claude-sonnet-4": "Claude Sonnet 4 (Новейшая)",
            "anthropic/claude-3-haiku": "Claude 3 Haiku (Быстрая)",
            
            # OpenAI модели
            "openai/gpt-3.5-turbo": "OpenAI GPT-3.5 Turbo",
            "openai/gpt-4": "OpenAI GPT-4",
            "openai/gpt-4o-mini": "OpenAI GPT-4o Mini",
            "openai/gpt-4o": "OpenAI GPT-4o",
            
            # Другие популярные модели
            "meta-llama/llama-3.1-70b-instruct": "Meta Llama 3.1 70B",
            "mistralai/mistral-7b-instruct": "Mistral 7B Instruct"
        }

    async def close(self):
        """Закрывает соединения"""
        if hasattr(self.client, 'close'):
            await self.client.close()

    def __del__(self):
        """Деструктор для очистки ресурсов"""
        pass 