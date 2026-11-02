"""The one injury table (modules.injury_status): every consumer derives from it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules import injury_status as table
from modules import injury_tone, player_availability, player_projections, rankings, trade_grade

ROOT = Path(__file__).resolve().parents[1]


def _sleeper_values(field: str) -> set[str]:
    path = ROOT / "data" / "sleeper_players.json"
    if not path.exists():
        pytest.skip("data/sleeper_players.json not present")
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows = rows.values() if isinstance(rows, dict) else rows
    return {str(r.get(field)) for r in rows if r.get(field)}


def test_every_real_sleeper_injury_tag_maps_to_exactly_one_known_row():
    for tag in _sleeper_values("injury_status"):
        cls = table.classify("Active", tag)
        assert cls.known, tag
        matches = [r for r in table.ROWS if r.category != "healthy" and (tag.lower() in r.aliases or any(
            tag.lower() == t for t in r.terms))]
        assert len(matches) <= 1, (tag, [r.key for r in matches])


def test_every_real_sleeper_roster_status_is_classified_without_guessing():
    for status in _sleeper_values("status"):
        cls = table.classify(status, "")
        assert cls.known, status
        if status.lower() in {"injured reserve", "physically unable to perform", "non football injury"}:
            assert cls.ruled_out and cls.category == "major", status


def test_availability_numbers_are_one_fact_not_two():
    for row in table.ROWS:
        if row.kind == "game_time":
            assert row.weeks_out == pytest.approx(1 - row.p_play, abs=0.005), row.key
        if row.ruled_out:
            assert row.p_play == 0.0, row.key
        assert 0.0 <= row.p_play <= 1.0


def test_projections_and_trade_grade_read_the_table_not_their_own_numbers():
    q = table.ROWS_BY_KEY["questionable"]
    out = player_projections._availability_adjustment({"status": "Active", "injury_status": "Questionable"}, 0)
    assert out["multiplier"] == q.p_play
    absence = trade_grade.estimate_injury_absence("Active", "Questionable")
    assert absence.weeks == q.weeks_out
    # The same designation costs one thing in both models.
    assert absence.weeks == pytest.approx(1 - out["multiplier"], abs=0.005)
    reserve = trade_grade.estimate_injury_absence("Injured Reserve", "IR")
    assert reserve.weeks == table.ROWS_BY_KEY["ir"].weeks_out == table.RESERVE_MIN_GAMES_OUT


def test_classification_is_whole_word_not_substring():
    # The old injury_level substring-matched "ir" and "out" inside other words.
    for text in ("Their", "Outside", "Fire", "Hospital"):
        cls = table.classify("Active", text)
        assert cls.row.key == "unknown" and not cls.known, text
        assert table.is_ruled_out("Active", text) is False
    assert table.classify("Active", "Out for season").row.key == "season_ending"
    assert table.is_ruled_out("Active", "Out") and not table.is_ruled_out("Active", "Doubtful")
    assert table.classify("Injured Reserve", "").ruled_out
    assert table.classify("Active", "Sus").suspended and table.classify("Active", "Sus").category == "major"
    assert table.category("Active", "NA") == "healthy" and table.category("Active", "") == "healthy"
    assert table.classify("", "Q").row.key == "questionable"  # whole-field abbreviation


def test_dnr_and_cov_are_out_everywhere():
    for tag in ("DNR", "COV"):
        assert table.is_ruled_out("Active", tag)
        assert rankings.is_ruled_out("Active", tag)
        assert player_availability.build_availability(tag)["unavailable"] is True
        assert rankings.injury_level("Active", tag) == "moderate"


def test_rankings_wrappers_delegate_to_the_table():
    for status, tag in [("Active", "Out"), ("Active", "IR"), ("Active", "Doubtful"), ("Active", "Questionable"),
                        ("Inactive", ""), ("Active", "Sus"), ("Active", "NA"), ("Injured Reserve", "")]:
        assert rankings.injury_level(status, tag) == table.category(status, tag)
        assert rankings.is_ruled_out(status, tag) == table.is_ruled_out(status, tag)
    assert rankings.injury_multiplier("Active", "IR") == table.DYNASTY_VALUE_MULTIPLIER["major"]
    assert rankings.current_availability_multiplier("Active", "BUF", 5, "Out") == table.CURRENT_SEASON_MULTIPLIER["moderate"]


def test_tone_map_is_derived_from_the_table():
    assert injury_tone.TONE_BY_STATUS == table.TONE_BY_STATUS
    for row in table.ROWS:
        for key in row.tone_keys:
            assert injury_tone.injury_tone(key) == row.tone


def test_roster_status_sets_in_rankings_and_eligibility_agree_with_the_table():
    from modules import player_eligibility, player_state_authority

    for value in rankings.INJURY_STATUSES:
        assert table.category(value, "") != "healthy", value
    for value in rankings.PLAYABLE_OR_INJURED_STATUSES - {"active"}:
        assert table.classify(value, "").known, value
    for value in player_eligibility.RESERVE_STATUS_TERMS:
        assert table.classify(value, "").ruled_out, value
    for value in player_state_authority.NFL_NON_ACTIONABLE_STATUSES & table.terms_for_kinds(("reserve", "out", "inactive")):
        assert table.classify(value, "").ruled_out, value


def test_value_trend_skips_anyone_the_table_rules_out():
    import pandas as pd

    from modules import player_value_trend as pvt

    assert not hasattr(pvt, "OUT_STATUSES")  # no private injury vocabulary left
    assert table.is_ruled_out("Injured Reserve", "")  # status-only IR (blank injury_status) is out too


# --- the temporary-injury guardrail: what the downstream gate already covers -------


@pytest.mark.parametrize(
    "week,strategy",
    [(8, "contender"), (8, "rebuild"), (0, "contender")],
    ids=["in-season contender", "in-season rebuild", "offseason"],
)
def test_selling_a_core_starter_for_short_term_injury_cover_is_declined_by_the_analyzer(monkeypatch, week, strategy):
    """Evidence for docs/injury-status-table.md: the Analyzer (which gates every Hub/Finder idea)
    already declines the harm case ``trade_ideas._temporary_injury_trade_guardrail`` hard-fails at
    generation time, in season (lineup model) and in the offseason (value ladder)."""

    from modules import nfl_schedule
    import tests.test_trade_lineup_model as t

    monkeypatch.setattr(nfl_schedule, "team_bye_week", lambda team, season, **kw: 99)
    roster = [
        t._row("QB1", "QB", 6000, ppg=20), t._row("RB1", "RB", 6000, ppg=16), t._row("RB2", "RB", 5200, ppg=14),
        t._row("WR1", "WR", 7800, ppg=19, age=23), t._row("WR2", "WR", 5000, ppg=14), t._row("WR3", "WR", 4800, ppg=13),
        t._row("TE1", "TE", 5000, ppg=11, status="Injured Reserve", injury="IR"), t._row("TE2", "TE", 1500, ppg=4),
    ]
    fit, verdict = t._evaluate(
        roster, ["WR1"], [t._row("TECover", "TE", 4700, ppg=9, age=29)], strategy=strategy,
        settings=dict(t.SETTINGS, current_week=week), waiver=t._fas(("TE", 3.0), ("WR", 5.0)),
    )
    assert (fit["lineup_model"] is not None) == bool(week)
    assert verdict.ui_verdict == "DECLINE"
