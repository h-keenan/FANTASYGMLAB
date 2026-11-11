"""Sweep-level tests for the decider/events/scale additions to
modules.push_triggers. (tests/test_push_triggers.py is the unchanged
regression suite proving existing categories behave identically.)

Supabase + Expo are mocked by URL at the requests boundary; no real push is
ever sent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from modules import notification_events, push_tokens, push_triggers

ENV = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
NOON_NY = datetime(2026, 10, 21, 17, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _base(monkeypatch):
    notification_events.reset_for_tests()
    monkeypatch.setattr(push_triggers, "fetch_push_timezones", lambda config: {})
    monkeypatch.setattr(push_triggers, "count_recent_pushes", lambda config, user_id, now=None: 0)
    monkeypatch.setattr(push_triggers, "_utcnow", lambda: NOON_NY)
    from modules import trade_hub_engine

    monkeypatch.setattr(trade_hub_engine, "roster_posture", lambda **kw: {"key": "retool"})
    yield
    notification_events.reset_for_tests()


def _run(*, users=("u1",), settings_rows=None, env=None, expo=None, events_response=None, leagues=("league-1",), roster_players=("p1", "p2")):
    """Run one sweep with every user rostering `roster_players` in each league.
    Returns (stats, posts, counters)."""

    players_df = pd.DataFrame(
        [
            {"player_id": "p1", "name": "Hurt Guy", "position": "RB", "dynasty_score": 50, "injury_status": "Out"},
            {"player_id": "p3", "name": "Not Mine", "position": "WR", "dynasty_score": 40, "injury_status": "IR"},
        ]
    )
    tables = {
        "push_tokens": [{"user_id": u, "expo_push_token": f"ExponentPushToken[{u}]"} for u in users],
        "profiles": [{"user_id": u, "sleeper_username": f"gm_{u}"} for u in users],
        "user_settings": settings_rows or [],
        "gm_targets": [],
        "team_stance": [{"user_id": u, "league_id": lg} for u in users for lg in leagues],
        "push_notification_log": [],
    }

    def fake_get(url, **kwargs):
        table = url.rsplit("/", 1)[-1]
        return Mock(status_code=200, json=lambda: tables.get(table, []))

    posts: list[tuple[str, object]] = []

    def fake_post(url, **kwargs):
        posts.append((url, kwargs.get("json")))
        if url == push_tokens.EXPO_PUSH_API_URL:
            return expo or Mock(status_code=200, json=lambda: {"data": [{"status": "ok", "id": "tk"} for _ in kwargs["json"]]})
        if url.endswith("/notification_events") and events_response is not None:
            return events_response
        return Mock(status_code=201)

    counters = {"get_league": 0, "get_rosters": 0}

    def get_league(league_id):
        counters["get_league"] += 1
        return {"name": "Secret"}

    def get_rosters(league_id):
        counters["get_rosters"] += 1
        return [{"roster_id": 1, "owner_id": "su", "players": list(roster_players)}]

    with patch("modules.push_triggers.load_valued_players", return_value=(players_df, "dynasty_score")), patch(
        "modules.sleeper_leagues.resolve_sleeper_user_id", return_value="su"
    ), patch(
        "modules.sleeper_leagues.get_user_leagues", return_value=[{"league_id": lg} for lg in leagues]
    ), patch("modules.sleeper.get_league", side_effect=get_league), patch(
        "modules.sleeper.get_rosters", side_effect=get_rosters
    ), patch("modules.dashboard_engine.compose_next_move_briefing", return_value=Mock(items=[])), patch(
        "modules.push_triggers.recap_push_item", return_value=None
    ), patch("requests.get", side_effect=fake_get), patch("requests.post", side_effect=fake_post), patch(
        "requests.delete"
    ):
        stats = push_triggers.run_push_trigger_sweep(environ={**ENV, **(env or {})})
    return stats, posts, counters


def _settings(user, prefs=None, categories=None):
    settings = {}
    if prefs is not None:
        settings["notification_prefs"] = prefs
    if categories is not None:
        settings["push_categories"] = categories
    return {"user_id": user, "settings": settings}


def _expo_posts(posts):
    return [p for p in posts if p[0] == push_tokens.EXPO_PUSH_API_URL]


# --- decider wired into the sweep -----------------------------------------


def test_injury_for_player_not_on_my_roster_is_not_pushed():
    # "p3" is IR in the player table but not on this user's roster: only p1 pushes.
    stats, posts, _ = _run()
    msg = _expo_posts(posts)[0][1][0]
    assert msg["body"] == "Hurt Guy is now Out"
    assert msg["data"]["url"] == "/players/league-1/p1"
    assert msg["data"]["notification_id"]


def test_per_league_mute_skips_league_entirely():
    rows = [_settings("u1", prefs={"league_overrides": {"league-1": "mute"}})]
    stats, posts, counters = _run(settings_rows=rows)
    assert stats["pushes_sent"] == 0 and not _expo_posts(posts)
    assert counters["get_rosters"] == 0  # no detector work for a muted league


def test_user_quiet_hours_and_timezone_are_honored(monkeypatch):
    # 13:00 NY (EDT) is 10:00 in LA; a user quiet window 9-11 local holds it.
    rows = [_settings("u1", prefs={"timezone": "America/Los_Angeles", "quiet_start": 9, "quiet_end": 11})]
    stats, posts, _ = _run(settings_rows=rows)
    assert stats["held_quiet_hours"] == 1 and not _expo_posts(posts)
    # ... and quiet hours off sends at once.
    stats, posts, _ = _run(settings_rows=[_settings("u1", prefs={"quiet_hours_enabled": False})])
    assert stats["pushes_sent"] == 1


def test_user_weekly_cap_is_honored(monkeypatch):
    monkeypatch.setattr(push_triggers, "count_recent_pushes", lambda config, user_id, now=None: 2)
    stats, posts, _ = _run(settings_rows=[_settings("u1", prefs={"weekly_cap": 2})])
    assert stats["capped"] == 1 and not posts


def test_legacy_category_toggle_still_wins():
    rows = [_settings("u1", categories={"injury": False})]
    stats, posts, _ = _run(settings_rows=rows)
    assert stats["pushes_sent"] == 0 and not _expo_posts(posts)


def test_malformed_prefs_blob_falls_back_to_defaults():
    rows = [_settings("u1", prefs={"quiet_start": "banana", "league_overrides": "nope", "weekly_cap": -3})]
    stats, _posts, _ = _run(settings_rows=rows)
    assert stats["pushes_sent"] == 1


# --- delivery honesty ------------------------------------------------------


def test_push_where_every_device_rejects_is_not_logged_as_delivered():
    expo = Mock(
        status_code=200,
        json=lambda: {"data": [{"status": "error", "details": {"error": "DeviceNotRegistered"}}]},
    )
    stats, posts, _ = _run(expo=expo)
    assert stats["pushes_sent"] == 0
    assert stats["errors"]
    assert not [p for p in posts if "push_notification_log" in p[0]]  # retried next sweep, not swallowed


# --- events (opt-in) --------------------------------------------------------


def test_events_are_off_by_default_and_written_when_enabled():
    _stats, posts, _ = _run()
    assert not [p for p in posts if "notification_events" in p[0]]

    stats, posts, _ = _run(env={"NOTIFICATION_EVENTS": "1"})
    events = [p for p in posts if p[0].endswith("/notification_events")]
    assert len(events) == 1
    row = events[0][1][0]
    assert row["state"] == "sent" and row["dedupe_key"] == "injury:p1:out"
    assert row["tickets"] == [{"token": "ExponentPushToken[u1]", "id": "tk"}]
    notification_id = _expo_posts(posts)[0][1][0]["data"]["notification_id"]
    assert row["batch_id"] == notification_id


def test_failed_send_is_recorded_as_failed_event():
    stats, posts, _ = _run(env={"NOTIFICATION_EVENTS": "1"}, expo=Mock(status_code=500))
    events = [p for p in posts if p[0].endswith("/notification_events")]
    assert events and events[0][1][0]["state"] == "failed"


def test_missing_events_table_never_breaks_the_sweep():
    missing = Mock(status_code=404, text="relation does not exist")
    stats, posts, _ = _run(env={"NOTIFICATION_EVENTS": "1"}, events_response=missing)
    assert stats["pushes_sent"] == 1 and not stats["errors"]
    assert [p for p in posts if "push_notification_log" in p[0]]  # legacy dedupe log still written
    assert not notification_events.events_enabled(environ={"NOTIFICATION_EVENTS": "1"})


# --- scale ------------------------------------------------------------------


def test_league_payload_and_rosters_are_fetched_once_per_league_per_run():
    stats, _posts, counters = _run(users=("u1", "u2", "u3"))
    assert stats["pushes_sent"] == 3
    assert counters == {"get_league": 1, "get_rosters": 1}


def test_sharding_partitions_users_stably():
    users = tuple(f"user-{i}" for i in range(12))
    seen: set[str] = set()
    for index in range(3):
        stats, _posts, _ = _run(users=users, env={"PUSH_SWEEP_SHARDS": "3", "PUSH_SWEEP_SHARD_INDEX": str(index)})
        assert stats["shard"] == f"{index}/3"
        shard_users = {u for u in users if push_triggers.user_shard(u, 3) == index}
        assert stats["accounts_checked"] == len(shard_users)
        assert not (shard_users & seen)
        seen |= shard_users
    assert seen == set(users)


def test_invalid_shard_config_falls_back_to_single_worker():
    assert push_triggers.load_sweep_shard(environ={"PUSH_SWEEP_SHARDS": "3", "PUSH_SWEEP_SHARD_INDEX": "3"}) == (1, 0)
    assert push_triggers.load_sweep_shard(environ={"PUSH_SWEEP_SHARDS": "x"}) == (1, 0)


def test_time_budget_stops_the_run_and_reports_skipped_users(monkeypatch):
    clock = iter([0.0, 0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0])
    monkeypatch.setattr(push_triggers.time, "monotonic", lambda: next(clock))
    stats, _posts, _ = _run(users=("u1", "u2", "u3"), env={"PUSH_SWEEP_TIME_BUDGET_SECONDS": "150"})
    assert stats["accounts_checked"] == 2
    assert stats["skipped_budget"] == 1


def test_user_order_rotates_each_slot_so_nobody_is_starved():
    users = [f"u{i}" for i in range(30)]
    first = push_triggers.sweep_user_order(users, NOON_NY)
    later = push_triggers.sweep_user_order(users, datetime(2026, 10, 21, 17, 30, tzinfo=timezone.utc))
    assert sorted(first) == sorted(later) == sorted(users)
    assert first != later


def test_receipt_poll_is_a_noop_without_the_flag():
    assert push_triggers.run_receipt_poll(environ=ENV) == {"enabled": False}
