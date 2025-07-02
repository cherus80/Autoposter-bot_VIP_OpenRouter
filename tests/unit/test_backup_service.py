"""
@file: tests/unit/test_backup_service.py
@description: Модульные тесты для сервиса резервного копирования
@dependencies: pytest, unittest.mock
@created: 2025-01-21
"""

import pytest
import asyncio
import tempfile
import json
import zipfile
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
from services.backup_service import BackupService


@pytest.mark.unit
@pytest.mark.backup
class TestBackupService:
    """Тестирование сервиса резервного копирования"""
    
    @pytest.fixture
    def backup_service(self, temp_backup_dir):
        """Создание экземпляра BackupService для тестов"""
        service = BackupService()
        service.backup_dir = temp_backup_dir
        return service
    
    @pytest.fixture
    def mock_async_session_maker(self):
        """Мокированная фабрика сессий"""
        session_mock = AsyncMock()
        session_mock.execute = AsyncMock()
        session_mock.commit = AsyncMock()
        session_mock.close = AsyncMock()
        
        async_session_maker_mock = AsyncMock()
        async_session_maker_mock.return_value.__aenter__ = AsyncMock(return_value=session_mock)
        async_session_maker_mock.return_value.__aexit__ = AsyncMock(return_value=None)
        
        return async_session_maker_mock
    
    @pytest.mark.asyncio
    async def test_get_backup_settings_default(self, backup_service):
        """Тест получения настроек по умолчанию"""
        with patch('database.settings_db.get_setting') as mock_get_setting:
            mock_get_setting.side_effect = lambda key, default: str(default)
            
            settings = await backup_service.get_backup_settings()
            
            assert settings["backup_enabled"] is True
            assert settings["backup_interval_hours"] == 24
            assert settings["max_backups"] == 7
    
    @pytest.mark.asyncio
    async def test_update_backup_settings(self, backup_service):
        """Тест обновления настроек резервного копирования"""
        new_settings = {
            "backup_enabled": False,
            "backup_interval_hours": 12,
            "max_backups": 5
        }
        
        with patch('database.settings_db.update_setting') as mock_update:
            mock_update.return_value = AsyncMock()
            
            result = await backup_service.update_backup_settings(new_settings)
            
            assert result is True
            assert mock_update.call_count == len(new_settings)
    
    @pytest.mark.asyncio
    async def test_create_database_backup_success(self, backup_service, temp_db_path):
        """Тест успешного создания резервной копии БД"""
        # Создаем тестовую БД
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'test')")
        conn.commit()
        conn.close()
        
        with patch('database.database.db_path', temp_db_path), \
             patch.object(backup_service, '_verify_backup', return_value=True):
            
            result = await backup_service.create_database_backup()
            
            assert result is not None
            assert Path(result).exists()
            assert Path(result).suffix == '.db'
    
    @pytest.mark.asyncio
    async def test_create_database_backup_verification_failed(self, backup_service, temp_db_path):
        """Тест создания бэкапа с неудачной верификацией"""
        with patch('database.database.db_path', temp_db_path), \
             patch.object(backup_service, '_verify_backup', return_value=False):
            
            result = await backup_service.create_database_backup()
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_verify_backup_success(self, backup_service, temp_db_path):
        """Тест успешной проверки целостности бэкапа"""
        # Создаем валидную БД
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()
        
        result = await backup_service._verify_backup(temp_db_path)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_verify_backup_corrupted(self, backup_service, temp_backup_dir):
        """Тест проверки поврежденного бэкапа"""
        # Создаем поврежденный файл
        corrupted_file = temp_backup_dir / "corrupted.db"
        corrupted_file.write_text("invalid database content")
        
        result = await backup_service._verify_backup(str(corrupted_file))
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_create_settings_backup(self, backup_service, mock_async_session_maker):
        """Тест создания резервной копии настроек"""
        # Мокируем данные из БД
        mock_settings_result = Mock()
        mock_settings_result.fetchall.return_value = [
            ("key1", "value1", "desc1"),
            ("key2", "value2", "desc2")
        ]
        
        mock_prompts_result = Mock()
        mock_prompts_result.fetchall.return_value = [
            (1, "content_text", "Test prompt"),
            (2, "image_generation", "Image prompt")
        ]
        
        mock_pub_settings_result = Mock()
        mock_pub_settings_result.fetchall.return_value = [
            (123456, True, False)
        ]
        
        with patch('database.database.async_session_maker', mock_async_session_maker):
            session_mock = await mock_async_session_maker().__aenter__()
            session_mock.execute.side_effect = [
                mock_settings_result,
                mock_prompts_result,
                mock_pub_settings_result
            ]
            
            result = await backup_service.create_settings_backup()
            
            assert result is not None
            assert Path(result).exists()
            assert Path(result).suffix == '.json'
            
            # Проверяем содержимое файла
            with open(result, 'r', encoding='utf-8') as f:
                data = json.load(f)
                assert 'backup_created' in data
                assert 'data' in data
                assert 'settings' in data['data']
                assert 'prompts' in data['data']
    
    @pytest.mark.asyncio
    async def test_create_full_backup(self, backup_service):
        """Тест создания полного бэкапа"""
        with patch.object(backup_service, 'create_database_backup') as mock_db_backup, \
             patch.object(backup_service, 'create_settings_backup') as mock_settings_backup:
            
            mock_db_backup.return_value = "/path/to/db_backup.db"
            mock_settings_backup.return_value = "/path/to/settings_backup.json"
            
            result = await backup_service.create_full_backup()
            
            assert result is not None
            assert result.endswith('.zip')
            
            mock_db_backup.assert_called_once()
            mock_settings_backup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_restore_from_backup_database(self, backup_service, temp_db_path):
        """Тест восстановления из резервной копии БД"""
        # Создаем тестовую резервную копию
        backup_db = temp_db_path + ".backup"
        import sqlite3
        conn = sqlite3.connect(backup_db)
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'restored')")
        conn.commit()
        conn.close()
        
        with patch.object(backup_service, 'create_database_backup') as mock_backup:
            mock_backup.return_value = "/path/to/safety_backup.db"
            
            result = await backup_service.restore_from_backup(backup_db, "database")
            
            assert result is True
            mock_backup.assert_called_once()  # Проверяем создание safety backup
    
    @pytest.mark.asyncio
    async def test_restore_from_backup_settings(self, backup_service, temp_backup_dir):
        """Тест восстановления настроек из бэкапа"""
        # Создаем тестовый файл настроек
        settings_backup = {
            "backup_type": "settings",
            "data": {
                "settings": {
                    "key1": {"value": "value1", "description": "desc1"}
                },
                "prompts": {
                    "content_text_1": "Test prompt"
                },
                "publishing_settings": {
                    123456: {"telegram": True, "vk": False}
                }
            }
        }
        
        settings_file = temp_backup_dir / "settings_backup.json"
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings_backup, f)
        
        with patch('database.settings_db.update_setting') as mock_update:
            mock_update.return_value = AsyncMock()
            
            result = await backup_service._restore_settings(str(settings_file))
            
            assert result is True
            assert mock_update.called
    
    @pytest.mark.asyncio
    async def test_cleanup_old_backups(self, backup_service, temp_backup_dir):
        """Тест очистки старых бэкапов"""
        # Создаем несколько тестовых бэкапов
        for i in range(10):
            backup_file = temp_backup_dir / f"backup_{i}.db"
            backup_file.touch()
        
        with patch.object(backup_service, 'get_backup_settings') as mock_settings:
            mock_settings.return_value = {"max_backups": 5}
            
            await backup_service.cleanup_old_backups()
            
            # Должно остаться только 5 файлов
            remaining_files = list(temp_backup_dir.glob("backup_*.db"))
            assert len(remaining_files) == 5
    
    @pytest.mark.asyncio
    async def test_get_backup_list(self, backup_service, temp_backup_dir):
        """Тест получения списка бэкапов"""
        # Создаем тестовые файлы бэкапов
        db_backup = temp_backup_dir / "backup_20250121_120000_autoposting_bot.db"
        settings_backup = temp_backup_dir / "settings_backup_20250121_120000.json"
        full_backup = temp_backup_dir / "full_backup_20250121_120000.zip"
        
        db_backup.write_text("test db content")
        settings_backup.write_text('{"test": "settings"}')
        full_backup.write_text("test zip content")
        
        backups = await backup_service.get_backup_list()
        
        assert len(backups) == 3
        assert all('type' in backup for backup in backups)
        assert all('size' in backup for backup in backups)
        assert all('created' in backup for backup in backups)
    
    @pytest.mark.asyncio
    async def test_notify_admin_backup_status_success(self, backup_service, mock_bot):
        """Тест уведомления администратора об успешном бэкапе"""
        backup_service.bot = mock_bot
        
        with patch('config.ADMIN_IDS', [123456, 789012]):
            await backup_service.notify_admin_backup_status(
                True, "/path/to/backup.zip"
            )
            
            assert mock_bot.send_message.call_count == 2
    
    @pytest.mark.asyncio
    async def test_notify_admin_backup_status_error(self, backup_service, mock_bot):
        """Тест уведомления администратора об ошибке бэкапа"""
        backup_service.bot = mock_bot
        
        with patch('config.ADMIN_IDS', [123456]):
            await backup_service.notify_admin_backup_status(
                False, error="Test error message"
            )
            
            mock_bot.send_message.assert_called_once()
            call_args = mock_bot.send_message.call_args
            assert "❌" in call_args[0][1]  # Проверяем наличие emoji ошибки
    
    def test_determine_backup_type(self, backup_service):
        """Тест определения типа бэкапа по имени файла"""
        assert backup_service._determine_backup_type("backup_123.db") == "База данных"
        assert backup_service._determine_backup_type("settings_backup.json") == "Настройки"
        assert backup_service._determine_backup_type("full_backup.zip") == "Полный бэкап"
        assert backup_service._determine_backup_type("unknown.txt") == "Неизвестный"
    
    def test_format_file_size(self, backup_service):
        """Тест форматирования размера файла"""
        assert backup_service._format_file_size(500) == "500 B"
        assert backup_service._format_file_size(1536) == "1.5 KB"
        assert backup_service._format_file_size(2097152) == "2.0 MB"
        assert backup_service._format_file_size(1073741824) == "1.0 GB"
    
    @pytest.mark.asyncio
    async def test_create_backup_with_custom_name(self, backup_service):
        """Тест создания бэкапа с кастомным именем"""
        custom_name = "custom_backup_test.db"
        
        with patch.object(backup_service, '_copy_database') as mock_copy, \
             patch.object(backup_service, '_verify_backup', return_value=True):
            
            result = await backup_service.create_database_backup(custom_name)
            
            assert result is not None
            assert custom_name in result
            mock_copy.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_backup_operations(self, backup_service):
        """Тест конкурентных операций резервного копирования"""
        with patch.object(backup_service, 'create_database_backup') as mock_db, \
             patch.object(backup_service, 'create_settings_backup') as mock_settings:
            
            mock_db.return_value = "/path/to/db.db"
            mock_settings.return_value = "/path/to/settings.json"
            
            # Запускаем несколько операций одновременно
            tasks = [
                backup_service.create_database_backup(),
                backup_service.create_settings_backup(),
                backup_service.create_full_backup()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Все операции должны завершиться без исключений
            assert len(results) == 3
            assert not any(isinstance(r, Exception) for r in results)
    
    @pytest.mark.asyncio
    async def test_backup_with_insufficient_space(self, backup_service):
        """Тест обработки нехватки места для бэкапа"""
        with patch.object(backup_service, '_copy_database') as mock_copy:
            mock_copy.side_effect = OSError("No space left on device")
            
            result = await backup_service.create_database_backup()
            
            assert result is None 