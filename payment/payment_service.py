"""Payment service with business logic for YooKassa integration"""

import logging
import uuid

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import ProductOption, PaymentStatus, CreatePaymentDTO
from database.queries import (
    get_price_by_option,
    create_payment,
    get_payment_by_external_id,
    update_payment_with_yookassa_data,
    update_payment_status,
    update_balance,
)
from bot.utils import LOADING_STICKER_ID, delete_loading_sticker
from payment.yookassa_client import YookassaClient
from payment.cache import invoice_cache

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Payment service coordinating YooKassa integration, caching, and database operations.

    Reference:
    - CardSubscriptionPaymentProcessor.kt (generate_payment_link logic)
    - PaymentService.kt (complete_payment logic)
    """

    def __init__(self, bot: Bot = None):
        """
        Initialize payment service

        Args:
            bot: Aiogram Bot instance for sending notifications (optional)
        """
        self.yookassa_client = YookassaClient()
        self.bot = bot

    async def generate_payment_link(self, user_id: int, option: ProductOption) -> str:
        """
        Generate payment link for user.
        Uses cache to avoid creating duplicate invoices.

        Flow:
        1. Check cache for valid link
        2. If found → return cached link
        3. Otherwise:
           - Generate order_id (UUID)
           - Get price from DB
           - Create payment via YooKassa API
           - Save payment to DB with WAITING status
           - Cache the link
           - Return confirmation_url

        Args:
            user_id: Telegram user ID
            option: Product option (SINGLE or PACKET)

        Returns:
            YooKassa confirmation URL (payment link)

        Raises:
            Exception: If payment creation fails
        """
        logger.info(
            f"💳 [PAYMENT] Generating payment link: user_id={user_id}, option={option.value}"
        )

        # Step 1: Check cache
        cached_invoice = invoice_cache.get(user_id, option)
        if cached_invoice:
            logger.info(
                f"✅ [PAYMENT] Using cached invoice: "
                f"external_invoice_id={cached_invoice.external_invoice_id}"
            )
            return cached_invoice.confirmation_url

        # Step 2: Get price configuration from database
        price_config = await get_price_by_option(option)
        if price_config is None:
            raise ValueError(
                f"Price configuration not found for option {option.value}"
            )

        logger.info(
            f"💰 [PAYMENT] Price: {price_config.price} RUB, reports_amount: {price_config.reports_amount}"
        )

        # Step 3: Generate unique order_id
        order_id = str(uuid.uuid4())
        logger.info(f"🔑 [PAYMENT] Generated order_id: {order_id}")

        # Step 4: Create payment in database FIRST (to avoid race condition with webhook)
        payment = await create_payment(
            CreatePaymentDTO(
                user_id=user_id, total_price=price_config.price, option=option
            )
        )

        if not payment:
            raise RuntimeError("Failed to create payment in database")

        logger.info(f"💾 [PAYMENT] Payment created in DB: payment_id={payment.id}")

        try:
            # Step 5: Create payment in YooKassa
            description = f"Пополнение баланса: {price_config.reports_amount} отчет(ов)"
            yookassa_response = await self.yookassa_client.create_payment(
                amount=float(price_config.price),
                order_id=order_id,
                description=description,
                user_id=user_id,
            )

            # Extract confirmation_url
            confirmation = yookassa_response.get("confirmation", {})
            confirmation_url = confirmation.get("confirmation_url")

            if not confirmation_url:
                raise RuntimeError("No confirmation_url in YooKassa response")

            logger.info(f"✅ [PAYMENT] YooKassa invoice created: {confirmation_url}")

            # Step 6: Update payment with YooKassa data
            updated_payment = await update_payment_with_yookassa_data(
                payment_id=payment.id,
                external_invoice_id=order_id,
                confirmation_url=confirmation_url,
                status=PaymentStatus.PENDING,
            )

            if not updated_payment:
                logger.warning(
                    f"⚠️ [PAYMENT] Failed to update payment {payment.id} with YooKassa data, "
                    f"but continuing"
                )

            # Step 7: Cache the link
            invoice_cache.set(
                user_id=user_id,
                option=option,
                external_invoice_id=order_id,
                confirmation_url=confirmation_url,
                ttl_seconds=3600,  # 1 hour
            )

            logger.info(
                f"✅ [PAYMENT] Payment link generated successfully: "
                f"payment_id={payment.id}, order_id={order_id}"
            )

            return confirmation_url

        except Exception as e:
            logger.error(
                f"❌ [PAYMENT] Failed to create YooKassa invoice: {e}", exc_info=True
            )
            # Mark payment as FAILED
            await update_payment_status(payment.id, PaymentStatus.FAILED)
            raise

    async def complete_payment(self, external_invoice_id: str) -> bool:
        """
        Complete payment after receiving webhook from YooKassa.

        Flow:
        1. Find payment by external_invoice_id
        2. Check status (idempotency - already processed?)
        3. Update status to SUCCESS
        4. Update user balance
        5. Send notification to user

        Args:
            external_invoice_id: YooKassa order_id from webhook metadata

        Returns:
            True if payment completed successfully, False otherwise
        """
        logger.info(
            f"💳 [COMPLETE] Processing payment: external_invoice_id={external_invoice_id}"
        )

        # Step 1: Find payment
        payment = await get_payment_by_external_id(external_invoice_id)

        if not payment:
            logger.error(
                f"❌ [COMPLETE] Payment not found: external_invoice_id={external_invoice_id}"
            )
            return False

        logger.info(
            f"📊 [COMPLETE] Found payment: "
            f"payment_id={payment.id}, user_id={payment.user_id}, "
            f"status={payment.status.value}, option={payment.option.value}"
        )

        # Send loading sticker to user while processing
        loading_sticker_id: int | None = None
        if self.bot:
            try:
                sticker_msg = await self.bot.send_sticker(
                    chat_id=payment.user_id, sticker=LOADING_STICKER_ID
                )
                loading_sticker_id = sticker_msg.message_id
                logger.debug(
                    f"📤 [COMPLETE] Sent loading sticker to user {payment.user_id}"
                )
            except Exception as e:
                logger.warning(f"⚠️ [COMPLETE] Could not send loading sticker: {e}")

        try:
            # Step 2: Get price configuration to determine reports_amount
            price_config = await get_price_by_option(payment.option)
            if not price_config:
                logger.error(
                    f"❌ [COMPLETE] Price config not found for option {payment.option.value}"
                )
                return False

            reports_amount = price_config.reports_amount
            logger.info(
                f"💰 [COMPLETE] Reports amount for option {payment.option.value}: {reports_amount}"
            )

            # Step 3: Check idempotency
            if payment.status == PaymentStatus.SUCCESS:
                logger.warning(
                    f"⚠️ [COMPLETE] Payment {payment.id} already processed (status=SUCCESS), "
                    f"skipping (webhook duplicate)"
                )
                return True  # Already processed, but not an error

            # Step 4: Update payment status to SUCCESS
            updated_payment = await update_payment_status(
                payment.id, PaymentStatus.SUCCESS
            )

            if not updated_payment:
                logger.error(
                    f"❌ [COMPLETE] Failed to update payment {payment.id} status"
                )
                return False

            logger.info(f"✅ [COMPLETE] Payment {payment.id} marked as SUCCESS")

            # Step 5: Update user balance
            updated_user = await update_balance(
                user_id=payment.user_id, amount=reports_amount
            )

            if not updated_user:
                logger.error(
                    f"❌ [COMPLETE] Failed to update balance for user {payment.user_id}"
                )
                return False

            logger.info(
                f"💰 [COMPLETE] Balance updated: user_id={payment.user_id}, "
                f"added {reports_amount} reports, "
                f"new_balance={updated_user.reports_balance}"
            )
        finally:
            # Delete loading sticker after all DB operations
            if self.bot and loading_sticker_id:
                await delete_loading_sticker(
                    self.bot, payment.user_id, loading_sticker_id
                )

        # Step 6: Send notification to user
        if self.bot:
            try:
                success_text = f"""
✅ <b>Платеж успешно выполнен!</b>

Зачислено отчетов: <b>{reports_amount}</b>
Текущий баланс: <b>{updated_user.reports_balance}</b> отчетов

Спасибо за покупку! 💚
"""
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🏠 Главное меню", callback_data="back_to_start"
                            )
                        ]
                    ]
                )
                await self.bot.send_message(
                    chat_id=payment.user_id, text=success_text, reply_markup=keyboard
                )
                logger.info(
                    f"📨 [COMPLETE] Notification sent to user {payment.user_id}"
                )
            except Exception as e:
                logger.error(
                    f"❌ [COMPLETE] Failed to send notification to user {payment.user_id}: {e}",
                    exc_info=True,
                )
                # Don't fail the whole operation if notification fails

        # Step 7: Invalidate cache so user can create new payment next time
        invoice_cache.invalidate(user_id=payment.user_id, option=payment.option)

        logger.info(
            f"✅ [COMPLETE] Payment {payment.id} completed successfully: "
            f"user_id={payment.user_id}, reports_added={reports_amount}"
        )

        return True

    async def cancel_payment(self, external_invoice_id: str) -> bool:
        """
        Cancel payment after receiving cancellation webhook from YooKassa.

        Flow:
        1. Find payment by external_invoice_id
        2. Check status (idempotency - already canceled/succeeded?)
        3. Update status to CANCELED
        4. Invalidate cache

        Args:
            external_invoice_id: YooKassa order_id from webhook metadata

        Returns:
            True if payment canceled successfully, False otherwise
        """
        logger.info(
            f"❌ [CANCEL] Processing cancellation: external_invoice_id={external_invoice_id}"
        )

        # Step 1: Find payment
        payment = await get_payment_by_external_id(external_invoice_id)

        if not payment:
            logger.error(
                f"❌ [CANCEL] Payment not found: external_invoice_id={external_invoice_id}"
            )
            return False

        logger.info(
            f"📊 [CANCEL] Found payment: "
            f"payment_id={payment.id}, user_id={payment.user_id}, "
            f"status={payment.status.value}, option={payment.option.value}"
        )

        # Step 2: Check idempotency
        if payment.status == PaymentStatus.CANCELED:
            logger.warning(
                f"⚠️ [CANCEL] Payment {payment.id} already canceled, "
                f"skipping (webhook duplicate)"
            )
            return True

        if payment.status == PaymentStatus.SUCCESS:
            logger.warning(
                f"⚠️ [CANCEL] Payment {payment.id} already succeeded, cannot cancel"
            )
            return False

        # Step 3: Update payment status to CANCELED
        updated_payment = await update_payment_status(
            payment.id, PaymentStatus.CANCELED
        )

        if not updated_payment:
            logger.error(f"❌ [CANCEL] Failed to update payment {payment.id} status")
            return False

        logger.info(f"✅ [CANCEL] Payment {payment.id} marked as CANCELED")

        # Step 4: Invalidate cache so user can create new payment
        invoice_cache.invalidate(user_id=payment.user_id, option=payment.option)

        logger.info(
            f"✅ [CANCEL] Payment {payment.id} canceled successfully: "
            f"user_id={payment.user_id}"
        )

        return True
