"""Database query functions"""
import logging
from typing import Optional
from datetime import datetime
from .client import get_supabase
from .models import User, CreateUserDTO, UpdateBalanceDTO, FeatureFlag, Payment, CreatePaymentDTO, PaymentStatus

logger = logging.getLogger(__name__)


async def get_user(user_id: int) -> Optional[User]:
    """Get user by Telegram ID"""
    try:
        supabase = get_supabase()
        response = supabase.table("users").select("*").eq("id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            return User(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None


async def create_user(data: CreateUserDTO) -> Optional[User]:
    """Create a new user"""
    try:
        supabase = get_supabase()
        user_data = {
            "id": data.id,
            "username": data.username,
            "created_at": datetime.utcnow().isoformat(),
            "reports_balance": 1
        }
        
        response = supabase.table("users").insert(user_data).execute()
        
        if response.data and len(response.data) > 0:
            logger.info(f"✅ Created user {data.id}")
            return User(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error creating user {data.id}: {e}")
        return None


async def get_or_create_user(user_id: int, username: Optional[str] = None) -> Optional[User]:
    """Get existing user or create new one"""
    user = await get_user(user_id)
    if user is None:
        user = await create_user(CreateUserDTO(id=user_id, username=username))
    return user


async def check_balance(user_id: int) -> int:
    """Check user's report balance"""
    user = await get_user(user_id)
    return user.reports_balance if user else 0


async def update_balance(user_id: int, amount: int) -> Optional[User]:
    """Update user balance (add or subtract)"""
    try:
        supabase = get_supabase()
        
        # Get current balance
        user = await get_user(user_id)
        if not user:
            logger.error(f"User {user_id} not found for balance update")
            return None
        
        new_balance = user.reports_balance + amount
        
        # Ensure balance doesn't go negative
        if new_balance < 0:
            new_balance = 0
        
        response = supabase.table("users").update({
            "reports_balance": new_balance
        }).eq("id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            logger.info(f"✅ Updated balance for user {user_id}: {user.reports_balance} -> {new_balance}")
            return User(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error updating balance for user {user_id}: {e}")
        return None


async def get_feature_flag(flag_name: str, default: bool = False) -> bool:
    """
    Get feature flag value by name.
    
    Args:
        flag_name: Name of the feature flag
        default: Default value if flag not found
        
    Returns:
        bool: Feature flag value (enabled/disabled)
    """
    try:
        logger.info(f"🔍 Fetching feature flag '{flag_name}' from database...")
        supabase = get_supabase()
        response = supabase.table("feature_flags").select("*").eq("name", flag_name).execute()

        if response.data and len(response.data) > 0:
            flag = FeatureFlag(**response.data[0])
            logger.info(f"🚩 Feature flag '{flag_name}' = {flag.enabled} (from database)")
            return flag.enabled
        
        logger.warning(f"⚠️  Feature flag '{flag_name}' not found in database, using default: {default}")
        return default
    except Exception as e:
        logger.error(f"❌ Error getting feature flag '{flag_name}' from database: {e}", exc_info=True)
        logger.warning(f"⚠️  Falling back to default value: {default}")
        return default


async def get_wb_use_mock() -> bool:
    """Get wb_use_mock feature flag value"""
    return await get_feature_flag("IS_WB_USE_MOCK", default=True)


async def get_compare_cards_mock() -> bool:
    """Get compare_cards_mock feature flag value"""
    return await get_feature_flag("IS_COMPARE_CARDS_MOCK", default=True)


# Payment functions

async def create_payment(data: CreatePaymentDTO) -> Optional[Payment]:
    """Create a new payment with status NEW"""
    try:
        supabase = get_supabase()
        payment_data = {
            "user_id": data.user_id,
            "reports_amount": data.reports_amount,
            "total_price": data.total_price,
            "status": PaymentStatus.NEW.value,
            "created_at": datetime.utcnow().isoformat(),
        }
        
        response = supabase.table("payments").insert(payment_data).execute()
        
        if response.data and len(response.data) > 0:
            payment = Payment(**response.data[0])
            logger.info(f"✅ Created payment {payment.id} for user {data.user_id}")
            return payment
        return None
    except Exception as e:
        logger.error(f"Error creating payment for user {data.user_id}: {e}", exc_info=True)
        return None


async def get_payment(payment_id: int) -> Optional[Payment]:
    """Get payment by ID"""
    try:
        supabase = get_supabase()
        response = supabase.table("payments").select("*").eq("id", payment_id).execute()
        
        if response.data and len(response.data) > 0:
            return Payment(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error getting payment {payment_id}: {e}", exc_info=True)
        return None


async def update_payment_status(payment_id: int, status: PaymentStatus) -> Optional[Payment]:
    """Update payment status"""
    try:
        supabase = get_supabase()
        response = supabase.table("payments").update({
            "status": status.value
        }).eq("id", payment_id).execute()
        
        if response.data and len(response.data) > 0:
            logger.info(f"✅ Updated payment {payment_id} status to {status.value}")
            return Payment(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error updating payment {payment_id} status: {e}", exc_info=True)
        return None


async def update_payment_charges(
    payment_id: int,
    telegram_charge_id: str,
    provider_charge_id: str
) -> Optional[Payment]:
    """Update payment charge IDs and set status to SUCCESS"""
    try:
        supabase = get_supabase()
        response = supabase.table("payments").update({
            "telegram_payment_charge_id": telegram_charge_id,
            "provider_payment_charge_id": provider_charge_id,
            "status": PaymentStatus.SUCCESS.value
        }).eq("id", payment_id).execute()
        
        if response.data and len(response.data) > 0:
            logger.info(f"✅ Updated payment {payment_id} charges and marked as SUCCESS")
            return Payment(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error updating payment {payment_id} charges: {e}", exc_info=True)
        return None
