# services/image_service.py - Сервис генерации изображений
import fal_client
import os
from config import FAL_AI_KEY

# Устанавливаем ключ аутентификации при импорте модуля
if FAL_AI_KEY:
    os.environ["FAL_KEY"] = FAL_AI_KEY

class ImageService:
    def __init__(self):
        # Клиент fal_client не требует инициализации в конструкторе
        pass
    
    async def generate_post_image(self, image_prompt: str):
        """
        Генерация изображения для поста с помощью Fal.ai Flux.1 Dev, используя готовый промпт.
        """
        if not FAL_AI_KEY:
            print("ERROR: Ключ FAL_AI_KEY не найден в переменных окружения.")
            return None
        
        try:
            # Асинхронный вызов API fal.ai с предоставленным промптом
            result = await fal_client.run_async(
                "fal-ai/flux/dev",
                arguments={"prompt": image_prompt},
            )
            
            # Извлекаем URL первого изображения из результата
            image_url = result["images"][0]["url"]
            return image_url
            
        except Exception as e:
            print(f"❌ Ошибка генерации изображения через Fal.ai: {e}")
            return None