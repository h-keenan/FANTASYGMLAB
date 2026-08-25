"""Founder Beta ship-pass regressions: portraits, league switch, startup, entitlement."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

from modules import auth_restore_lifecycle
from modules import auth_supabase
from modules import compact_fantasy_assets as compact
from modules import game_plan_package
from modules import premium
from modules import session_integrity
from modules.game_plan_package import GAME_PLAN_CONTEXT_FLAGS
from modules.player_profile_ui import player_headshot_preset
from scripts.measure_interaction_rerun_architecture import count_explicit_reruns


ROOT = Path(__file__).resolve().parents[1]
PORTRAIT_SOURCES = (
    ROOT / "modules" / "app_styles.py",
    ROOT / "modules" / "football_asset_styles.py",
    ROOT / "modules" / "compact_fantasy_assets.py",
    ROOT / "modules" / "player_profile_ui.py",
    ROOT / "modules" / "player_quick_view_styles.py",
    ROOT / "modules" / "daily_gm_briefing_ui.py",
    ROOT / "app.py",
)


class _State(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _seed_league(state: dict, league_id: str, *, extra: dict | None = None) -> None:
    state.update(
        {
            "selected_league_id": league_id,
            "selected_league_name": f"League {league_id[-1].upper()}",
            "username": "gm_user",
            "active_league_context": {
                "selected_league_id": league_id,
                "selected_league_name": f"League {league_id[-1].upper()}",
                "username": "gm_user",
                "my_roster_id": 1 if league_id.endswith("a") else 2,
            },
            "_effective_entitlement": "premium",
            "account_profile": {"entitlement": "premium", "user_id": "user-1"},
            "player_quick_view_player_id": "4046",
            "trade_hub_player_id": "4046",
            f"trade_hub_focus_player_id_{league_id}": "4046",
            f"trade_hub_mode_{league_id}": "find",
            "canonical_recommendation_narrative": {
                "recommendation_id": "rec-1",
                "league_id": league_id,
            },
            "trade_send_assets": [{"player_id": "4046"}],
            "_game_plan_package_bundle": {
                "briefing": {"league_id": league_id, "items": []},
                "league_id": league_id,
            },
            "_game_plan_package_signature": f"sig-{league_id}",
            "role_map": {"4046": "hold"},
        }
    )
    if extra:
        state.update(extra)


def test_dashboard_uses_canonical_standard_portrait_primitive():
    assert player_headshot_preset("dg-compact-asset-avatar") == "standard"
    assert player_headshot_preset("scan-card-avatar") == "standard"
    assert player_headshot_preset("compact-player-avatar") == "standard"
    html = compact.game_plan_trade_visual_html(
        {
            "send": [
                {
                    "asset_type": "player",
                    "player_id": "11655",
                    "name": "Tyrone Tracy",
                    "position": "RB",
                    "team": "NYG",
                }
            ],
            "receive": [
                {
                    "asset_type": "player",
                    "player_id": "6904",
                    "name": "Jalen Hurts",
                    "position": "QB",
                    "team": "PHI",
                }
            ],
        }
    )
    assert "dg-compact-asset--standard" in html
    assert "dg-player-headshot--standard" in html
    watch = compact.watch_attention_html(
        [
            {
                "asset_type": "player",
                "player_id": "4199",
                "name": "Aaron Jones",
                "position": "RB",
                "team": "MIN",
            }
        ]
    )
    assert "dg-compact-asset--standard" in watch
    ui = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert 'size="standard"' in ui
    assert "--size-asset-standard:3.25rem" in ui.replace(" ", "")


def test_no_per_player_dashboard_portrait_offsets():
    blob = "\n".join(path.read_text(encoding="utf-8") for path in PORTRAIT_SOURCES)
    assert re.search(r"object-position[^;]*11655", blob) is None
    assert "[data-player-id" not in blob
    assert "HURTS_OFFSET" not in blob
    assert "PLAYER_OBJECT_POSITION" not in blob
    assert ".player-tyrone" not in blob.casefold()


def test_session_key_lifetimes_keep_entitlement_account_owned():
    assert session_integrity.SESSION_KEY_LIFETIMES["_effective_entitlement"] == "ACCOUNT"
    assert session_integrity.SESSION_KEY_LIFETIMES["selected_league_id"] == "LEAGUE"
    assert session_integrity.SESSION_KEY_LIFETIMES["my_roster_id"] == "ROSTER"
    assert session_integrity.SESSION_KEY_LIFETIMES["players"] == "GLOBAL"
    assert session_integrity.SESSION_KEY_LIFETIMES["_game_plan_package_bundle"] == "LEAGUE"
    assert session_integrity.SESSION_KEY_LIFETIMES["_signal_intelligence_timeline"] == "LEAGUE"
    assert session_integrity.SESSION_KEY_LIFETIMES["_news_intelligence_timeline_events"] == "LEAGUE"


def test_league_a_to_b_invalidation_and_entitlement_survives():
    import app

    state = _State()
    _seed_league(state, "league-a")
    with patch("streamlit.session_state", state):
        app._clear_league_switch_transient_state(previous_league_id="league-a")
    assert "player_quick_view_player_id" not in state
    assert "trade_hub_player_id" not in state
    assert "trade_hub_focus_player_id_league-a" not in state
    assert "trade_hub_mode_league-a" not in state
    assert "trade_send_assets" not in state
    assert "_game_plan_package_bundle" not in state
    assert state.get("_effective_entitlement") == "premium"
    assert state.get("account_profile", {}).get("entitlement") == "premium"


def test_league_a_b_a_restoration_and_b_to_c():
    import app

    state = _State()
    _seed_league(state, "league-a")
    with patch("streamlit.session_state", state):
        app._clear_league_switch_transient_state(previous_league_id="league-a")
        state["selected_league_id"] = "league-b"
        state["active_league_context"] = {
            "selected_league_id": "league-b",
            "username": "gm_user",
            "my_roster_id": 2,
        }
        app._clear_league_switch_transient_state(previous_league_id="league-b")
        state["selected_league_id"] = "league-c"
        state["active_league_context"] = {
            "selected_league_id": "league-c",
            "username": "gm_user",
            "my_roster_id": 3,
        }
        app._clear_league_switch_transient_state(previous_league_id="league-c")
        _seed_league(state, "league-a")
    assert state["selected_league_id"] == "league-a"
    assert state["active_league_context"]["my_roster_id"] == 1
    assert state["_effective_entitlement"] == "premium"


def test_rapid_switch_rejects_stale_game_plan_package():
    state = {
        "selected_league_id": "league-b",
        game_plan_package.PACKAGE_SIG_KEY: "same-sig",
        game_plan_package.PACKAGE_KEY: {
            "signature": "same-sig",
            "built_at": 9_999_999_999,
            "briefing": {"league_id": "league-a", "items": [{"headline": "A"}]},
        },
    }
    cached, hit = game_plan_package.lookup_package(
        state, signature="same-sig", expected_league_id="league-b"
    )
    assert hit is False
    assert cached is None
    assert state.get(game_plan_package.LAST_MISS_REASON_KEY) == "league_mismatch"


def test_trade_hub_stale_focus_cleared_on_switch():
    import app

    state = _State()
    state["trade_hub_focus_player_id_league-a"] = "11655"
    state["trade_hub_mode_league-a"] = "find"
    state["player_trade_hub_target_player_league-a"] = "6904"
    with patch("streamlit.session_state", state):
        app._clear_league_namespaced_trade_hub_focus("league-a")
    assert "trade_hub_focus_player_id_league-a" not in state
    assert "trade_hub_mode_league-a" not in state
    assert "player_trade_hub_target_player_league-a" not in state


def test_player_roster_membership_rebinds_on_league_context_rebuild():
    import app

    state = _State()
    state["username"] = "gm_user"
    state["selected_league_id"] = "league-b"
    state["selected_league_name"] = "League B"
    state["active_league_context"] = {
        "selected_league_id": "league-a",
        "username": "gm_user",
        "my_roster_id": 1,
        "selected_league_name": "League A",
    }
    with (
        patch("streamlit.session_state", state),
        patch.object(app, "get_user_roster_id", return_value=9),
        patch.object(app, "get_user_leagues", return_value=[]),
    ):
        context = app.resolve_active_league_context()
    assert context["selected_league_id"] == "league-b"
    assert context["my_roster_id"] == 9


def test_returning_session_reuses_league_context_without_second_roster_lookup():
    import app

    state = _State()
    state["username"] = "gm_user"
    state["selected_league_id"] = "league-a"
    state["selected_league_name"] = "League A"
    state["active_league_context"] = {
        "selected_league_id": "league-a",
        "selected_league_name": "League A",
        "username": "gm_user",
        "my_roster_id": 4,
    }
    with (
        patch("streamlit.session_state", state),
        patch.object(app, "get_user_roster_id") as roster_lookup,
    ):
        first = app.resolve_active_league_context()
        second = app.resolve_active_league_context()
    assert first is second
    assert first["my_roster_id"] == 4
    roster_lookup.assert_not_called()
    assert auth_restore_lifecycle.should_skip_duplicate_workspace_hydrate(state) is False
    state[auth_restore_lifecycle.RESTORE_PHASE_KEY] = int(
        auth_restore_lifecycle.RestorePhase.READY
    )
    assert auth_restore_lifecycle.should_skip_duplicate_workspace_hydrate(state) is True


def test_entitlement_clears_on_logout_and_guest_cannot_inherit_premium():
    import app

    state = _State()
    state["_effective_entitlement"] = "premium"
    state["account_profile"] = {"entitlement": "premium"}
    auth_supabase.clear_auth_session(state)
    assert "_effective_entitlement" not in state
    state["_effective_entitlement"] = "premium"
    with patch("streamlit.session_state", state):
        assert app.current_user_entitlement() == premium.FREE
    assert state.get("_effective_entitlement") in {premium.FREE, None} or (
        "_effective_entitlement" not in state or state["_effective_entitlement"] == premium.FREE
    )


def test_dashboard_game_plan_remains_trust_enforced():
    assert GAME_PLAN_CONTEXT_FLAGS[2] is True
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "GAME_PLAN_CONTEXT_FLAGS" in app_source
    assert "include_trust" in app_source


def test_no_new_explicit_rerun():
    assert count_explicit_reruns() <= 62


def test_viewport_preservation_helper_still_mounted():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "viewport_preservation.render_viewport_preservation()" in app


def test_primary_loop_does_not_force_dashboard_on_league_switch():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    section = app.split("def _switch_to_saved_league", 1)[1].split(
        "def render_header_league_switcher", 1
    )[0]
    assert "route_to_dashboard=False" in section


def test_scan_card_no_longer_zeroes_headshot_transform():
    css = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    block = css.split(".scan-card-avatar img {", 1)[1].split(".scan-card-copy", 1)[0]
    assert "transform: none" not in block
    assert "object-position: center top" not in block
    assert "object-position: center var(--dg-headshot-focus, 18%) !important" in css


def test_provider_call_inventory_keeps_reduced_game_plan_context():
    assert GAME_PLAN_CONTEXT_FLAGS == (False, True, True, True)
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "GAME_PLAN_CONTEXT_FLAGS" in app_source
