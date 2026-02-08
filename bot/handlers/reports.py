"""Report generation handlers"""
import logging
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from database.models import User, CreateReportDTO
from database.queries import create_report
from bot.queue import ReportQueue, ReportTask
from bot.states import CompareCardsStates
from bot.utils import send_loading_sticker

logger = logging.getLogger(__name__)

router = Router()


async def _show_compare_cards_prompt(keyboard: InlineKeyboardMarkup) -> tuple[str, InlineKeyboardMarkup]:
    """Generate compare cards prompt text and keyboard"""
    text = """🔍 <b>Сравнение карточек</b>

Отправьте артикулы товаров списком через запятую.

📋 <b>Правила:</b>
• Минимум 2 артикула
• Максимум 5 артикулов
• Артикулы через запятую

💡 <b>Примеры:</b>
<code>123456789,987654321</code>
<code>111111111,222222222,333333333</code>"""
    return text, keyboard


@router.callback_query(F.data == "compare_cards")
async def request_compare_cards_callback(callback: CallbackQuery, user: User, state: FSMContext):
    """Handle compare cards inline button - start comparison flow"""
    logger.info(f"User {user.id} clicked compare cards button via callback")
    
    await callback.answer()
    
    # Set state to waiting for articles
    await state.set_state(CompareCardsStates.waiting_for_articles)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_compare")]
    ])
    
    text, keyboard = await _show_compare_cards_prompt(keyboard)
    await callback.message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "cancel_compare")
async def cancel_compare_callback(callback: CallbackQuery, state: FSMContext):
    """Handle cancel compare button click"""
    user_id = callback.from_user.id
    logger.info(f"❌ [COMPARE] User {user_id} cancelled compare process")
    
    await state.clear()
    await callback.answer()
    await callback.message.delete()
    logger.info(f"✅ [COMPARE] Compare process cancelled and state cleared for user {user_id}")


@router.message(CompareCardsStates.waiting_for_articles, F.text)
async def process_articles(message: Message, user: User, report_queue: ReportQueue, state: FSMContext):
    """Process articles from user input"""
    logger.info(f"User {user.id} sent articles: {message.text}")
    
    # Check balance
    if user.reports_balance <= 0:
        await state.clear()
        await message.answer(
            "❌ <b>Недостаточно средств</b>\n\n"
            f"💰 Ваш баланс: {user.reports_balance} отчетов\n\n"
            "Пополните баланс для генерации отчетов."
        )
        return
    
    # Parse articles - split by comma and remove spaces
    args_text = (message.text or "").strip()
    
    if not args_text:
        await message.answer(
            "❌ <b>Не указаны артикулы</b>\n\n"
            "Отправьте артикулы через запятую.\n\n"
            "💡 Пример: <code>123456789,987654321</code>"
        )
        return
    
    try:
        articles_str = [a.strip() for a in args_text.split(",")]
        articles = [int(a) for a in articles_str if a]
    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат артикулов</b>\n\n"
            "Артикулы должны быть числами, разделенными запятыми.\n\n"
            "💡 Пример: <code>123456789,987654321</code>"
        )
        return
    
    # Validate count
    if len(articles) < 2:
        await message.answer(
            "❌ <b>Слишком мало артикулов</b>\n\n"
            "Для сравнения нужно минимум 2 артикула.\n\n"
            "💡 Пример: <code>123456789,987654321</code>"
        )
        return
    
    if len(articles) > 5:
        await message.answer(
            "❌ <b>Слишком много артикулов</b>\n\n"
            "Максимум 5 артикулов для сравнения.\n\n"
            "💡 Пример: <code>111,222,333,444,555</code>"
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
    
    # Create report record in DB with state NEW
    report = await create_report(CreateReportDTO(
        user_id=user.id,
        articles=articles_text,
    ))
    report_id = report.id if report else None
    if report:
        logger.info(f"📝 Created report {report.id} for user {user.id}")
    else:
        logger.warning(f"⚠️ Failed to create report record for user {user.id}")
    
    # Send animated loading sticker
    sticker_msg_id = await send_loading_sticker(message)
    
    # Create task with sticker message ID and report ID
    task = ReportTask.create(
        user_id=user.id,
        chat_id=message.chat.id,
        articles=articles,
        report_id=report_id,
        loading_message_id=sticker_msg_id,
    )
    
    # Add to queue
    await report_queue.add_task(task)
    
    # Clear state after adding task to queue
    await state.clear()
    
    logger.info(f"Created compare task {task.task_id} with {len(articles)} articles, report_id={report_id}")
