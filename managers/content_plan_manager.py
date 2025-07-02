# managers/content_plan_manager.py - Управление контент-планом
import json
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.database import async_session_maker
from database.models import ContentPlan

class ContentPlanManager:
    def __init__(self, session_maker=async_session_maker):
        self.session_maker = session_maker

    async def upload_plan_from_json(self, json_data: str):
        """
        Загружает контент-план из JSON-строки.
        Предварительно очищает старый план.
        Новый формат: JSON является списком объектов.
        """
        try:
            plan_items = json.loads(json_data)
            if not isinstance(plan_items, list):
                return False, "Ошибка формата: JSON должен быть списком (массивом) объектов."
        except json.JSONDecodeError:
            return False, "Ошибка декодирования JSON."

        async with self.session_maker() as session:
            # Очищаем старый план
            await session.execute(ContentPlan.__table__.delete())
            
            # Добавляем новые записи
            for item in plan_items:
                new_item = ContentPlan(
                    category=item.get("category"),
                    theme=item.get("theme"),
                    post_description=item.get("post_description"),
                )
                session.add(new_item)
            
            await session.commit()
        return True, f"Контент-план успешно загружен. {len(plan_items)} записей."

    async def get_next_topic(self):
        """
        Получает следующую неиспользованную тему из контент-плана.
        Сортирует по ID, так как поле 'day' было удалено.
        """
        async with self.session_maker() as session:
            stmt = select(ContentPlan).where(ContentPlan.used == False).order_by(ContentPlan.id)
            result = await session.execute(stmt)
            topic = result.scalars().first()
            return topic

    async def mark_topic_as_used(self, topic_id: int):
        """
        Помечает тему как использованную, а не удаляет ее.
        """
        async with self.session_maker() as session:
            stmt = (
                update(ContentPlan)
                .where(ContentPlan.id == topic_id)
                .values(used=True)
            )
            await session.execute(stmt)
            await session.commit()
            
    async def count_remaining_topics(self) -> int:
        """
        Считает, сколько неиспользованных тем осталось в контент-плане.
        """
        async with self.session_maker() as session:
            stmt = select(func.count()).select_from(ContentPlan).where(ContentPlan.used == False)
            result = await session.execute(stmt)
            return result.scalar_one()
    
    async def add_content_items(self, items: list) -> int:
        """
        Добавляет новые темы в контент-план.
        Возвращает количество успешно добавленных тем.
        """
        success_count = 0
        async with self.session_maker() as session:
            for item in items:
                # Проверяем, существует ли уже такая тема
                stmt = select(ContentPlan).where(ContentPlan.theme == item['theme'])
                result = await session.execute(stmt)
                existing = result.scalars().first()
                
                if not existing:
                    new_item = ContentPlan(
                        category=item.get('category', ''),
                        theme=item['theme'],
                        post_description=item.get('post_description', ''),
                        with_image=True,  # По умолчанию с изображением
                        used=False
                    )
                    session.add(new_item)
                    success_count += 1
            
            await session.commit()
        return success_count
    
    async def get_unused_items(self, limit: int = 10, offset: int = 0) -> list:
        """
        Получает список неиспользованных тем (до limit штук).
        """
        async with self.session_maker() as session:
            stmt = select(ContentPlan).where(ContentPlan.used == False).order_by(ContentPlan.id).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def count_unused_items(self) -> int:
        """
        Считает количество неиспользованных тем.
        """
        async with self.session_maker() as session:
            stmt = select(func.count()).select_from(ContentPlan).where(ContentPlan.used == False)
            result = await session.execute(stmt)
            return result.scalar_one()
    
    async def clear_all_items(self) -> int:
        """
        Удаляет все темы из контент-плана.
        Возвращает количество удаленных записей.
        """
        async with self.session_maker() as session:
            # Считаем количество записей перед удалением
            count_stmt = select(func.count()).select_from(ContentPlan)
            count_result = await session.execute(count_stmt)
            total_count = count_result.scalar_one()
            
            # Удаляем все записи
            delete_stmt = delete(ContentPlan)
            await session.execute(delete_stmt)
            await session.commit()
            
            return total_count
    
    async def get_used_items(self, limit: int = 10, offset: int = 0) -> list:
        """
        Получает список использованных (опубликованных) тем.
        """
        async with self.session_maker() as session:
            stmt = select(ContentPlan).where(ContentPlan.used == True).order_by(ContentPlan.id.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def count_used_items(self) -> int:
        """
        Считает количество использованных тем.
        """
        async with self.session_maker() as session:
            stmt = select(func.count()).select_from(ContentPlan).where(ContentPlan.used == True)
            result = await session.execute(stmt)
            return result.scalar_one()
    
    async def get_all_items(self, limit: int = 10, offset: int = 0) -> list:
        """
        Получает все темы (использованные и неиспользованные).
        """
        async with self.session_maker() as session:
            stmt = select(ContentPlan).order_by(ContentPlan.used, ContentPlan.id).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def count_all_items(self) -> int:
        """
        Считает общее количество тем.
        """
        async with self.session_maker() as session:
            stmt = select(func.count()).select_from(ContentPlan)
            result = await session.execute(stmt)
            return result.scalar_one()
    
    async def restore_topic(self, topic_id: int) -> bool:
        """
        Восстанавливает тему (помечает как неиспользованную).
        Возвращает True, если тема была найдена и восстановлена.
        """
        async with self.session_maker() as session:
            stmt = (
                update(ContentPlan)
                .where(ContentPlan.id == topic_id, ContentPlan.used == True)
                .values(used=False)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
    
    async def get_topic_by_id(self, topic_id: int):
        """
        Получает тему по ID.
        """
        async with self.session_maker() as session:
            stmt = select(ContentPlan).where(ContentPlan.id == topic_id)
            result = await session.execute(stmt)
            return result.scalars().first() 