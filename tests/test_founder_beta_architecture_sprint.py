from pathlib import Path
from unittest.mock import patch

import pandas as pd

import app
from modules import deferred_rendering
from modules import workspace_context


ROOT = Path(__file__).resolve().parents[1]


def _context_builder():
    return getattr(app.cached_league_context, "__wrapped__", app.cached_league_context)


def _summary() -> pd.DataFrame:
    return pd.DataFrame(
        [{"roster_id": 1, "team_name": "Fixture", "power_score": 100}]
    )


def test_reduced_route_context_skips_secondary_intelligence_trust_and_maturity():
    summary = _summary()
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
        patch.object(app, "get_rosters") as rosters,
        patch.object(app, "build_trade_trust_context") as trust,
        patch.object(app.league_maturity, "build_league_evidence", return_value={}) as maturity,
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
    rosters.assert_not_called()
    trust.assert_not_called()
    # One call initializes the stable empty result before route-specific work.
    assert maturity.call_count == 1
    assert context["league_intelligence_frame"].empty
    assert context["roster_player_map"] == {}
    assert context["trade_trust_context"] is None


def test_default_context_preserves_full_analysis_contract():
    summary = _summary()
    intelligence_frame = summary.assign(power_rank=1)
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
        patch.object(app, "cached_league_intelligence_frame", return_value=intelligence_frame) as intelligence,
        patch.object(app, "get_rosters", return_value=[{"roster_id": 1, "players": ["p1"]}]),
        patch.object(app, "build_trade_trust_context", return_value="trust") as trust,
        patch.object(app, "get_league", return_value={"league_id": "fixture"}),
        patch.object(app.league_maturity, "build_league_evidence", return_value={"phase": "regular"}) as maturity,
    ):
        context = _context_builder()(
            pd.DataFrame({"player_id": ["p1"]}),
            "fixture",
            "value_score",
            {},
        )

    intelligence.assert_called_once()
    trust.assert_called_once()
    assert maturity.call_count == 2
    assert context["league_intelligence_frame"].equals(intelligence_frame)
    assert context["roster_player_map"] == {"1": ("p1",)}
    assert context["trade_trust_context"] == "trust"
    assert context["league_maturity"] == {"phase": "regular"}


def test_deferred_sections_are_namespaced_and_restart_safe():
    state = {}
    dashboard = "dashboard_league_pulse_league-a"
    trade = "trade_hub_return_paths_league-a_roster-1"

    assert not deferred_rendering.is_deferred_section_ready(state, dashboard)
    deferred_rendering.mark_deferred_section_ready(state, dashboard)
    assert deferred_rendering.is_deferred_section_ready(state, dashboard)
    assert not deferred_rendering.is_deferred_section_ready(state, trade)
    deferred_rendering.reset_deferred_section(state, dashboard)
    assert not deferred_rendering.is_deferred_section_ready(state, dashboard)


def test_workspace_identity_is_frozen_and_normalized_once_per_rerun():
    identity = workspace_context.WorkspaceIdentity.from_mapping(
        {
            "username": " fixture-user ",
            "selected_league_id": " league-a ",
            "selected_league_name": " Fixture League ",
            "my_roster_id": 7,
        },
        platform="Sleeper",
    )

    assert identity.username == "fixture-user"
    assert identity.league_id == "league-a"
    assert identity.league_name == "Fixture League"
    assert identity.roster_id == 7
    assert identity.platform == "sleeper"
    assert identity.has_active_league
    assert identity.has_roster


def test_secondary_work_is_behind_explicit_interaction_boundaries():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert 'button_label="Load League Pulse"' in source
    assert 'button_label="Load detailed table"' in source
    assert 'button_label="Load Player Explainer"' in source
    assert 'button_label="Load player return search"' in source
    assert '"dashboard_deferred_league_pulse"' in source
    assert '"trade_hub_deferred_return_search"' in source


def test_reduced_context_is_used_only_by_routes_that_do_not_consume_deep_analysis():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert source.count("include_intelligence=False") == 2
    assert "league_context = get_shared_league_context(include_trust=False)" in source
    assert "trade_hub_context = get_shared_league_context()" in source
    assert "league_context_my_team = get_shared_league_context()" in source


def test_trade_board_pagination_uses_widget_callback_not_explicit_rerun():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index('if len(active_ideas) > visible_count:')
    end = source.index("else:\n                    trade_hub_ui.render_trade_hub_empty_state", start)
    pagination = source[start:end]

    assert "on_click=increment_session_counter" in pagination
    assert "st.rerun()" not in pagination
