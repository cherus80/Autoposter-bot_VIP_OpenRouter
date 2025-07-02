#!/usr/bin/env python3
"""
Менеджер для управления Autoposter Bot
Позволяет запускать, останавливать и проверять статус бота
"""
import os
import sys
import signal
import subprocess
import time

def get_bot_pids():
    """Получает PID всех запущенных процессов bot.py"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        pids = []
        
        for line in lines:
            if 'bot.py' in line and 'grep' not in line:
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = int(parts[1])
                        pids.append(pid)
                    except ValueError:
                        continue
        return pids
    except Exception as e:
        print(f"❌ Ошибка получения PID: {e}")
        return []

def status():
    """Проверяет статус бота"""
    pids = get_bot_pids()
    
    if not pids:
        print("🔴 Бот не запущен")
        return False
    elif len(pids) == 1:
        print(f"🟢 Бот запущен (PID: {pids[0]})")
        return True
    else:
        print(f"⚠️ Найдено {len(pids)} копий бота (PID: {', '.join(map(str, pids))})")
        print("🔧 Рекомендуется остановить все копии и запустить заново")
        return True

def stop():
    """Останавливает все копии бота"""
    pids = get_bot_pids()
    
    if not pids:
        print("ℹ️ Бот уже остановлен")
        return
    
    print(f"🛑 Останавливаю {len(pids)} процесс(ов)...")
    
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"✅ Процесс {pid} остановлен")
        except ProcessLookupError:
            print(f"⚠️ Процесс {pid} уже не существует")
        except PermissionError:
            print(f"❌ Нет прав для остановки процесса {pid}")
        except Exception as e:
            print(f"❌ Ошибка остановки процесса {pid}: {e}")
    
    # Ждем немного и проверяем
    time.sleep(2)
    remaining_pids = get_bot_pids()
    
    if remaining_pids:
        print(f"⚠️ Принудительная остановка {len(remaining_pids)} процесс(ов)...")
        for pid in remaining_pids:
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"🔥 Процесс {pid} принудительно остановлен")
            except Exception as e:
                print(f"❌ Не удалось остановить процесс {pid}: {e}")

def start():
    """Запускает бота"""
    # Сначала проверяем, не запущен ли уже
    pids = get_bot_pids()
    if pids:
        print(f"⚠️ Бот уже запущен (PID: {', '.join(map(str, pids))})")
        choice = input("Остановить существующие процессы и запустить заново? (y/N): ")
        if choice.lower() in ['y', 'yes', 'д', 'да']:
            stop()
            time.sleep(1)
        else:
            print("❌ Отмена запуска")
            return
    
    print("🚀 Запускаю бота...")
    
    try:
        # Запускаем бота в фоне
        process = subprocess.Popen([sys.executable, 'bot.py'], 
                                 stdout=subprocess.DEVNULL, 
                                 stderr=subprocess.DEVNULL)
        
        # Ждем немного и проверяем
        time.sleep(3)
        
        if process.poll() is None:  # Процесс все еще работает
            print(f"✅ Бот успешно запущен (PID: {process.pid})")
        else:
            print("❌ Бот не смог запуститься. Проверьте логи:")
            print("python3 bot.py")
            
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")

def restart():
    """Перезапускает бота"""
    print("🔄 Перезапуск бота...")
    stop()
    time.sleep(2)
    start()

def main():
    if len(sys.argv) < 2:
        print("🤖 Менеджер Autoposter Bot")
        print("=" * 40)
        print("Использование:")
        print("  python3 bot_manager.py status   - проверить статус")
        print("  python3 bot_manager.py start    - запустить бота")
        print("  python3 bot_manager.py stop     - остановить бота")
        print("  python3 bot_manager.py restart  - перезапустить бота")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'status':
        status()
    elif command == 'start':
        start()
    elif command == 'stop':
        stop()
    elif command == 'restart':
        restart()
    else:
        print(f"❌ Неизвестная команда: {command}")
        print("Доступные команды: status, start, stop, restart")

if __name__ == "__main__":
    main() 