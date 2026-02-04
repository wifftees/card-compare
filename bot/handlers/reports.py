"""Report generation handlers"""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from database.models import User
from bot.queue import ReportQueue, ReportTask

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "🔍 Сравнение карточек")
async def request_compare_cards_menu(message: Message, user: User):
    """Handle compare cards menu button"""
    logger.info(f"User {user.id} clicked compare cards button")
    
    await message.answer(
        "🔍 <b>Сравнение карточек</b>\n\n"
        "Для сравнения карточек используйте команду:\n"
        "<code>/compare артикул1,артикул2,...</code>\n\n"
        "📋 <b>Правила:</b>\n"
        "• Минимум 2 артикула\n"
        "• Максимум 5 артикулов\n"
        "• Артикулы через запятую\n\n"
        "💡 <b>Примеры:</b>\n"
        "<code>/compare 123456789,987654321</code>\n"
        "<code>/compare 111111111,222222222,333333333</code>"
    )


@router.message(Command("compare"))
async def cmd_compare(message: Message, user: User, report_queue: ReportQueue):
    """Handle /compare command"""
    logger.info(f"User {user.id} requested compare command")
    
    # Check balance
    if user.reports_balance <= 0:
        await message.answer(
            "❌ <b>Недостаточно средств</b>\n\n"
            f"💰 Ваш баланс: {user.reports_balance} отчетов\n\n"
            "Пополните баланс для генерации отчетов."
        )
        return
    
    # Parse command arguments
    command_text = message.text or ""
    # Remove /compare command
    args_text = command_text.replace("/compare", "").strip()
    
    if not args_text:
        await message.answer(
            "❌ <b>Не указаны артикулы</b>\n\n"
            "Используйте: <code>/compare артикул1,артикул2,...</code>\n\n"
            "💡 Пример: <code>/compare 123456789,987654321</code>"
        )
        return
    
    # Parse articles - split by comma and remove spaces
    try:
        articles_str = [a.strip() for a in args_text.split(",")]
        articles = [int(a) for a in articles_str if a]
    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат артикулов</b>\n\n"
            "Артикулы должны быть числами, разделенными запятыми.\n\n"
            "💡 Пример: <code>/compare 123456789,987654321</code>"
        )
        return
    
    # Validate count
    if len(articles) < 2:
        await message.answer(
            "❌ <b>Слишком мало артикулов</b>\n\n"
            "Для сравнения нужно минимум 2 артикула.\n\n"
            "💡 Пример: <code>/compare 123456789,987654321</code>"
        )
        return
    
    if len(articles) > 5:
        await message.answer(
            "❌ <b>Слишком много артикулов</b>\n\n"
            "Максимум 5 артикулов для сравнения.\n\n"
            "💡 Пример: <code>/compare 111,222,333,444,555</code>"
        )
        return
    
    # Send info message
    articles_text = ", ".join(str(a) for a in articles)
    queue_size = report_queue.qsize() + 1  # +1 for current task
    
    await message.answer(
        f"✅ <b>Задача добавлена в очередь</b>\n\n"
        f"📦 Артикулы: <code>{articles_text}</code>\n"
        f"📊 Позиция в очереди: {queue_size}\n\n"
        f"⏳ Ожидайте, отчет будет готов через несколько минут...\n"
        f"💰 После генерации будет списано: 1 отчет"
    )
    
    # Send animated loading sticker
    sticker_msg = await message.answer_sticker(
        sticker="CAACAgIAAxkBAAEVqDFpf0pGFIP-sRsnvOx-jWd1idNYOwACtCMAAphLKUjeub7NKlvk2TgE"
    )
    
    # Create task with sticker message ID
    task = ReportTask.create(
        user_id=user.id,
        chat_id=message.chat.id,
        articles=articles,
        loading_message_id=sticker_msg.message_id
    )
    
    # Add to queue
    await report_queue.add_task(task)
    
    logger.info(f"Created compare task {task.task_id} with {len(articles)} articles, sticker_msg_id={sticker_msg.message_id}")
