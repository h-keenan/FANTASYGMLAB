"""True-cold structured refresh attribution and output-equivalence."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from modules import player_hydrate_stages
from modules import rankings
from modules import structured_player_refresh as spr


def _tiny_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "player_id": "1",
                "name": "Alpha",
                "position": "WR",
                "team": "KC",
                "team_abbr": "KC",
                "status": "Active",
                "injury_status": "",
                "depth_chart_position": "WR",
                "depth_chart_order": 1,
                "active": True,
                "news_updated": 1,
                "market_score": 4000.0,
                "age": 26.0,
                "years_exp": 4.0,
                "search_rank": 20,
                "value": 4000,
                "score": 4000,
                "dynasty_score": 4000,
                "value_score": 4000,
                "is_current_fantasy_eligible": True,
            }
        ]
    )


def test_structured_refresh_emits_exclusive_substages():
    player_hydrate_stages.begin_hydrate()
    frame = _tiny_frame()
    sleeper = {
        "1": {
            "full_name": "Alpha",
            "position": "WR",
            "team": "SF",
            "status": "Active",
            "injury_status": "Questionable",
            "depth_chart_position": "WR",
            "depth_chart_order": 1,
            "active": True,
            "news_updated": 2,
            "search_rank": 20,
        }
    }
    spr.refresh_structured_player_state(frame, sleeper, reconcile_universe=False)
    names = [row["name"] for row in player_hydrate_stages.recorded()]
    assert "structured_patch_fields" in names
    assert "sleeper_lookup_index" in names


def test_patch_matches_normalize_owned_sleeper_fields():
    frame = _tiny_frame()
    sleeper = {
        "1": {
            "full_name": "Alpha",
            "position": "WR",
            "team": "DAL",
            "team_abbr": "DAL",
            "status": "Injured Reserve",
            "injury_status": "IR",
            "depth_chart_position": "WR",
            "depth_chart_order": 2,
            "active": True,
            "news_updated": 99,
            "search_rank": 20,
        }
    }
    patched = spr._patch_structured_fields(frame, sleeper)
    expected = rankings.normalize_player_record("1", dict(sleeper["1"]))
    for column in spr.STRUCTURED_PATCH_FIELDS:
        assert patched.loc[0, column] == expected[column]


def test_sleeper_injury_mutation_changes_structured_fingerprint():
    frame = _tiny_frame()
    healthy = {"1": {"position": "WR", "team": "KC", "status": "Active", "injury_status": "", "search_rank": 20, "full_name": "A"}}
    injured = {"1": {"position": "WR", "team": "KC", "status": "Active", "injury_status": "Out", "search_rank": 20, "full_name": "A"}}
    first = spr._patch_structured_fields(frame, healthy)
    second = spr._patch_structured_fields(frame, injured)
    assert spr.structured_state_fingerprint(first) != spr.structured_state_fingerprint(second)
    assert second.loc[0, "injury_status"] == "Out"


def test_eligibility_annotation_still_uses_canonical_row_owner():
    source = open("modules/player_eligibility.py", encoding="utf-8").read()
    assert "player_eligibility(row, now=resolved_now)" in source
    assert "enforce_player_record(" in source
