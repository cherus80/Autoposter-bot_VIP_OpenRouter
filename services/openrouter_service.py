"""
@file: services/openrouter_service.py
@description: Сервис для работы с OpenRouter.ai API с retry механизмом (HTTP версия)
@dependencies: config.py, utils/error_handler.py
@created: 2025-01-30
"""

import httpx
import json
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
    """Сервис для работы с OpenRouter.ai API через прямые HTTP запросы"""
    
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.post_model = OPENROUTER_POST_MODEL
        self.image_prompt_model = OPENROUTER_IMAGE_PROMPT_MODEL
        self.base_url = "https://openrouter.ai/api/v1"
        
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY не найден в конфигурации. OpenRouter сервис недоступен.")
            self.client = None
            return
        
        # Определяем заголовки для всех запросов
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/openrouter/autoposter-bot",
            "X-Title": "Autoposter Bot"
        }
        
        # Настройка HTTP клиента
        if PROXY_URL:
            self.client = httpx.AsyncClient(proxies=PROXY_URL, timeout=30.0)
        else:
            self.client = httpx.AsyncClient(timeout=30.0)
        
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
        
        # Подготавливаем данные для запроса
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
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
                
                # Отправляем POST запрос
                response = await self.client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload
                )
                
                # Проверяем статус ответа
                if response.status_code == 200:
                    result = response.json()
                    
                    if attempt > 0:
                        logger.info(f"✅ OpenRouter API успешно ответил на попытке {attempt + 1}: модель={model}")
                    else:
                        logger.info(f"Успешный ответ от OpenRouter API: модель={model}")
                    
                    return result
                else:
                    # Ошибка HTTP
                    error_text = response.text
                    error_msg = f"HTTP {response.status_code}: {error_text}"
                    
                    if response.status_code == 401:
                        logger.error(f"❌ OpenRouter API: Ошибка аутентификации (401)")
                        logger.error(f"Используемый API ключ: {self.api_key[:15]}...")
                        logger.error(f"Заголовки: {self.headers}")
                        logger.error(f"Ответ сервера: {error_text}")
                        # Не повторяем при ошибках аутентификации
                        break
                    
                    raise Exception(error_msg)
                
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
                "content": f"Создай пост на тему: {topic}"
            }
        ]
        
        return await self.generate_content(
            messages=messages,
            model=model,
            use_for_posts=True
        )

    @graceful_degradation(fallback_function=None)
    async def generate_image_prompt(
        self,
        post_text: str,
        model: str = None
    ) -> Optional[str]:
        """
        Генерирует промпт для изображения на основе текста поста
        
        Args:
            post_text: Текст поста для которого нужно создать промпт
            model: Модель для использования (если None, использует OPENROUTER_IMAGE_PROMPT_MODEL)
        
        Returns:
            Строка с промптом для изображения или None в случае ошибки
        """
        # Системный промпт для генерации промптов изображений
        system_prompt = """Ты генератор промптов для создания изображений. Создавай краткие и понятные промпты на английском языке для генерации изображений, которые соответствуют теме поста. 

Промпт должен быть:
- На английском языке
- Конкретным и описательным
- Без упоминания текста или слов на изображении
- Фокусированным на визуальных элементах

Отвечай только промптом, без дополнительных пояснений."""

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"Создай промпт для изображения к этому посту:\n\n{post_text}"
            }
        ]
        
        result = await self.generate_content(
            messages=messages,
            model=model,
            use_for_posts=False,
            max_tokens=200,
            temperature=0.8
        )
        
        if result and result.get("choices"):
            content = result["choices"][0]["message"]["content"]
            return self._fix_html_tags(content.strip())
        
        return None

    def _fix_html_tags(self, text: str) -> str:
        """
        Убирает HTML теги из текста
        
        Args:
            text: Исходный текст
            
        Returns:
            Текст без HTML тегов
        """
        import re
        # Убираем HTML теги
        clean_text = re.sub(r'<[^>]+>', '', text)
        return clean_text.strip()

    def get_available_models(self) -> Dict[str, str]:
        """
        Возвращает словарь доступных моделей
        
        Returns:
            Словарь с моделями {название: описание}
        """
        return {
            "deepseek/deepseek-r1:free": "DeepSeek R1 (бесплатная)",
            "openai/gpt-4o-mini-2024-07-18": "GPT-4o Mini (платная)",
            "anthropic/claude-sonnet-4": "Claude Sonnet 4 (платная)",
            "mistralai/mistral-nemo:free": "Mistral Nemo (бесплатная)",
            "google/gemma-2-9b-it:free": "Google Gemma 2 9B (бесплатная)"
        }

    async def close(self):
        """Закрывает HTTP клиент"""
        if self.client:
            await self.client.aclose()

    def __del__(self):
        """Деструктор для закрытия клиента"""
        if hasattr(self, 'client') and self.client:
            # В деструкторе просто помечаем для закрытия
            pass 