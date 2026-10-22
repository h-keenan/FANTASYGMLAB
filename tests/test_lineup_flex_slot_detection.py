"""Regression (logic audit 2026-10): Sleeper flex-slot detection and the
order flex slots are filled in.

- WRRB_FLEX was counted as a WR/RB flex AND (via the "FLEX" substring) as an
  RB/WR/TE flex, so a WRRB_FLEX league got one more lineup slot than it has.
- IDP_FLEX was counted as an offensive RB/WR/TE flex.
- FLEX was filled before the narrower WR/RB slot, which could bench a TE
  that should have started.
"""

from __future__ import annotations

import pandas as pd

from modules import league_value_settings
from modules.team_eval import _lineup_slots, _score_starter_weighted_roster, suggest_optimal_lineup


def _settings(positions):
    return league_value_settings.detect_league_value_settings_from_payload(
        {"roster_positions": positions + ["BN"] * 6}
    )


def test_wrrb_flex_is_counted_once():
    positions = ["QB", "RB", "RB", "WR", "WR", "TE", "WRRB_FLEX", "FLEX"]
    settings = _settings(positions)
    assert settings["regular_flex_count"] == 1
    assert settings["wrrb_flex_count"] == 1
    assert settings["flex_count"] == 2
    assert sum(_lineup_slots(settings).values()) == len(positions)


def test_idp_flex_is_not_an_offensive_flex():
    positions = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF", "DL", "LB", "DB", "IDP_FLEX"]
    settings = _settings(positions)
    assert settings["regular_flex_count"] == 1
    assert settings["flex_count"] == 1
    assert settings["other_starter_count"] == 5  # DEF, DL, LB, DB, IDP_FLEX
    assert _lineup_slots(settings)["FLEX"] == 1


def _roster():
    rows = [
        ("qb", "QB", 5000),
        ("rb1", "RB", 9000),
        ("rb2", "RB", 8000),
        ("rb3", "RB", 7000),
        ("wr1", "WR", 6000),
        ("wr2", "WR", 5900),
        ("te1", "TE", 4000),
        ("te2", "TE", 3000),
        ("wr3", "WR", 1000),
    ]
    return pd.DataFrame(
        [
            {"player_id": pid, "name": pid, "position": pos, "value_score": score, "status": "Active", "injury_status": ""}
            for pid, pos, score in rows
        ]
    )


def test_narrow_wrrb_slot_is_filled_before_flex():
    # QB, RB, RB, WR, WR, TE, WRRB_FLEX, FLEX: best lineup starts rb3 at
    # WR/RB and te2 at FLEX. Filling FLEX first put rb3 at FLEX and wr3
    # (1000) at WR/RB, benching te2 (3000).
    settings = _settings(["QB", "RB", "RB", "WR", "WR", "TE", "WRRB_FLEX", "FLEX"])
    lineup = suggest_optimal_lineup(_roster(), settings, score_field="value_score")
    starters = set(lineup.loc[lineup["suggested_starter"], "player_id"])
    assert "te2" in starters
    assert "wr3" not in starters
    assert int(lineup["suggested_starter"].sum()) == 8

    scored = _score_starter_weighted_roster(_roster(), "value_score", settings)
    expected = 5000 + 9000 + 8000 + 7000 + 6000 + 5900 + 4000 + 3000
    assert scored["starter_score"] == expected
