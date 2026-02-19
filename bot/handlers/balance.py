"""Balance handler"""
import logging
from aiogram import Router, F
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext

from database.models import User, ProductOption, EventType, CreateEventDTO
from database.queries import create_event
from bot.states import RefillBalanceStates
from bot.utils import LoadingSticker
from payment.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = Router()


async def _show_balance_text(user: User, keyboard: InlineKeyboardMarkup) -> tuple[str, InlineKeyboardMarkup]:
    """Generate balance text and keyboard"""
    balance_text = f"""
💰 <b>Ваш баланс</b>

Доступно отчетов: <b>{user.reports_balance}</b>
"""
    return balance_text, keyboard


@router.callback_query(F.data == "balance")
async def show_balance_callback(callback: CallbackQuery, user: User):
    """Show user balance and refill options from inline button"""
    logger.info(f"User {user.id} requested balance via callback")
    
    # Track CLICK_BALANCE event
    await create_event(CreateEventDTO(user_id=user.id, event_type=EventType.CLICK_BALANCE))
    
    await callback.answer()
    
    async with LoadingSticker(callback.message, callback.bot):
        # Get prices from database
        from database.queries import get_price_by_option
        
        single_price = await get_price_by_option(ProductOption.SINGLE)
        packet_price = await get_price_by_option(ProductOption.PACKET)
        
        if single_price is None or packet_price is None:
            logger.error(f"❌ Failed to fetch prices from database for user {user.id}")
            await callback.message.answer(
                "❌ Ошибка загрузки цен. Попробуйте позже."
            )
            return
        
        logger.info(
            f"💰 Loaded prices for user {user.id}: "
            f"SINGLE={single_price.price} RUB, PACKET={packet_price.price} RUB"
        )
        
        # Create keyboard with pricing options
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"📄 1 отчет - {single_price.price} ₽", 
                callback_data="buy_single"
            )],
            [InlineKeyboardButton(
                text=f"📦 Пакет ({packet_price.reports_amount} отчетов) - {packet_price.price} ₽", 
                callback_data="buy_packet"
            )],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_start")]
        ])
        
        balance_text = f"""
💰 <b>Ваш баланс</b>

Доступно отчетов: <b>{user.reports_balance}</b>

Выберите действие ниже 👇
"""
    
    await callback.message.answer(balance_text, reply_markup=keyboard)

@router.callback_query(F.data == "buy_single")
async def buy_single_callback(callback: CallbackQuery, user: User, state: FSMContext):
    """Handle buy single report button - generate YooKassa payment link"""
    logger.info(f"💳 [PAYMENT] User {user.id} selected SINGLE option")
    
    # Track CLICK_SINGLE event
    await create_event(CreateEventDTO(user_id=user.id, event_type=EventType.CLICK_SINGLE))
    
    await callback.answer()
    
    async with LoadingSticker(callback.message, callback.bot):
        # Get price from database
        from database.queries import get_price_by_option
        
        price = await get_price_by_option(ProductOption.SINGLE)
        
        if price is None:
            logger.error(f"❌ [PAYMENT] Failed to fetch SINGLE price for user {user.id}")
            await callback.message.answer("❌ Ошибка загрузки цены. Попробуйте позже.")
            return
        
        logger.info(f"💰 [PAYMENT] SINGLE price: {price.price} RUB")
        
        try:
            # Generate payment link via YooKassa
            payment_service = PaymentService(bot=callback.bot)
            confirmation_url = await payment_service.generate_payment_link(
                user_id=user.id,
                option=ProductOption.SINGLE
            )
            
            # Create keyboard with payment link
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=confirmation_url)],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_payment")]
            ])
            
            payment_text = f"""
💳 <b>Оплата</b>

Товар: <b>1 отчет</b>
Сумма: <b>{price.price} ₽</b>

Нажмите на кнопку ниже для перехода к оплате.
После успешной оплаты баланс будет автоматически пополнен.
"""
            
        
        except Exception as e:
            logger.error(f"❌ [PAYMENT] Error generating payment link: {e}", exc_info=True)
            await callback.message.answer(
                "❌ Ошибка создания платежа. Попробуйте позже."
            )
            return
    
    await callback.message.answer(payment_text, reply_markup=keyboard)
    logger.info(f"✅ [PAYMENT] Payment link sent to user {user.id}")


@router.callback_query(F.data == "buy_packet")
async def buy_packet_callback(callback: CallbackQuery, user: User, state: FSMContext):
    """Handle buy packet button - generate YooKassa payment link"""
    logger.info(f"💳 [PAYMENT] User {user.id} selected PACKET option")
    
    # Track CLICK_PACKET event
    await create_event(CreateEventDTO(user_id=user.id, event_type=EventType.CLICK_PACKET))
    
    await callback.answer()
    
    async with LoadingSticker(callback.message, callback.bot):
        # Get price from database
        from database.queries import get_price_by_option
        
        price = await get_price_by_option(ProductOption.PACKET)
        
        if price is None:
            logger.error(f"❌ [PAYMENT] Failed to fetch PACKET price for user {user.id}")
            await callback.message.answer("❌ Ошибка загрузки цены. Попробуйте позже.")
            return
        
        logger.info(f"💰 [PAYMENT] PACKET price: {price.price} RUB")
        
        try:
            # Generate payment link via YooKassa
            payment_service = PaymentService(bot=callback.bot)
            confirmation_url = await payment_service.generate_payment_link(
                user_id=user.id,
                option=ProductOption.PACKET
            )
            
            # Create keyboard with payment link
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=confirmation_url)],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_payment")]
            ])
            
            payment_text = f"""
💳 <b>Оплата</b>

Товар: <b>Пакет ({price.reports_amount} отчетов)</b>
Сумма: <b>{price.price} ₽</b>

Нажмите на кнопку ниже для перехода к оплате.
После успешной оплаты баланс будет автоматически пополнен.
"""
            

        
        except Exception as e:
            logger.error(f"❌ [PAYMENT] Error generating payment link: {e}", exc_info=True)
            await callback.message.answer(
                "❌ Ошибка создания платежа. Попробуйте позже."
            )
            return
    
    await callback.message.answer(payment_text, reply_markup=keyboard)
    logger.info(f"✅ [PAYMENT] Payment link sent to user {user.id}")


@router.callback_query(F.data == "cancel_refill")
async def cancel_refill_callback(callback: CallbackQuery, state: FSMContext):
    """Handle cancel refill button click"""
    user_id = callback.from_user.id
    logger.info(f"❌ [REFILL] User {user_id} cancelled refill process")
    
    # Track CLICK_CANCEL_BALANCE event
    await create_event(CreateEventDTO(user_id=user_id, event_type=EventType.CLICK_CANCEL_BALANCE))
    
    await state.clear()
    await callback.answer()
    await callback.message.delete()
    logger.info(f"✅ [REFILL] Refill process cancelled and state cleared for user {user_id}")


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment_callback(callback: CallbackQuery, state: FSMContext):
    """Handle cancel payment button click (after payment link is shown)"""
    user_id = callback.from_user.id
    logger.info(f"❌ [PAYMENT] User {user_id} cancelled payment process")
    
    # Track CLICK_CANCEL_PAYMENT event
    await create_event(CreateEventDTO(user_id=user_id, event_type=EventType.CLICK_CANCEL_PAYMENT))
    
    await state.clear()
    await callback.answer()
    await callback.message.delete()
    logger.info(f"✅ [PAYMENT] Payment process cancelled and state cleared for user {user_id}")
