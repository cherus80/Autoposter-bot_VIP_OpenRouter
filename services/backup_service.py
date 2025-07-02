"""
@file: services/backup_service.py
@description: Сервис автоматического резервного копирования базы данных и настроек
@dependencies: sqlite3, asyncio, logging, shutil
@created: 2025-01-21
"""

import asyncio
import logging
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import json

from config import ADMIN_IDS
from database.database import async_session_maker, db_path
from database.settings_db import get_setting, update_setting
from utils.error_handler import handle_errors, ErrorSeverity

logger = logging.getLogger(__name__)


class BackupService:
    """Сервис для управления резервным копированием"""
    
    def __init__(self, bot=None):
        self.bot = bot
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # Настройки по умолчанию
        self.default_settings = {
            "backup_enabled": True,
            "backup_interval_hours": 24,  # Раз в сутки
            "max_backups": 7,  # Хранить 7 последних бэкапов
            "backup_database": True,
            "backup_settings": True,
            "backup_prompts": True,
            "compress_backups": True,
            "notify_admin": True
        }
    
    async def get_backup_settings(self) -> Dict:
        """Получить настройки резервного копирования"""
        try:
            settings = {}
            for key, default_value in self.default_settings.items():
                value = await get_setting(f"backup_{key}", str(default_value))
                # Конвертируем строки в правильные типы
                if isinstance(default_value, bool):
                    settings[key] = value.lower() == 'true'
                elif isinstance(default_value, int):
                    settings[key] = int(value)
                else:
                    settings[key] = value
            
            return settings
            
        except Exception as e:
            logger.error(f"Ошибка получения настроек бэкапа: {e}")
            return self.default_settings
    
    async def update_backup_settings(self, settings: Dict) -> bool:
        """Обновить настройки резервного копирования"""
        try:
            # Проверяем, что обновляем только валидные ключи
            valid_keys = set(self.default_settings.keys())
            for key, value in settings.items():
                if key in valid_keys:
                    await update_setting(f"backup_{key}", str(value))
                    logger.debug(f"Обновлена настройка backup_{key} = {value}")
                else:
                    logger.warning(f"Попытка обновить неизвестную настройку: {key}")
            
            logger.info("Настройки резервного копирования обновлены")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления настроек бэкапа: {e}")
            return False
    
    @handle_errors(context="create_database_backup", severity=ErrorSeverity.HIGH)
    async def create_database_backup(self, backup_name: Optional[str] = None) -> Optional[str]:
        """Создать резервную копию базы данных"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if not backup_name:
                backup_name = f"backup_{timestamp}_autoposting_bot.db"
            
            backup_path = self.backup_dir / backup_name
            
            # Создаем резервную копию SQLite базы данных
            # Используем VACUUM INTO для создания чистой копии
            async with async_session_maker() as session:
                # Закрываем сессию перед копированием
                await session.close()
            
            # Выполняем копирование в отдельном потоке
            await asyncio.get_event_loop().run_in_executor(
                None, self._copy_database, db_path, str(backup_path)
            )
            
            # Проверяем целостность бэкапа
            if await self._verify_backup(str(backup_path)):
                logger.info(f"Резервная копия БД создана: {backup_path}")
                return str(backup_path)
            else:
                logger.error("Резервная копия БД повреждена, удаляем")
                if backup_path.exists():
                    backup_path.unlink()
                return None
                
        except Exception as e:
            logger.error(f"Ошибка создания резервной копии БД: {e}")
            return None
    
    def _copy_database(self, source_path: str, backup_path: str):
        """Копирование базы данных с блокировкой (синхронная функция)"""
        # Используем SQLite BACKUP API для безопасного копирования
        source_conn = sqlite3.connect(source_path)
        backup_conn = sqlite3.connect(backup_path)
        
        try:
            source_conn.backup(backup_conn)
            logger.info("База данных скопирована успешно")
        finally:
            source_conn.close()
            backup_conn.close()
    
    async def _verify_backup(self, backup_path: str) -> bool:
        """Проверить целостность резервной копии"""
        try:
            conn = sqlite3.connect(backup_path)
            cursor = conn.cursor()
            
            # Проверяем целостность базы данных
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            
            conn.close()
            
            return result[0] == "ok"
            
        except Exception as e:
            logger.error(f"Ошибка проверки целостности бэкапа: {e}")
            return False
    
    async def create_settings_backup(self, backup_name: Optional[str] = None) -> Optional[str]:
        """Создать резервную копию настроек и промптов"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if not backup_name:
                backup_name = f"settings_backup_{timestamp}.json"
            
            backup_path = self.backup_dir / backup_name
            
            # Собираем все настройки из БД
            async with async_session_maker() as session:
                from sqlalchemy import select, text
                
                # Получаем настройки
                try:
                    settings_result = await session.execute(select(text("key, value, description")).select_from(text("settings")))
                    settings = {row[0]: {"value": row[1], "description": row[2]} for row in settings_result.fetchall()}
                except:
                    settings = {}
                
                # Получаем промпты
                try:
                    prompts_result = await session.execute(select(text("id, prompt_type, content")).select_from(text("ai_prompts")))
                    prompts = {f"{row[1]}_{row[0]}": row[2] for row in prompts_result.fetchall()}
                except:
                    prompts = {}
                
                # Получаем настройки публикации
                try:
                    pub_settings_result = await session.execute(select(text("user_id, publish_to_tg, publish_to_vk")).select_from(text("publishing_settings")))
                    pub_settings = {row[0]: {"telegram": row[1], "vk": row[2]} for row in pub_settings_result.fetchall()}
                except:
                    pub_settings = {}
            
            # Создаем JSON с настройками
            backup_data = {
                "backup_created": timestamp,
                "backup_type": "settings",
                "data": {
                    "settings": settings,
                    "prompts": prompts,
                    "publishing_settings": pub_settings
                }
            }
            
            # Сохраняем в файл
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Резервная копия настроек создана: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Ошибка создания резервной копии настроек: {e}")
            return None
    
    async def create_full_backup(self) -> Optional[str]:
        """Создать полную резервную копию (БД + настройки)"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            settings = await self.get_backup_settings()
            
            backup_files = []
            
            # Создаем резервную копию БД
            if settings.get("backup_database", True):
                db_backup = await self.create_database_backup(f"db_backup_{timestamp}.db")
                if db_backup:
                    backup_files.append(db_backup)
            
            # Создаем резервную копию настроек
            if settings.get("backup_settings", True):
                settings_backup = await self.create_settings_backup(f"settings_backup_{timestamp}.json")
                if settings_backup:
                    backup_files.append(settings_backup)
            
            # Если включено сжатие, создаем ZIP архив
            if settings.get("compress_backups", True) and backup_files:
                zip_path = self.backup_dir / f"full_backup_{timestamp}.zip"
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in backup_files:
                        zipf.write(file_path, Path(file_path).name)
                
                # Удаляем исходные файлы после архивирования
                for file_path in backup_files:
                    Path(file_path).unlink()
                
                logger.info(f"Полная резервная копия создана: {zip_path}")
                return str(zip_path)
            
            elif backup_files:
                logger.info(f"Резервные копии созданы: {backup_files}")
                return backup_files[0]  # Возвращаем первый файл как основной
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка создания полной резервной копии: {e}")
            return None
    
    async def restore_from_backup(self, backup_path: str, backup_type: str = "auto") -> bool:
        """Восстановить данные из резервной копии"""
        try:
            backup_file = Path(backup_path)
            
            if not backup_file.exists():
                logger.error(f"Файл резервной копии не найден: {backup_path}")
                return False
            
            # Определяем тип бэкапа
            if backup_file.suffix == '.zip':
                return await self._restore_from_zip(backup_path)
            elif backup_file.suffix == '.db':
                return await self._restore_database(backup_path)
            elif backup_file.suffix == '.json':
                return await self._restore_settings(backup_path)
            else:
                logger.error(f"Неподдерживаемый тип резервной копии: {backup_file.suffix}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка восстановления из резервной копии: {e}")
            return False
    
    async def _restore_from_zip(self, zip_path: str) -> bool:
        """Восстановить из ZIP архива"""
        try:
            temp_dir = self.backup_dir / "temp_restore"
            temp_dir.mkdir(exist_ok=True)
            
            # Извлекаем архив
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                zipf.extractall(temp_dir)
            
            success = True
            
            # Восстанавливаем файлы
            for file_path in temp_dir.iterdir():
                if file_path.suffix == '.db':
                    success &= await self._restore_database(str(file_path))
                elif file_path.suffix == '.json':
                    success &= await self._restore_settings(str(file_path))
            
            # Очищаем временную папку
            shutil.rmtree(temp_dir)
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка восстановления из ZIP: {e}")
            return False
    
    async def _restore_database(self, backup_path: str) -> bool:
        """Восстановить базу данных"""
        try:
            # Создаем резервную копию текущей БД перед восстановлением
            current_backup = await self.create_database_backup(f"before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            
            # Копируем резервную копию на место текущей БД
            await asyncio.get_event_loop().run_in_executor(
                None, shutil.copy2, backup_path, db_path
            )
            
            # Проверяем восстановленную БД
            if await self._verify_backup(db_path):
                logger.info("База данных успешно восстановлена")
                return True
            else:
                # Откатываемся к предыдущей версии
                if current_backup:
                    await asyncio.get_event_loop().run_in_executor(
                        None, shutil.copy2, current_backup, db_path
                    )
                logger.error("Восстановленная БД повреждена, откат выполнен")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка восстановления БД: {e}")
            return False
    
    async def _restore_settings(self, settings_path: str) -> bool:
        """Восстановить настройки из JSON"""
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            data = backup_data.get("data", {})
            
            # Восстанавливаем настройки
            settings = data.get("settings", {})
            for key, setting_data in settings.items():
                await update_setting(key, setting_data["value"])
            
            logger.info("Настройки успешно восстановлены")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка восстановления настроек: {e}")
            return False
    
    async def cleanup_old_backups(self) -> None:
        """Удалить старые резервные копии"""
        try:
            settings = await self.get_backup_settings()
            max_backups = settings.get("max_backups", 7)
            
            # Получаем список всех бэкапов с временными метками
            backup_files = []
            for file_path in self.backup_dir.iterdir():
                if file_path.is_file() and any(file_path.name.startswith(prefix) for prefix in ["backup_", "full_backup_", "settings_backup_"]):
                    backup_files.append((file_path.stat().st_mtime, file_path))
            
            # Сортируем по времени создания (новые первыми)
            backup_files.sort(reverse=True)
            
            # Удаляем старые бэкапы
            if len(backup_files) > max_backups:
                for _, file_path in backup_files[max_backups:]:
                    file_path.unlink()
                    logger.info(f"Удален старый бэкап: {file_path.name}")
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых бэкапов: {e}")
    
    async def get_backup_list(self) -> List[Dict]:
        """Получить список доступных резервных копий"""
        try:
            backups = []
            
            for file_path in self.backup_dir.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    backup_info = {
                        "name": file_path.name,
                        "path": str(file_path),
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(stat.st_mtime),
                        "type": self._determine_backup_type(file_path.name)
                    }
                    backups.append(backup_info)
            
            # Сортируем по времени создания (новые первыми)
            backups.sort(key=lambda x: x["created"], reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error(f"Ошибка получения списка бэкапов: {e}")
            return []
    
    async def delete_backup(self, backup_path: str) -> bool:
        """Удалить резервную копию"""
        try:
            backup_file = Path(backup_path)
            
            # Проверяем, что файл находится в директории backups
            if not str(backup_file.resolve()).startswith(str(self.backup_dir.resolve())):
                logger.error(f"Попытка удалить файл вне директории backups: {backup_path}")
                return False
            
            # Проверяем существование файла
            if not backup_file.exists():
                logger.warning(f"Файл для удаления не найден: {backup_path}")
                return False
            
            # Сохраняем информацию для уведомления
            file_name = backup_file.name
            file_size = backup_file.stat().st_size
            
            # Удаляем файл
            backup_file.unlink()
            logger.info(f"Резервная копия удалена: {backup_path}")
            
            # Уведомляем администратора если включены уведомления
            settings = await self.get_backup_settings()
            if settings.get("notify_admin", True) and self.bot:
                await self.notify_admin_backup_deleted(file_name, file_size)
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления резервной копии {backup_path}: {e}")
            return False
    
    def _determine_backup_type(self, filename: str) -> str:
        """Определить тип резервной копии по имени файла"""
        if filename.startswith("full_backup_"):
            return "Полный бэкап"
        elif filename.startswith("settings_backup_"):
            return "Настройки"
        elif filename.startswith("backup_") and filename.endswith(".db"):
            return "База данных"
        else:
            return "Неизвестный"
    
    async def notify_admin_backup_status(self, success: bool, backup_path: Optional[str] = None, error: Optional[str] = None) -> None:
        """Уведомить администратора о статусе резервного копирования"""
        try:
            settings = await self.get_backup_settings()
            if not settings.get("notify_admin", True) or not self.bot:
                return
            
            if success and backup_path:
                message = (
                    "✅ <b>Резервное копирование выполнено успешно</b>\n\n"
                    f"📁 <b>Файл:</b> <code>{Path(backup_path).name}</code>\n"
                    f"🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
                    f"💾 <b>Размер:</b> {self._format_file_size(Path(backup_path).stat().st_size)}"
                )
            else:
                message = (
                    "❌ <b>Ошибка резервного копирования</b>\n\n"
                    f"🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
                    f"❗ <b>Ошибка:</b> <code>{error or 'Неизвестная ошибка'}</code>"
                )
            
            # Отправляем уведомление всем администраторам
            for admin_id in ADMIN_IDS:
                try:
                    await self.bot.send_message(admin_id, message, disable_web_page_preview=True)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка уведомления о статусе бэкапа: {e}")

    async def notify_admin_backup_deleted(self, file_name: str, file_size: int) -> None:
        """Уведомить администратора об удалении резервной копии"""
        try:
            if not self.bot:
                return
            
            message = (
                "🗑️ <b>Резервная копия удалена</b>\n\n"
                f"📁 <b>Файл:</b> <code>{file_name}</code>\n"
                f"🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
                f"💾 <b>Размер:</b> {self._format_file_size(file_size)}"
            )
            
            # Отправляем уведомление всем администраторам
            for admin_id in ADMIN_IDS:
                try:
                    await self.bot.send_message(admin_id, message, disable_web_page_preview=True)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка уведомления об удалении бэкапа: {e}")

    async def create_project_export(self) -> Optional[str]:
        """Создать полный экспорт проекта (код + данные + настройки)"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Сократим имя файла для избежания ошибки BUTTON_DATA_INVALID
            export_path = self.backup_dir / f"project_export_{timestamp}.zip"
            
            logger.info(f"Создание полного экспорта проекта: {export_path}")
            
            # Путь к корню проекта (на уровень выше от backups)
            project_root = self.backup_dir.parent
            
            with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Добавляем все файлы проекта, исключая ненужные
                exclude_patterns = {
                    '__pycache__', '.git', '.env', 'node_modules', '.DS_Store',
                    'backups', 'temp', '.pytest_cache', 'logs', '*.log',
                    '.vscode', '.idea', '*.pyc', '*.pyo'
                }
                
                for root, dirs, files in os.walk(project_root):
                    # Фильтруем директории
                    dirs[:] = [d for d in dirs if not any(pattern in d for pattern in exclude_patterns)]
                    
                    for file in files:
                        # Пропускаем исключенные файлы
                        if any(pattern in file for pattern in exclude_patterns):
                            continue
                            
                        file_path = Path(root) / file
                        
                        # Создаем относительный путь от корня проекта
                        try:
                            rel_path = file_path.relative_to(project_root)
                            zipf.write(file_path, rel_path)
                            logger.debug(f"Добавлен в экспорт: {rel_path}")
                        except ValueError:
                            # Файл вне проекта, пропускаем
                            continue
                
                # Добавляем README для экспорта
                readme_content = self._generate_export_readme()
                zipf.writestr("EXPORT_README.md", readme_content)
            
            # Проверяем созданный экспорт
            if export_path.exists():
                export_size = export_path.stat().st_size
                logger.info(f"Экспорт проекта создан: {export_path}, размер: {export_size} байт")
                
                # Уведомляем администратора
                if self.bot:
                    await self.notify_admin_project_export(export_path.name, export_size)
                
                return str(export_path)
            else:
                logger.error("Экспорт проекта не был создан!")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка создания экспорта проекта: {e}")
            return None

    def _generate_export_readme(self) -> str:
        """Генерирует README для экспорта проекта"""
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        return f"""# 📦 Autoposter Bot - Полный экспорт проекта

**Дата экспорта:** {current_time}

## 📋 Содержимое экспорта

Этот архив содержит полную копию проекта Autoposter Bot:

### 📁 Исходный код:
- `bot.py` - главный файл бота
- `config.py` - конфигурация
- `handlers/` - обработчики команд
- `services/` - сервисы (AI, бэкапы, VK, etc.)
- `database/` - модули базы данных
- `utils/` - утилиты
- `managers/` - менеджеры
- `tests/` - тесты
- `docs/` - документация

### 📊 Данные:
- База данных SQLite с постами и настройками
- Конфигурационные файлы
- Docker файлы для развертывания

### 🚀 Восстановление проекта:

1. **Распакуйте архив** в желаемую директорию
2. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Настройте переменные окружения** в `.env` файле
4. **Запустите бота:**
   ```bash
   python bot.py
   ```

### 📝 Примечания:
- Убедитесь что у вас установлен Python 3.8+
- Настройте токены Telegram и VK API
- Проверьте настройки базы данных

**Создано системой резервного копирования Autoposter Bot**
"""

    async def notify_admin_project_export(self, file_name: str, file_size: int) -> None:
        """Уведомить администратора о создании экспорта проекта"""
        try:
            if not self.bot:
                return
            
            message = (
                "📦 <b>Экспорт проекта создан</b>\n\n"
                f"📁 <b>Файл:</b> <code>{file_name}</code>\n"
                f"🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
                f"💾 <b>Размер:</b> {self._format_file_size(file_size)}\n\n"
                f"📋 <b>Содержит:</b> полный исходный код + данные + настройки\n"
                f"🎯 <b>Назначение:</b> полное восстановление проекта на новом сервере"
            )
            
            # Отправляем уведомление всем администраторам
            for admin_id in ADMIN_IDS:
                try:
                    await self.bot.send_message(admin_id, message, disable_web_page_preview=True)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка уведомления об экспорте проекта: {e}")
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Форматировать размер файла в читаемом виде"""
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} ТБ"


# Глобальный экземпляр сервиса бэкапа
backup_service = BackupService()

# Функции-обертки для удобства использования
async def create_backup() -> Optional[str]:
    """Создать резервную копию"""
    return await backup_service.create_full_backup()

async def restore_backup(backup_path: str) -> bool:
    """Восстановить из резервной копии"""
    return await backup_service.restore_from_backup(backup_path)

async def get_backups() -> List[Dict]:
    """Получить список резервных копий"""
    return await backup_service.get_backup_list() 

async def delete_backup(backup_path: str) -> bool:
    """Удалить резервную копию"""
    return await backup_service.delete_backup(backup_path)

async def create_project_export() -> Optional[str]:
    """Создать полный экспорт проекта"""
    return await backup_service.create_project_export()