"""Balance handler"""
import logging
from aiogram import Router, F
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
    ContentType
)
from aiogram.fsm.context import FSMContext

from database.models import User
from bot.states import RefillBalanceStates
from bot.config import settings

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "💰 Баланс")
async def show_balance(message: Message, user: User):
    """Show user balance"""
    logger.info(f"User {user.id} requested balance")
    
    balance_text = f"""
💰 <b>Ваш баланс</b>

Доступно отчетов: <b>{user.reports_balance}</b>
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="refill_balance")]
    ])
    
    await message.answer(balance_text, reply_markup=keyboard)


@router.callback_query(F.data == "refill_balance")
async def refill_balance_callback(callback: CallbackQuery, user: User, state: FSMContext):
    """Handle refill balance button click - start refill process"""
    logger.info(f"User {user.id} started refill balance process")
    
    await callback.answer()
    
    # Set FSM state
    await state.set_state(RefillBalanceStates.waiting_for_amount)
    
    # Create cancel keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить пополнение баланса", callback_data="cancel_refill")]
    ])
    
    refill_text = f"""
💳 <b>Пополнение баланса</b>

1 отчет = <b>{settings.report_price} ₽</b>

Введите количество отчетов, которые вы хотите оплатить:
"""
    
    await callback.message.answer(refill_text, reply_markup=keyboard)


@router.callback_query(F.data == "cancel_refill")
async def cancel_refill_callback(callback: CallbackQuery, state: FSMContext):
    """Handle cancel refill button click"""
    user_id = callback.from_user.id
    logger.info(f"❌ [REFILL] User {user_id} cancelled refill process")
    
    # Get state data before clearing to log what was cancelled
    data = await state.get_data()
    amount = data.get("amount")
    total_price = data.get("total_price")
    
    if amount or total_price:
        logger.info(
            f"📊 [REFILL] Cancelled payment details for user {user_id}: "
            f"reports_amount={amount}, total_price={total_price} RUB"
        )
    
    await state.clear()
    await callback.answer("❌ Пополнение баланса отменено", show_alert=True)
    await callback.message.delete()
    logger.info(f"✅ [REFILL] Refill process cancelled and state cleared for user {user_id}")


@router.callback_query(F.data == "pay_invoice")
async def pay_invoice_callback(callback: CallbackQuery, user: User, state: FSMContext):
    """Handle pay invoice button click - send invoice for payment"""
    logger.info(f"💳 [PAYMENT] User {user.id} clicked pay button")
    
    await callback.answer()
    
    # Get amount from FSM context
    data = await state.get_data()
    amount = data.get("amount")
    total_price = data.get("total_price")
    
    if not amount or not total_price:
        logger.warning(f"⚠️ [PAYMENT] User {user.id}: missing payment data in FSM state")
        await callback.message.answer("❌ Ошибка: данные о платеже не найдены. Начните заново.")
        await state.clear()
        return
    
    logger.info(
        f"📊 [PAYMENT] User {user.id}: creating payment - "
        f"reports_amount={amount}, total_price={total_price} RUB, "
        f"price_per_report={settings.report_price} RUB"
    )
    
    # Create payment entity in database with status NEW
    from database.queries import create_payment
    from database.models import CreatePaymentDTO
    
    payment = await create_payment(CreatePaymentDTO(
        user_id=user.id,
        reports_amount=amount,
        total_price=total_price
    ))
    
    if not payment:
        logger.error(f"❌ [PAYMENT] User {user.id}: failed to create payment in database")
        await callback.message.answer("❌ Ошибка создания платежа. Попробуйте позже.")
        await state.clear()
        return
    
    logger.info(
        f"✅ [PAYMENT] Created payment {payment.id} for user {user.id} "
        f"(status={payment.status.value}, reports={payment.reports_amount}, "
        f"price={payment.total_price} RUB)"
    )
    
    # Calculate price in kopecks
    total_price_kopecks = total_price * 100
    
    # Create LabeledPrice structure
    prices = [
        LabeledPrice(label=f"Отчеты ({amount} шт.)", amount=total_price_kopecks)
    ]
    
    # Set state to waiting for payment
    await state.set_state(RefillBalanceStates.waiting_for_payment)
    
    logger.info(
        f"📤 [PAYMENT] Sending invoice for payment {payment.id} to user {user.id} "
        f"(amount={total_price_kopecks} kopecks, payload={payment.id})"
    )
    
    # Send invoice for payment with payment_id in payload
    await callback.message.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="💳 Пополнение баланса",
        description=f"Покупка {amount} отчетов по {settings.report_price} ₽ каждый",
        payload=str(payment.id),  # Put payment_id in payload
        provider_token=settings.payment_token,
        currency="RUB",
        prices=prices,
        start_parameter="refill_balance",
        photo_url=None,
        photo_size=None,
        photo_width=None,
        photo_height=None,
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        send_phone_number_to_provider=False,
        send_email_to_provider=False,
        is_flexible=False
    )
    
    logger.info(f"✅ [PAYMENT] Invoice sent successfully for payment {payment.id}")


@router.message(RefillBalanceStates.waiting_for_amount, F.text)
@router.message(RefillBalanceStates.waiting_for_confirmation, F.text)
async def process_refill_amount(message: Message, user: User, state: FSMContext):
    """Process user input for refill amount (works for both initial input and changes)"""
    logger.info(
        f"📝 [REFILL] User {user.id} entered amount: '{message.text}' "
        f"(current state: {await state.get_state()})"
    )
    
    # Validate input
    try:
        amount = int(message.text.strip())
        
        if amount <= 0:
            logger.warning(
                f"⚠️ [REFILL] User {user.id} entered invalid amount: {amount} (<= 0)"
            )
            await message.answer("❌ Количество отчетов должно быть больше нуля. Попробуйте еще раз:")
            return
        
        if amount > 1000:
            logger.warning(
                f"⚠️ [REFILL] User {user.id} entered amount exceeding limit: {amount} (> 1000)"
            )
            await message.answer("❌ Максимальное количество отчетов за раз - 1000. Попробуйте еще раз:")
            return
            
    except ValueError:
        logger.warning(
            f"⚠️ [REFILL] User {user.id} entered non-numeric value: '{message.text}'"
        )
        await message.answer("❌ Пожалуйста, введите корректное число:")
        return
    
    # Calculate total price
    total_price = amount * settings.report_price
    
    logger.info(
        f"💰 [REFILL] User {user.id}: calculated payment details - "
        f"reports_amount={amount}, price_per_report={settings.report_price} RUB, "
        f"total_price={total_price} RUB"
    )
    
    # Save amount to FSM context
    await state.update_data(amount=amount, total_price=total_price)
    await state.set_state(RefillBalanceStates.waiting_for_confirmation)
    
    logger.info(
        f"💾 [REFILL] Saved payment data to FSM state for user {user.id}: "
        f"amount={amount}, total_price={total_price}"
    )
    
    # Create keyboard with payment and cancel buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить", callback_data="pay_invoice")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_refill")]
    ])
    
    confirmation_text = f"""
💳 <b>Подтверждение пополнения</b>

Количество отчетов: <b>{amount}</b>
Цена за отчет: <b>{settings.report_price} ₽</b>

💰 <b>Итого к оплате: {total_price} ₽</b>

<i>Чтобы изменить количество, введите другое число</i>
"""
    
    await message.answer(confirmation_text, reply_markup=keyboard)
    logger.info(
        f"✅ [REFILL] Sent confirmation message to user {user.id} "
        f"for {amount} reports ({total_price} RUB)"
    )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """
    Handle pre-checkout query.
    This handler MUST answer OK to proceed with payment.
    """
    user_id = pre_checkout_query.from_user.id
    logger.info(
        f"🔍 [PRE-CHECKOUT] Pre-checkout query from user {user_id} "
        f"(payload={pre_checkout_query.invoice_payload}, "
        f"amount={pre_checkout_query.total_amount} kopecks, "
        f"currency={pre_checkout_query.currency})"
    )
    
    try:
        # Extract payment_id from payload
        payment_id = int(pre_checkout_query.invoice_payload)
        logger.info(f"📋 [PRE-CHECKOUT] Extracted payment_id={payment_id} from payload")
        
        # Get payment from database
        from database.queries import get_payment, update_payment_status
        from database.models import PaymentStatus
        
        payment = await get_payment(payment_id)
        
        if not payment:
            logger.error(
                f"❌ [PRE-CHECKOUT] Payment {payment_id} not found in database "
                f"for user {user_id}"
            )
            await pre_checkout_query.answer(
                ok=False,
                error_message="Платеж не найден. Попробуйте еще раз."
            )
            return
        
        logger.info(
            f"📊 [PRE-CHECKOUT] Found payment {payment_id}: "
            f"user_id={payment.user_id}, status={payment.status.value}, "
            f"reports_amount={payment.reports_amount}, total_price={payment.total_price} RUB"
        )
        
        # Verify user matches
        if payment.user_id != user_id:
            logger.error(
                f"❌ [PRE-CHECKOUT] User mismatch for payment {payment_id}: "
                f"payment.user_id={payment.user_id}, query.user_id={user_id}"
            )
            await pre_checkout_query.answer(
                ok=False,
                error_message="Ошибка проверки платежа. Попробуйте еще раз."
            )
            return
        
        # Verify price: total_price / reports_amount should equal REPORT_PRICE
        price_per_report = payment.total_price / payment.reports_amount
        
        logger.info(
            f"💰 [PRE-CHECKOUT] Validating price: "
            f"price_per_report={price_per_report:.2f} RUB, "
            f"expected={settings.report_price} RUB"
        )
        
        if abs(price_per_report - settings.report_price) > 0.01:  # Allow small float difference
            logger.error(
                f"❌ [PRE-CHECKOUT] Price mismatch for payment {payment_id}: "
                f"expected {settings.report_price} RUB, got {price_per_report:.2f} RUB"
            )
            await pre_checkout_query.answer(
                ok=False,
                error_message="Ошибка проверки цены. Попробуйте еще раз."
            )
            return
        
        # Verify total amount matches Telegram's total
        # pre_checkout_query.total_amount is in kopecks
        expected_amount_kopecks = payment.total_price * 100
        
        logger.info(
            f"💵 [PRE-CHECKOUT] Validating amount: "
            f"expected={expected_amount_kopecks} kopecks, "
            f"received={pre_checkout_query.total_amount} kopecks"
        )
        
        if pre_checkout_query.total_amount != expected_amount_kopecks:
            logger.error(
                f"❌ [PRE-CHECKOUT] Amount mismatch for payment {payment_id}: "
                f"expected {expected_amount_kopecks} kopecks, "
                f"got {pre_checkout_query.total_amount} kopecks"
            )
            await pre_checkout_query.answer(
                ok=False,
                error_message="Ошибка проверки суммы. Попробуйте еще раз."
            )
            return
        
        # Update payment status to PENDING
        logger.info(f"🔄 [PRE-CHECKOUT] Updating payment {payment_id} status to PENDING")
        updated_payment = await update_payment_status(payment_id, PaymentStatus.PENDING)
        
        if updated_payment:
            logger.info(
                f"✅ [PRE-CHECKOUT] Payment {payment_id} status updated to PENDING"
            )
        else:
            logger.warning(
                f"⚠️ [PRE-CHECKOUT] Failed to update payment {payment_id} status, "
                f"but continuing with validation"
            )
        
        # Allow payment to proceed
        logger.info(
            f"✅ [PRE-CHECKOUT] Pre-checkout validation passed for payment {payment_id}, "
            f"allowing payment to proceed"
        )
        await pre_checkout_query.answer(ok=True)
        
    except ValueError as e:
        logger.error(
            f"❌ [PRE-CHECKOUT] Invalid payment_id in payload: "
            f"{pre_checkout_query.invoice_payload}, error: {e}"
        )
        await pre_checkout_query.answer(
            ok=False,
            error_message="Неверный формат платежа. Попробуйте еще раз."
        )
    except Exception as e:
        logger.error(
            f"❌ [PRE-CHECKOUT] Unexpected error in pre_checkout_query for user {user_id}: {e}",
            exc_info=True
        )
        await pre_checkout_query.answer(
            ok=False,
            error_message="Произошла ошибка. Попробуйте позже."
        )


@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: Message, user: User, state: FSMContext):
    """Handle successful payment and update user balance"""
    payment_info = message.successful_payment
    logger.info(
        f"💳 [SUCCESSFUL-PAYMENT] Successful payment received from user {user.id}: "
        f"amount={payment_info.total_amount / 100} {payment_info.currency}, "
        f"payload={payment_info.invoice_payload}, "
        f"telegram_charge_id={payment_info.telegram_payment_charge_id}, "
        f"provider_charge_id={payment_info.provider_payment_charge_id}"
    )
    
    try:
        # Extract payment_id from payload
        payment_id = int(payment_info.invoice_payload)
        logger.info(f"📋 [SUCCESSFUL-PAYMENT] Extracted payment_id={payment_id} from payload")
        
        # Get payment from database
        from database.queries import get_payment, update_payment_charges, update_balance
        
        payment = await get_payment(payment_id)
        
        if not payment:
            logger.error(
                f"❌ [SUCCESSFUL-PAYMENT] Payment {payment_id} not found in database "
                f"for user {user.id}"
            )
            await message.answer(
                "❌ Ошибка: платеж не найден. "
                "Пожалуйста, свяжитесь с поддержкой."
            )
            return
        
        logger.info(
            f"📊 [SUCCESSFUL-PAYMENT] Found payment {payment_id}: "
            f"user_id={payment.user_id}, status={payment.status.value}, "
            f"reports_amount={payment.reports_amount}, total_price={payment.total_price} RUB"
        )
        
        # Verify user matches
        if payment.user_id != user.id:
            logger.error(
                f"❌ [SUCCESSFUL-PAYMENT] User mismatch for payment {payment_id}: "
                f"payment.user_id={payment.user_id}, message.user_id={user.id}"
            )
            await message.answer(
                "❌ Ошибка: несоответствие данных платежа. "
                "Пожалуйста, свяжитесь с поддержкой."
            )
            return
        
        # Verify payment status
        if payment.status.value == "SUCCESS":
            logger.warning(
                f"⚠️ [SUCCESSFUL-PAYMENT] Payment {payment_id} already processed "
                f"(status=SUCCESS), but received successful_payment again"
            )
            # Still proceed to update balance if needed, but log the duplicate
        
        # Update payment with charge IDs and set status to SUCCESS
        logger.info(
            f"🔄 [SUCCESSFUL-PAYMENT] Updating payment {payment_id} with charge IDs "
            f"and setting status to SUCCESS"
        )
        updated_payment = await update_payment_charges(
            payment_id=payment_id,
            telegram_charge_id=payment_info.telegram_payment_charge_id,
            provider_charge_id=payment_info.provider_payment_charge_id
        )
        
        if updated_payment:
            logger.info(
                f"✅ [SUCCESSFUL-PAYMENT] Payment {payment_id} updated successfully: "
                f"status={updated_payment.status.value}, "
                f"telegram_charge_id={updated_payment.telegram_payment_charge_id}, "
                f"provider_charge_id={updated_payment.provider_payment_charge_id}"
            )
        else:
            logger.error(
                f"❌ [SUCCESSFUL-PAYMENT] Failed to update payment {payment_id} "
                f"with charge IDs"
            )
        
        # Get current balance before update
        old_balance = user.reports_balance
        logger.info(
            f"💰 [SUCCESSFUL-PAYMENT] Current balance for user {user.id}: {old_balance} reports"
        )
        
        # Update user balance
        logger.info(
            f"🔄 [SUCCESSFUL-PAYMENT] Adding {payment.reports_amount} reports "
            f"to user {user.id} balance"
        )
        updated_user = await update_balance(
            user_id=user.id,
            amount=payment.reports_amount
        )
        
        if updated_user:
            new_balance = updated_user.reports_balance
            logger.info(
                f"✅ [SUCCESSFUL-PAYMENT] Balance updated for user {user.id}: "
                f"{old_balance} -> {new_balance} reports "
                f"(added {payment.reports_amount} reports)"
            )
        else:
            logger.error(
                f"❌ [SUCCESSFUL-PAYMENT] Failed to update balance for user {user.id}"
            )
            new_balance = old_balance
        
        # Clear FSM state
        await state.clear()
        logger.info(f"🧹 [SUCCESSFUL-PAYMENT] Cleared FSM state for user {user.id}")
        
        # Send success message
        success_text = f"""
✅ <b>Платеж успешно выполнен!</b>

Зачислено отчетов: <b>{payment.reports_amount}</b>
Текущий баланс: <b>{new_balance}</b> отчетов

Спасибо за покупку! 💚
"""
        
        await message.answer(success_text)
        logger.info(
            f"✅ [SUCCESSFUL-PAYMENT] Payment {payment_id} processed successfully "
            f"for user {user.id}: added {payment.reports_amount} reports, "
            f"new balance={new_balance}"
        )
        
    except ValueError as e:
        logger.error(
            f"❌ [SUCCESSFUL-PAYMENT] Invalid payment_id in payload: "
            f"{payment_info.invoice_payload}, error: {e}"
        )
        await message.answer(
            "❌ Ошибка обработки платежа. "
            "Пожалуйста, свяжитесь с поддержкой."
        )
    except Exception as e:
        logger.error(
            f"❌ [SUCCESSFUL-PAYMENT] Unexpected error processing successful payment "
            f"for user {user.id}: {e}",
            exc_info=True
        )
        await message.answer(
            "❌ Произошла ошибка при обработке платежа. "
            "Пожалуйста, свяжитесь с поддержкой."
        )
