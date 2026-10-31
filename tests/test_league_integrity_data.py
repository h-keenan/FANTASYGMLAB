"""modules.league_integrity_data: the Sleeper-fetching wrapper, with fake
Sleeper calls (no network, no players database)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from modules import league_integrity_data as data
from tests.test_league_integrity import TEAMS, _tank_lineups, build


def _run(status="in_season", leg=7):
    built = build(_tank_lineups())
    league = {**built["league"], "status": status, "season": "2026",
              "settings": {**built["league"]["settings"], "leg": leg}}
    players = {p: {"full_name": m["name"], "position": m["position"], "team": "XXX"} for p, m in built["player_meta"].items()}
    with patch("modules.sleeper.get_league", return_value=league), \
            patch("modules.sleeper.get_rosters", return_value=built["rosters"]), \
            patch("modules.sleeper.get_league_roster_profiles", return_value=built["profiles"]), \
            patch("modules.sleeper.get_matchups", side_effect=lambda lid, w: built["weekly"].get(w, [])), \
            patch("modules.sleeper.get_players", return_value=players), \
            patch("modules.sleeper.get_transactions", return_value=[]), \
            patch("modules.league_value_settings.build_valued_players_frame_cached", return_value=pd.DataFrame()), \
            patch("modules.nfl_schedule.team_bye_week", return_value=None):
        return data._build("L1", "record", "unused.db", 0)


def test_build_reads_weeks_before_current_leg_only():
    report = _run(leg=7)
    assert report["weeks_evaluated"] == 6 and report["week"] == 7
    tanker = next(t for t in report["teams"] if t["roster_id"] == 6)
    assert tanker["band"] == "worth_a_look"  # lineup only; no transactions fetched


def test_offseason_league_reports_offseason():
    assert _run(status="pre_draft", leg=0)["reason"] == "offseason"


def test_is_commissioner_requires_is_owner_true():
    users = [{"user_id": "a", "is_owner": True}, {"user_id": "b", "is_owner": None}, {"user_id": "c"}]
    assert data.is_commissioner(users, "a") and not data.is_commissioner(users, "b")
    assert not data.is_commissioner(users, "c") and not data.is_commissioner(users, "")
