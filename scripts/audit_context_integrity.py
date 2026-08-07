"""Run deterministic repository checks for cross-surface context integrity."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def audit() -> dict:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    main = source[source.index("def main():") :]
    set_selected = source[
        source.index("def set_selected_league(") : source.index(
            "def _open_mobile_destination_sheet",
            source.index("def set_selected_league("),
        )
    ]
    transient_keys = source[
        source.index("LEAGUE_SWITCH_TRANSIENT_STATE_KEYS") : source.index(
            "LEAGUE_SETTINGS_OVERRIDE_KEYS"
        )
    ]
    clearer = source[
        source.index("def _clear_league_switch_transient_state(") : source.index(
            "def _open_notification_destination("
        )
    ]
    notification_open = source[
        source.index("def _open_notification_item(") : source.index(
            "def _reset_selected_league_for_import("
        )
    ]
    feedback = source[
        source.index("def render_recommendation_feedback(") : source.index(
            "def render_recommendation_feedback("
        )
        + 1600
    ]
    home_route = source[
        source.index("def _open_home_command_route(") : source.index(
            "def _render_team_card_tap_grid("
        )
    ]
    my_roster_idx = feedback.index('active_context.get("my_roster_id")')
    browsed_idx = feedback.index('st.session_state.get("selected_team_roster_id")')
    checks = {
        "workspace_identity_resolved_once": main.count(
            "workspace_identity = workspace_context.WorkspaceIdentity.from_mapping("
        )
        == 1,
        "active_valuation_built_once": main.count(
            "df_players = valuation_archetype_service.apply_active_valuation("
        )
        == 1,
        "dashboard_uses_canonical_identity": "selected_league_id=selected_league_id"
        in main,
        "trade_hub_uses_shared_context": "trade_hub_context = get_shared_league_context()"
        in main,
        "waivers_use_canonical_league": "selected_league_id=selected_league_id"
        in main[main.index('if current_page == "waivers"') :],
        "news_is_league_scoped": 'roster_news_key = f"roster_news_{selected_league_id}_{my_roster_id}"'
        in main,
        "trade_entitlement_after_trust": main.index("ideas = enforce_cached_trade_ideas(")
        < main.index("trade_hub_ui.trade_hub_entitlement_presentation("),
        "league_switch_invalidates_active_context": 'st.session_state.pop("active_league_context", None)'
        in set_selected,
        "league_switch_clears_transient_via_canonical_owner": (
            "_clear_league_switch_transient_state(previous_league_id=previous_league_id)"
            in set_selected
        ),
        "league_switch_clears_role_map": '"role_map"' in transient_keys,
        "league_switch_resets_scoring_overrides": "_reset_league_settings_overrides()"
        in clearer,
        "notification_routes_clear_overlays": (
            "on_open_item=_open_notification_item" in source
            and "_clear_player_quick_view()" in notification_open
            and "trade_detail_navigation.close(" in notification_open
        ),
        "home_command_route_uses_session_league": (
            'league_id = _safe_text(st.session_state.get("selected_league_id")).strip()'
            in home_route
        ),
        "feedback_prefers_canonical_roster": my_roster_idx < browsed_idx,
    }
    return {"valid": all(checks.values()), "checks": checks}


def main() -> int:
    report = audit()
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
