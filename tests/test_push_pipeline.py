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
    # Team-profile prefetch is exercised by its own tests; the rest of the sweep
    # tests stay off the (heavy) real profile build.
    monkeypatch.setenv("DYNASTYGM_PARTNER_CONTEXT_DASHBOARD_V1", "0")
    monkeypatch.setattr(push_triggers, "fetch_push_timezones", lambda config: {})
    monkeypatch.setattr(push_triggers, "count_recent_pushes", lambda config, user_id, now=None: 0)
    monkeypatch.setattr(push_triggers, "count_pushes_today", lambda config, user_id, now=None: 0)
    monkeypatch.setattr(push_triggers, "_utcnow", lambda: NOON_NY)
    from modules import trade_hub_engine

    monkeypatch.setattr(trade_hub_engine, "roster_posture", lambda **kw: {"key": "retool"})
    yield
    notification_events.reset_for_tests()


def _run(*, users=("u1",), log_rows=None, settings_rows=None, env=None, expo=None, events_response=None, leagues=("league-1",), roster_players=("p1", "p2")):
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
        "push_notification_log": list(log_rows or []),
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


def test_team_profiles_are_prefetched_once_per_league_per_run_without_extra_sleeper_reads(monkeypatch):
    from modules import team_profile

    built, seen = [], []

    def fake_profiles(*, league_id, lens, players_db_path):
        from modules import sleeper

        # The build must read the league from the sweep's snapshot, not Sleeper.
        sleeper.get_league(league_id)
        sleeper.get_rosters(league_id)
        built.append((league_id, lens))
        return {"teams": {"1": {}}}

    monkeypatch.setattr(team_profile, "league_team_profiles_cached", fake_profiles)
    monkeypatch.setenv("DYNASTYGM_PARTNER_CONTEXT_DASHBOARD_V1", "1")
    original = push_triggers.league_briefing_push_items

    def spy(**kwargs):
        seen.append(kwargs.get("team_profiles"))
        return original(**kwargs)

    monkeypatch.setattr(push_triggers, "league_briefing_push_items", spy)
    stats, _posts, counters = _run(users=("u1", "u2", "u3"))
    assert len(built) == 1
    assert seen == [{"teams": {"1": {}}}] * 3
    assert counters == {"get_league": 1, "get_rosters": 1}
    assert not stats["errors"]


def test_team_profiles_prefetch_respects_the_dashboard_flag(monkeypatch):
    from modules import partner_context, team_profile

    def boom(**kw):
        raise AssertionError("flag off must not build")

    monkeypatch.setattr(team_profile, "league_team_profiles_cached", boom)
    monkeypatch.setenv(partner_context.DASHBOARD_ENV_KEY, "0")
    stats, _posts, counters = _run(users=("u1", "u2"))
    assert counters == {"get_league": 1, "get_rosters": 1} and not stats["errors"]


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


# --- dedupe, daily cap, quiet hours (notifications audit 2026-11) -----------


def test_already_logged_injury_is_never_pushed_again():
    log = [{"user_id": "u1", "recommendation_id": "injury:p1:out", "league_id": "league-1"}]
    stats, posts, _ = _run(log_rows=log)
    assert stats["pushes_sent"] == 0 and not _expo_posts(posts)


def test_same_player_in_two_leagues_is_one_item_not_a_plus_one_more():
    stats, posts, _ = _run(leagues=("league-1", "league-2"))
    sent = _expo_posts(posts)
    assert len(sent) == 1
    msg = sent[0][1][0]
    assert msg["body"] == "Hurt Guy is now Out"
    assert "more update" not in msg["body"]
    log_posts = [p for p in posts if p[0].endswith("/push_notification_log")]
    ids = [row["recommendation_id"] for _url, rows in log_posts for row in rows]
    assert len(ids) == len(set(ids))


def test_second_sweep_after_a_logged_push_sends_nothing():
    stats, posts, _ = _run()
    logged = [p for p in posts if p[0].endswith("/push_notification_log")]
    rows = [row for _url, batch in logged for row in batch]
    assert rows and stats["pushes_sent"] == 1
    stats2, posts2, _ = _run(log_rows=rows)
    assert stats2["pushes_sent"] == 0 and not _expo_posts(posts2)


def test_daily_cap_blocks_noncritical_but_keeps_one_critical_slot(monkeypatch):
    # Default daily cap is 2: the last slot is reserved for critical categories.
    monkeypatch.setattr(push_triggers, "count_pushes_today", lambda config, user_id, now=None: 1)
    stats, posts, _ = _run()  # injury is critical: uses the reserved slot
    assert stats["pushes_sent"] == 1
    monkeypatch.setattr(push_triggers, "count_pushes_today", lambda config, user_id, now=None: 2)
    stats, posts, _ = _run()
    assert stats["pushes_sent"] == 0 and stats["capped"] == 1


def test_unreadable_daily_count_holds_the_push(monkeypatch):
    monkeypatch.setattr(push_triggers, "count_pushes_today", lambda config, user_id, now=None: None)
    stats, posts, _ = _run()
    assert stats["pushes_sent"] == 0 and not _expo_posts(posts)


@pytest.mark.parametrize(
    "zone",
    ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "Pacific/Honolulu", "Europe/London"],
)
def test_no_push_is_ever_allowed_inside_a_users_local_quiet_window(zone):
    """Every UTC hour of a DST and a non-DST day, per zone: if the decider allows
    a push, the user's local hour is outside 22:00-08:00."""

    from datetime import timedelta
    from zoneinfo import ZoneInfo

    from modules import notification_decider as nd
    from modules import notification_prefs as np_

    item = {"category": "watch", "league_id": "L", "recommendation_id": "w"}
    for day in (datetime(2026, 7, 15, tzinfo=timezone.utc), datetime(2026, 12, 15, tzinfo=timezone.utc)):
        for hour in range(24):
            now = day + timedelta(hours=hour)
            local_hour = push_triggers._local_hour(zone, now)
            assert local_hour == now.astimezone(ZoneInfo(zone)).hour
            decision = nd.decide(
                [item], prefs=np_.default_prefs(), now=now, local_hour=local_hour,
                sent_this_week_fn=lambda: 0, default_cap=4,
            )
            if local_hour >= 22 or local_hour < 8:
                assert not decision.allowed and decision.held == "quiet_hours"
            else:
                assert decision.allowed


def test_unknown_timezone_is_read_conservatively():
    """No device timezone on file: the sweep reads US Eastern, so the morning
    end of quiet hours is widened to keep a Pacific user's 5am out."""

    from modules import notification_decider as nd
    from modules import notification_prefs as np_

    item = {"category": "watch", "league_id": "L", "recommendation_id": "w"}

    def run(hour, tz_known):
        return nd.decide(
            [item], prefs=np_.default_prefs(), now=NOON_NY, local_hour=hour,
            sent_this_week_fn=lambda: 0, default_cap=4, tz_known=tz_known,
        )

    assert run(9, True).allowed
    assert run(9, False).held == "quiet_hours"  # 9am ET is 6am PT
    assert run(10, False).held == "quiet_hours"
    assert run(11, False).allowed


def test_push_copy_has_no_em_dashes():
    stats, posts, _ = _run()
    for _url, body in _expo_posts(posts):
        for msg in body:
            text = msg["title"] + msg["body"]
            assert "—" not in text and "–" not in text
    item = push_triggers.gm_stance_reminder_push_item(league_id="L", league_name="n", leagues_with_stance=set())
    assert item and "—" not in item["headline"]


def _briefing_items(league):
    waiver = Mock(category="top_priority", headline="Add a free agent", recommendation_id="w1",
                  route_player_id="", route_player_name="", destination="waivers")
    trade = Mock(category="watch", headline="A trade idea is ready", recommendation_id="t1",
                 route_player_id="", route_player_name="", destination="trade_hub")
    players_df = pd.DataFrame([{"player_id": "p1", "position": "RB", "dynasty_score": 50}])
    with patch("modules.sleeper.get_rosters", return_value=[{"roster_id": 1, "owner_id": "su", "players": ["p1"]}]), patch(
        "modules.dashboard_engine.compose_next_move_briefing", return_value=Mock(items=[waiver, trade])
    ):
        return push_triggers.league_briefing_push_items(
            league_id="L", sleeper_user_id="su", players_df=players_df, score_field="dynasty_score", league=league
        )


def test_offseason_waiver_add_is_not_pushed_but_in_season_is():
    assert [i["recommendation_id"] for i in _briefing_items({"name": "X", "status": "complete"})] == ["t1"]
    assert [i["recommendation_id"] for i in _briefing_items({"name": "X", "status": "in_season"})] == ["w1", "t1"]


def test_sweep_script_exits_nonzero_when_it_failed_closed(monkeypatch):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "run_push_trigger_sweep", Path(__file__).resolve().parents[1] / "scripts" / "run_push_trigger_sweep.py"
    )
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    monkeypatch.setattr(push_triggers, "run_trade_outcome_followup_sweep", lambda **kw: {})
    monkeypatch.setattr(push_triggers, "run_receipt_poll", lambda **kw: {})
    monkeypatch.setattr(push_triggers, "run_push_trigger_sweep", lambda **kw: {"configured": True, "ok": False})
    assert script.main() == 1
    monkeypatch.setattr(push_triggers, "run_push_trigger_sweep", lambda **kw: {"configured": True, "ok": True})
    assert script.main() == 0
