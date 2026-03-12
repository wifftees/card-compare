"""Balance handler"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.models import User, ProductOption, EventType, CreateEventDTO
from database.queries import create_event
from bot.utils import LoadingSticker
from payment.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = Router()


async def _show_balance_text(
    user: User, keyboard: InlineKeyboardMarkup
) -> tuple[str, InlineKeyboardMarkup]:
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
    await create_event(
        CreateEventDTO(user_id=user.id, event_type=EventType.CLICK_BALANCE)
    )

    await callback.answer()

    async with LoadingSticker(callback.message, callback.bot):
        # Get prices from database
        from database.queries import get_price_by_option

        single_price = await get_price_by_option(ProductOption.SINGLE)
        packet_price = await get_price_by_option(ProductOption.PACKET)
        packet_first_price = await get_price_by_option(ProductOption.PACKET_FIRST)
        packet_second_price = await get_price_by_option(ProductOption.PACKET_SECOND)

        if any(
            p is None
            for p in (
                single_price,
                packet_price,
                packet_first_price,
                packet_second_price,
            )
        ):
            logger.error(f"❌ Failed to fetch prices from database for user {user.id}")
            await callback.message.answer("❌ Ошибка загрузки цен. Попробуйте позже.")
            return

        logger.info(
            f"💰 Loaded prices for user {user.id}: "
            f"SINGLE={single_price.price} RUB, PACKET={packet_price.price} RUB, "
            f"PACKET_FIRST={packet_first_price.price} RUB, "
            f"PACKET_SECOND={packet_second_price.price} RUB"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"📄 1 отчет - {single_price.price} ₽",
                        callback_data="buy:SINGLE",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"📦 Пакет ({packet_price.reports_amount} отчетов) - {packet_price.price} ₽",
                        callback_data="buy:PACKET",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"📦 Месяц под контролем ({packet_first_price.reports_amount} отчетов) - {packet_first_price.price} ₽",
                        callback_data="buy:PACKET_FIRST",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"📦 Профессионал ({packet_second_price.reports_amount} отчетов) - {packet_second_price.price} ₽",
                        callback_data="buy:PACKET_SECOND",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 Главное меню", callback_data="back_to_start"
                    )
                ],
            ]
        )

        balance_text = f"""
💰 <b>Ваш баланс</b>

Доступно отчетов: <b>{user.reports_balance}</b>

Выберите действие ниже 👇
"""

    await callback.message.answer(balance_text, reply_markup=keyboard)


BUY_OPTIONS: dict[str, tuple[ProductOption, EventType, str]] = {
    "SINGLE": (ProductOption.SINGLE, EventType.CLICK_SINGLE, "1 отчет"),
    "PACKET": (ProductOption.PACKET, EventType.CLICK_PACKET, "Пакет"),
    "PACKET_FIRST": (
        ProductOption.PACKET_FIRST,
        EventType.CLICK_PACKET_FIRST,
        "Месяц под контролем",
    ),
    "PACKET_SECOND": (
        ProductOption.PACKET_SECOND,
        EventType.CLICK_PACKET_SECOND,
        "Профессионал",
    ),
}

UPGRADE_MAP: dict[str, str] = {
    "SINGLE": "PACKET",
    "PACKET": "PACKET_FIRST",
    "PACKET_FIRST": "PACKET_SECOND",
}


@router.callback_query(F.data.startswith("buy:") | F.data.startswith("upgrade:"))
async def buy_option_callback(callback: CallbackQuery, user: User, state: FSMContext):  # pylint: disable=unused-argument
    """Unified handler for all buy and upgrade options"""
    prefix, option_key = callback.data.split(":", 1)
    is_upgrade = prefix == "upgrade"

    if option_key not in BUY_OPTIONS:
        logger.warning(
            f"[PAYMENT] Unknown buy option '{option_key}' from user {user.id}"
        )
        await callback.answer("Неизвестная опция", show_alert=True)
        return

    product_option, event_type, display_name = BUY_OPTIONS[option_key]

    logger.info(f"💳 [PAYMENT] User {user.id} selected {option_key} option")
    await create_event(CreateEventDTO(user_id=user.id, event_type=event_type))
    await callback.answer()

    if is_upgrade:
        await callback.message.delete()

    async with LoadingSticker(callback.message, callback.bot):
        from database.queries import get_price_by_option

        price = await get_price_by_option(product_option)

        if price is None:
            logger.error(
                f"❌ [PAYMENT] Failed to fetch {option_key} price for user {user.id}"
            )
            await callback.message.answer("❌ Ошибка загрузки цены. Попробуйте позже.")
            return

        logger.info(f"💰 [PAYMENT] {option_key} price: {price.price} RUB")

        try:
            payment_service = PaymentService(bot=callback.bot)
            confirmation_url = await payment_service.generate_payment_link(
                user_id=user.id, option=product_option
            )

            buttons = [
                [InlineKeyboardButton(text="💳 Оплатить", url=confirmation_url)],
            ]

            upgrade_key = UPGRADE_MAP.get(option_key)
            if upgrade_key and upgrade_key in BUY_OPTIONS:
                _, _, upgrade_name = BUY_OPTIONS[upgrade_key]
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"⬆️ Улучшить до «{upgrade_name}»",
                            callback_data=f"upgrade:{upgrade_key}",
                        )
                    ]
                )

            buttons.append(
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_payment")]
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            if price.reports_amount > 1:
                product_label = f"{display_name} ({price.reports_amount} отчетов)"
            else:
                product_label = display_name

            payment_text = f"""
💳 <b>Оплата</b>

Товар: <b>{product_label}</b>
Сумма: <b>{price.price} ₽</b>

Нажмите на кнопку ниже для перехода к оплате.
После успешной оплаты баланс будет автоматически пополнен.
"""

        except Exception as e:
            logger.error(
                f"❌ [PAYMENT] Error generating payment link: {e}", exc_info=True
            )
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
    await create_event(
        CreateEventDTO(user_id=user_id, event_type=EventType.CLICK_CANCEL_BALANCE)
    )

    await state.clear()
    await callback.answer()
    await callback.message.delete()
    logger.info(
        f"✅ [REFILL] Refill process cancelled and state cleared for user {user_id}"
    )


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment_callback(callback: CallbackQuery, state: FSMContext):
    """Handle cancel payment button click (after payment link is shown)"""
    user_id = callback.from_user.id
    logger.info(f"❌ [PAYMENT] User {user_id} cancelled payment process")

    # Track CLICK_CANCEL_PAYMENT event
    await create_event(
        CreateEventDTO(user_id=user_id, event_type=EventType.CLICK_CANCEL_PAYMENT)
    )

    await state.clear()
    await callback.answer()
    await callback.message.delete()
    logger.info(
        f"✅ [PAYMENT] Payment process cancelled and state cleared for user {user_id}"
    )
