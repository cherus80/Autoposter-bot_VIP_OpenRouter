"""
@file: services/backup_scheduler.py
@description: Планировщик автоматического резервного копирования
@dependencies: asyncio, logging, BackupService
@created: 2025-01-21
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from services.backup_service import backup_service
from utils.error_handler import handle_errors, ErrorSeverity

logger = logging.getLogger(__name__)


class BackupScheduler:
    """Планировщик автоматического резервного копирования"""
    
    def __init__(self, bot=None):
        self.bot = bot
        self.backup_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Инициализируем backup_service с ботом
        backup_service.bot = bot
    
    async def start(self) -> None:
        """Запустить планировщик резервного копирования"""
        if self.is_running:
            logger.warning("Планировщик резервного копирования уже запущен")
            return
        
        try:
            self.is_running = True
            self.backup_task = asyncio.create_task(self._backup_loop())
            logger.info("Планировщик резервного копирования запущен")
            
        except Exception as e:
            logger.error(f"Ошибка запуска планировщика резервного копирования: {e}")
            self.is_running = False
    
    async def stop(self) -> None:
        """Остановить планировщик резервного копирования"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.backup_task and not self.backup_task.done():
            self.backup_task.cancel()
            try:
                await self.backup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Планировщик резервного копирования остановлен")
    
    @handle_errors(context="backup_loop", severity=ErrorSeverity.HIGH)
    async def _backup_loop(self) -> None:
        """Основной цикл планировщика резервного копирования"""
        logger.info("Запущен цикл автоматического резервного копирования")
        
        while self.is_running:
            try:
                # Получаем настройки резервного копирования
                settings = await backup_service.get_backup_settings()
                
                if not settings.get("backup_enabled", True):
                    # Если резервное копирование отключено, ждем час и проверяем снова
                    await asyncio.sleep(3600)  # 1 час
                    continue
                
                # Проверяем, нужно ли выполнить резервное копирование
                if await self._should_create_backup(settings):
                    await self._perform_scheduled_backup()
                
                # Выполняем очистку старых бэкапов
                await backup_service.cleanup_old_backups()
                
                # Ждем следующую проверку (раз в час)
                await asyncio.sleep(3600)  # 1 час
                
            except asyncio.CancelledError:
                logger.info("Цикл резервного копирования отменен")
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле резервного копирования: {e}")
                # При ошибке ждем меньше времени перед повторной попыткой
                await asyncio.sleep(300)  # 5 минут
    
    async def _should_create_backup(self, settings: dict) -> bool:
        """Определить, нужно ли создавать резервную копию"""
        try:
            interval_hours = settings.get("backup_interval_hours", 24)
            
            # Получаем список существующих бэкапов
            backups = await backup_service.get_backup_list()
            
            if not backups:
                # Если нет бэкапов, создаем первый
                logger.info("Бэкапы не найдены, создаем первый")
                return True
            
            # Находим последний полный бэкап
            last_full_backup = None
            for backup in backups:
                if backup["type"] == "Полный бэкап":
                    last_full_backup = backup
                    break
            
            if not last_full_backup:
                logger.info("Полный бэкап не найден, создаем новый")
                return True
            
            # Проверяем, прошло ли достаточно времени с последнего бэкапа
            time_since_backup = datetime.now() - last_full_backup["created"]
            hours_since_backup = time_since_backup.total_seconds() / 3600
            
            if hours_since_backup >= interval_hours:
                logger.info(f"Прошло {hours_since_backup:.1f} часов с последнего бэкапа, создаем новый")
                return True
            else:
                logger.debug(f"До следующего бэкапа осталось {interval_hours - hours_since_backup:.1f} часов")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка проверки необходимости резервного копирования: {e}")
            return False
    
    async def _perform_scheduled_backup(self) -> None:
        """Выполнить запланированное резервное копирование"""
        try:
            logger.info("Начинаю автоматическое резервное копирование...")
            
            # Создаем полную резервную копию
            backup_path = await backup_service.create_full_backup()
            
            if backup_path:
                logger.info(f"Автоматическое резервное копирование завершено: {backup_path}")
                
                # Уведомляем администратора об успешном создании бэкапа
                await backup_service.notify_admin_backup_status(True, backup_path)
                
                # Обновляем время последнего бэкапа в настройках
                await self._update_last_backup_time()
            else:
                error_msg = "Не удалось создать резервную копию"
                logger.error(error_msg)
                await backup_service.notify_admin_backup_status(False, error=error_msg)
                
        except Exception as e:
            error_msg = f"Ошибка автоматического резервного копирования: {e}"
            logger.error(error_msg)
            await backup_service.notify_admin_backup_status(False, error=str(e))
    
    async def _update_last_backup_time(self) -> None:
        """Обновить время последнего резервного копирования"""
        try:
            from database.settings_db import update_setting
            
            current_time = datetime.now().isoformat()
            await update_setting("last_backup_time", current_time)
            
        except Exception as e:
            logger.error(f"Ошибка обновления времени последнего бэкапа: {e}")
    
    async def force_backup(self) -> Optional[str]:
        """Принудительно создать резервную копию (вне расписания)"""
        try:
            logger.info("Принудительное создание резервной копии...")
            
            backup_path = await backup_service.create_full_backup()
            
            if backup_path:
                logger.info(f"Принудительная резервная копия создана: {backup_path}")
                await backup_service.notify_admin_backup_status(True, backup_path)
                await self._update_last_backup_time()
                return backup_path
            else:
                logger.error("Не удалось создать принудительную резервную копию")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка принудительного резервного копирования: {e}")
            return None
    
    async def get_backup_status(self) -> dict:
        """Получить статус системы резервного копирования"""
        try:
            settings = await backup_service.get_backup_settings()
            backups = await backup_service.get_backup_list()
            
            # Находим последний бэкап
            last_backup = None
            if backups:
                last_backup = backups[0]  # Список уже отсортирован по времени
            
            # Получаем время последнего автоматического бэкапа
            from database.settings_db import get_setting
            last_auto_backup_str = await get_setting("last_backup_time", "")
            last_auto_backup = None
            if last_auto_backup_str:
                try:
                    last_auto_backup = datetime.fromisoformat(last_auto_backup_str)
                except:
                    pass
            
            status = {
                "scheduler_running": self.is_running,
                "backup_enabled": settings.get("backup_enabled", True),
                "backup_interval_hours": settings.get("backup_interval_hours", 24),
                "max_backups": settings.get("max_backups", 7),
                "total_backups": len(backups),
                "last_backup": last_backup,
                "last_auto_backup": last_auto_backup,
                "next_backup_in_hours": None
            }
            
            # Рассчитываем время до следующего бэкапа
            if last_auto_backup and settings.get("backup_enabled", True):
                interval_hours = settings.get("backup_interval_hours", 24)
                time_since = datetime.now() - last_auto_backup
                hours_since = time_since.total_seconds() / 3600
                next_backup_in = max(0, interval_hours - hours_since)
                status["next_backup_in_hours"] = round(next_backup_in, 1)
            
            return status
            
        except Exception as e:
            logger.error(f"Ошибка получения статуса резервного копирования: {e}")
            return {
                "scheduler_running": self.is_running,
                "error": str(e)
            }


# Глобальный экземпляр планировщика бэкапов
backup_scheduler = BackupScheduler() 