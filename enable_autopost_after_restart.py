#!/usr/bin/env python3
import asyncio
from database.settings_db import update_setting

async def enable_autopost():
    await update_setting('auto_mode_status', 'on')
    await update_setting('auto_posting_enabled', '1')
    print("✅ Автопостинг включен с безопасной моделью")

if __name__ == "__main__":
    asyncio.run(enable_autopost())
