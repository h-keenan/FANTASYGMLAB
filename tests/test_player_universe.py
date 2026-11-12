from datetime import date, datetime, timezone

import pandas as pd
import pytest

from modules import player_universe as pu
from modules import rankings
from modules.player_eligibility import player_eligibility

NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
SEASON = 2026
MS_PER_DAY = 86_400_000


def news_days_ago(days):
    return int(NOW.timestamp() * 1000) - days * MS_PER_DAY


def row(**kw):
    base = {"position": "WR", "team": "", "status": "Active", "active": True, "years_exp": 5, "age": 27,
            "injury_status": "", "depth_chart_position": "", "depth_chart_order": None,
            "news_updated": None, "fantasycalc_value": 0, "stats_season": None, "prior_season": None}
    base.update(kw)
    return base


def state(**kw):
    return pu.lifecycle_state(row(**kw), now=NOW, season=SEASON)


# --- age ----------------------------------------------------------------------
def test_age_on_completed_years():
    assert pu.age_on("2000-11-12", date(2026, 11, 12)) == 26
    assert pu.age_on("2000-11-13", date(2026, 11, 12)) == 25
    assert pu.age_on("2000-02-29", date(2026, 2, 28)) == 25
    assert pu.age_on("", date(2026, 1, 1)) is None
    assert pu.age_on("not-a-date", date(2026, 1, 1)) is None
    assert pu.age_on("2030-01-01", date(2026, 1, 1)) is None


def test_resolve_age_prefers_birth_date_over_frozen_sleeper_age():
    # Henry Ruggs: Sleeper still says 22 on a record frozen years ago.
    assert pu.resolve_age("1999-01-24", 22, as_of=date(2026, 11, 12)) == 27.0
    assert pu.resolve_age("", 22, as_of=date(2026, 11, 12)) == 22.0
    assert pu.resolve_age(None, None, as_of=date(2026, 11, 12)) is None


def test_normalize_player_record_keeps_birth_date_and_corrects_age():
    rec = rankings.normalize_player_record(
        "6789",
        {"full_name": "Henry Ruggs", "position": "WR", "age": 22, "birth_date": "1999-01-24", "search_rank": 700},
        as_of=date(2026, 11, 12),
    )
    assert rec["birth_date"] == "1999-01-24" and rec["age"] == 27.0
    legacy = rankings.normalize_player_record("1", {"full_name": "No Birth", "position": "WR", "age": 25})
    assert legacy["age"] == 25.0 and legacy["birth_date"] == ""


def test_age_curve_runs_on_the_corrected_age():
    # Elezekiel Elliott shape: Sleeper's frozen age says 22, birth date says 31.
    frozen = rankings.age_multiplier("RB", 22)
    real = rankings.age_multiplier("RB", 31)
    assert real < frozen


# --- lifecycle ----------------------------------------------------------------
def test_team_held_states():
    assert state(team="KC") == pu.ACTIVE_ROSTERED
    assert state(team="KC", status="Injured Reserve", active=False) == pu.RESERVE
    assert state(team="KC", status="Inactive", injury_status="IR", active=True) == pu.RESERVE
    assert state(team="KC", status="Practice Squad") == pu.PRACTICE_SQUAD
    assert state(team="KC", years_exp=1, age=22) == pu.ACTIVE_ROSTERED  # rookie, no other evidence needed


def test_free_agent_needs_real_evidence_not_just_news():
    assert state(fantasycalc_value=1200) == pu.FREE_AGENT
    assert state(stats_season=2025) == pu.FREE_AGENT
    assert state(prior_season=2025) == pu.FREE_AGENT
    assert state(depth_chart_position="WR") == pu.FREE_AGENT
    # Fresh news alone is how retirees linger (Sleeper bumps news_updated on record edits).
    assert state(news_updated=news_days_ago(3)) == pu.RETIRED_OR_UNKNOWN
    assert state() == pu.RETIRED_OR_UNKNOWN
    assert state(stats_season=2023) == pu.RETIRED_OR_UNKNOWN  # stale stats


def test_phantom_rookie_is_unknown_not_a_current_rookie():
    assert state(years_exp=1, age=22) == pu.RETIRED_OR_UNKNOWN
    assert state(years_exp=0, age=21, fantasycalc_value=900) == pu.FREE_AGENT


def test_stale_listed_veteran_and_retirement_age():
    assert state(team="PIT", years_exp=18, age=39) == pu.RETIRED_OR_UNKNOWN  # Roethlisberger shape
    assert state(team="PIT", years_exp=18, age=39, depth_chart_position="QB") == pu.ACTIVE_ROSTERED
    assert state(age=41, fantasycalc_value=1000) == pu.RETIRED_OR_UNKNOWN
    assert state(team="LV", position="K", years_exp=15, age=41, depth_chart_position="K") == pu.ACTIVE_ROSTERED


def test_inactive_status_is_not_a_retirement_synonym():
    assert state(status="Inactive", active=False, stats_season=2025) == pu.INACTIVE
    assert state(status="Inactive", active=False) == pu.RETIRED_OR_UNKNOWN


def test_annotate_lifecycle_is_aligned_and_covers_every_row():
    frame = pd.DataFrame([row(team="KC"), row(), row(fantasycalc_value=500)], index=[10, 20, 30])
    out = pu.annotate_lifecycle(frame, now=NOW)
    assert out.index.tolist() == [10, 20, 30]
    assert out.tolist() == [pu.ACTIVE_ROSTERED, pu.RETIRED_OR_UNKNOWN, pu.FREE_AGENT]
    assert set(out) <= set(pu.LIFECYCLE_STATES)


def test_named_predicates_per_surface():
    table = {s: (pu.is_rankable(s), pu.is_searchable(s), pu.is_waiver_actionable(s), pu.is_tradeable_asset(s))
             for s in pu.LIFECYCLE_STATES}
    assert table[pu.ACTIVE_ROSTERED] == (True, True, True, True)
    assert table[pu.FREE_AGENT] == (True, True, True, True)
    assert table[pu.RESERVE] == (True, True, False, True)
    assert table[pu.PRACTICE_SQUAD] == (True, True, False, True)
    assert table[pu.INACTIVE] == (False, True, False, True)
    assert table[pu.RETIRED_OR_UNKNOWN] == (False, False, False, False)
    series = pd.Series([pu.FREE_AGENT, pu.RETIRED_OR_UNKNOWN])
    assert pu.is_rankable(series).tolist() == [True, False]


# --- eligibility gate (membership is preserved; the rookie rule is evidence-based) ----
def test_gate_rookie_requires_a_club_but_membership_is_retained():
    teamed = player_eligibility(row(team="NE", years_exp=1, age=22), now=NOW)
    assert teamed == {"eligible": True, "reason": "current_rookie", "current_signal": True}
    ghost = player_eligibility(row(years_exp=1, age=22), now=NOW)
    assert ghost["eligible"] is True  # nobody leaves the pool in this phase
    assert ghost["reason"] == "retained_unevidenced_record" and ghost["current_signal"] is False


def test_gate_unchanged_for_ordinary_rows():
    assert player_eligibility(row(team="KC", depth_chart_position="WR"), now=NOW)["reason"] == "corroborated_current_player"
    assert player_eligibility(row(status="Inactive", active=False), now=NOW)["reason"] == "explicitly_inactive"
    assert player_eligibility(row(position="DB", fantasy_positions=["DB"]), now=NOW)["reason"] == "invalid_fantasy_position"
    stale = player_eligibility(row(years_exp=9, age=30, news_updated=news_days_ago(900)), now=NOW)
    assert stale["eligible"] is False


def test_retention_policy_is_one_switch(monkeypatch):
    from modules import player_eligibility as pe

    monkeypatch.setattr(pe, "RETAIN_UNEVIDENCED_ROOKIE_RECORDS", False)
    assert pe.player_eligibility(row(years_exp=1, age=22), now=NOW)["eligible"] is False
    assert pe.player_eligibility(row(team="NE", years_exp=1, age=22), now=NOW)["eligible"] is True
