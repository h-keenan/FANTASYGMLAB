"""Regression: League Rankings must not KeyError when summary frames lack archetype_label."""

from unittest.mock import patch

import pandas as pd
import pytest

from modules.team_eval import refine_team_directions


def _summary_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "roster_id": 1,
                "team_name": "Alpha",
                "owner_name": "A",
                "power_score": 120,
                "franchise_score": 110,
                "power_rank": 1,
                "franchise_rank": 1,
                "strategy_display": "Contend",
                "total_score": 100,
            },
            {
                "roster_id": 2,
                "team_name": "Beta",
                "owner_name": "B",
                "power_score": 90,
                "franchise_score": 95,
                "power_rank": 2,
                "franchise_rank": 2,
                "strategy_display": "Rebuild",
                "total_score": 80,
            },
        ]
    )


def test_production_crash_path_summary_frame_lacks_archetype_label():
    """Reproduce the #212 KeyError: hard column select on a frame without archetype_label."""

    df_intel = _summary_frame()
    assert "archetype_label" not in df_intel.columns
    with pytest.raises(KeyError, match="archetype_label"):
        _ = df_intel[
            [
                "power_rank",
                "franchise_rank",
                "team_name",
                "owner_name",
                "archetype_label",
                "trading_style",
                "roster_philosophy",
                "asset_behavior",
                "activity_level",
                "power_score",
                "franchise_score",
                "draft_capital",
                "health_flag",
                "injury_burden",
                "injured_starters",
                "total_score",
                "starter_score",
                "bench_score",
                "raw_roster_score",
                "avg_age",
                "qb_score",
                "rb_score",
                "wr_score",
                "te_score",
                "strategy_display",
            ]
        ]
