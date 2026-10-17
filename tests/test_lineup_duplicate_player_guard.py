"""A player must never fill two lineup slots at once.

Reported by coridian_ (screenshots, 2026-10-17): Ashton Jeanty, Marvin
Harrison, Parker Washington, and Cam Skattebo each appeared TWICE in a
suggested lineup — once in a named-position slot and again in FLEX/WR-RB.

Root cause: suggest_optimal_lineup's internal `assign_slots` tracks
uniqueness by row INDEX, not by player_id. If the incoming roster frame
ever has the same player_id on two separate rows (an upstream data
duplication, not reproduced/root-caused here), each row gets independently
assigned to its own slot since nothing stops a second row for an
already-placed player from also winning a slot. The fix dedupes by
player_id before slot assignment, in the one shared engine every roster/
lineup surface (Dashboard, My Team, Matchup, GM Plan, League Rankings,
Trade Analyzer, Trade Ideas) calls — a guard against the symptom
regardless of where the upstream duplicate row came from.
"""

import pandas as pd

from modules import team_eval


_SETTINGS = {
    "qb_count": 1,
    "rb_count": 1,
    "wr_count": 1,
    "te_count": 1,
    "regular_flex_count": 1,
    "k_count": 0,
}


def _player(player_id, position, score):
    return {
        "player_id": player_id,
        "name": player_id,
        "position": position,
        "team": "HOU",
        "age": 24,
        "status": "Active",
        "injury_status": "",
        "value_score": score,
        "dynasty_score": score,
    }


def test_a_duplicated_player_row_never_fills_two_slots():
    # "wr1" appears twice in the incoming frame (the exact shape of the
    # reported bug) — high enough value to be both the WR starter AND the
    # FLEX pick if nothing deduped it first.
    rows = [
        _player("qb1", "QB", 100),
        _player("rb1", "RB", 90),
        _player("wr1", "WR", 95),
        _player("wr1", "WR", 95),
        _player("te1", "TE", 50),
        _player("wr2", "WR", 40),
    ]

    lineup = team_eval.suggest_optimal_lineup(pd.DataFrame(rows), _SETTINGS)

    # Only one row for wr1 survives at all...
    wr1_rows = lineup[lineup["player_id"] == "wr1"]
    assert len(wr1_rows) == 1
    # ...so it can only occupy one slot, not two.
    starters = lineup[lineup["suggested_starter"]]
    wr1_starter_rows = starters[starters["player_id"] == "wr1"]
    assert len(wr1_starter_rows) == 1
    # The genuinely different next-best WR gets the FLEX spot — correct
    # behavior once wr1's phantom second row is gone, not wr1 double-
    # counted into both WR and FLEX.
    assert "wr2" in set(starters["player_id"])
    wr2_slot = starters[starters["player_id"] == "wr2"]["slot"].iloc[0]
    assert wr2_slot == "FLEX"


def test_duplicate_rows_with_the_same_score_keep_exactly_one_copy():
    rows = [_player("rb1", "RB", 80), _player("rb1", "RB", 80), _player("rb1", "RB", 80)]

    lineup = team_eval.suggest_optimal_lineup(pd.DataFrame(rows), _SETTINGS)

    assert len(lineup[lineup["player_id"] == "rb1"]) == 1


def test_no_duplicates_is_unaffected():
    rows = [_player("qb1", "QB", 100), _player("rb1", "RB", 90), _player("wr1", "WR", 80)]

    lineup = team_eval.suggest_optimal_lineup(pd.DataFrame(rows), _SETTINGS)

    assert len(lineup) == 3
    assert set(lineup["player_id"]) == {"qb1", "rb1", "wr1"}
