"""Database queries for the notification campaigns system"""

import logging
from datetime import datetime
from typing import Optional

from database.client import get_supabase
from .models import (
    NotificationCampaign,
    NotificationStep,
    UserNotification,
    NotificationStatus,
)

logger = logging.getLogger(__name__)


def _supabase():
    return get_supabase()


async def get_enabled_campaigns() -> list[NotificationCampaign]:
    try:
        resp = (
            _supabase()
            .table("notification_campaigns")
            .select("*")
            .eq("enabled", True)
            .execute()
        )
        return [NotificationCampaign(**row) for row in (resp.data or [])]
    except Exception as e:
        logger.error(f"Error fetching enabled campaigns: {e}", exc_info=True)
        return []


async def get_campaign_steps(campaign_id: str) -> list[NotificationStep]:
    try:
        resp = (
            _supabase()
            .table("notification_steps")
            .select("*")
            .eq("campaign_id", campaign_id)
            .order("step_order")
            .execute()
        )
        return [NotificationStep(**row) for row in (resp.data or [])]
    except Exception as e:
        logger.error(
            f"Error fetching steps for campaign {campaign_id}: {e}", exc_info=True
        )
        return []


async def get_active_user_notifications(campaign_id: str) -> list[UserNotification]:
    """All ACTIVE records for a given campaign."""
    try:
        resp = (
            _supabase()
            .table("user_notifications")
            .select("*")
            .eq("campaign_id", campaign_id)
            .eq("status", NotificationStatus.ACTIVE.value)
            .execute()
        )
        return [UserNotification(**row) for row in (resp.data or [])]
    except Exception as e:
        logger.error(
            f"Error fetching active user_notifications for {campaign_id}: {e}",
            exc_info=True,
        )
        return []


async def get_due_notifications(
    campaign_id: str, now: datetime
) -> list[UserNotification]:
    """ACTIVE records whose next_send_at <= now."""
    try:
        resp = (
            _supabase()
            .table("user_notifications")
            .select("*")
            .eq("campaign_id", campaign_id)
            .eq("status", NotificationStatus.ACTIVE.value)
            .lte("next_send_at", now.isoformat())
            .execute()
        )
        return [UserNotification(**row) for row in (resp.data or [])]
    except Exception as e:
        logger.error(
            f"Error fetching due notifications for {campaign_id}: {e}", exc_info=True
        )
        return []


async def upsert_user_notification(
    user_id: int,
    campaign_id: str,
    trigger_event_at: datetime,
    next_send_at: datetime,
) -> Optional[UserNotification]:
    """Create or reset a user notification record."""
    now = datetime.utcnow().isoformat()
    data = {
        "user_id": user_id,
        "campaign_id": campaign_id,
        "status": NotificationStatus.ACTIVE.value,
        "current_step": 0,
        "trigger_event_at": trigger_event_at.isoformat(),
        "last_sent_at": None,
        "next_send_at": next_send_at.isoformat(),
        "created_at": now,
        "updated_at": now,
    }
    try:
        resp = (
            _supabase()
            .table("user_notifications")
            .upsert(data, on_conflict="user_id,campaign_id")
            .execute()
        )
        if resp.data:
            return UserNotification(**resp.data[0])
        return None
    except Exception as e:
        logger.error(
            f"Error upserting user_notification user={user_id} campaign={campaign_id}: {e}",
            exc_info=True,
        )
        return None


async def advance_notification(
    notification_id: int,
    new_step: int,
    next_send_at: datetime,
) -> None:
    """Advance a notification to the next step after successful send."""
    now = datetime.utcnow().isoformat()
    try:
        _supabase().table("user_notifications").update(
            {
                "current_step": new_step,
                "last_sent_at": now,
                "next_send_at": next_send_at.isoformat(),
                "updated_at": now,
            }
        ).eq("id", notification_id).execute()
    except Exception as e:
        logger.error(
            f"Error advancing notification {notification_id}: {e}", exc_info=True
        )


async def mark_notification_status(
    notification_id: int,
    status: NotificationStatus,
) -> None:
    now = datetime.utcnow().isoformat()
    try:
        _supabase().table("user_notifications").update(
            {
                "status": status.value,
                "updated_at": now,
            }
        ).eq("id", notification_id).execute()
    except Exception as e:
        logger.error(
            f"Error marking notification {notification_id} as {status.value}: {e}",
            exc_info=True,
        )


async def cancel_notifications_for_users(
    campaign_id: str,
    user_ids: list[int],
) -> None:
    """Cancel ACTIVE notifications for users no longer in the target audience."""
    if not user_ids:
        return
    now = datetime.utcnow().isoformat()
    try:
        _supabase().table("user_notifications").update(
            {
                "status": NotificationStatus.CANCELLED.value,
                "updated_at": now,
            }
        ).eq("campaign_id", campaign_id).eq(
            "status", NotificationStatus.ACTIVE.value
        ).in_("user_id", user_ids).execute()
    except Exception as e:
        logger.error(
            f"Error cancelling notifications for campaign {campaign_id}: {e}",
            exc_info=True,
        )
