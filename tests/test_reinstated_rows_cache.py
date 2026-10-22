"""Sharing _reinstated_inactive_roster_rows' scoring under the valued pool's
own cache version (perf audit 2026-10-21).

The scoring is a pure function of (valued pool version, identity rows,
league settings, score field, disk-cache versions). These tests pin that a
repeat with the same inputs reuses the result, and that any changed input
or an unversioned frame is scored again, as before.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from modules import league_value_settings, rankings
from services import mobile_api_service as svc

_LOOKUP = {
    "ir_rb": {
        "player_id": "ir_rb",
        "full_name": "IR Runner",
        "position": "RB",
        "fantasy_positions": ["RB"],
        "team": "KC",
        "status": "Inactive",
        "injury_status": "IR",
        "age": 24,
    },
    "ir_wr": {
        "player_id": "ir_wr",
        "full_name": "IR Catcher",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "team": "BUF",
        "status": "Inactive",
        "injury_status": "IR",
        "age": 27,
    },
}
_SETTINGS = {"scoring_settings": {}}


def _pool() -> pd.DataFrame:
    return pd.DataFrame(
        [{"player_id": f"rb{i}", "position": "RB", "dynasty_score": 1000 + i * 100} for i in range(12)]
        + [{"player_id": f"wr{i}", "position": "WR", "dynasty_score": 900 + i * 100} for i in range(12)]
    )


def _versioned_pool(cache_key: str = "valued_players_frame:abc") -> pd.DataFrame:
    frame = _pool()
    league_value_settings._remember_valued_frame_cache_key(frame, cache_key)
    return frame


def _call(valued, ids=("ir_rb",), settings=_SETTINGS, **kwargs):
    return svc._reinstated_inactive_roster_rows(
        set(ids), players_lookup=_LOOKUP, valued=valued, settings=settings, score_field="dynasty_score", **kwargs
    )


def _patched_scoring():
    return (
        patch("modules.rankings.hydrate_reconciled_valuations_from_cache", side_effect=lambda ref, c: c.assign(dynasty_score=1150)),
        patch("modules.league_value_settings.apply_valuation_lens", side_effect=lambda df, lens, settings: df),
    )


def test_valued_frame_cache_key_is_only_known_for_the_exact_returned_frame():
    frame = _versioned_pool("valued_players_frame:k1")
    assert league_value_settings.valued_players_frame_cache_key(frame) == "valued_players_frame:k1"
    assert league_value_settings.valued_players_frame_cache_key(frame.copy()) == ""
    assert league_value_settings.valued_players_frame_cache_key(frame[frame["position"] == "RB"]) == ""
    assert league_value_settings.valued_players_frame_cache_key(_pool()) == ""
    assert league_value_settings.valued_players_frame_cache_key(None) == ""


def test_build_valued_players_frame_cached_versions_its_returned_frame():
    with patch.object(league_value_settings, "_build_valued_players_frame_cached", return_value=_pool()):
        frame = league_value_settings.build_valued_players_frame_cached(league_id="L1", lens="Dynasty", players_db_path="x.db")
    key = league_value_settings.valued_players_frame_cache_key(frame)
    assert key.startswith("valued_players_frame:")


def test_same_inputs_score_once_and_return_independent_rows():
    valued = _versioned_pool()
    hydrate, lens = _patched_scoring()
    with hydrate, lens, patch.object(svc, "_score_reinstated_inactive_rows", wraps=svc._score_reinstated_inactive_rows) as score:
        first = _call(valued)
        first[0]["name"] = "MUTATED"
        second = _call(valued)
    assert score.call_count == 1
    assert second[0]["player_id"] == "ir_rb"
    assert second[0]["name"] == "IR Runner"
    assert second[0]["dynasty_score"] == 1150


def test_any_changed_input_is_scored_again():
    valued = _versioned_pool()
    hydrate, lens = _patched_scoring()
    with hydrate, lens, patch.object(svc, "_score_reinstated_inactive_rows", wraps=svc._score_reinstated_inactive_rows) as score:
        _call(valued)
        _call(valued, ids=("ir_rb", "ir_wr"))  # different identity rows
        _call(valued, settings={"scoring_settings": {"rec": 1}})  # different league settings
        _call(_versioned_pool("valued_players_frame:newer-bucket"))  # newer valued pool
        versions = rankings.reconciled_valuation_cache_versions()
        bumped = tuple((path, (mtime or 0) + 1, size) for path, mtime, size in versions)
        with patch("modules.rankings.reconciled_valuation_cache_versions", return_value=bumped):
            _call(valued)  # a refreshed disk cache
    assert score.call_count == 5


def test_an_unversioned_frame_is_scored_on_every_call_as_before():
    hydrate, lens = _patched_scoring()
    with hydrate, lens, patch.object(svc, "_score_reinstated_inactive_rows", wraps=svc._score_reinstated_inactive_rows) as score:
        _call(_pool())
        _call(_pool())
    assert score.call_count == 2


def test_suggested_lineup_split_shares_the_pool_version_across_its_internal_copy():
    valued = _versioned_pool()
    roster = {"players": ["rb0", "ir_rb"], "starters": ["rb0"], "reserve": ["ir_rb"]}
    hydrate, lens = _patched_scoring()
    with hydrate, lens, patch.object(svc, "_score_reinstated_inactive_rows", wraps=svc._score_reinstated_inactive_rows) as score:
        first = svc._suggested_lineup_split(valued, roster, _SETTINGS, "dynasty_score", players_lookup=_LOOKUP)
        second = svc._suggested_lineup_split(valued, roster, _SETTINGS, "dynasty_score", players_lookup=_LOOKUP)
    assert score.call_count == 1
    assert first == second
    assert "ir_rb" in {row["player_id"] for row in first[0] + first[1]}
