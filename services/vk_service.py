# services/vk_service.py - Сервис для работы с VK API
import vk_api
import requests
import logging
from config import VK_ACCESS_TOKEN, VK_GROUP_ID, VK_CTA_TEXT

class VKService:
    def __init__(self):
        self.token = VK_ACCESS_TOKEN
        self.group_id = VK_GROUP_ID
        self.cta_text = VK_CTA_TEXT
        self.is_configured = False
        
        # Проверяем наличие токенов
        if not all([VK_ACCESS_TOKEN, VK_GROUP_ID]):
            logging.warning("VK_ACCESS_TOKEN и/или VK_GROUP_ID не установлены. VK публикация будет недоступна.")
            self.vk_session = None
            self.vk = None
        else:
            try:
                self.vk_session = vk_api.VkApi(token=self.token)
                self.vk = self.vk_session.get_api()
                self.is_configured = True
                logging.info("VK сервис успешно инициализирован")
            except Exception as e:
                logging.error(f"Ошибка инициализации VK API: {e}")
                self.vk_session = None
                self.vk = None

    async def post_to_group(self, content: str, image_url: str = None):
        """Публикует пост на стене группы VK."""
        if not self.is_configured:
            logging.warning("VK сервис не настроен. Пропускаем публикацию в VK.")
            return False
            
        try:
            attachments = ''
            
            # Очистка контента от нулевых байтов
            clean_content = content.replace('\x00', '')
            
            if image_url:
                print(f"INFO: Загружаем изображение: {image_url}")
                photo_attachment = await self.upload_image(image_url)
                if photo_attachment:
                    attachments = photo_attachment
                    print(f"INFO: Attachment сформирован: {attachments}")
                else:
                    print("WARNING: Не удалось загрузить изображение")

            post_text = clean_content
            if self.cta_text and self.cta_text not in post_text:
                post_text += self.cta_text
            
            print(f"INFO: Публикуем пост с attachments: '{attachments}'")
            
            self.vk.wall.post(
                owner_id=f"-{self.group_id}",
                from_group=1,
                message=post_text,
                attachments=attachments
            )
            print("INFO: Пост успешно опубликован в VK.")
            return True
            
        except Exception as e:
            print(f"ERROR: Ошибка публикации в VK: {e}")
            return False

    async def upload_image(self, image_url: str) -> str | None:
        """Загружает изображение по URL на сервер VK."""
        if not self.is_configured:
            logging.warning("VK сервис не настроен. Пропускаем загрузку изображения.")
            return None
            
        try:
            # 1. Получаем адрес для загрузки
            upload_server = self.vk.photos.getWallUploadServer(group_id=self.group_id)
            upload_url = upload_server['upload_url']

            # 2. Скачиваем изображение по URL
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            
            # 3. Загружаем на сервер VK
            files = {'photo': ('image.jpg', response.content, 'image/jpeg')}
            upload_response = requests.post(upload_url, files=files).json()
            
            if not upload_response.get('photo'):
                 raise Exception(f"VK API upload error: {upload_response}")

            # 4. Сохраняем фото на стене
            save_response = self.vk.photos.saveWallPhoto(
                group_id=self.group_id,
                photo=upload_response['photo'],
                server=upload_response['server'],
                hash=upload_response['hash']
            )[0]
            
            owner_id = save_response['owner_id']
            photo_id = save_response['id']
            
            # Правильный формат для фотографий на стене группы
            return f"photo{owner_id}_{photo_id}"

        except Exception as e:
            print(f"ERROR: Ошибка загрузки изображения в VK: {e}")
            return None

    def adapt_text_for_vk(self, text: str):
        """Адаптация текста для VK"""
        # Заменяем эмодзи на VK-совместимые
        emoji_map = {
            "🤖": "🤖",
            "🚀": "🚀", 
            "💡": "💡",
            "⚡": "⚡",
            "🔥": "🔥"
        }
        
        for tg_emoji, vk_emoji in emoji_map.items():
            text = text.replace(tg_emoji, vk_emoji)
        
        return text 