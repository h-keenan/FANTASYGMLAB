from pathlib import Path
from unittest.mock import patch

import pandas as pd

import app
from scripts.audit_founder_beta_performance import inventory


ROOT = Path(__file__).resolve().parents[1]


def test_preferences_leave_common_startup_and_load_at_dashboard_boundary():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    startup = source.split("def main():", 1)[1].split("# SIDEBAR", 1)[0]
    dashboard = source.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]

    assert "refresh_authenticated_preferences(" not in startup
    assert "user_preference_loading" in dashboard
    assert "refresh_authenticated_preferences(" in dashboard


def test_workspace_shell_context_does_not_build_intelligence_or_trust():
    summary = pd.DataFrame(
        [
            {
                "roster_id": 1,
                "team_name": "Fixture Team",
                "power_score": 100,
                "franchise_score": 100,
            }
        ]
    )
    display = summary.assign(power_rank=1, franchise_rank=1)
    builder = getattr(app.cached_league_shell_context, "__wrapped__", app.cached_league_shell_context)

    with (
        patch.object(app, "cached_team_direction_summary", return_value=summary),
        patch.object(app, "cached_draft_pick_assets", return_value=[]),
        patch.object(app, "build_draft_capital_summary", return_value=pd.DataFrame()),
        patch.object(app, "build_league_display_frame", return_value=display),
        patch.object(app, "get_league_roster_profiles", return_value={"1": {"team_name": "Fixture Team"}}),
        patch.object(app, "_enrich_league_display_with_roster_profiles", side_effect=lambda frame, _profiles: frame),
        patch.object(app, "add_league_detail_ranks", side_effect=lambda frame: frame),
        patch.object(app, "cached_league_intelligence_frame") as intelligence,
        patch.object(app, "build_trade_trust_context") as trust,
    ):
        context = builder(pd.DataFrame({"player_id": ["p1"]}), "fixture", "value_score", {})

    assert context["league_detail_ranks"].equals(display)
    assert context["roster_profiles"]["1"]["team_name"] == "Fixture Team"
    intelligence.assert_not_called()
    trust.assert_not_called()


def test_route_level_performance_boundary_covers_every_founder_beta_workspace():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'f"page_route_total_{_safe_text(current_page, \'unknown\')}"' in source
    for route in ("dashboard", "my_team", "trade_hub", "waivers"):
        assert f'current_page == "{route}"' in source
    assert 'current_page in {"rankings", "teams", "draft_summary"' in source


def test_static_performance_inventory_is_deterministic_and_complete():
    first = inventory()
    second = inventory()

    assert first == second
    assert first["cache_count"] >= 30
    assert first["explicit_rerun_count"] >= 1
    assert "workspace_shell_context_generation" in first["timing_labels"]
    assert "user_preference_loading" in first["timing_labels"]


def test_mobile_visual_harness_covers_waivers_in_addition_to_existing_pages():
    validation = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")

    assert '"waivers": ("Waiver Priorities", "Available Targets")' in validation
    assert '"waivers": _waivers' in harness


def test_reset_preference_remains_lazy_and_idempotent():
    account_ui = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")
    preferences = (ROOT / "modules" / "user_preferences.py").read_text(encoding="utf-8")

    assert 'disabled=not onboarding_hidden' not in account_ui
    assert 'if "account_user_settings" not in session_state:' in preferences
    assert "fetch_user_settings(" in preferences
