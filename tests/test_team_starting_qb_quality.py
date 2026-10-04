"""modules.rankings.team_starting_qb_quality — the "team passing-offense
tier" signal added to close a real gap a read-only weekly-projection audit
flagged: WR/TE projections had zero awareness of their own team's starting
QB quality. This reuses the existing ``_usage_quality_from_rates`` QB
scoring and ``depth_chart_slot`` helpers rather than reimplementing them.

Covers selection (best depth-chart slot, tie-break by pass_att_pg, fallback
to pass_att_pg when depth-chart data is missing/ambiguous) and the honest
"no signal" edge cases (no QB on the roster, empty/malformed frame). This
module's output is never consumed anywhere near value_score or
modules.rankings's own composite valuation — see
modules.player_projections for the only real caller.
"""

from __future__ import annotations

import pandas as pd

from modules import rankings


def _qb_row(**kwargs):
    base = {
        "player_id": None,
        "position": "QB",
        "team": None,
        "depth_chart_position": None,
        "depth_chart_order": None,
        "pass_attempts": None,
        "games_played": None,
        "rushing_yards": None,
    }
    base.update(kwargs)
    return base


def test_picks_clear_depth_chart_starter():
    df = pd.DataFrame(
        [
            _qb_row(player_id="starter", team="AAA", depth_chart_position="QB1", pass_attempts=320, games_played=10),
            _qb_row(player_id="backup", team="AAA", depth_chart_position="QB2", pass_attempts=20, games_played=10),
        ]
    )

    quality, info = rankings.team_starting_qb_quality("AAA", df)

    assert info["selected_player_id"] == "starter"
    assert info["selection_method"] == "depth_chart"
    assert info["qb_count"] == 2
    assert quality is not None
    assert 0.0 <= quality <= 1.0


def test_falls_back_to_pass_att_pg_when_depth_chart_missing():
    df = pd.DataFrame(
        [
            _qb_row(player_id="qb_high_volume", team="BBB", pass_attempts=300, games_played=10),
            _qb_row(player_id="qb_low_volume", team="BBB", pass_attempts=30, games_played=10),
        ]
    )

    quality, info = rankings.team_starting_qb_quality("BBB", df)

    assert info["selected_player_id"] == "qb_high_volume"
    assert info["selection_method"] == "pass_att_pg_fallback"
    assert quality is not None


def test_tie_at_best_depth_chart_slot_breaks_by_pass_att_pg():
    df = pd.DataFrame(
        [
            _qb_row(player_id="qb_a", team="CCC", depth_chart_position="QB1", pass_attempts=100, games_played=5),
            _qb_row(player_id="qb_b", team="CCC", depth_chart_position="QB1", pass_attempts=250, games_played=5),
        ]
    )

    quality, info = rankings.team_starting_qb_quality("CCC", df)

    assert info["selected_player_id"] == "qb_b"
    assert info["selection_method"] == "depth_chart_tie_broken_by_pass_att_pg"
    assert quality is not None


def test_no_qb_on_roster_returns_no_signal():
    df = pd.DataFrame(
        [
            _qb_row(player_id="other_team_qb", team="ZZZ", depth_chart_position="QB1", pass_attempts=300, games_played=10),
        ]
    )

    quality, info = rankings.team_starting_qb_quality("AAA", df)

    assert quality is None
    assert info["qb_count"] == 0
    assert info["selected_player_id"] is None


def test_empty_frame_returns_no_signal():
    quality, info = rankings.team_starting_qb_quality("AAA", pd.DataFrame())

    assert quality is None
    assert info["selected_player_id"] is None


def test_none_frame_returns_no_signal():
    quality, info = rankings.team_starting_qb_quality("AAA", None)

    assert quality is None


def test_blank_team_returns_no_signal():
    df = pd.DataFrame(
        [_qb_row(player_id="qb_a", team="AAA", depth_chart_position="QB1", pass_attempts=300, games_played=10)]
    )

    quality, info = rankings.team_starting_qb_quality("", df)

    assert quality is None
    assert info["team"] is None


def test_qb_with_no_usable_evidence_at_all_returns_none_quality_but_identifies_qb():
    df = pd.DataFrame(
        [_qb_row(player_id="mystery_qb", team="DDD", depth_chart_position="QB1")]
    )

    quality, info = rankings.team_starting_qb_quality("DDD", df)

    assert quality is None
    assert info["selected_player_id"] == "mystery_qb"
    assert info["selection_method"] == "depth_chart"
