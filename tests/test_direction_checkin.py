"""modules.direction_checkin: when the Dashboard asks whether the team's
direction still fits. Pure decider, so every stage and edge is a plain call."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from modules import direction_checkin as dc

NOW = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)


def decide(week, *, stance="competing", handled=None, status="in_season", deadline=11, playoff_start=15, now=NOW, season=2026):
    return dc.decide(
        league_status=status, season=season, week=week, stance=stance, handled=handled, now=now,
        playoff_week_start=playoff_start, trade_deadline=deadline,
    )


def test_windows_for_a_standard_league_do_not_overlap_and_cover_four_moments():
    w = dc.windows(15, 11)
    assert w == {"season_start": (1, 2), "trade_deadline": (10, 11), "playoff_push": (12, 14), "midseason": (7, 8)}
    weeks = [x for first, last in w.values() for x in range(first, last + 1)]
    assert len(weeks) == len(set(weeks))


@pytest.mark.parametrize("deadline,expected", [
    (13, {"season_start": (1, 2), "trade_deadline": (12, 13), "playoff_push": (14, 14), "midseason": (7, 8)}),
    (14, {"season_start": (1, 2), "trade_deadline": (13, 14), "playoff_push": (12, 12), "midseason": (7, 8)}),
    (99, {"season_start": (1, 2), "playoff_push": (12, 14), "midseason": (7, 8)}),  # Sleeper's "no deadline"
    (None, {"season_start": (1, 2), "playoff_push": (12, 14), "midseason": (7, 8)}),
    (0, {"season_start": (1, 2), "playoff_push": (12, 14), "midseason": (7, 8)}),
])
def test_deadline_edges(deadline, expected):
    assert dc.windows(15, deadline) == expected


def test_shorter_and_unknown_playoff_start():
    assert dc.windows(None, None) == dc.windows(15, None)
    short = dc.windows(13, 9)  # 12 regular-season weeks
    assert short["playoff_push"] == (10, 12) and short["trade_deadline"] == (8, 9) and short["midseason"] == (6, 7)
    weeks = [x for first, last in short.values() for x in range(first, last + 1)]
    assert len(weeks) == len(set(weeks))


@pytest.mark.parametrize("week,moment", [
    (1, "season_start"), (2, "season_start"), (3, ""), (6, ""), (7, "midseason"), (8, "midseason"), (9, ""),
    (10, "trade_deadline"), (11, "trade_deadline"), (12, "playoff_push"), (14, "playoff_push"), (15, ""), (18, ""),
])
def test_moment_for_week(week, moment):
    assert dc.moment_for_week(week, 15, 11) == moment


def test_shows_at_a_moment_and_names_it():
    d = decide(8)
    assert d.show is True and d.moment == "midseason" and d.moment_key == "2026:midseason" and d.reason == ""


@pytest.mark.parametrize("kwargs,reason", [
    ({"status": "pre_draft", "week": 1}, "not_in_season"),
    ({"status": "drafting", "week": 1}, "not_in_season"),
    ({"status": "complete", "week": 8}, "not_in_season"),
    ({"week": None}, "not_in_season"),
    ({"week": 0}, "not_in_season"),
    ({"stance": ""}, "no_direction_set"),
    ({"stance": None}, "no_direction_set"),
    ({"week": 5}, "no_moment"),
    ({"week": 16}, "no_moment"),
])
def test_every_no_has_an_auditable_reason(kwargs, reason):
    args = {"week": 8, **kwargs}
    d = decide(**args)
    assert d.show is False and d.reason == reason


def test_post_season_status_counts_as_in_season_only_inside_a_window():
    assert decide(8, status="post_season").show is True
    assert decide(16, status="post_season").reason == "no_moment"


def test_an_answered_or_dismissed_moment_never_shows_again_that_season():
    for action in dc.ACTIONS:
        handled = {"2026:midseason": {"at": (NOW - timedelta(days=1)).isoformat(), "action": action}}
        d = decide(8, handled=handled)
        assert d.show is False and d.reason == "already_handled" and d.moment == "midseason"
    # ... but a new season starts clean.
    old = {"2025:midseason": {"at": (NOW - timedelta(days=300)).isoformat(), "action": "dismissed"}}
    assert decide(8, handled=old).show is True


def test_rate_limit_spans_moments_and_expires():
    recent = {"2026:season_start": {"at": (NOW - timedelta(days=dc.RATE_LIMIT_DAYS - 1)).isoformat(), "action": "kept"}}
    d = decide(8, handled=recent)
    assert d.show is False and d.reason == "rate_limited" and d.moment == "midseason"
    ok = {"2026:season_start": {"at": (NOW - timedelta(days=dc.RATE_LIMIT_DAYS)).isoformat(), "action": "kept"}}
    assert decide(8, handled=ok).show is True


def test_a_full_season_prompts_four_times_at_most_and_never_closer_than_the_rate_limit():
    """Walk a season week by week, dismissing each prompt the day it shows."""

    handled: dict = {}
    shown = []
    start = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    for week in range(1, 18):
        now = start + timedelta(weeks=week - 1)
        d = decide(week, handled=handled, now=now)
        if d.show:
            shown.append((week, d.moment))
            handled = dc.handled_for_league(dc.record_answer({"direction_checkin": {"L1": handled}}, "L1", d.moment_key, "dismissed", now), "L1")
    assert shown == [(1, "season_start"), (7, "midseason"), (10, "trade_deadline"), (12, "playoff_push")]
    weeks = [w for w, _ in shown]
    assert all((b - a) * 7 >= dc.RATE_LIMIT_DAYS for a, b in zip(weeks, weeks[1:]))
    # A league whose dismissals are recorded as they happen never asks twice in a window.
    assert not any(decide(w, handled=handled, now=start + timedelta(weeks=w - 1)).show for w in range(1, 18))


def test_unanswered_prompt_keeps_showing_only_inside_its_window():
    # Never answered: it stays up through the window (the card is dismissible), gone after it.
    assert decide(7).show is True and decide(8).show is True
    assert decide(9).show is False and decide(9).reason == "no_moment"


def test_bad_inputs_never_raise():
    assert decide("8").show is True
    assert decide(True).reason == "not_in_season"
    assert decide(8, handled="nope").show is True
    assert decide(8, handled={"2026:midseason": None, "x": 1}).show is False  # a record for this moment, however malformed


def test_copy_names_the_moment_and_direction():
    c = dc.copy_for("trade_deadline", "Rebuilding")
    assert c["headline"] == "Trade deadline: still Rebuilding?" and "Rebuilding" in c["body"]
    assert "shapes the trades" in c["body"] and c["keep_label"] == "Still fits" and c["dismiss_label"] == "Not now"
    assert "still your direction?" in dc.copy_for("midseason", "")["headline"]
    for moment in dc.MOMENTS:
        assert dc.copy_for(moment, "Balanced")["headline"].startswith(dc.MOMENT_LABELS[moment])


def test_record_answer_keeps_other_settings_and_trims():
    base = {"ui_density": "compact", "notification_prefs": {"weekly_cap": 2}}
    out = dc.record_answer(base, "L1", "2026:midseason", "kept", NOW)
    assert out["ui_density"] == "compact" and out["notification_prefs"] == {"weekly_cap": 2}
    assert dc.handled_for_league(out, "L1") == {"2026:midseason": {"at": NOW.isoformat(), "action": "kept"}}
    assert dc.handled_for_league(out, "L2") == {}
    assert "direction_checkin" not in base  # the input is never mutated
    # Bounded: the newest records survive.
    settings: dict = {}
    for i in range(30):
        settings = dc.record_answer(settings, "L1", f"{2000 + i}:midseason", "kept", NOW + timedelta(days=i))
    kept = dc.handled_for_league(settings, "L1")
    assert len(kept) == dc.MAX_RECORDS_PER_LEAGUE and "2029:midseason" in kept and "2000:midseason" not in kept
    many: dict = {}
    for i in range(dc.MAX_LEAGUES + 5):
        many = dc.record_answer(many, f"L{i}", "2026:midseason", "kept", NOW + timedelta(minutes=i))
    assert len(many["direction_checkin"]) == dc.MAX_LEAGUES and "L0" not in many["direction_checkin"]


def test_handled_for_league_drops_malformed_records():
    settings = {"direction_checkin": {"L1": {
        "2026:midseason": {"at": NOW.isoformat(), "action": "kept"},
        "garbage": {"at": NOW.isoformat(), "action": "kept"},
        "2026:playoff_push": {"at": "not a date", "action": "kept"},
        "2026:trade_deadline": {"at": NOW.isoformat(), "action": "weird"},
        "2026:season_start": "nope",
    }}}
    got = dc.handled_for_league(settings, "L1")
    assert set(got) == {"2026:midseason", "2026:trade_deadline"} and got["2026:trade_deadline"]["action"] == "dismissed"
    assert dc.handled_for_league(None, "L1") == {} and dc.handled_for_league({"direction_checkin": []}, "L1") == {}


@pytest.mark.parametrize("action,key,ok", [
    ("kept", "2026:midseason", True), ("changed", "2026:playoff_push", True), ("dismissed", "2026:season_start", True),
    ("later", "2026:midseason", False), ("kept", "midseason", False), ("kept", "2026:nope", False), ("kept", "", False),
    (None, "2026:midseason", False),
])
def test_validate_action(action, key, ok):
    assert (dc.validate_action(action, key) == "") is ok
