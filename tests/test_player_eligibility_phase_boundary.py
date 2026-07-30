from datetime import datetime, timezone

import pandas as pd

from modules.player_eligibility import annotate_player_eligibility, player_eligibility
from scripts.benchmark_player_eligibility_trust import decompose_annotation


NOW = datetime(2026, 7, 30, tzinfo=timezone.utc)


def _player(**overrides):
    player = {
        "player_id": "101",
        "name": "Controlled Player",
        "position": "QB",
        "fantasy_positions": "QB",
        "sport": "nfl",
        "active": True,
        "status": "active",
        "team": "CHI",
        "years_exp": 4,
        "stats_season": 2025,
        "news_updated": int(NOW.timestamp()),
    }
    player.update(overrides)
    return player


def test_phase_harness_is_field_for_field_equivalent_to_production_annotation():
    players = pd.DataFrame([_player(), _player(player_id="202", position="RB")])

    actual, phases = decompose_annotation(players, now=NOW)
    expected = annotate_player_eligibility(players, now=NOW)

    pd.testing.assert_frame_equal(actual, expected, check_dtype=True)
    assert set(phases) == {
        "dataframe_copy_ms",
        "eligibility_validation_ms",
        "eligibility_derivation_ms",
        "trust_fingerprint_preparation_ms",
        "trust_identity_preparation_ms",
        "trust_preparation_ms",
        "trust_enforcement_ms",
        "result_assignment_ms",
        "annotation_total_ms",
    }


def test_eligibility_is_date_sensitive_and_not_snapshot_deterministic():
    news_timestamp = int(datetime(2024, 7, 29, tzinfo=timezone.utc).timestamp())
    player = _player(
        stats_season=None,
        fantasycalc_value=0,
        depth_chart_position="",
        depth_chart_order=0,
        years_exp=4,
        news_updated=news_timestamp,
    )

    within_window = player_eligibility(
        player,
        now=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    outside_window = player_eligibility(player, now=NOW)

    assert within_window["eligible"] is True
    assert outside_window["eligible"] is False
    assert outside_window["reason"] == "missing_current_player_corroboration"
