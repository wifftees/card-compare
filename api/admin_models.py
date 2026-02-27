"""Pydantic v2 request/response models and helpers for admin dashboard endpoints.

Covers:
- ``POST /api/admin/overview`` – business-metrics dashboard
- ``POST /api/admin/conversions`` – funnel conversion analytics
- Shared ``compute_range`` helper for range-preset resolution
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Range preset
# ---------------------------------------------------------------------------

class RangePreset(str, Enum):
    """Supported dashboard time-range presets."""

    ONE_DAY = "1d"
    SEVEN_DAYS = "7d"
    ONE_MONTH = "1m"
    ALL = "all"


def compute_range(preset: RangePreset) -> tuple[Optional[datetime], datetime]:
    """Derive ``(range_start, range_end)`` from a range preset.

    ``range_end`` is always server UTC "now".
    ``range_start`` is ``range_end − duration``, or ``None`` for *all*.

    Returns:
        A 2-tuple of ``(range_start, range_end)`` where ``range_start``
        may be ``None`` when the preset is ``all``.
    """
    range_end = datetime.now(timezone.utc)

    if preset == RangePreset.ONE_DAY:
        range_start = range_end - timedelta(days=1)
    elif preset == RangePreset.SEVEN_DAYS:
        range_start = range_end - timedelta(days=7)
    elif preset == RangePreset.ONE_MONTH:
        range_start = range_end - timedelta(days=30)
    elif preset == RangePreset.ALL:
        range_start = None
    else:
        raise ValueError(f"Unknown preset: {preset}")

    return range_start, range_end


# ---------------------------------------------------------------------------
# POST /api/admin/overview
# ---------------------------------------------------------------------------

class OverviewRequest(BaseModel):
    """Request body for ``POST /api/admin/overview``."""

    range: RangePreset


class CoreKPIs(BaseModel):
    """Core business KPIs (users & reports)."""

    new_users: int
    active_users: int
    reports_generated: int


class PaymentMetrics(BaseModel):
    """Aggregated payment metrics."""

    revenue: int
    paying_users: int
    by_status: dict[str, int]
    revenue_by_option: dict[str, int]


class ReferrerEntry(BaseModel):
    """A single row in a top-referrers leaderboard."""

    user_id: int
    count: int


class RevenueReferrerEntry(BaseModel):
    """A single row in a top-referrers-by-revenue leaderboard."""

    user_id: int
    revenue: int


class ReferralFunnel(BaseModel):
    """Aggregated counts for the referred-user lifecycle funnel."""

    created: int
    activated: int
    paid: int


class ReferralMetrics(BaseModel):
    """Referral programme metrics."""

    active_referrers: int
    new_referred_users: int
    referrals_per_referrer_avg: Optional[float]
    referrals_per_referrer_median: Optional[float]
    top_referrers_by_referred_users: list[ReferrerEntry]
    qualified_referrals_count: int
    qualified_referrals_rate: Optional[float]
    referred_revenue: int
    top_referrers_by_referred_revenue: list[RevenueReferrerEntry]
    referral_funnel: ReferralFunnel
    estimated_bonus_earned: int


class RepeatReporters(BaseModel):
    """Repeat-reporter metrics (always computed all-time)."""

    repeat_reporters_count: int
    repeat_reporters_rate: Optional[float]


class PayerSegmentation(BaseModel):
    """Payer lifecycle and frequency segmentation counts."""

    new_payer_count: int
    returning_payer_count: int
    churned_payer_count: int
    one_time_payer_count: int
    repeat_payer_count: int
    power_payer_count: int


class OverviewResponse(BaseModel):
    """Response body for ``POST /api/admin/overview``."""

    range: RangePreset
    range_start: Optional[datetime]
    range_end: datetime
    core_kpis: CoreKPIs
    payments: PaymentMetrics
    referrals: ReferralMetrics
    repeat_reporters: RepeatReporters
    payer_segmentation: PayerSegmentation


# ---------------------------------------------------------------------------
# POST /api/admin/conversions
# ---------------------------------------------------------------------------

class ConversionsRequest(BaseModel):
    """Request body for ``POST /api/admin/conversions``."""

    range: RangePreset = RangePreset.ALL
    categories: list[int] = Field(min_length=1)


class ConversionGroup(BaseModel):
    """Size of a single conversion category's user set."""

    category: int
    size: int
    range_applied: bool


class ConversionStep(BaseModel):
    """Adjacent-transition conversion between two categories."""

    from_category: int
    to_category: int
    numerator: int
    denominator: int
    percent: Optional[float]


class ConversionsResponse(BaseModel):
    """Response body for ``POST /api/admin/conversions``."""

    range: RangePreset
    range_start: Optional[datetime]
    range_end: datetime
    groups: list[ConversionGroup]
    conversions: list[ConversionStep]


# ---------------------------------------------------------------------------
# POST /api/admin/broadcast
# ---------------------------------------------------------------------------

class BroadcastRequest(BaseModel):
    """Request body for ``POST /api/admin/broadcast``."""

    category: int
    message: str = Field(min_length=1)


class BroadcastResponse(BaseModel):
    """Response body for ``POST /api/admin/broadcast``."""

    sent: int
    failed: int
    total: int


# ---------------------------------------------------------------------------
# GET /api/admin/prices
# ---------------------------------------------------------------------------

class PriceRow(BaseModel):
    """A single price configuration row."""

    option: str
    price: int
    reports_amount: int


class PricesListResponse(BaseModel):
    """Response body for ``GET /api/admin/prices``."""

    prices: list[PriceRow]


# ---------------------------------------------------------------------------
# POST /api/admin/prices
# ---------------------------------------------------------------------------

class PriceUpdateRow(BaseModel):
    """A single price row for bulk update."""

    option: str
    price: int = Field(ge=0)
    reports_amount: int = Field(gt=0)


class PricesUpdateRequest(BaseModel):
    """Request body for ``POST /api/admin/prices``."""

    prices: list[PriceUpdateRow] = Field(min_length=1)


class PricesUpdateResponse(BaseModel):
    """Response body for ``POST /api/admin/prices``."""

    updated: int
    prices: list[PriceRow]
