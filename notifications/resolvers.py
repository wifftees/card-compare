"""Concrete campaign resolvers.

Each resolver returns users who currently qualify for a campaign together with
the timestamp that serves as the starting point for the notification schedule.

Import this module at startup so the decorators register the resolvers.
"""
import logging
from datetime import datetime

from database.client import get_supabase
from database.models import EventType, ReportState
from .models import CampaignTarget
from .registry import registry

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


def _supabase():
    return get_supabase()


def _fetch_all(table: str, columns: str, filters: dict | None = None) -> list[dict]:
    """Paginate through a Supabase table to bypass the 1000-row default limit."""
    all_data: list[dict] = []
    offset = 0
    while True:
        query = _supabase().table(table).select(columns)
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        batch = (query.range(offset, offset + BATCH_SIZE - 1).execute()).data or []
        all_data.extend(batch)
        if len(batch) < BATCH_SIZE:
            break
        offset += BATCH_SIZE
    return all_data


@registry.resolver("click_example_report")
async def resolve_click_example_report() -> list[CampaignTarget]:
    """Users who clicked CLICK_EXAMPLE_REPORT but have zero GENERATED reports."""
    try:
        events = _fetch_all(
            "events", "user_id, timestamp",
            filters={"event_type": EventType.CLICK_EXAMPLE_REPORT.value},
        )
        if not events:
            return []

        latest_per_user: dict[int, datetime] = {}
        for row in events:
            uid = row["user_id"]
            ts = datetime.fromisoformat(row["timestamp"])
            if uid not in latest_per_user or ts > latest_per_user[uid]:
                latest_per_user[uid] = ts

        reports = _fetch_all(
            "reports", "user_id",
            filters={"state": ReportState.GENERATED.value},
        )
        users_with_reports = {r["user_id"] for r in reports}

        targets = [
            CampaignTarget(user_id=uid, trigger_at=ts)
            for uid, ts in latest_per_user.items()
            if uid not in users_with_reports
        ]
        logger.info(f"Resolver click_example_report: {len(targets)} targets")
        return targets
    except Exception as e:
        logger.error(f"Error in click_example_report resolver: {e}", exc_info=True)
        return []


@registry.resolver("click_start_no_report")
async def resolve_click_start_no_report() -> list[CampaignTarget]:
    """Users who clicked CLICK_START but never clicked CLICK_EXAMPLE_REPORT
    and have zero reports of any state."""
    try:
        start_events = _fetch_all(
            "events", "user_id, timestamp",
            filters={"event_type": EventType.CLICK_START.value},
        )
        if not start_events:
            return []

        latest_per_user: dict[int, datetime] = {}
        for row in start_events:
            uid = row["user_id"]
            ts = datetime.fromisoformat(row["timestamp"])
            if uid not in latest_per_user or ts > latest_per_user[uid]:
                latest_per_user[uid] = ts

        example_events = _fetch_all(
            "events", "user_id",
            filters={"event_type": EventType.CLICK_EXAMPLE_REPORT.value},
        )
        users_with_example = {r["user_id"] for r in example_events}

        reports = _fetch_all("reports", "user_id")
        users_with_reports = {r["user_id"] for r in reports}

        exclude = users_with_example | users_with_reports
        targets = [
            CampaignTarget(user_id=uid, trigger_at=ts)
            for uid, ts in latest_per_user.items()
            if uid not in exclude
        ]
        logger.info(f"Resolver click_start_no_report: {len(targets)} targets")
        return targets
    except Exception as e:
        logger.error(f"Error in click_start_no_report resolver: {e}", exc_info=True)
        return []


@registry.resolver("generated_report")
async def resolve_generated_report() -> list[CampaignTarget]:
    """Users who have exactly one GENERATED report.

    trigger_at = updated_at of their single GENERATED report.
    """
    try:
        reports = _fetch_all(
            "reports", "user_id, updated_at",
            filters={"state": ReportState.GENERATED.value},
        )
        if not reports:
            return []

        user_reports: dict[int, list[datetime]] = {}
        for row in reports:
            uid = row["user_id"]
            ts_raw = row.get("updated_at") or row.get("created_at")
            if ts_raw is None:
                continue
            ts = datetime.fromisoformat(ts_raw)
            if uid not in user_reports:
                user_reports[uid] = []
            user_reports[uid].append(ts)

        targets = [
            CampaignTarget(user_id=uid, trigger_at=timestamps[0])
            for uid, timestamps in user_reports.items()
            if len(timestamps) == 1
        ]
        logger.info(f"Resolver generated_report: {len(targets)} targets")
        return targets
    except Exception as e:
        logger.error(f"Error in generated_report resolver: {e}", exc_info=True)
        return []
