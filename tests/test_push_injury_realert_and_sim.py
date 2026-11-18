"""Injury re-alerts (hurt -> healthy -> hurt again) and the opt-in Fantasy Sim week-ready push."""

from datetime import datetime, timedelta, timezone

from modules import notification_decider as nd
from modules import push_triggers as pt

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def _row(rid, days_ago):
    return {"recommendation_id": rid, "sent_at": (NOW - timedelta(days=days_ago)).isoformat()}


def _resets(injury, markers, healthy, unavailable):
    return pt.injury_realert_resets(
        injury_rows=injury, marker_rows=markers, healthy_ids=healthy, unavailable_ids=unavailable, now=NOW
    )


def test_first_healthy_sighting_creates_marker_only():
    assert _resets([_row("injury:p1:out", 10)], [], {"p1"}, set()) == (["injury_clear:p1"], [], [])


def test_realert_needs_healthy_period_and_min_gap():
    inj = [_row("injury:p1:out", 10)]
    assert _resets(inj, [_row("injury_clear:p1", 1)], {"p1"}, set()) == ([], [], [])
    create, delete, reset = _resets(inj, [_row("injury_clear:p1", 4)], {"p1"}, set())
    assert reset == ["p1"] and "injury:p1:out" in delete and "injury_clear:p1" in delete
    # Last injury push only 5 days ago: below the 7 day minimum gap.
    assert _resets([_row("injury:p1:out", 5)], [_row("injury_clear:p1", 4)], {"p1"}, set())[2] == []


def test_flicker_drops_marker_and_never_resets():
    res = _resets([_row("injury:p1:out", 20)], [_row("injury_clear:p1", 9)], set(), {"p1"})
    assert res == ([], ["injury_clear:p1"], [])


def test_sim_week_ready_is_opt_in_and_off_by_default():
    assert pt.push_item_allowed({}, user_id="u", category="sim_week_ready") is False
    assert pt.push_item_allowed({"u": {}}, user_id="u", category="sim_week_ready") is False
    assert pt.push_item_allowed({"u": {"sim_week_ready": True}}, user_id="u", category="sim_week_ready") is True
    assert pt.push_item_allowed({}, user_id="u", category="injury") is True


def _game(hours, **extra):
    return {"id": "g1", "status": "in_season", "current_week": 4, "updated_at": (NOW - timedelta(hours=hours)).isoformat(), **extra}


def test_sim_week_ready_waits_then_stops_nagging():
    assert pt.sim_week_ready_push_item([_game(2)], now=NOW) is None
    item = pt.sim_week_ready_push_item([_game(30)], now=NOW)
    assert item["recommendation_id"] == "sim_week_ready:g1:4" and item["category"] == "sim_week_ready"
    assert pt.sim_week_ready_push_item([_game(24 * 9)], now=NOW) is None
    assert pt.sim_week_ready_push_item([_game(30, status="complete")], now=NOW) is None


def test_sim_week_ready_deep_link_and_title():
    assert nd.deep_link_for({"category": "sim_week_ready"}) == "/gm-game"
    assert pt.PUSH_TITLE_BY_CATEGORY["sim_week_ready"] == "Fantasy Sim"
