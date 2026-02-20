"""Webhook handler for YooKassa payment notifications"""
import logging
import math
from typing import Dict, Any

from payment.payment_service import PaymentService
from database.queries import create_event, get_user, get_payment_by_external_id, add_referral_balance
from database.models import EventType, CreateEventDTO

logger = logging.getLogger(__name__)


async def handle_yookassa_webhook(
    data: Dict[str, Any],
    payment_service: PaymentService
) -> Dict[str, str]:
    """
    Handle webhook notification from YooKassa.
    
    YooKassa sends webhook when payment status changes.
    We only process "payment.succeeded" events.
    
    IMPORTANT: Always return HTTP 200, otherwise YooKassa will retry for 24 hours!
    
    Reference: PaymentController.kt handleYookassaNotification()
    
    Webhook payload example:
    {
      "type": "notification",
      "event": "payment.succeeded",
      "object": {
        "id": "2d90d360-000f-5000-9000-10a7bb3cfdb2",
        "status": "succeeded",
        "amount": {"value": "300.00", "currency": "RUB"},
        "metadata": {"order_id": "550e8400-e29b-41d4-a716-446655440000"}
      }
    }
    
    Args:
        data: Webhook payload from YooKassa
        payment_service: PaymentService instance
        
    Returns:
        Dict with {"status": "ok"} (for HTTP response)
    """
    logger.info(f"🔔 [WEBHOOK] Received notification from YooKassa: {data}")
    
    try:
        # Step 1: Check event type
        event = data.get("event")
        
        # Step 2: Extract order_id and user_id from metadata
        obj = data.get("object", {})
        metadata = obj.get("metadata", {})
        order_id = metadata.get("order_id")
        user_id_str = metadata.get("user_id")
        
        if event == "payment.succeeded":
            if not order_id:
                logger.error("❌ [WEBHOOK] Missing order_id in metadata")
                return {"status": "ok", "error": "missing_order_id"}
            
            if not user_id_str:
                logger.error("❌ [WEBHOOK] Missing user_id in metadata")
                return {"status": "ok", "error": "missing_user_id"}
            
            try:
                user_id = int(user_id_str)
            except (ValueError, TypeError):
                logger.error(f"❌ [WEBHOOK] Invalid user_id format: {user_id_str}")
                return {"status": "ok", "error": "invalid_user_id"}
            
            logger.info(f"🔑 [WEBHOOK] Processing payment.succeeded: order_id={order_id}, user_id={user_id}")
            
            success = await payment_service.complete_payment(order_id)
            await create_event(CreateEventDTO(user_id=user_id, event_type=EventType.PAY_FOR_OPTION))
            
            if success:
                logger.info(f"✅ [WEBHOOK] Payment completed successfully: order_id={order_id}")

                # Referral bonus: credit 20% (rounded up) to the inviter
                try:
                    buyer = await get_user(user_id)
                    if buyer and buyer.invited_by:
                        payment_obj = await get_payment_by_external_id(order_id)
                        if payment_obj:
                            bonus = math.ceil(payment_obj.total_price * 0.2)
                            await add_referral_balance(buyer.invited_by, bonus)
                            logger.info(
                                f"💸 [WEBHOOK] Referral bonus {bonus} credited to user {buyer.invited_by} "
                                f"(20% of {payment_obj.total_price})"
                            )
                except Exception as ref_err:
                    logger.error(f"❌ [WEBHOOK] Failed to process referral bonus: {ref_err}", exc_info=True)
            else:
                logger.error(f"❌ [WEBHOOK] Failed to complete payment: order_id={order_id}")
        
        elif event == "payment.canceled":
            if not order_id:
                logger.error("❌ [WEBHOOK] Missing order_id in metadata for canceled event")
                return {"status": "ok", "error": "missing_order_id"}
            
            logger.info(f"🔑 [WEBHOOK] Processing payment.canceled: order_id={order_id}")
            
            success = await payment_service.cancel_payment(order_id)
            
            if success:
                logger.info(f"✅ [WEBHOOK] Payment canceled successfully: order_id={order_id}")
            else:
                logger.error(f"❌ [WEBHOOK] Failed to cancel payment: order_id={order_id}")
        
        else:
            logger.info(
                f"ℹ️  [WEBHOOK] Ignoring event: {event} "
                f"(only processing payment.succeeded and payment.canceled)"
            )
        
        # Always return 200 OK
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(
            f"❌ [WEBHOOK] Unexpected error processing webhook: {e}",
            exc_info=True
        )
        # Still return 200 to prevent retries
        return {"status": "ok", "error": str(e)}
