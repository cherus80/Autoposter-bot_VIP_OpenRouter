"""
@file: handlers/content_plan.py
@description: Обработчики загрузки и управления контент-планом
@dependencies: managers/content_plan_manager.py
@created: 2025-01-20
"""

import logging
import json
import csv
import io
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, Document

from managers.content_plan_manager import ContentPlanManager

logger = logging.getLogger(__name__)
router = Router()
content_manager = ContentPlanManager()

# FSM для загрузки контент-плана
class UploadContentPlan(StatesGroup):
    waiting_for_file = State()

class ViewContentPlan(StatesGroup):
    viewing_all = State()
    viewing_unused = State() 
    viewing_used = State()
    selecting_topic = State()

@router.callback_query(F.data == "menu:upload_content_plan")
async def cb_upload_content_plan(cb: CallbackQuery, state: FSMContext):
    """Загрузка контент-плана"""
    await state.set_state(UploadContentPlan.waiting_for_file)
    
    await cb.message.edit_text(
        f"📅 <b>Загрузка контент-плана</b>\n\n"
        f"Отправьте файл с контент-планом в одном из форматов:\n\n"
        f"📄 <b>JSON:</b>\n"
        f"<code>[\n"
        f'  {{"category": "ai_news", "theme": "Тема поста", "post_description": "Описание"}},\n'
        f'  {{"category": "tutorials", "theme": "Тема 2", "post_description": "Описание 2"}}\n'
        f"]</code>\n\n"
        f"📊 <b>CSV:</b>\n"
        f"<code>category,theme,post_description\n"
        f"ai_news,Тема поста,Описание\n"
        f"tutorials,Тема 2,Описание 2</code>\n\n"
        f"💡 <b>Поля:</b>\n"
        f"• category - категория (опционально)\n"
        f"• theme - тема поста (обязательно)\n"
        f"• post_description - описание/детали (опционально)",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📋 Показать пример", callback_data="content:example")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="content:cancel")]
            ]
        )
    )
    await cb.answer()

@router.message(UploadContentPlan.waiting_for_file, F.document)
async def process_content_file(msg: Message, state: FSMContext):
    """Обработка загруженного файла с контент-планом"""
    document: Document = msg.document
    
    # Проверяем размер файла (максимум 5MB)
    if document.file_size > 5 * 1024 * 1024:
        await msg.answer("❌ Файл слишком большой! Максимум 5MB.")
        return
    
    # Проверяем расширение файла
    filename = document.file_name.lower()
    if not (filename.endswith('.json') or filename.endswith('.csv')):
        await msg.answer("❌ Поддерживаются только файлы .json и .csv")
        return
    
    try:
        # Скачиваем файл
        file = await msg.bot.get_file(document.file_id)
        file_content = await msg.bot.download_file(file.file_path)
        
        # Читаем содержимое
        content_text = file_content.read().decode('utf-8')
        
        # Парсим в зависимости от формата
        if filename.endswith('.json'):
            content_items = await parse_json_content(content_text)
        else:  # CSV
            content_items = await parse_csv_content(content_text)
        
        if not content_items:
            await msg.answer("❌ Файл пустой или имеет неверный формат!")
            return
        
        # Сохраняем контент-план
        success_count = await content_manager.add_content_items(content_items)
        
        await msg.answer(
            f"✅ <b>Контент-план загружен!</b>\n\n"
            f"📊 Обработано: {len(content_items)} тем\n"
            f"✅ Добавлено: {success_count} новых тем\n"
            f"🔄 Пропущено: {len(content_items) - success_count} дубликатов",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📋 Показать план", callback_data="content:show")],
                    [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu")]
                ]
            )
        )
        
        logger.info(f"Контент-план загружен: {success_count} новых тем из {len(content_items)}")
        
    except Exception as e:
        logger.error(f"Ошибка загрузки контент-плана: {e}")
        await msg.answer(f"❌ Ошибка обработки файла: {str(e)}")
    
    await state.clear()

@router.message(UploadContentPlan.waiting_for_file, ~F.document)
async def process_invalid_content(msg: Message):
    """Обработка неверного типа сообщения"""
    await msg.answer("❌ Пожалуйста, отправьте файл (.json или .csv)")

async def parse_json_content(content_text: str) -> list:
    """Парсинг JSON контент-плана"""
    try:
        data = json.loads(content_text)
        
        if not isinstance(data, list):
            raise ValueError("JSON должен содержать массив объектов")
        
        content_items = []
        for item in data:
            if not isinstance(item, dict) or 'theme' not in item:
                continue
            
            content_items.append({
                'category': item.get('category', ''),
                'theme': item['theme'],
                'post_description': item.get('post_description', '')
            })
        
        return content_items
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Неверный формат JSON: {e}")

async def parse_csv_content(content_text: str) -> list:
    """Парсинг CSV контент-плана"""
    try:
        csv_reader = csv.DictReader(io.StringIO(content_text))
        content_items = []
        
        for row in csv_reader:
            if 'theme' not in row or not row['theme'].strip():
                continue
            
            content_items.append({
                'category': row.get('category', '').strip(),
                'theme': row['theme'].strip(),
                'post_description': row.get('post_description', '').strip()
            })
        
        return content_items
        
    except Exception as e:
        raise ValueError(f"Ошибка парсинга CSV: {e}")

@router.callback_query(F.data == "content:example")
async def cb_content_example(cb: CallbackQuery):
    """Показать пример файлов"""
    example_text = f"""📋 <b>Примеры файлов контент-плана</b>

 🗂️ <b>JSON пример (content_plan.json):</b>
 <code>[
   {{
     "category": "ai_tools",
     "theme": "5 лучших AI инструментов для работы",
     "post_description": "Обзор популярных инструментов с примерами"
   }},
   {{
     "category": "tutorials",
     "theme": "Как настроить ChatGPT для бизнеса",
     "post_description": "Пошаговая инструкция"
   }},
   {{
     "category": "automation",
     "theme": "Автоматизация соцсетей",
     "post_description": "Практические советы по автоматизации"
   }}
 ]</code>

 📊 <b>CSV пример (content_plan.csv):</b>
 <code>category,theme,post_description
 "ai_tools","5 лучших AI инструментов для работы","Обзор популярных инструментов"
 "tutorials","Как настроить ChatGPT для бизнеса","Пошаговая инструкция"
 "automation","Автоматизация соцсетей","Практические советы"</code>"""

    await cb.message.answer(
        example_text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:upload_content_plan")]]
        )
    )
    await cb.answer()

@router.callback_query(F.data == "content:show")
async def cb_show_content_plan(cb: CallbackQuery):
    """Показать меню просмотра контент-плана"""
    unused_count = await content_manager.count_unused_items()
    used_count = await content_manager.count_used_items()
    total_count = await content_manager.count_all_items()
    
    if total_count == 0:
        await cb.message.edit_text(
            "📅 <b>Контент-план пуст</b>\n\n"
            "Загрузите файл с темами для постов.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📤 Загрузить план", callback_data="menu:upload_content_plan")],
                    [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu")]
                ]
            )
        )
        return
    
    plan_text = f"📅 <b>Управление контент-планом</b>\n\n"
    plan_text += f"📊 <b>Статистика:</b>\n"
    plan_text += f"• Всего тем: {total_count}\n"
    plan_text += f"• Неопубликованных: {unused_count}\n"
    plan_text += f"• Опубликованных: {used_count}\n\n"
    plan_text += f"Выберите действие:"
    
    keyboard = [
        [InlineKeyboardButton(text=f"📋 Все темы ({total_count})", callback_data="content:view_all")],
        [InlineKeyboardButton(text=f"🔄 Неопубликованные ({unused_count})", callback_data="content:view_unused")],
        [InlineKeyboardButton(text=f"✅ Опубликованные ({used_count})", callback_data="content:view_used")],
        [InlineKeyboardButton(text="🗑️ Очистить план", callback_data="content:clear")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu")]
    ]
    
    await cb.message.edit_text(
        plan_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await cb.answer()

@router.callback_query(F.data == "content:clear")
async def cb_clear_content_plan(cb: CallbackQuery):
    """Очистить контент-план с подтверждением"""
    total_count = await content_manager.count_all_items()
    unused_count = await content_manager.count_unused_items()
    
    await cb.message.edit_text(
        f"⚠️ <b>Подтверждение очистки</b>\n\n"
        f"❌ <b>ВНИМАНИЕ!</b> Это действие нельзя отменить.\n\n"
        f"📊 <b>Будет удалено:</b>\n"
        f"• Всего тем: <b>{total_count}</b>\n"
        f"• Неопубликованных: <b>{unused_count}</b>\n"
        f"• Опубликованных: <b>{total_count - unused_count}</b>\n\n"
        f"🗑️ Вы уверены, что хотите <b>безвозвратно удалить</b> все темы из контент-плана?\n\n"
        f"💡 <i>Рекомендуем сделать резервную копию перед очисткой.</i>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⚠️ Да, удалить ВСЕ", callback_data="content:confirm_clear")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="content:show")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
            ]
        )
    )
    await cb.answer()

@router.callback_query(F.data == "content:confirm_clear")
async def cb_confirm_clear_content_plan(cb: CallbackQuery):
    """Подтвержденная очистка контент-плана"""
    try:
        total_deleted = await content_manager.clear_all_items()
        
        await cb.message.edit_text(
            f"✅ <b>Контент-план очищен</b>\n\n"
            f"🗑️ Удалено тем: <b>{total_deleted}</b>\n"
            f"📂 Контент-план теперь пустой.\n\n"
            f"💡 <i>Загрузите новый план для продолжения работы.</i>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📂 Загрузить новый план", callback_data="menu:upload_content_plan")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
                ]
            )
        )
        await cb.answer("✅ Контент-план очищен!")
        
    except Exception as e:
        logger.error(f"Ошибка при очистке контент-плана: {e}")
        await cb.message.edit_text(
            f"❌ <b>Ошибка при очистке</b>\n\n"
            f"Не удалось очистить контент-план.\n"
            f"Попробуйте позже или обратитесь к администратору.\n\n"
            f"🔧 <i>Код ошибки: {str(e)[:50]}...</i>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="content:clear")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
                ]
            )
        )
        await cb.answer("❌ Ошибка при очистке")

@router.callback_query(F.data == "content:view_all")
async def cb_view_all_topics(cb: CallbackQuery, state: FSMContext):
    """Просмотр всех тем"""
    await state.set_state(ViewContentPlan.viewing_all)
    await show_topics_page(cb, "all", 0)

@router.callback_query(F.data == "content:view_unused")
async def cb_view_unused_topics(cb: CallbackQuery, state: FSMContext):
    """Просмотр неопубликованных тем"""
    await state.set_state(ViewContentPlan.viewing_unused)
    await show_topics_page(cb, "unused", 0)

@router.callback_query(F.data == "content:view_used")
async def cb_view_used_topics(cb: CallbackQuery, state: FSMContext):
    """Просмотр опубликованных тем"""
    await state.set_state(ViewContentPlan.viewing_used)
    await show_topics_page(cb, "used", 0)

async def show_topics_page(cb: CallbackQuery, topic_type: str, page: int):
    """Показать страницу с темами"""
    limit = 5
    offset = page * limit
    
    if topic_type == "all":
        items = await content_manager.get_all_items(limit=limit, offset=offset)
        total_count = await content_manager.count_all_items()
        title = "📋 Все темы"
    elif topic_type == "unused":
        items = await content_manager.get_unused_items(limit=limit, offset=offset)
        total_count = await content_manager.count_unused_items()
        title = "🔄 Неопубликованные темы"
    else:  # used
        items = await content_manager.get_used_items(limit=limit, offset=offset)
        total_count = await content_manager.count_used_items()
        title = "✅ Опубликованные темы"
    
    if not items:
        text = f"{title}\n\nТемы не найдены."
        keyboard = [[InlineKeyboardButton(text="⬅️ Назад", callback_data="content:show")]]
    else:
        text = f"{title} (стр. {page + 1})\n\n"
        
        for i, item in enumerate(items, 1):
            status_icon = "✅" if item.used else "🔄"
            category_icon = "📂" if item.category else "📝"
            text += f"{status_icon} {category_icon} <b>{item.theme}</b>\n"
            if item.category:
                text += f"   🏷️ <i>{item.category}</i>\n"
            if item.post_description:
                desc = item.post_description[:80] + "..." if len(item.post_description) > 80 else item.post_description
                text += f"   💭 <i>{desc}</i>\n"
            
            # Кнопка действия для каждой темы
            action_text = "🔄 Восстановить" if item.used else "ℹ️ Подробнее"
            text += f"   👆 /{item.id} - {action_text}\n\n"
        
        # Пагинация
        keyboard = []
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="◀️ Пред", callback_data=f"content:page_{topic_type}_{page-1}"))
        if (page + 1) * limit < total_count:
            nav_row.append(InlineKeyboardButton(text="След ▶️", callback_data=f"content:page_{topic_type}_{page+1}"))
        
        if nav_row:
            keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="content:show")])
        
        text += f"\n💡 <i>Отправьте /{'{'}ID{'}'} для действий с темой</i>"
    
    await cb.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await cb.answer()

@router.callback_query(F.data.startswith("content:page_"))
async def cb_content_page(cb: CallbackQuery):
    """Обработка пагинации"""
    # Формат: content:page_topic_type_page_number
    # Убираем префикс "content:page_" и разделяем остаток
    data_parts = cb.data[13:]  # Убираем "content:page_"
    parts = data_parts.rsplit("_", 1)  # Разделяем с конца, чтобы получить topic_type и page
    
    if len(parts) != 2:
        await cb.answer("❌ Ошибка навигации")
        return
    
    topic_type, page_str = parts
    try:
        page = int(page_str)
        await show_topics_page(cb, topic_type, page)
    except ValueError:
        await cb.answer("❌ Ошибка номера страницы")

@router.message(ViewContentPlan.viewing_all, F.text.startswith("/"))
@router.message(ViewContentPlan.viewing_unused, F.text.startswith("/"))
@router.message(ViewContentPlan.viewing_used, F.text.startswith("/"))
async def process_topic_command(msg: Message, state: FSMContext):
    """Обработка команд для работы с темами"""
    try:
        topic_id = int(msg.text[1:])  # Убираем "/"
        topic = await content_manager.get_topic_by_id(topic_id)
        
        if not topic:
            await msg.answer("❌ Тема не найдена")
            return
        
        status_text = "✅ Опубликована" if topic.used else "🔄 Не опубликована"
        
        text = f"📋 <b>Детали темы #{topic.id}</b>\n\n"
        text += f"📊 <b>Статус:</b> {status_text}\n"
        if topic.category:
            text += f"🏷️ <b>Категория:</b> {topic.category}\n"
        text += f"📝 <b>Тема:</b> {topic.theme}\n"
        if topic.post_description:
            text += f"💭 <b>Описание:</b> {topic.post_description}\n"
        
        keyboard = []
        if topic.used:
            keyboard.append([InlineKeyboardButton(text="🔄 Восстановить тему", callback_data=f"content:restore_{topic.id}")])
        
        keyboard.append([InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="content:back_to_list")])
        
        await msg.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    except ValueError:
        await msg.answer("❌ Неверный формат команды. Используйте: /123")

@router.callback_query(F.data.startswith("content:restore_"))
async def cb_restore_topic(cb: CallbackQuery):
    """Восстановление темы"""
    topic_id = int(cb.data.split("_")[2])
    
    success = await content_manager.restore_topic(topic_id)
    
    if success:
        await cb.answer("✅ Тема восстановлена!")
        topic = await content_manager.get_topic_by_id(topic_id)
        
        text = f"📋 <b>Тема #{topic.id} восстановлена</b>\n\n"
        text += f"📊 <b>Статус:</b> 🔄 Не опубликована\n"
        if topic.category:
            text += f"🏷️ <b>Категория:</b> {topic.category}\n"
        text += f"📝 <b>Тема:</b> {topic.theme}\n"
        if topic.post_description:
            text += f"💭 <b>Описание:</b> {topic.post_description}\n"
        
        await cb.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="content:back_to_list")]]
            )
        )
    else:
        await cb.answer("❌ Ошибка восстановления")

@router.callback_query(F.data == "content:back_to_list")
async def cb_back_to_list(cb: CallbackQuery, state: FSMContext):
    """Возврат к списку тем"""
    current_state = await state.get_state()
    
    if current_state == ViewContentPlan.viewing_all.state:
        await show_topics_page(cb, "all", 0)
    elif current_state == ViewContentPlan.viewing_unused.state:
        await show_topics_page(cb, "unused", 0) 
    elif current_state == ViewContentPlan.viewing_used.state:
        await show_topics_page(cb, "used", 0)
    else:
        await cb_show_content_plan(cb)

@router.callback_query(F.data == "content:cancel")
async def cb_content_cancel(cb: CallbackQuery, state: FSMContext):
    """Отмена загрузки контент-плана"""
    await state.clear()
    await cb.answer("❌ Загрузка отменена")
    
    # Возвращаемся в главное меню
    from handlers.menu import build_main_menu_keyboard
    await cb.message.edit_text(
        "🤖 <b>Главное меню бота</b>\n\n"
        "Выберите нужное действие:",
        reply_markup=build_main_menu_keyboard()
    ) 