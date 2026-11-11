"""Pure decider + prefs logic (modules.notification_decider / notification_prefs)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from modules import notification_decider as nd
from modules import notification_prefs as np_

NOW = datetime(2026, 10, 21, 17, 0, tzinfo=timezone.utc)


def _item(category="watch", league="L1", rid=None, **extra):
    return {"category": category, "league_id": league, "recommendation_id": rid or f"{category}:{league}", **extra}


def _decide(items, *, prefs=None, hour=12, sent=0, cap=4, rosters=None, now=NOW):
    return nd.decide(
        items,
        prefs={**np_.default_prefs(), **(prefs or {})},
        now=now,
        local_hour=hour,
        sent_this_week_fn=lambda: sent,
        default_cap=cap,
        roster_ids_by_league=rosters,
    )


def test_default_prefs_reproduce_legacy_quiet_hours_and_cap():
    assert _decide([_item()], hour=12).allowed
    for hour in (22, 23, 0, 7):
        assert _decide([_item()], hour=hour).held == "quiet_hours"
    assert _decide([_item()], hour=8).allowed
    # cap: last slot reserved for critical categories
    assert _decide([_item("watch"), _item("injury", rid="i")], sent=3).allowed == [_item("injury", rid="i")]
    assert _decide([_item("injury", rid="i")], sent=4).held == "capped"


def test_user_quiet_window_wraps_and_can_be_disabled():
    prefs = {"quiet_start": 23, "quiet_end": 6}
    assert _decide([_item()], prefs=prefs, hour=22).allowed
    assert _decide([_item()], prefs=prefs, hour=2).held == "quiet_hours"
    assert _decide([_item()], prefs={"quiet_hours_enabled": False}, hour=3).allowed
    # daytime window (no wrap)
    assert _decide([_item()], prefs={"quiet_start": 9, "quiet_end": 17}, hour=10).held == "quiet_hours"


def test_critical_may_break_quiet_hours_only_when_opted_in():
    items = [_item("watch"), _item("lineup_lock", rid="ll")]
    assert _decide(items, hour=3).held == "quiet_hours"
    decision = _decide(items, prefs={"critical_breaks_quiet": True}, hour=3)
    assert [i["category"] for i in decision.allowed] == ["lineup_lock"]


def test_per_league_mute_and_critical_only():
    items = [_item("watch", "L1"), _item("injury", "L1", rid="i1", player_id="p"), _item("watch", "L2")]
    rosters = {"L1": {"p"}, "L2": set()}
    muted = _decide(items, prefs={"league_overrides": {"L1": "mute"}}, rosters=rosters)
    assert [i["league_id"] for i in muted.allowed] == ["L2"]
    assert {r for _i, r in muted.suppressed} == {"league_muted"}
    critical = _decide(items, prefs={"league_overrides": {"L1": "critical"}}, rosters=rosters)
    assert [(i["category"], i["league_id"]) for i in critical.allowed] == [("injury", "L1"), ("watch", "L2")]
    assert ("league_critical_only") in {r for _i, r in critical.suppressed}


def test_digest_holds_until_window_but_never_for_critical():
    prefs = {"category_modes": {"watch": "digest", "injury": "digest"}, "digest_hour": 8}
    watch = _item("watch")
    assert _decide([watch], prefs=prefs, hour=12).held == "digest"
    assert _decide([watch], prefs=prefs, hour=9).allowed == [watch]
    # injury is critical: digest mode is ignored for it
    assert _decide([_item("injury", rid="i", player_id="p")], prefs=prefs, hour=12, rosters={"L1": {"p"}}).allowed


def test_stale_items_are_dropped_not_sent():
    live = _item("lineup_lock", rid="a", expires_at=(NOW + timedelta(minutes=30)).isoformat())
    dead = _item("lineup_lock", rid="b", expires_at=(NOW - timedelta(minutes=1)).isoformat())
    decision = _decide([live, dead])
    assert decision.allowed == [live]
    assert decision.suppressed == [(dead, "stale")]
    assert _decide([dead]).held == "nothing_left"


def test_injury_for_a_player_not_on_your_roster_is_irrelevant():
    mine = _item("injury", rid="m", player_id="p1")
    other = _item("injury", rid="o", player_id="p2")
    decision = _decide([mine, other], rosters={"L1": {"p1"}})
    assert decision.allowed == [mine]
    assert decision.suppressed == [(other, "not_on_roster")]
    # Unknown roster (fetch failed): do not guess, keep prior behavior.
    assert len(_decide([mine, other], rosters={}).allowed) == 2


def test_unreadable_push_count_holds_everything():
    decision = nd.decide(
        [_item()], prefs=np_.default_prefs(), now=NOW, local_hour=12, sent_this_week_fn=lambda: None, default_cap=4
    )
    assert decision.held == "count_unavailable" and not decision.allowed


def test_user_weekly_cap_overrides_default():
    assert _decide([_item()], prefs={"weekly_cap": 2}, sent=2).held == "capped"
    assert _decide([_item()], prefs={"weekly_cap": 7}, sent=5).allowed


def test_deep_links_point_at_the_exact_screen():
    assert nd.deep_link_for(_item("lineup_lock", "L 1")) == "/matchup/L%201"
    assert nd.deep_link_for(_item("trade_deadline")) == "/trade-hub/L1"
    assert nd.deep_link_for(_item("waiver_reminder")) == "/waivers/L1"
    assert nd.deep_link_for(_item("weekly_roundup", week=9)) == "/league-recaps/L1?tab=roundup&week=9"
    assert nd.deep_link_for(_item("injury", player_id="42")) == "/players/L1/42"
    assert nd.deep_link_for(_item("top_priority")) == "/dashboard/L1"
    assert nd.deep_link_for({"category": "trade_followup"}) == "/alerts"
    assert nd.deep_link_for({"category": "watch"}) == ""


# --- prefs ---------------------------------------------------------------


def test_normalize_prefs_is_lenient_about_garbage():
    prefs = np_.normalize_prefs(
        {
            "quiet_start": "x",
            "quiet_end": 99,
            "weekly_cap": 500,
            "timezone": "Not/AZone",
            "league_overrides": {"L1": "mute", "L2": "bogus", "L3": "all"},
            "category_modes": {"watch": "digest", "injury": "digest", "nope": "digest"},
        },
        valid_categories=("watch", "injury"),
    )
    assert (prefs["quiet_start"], prefs["quiet_end"]) == (22, 8)
    assert prefs["weekly_cap"] is None and prefs["timezone"] == ""
    assert prefs["league_overrides"] == {"L1": "mute"}
    assert prefs["category_modes"] == {"watch": "digest"}  # critical + unknown dropped
    assert np_.normalize_prefs(None) == np_.default_prefs()


def test_apply_patch_merges_per_key():
    current = np_.normalize_prefs({"league_overrides": {"L1": "mute", "L2": "critical"}})
    merged = np_.apply_patch(current, {"league_overrides": {"L1": "all", "L3": "mute"}, "weekly_cap": 2})
    assert merged["league_overrides"] == {"L2": "critical", "L3": "mute"}
    assert merged["weekly_cap"] == 2
    assert np_.apply_patch(merged, {"weekly_cap": None})["weekly_cap"] is None


def test_validate_patch_is_strict():
    cats = ("watch", "injury")
    ok = np_.validate_patch
    assert ok({"quiet_start": 22, "quiet_end": 7, "weekly_cap": 3}, valid_categories=cats) == ""
    assert ok({"quiet_start": 25}, valid_categories=cats)
    assert ok({"quiet_start": 5, "quiet_end": 5}, valid_categories=cats)
    assert ok({"weekly_cap": 99}, valid_categories=cats)
    assert ok({"timezone": "Mars/Base"}, valid_categories=cats)
    assert ok({"league_overrides": {"L1": "loud"}}, valid_categories=cats)
    assert ok({"category_modes": {"injury": "digest"}}, valid_categories=cats)
    assert ok({"category_modes": {"bogus": "digest"}}, valid_categories=cats)
    assert ok({"quiet_hours_enabled": "yes"}, valid_categories=cats)
