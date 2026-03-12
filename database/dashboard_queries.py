"""Query helpers that compute admin-dashboard overview metrics.

Each public ``fetch_*`` function accepts a time range and returns
the corresponding Pydantic response model defined in ``api.admin_models``.
The Supabase client is synchronous; functions are ``async`` only to match
the existing convention used in ``database.queries``.
"""

from __future__ import annotations

import logging
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from database.client import get_supabase
from database.models import EventType, PaymentStatus, ReportState

from api.admin_models import (
    CoreKPIs,
    PayerSegmentation,
    PaymentMetrics,
    ReferralFunnel,
    ReferralMetrics,
    ReferrerEntry,
    RepeatReporters,
    RevenueReferrerEntry,
)

logger = logging.getLogger(__name__)

_BATCH = 1000
_DEFAULT_TOP_N = 10


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iso(dt: datetime) -> str:
    """Format *dt* as ISO-8601 string suitable for PostgREST filters."""
    return dt.isoformat()


def _parse_dt(raw: str) -> datetime:
    """Parse an ISO-8601 string returned by Supabase into a tz-aware datetime."""
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _fetch_all(build_query: Callable[[], Any]) -> list[dict[str, Any]]:
    """Paginate through all rows for the query produced by *build_query*.

    *build_query* is called once per page so that each invocation starts from
    a fresh ``SelectRequestBuilder`` (required because ``.range()`` mutates the
    builder's internal state).
    """
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch = (build_query().range(offset, offset + _BATCH - 1).execute()).data or []
        rows.extend(batch)
        if len(batch) < _BATCH:
            break
        offset += _BATCH
    return rows


def _apply_range(
    query: Any,
    column: str,
    range_start: Optional[datetime],
    range_end: datetime,
) -> Any:
    """Apply ``[range_start, range_end]`` filters on *column*."""
    if range_start is not None:
        query = query.gte(column, _iso(range_start))
    return query.lte(column, _iso(range_end))


# ---------------------------------------------------------------------------
# 2.1  Core KPIs
# ---------------------------------------------------------------------------


async def fetch_core_kpis(
    range_start: Optional[datetime],
    range_end: datetime,
) -> CoreKPIs:
    """Compute ``core_kpis`` section of the overview response."""
    sb = get_supabase()
    end_iso = _iso(range_end)

    # --- new_users ---
    q = sb.table("users").select("id", count="exact")  # type: ignore[arg-type]
    if range_start is not None:
        q = q.gte("created_at", _iso(range_start))
    q = q.lte("created_at", end_iso)
    new_users: int = q.execute().count or 0

    # --- active_users (skip for "all" — range_start is None) ---
    if range_start is not None:
        active_users: int = (
            sb.table("users")
            .select("id", count="exact")  # type: ignore[arg-type]
            .gte("last_active_at", _iso(range_start))
            .lte("last_active_at", end_iso)
            .execute()
        ).count or 0
    else:
        active_users = 0

    # --- reports_generated (updated_at preferred, created_at fallback) ---
    # Two disjoint count queries cover the COALESCE logic PostgREST lacks.
    # 1) GENERATED with updated_at IS NOT NULL and updated_at in range
    q1 = (
        sb.table("reports")
        .select("id", count="exact")  # type: ignore[arg-type]
        .eq("state", ReportState.GENERATED.value)
        .not_.is_("updated_at", "null")
    )
    q1 = _apply_range(q1, "updated_at", range_start, range_end)
    count_with_updated: int = q1.execute().count or 0

    # 2) GENERATED with updated_at IS NULL and created_at in range
    q2 = (
        sb.table("reports")
        .select("id", count="exact")  # type: ignore[arg-type]
        .eq("state", ReportState.GENERATED.value)
        .is_("updated_at", "null")
    )
    q2 = _apply_range(q2, "created_at", range_start, range_end)
    count_without_updated: int = q2.execute().count or 0

    return CoreKPIs(
        new_users=new_users,
        active_users=active_users,
        reports_generated=count_with_updated + count_without_updated,
    )


# ---------------------------------------------------------------------------
# 2.2  Payment metrics
# ---------------------------------------------------------------------------


async def fetch_payment_metrics(
    range_start: Optional[datetime],
    range_end: datetime,
) -> PaymentMetrics:
    """Compute ``payments`` section of the overview response."""
    sb = get_supabase()

    def _build() -> Any:
        q = sb.table("payments").select("user_id,total_price,status,option")
        return _apply_range(q, "created_at", range_start, range_end)

    rows = _fetch_all(_build)

    revenue = 0
    paying_user_ids: set[int] = set()
    by_status: Counter[str] = Counter()
    rev_by_option: defaultdict[str, int] = defaultdict(int)

    for row in rows:
        status = row["status"]
        by_status[status] += 1
        if status == PaymentStatus.SUCCESS.value:
            revenue += row["total_price"]
            paying_user_ids.add(row["user_id"])
            rev_by_option[row["option"]] += row["total_price"]

    return PaymentMetrics(
        revenue=revenue,
        paying_users=len(paying_user_ids),
        by_status=dict(by_status),
        revenue_by_option=dict(rev_by_option),
    )


# ---------------------------------------------------------------------------
# 2.3  Referral metrics
# ---------------------------------------------------------------------------


async def fetch_referral_metrics(
    range_start: Optional[datetime],
    range_end: datetime,
    *,
    top_n: int = _DEFAULT_TOP_N,
) -> ReferralMetrics:
    """Compute ``referrals`` section of the overview response."""
    sb = get_supabase()

    # -- 1. All referred users (all-time) — needed for revenue attribution --
    all_referred = _fetch_all(
        lambda: sb.table("users").select("id,invited_by").not_.is_("invited_by", "null")
    )
    inviter_of: dict[int, int] = {r["id"]: r["invited_by"] for r in all_referred}

    # -- 2. Referred users created in range --
    def _build_range_referred() -> Any:
        q = sb.table("users").select("id,invited_by").not_.is_("invited_by", "null")
        return _apply_range(q, "created_at", range_start, range_end)

    range_referred = _fetch_all(_build_range_referred)
    range_referred_ids: set[int] = {r["id"] for r in range_referred}
    new_referred_users = len(range_referred_ids)

    by_inviter: Counter[int] = Counter()
    for r in range_referred:
        by_inviter[r["invited_by"]] += 1

    active_referrers = len(by_inviter)

    if active_referrers:
        counts = list(by_inviter.values())
        avg: Optional[float] = sum(counts) / len(counts)
        med: Optional[float] = float(statistics.median(counts))
    else:
        avg = med = None

    top_users = sorted(by_inviter.items(), key=lambda x: x[1], reverse=True)[:top_n]

    # -- 3. CLICK_COMPARE events in range → qualified referrals & funnel --
    def _build_activation() -> Any:
        q = (
            sb.table("events")
            .select("user_id")
            .eq("event_type", EventType.CLICK_COMPARE.value)
        )
        return _apply_range(q, "timestamp", range_start, range_end)

    activated_ids: set[int] = {r["user_id"] for r in _fetch_all(_build_activation)}
    qualified_ids = range_referred_ids & activated_ids
    qualified_count = len(qualified_ids)

    # -- 4. SUCCESS payments in range → revenue, bonus, funnel "paid" --
    def _build_payments() -> Any:
        q = (
            sb.table("payments")
            .select("user_id,total_price")
            .eq("status", PaymentStatus.SUCCESS.value)
        )
        return _apply_range(q, "created_at", range_start, range_end)

    payment_rows = _fetch_all(_build_payments)

    referred_revenue = 0
    rev_by_inviter: Counter[int] = Counter()
    bonus_total = 0
    paid_referred_in_range: set[int] = set()

    for p in payment_rows:
        uid = p["user_id"]
        if uid not in inviter_of:
            continue
        price: int = p["total_price"]
        referred_revenue += price
        rev_by_inviter[inviter_of[uid]] += price
        bonus_total += math.ceil(price * 0.2)
        if uid in range_referred_ids:
            paid_referred_in_range.add(uid)

    top_rev = sorted(
        rev_by_inviter.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:top_n]

    return ReferralMetrics(
        active_referrers=active_referrers,
        new_referred_users=new_referred_users,
        referrals_per_referrer_avg=avg,
        referrals_per_referrer_median=med,
        top_referrers_by_referred_users=[
            ReferrerEntry(user_id=u, count=c) for u, c in top_users
        ],
        qualified_referrals_count=qualified_count,
        qualified_referrals_rate=(
            qualified_count / new_referred_users if new_referred_users else None
        ),
        referred_revenue=referred_revenue,
        top_referrers_by_referred_revenue=[
            RevenueReferrerEntry(user_id=u, revenue=r) for u, r in top_rev
        ],
        referral_funnel=ReferralFunnel(
            created=new_referred_users,
            activated=qualified_count,
            paid=len(paid_referred_in_range),
        ),
        estimated_bonus_earned=bonus_total,
    )


# ---------------------------------------------------------------------------
# 2.4  Repeat reporters (all-time, range-independent)
# ---------------------------------------------------------------------------


async def fetch_repeat_reporters() -> RepeatReporters:
    """Compute ``repeat_reporters`` section (always all-time)."""
    sb = get_supabase()

    rows = _fetch_all(
        lambda: (
            sb.table("reports")
            .select("user_id")
            .eq("state", ReportState.GENERATED.value)
        )
    )

    reports_per_user: Counter[int] = Counter()
    for row in rows:
        reports_per_user[row["user_id"]] += 1

    total_reporters = len(reports_per_user)
    repeat_count = sum(1 for c in reports_per_user.values() if c >= 2)

    return RepeatReporters(
        repeat_reporters_count=repeat_count,
        repeat_reporters_rate=(
            repeat_count / total_reporters if total_reporters else None
        ),
    )


# ---------------------------------------------------------------------------
# 2.5  Payer segmentation
# ---------------------------------------------------------------------------


async def fetch_payer_segmentation(
    range_start: Optional[datetime],
    range_end: datetime,
) -> PayerSegmentation:
    """Compute ``payer_segmentation`` section of the overview response.

    *Lifecycle* (new / returning / churned) is range-aware.
    *Frequency* (one-time / repeat / power) is always all-time.
    """
    sb = get_supabase()

    rows = _fetch_all(
        lambda: (
            sb.table("payments")
            .select("user_id,created_at")
            .eq("status", PaymentStatus.SUCCESS.value)
        )
    )

    user_payments: defaultdict[int, list[datetime]] = defaultdict(list)
    for row in rows:
        user_payments[row["user_id"]].append(_parse_dt(row["created_at"]))

    # -- Frequency (all-time) --
    one_time = repeat = power = 0
    for payments in user_payments.values():
        n = len(payments)
        if n == 1:
            one_time += 1
        elif n <= 3:
            repeat += 1
        else:
            power += 1

    # -- Lifecycle (range-aware) --
    new_payer = returning_payer = churned_payer = 0
    churn_cutoff = range_end - timedelta(days=60)

    for payments in user_payments.values():
        payments_sorted = sorted(payments)
        first = payments_sorted[0]
        last = payments_sorted[-1]

        first_in_range = (
            range_start is None or first >= range_start
        ) and first <= range_end

        if first_in_range:
            new_payer += 1

        if range_start is not None:
            has_before = any(p < range_start for p in payments_sorted)
            has_in = any(range_start <= p <= range_end for p in payments_sorted)
            if has_before and has_in:
                returning_payer += 1

        if last < churn_cutoff:
            churned_payer += 1

    return PayerSegmentation(
        new_payer_count=new_payer,
        returning_payer_count=returning_payer,
        churned_payer_count=churned_payer,
        one_time_payer_count=one_time,
        repeat_payer_count=repeat,
        power_payer_count=power,
    )
