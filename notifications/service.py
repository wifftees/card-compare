"""Core notification service — runs one cycle of the notification worker."""
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramNotFound, TelegramBadRequest

from .models import (
    CampaignTarget,
    NotificationCampaign,
    NotificationStep,
    NotificationStatus,
    UserNotification,
)
from .queries import (
    get_enabled_campaigns,
    get_campaign_steps,
    get_active_user_notifications,
    get_due_notifications,
    upsert_user_notification,
    advance_notification,
    mark_notification_status,
    cancel_notifications_for_users,
)
from .registry import registry

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, bot: Bot):
        self._bot = bot

    async def run_cycle(self) -> None:
        logger.info("🔔 Notification cycle started")
        campaigns = await get_enabled_campaigns()
        if not campaigns:
            logger.info("🔔 No enabled campaigns, cycle finished")
            return

        for campaign in campaigns:
            resolver = registry.get(campaign.id)
            if resolver is None:
                logger.warning(f"No resolver registered for campaign '{campaign.id}', skipping")
                continue

            try:
                await self._process_campaign(campaign, resolver)
            except Exception as e:
                logger.error(
                    f"Error processing campaign '{campaign.id}': {e}",
                    exc_info=True,
                )

        logger.info("🔔 Notification cycle finished")

    async def _process_campaign(self, campaign: NotificationCampaign, resolver) -> None:
        targets: list[CampaignTarget] = await resolver()
        steps = await get_campaign_steps(campaign.id)
        if not steps:
            logger.warning(f"Campaign '{campaign.id}' has no steps configured, skipping")
            return

        target_map: dict[int, CampaignTarget] = {t.user_id: t for t in targets}
        active_records = await get_active_user_notifications(campaign.id)
        active_map: dict[int, UserNotification] = {r.user_id: r for r in active_records}

        enrolled, reset, cancelled = await self._sync_enrollments(
            campaign.id, target_map, active_map, steps,
        )
        if enrolled or reset or cancelled:
            logger.info(
                f"Campaign '{campaign.id}' sync: "
                f"enrolled={enrolled}, reset={reset}, cancelled={cancelled}"
            )

        now = datetime.now(timezone.utc)
        due = await get_due_notifications(campaign.id, now)

        if not due:
            active = await get_active_user_notifications(campaign.id)
            if active:
                nearest = min(n.next_send_at for n in active)
                logger.info(
                    f"Campaign '{campaign.id}': {len(active)} active, "
                    f"nearest next_send_at={nearest.isoformat()}, now={now.isoformat()}"
                )
            return

        sent = 0
        blocked = 0
        for notif in due:
            ok = await self._send_and_advance(notif, campaign, steps)
            if ok:
                sent += 1
            else:
                blocked += 1

        logger.info(
            f"Campaign '{campaign.id}' send: "
            f"due={len(due)}, sent={sent}, blocked={blocked}"
        )

    async def _sync_enrollments(
        self,
        campaign_id: str,
        target_map: dict[int, CampaignTarget],
        active_map: dict[int, UserNotification],
        steps: list[NotificationStep],
    ) -> tuple[int, int, int]:
        """Returns (enrolled, reset, cancelled) counts."""
        first_delay = timedelta(seconds=steps[0].delay_seconds)

        users_to_cancel: list[int] = []
        reset_count = 0
        for uid, record in active_map.items():
            if uid not in target_map:
                users_to_cancel.append(uid)
                continue
            target = target_map[uid]
            if record.trigger_event_at != target.trigger_at:
                next_send = target.trigger_at + first_delay
                await upsert_user_notification(uid, campaign_id, target.trigger_at, next_send)
                reset_count += 1

        if users_to_cancel:
            await cancel_notifications_for_users(campaign_id, users_to_cancel)

        enrolled_count = 0
        for uid, target in target_map.items():
            if uid not in active_map:
                next_send = target.trigger_at + first_delay
                await upsert_user_notification(uid, campaign_id, target.trigger_at, next_send)
                enrolled_count += 1
                logger.info(
                    f"Enrolled user {uid} in '{campaign_id}': "
                    f"trigger_at={target.trigger_at.isoformat()}, "
                    f"next_send_at={next_send.isoformat()}"
                )

        return enrolled_count, reset_count, len(users_to_cancel)

    async def _send_and_advance(
        self,
        notif: UserNotification,
        campaign: NotificationCampaign,
        steps: list[NotificationStep],
    ) -> bool:
        """Send notification and advance step. Returns True if sent, False if blocked."""
        logger.info(
            f"Sending '{campaign.id}' step {notif.current_step} to user {notif.user_id}"
        )
        success = await self._try_send(notif.user_id, campaign.message_template)

        if not success:
            await mark_notification_status(notif.id, NotificationStatus.BLOCKED)
            return False

        new_step = notif.current_step + 1
        now = datetime.now(timezone.utc)

        if new_step < len(steps):
            delay = timedelta(seconds=steps[new_step].delay_seconds)
            await advance_notification(notif.id, new_step, now + delay)
        elif campaign.repeat_last_step:
            delay = timedelta(seconds=steps[-1].delay_seconds)
            await advance_notification(notif.id, new_step, now + delay)
        else:
            await mark_notification_status(notif.id, NotificationStatus.COMPLETED)

        return True

    async def _try_send(self, user_id: int, text: str) -> bool:
        """Returns True on success, False if the user is unreachable."""
        try:
            await self._bot.send_message(
                chat_id=user_id, text=text, parse_mode=ParseMode.HTML,
            )
            return True
        except (TelegramForbiddenError, TelegramNotFound):
            logger.warning(f"User {user_id} is unreachable (blocked/deactivated)")
            return False
        except TelegramBadRequest as e:
            if "chat not found" in str(e).lower():
                logger.warning(f"User {user_id} chat not found")
                return False
            logger.error(f"Bad request sending to user {user_id}: {e}", exc_info=True)
            return True
        except Exception as e:
            logger.error(f"Transient error sending to user {user_id}: {e}", exc_info=True)
            return True
