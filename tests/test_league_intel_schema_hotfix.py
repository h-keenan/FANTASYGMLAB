"""Regression: League Overview must not KeyError when summary frames lack archetype_label."""

from unittest.mock import patch

import pandas as pd
import pytest

import app
from modules.team_eval import refine_team_directions


def _context_builder():
    return getattr(app.cached_league_context, "__wrapped__", app.cached_league_context)


def _shell_builder():
    return getattr(app.cached_league_shell_context, "__wrapped__", app.cached_league_shell_context)


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


def test_schema_guard_fails_soft_when_archetype_missing():
    summary = _summary_frame()
    guarded = app.select_league_frame_columns(
        summary,
        [
            "power_rank",
            "team_name",
            "archetype_label",
            "strategy_display",
        ],
        required=["archetype_label", "team_name"],
    )
    assert guarded is None

    metrics = app.select_league_frame_columns(
        summary,
        [
            "power_rank",
            "team_name",
            "archetype_label",
            "strategy_display",
        ],
        required=["team_name", "power_rank"],
    )
    assert metrics is not None
    assert "team_name" in metrics.columns
    assert "archetype_label" not in metrics.columns


def test_full_intelligence_path_includes_real_archetype_label():
    summary = _summary_frame()
    raw_intel = summary.copy()
    # Minimal columns refine_team_directions needs to classify.
    for column, value in {
        "rank": [1, 2],
        "current_roster_rank": [1, 2],
        "current_roster_score": [100, 80],
        "starter_rank": [1, 2],
        "starter_score": [100, 80],
        "bench_rank": [1, 2],
        "bench_score": [50, 40],
        "age_rank": [2, 1],
        "avg_age": [27.0, 24.0],
        "draft_capital_rank": [2, 1],
        "draft_capital": [40, 80],
    }.items():
        raw_intel[column] = value

    shell = {
        "team_direction_summary": summary,
        "draft_pick_assets": [],
        "draft_capital_summary": pd.DataFrame(),
        "league_display_frame": summary,
        "league_detail_ranks": summary,
        "roster_profiles": {},
    }
    refined_direction = refine_team_directions(raw_intel)

    with (
        patch.object(
            app,
            "cached_league_core_context",
            return_value={
                "league_summary": summary,
                "league_detail_ranks": summary,
                "league_intelligence_frame": raw_intel,
            },
        ),
        patch.object(app, "cached_league_shell_context", return_value=shell),
        patch.object(app, "cached_league_intelligence_frame") as intelligence_builder,
        patch.object(app, "cached_team_direction_summary", return_value=refined_direction),
        patch.object(app, "get_rosters", return_value=[]),
        patch.object(app, "build_trade_trust_context", return_value=None),
        patch.object(app, "get_league", return_value={}),
        patch.object(app.league_maturity, "build_league_evidence", return_value={}),
    ):
        context = _context_builder()(
            pd.DataFrame({"player_id": ["p1"]}),
            "fixture",
            "value_score",
            {},
            include_intelligence=True,
            include_roster_map=False,
            include_trust=False,
            include_maturity=False,
        )

    intelligence_builder.assert_not_called()
    intel = context["league_intelligence_frame"]
    assert not intel.empty
    assert "archetype_label" in intel.columns
    assert intel["archetype_label"].astype(str).str.len().gt(0).all()
    assert "archetype_label" in context["team_direction_summary"].columns

    archetypes = app.select_league_frame_columns(
        intel,
        ["team_name", "archetype_label", "archetype_explanation"],
        required=["archetype_label", "team_name"],
    )
    assert archetypes is not None


def test_shell_summary_path_never_builds_direction_or_intelligence():
    summary = _summary_frame()
    display = summary.copy()

    with (
        patch.object(app, "cached_league_summary", return_value=summary),
        patch.object(app, "cached_team_direction_summary") as direction,
        patch.object(app, "cached_draft_pick_assets", return_value=[]),
        patch.object(app, "build_draft_capital_summary", return_value=pd.DataFrame()),
        patch.object(app, "build_league_display_frame", return_value=display),
        patch.object(app, "get_league_roster_profiles", return_value={}),
        patch.object(
            app,
            "_enrich_league_display_with_roster_profiles",
            side_effect=lambda frame, _profiles: frame,
        ),
        patch.object(app, "add_league_detail_ranks", side_effect=lambda frame: frame),
        patch.object(app, "cached_league_intelligence_frame") as intelligence,
        patch.object(app, "refine_team_directions") as refine,
    ):
        context = _shell_builder()(
            pd.DataFrame({"player_id": ["p1"]}),
            "fixture",
            "value_score",
            {},
        )

    direction.assert_not_called()
    intelligence.assert_not_called()
    refine.assert_not_called()
    assert "archetype_label" not in context["team_direction_summary"].columns


def test_reduced_context_keeps_intelligence_empty_without_crash():
    summary = _summary_frame()
    shell = {
        "team_direction_summary": summary,
        "draft_pick_assets": [],
        "draft_capital_summary": pd.DataFrame(),
        "league_display_frame": summary,
        "league_detail_ranks": summary,
        "roster_profiles": {},
    }
    with (
        patch.object(app, "cached_league_core_context", return_value={"league_summary": summary}),
        patch.object(app, "cached_league_shell_context", return_value=shell),
        patch.object(app, "cached_league_intelligence_frame") as intelligence,
        patch.object(app, "cached_team_direction_summary") as direction,
        patch.object(app, "refine_team_directions") as refine,
    ):
        context = _context_builder()(
            pd.DataFrame({"player_id": ["p1"]}),
            "fixture",
            "value_score",
            {},
            include_intelligence=False,
            include_roster_map=False,
            include_trust=False,
            include_maturity=False,
        )

    intelligence.assert_not_called()
    direction.assert_not_called()
    refine.assert_not_called()
    assert context["league_intelligence_frame"].empty
    assert app.select_league_frame_columns(
        context["league_intelligence_frame"],
        ["archetype_label"],
        required=["archetype_label"],
    ) is None


def test_startup_critical_path_still_defers_direction_summary():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    shell_start = source.index("def _build_shell_chrome_bundle()")
    shell_end = source.index(
        "shell_chrome_signature = prepared_player_frame.build_shell_signature",
        shell_start,
    )
    shell = source[shell_start:shell_end]
    assert "cached_team_direction_summary(" not in shell
    assert "cached_league_intelligence_frame(" not in shell

    dismiss = source.index('runtime_trace.mark("first_usable_paint")')
    # Route bodies that need full intelligence run after first-usable dismiss.
    league_overview = source.index(
        "get_shared_league_context(include_trust=False)",
        dismiss,
    )
    my_team = source.index("league_context_my_team = get_shared_league_context()", dismiss)
    assert league_overview > dismiss
    assert my_team > dismiss
