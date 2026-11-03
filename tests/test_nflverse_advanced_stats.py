"""modules.nflverse_advanced_stats: aggregation, mapping, validation, IO."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from modules import nflverse_advanced_stats as adv
from modules.gsis_crosswalk import GsisCrosswalk


def _pbp():
    rows = [
        # KC week 1: WR 00-0000001 targeted at the 10 (RZ), run by RB 00-0000002 at the 3 (GL), a sack, a kneel, a 2pt.
        dict(season_type="REG", week=1, posteam="KC", play_type="pass", yardline_100=10, receiver_player_id="00-0000001", rusher_player_id=None, sack=0, two_point_attempt=0),
        dict(season_type="REG", week=1, posteam="KC", play_type="run", yardline_100=3, receiver_player_id=None, rusher_player_id="00-0000002", sack=0, two_point_attempt=0),
        dict(season_type="REG", week=1, posteam="KC", play_type="run", yardline_100=60, receiver_player_id=None, rusher_player_id="00-0000002", sack=0, two_point_attempt=0),
        dict(season_type="REG", week=1, posteam="KC", play_type="pass", yardline_100=40, receiver_player_id=None, rusher_player_id=None, sack=1, two_point_attempt=0),
        dict(season_type="REG", week=1, posteam="KC", play_type="qb_kneel", yardline_100=1, receiver_player_id=None, rusher_player_id="00-0000009", sack=0, two_point_attempt=0),
        dict(season_type="REG", week=1, posteam="KC", play_type="pass", yardline_100=2, receiver_player_id="00-0000001", rusher_player_id=None, sack=0, two_point_attempt=1),
        dict(season_type="POST", week=1, posteam="KC", play_type="pass", yardline_100=10, receiver_player_id="00-0000001", rusher_player_id=None, sack=0, two_point_attempt=0),
    ]
    return pd.DataFrame(rows)


def _stats():
    return pd.DataFrame([
        dict(player_id="00-0000001", player_display_name="Wide Out", position="WR", season=2026, week=1, season_type="REG", team="KC", targets=1, carries=0, receptions=1, receiving_air_yards=8.0, target_share=1.0, air_yards_share=1.0, wopr=2.2),
        dict(player_id="00-0000002", player_display_name="Run Back", position="RB", season=2026, week=1, season_type="REG", team="KC", targets=0, carries=2, receptions=0, receiving_air_yards=0.0, target_share=0.0, air_yards_share=0.0, wopr=0.0),
        dict(player_id="00-0000003", player_display_name="Nobody Known", position="TE", season=2026, week=1, season_type="REG", team="KC", targets=0, carries=0, receptions=0, receiving_air_yards=0.0, target_share=0.0, air_yards_share=0.0, wopr=0.0),
        dict(player_id="00-0000004", player_display_name="Quarter Back", position="QB", season=2026, week=1, season_type="REG", team="KC", targets=0, carries=0, receptions=0, receiving_air_yards=0.0, target_share=None, air_yards_share=None, wopr=None),
    ])


SLEEPER = {
    "10": {"player_id": "10", "full_name": "Wide Out", "team": "KC", "position": "WR", "gsis_id": "00-0000001"},
    "11": {"player_id": "11", "full_name": "Run Back", "team": "KC", "position": "RB", "gsis_id": ""},
}


def test_aggregate_pbp_counts_only_real_looks():
    players, teams = adv.aggregate_pbp(_pbp())
    assert players[("00-0000001", 1)] == {"rz_targets": 1}
    assert players[("00-0000002", 1)] == {"rz_carries": 1, "gl_carries": 1}
    assert ("00-0000009", 1) not in players  # kneel excluded
    assert teams[("KC", 1)] == {"rush_att": 2, "rz_rush_att": 1, "targets": 1, "rz_targets": 1}


def test_build_payload_maps_exact_then_by_name_and_keeps_unmapped_honest():
    players, teams = adv.aggregate_pbp(_pbp())
    payload = adv.build_season_payload(2026, _stats(), players, teams, GsisCrosswalk(SLEEPER), generated_at="t")
    assert set(payload["players"]) == {"00-0000001", "00-0000002", "00-0000003"}  # QB excluded
    assert payload["players"]["00-0000001"]["match"] == "gsis_exact"
    assert payload["players"]["00-0000002"]["match"] == "name_team_position"
    assert payload["players"]["00-0000002"]["sleeper_id"] == "11"
    assert payload["players"]["00-0000003"]["sleeper_id"] is None
    assert payload["meta"]["unmapped_by_reason"] == {"player_not_in_sleeper_dump": 1}
    wk = payload["players"]["00-0000002"]["weeks"]["1"]
    assert wk["opportunity_share"] == round(2 / 3, 4)  # 2 carries / (2 rush + 1 target)
    assert wk["gl_carries"] == 1


def test_name_match_with_conflicting_gsis_is_rejected():
    sleeper = {"11": {"player_id": "11", "full_name": "Run Back", "team": "KC", "position": "RB", "gsis_id": "00-0000099"}}
    players, teams = adv.aggregate_pbp(_pbp())
    payload = adv.build_season_payload(2026, _stats(), players, teams, GsisCrosswalk(sleeper), generated_at="t")
    assert payload["players"]["00-0000002"]["sleeper_id"] is None
    assert payload["players"]["00-0000002"]["match"] == "gsis_conflict"


def test_team_alias_normalized():
    assert adv.normalize_team("LA") == "LAR" and adv.normalize_team("jac") == "JAX"


def test_validate_rejects_tiny_or_unmapped_payloads():
    assert adv.validate_payload({"schema_version": adv.SCHEMA_VERSION, "players": {}}, min_players=2)
    bad = {"schema_version": adv.SCHEMA_VERSION, "through_week": 3, "players": {"a": {}, "b": {}, "c": {}}, "meta": {"mapped_to_sleeper": 1}}
    assert any("mapped" in p for p in adv.validate_payload(bad, min_players=2))
    ok = {**bad, "meta": {"mapped_to_sleeper": 3}}
    assert adv.validate_payload(ok, min_players=2) == []


def test_write_if_changed_ignores_generated_at(tmp_path):
    path = str(tmp_path / "x.json")
    payload = {"schema_version": 1, "generated_at": "a", "players": {}}
    assert adv.write_if_changed(payload, path) is True
    assert adv.write_if_changed({**payload, "generated_at": "b"}, path) is False
    assert adv.write_if_changed({**payload, "players": {"z": 1}}, path) is True
    assert json.loads(open(path).read())["players"] == {"z": 1}


def test_reader_reports_unavailable_explicitly(tmp_path):
    out = adv.weekly_for_sleeper_id("11", 2026, data_dir=str(tmp_path))
    assert out == {"available": False, "reason": "advanced_stats_file_unavailable"}
    players, teams = adv.aggregate_pbp(_pbp())
    payload = adv.build_season_payload(2026, _stats(), players, teams, GsisCrosswalk(SLEEPER), generated_at="t")
    adv.write_if_changed(payload, str(tmp_path / "nflverse_advanced_stats_2026.json"))
    found = adv.weekly_for_sleeper_id("11", 2026, data_dir=str(tmp_path))
    assert found["available"] and found["weeks"][1]["gl_carries"] == 1
    assert adv.weekly_for_sleeper_id("999", 2026, data_dir=str(tmp_path))["reason"] == "player_not_in_advanced_stats"


def test_download_retries_then_raises_explicit_error(monkeypatch):
    calls = []

    class Boom:
        def get(self, *a, **k):
            calls.append(1)
            raise OSError("down")

    monkeypatch.setattr(adv, "FETCH_BACKOFF_SECONDS", 0)
    with pytest.raises(adv.AdvancedStatsError):
        adv._download("http://x", max_bytes=10, session=Boom())
    assert len(calls) == adv.FETCH_ATTEMPTS
