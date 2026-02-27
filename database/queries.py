"""Database query functions"""

import logging
from datetime import datetime
from typing import Optional

from .client import get_supabase
from .models import (
    User,
    CreateUserDTO,
    FeatureFlag,
    Payment,
    CreatePaymentDTO,
    PaymentStatus,
    Price,
    ProductOption,
    Report,
    CreateReportDTO,
    ReportState,
    Event,
    CreateEventDTO,
    EventType,
)

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
            "reports_balance": 0,
            "invited_by": data.invited_by,
        }

        response = supabase.table("users").insert(user_data).execute()

        if response.data and len(response.data) > 0:
            invited_by_info = (
                f" (invited by {data.invited_by})" if data.invited_by else ""
            )
            logger.info(f"✅ Created user {data.id}{invited_by_info}")
            return User(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error creating user {data.id}: {e}")
        return None


async def get_or_create_user(
    user_id: int, username: Optional[str] = None
) -> Optional[User]:
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

        response = (
            supabase.table("users")
            .update({"reports_balance": new_balance})
            .eq("id", user_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            logger.info(
                f"✅ Updated balance for user {user_id}: {user.reports_balance} -> {new_balance}"
            )
            return User(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error updating balance for user {user_id}: {e}")
        return None


async def count_referrals(user_id: int) -> int:
    """Count total number of users invited by the given user_id"""
    try:
        supabase = get_supabase()
        response = (
            supabase.table("users")
            .select("id", count="exact")
            .eq("invited_by", user_id)
            .execute()
        )

        count = response.count if response.count is not None else 0
        logger.debug(f"User {user_id} has {count} referrals")
        return count
    except Exception as e:
        logger.error(f"Error counting referrals for user {user_id}: {e}")
        return 0


async def add_referral_balance(user_id: int, amount: int) -> Optional[User]:
    """Add amount to referral_balance for the given user"""
    try:
        supabase = get_supabase()
        user = await get_user(user_id)
        if not user:
            logger.error(f"User {user_id} not found for referral_balance update")
            return None

        new_balance = user.referral_balance + amount
        response = (
            supabase.table("users")
            .update({"referral_balance": new_balance})
            .eq("id", user_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            logger.info(
                f"✅ Updated referral_balance for user {user_id}: {user.referral_balance} -> {new_balance}"
            )
            return User(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error updating referral_balance for user {user_id}: {e}")
        return None


async def update_last_active_at(user_id: int) -> Optional[User]:
    """Update user's last_active_at timestamp"""
    try:
        supabase = get_supabase()
        response = (
            supabase.table("users")
            .update({"last_active_at": datetime.utcnow().isoformat()})
            .eq("id", user_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            logger.info(f"✅ Updated last_active_at for user {user_id}")
            return User(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error updating last_active_at for user {user_id}: {e}")
        return None


async def create_event(data: CreateEventDTO) -> Optional[Event]:
    """Create a new event and update user's last_active_at."""
    try:
        supabase = get_supabase()
        event_data = {
            "user_id": data.user_id,
            "event_type": data.event_type.value,
            "timestamp": datetime.utcnow().isoformat(),
        }

        response = supabase.table("events").insert(event_data).execute()

        if response.data and len(response.data) > 0:
            event = Event(**response.data[0])
            logger.info(
                f"✅ Created event {event.id} for user {data.user_id}: {data.event_type.value}"
            )

            # Update user's last_active_at
            await update_last_active_at(data.user_id)

            return event
        return None
    except Exception as e:
        logger.error(
            f"Error creating event for user {data.user_id}: {e}", exc_info=True
        )
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
        response = (
            supabase.table("feature_flags").select("*").eq("name", flag_name).execute()
        )

        if response.data and len(response.data) > 0:
            flag = FeatureFlag(**response.data[0])
            logger.info(
                f"🚩 Feature flag '{flag_name}' = {flag.enabled} (from database)"
            )
            return flag.enabled

        logger.warning(
            f"⚠️  Feature flag '{flag_name}' not found in database, using default: {default}"
        )
        return default
    except Exception as e:
        logger.error(
            f"❌ Error getting feature flag '{flag_name}' from database: {e}",
            exc_info=True,
        )
        logger.warning(f"⚠️  Falling back to default value: {default}")
        return default


async def get_wb_use_mock() -> bool:
    """Get wb_use_mock feature flag value"""
    return await get_feature_flag("IS_WB_USE_MOCK", default=True)


async def get_compare_cards_mock() -> bool:
    """Get compare_cards_mock feature flag value"""
    return await get_feature_flag("IS_COMPARE_CARDS_MOCK", default=True)


# Price functions


async def get_price_by_option(option: ProductOption) -> Optional[Price]:
    """
    Get price configuration by product option.

    Args:
        option: Product option (SINGLE or PACKET)

    Returns:
        Price: Price object with price and reports_amount, or None if not found
    """
    try:
        logger.info(f"🔍 Fetching price for option '{option.value}' from database...")
        supabase = get_supabase()
        response = (
            supabase.table("prices").select("*").eq("option", option.value).execute()
        )

        if response.data and len(response.data) > 0:
            price = Price(**response.data[0])
            logger.info(
                f"💰 Price for '{option.value}' = {price.price} RUB, "
                f"reports_amount = {price.reports_amount} (from database)"
            )
            return price

        logger.warning(f"⚠️  Price for option '{option.value}' not found in database")
        return None
    except Exception as e:
        logger.error(
            f"❌ Error getting price for option '{option.value}' from database: {e}",
            exc_info=True,
        )
        return None


# Payment functions


async def create_payment(data: CreatePaymentDTO) -> Optional[Payment]:
    """Create a new payment with status NEW"""
    try:
        supabase = get_supabase()
        payment_data = {
            "user_id": data.user_id,
            "total_price": data.total_price,
            "option": data.option.value,
            "status": PaymentStatus.NEW.value,
            "created_at": datetime.utcnow().isoformat(),
        }

        response = supabase.table("payments").insert(payment_data).execute()

        if response.data and len(response.data) > 0:
            payment = Payment(**response.data[0])
            logger.info(
                f"✅ Created payment {payment.id} for user {data.user_id} (option={payment.option.value})"
            )
            return payment
        return None
    except Exception as e:
        logger.error(
            f"Error creating payment for user {data.user_id}: {e}", exc_info=True
        )
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


async def get_payment_by_external_id(external_invoice_id: str) -> Optional[Payment]:
    """Get payment by external invoice ID (YooKassa order_id)"""
    try:
        supabase = get_supabase()
        response = (
            supabase.table("payments")
            .select("*")
            .eq("external_invoice_id", external_invoice_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            return Payment(**response.data[0])
        return None
    except Exception as e:
        logger.error(
            f"Error getting payment by external_invoice_id {external_invoice_id}: {e}",
            exc_info=True,
        )
        return None


async def update_payment_status(
    payment_id: int, status: PaymentStatus
) -> Optional[Payment]:
    """Update payment status and updated_at timestamp"""
    try:
        supabase = get_supabase()
        response = (
            supabase.table("payments")
            .update(
                {"status": status.value, "updated_at": datetime.utcnow().isoformat()}
            )
            .eq("id", payment_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            logger.info(f"✅ Updated payment {payment_id} status to {status.value}")
            return Payment(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error updating payment {payment_id} status: {e}", exc_info=True)
        return None


async def update_payment_charges(
    payment_id: int, telegram_charge_id: str, provider_charge_id: str
) -> Optional[Payment]:
    """Update payment charge IDs and set status to SUCCESS"""
    try:
        supabase = get_supabase()
        response = (
            supabase.table("payments")
            .update(
                {
                    "telegram_payment_charge_id": telegram_charge_id,
                    "provider_payment_charge_id": provider_charge_id,
                    "status": PaymentStatus.SUCCESS.value,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            .eq("id", payment_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            logger.info(
                f"✅ Updated payment {payment_id} charges and marked as SUCCESS"
            )
            return Payment(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error updating payment {payment_id} charges: {e}", exc_info=True)
        return None


async def update_payment_with_yookassa_data(
    payment_id: int,
    external_invoice_id: str,
    confirmation_url: str,
    status: PaymentStatus,
) -> Optional[Payment]:
    """Update payment with YooKassa data (external_invoice_id, confirmation_url, status)"""
    try:
        supabase = get_supabase()
        response = (
            supabase.table("payments")
            .update(
                {
                    "external_invoice_id": external_invoice_id,
                    "confirmation_url": confirmation_url,
                    "status": status.value,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            .eq("id", payment_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            logger.info(
                f"✅ Updated payment {payment_id} with YooKassa data: "
                f"external_invoice_id={external_invoice_id}, status={status.value}"
            )
            return Payment(**response.data[0])
        return None
    except Exception as e:
        logger.error(
            f"Error updating payment {payment_id} with YooKassa data: {e}",
            exc_info=True,
        )
        return None


# Report functions


async def create_report(data: CreateReportDTO) -> Optional[Report]:
    """Create a new report with state NEW"""
    try:
        supabase = get_supabase()
        report_data = {
            "user_id": data.user_id,
            "articles": data.articles,
            "state": ReportState.NEW.value,
            "created_at": datetime.utcnow().isoformat(),
        }

        response = supabase.table("reports").insert(report_data).execute()

        if response.data and len(response.data) > 0:
            report = Report(**response.data[0])
            logger.info(
                f"✅ Created report {report.id} for user {data.user_id} (articles={data.articles})"
            )
            return report
        return None
    except Exception as e:
        logger.error(
            f"Error creating report for user {data.user_id}: {e}", exc_info=True
        )
        return None


async def update_report_state(report_id: int, state: ReportState) -> Optional[Report]:
    """Update report state and updated_at timestamp"""
    try:
        supabase = get_supabase()
        response = (
            supabase.table("reports")
            .update({"state": state.value, "updated_at": datetime.utcnow().isoformat()})
            .eq("id", report_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            logger.info(f"✅ Updated report {report_id} state to {state.value}")
            return Report(**response.data[0])
        return None
    except Exception as e:
        logger.error(f"Error updating report {report_id} state: {e}", exc_info=True)
        return None


# Conversion analytics functions


async def get_unique_user_ids_by_events(
    event_types: list[EventType],
    range_start: Optional[datetime] = None,
    range_end: Optional[datetime] = None,
) -> list[int]:
    """
    Get unique user IDs who have at least one event of any of the given types.

    Args:
        event_types: List of event types to filter by (OR logic)
        range_start: Optional lower bound for events.timestamp (inclusive)
        range_end: Optional upper bound for events.timestamp (inclusive).
            When range_start is None (all-time), only range_end is applied.

    Returns:
        list[int]: Unique user IDs
    """
    try:
        supabase = get_supabase()
        all_data: list[dict] = []
        batch_size = 1000
        offset = 0

        event_values = [et.value for et in event_types]

        while True:
            query = (
                supabase.table("events")
                .select("user_id,timestamp")
                .in_("event_type", event_values)
            )
            if range_start is not None:
                query = query.gte("timestamp", range_start.isoformat())
            if range_end is not None:
                query = query.lte("timestamp", range_end.isoformat())

            resp = query.range(offset, offset + batch_size - 1).execute()
            batch = resp.data or []
            all_data.extend(batch)

            if len(batch) < batch_size:
                break
            offset += batch_size

        unique_users = list({row["user_id"] for row in all_data})
        logger.info(f"📊 Unique users for events {event_values}: {len(unique_users)}")
        return unique_users
    except Exception as e:
        logger.error(
            f"Error fetching unique users by events {event_types}: {e}", exc_info=True
        )
        return []


async def count_unique_users_by_events(
    event_types: list[EventType],
    range_start: Optional[datetime] = None,
    range_end: Optional[datetime] = None,
) -> int:
    """
    Count unique users who have at least one event of any of the given types.

    Args:
        event_types: List of event types to filter by (OR logic)
        range_start: Optional lower bound for events.timestamp
        range_end: Optional upper bound for events.timestamp

    Returns:
        int: Number of unique users
    """
    return len(
        await get_unique_user_ids_by_events(
            event_types, range_start=range_start, range_end=range_end
        )
    )


async def get_usernames_by_ids(user_ids: list[int]) -> dict[int, Optional[str]]:
    """
    Fetch usernames for given user IDs from the users table.

    Args:
        user_ids: List of Telegram user IDs

    Returns:
        dict mapping user_id to username (None if not set)
    """
    if not user_ids:
        return {}
    try:
        supabase = get_supabase()
        result: dict[int, Optional[str]] = {}
        batch_size = 1000
        offset = 0

        while True:
            resp = (
                supabase.table("users")
                .select("id, username")
                .in_("id", user_ids)
                .range(offset, offset + batch_size - 1)
                .execute()
            )
            batch = resp.data or []
            for row in batch:
                result[row["id"]] = row.get("username")
            if len(batch) < batch_size:
                break
            offset += batch_size

        return result
    except Exception as e:
        logger.error(
            f"Error fetching usernames for {len(user_ids)} users: {e}", exc_info=True
        )
        return {}


# Admin broadcast query functions


def _fetch_all_rows(
    supabase, table: str, columns: str, filters: Optional[dict] = None
) -> list[dict]:
    """
    Fetch all rows from a Supabase table, handling the default 1000-row limit
    by paginating with .range().

    Args:
        supabase: Supabase client instance
        table: Table name
        columns: Columns to select (e.g. "user_id")
        filters: Optional dict of {column: value} equality filters

    Returns:
        list[dict]: All rows from the table matching the filters
    """
    all_data: list[dict] = []
    batch_size = 1000
    offset = 0

    while True:
        query = supabase.table(table).select(columns)
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        resp = query.range(offset, offset + batch_size - 1).execute()

        batch = resp.data or []
        all_data.extend(batch)

        if len(batch) < batch_size:
            break
        offset += batch_size

    return all_data


async def get_users_no_reports_no_payments() -> list[int]:
    """
    Get user IDs who pressed /start but never created a report or made a payment.

    Returns:
        list[int]: Telegram user IDs
    """
    try:
        supabase = get_supabase()

        # Fetch all user IDs (paginated)
        users_data = _fetch_all_rows(supabase, "users", "id")
        all_user_ids = {row["id"] for row in users_data}

        # Fetch user IDs that have at least one report (paginated)
        reports_data = _fetch_all_rows(supabase, "reports", "user_id")
        users_with_reports = {row["user_id"] for row in reports_data}

        # Fetch user IDs that have at least one successful payment (paginated)
        payments_data = _fetch_all_rows(
            supabase,
            "payments",
            "user_id",
            filters={"status": PaymentStatus.SUCCESS.value},
        )
        users_with_payments = {row["user_id"] for row in payments_data}

        # Users with no reports AND no payments
        result = list(all_user_ids - users_with_reports - users_with_payments)
        logger.info(f"📊 [ADMIN] Users with no activity: {len(result)}")
        return result
    except Exception as e:
        logger.error(
            f"Error fetching users with no reports/payments: {e}", exc_info=True
        )
        return []


async def get_users_one_report_no_payments() -> list[int]:
    """
    Get user IDs who used their trial report (exactly 1 report) but never made a payment.

    Returns:
        list[int]: Telegram user IDs
    """
    try:
        supabase = get_supabase()

        # Fetch all reports (paginated to avoid 1000-row limit)
        reports_data = _fetch_all_rows(supabase, "reports", "user_id")
        report_counts: dict[int, int] = {}
        for row in reports_data:
            uid = row["user_id"]
            report_counts[uid] = report_counts.get(uid, 0) + 1

        # Users with exactly 1 report
        users_one_report = {uid for uid, count in report_counts.items() if count == 1}

        # Fetch user IDs that have at least one successful payment (paginated)
        payments_data = _fetch_all_rows(
            supabase,
            "payments",
            "user_id",
            filters={"status": PaymentStatus.SUCCESS.value},
        )
        users_with_payments = {row["user_id"] for row in payments_data}

        # Users with exactly 1 report AND no successful payments
        result = list(users_one_report - users_with_payments)
        logger.info(
            f"📊 [ADMIN] Users who used trial (1 report, no payments): {len(result)}"
        )
        return result
    except Exception as e:
        logger.error(
            f"Error fetching users with 1 report/no payments: {e}", exc_info=True
        )
        return []


async def get_users_single_purchase() -> list[int]:
    """
    Get user IDs who made exactly one SINGLE report purchase.

    Returns:
        list[int]: Telegram user IDs
    """
    try:
        supabase = get_supabase()

        # Fetch successful SINGLE payments (paginated)
        payments_data = _fetch_all_rows(
            supabase,
            "payments",
            "user_id",
            filters={
                "option": ProductOption.SINGLE.value,
                "status": PaymentStatus.SUCCESS.value,
            },
        )

        # Count successful SINGLE payments per user
        payment_counts: dict[int, int] = {}
        for row in payments_data:
            uid = row["user_id"]
            payment_counts[uid] = payment_counts.get(uid, 0) + 1

        # Only users with exactly 1 successful SINGLE payment
        result = [uid for uid, count in payment_counts.items() if count == 1]
        logger.info(f"📊 [ADMIN] Users with SINGLE purchase: {len(result)}")
        return result
    except Exception as e:
        logger.error(f"Error fetching users with single purchase: {e}", exc_info=True)
        return []
