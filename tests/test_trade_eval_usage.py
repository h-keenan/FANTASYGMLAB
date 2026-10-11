import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo as ZoneInfoShim

from modules import premium
from modules import trade_eval_usage


class TestWeekStartBoundary(unittest.TestCase):
    """Monday 00:00 reset boundary, computed in the user's own timezone."""

    def test_week_start_is_monday_midnight_in_given_timezone(self):
        # Wednesday 2026-10-14 15:00 UTC -> most recent Monday in
        # America/New_York (UTC-4 in October) is 2026-10-12 00:00 local,
        # i.e. 2026-10-12T04:00:00+00:00.
        now = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)
        boundary = trade_eval_usage.week_start_utc(now, "America/New_York")
        self.assertEqual(boundary.isoformat(), "2026-10-12T04:00:00+00:00")

    def test_timestamp_just_before_monday_local_midnight_is_prior_week(self):
        # Sunday 23:59:59 local time in America/New_York is still the prior
        # week — one second before the Monday boundary.
        just_before = datetime(2026, 10, 11, 23, 59, 59, tzinfo=ZoneInfoShim("America/New_York"))
        boundary_for_just_before = trade_eval_usage.week_start_utc(just_before, "America/New_York")
        boundary_a_week_later = trade_eval_usage.week_start_utc(
            datetime(2026, 10, 12, 0, 0, 1, tzinfo=ZoneInfoShim("America/New_York")),
            "America/New_York",
        )
        self.assertNotEqual(boundary_for_just_before, boundary_a_week_later)
        self.assertEqual(
            boundary_for_just_before.isoformat(), "2026-10-05T04:00:00+00:00"
        )

    def test_timestamp_just_after_monday_local_midnight_is_current_week(self):
        just_after = datetime(2026, 10, 12, 0, 0, 1, tzinfo=ZoneInfoShim("America/New_York"))
        boundary = trade_eval_usage.week_start_utc(just_after, "America/New_York")
        self.assertEqual(boundary.isoformat(), "2026-10-12T04:00:00+00:00")

    def test_naive_datetime_is_treated_as_utc(self):
        naive = datetime(2026, 10, 14, 12, 0)
        aware = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(
            trade_eval_usage.week_start_utc(naive, "UTC"),
            trade_eval_usage.week_start_utc(aware, "UTC"),
        )

    def test_unknown_timezone_degrades_to_utc_instead_of_raising(self):
        now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        boundary = trade_eval_usage.week_start_utc(now, "Not/ARealZone")
        self.assertEqual(boundary, trade_eval_usage.week_start_utc(now, "UTC"))

    def test_different_timezones_can_disagree_on_which_week_it_is(self):
        # 2026-10-12 is a Monday. At 00:30 UTC, it is already Monday in
        # UTC/Europe but still Sunday night in America/Los_Angeles
        # (UTC-7), which must still report the *previous* week's boundary.
        now = datetime(2026, 10, 12, 0, 30, tzinfo=timezone.utc)
        utc_boundary = trade_eval_usage.week_start_utc(now, "UTC")
        la_boundary = trade_eval_usage.week_start_utc(now, "America/Los_Angeles")
        self.assertEqual(utc_boundary.isoformat(), "2026-10-12T00:00:00+00:00")
        self.assertEqual(la_boundary.isoformat(), "2026-10-05T07:00:00+00:00")


class TestEvalsUsedThisWeek(unittest.TestCase):
    def test_no_record_means_zero_used(self):
        self.assertEqual(trade_eval_usage.evals_used_this_week(None), 0)
        self.assertEqual(trade_eval_usage.evals_used_this_week({}), 0)

    def test_record_from_current_week_counts(self):
        now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        boundary = trade_eval_usage.week_start_utc(now, "UTC").isoformat()
        settings = {"settings": {trade_eval_usage.TRADE_EVAL_USAGE_SETTINGS_KEY: {
            "week_start": boundary, "count": 2,
        }}}
        self.assertEqual(
            trade_eval_usage.evals_used_this_week(settings, tz_name="UTC", now=now), 2
        )

    def test_record_from_prior_week_resets_to_zero(self):
        prior_now = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
        prior_boundary = trade_eval_usage.week_start_utc(prior_now, "UTC").isoformat()
        settings = {"settings": {trade_eval_usage.TRADE_EVAL_USAGE_SETTINGS_KEY: {
            "week_start": prior_boundary, "count": 3,
        }}}
        this_week_now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(
            trade_eval_usage.evals_used_this_week(settings, tz_name="UTC", now=this_week_now),
            0,
        )

    def test_crossing_the_monday_boundary_resets_even_a_few_seconds_later(self):
        settings_holder = {}

        sunday_late = datetime(2026, 10, 11, 23, 59, 59, tzinfo=timezone.utc)
        settings_holder["settings"] = trade_eval_usage.with_trade_eval_recorded(
            settings_holder, tz_name="UTC", now=sunday_late
        )["settings"]
        self.assertEqual(
            trade_eval_usage.evals_used_this_week(settings_holder, tz_name="UTC", now=sunday_late),
            1,
        )

        monday_early = datetime(2026, 10, 12, 0, 0, 1, tzinfo=timezone.utc)
        self.assertEqual(
            trade_eval_usage.evals_used_this_week(settings_holder, tz_name="UTC", now=monday_early),
            0,
        )


class TestRemainingAndRecording(unittest.TestCase):
    def test_free_tier_starts_with_full_weekly_allowance(self):
        self.assertEqual(
            trade_eval_usage.trade_evals_remaining_this_week("user-1", premium.FREE),
            trade_eval_usage.FREE_WEEKLY_TRADE_EVAL_LIMIT,
        )

    def test_pro_and_front_office_are_unlimited(self):
        self.assertIsNone(
            trade_eval_usage.trade_evals_remaining_this_week("user-1", premium.PRO)
        )
        self.assertIsNone(
            trade_eval_usage.trade_evals_remaining_this_week("user-1", premium.FRONT_OFFICE)
        )

    def test_remaining_decreases_as_recorded_and_floors_at_zero(self):
        now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        settings = None
        for expected_remaining_before in (3, 2, 1):
            self.assertEqual(
                trade_eval_usage.trade_evals_remaining_this_week(
                    "user-1", premium.FREE, user_settings=settings, tz_name="UTC", now=now
                ),
                expected_remaining_before,
            )
            settings = trade_eval_usage.with_trade_eval_recorded(settings, tz_name="UTC", now=now)

        self.assertEqual(
            trade_eval_usage.trade_evals_remaining_this_week(
                "user-1", premium.FREE, user_settings=settings, tz_name="UTC", now=now
            ),
            0,
        )
        # A 4th use still floors at zero rather than going negative.
        settings = trade_eval_usage.with_trade_eval_recorded(settings, tz_name="UTC", now=now)
        self.assertEqual(
            trade_eval_usage.trade_evals_remaining_this_week(
                "user-1", premium.FREE, user_settings=settings, tz_name="UTC", now=now
            ),
            0,
        )

    def test_with_trade_eval_recorded_preserves_unrelated_settings(self):
        existing = {"settings": {"theme_mode": "dark"}}
        updated = trade_eval_usage.with_trade_eval_recorded(existing, tz_name="UTC")
        self.assertEqual(updated["settings"]["theme_mode"], "dark")
        self.assertIn(trade_eval_usage.TRADE_EVAL_USAGE_SETTINGS_KEY, updated["settings"])

    def test_record_trade_eval_used_without_session_fails_closed(self):
        error = trade_eval_usage.record_trade_eval_used("user-1")
        self.assertEqual(error, "Authentication is required.")


if __name__ == "__main__":
    unittest.main()
