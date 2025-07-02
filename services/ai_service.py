# services/ai_service.py - Сервис работы с ИИ через OpenRouter.ai
import fal_client
import openai
from config import OPENROUTER_API_KEY, OPENROUTER_POST_MODEL, OPENROUTER_IMAGE_PROMPT_MODEL, PROXY_URL, FAL_AI_KEY, OPENAI_API_KEY
import logging
import json
import random
import re
from managers.prompt_manager import PromptManager
from services.image_service import ImageService
from services.openrouter_service import OpenRouterService
from templates.style_examples import get_style_examples_text
from utils.error_handler import APIWrapper, ErrorSeverity, graceful_degradation, handle_errors

def clean_post_text(text: str) -> str:
    """Удаляет из начала текста 'Заголовок: ...' и подобные конструкции, а также очищает неподдерживаемые HTML теги."""
    # Удаляем 'Заголовок: "..."' или 'Тема: "..."' в начале строки, игнорируя регистр
    text = re.sub(r'^(?:Заголовок|Тема|Title):?\s*["«]?(.*?["»]?\n+)', '', text.strip(), flags=re.IGNORECASE)
    # Удаляем просто 'Заголовок: ' или 'Тема: ', если они в начале
    text = re.sub(r'^(?:Заголовок|Тема|Title):?\s*', '', text.strip(), flags=re.IGNORECASE)
    
    # Заменяем неподдерживаемые HTML теги на допустимые или убираем их
    # <br> -> перенос строки (Telegram не поддерживает <br>)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    
    # Убираем неподдерживаемые теги: <p>, <div>, <span> и их содержимое остается
    text = re.sub(r'</?(?:p|div|span)[^>]*>', '', text, flags=re.IGNORECASE)
    
    # Убираем другие неподдерживаемые теги но оставляем содержимое
    text = re.sub(r'</?(?:em|strong|h[1-6]|ul|ol|li)[^>]*>', '', text, flags=re.IGNORECASE)
    
    return text.strip()

# Промпт по умолчанию, если в БД ничего нет
DEFAULT_VISUAL_PROMPT = """
Проанализируй пост и извлеки элементы для создания СЦЕНЫ с персонажем.

Верни JSON с полями:
- "main_action": конкретное действие ("debugging Python code", "configuring API", "testing bot automation")
- "environment": детальная обстановка ("late night coding setup", "modern home office with multiple monitors", "professional workspace")
- "objects": специфичные предметы (["MacBook Pro", "external 4K monitors", "mechanical keyboard", "coffee mug", "notebook with sketches"])
- "mood": эмоциональное состояние ("intensely focused", "problem-solving mode", "breakthrough moment", "frustrated debugging")
- "tech_context": технические детали (["Python code on screen", "API documentation", "bot interface", "terminal windows", "GitHub repository"])
- "lighting": атмосфера освещения ("blue screen glow with warm desk lamp", "late night coding ambiance", "focused task lighting")
- "composition": ракурс кадра ("over shoulder view of screens", "three-quarter profile working", "side angle coding")
- "story_moment": ключевой момент ("debugging session", "successful API integration", "bot deployment", "code review")
"""

class AIService:
    def __init__(self):
        # Инициализируем OpenRouter сервис
        self.openrouter_service = OpenRouterService()
        self.image_service = ImageService()
        self.prompt_manager = PromptManager()
        
        # Модели для разных задач
        self.post_model = OPENROUTER_POST_MODEL
        self.image_prompt_model = OPENROUTER_IMAGE_PROMPT_MODEL
        
        # Инициализируем OpenAI клиент для транскрипции (если ключ доступен)
        self.openai_client = None
        if OPENAI_API_KEY:
            self.openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
            logging.info("OpenAI клиент инициализирован для транскрипции")
        else:
            logging.warning("OPENAI_API_KEY не найден в конфигурации. Транскрипция голосовых сообщений будет недоступна.")
        
        # fal-client автоматически использует переменную окружения FAL_KEY,
        # дополнительная конфигурация не требуется.
        if not FAL_AI_KEY:
            logging.warning("FAL_AI_KEY не найден в конфигурации. Генерация изображений будет недоступна.")
        
        # Проверяем доступность OpenRouter
        if not OPENROUTER_API_KEY:
            logging.warning("OPENROUTER_API_KEY не найден в конфигурации. AI функции будут недоступны.")
        
        logging.info(f"AIService инициализирован с моделями: posts={self.post_model}, image_prompts={self.image_prompt_model}")
    
    def get_available_models(self) -> dict:
        """Возвращает доступные модели OpenRouter"""
        return self.openrouter_service.get_available_models() if self.openrouter_service.client else {}
    
    @handle_errors(context="Генерация поста", severity=ErrorSeverity.HIGH, fallback_return=None)
    async def generate_post(self, topic: str = None, custom_prompt: str = None, with_image: bool = False, image_style: str = None, system_prompt: str | None = None, model: str = None):
        """
        Генерирует пост через OpenRouter. Может использовать тему или кастомный промпт.
        Если with_image=True, генерирует и изображение.
        """
        image_url = None

        # 1. Генерация текста поста
        
        # Определяем системный промпт. Приоритет у кастомного, если он передан.
        system_prompt = system_prompt or custom_prompt or await self.prompt_manager.get_prompt('content_generation')

        # Если системного промпта все еще нет, используем дефолтный
        if not system_prompt:
            logging.error("System prompt for content is not set. Using a default one.")
            system_prompt = """Ты эксперт и блогер по AI и автоматизации. Пиши ТОЛЬКО по-русски посты для подписчиков Telegram-канала про AI от первого лица.

КРИТИЧЕСКИ ВАЖНО! Строго соблюдай структуру:

ОБЯЗАТЕЛЬНАЯ СТРУКТУРА:
1. <b>Конкретный результат/цифра: краткое описание</b>
2. Пустая строка
3. 🎯 Эмодзи + первый абзац (1-2 предложения)
4. 🚀 Эмодзи + второй абзац (1-2 предложения)  
5. 📊 Эмодзи + третий абзац с цифрами (1-2 предложения)
6. 💡 Эмодзи + четвертый абзац (1-2 предложения)
7. ⚡ Эмодзи + пятый абзац (1-2 предложения)
8. 🔥 Эмодзи + шестой абзац (1-2 предложения)
9. Пустая строка
10. Призыв к действию с подпиской на канал (указать полную ссылку типа https://t.me/+abc123)
11. Пустая строка
12. 3-5 хэштегов через пробел

ФОРМАТИРОВАНИЕ БЕЗ ИСКЛЮЧЕНИЙ:
• ТОЛЬКО HTML-теги: <b></b> и <i></i>
• НИКАКИХ ** или __ символов!
• Цифры и ключевые термины ВСЕГДА в <b></b>
• Инструменты/технологии в <i></i>
• Один эмодзи в начале каждого абзаца

HTML ТЕГИ - КРИТИЧЕСКИ ВАЖНО:
✅ РАЗРЕШЕНО ИСПОЛЬЗОВАТЬ:
• <b>текст</b> - для жирного шрифта
• <i>текст</i> - для курсива

❌ СТРОГО ЗАПРЕЩЕНО ИСПОЛЬЗОВАТЬ:
• <br> или <br/> - НЕ используй для переносов строк! Используй обычные переносы
• <p>, </p> - НЕ используй абзацы
• <div>, </div> - НЕ используй блоки
• <span>, </span> - НЕ используй инлайн элементы  
• <em>, </em> - НЕ используй вместо <i>
• <strong>, </strong> - НЕ используй вместо <b>
• <h1>, <h2>, <h3>, <h4>, <h5>, <h6> - НЕ используй заголовки
• <ul>, <ol>, <li> - НЕ используй списки
• Любые другие HTML теги кроме <b> и <i>

ОБЯЗАТЕЛЬНЫЕ ЭЛЕМЕНТЫ:
• Конкретные цифры в каждом посте
• Временные рамки ("за 3 недели", "месяц назад")
• Названия инструментов/технологий
• Сравнения "до/после"
• Личный опыт от первого лица

ЗАПРЕЩЕНО:
• Вводные фразы "честно говоря", "по опыту"
• Водянистые обобщения
• Символы ** или __
• Заголовки типа "Заголовок:" или "Тема:"

СТИЛЬ: дерзко, уверенно, без воды, сразу к результату. Пиши как успешный эксперт, который делится конкретными достижениями."""
        
        # Объединяем системный промпт с дополнительными примерами стилей
        enhanced_system_prompt = system_prompt + "\n\n" + get_style_examples_text()
        
        logging.info(f"Генерация текста поста через OpenRouter: модель={model or self.post_model}, тема='{topic}'")
        
        # Генерируем пост через OpenRouter
        try:
            result = await self.openrouter_service.generate_post(
                topic=topic or "интересная тема",
                system_prompt=enhanced_system_prompt,
                model=model
            )
            
            if not result:
                raise Exception("OpenRouter не вернул результат")
            
            final_text = result["text"]
            logging.info(f"Сгенерирован текст через OpenRouter: {final_text[:100]}...")
            
        except Exception as e:
            logging.error(f"Ошибка при генерации текста поста через OpenRouter: {e}")
            raise Exception(f"Не удалось сгенерировать текст поста: {e}")

        # 2. Генерация изображения (если требуется)
        if with_image:
            image_url = await self._generate_image_with_fallback(final_text, image_style)

        return {"text": final_text, "image_url": image_url}

    # Старые методы, связанные с AI провайдерами, больше не нужны

    @graceful_degradation(fallback_function=None)
    async def _generate_image_with_fallback(self, post_text: str, image_style: str = None) -> str | None:
        """
        Вспомогательный метод для генерации изображений с graceful degradation
        """
        logging.info("Начинается генерация изображения...")
        image_prompt_template = await self.prompt_manager.get_prompt('image')
        if not image_prompt_template:
            logging.warning("Промпт для изображения не установлен, но запрошена генерация. Генерация изображения пропускается.")
            return None

        # Формируем сообщение для OpenAI для генерации промпта для Fal.ai
        prompt_for_fal_generator = image_prompt_template.replace("{post_text}", post_text)

        system_prompt_for_image = (
            "You are an assistant that creates prompts for an AI artist (like Fal.ai or Midjourney). "
            "Your task is to create a concise but detailed prompt in English based on the provided text and instructions "
            "to generate a beautiful and relevant image. The prompt should be no longer than 100 words."
        )

        logging.info("Используется пользовательский ШАБЛОН промпта для генерации промпта изображения...")
        
        # Генерация промпта для изображения через OpenRouter
        try:
            logging.info("Генерация промпта изображения через OpenRouter")
            
            messages = [
                    {
                        "role": "system", 
                        "content": system_prompt_for_image
                    },
                    {
                        "role": "user", 
                        "content": prompt_for_fal_generator
                    }
                ]
                
            result = await self.openrouter_service.generate_content(
                messages=messages,
                model=None,  # Используем модель для промптов изображений
                temperature=0.7,
                max_tokens=200,
                use_for_posts=False  # Используем модель для промптов изображений
            )
                
            if result and result.get("choices"):
                response_content = result["choices"][0]["message"]["content"]
                logging.info("Промпт изображения сгенерирован через OpenRouter")
                response = type('obj', (object,), {
                    'choices': [type('obj', (object,), {
                        'message': type('obj', (object,), {'content': response_content})()
                    })()]
                })()
            else:
                response = None
                
        except Exception as e:
            logging.error(f"Ошибка при генерации промпта изображения через OpenRouter: {e}")
            response = None
        
        if not response:
            logging.warning("Не удалось сгенерировать промпт для изображения")
            return None
            
        image_prompt_for_fal = response.choices[0].message.content
        
        # Добавляем стиль к готовому промпту, если он указан
        if image_style and image_style != "none":
            logging.info(f"Добавляется стиль изображения: {image_style}")
            image_prompt_for_fal += f", in the style of {image_style}"
        else:
            logging.info("Стиль изображения не указан или 'none'.")
        
        logging.info(f"Финальный промпт для fal.ai: {image_prompt_for_fal[:100]}...")
        
        # Безопасная генерация изображения
        logging.info(f"Отправка запроса в fal.ai с промптом: {image_prompt_for_fal[:70]}...")
        try:
            image_url = await self.image_service.generate_post_image(image_prompt_for_fal)
        except Exception as e:
            logging.error(f"Ошибка генерации изображения: {e}")
            image_url = None
        
        if image_url:
            logging.info("Ответ от fal.ai получен.")
        else:
            logging.warning("Не удалось сгенерировать изображение")
            
        return image_url
    
    async def generate_post_from_plan(self, system_prompt: str, content_plan_topic, with_image: bool = False, image_style: str = None):
        """
        Генерирует пост, используя системный промпт и данные из контент-плана.
        Создает развернутые и качественные посты.
        Использует интеллектуальное переключение между AI провайдерами.
        """
        # Проверяем что system_prompt не None
        if not system_prompt:
            logging.error("System prompt не найден в базе данных!")
            raise Exception("System prompt для генерации контента не настроен. Пожалуйста, настройте промпт через меню бота.")
        
        # Заполняем плейсхолдеры в системном промпте
        final_system_prompt = system_prompt.format(
            category=getattr(content_plan_topic, 'category', ''),
            theme=getattr(content_plan_topic, 'theme', ''),
            topic=getattr(content_plan_topic, 'theme', ''),  # Добавляем topic как алиас для theme
            post_description=getattr(content_plan_topic, 'post_description', '')
        )
        
        # Убираем ограничения на длину - пусть промпт сам контролирует качество
        if with_image:
            # Для постов с изображением - умеренная длина
            length_prompt = "Важно: Пост должен быть содержательным и интересным (350-450 слов). Текст должен дополнять изображение и привлекать внимание."
        else:
            # Для постов без изображения - развернутый контент  
            length_prompt = "Важно: Пост должен быть подробным и самодостаточным (500-600 слов). Раскрой тему полностью, добавь личный опыт и практические советы."
        
        # Добавляем инструкцию по длине
        final_system_prompt += f"\\n\\n{length_prompt}"
        
        # Используем основной метод generate_post для генерации
        try:
            result = await self.generate_post(
                topic=getattr(content_plan_topic, 'theme', ''),
                custom_prompt=None,
                with_image=with_image,
                image_style=image_style,
                system_prompt=final_system_prompt
            )
            
            # Очищаем текст от заголовков
            cleaned_content = clean_post_text(result["text"])
            
            # Исправляем капитализацию и улучшаем качество
            from utils.text_utils import TextUtils
            improved_content = TextUtils.improve_post_quality(cleaned_content)
            
            humanized_content = await self.humanize_post(improved_content)
            
            return {
                "text": humanized_content,
                "image_url": result.get("image_url")
            }
            
        except Exception as e:
            logging.error(f"Ошибка при генерации поста из контент-плана: {e}")
            raise Exception("Не удалось сгенерировать пост из контент-плана")
    
    async def extract_visual_elements(self, post_text: str) -> dict:
        """Извлекает ключевые визуальные элементы из поста, используя промпт из БД."""
        
        system_prompt = await self.prompt_manager.get_prompt('image') or DEFAULT_VISUAL_PROMPT
        
        try:
            # Используем OpenRouter для извлечения визуальных элементов
            logging.info("Извлечение визуальных элементов через OpenRouter")
            
            messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Пост: {post_text}"}
            ]
            
            result = await self.openrouter_service.generate_content(
                messages=messages,
                model=None,  # Используем модель для промптов изображений
                temperature=0.8,
                max_tokens=500,
                use_for_posts=False
            )
            
            if result and result.get("choices"):
                response_content = result["choices"][0]["message"]["content"]
                response = type('obj', (object,), {
                    'choices': [type('obj', (object,), {
                        'message': type('obj', (object,), {'content': response_content})()
                    })()]
                })()
            else:
                response = None
                
        except Exception as e:
            logging.error(f"Ошибка при извлечении визуальных элементов через OpenRouter: {e}")
            response = None
        
        if not response:
            # Возвращаем fallback если не удалось получить ответ
            return {
                "main_action": "programming on computer",
                "environment": "modern coding setup with multiple monitors",
                "objects": ["laptop", "external monitors", "coffee"],
                "mood": "focused",
                "tech_context": ["code on screens"],
                "lighting": "blue screen glow",
                "composition": "three-quarter view",
                "story_moment": "coding session"
            }
        
        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            # Fallback если JSON не распарсился
            return {
                "main_action": "programming on computer",
                "environment": "modern coding setup with multiple monitors",
                "objects": ["laptop", "external monitors", "coffee"],
                "mood": "focused",
                "tech_context": ["code on screens"],
                "lighting": "blue screen glow",
                "composition": "three-quarter view",
                "story_moment": "coding session"
            }
    
    async def generate_contextual_image_with_character(self, post_text: str, style: str = None) -> str:
        """
        Генерирует промпт для изображения.
        - Если пользователь задал собственный промпт, использует его для генерации нового промпта через GPT.
        - Если нет, анализирует текст поста и создает промпт автоматически.
        """
        custom_image_prompt_template = await self.prompt_manager.get_prompt('image')

        if custom_image_prompt_template:
            # Пользовательский промпт существует. Используем его как ШАБЛОН для GPT.
            logging.info(f"Используется пользовательский ШАБЛОН промпта для генерации промпта изображения...")
            
            try:
                # Создаем промпт для fal.ai с приоритетом Perplexity
                try:
                    # Используем OpenRouter для генерации контекстуального промпта
                    logging.info("Генерация контекстуального промпта через OpenRouter")
                    
                    messages = [
                            {"role": "system", "content": custom_image_prompt_template},
                            {"role": "user", "content": post_text}
                    ]
                    
                    result = await self.openrouter_service.generate_content(
                        messages=messages,
                        model=None,  # Используем модель для промптов изображений
                        temperature=0.7,
                        max_tokens=200,
                        use_for_posts=False
                    )
                    
                    if result and result.get("choices"):
                        response_content = result["choices"][0]["message"]["content"]
                        response = type('obj', (object,), {
                            'choices': [type('obj', (object,), {
                                'message': type('obj', (object,), {'content': response_content})()
                            })()]
                        })()
                    else:
                        response = None
                        
                except Exception as e:
                    logging.error(f"Ошибка при генерации контекстуального промпта через OpenRouter: {e}")
                    response = None
                
                if response:
                    scene_description = response.choices[0].message.content.strip()
                else:
                    # Fallback если не удалось получить ответ
                    scene_description = f"A photorealistic image inspired by the following text: {post_text}"
                logging.info(f"Сгенерирован новый промпт для fal.ai: {scene_description[:150]}...")

            except Exception as e:
                logging.error(f"Ошибка при генерации промпта для изображения с помощью GPT: {e}")
                # Fallback в случае ошибки
                scene_description = f"A photorealistic image inspired by the following text: {post_text}"

        else:
            # Пользовательский промпт не найден. Работаем по старой схеме с JSON.
            logging.info("Пользовательский промпт не найден, генерируется на основе анализа текста (JSON).")
            visual_elements = await self.extract_visual_elements(post_text)
            
            # Собираем промпт только из извлеченных элементов, без персонажа.
            scene_description = f"""
            {visual_elements.get('main_action', 'working on computer')}, 
            {visual_elements.get('composition', 'three-quarter view')},
            {visual_elements.get('environment', 'modern office setup')}, 
            {visual_elements.get('mood', 'focused')} expression,
            detailed scene with {', '.join(visual_elements.get('objects', ['multiple monitors']))},
            {visual_elements.get('lighting', 'blue screen glow')},
            showing {', '.join(visual_elements.get('tech_context', ['code on screens']))},
            capturing {visual_elements.get('story_moment', 'work moment')},
            professional photography, detailed, realistic, high quality
            """
        
        # Добавляем стиль в любом случае, если он выбран
        if style and style.lower() != 'none':
            scene_description += f", in the style of {style}"
            
        # Очищаем от лишних пробелов и переносов строк
        return " ".join(scene_description.strip().split())
    
    async def generate_image_with_fal_api(self, post_text: str, image_style: str = None) -> dict:
        """Генерирует изображение через FAL API с использованием fal-client."""
        
        if not FAL_AI_KEY:
            return {"success": False, "error": "FAL_AI_KEY не установлен в конфигурации"}
        
        prompt = await self.generate_contextual_image_with_character(post_text, style=image_style)
        
        # Параметры для fal-client
        payload = {
            "prompt": prompt,
            "image_size": "landscape_4_3",
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
            "num_images": 1,
            "enable_safety_checker": True,
            "seed": random.randint(0, 2**32 - 1) # Добавляем случайный seed для разнообразия
        }
        
        try:
            # Используем fal_client.run_async для прямого вызова
            logging.info(f"Отправка запроса в fal.ai с промптом: {prompt[:100]}...")
            result = await fal_client.run_async(
                "fal-ai/flux/dev",
                arguments=payload
            )
            logging.info("Ответ от fal.ai получен.")
            
            return {
                "success": True,
                "image_url": result["images"][0]["url"],
                "prompt_used": prompt
            }
        except Exception as e:
            logging.error(f"Ошибка при генерации изображения через fal-client: {e}")
            return {"success": False, "error": f"Ошибка fal-client: {str(e)}"}
    
    # Оставляем старые методы для обратной совместимости
    async def generate_image_prompt(self, post_text: str) -> str:
        """Генерирует креативный промпт для изображений."""
        return await self.generate_contextual_image_with_character(post_text)
    
    async def generate_story_based_image(self, post_text: str) -> str:
        """Создает изображение на основе истории поста."""
        return await self.generate_contextual_image_with_character(post_text)
    
    async def humanize_post(self, content: str):
        """Минимальная обработка - только возвращаем контент без изменений"""
        return content

    async def transcribe_audio(self, audio_file_path: str) -> str:
        """
        Транскрибирует аудиофайл с помощью OpenAI Whisper.
        Возвращает None если OpenAI API ключ не настроен.
        """
        if not self.openai_client:
            logging.warning("OpenAI API ключ не настроен. Транскрипция недоступна.")
            return None
            
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcription = await self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
            return transcription.text
        except Exception as e:
            logging.error(f"Ошибка при транскрибации аудио: {e}")
            return None
