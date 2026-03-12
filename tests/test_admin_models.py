"""Tests for admin dashboard models and range preset helpers.

Covers:
- Task 6.1: Range preset helper (1d/7d/1m/all) and boundary handling
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


from api.admin_models import RangePreset, compute_range


class TestComputeRange:
    """Test range preset computation and boundary handling."""

    def test_one_day_preset(self) -> None:
        """1d preset should return range_end - 1 day."""
        range_start, range_end = compute_range(RangePreset.ONE_DAY)

        assert range_start is not None
        assert range_end.tzinfo == timezone.utc
        assert range_start.tzinfo == timezone.utc

        delta = range_end - range_start
        assert delta == timedelta(days=1)

        # Verify range_end is approximately "now"
        now = datetime.now(timezone.utc)
        assert abs((now - range_end).total_seconds()) < 2

    def test_seven_days_preset(self) -> None:
        """7d preset should return range_end - 7 days."""
        range_start, range_end = compute_range(RangePreset.SEVEN_DAYS)

        assert range_start is not None
        assert range_end.tzinfo == timezone.utc
        assert range_start.tzinfo == timezone.utc

        delta = range_end - range_start
        assert delta == timedelta(days=7)

        now = datetime.now(timezone.utc)
        assert abs((now - range_end).total_seconds()) < 2

    def test_one_month_preset(self) -> None:
        """1m preset should return range_end - 30 days."""
        range_start, range_end = compute_range(RangePreset.ONE_MONTH)

        assert range_start is not None
        assert range_end.tzinfo == timezone.utc
        assert range_start.tzinfo == timezone.utc

        delta = range_end - range_start
        assert delta == timedelta(days=30)

        now = datetime.now(timezone.utc)
        assert abs((now - range_end).total_seconds()) < 2

    def test_all_preset(self) -> None:
        """'all' preset should return None for range_start."""
        range_start, range_end = compute_range(RangePreset.ALL)

        assert range_start is None
        assert range_end.tzinfo == timezone.utc

        now = datetime.now(timezone.utc)
        assert abs((now - range_end).total_seconds()) < 2

    def test_range_end_is_always_utc_now(self) -> None:
        """All presets should use UTC 'now' as range_end."""
        presets = [
            RangePreset.ONE_DAY,
            RangePreset.SEVEN_DAYS,
            RangePreset.ONE_MONTH,
            RangePreset.ALL,
        ]

        now_before = datetime.now(timezone.utc)

        for preset in presets:
            _, range_end = compute_range(preset)
            assert range_end.tzinfo == timezone.utc

            now_after = datetime.now(timezone.utc)
            assert now_before <= range_end <= now_after

    def test_range_start_always_before_range_end(self) -> None:
        """When range_start is not None, it must be < range_end."""
        presets_with_start = [
            RangePreset.ONE_DAY,
            RangePreset.SEVEN_DAYS,
            RangePreset.ONE_MONTH,
        ]

        for preset in presets_with_start:
            range_start, range_end = compute_range(preset)
            assert range_start is not None
            assert range_start < range_end

    def test_boundary_handling_negative_duration(self) -> None:
        """Range computation should never produce negative duration."""
        # This tests that the implementation correctly subtracts duration
        # from range_end, not the other way around
        range_start, range_end = compute_range(RangePreset.ONE_DAY)

        assert range_start is not None
        assert (range_end - range_start).total_seconds() > 0

    def test_timezone_consistency(self) -> None:
        """All returned datetimes must be timezone-aware UTC."""
        for preset in RangePreset:
            range_start, range_end = compute_range(preset)

            assert range_end.tzinfo is not None
            assert range_end.tzinfo == timezone.utc

            if range_start is not None:
                assert range_start.tzinfo is not None
                assert range_start.tzinfo == timezone.utc

    def test_multiple_calls_produce_increasing_times(self) -> None:
        """Sequential calls should produce monotonically increasing range_end."""
        _, first_end = compute_range(RangePreset.ONE_DAY)

        # Small delay to ensure time advances
        import time

        time.sleep(0.01)

        _, second_end = compute_range(RangePreset.ONE_DAY)

        assert second_end >= first_end
