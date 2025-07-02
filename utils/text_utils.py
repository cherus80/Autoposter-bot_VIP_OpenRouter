"""
@file: utils/text_utils.py
@description: Утилиты для обработки текста постов
@dependencies: services/ai_service.py, aiogram
@created: 2025-01-20
"""

import os
import re
import logging
from typing import Optional, Dict, List, Tuple
from aiogram import Bot
from aiogram.types import Voice

logger = logging.getLogger(__name__)

class TextUtils:
    """Утилиты для обработки и форматирования текста"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Очистка текста от лишних пробелов и символов"""
        if not text:
            return ""
        
        # Убираем лишние пробелы, но сохраняем переносы строк
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            cleaned_line = re.sub(r'\s+', ' ', line).strip()
            cleaned_lines.append(cleaned_line)
        
        return '\n'.join(cleaned_lines)
    
    @staticmethod
    def format_for_platform(text: str, platform: str) -> str:
        """Форматирует текст для конкретной платформы"""
        if platform.lower() == "telegram":
            return TextUtils.adapt_for_telegram(text)
        elif platform.lower() == "vk":
            return TextUtils.adapt_for_vk(text)
        else:
            return text
    
    @staticmethod
    def improve_post_quality(text: str) -> str:
        """Минимальная обработка поста - только очистка лишних пробелов"""
        # AI генерирует готовый пост со всем форматированием
        # Код только убирает лишние пробелы
        return TextUtils.clean_text(text)
    
    @staticmethod
    def adapt_for_telegram(text: str) -> str:
        """Адаптирует пост для Telegram (HTML поддерживается)"""
        return text
    
    @staticmethod
    def adapt_for_vk(text: str) -> str:
        """Адаптирует пост для VK (убирает только HTML теги)"""
        # Убираем HTML теги
        text = text.replace('<b>', '').replace('</b>', '')
        text = text.replace('<i>', '').replace('</i>', '')
        
        # Больше никаких замен - пользователь сам указывает нужные ссылки в промпте
        return text

    @staticmethod
    def validate_post_structure(text: str) -> Dict[str, any]:
        """
        Валидация структуры поста согласно стандартам
        
        Returns:
            Dict с результатами валидации:
            {
                'is_valid': bool,
                'errors': List[str],
                'warnings': List[str],
                'score': int (0-100),
                'suggestions': List[str]
            }
        """
        errors = []
        warnings = []
        suggestions = []
        score = 100
        
        lines = text.strip().split('\n')
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        
        # 1. Проверка заголовка
        if not non_empty_lines:
            errors.append("Пост пустой")
            return TextUtils._build_validation_result(False, errors, warnings, 0, suggestions)
        
        first_line = non_empty_lines[0]
        if not (first_line.startswith('<b>') and first_line.endswith('</b>')):
            errors.append("Заголовок должен быть в тегах <b></b>")
            score -= 20
        
        # Проверка длины заголовка
        header_text = first_line.replace('<b>', '').replace('</b>', '')
        if len(header_text) > 60:
            warnings.append(f"Заголовок слишком длинный ({len(header_text)} символов, рекомендуется до 60)")
            score -= 5
        
        # Проверка на цифры в заголовке
        if not re.search(r'\d+', header_text):
            warnings.append("В заголовке желательны конкретные цифры")
            score -= 5
        
        # 2. Проверка наличия эмодзи в абзацах
        emoji_pattern = r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+'
        paragraphs_with_emoji = 0
        total_paragraphs = 0
        
        for line in non_empty_lines[1:]:  # Исключаем заголовок
            if line.startswith('#'):  # Пропускаем хэштеги
                continue
            if 't.me/' in line:  # Пропускаем CTA со ссылкой
                continue
            
            total_paragraphs += 1
            if re.search(emoji_pattern, line):
                paragraphs_with_emoji += 1
        
        if total_paragraphs > 0:
            emoji_ratio = paragraphs_with_emoji / total_paragraphs
            if emoji_ratio < 0.7:  # Менее 70% абзацев с эмодзи
                warnings.append(f"Мало эмодзи: {paragraphs_with_emoji}/{total_paragraphs} абзацев")
                score -= 10
        
        # 3. Проверка HTML форматирования
        if '**' in text or '__' in text:
            errors.append("Найдены запрещенные символы ** или __. Используйте только HTML теги <b>, <i>")
            score -= 15
        
        # Проверка наличия <b> тегов для выделения
        bold_count = text.count('<b>')
        if bold_count < 3:
            warnings.append(f"Мало выделений жирным ({bold_count}), рекомендуется минимум 3-5")
            score -= 5
        
        # 4. Проверка цифр и фактов
        numbers = re.findall(r'\b\d+[%₽\$]?\b', text)
        if len(numbers) < 3:
            warnings.append(f"Мало конкретных цифр ({len(numbers)}), добавьте больше фактов")
            score -= 10
        
        # 5. Проверка наличия призыва к действию (CTA)
        # Ищем любые ссылки, упоминания каналов или призывы
        cta_patterns = [
            r'@\w+',  # @упоминания
            r't\.me/',  # Telegram ссылки
            r'подписыв',  # "подписывайся", "подписывайтесь"
            r'присоединя',  # "присоединяйся", "присоединяйтесь"
        ]
        
        has_cta = any(re.search(pattern, text, re.IGNORECASE) for pattern in cta_patterns)
        if not has_cta:
            warnings.append("Рекомендуется добавить призыв к действию (ссылку на канал, подписку)")
            score -= 10
        
        # 6. Проверка хэштегов
        hashtags = re.findall(r'#\w+', text)
        if len(hashtags) < 3:
            warnings.append(f"Мало хэштегов ({len(hashtags)}), рекомендуется 3-5")
            score -= 5
        elif len(hashtags) > 6:
            warnings.append(f"Слишком много хэштегов ({len(hashtags)}), рекомендуется 3-5")
            score -= 3
        
        # 7. Проверка запрещенных фраз
        forbidden_phrases = ["честно говоря", "по опыту", "недавно наткнулся", "хочу поделиться"]
        for phrase in forbidden_phrases:
            if phrase.lower() in text.lower():
                errors.append(f"Найдена запрещенная фраза: '{phrase}'")
                score -= 10
        
        # 8. Проверка длины поста
        word_count = len(text.split())
        if word_count < 50:
            warnings.append(f"Пост слишком короткий ({word_count} слов), рекомендуется 300-500")
            score -= 15
        elif word_count > 600:
            warnings.append(f"Пост слишком длинный ({word_count} слов), рекомендуется 300-500")
            score -= 10
        
        # Генерация предложений по улучшению
        if score < 80:
            suggestions.extend(TextUtils._generate_improvement_suggestions(errors, warnings))
        
        is_valid = len(errors) == 0 and score >= 70
        
        return TextUtils._build_validation_result(is_valid, errors, warnings, max(0, score), suggestions)

    @staticmethod
    def _build_validation_result(is_valid: bool, errors: List[str], warnings: List[str], 
                               score: int, suggestions: List[str]) -> Dict[str, any]:
        """Создает результат валидации"""
        return {
            'is_valid': is_valid,
            'errors': errors,
            'warnings': warnings,
            'score': score,
            'suggestions': suggestions
        }

    @staticmethod
    def _generate_improvement_suggestions(errors: List[str], warnings: List[str]) -> List[str]:
        """Генерирует предложения по улучшению поста"""
        suggestions = []
        
        if errors:
            for error in errors:
                if "HTML" in error or "тег" in error:
                    suggestions.append("Проверьте правильность HTML тегов <b></b> и <i></i>")
                elif "заголовок" in error.lower():
                    suggestions.append("Начните пост с заголовка в тегах <b></b>")
                elif "**" in error or "__" in error:
                    suggestions.append("Замените ** на <b></b>, а __ на <i></i>")
                elif "призыв" in error.lower() or "cta" in error.lower():
                    suggestions.append("Добавьте призыв к действию с полной ссылкой на канал (https://t.me/+abc123)")
        
        for warning in warnings:
            if "эмодзи" in warning.lower():
                suggestions.append("Добавьте эмодзи в начало каждого абзаца")
            elif "цифр" in warning.lower():
                suggestions.append("Включите больше конкретных цифр и процентов")
            elif "хэштегов" in warning.lower():
                suggestions.append("Добавьте 3-5 релевантных хэштегов в конце поста")
        
        return list(set(suggestions))  # Убираем дубликаты
    
    @staticmethod
    def auto_fix_common_issues(text: str) -> Tuple[str, List[str]]:
        """
        Автоматически исправляет базовые проблемы форматирования
        
        Returns:
            Tuple[исправленный_текст, список_примененных_исправлений]
        """
        fixes_applied = []
        fixed_text = text
        
        # 1. Замена ** на <b>
        if '**' in fixed_text:
            # Ищем парные ** и заменяем на <b></b>
            fixed_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', fixed_text)
            fixes_applied.append("Заменены ** на <b></b>")
        
        # 2. Замена __ на <i>
        if '__' in fixed_text:
            fixed_text = re.sub(r'__(.*?)__', r'<i>\1</i>', fixed_text)
            fixes_applied.append("Заменены __ на <i></i>")
        
        # 3. Убираем лишние пустые строки (больше 2 подряд)
        fixed_text = re.sub(r'\n{3,}', '\n\n', fixed_text)
        if len(re.findall(r'\n{3,}', text)) > 0:
            fixes_applied.append("Убраны лишние пустые строки")
        
        # 4. Добавляем пробел после эмодзи, если его нет
        emoji_pattern = r'([\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF])([^\s])'
        if re.search(emoji_pattern, fixed_text):
            fixed_text = re.sub(emoji_pattern, r'\1 \2', fixed_text)
            fixes_applied.append("Добавлены пробелы после эмодзи")
        
        return fixed_text, fixes_applied

    @staticmethod
    def get_post_statistics(text: str) -> Dict[str, any]:
        """Возвращает статистику поста"""
        lines = text.strip().split('\n')
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        
        # Подсчет статистики
        word_count = len(text.split())
        char_count = len(text)
        line_count = len(non_empty_lines)
        
        # Подсчет элементов
        bold_tags = text.count('<b>')
        italic_tags = text.count('<i>')
        emoji_count = len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', text))
        hashtag_count = len(re.findall(r'#\w+', text))
        number_count = len(re.findall(r'\b\d+[%₽\$]?\b', text))
        
        # Проверка структурных элементов
        has_title = len(non_empty_lines) > 0 and non_empty_lines[0].startswith('<b>') and non_empty_lines[0].endswith('</b>')
        cta_patterns = [
            r'@\w+',  # @упоминания
            r't\.me/',  # Telegram ссылки
            r'подписыв',  # "подписывайся", "подписывайтесь"
            r'присоединя',  # "присоединяйся", "присоединяйтесь"
        ]
        has_cta = any(re.search(pattern, text, re.IGNORECASE) for pattern in cta_patterns)
        
        return {
            'word_count': word_count,
            'char_count': char_count,
            'line_count': line_count,
            'bold_tags': bold_tags,
            'italic_tags': italic_tags,
            'emoji_count': emoji_count,
            'hashtag_count': hashtag_count,
            'number_count': number_count,
            'has_title': has_title,
            'has_cta': has_cta,
            'estimated_read_time': max(1, word_count // 200)  # минут на чтение
        }

async def download_voice_message(bot: Bot, voice: Voice, download_dir: str = "temp") -> str:
    """
    Скачивает голосовое сообщение и возвращает путь к файлу.
    
    Args:
        bot: Экземпляр бота
        voice: Объект голосового сообщения
        download_dir: Директория для сохранения (по умолчанию 'temp')
    
    Returns:
        str: Путь к скачанному файлу
    """
    try:
        # Создаем директорию если её нет
        os.makedirs(download_dir, exist_ok=True)
        
        # Получаем информацию о файле
        file_info = await bot.get_file(voice.file_id)
        
        # Формируем путь для сохранения
        file_path = os.path.join(download_dir, f"voice_{voice.file_id}.ogg")
        
        # Скачиваем файл
        await bot.download_file(file_info.file_path, file_path)
        
        logger.info(f"Голосовое сообщение скачано: {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"Ошибка при скачивании голосового сообщения: {e}")
        raise

async def transcribe_voice_message(bot: Bot, voice: Voice) -> str:
    """
    Скачивает и транскрибирует голосовое сообщение.
    
    Args:
        bot: Экземпляр бота
        voice: Объект голосового сообщения
    
    Returns:
        str: Транскрибированный текст или None при ошибке
    """
    voice_file_path = None
    try:
        # Скачиваем голосовое сообщение
        voice_file_path = await download_voice_message(bot, voice)
        
        # Транскрибируем с помощью OpenAI Whisper
        from services.ai_service import AIService
        ai_service = AIService()
        transcribed_text = await ai_service.transcribe_audio(voice_file_path)
        
        if transcribed_text:
            logger.info(f"Голосовое сообщение транскрибировано: {transcribed_text[:100]}...")
            return transcribed_text.strip()
        else:
            logger.warning("Не удалось транскрибировать голосовое сообщение")
            return None
            
    except Exception as e:
        logger.error(f"Ошибка при транскрибации голосового сообщения: {e}")
        return None
    finally:
        # Удаляем временный файл
        if voice_file_path and os.path.exists(voice_file_path):
            try:
                os.remove(voice_file_path)
                logger.info(f"Временный файл удален: {voice_file_path}")
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл {voice_file_path}: {e}")

def cleanup_temp_files(download_dir: str = "temp"):
    """
    Очищает временные файлы голосовых сообщений.
    
    Args:
        download_dir: Директория с временными файлами
    """
    try:
        if os.path.exists(download_dir):
            for filename in os.listdir(download_dir):
                if filename.startswith("voice_") and filename.endswith(".ogg"):
                    file_path = os.path.join(download_dir, filename)
                    os.remove(file_path)
                    logger.info(f"Удален временный файл: {file_path}")
    except Exception as e:
        logger.warning(f"Ошибка при очистке временных файлов: {e}")