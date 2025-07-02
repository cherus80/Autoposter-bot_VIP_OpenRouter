# database/posts_db.py
from sqlalchemy import select, func, desc
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from .database import async_session_maker
from .models import Post
import traceback
import logging

async def count_posts(days_ago: int = None) -> int:
    """
    Подсчитывает количество постов.
    Если указан days_ago, считает только за последние N дней.
    """
    async with async_session_maker() as session:
        query = select(func.count(Post.id))
        if days_ago:
            start_date = datetime.utcnow() - timedelta(days=days_ago)
            query = query.where(Post.created_at >= start_date)
        
        result = await session.execute(query)
        return result.scalar_one()

async def get_last_post_time() -> datetime | None:
    """
    Возвращает время создания самого последнего поста.
    """
    async with async_session_maker() as session:
        query = select(Post.published_at).order_by(desc(Post.published_at)).limit(1)
        result = await session.execute(query)
        return result.scalar_one_or_none()

async def save_post(
    content: str,
    with_image: bool,
    image_url: str | None = None,
    platforms: dict = None,
    topic: str = "Без темы",
    post_type: str = "Ручной",
    published_at: datetime = None
):
    """
    Универсальная функция для сохранения информации о посте в БД.
    Сохраняет как автоматические, так и ручные посты.
    """
    if published_at is None:
        published_at = datetime.utcnow()
    
    if platforms is None:
        platforms = {'telegram': False, 'vk': False}

    try:
        async with async_session_maker() as session:
            new_post = Post(
                content=content,
                topic=topic,
                post_type=post_type,
                with_image=with_image,
                image_url=image_url,
                telegram_published=platforms.get('telegram', False),
                vk_published=platforms.get('vk', False),
                published_at=published_at,
                created_at=published_at 
            )
            
            session.add(new_post)
            await session.commit()
            
            logging.info(f"Пост '{topic[:30]}...' ({post_type}) сохранен в БД. ID: {new_post.id}")
            return new_post.id
            
    except Exception as e:
        logging.error(f"Критическая ошибка при сохранении поста в БД: {e}", exc_info=True)
        await session.rollback() # Rollback on error
        raise

async def get_recent_posts(limit: int = 10) -> list:
    """Возвращает последние посты для отладки."""
    async with async_session_maker() as session:
        query = select(Post).order_by(desc(Post.created_at)).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

async def get_posts_by_type(post_type: str, days_ago: int = 7) -> int:
    """Подсчитывает количество постов определенного типа за период."""
    async with async_session_maker() as session:
        start_date = datetime.utcnow() - timedelta(days=days_ago)
        query = select(func.count(Post.id)).where(
            Post.post_type == post_type,
            Post.created_at >= start_date
        )
        result = await session.execute(query)
        return result.scalar_one()

async def get_posts_with_images_count(days_ago: int = 7) -> int:
    """Подсчитывает количество постов с изображениями за период."""
    async with async_session_maker() as session:
        start_date = datetime.utcnow() - timedelta(days=days_ago)
        query = select(func.count(Post.id)).where(
            Post.with_image == True,
            Post.created_at >= start_date
        )
        result = await session.execute(query)
        return result.scalar_one()

async def get_platform_stats(platform: str, days_ago: int = 7) -> dict:
    """Получает статистику публикаций по платформе."""
    async with async_session_maker() as session:
        start_date = datetime.utcnow() - timedelta(days=days_ago)
        
        if platform == "telegram":
            query = select(func.count(Post.id)).where(
                Post.telegram_published == True,
                Post.created_at >= start_date
            )
        elif platform == "vk":
            query = select(func.count(Post.id)).where(
                Post.vk_published == True,
                Post.created_at >= start_date
            )
        else:
            return {"error": "Неизвестная платформа"}
        
        result = await session.execute(query)
        return {"platform": platform, "posts": result.scalar_one(), "period_days": days_ago}
