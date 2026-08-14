"""P0 critical-path cache pass: auth restore, prepared frame, Game Plan."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from modules import account_ui
from modules import auth_restore_lifecycle
from modules import auth_supabase
from modules import game_plan_package
from modules import prepared_player_frame
from modules import session_integrity
from modules import performance
from scripts import measure_critical_path_caches


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def _auth_payload(user_id: str = "user-a") -> dict:
    return {
        "user": {"id": user_id, "email": f"{user_id}@example.com"},
        "user_id": user_id,
        "email": f"{user_id}@example.com",
        "access_token": f"access-{user_id}",
        "refresh_token": f"refresh-{user_id}",
        "expires_at": 9999999999,
        "token_type": "bearer",
    }


def test_returning_authenticated_skips_bridge_remount():
    state: dict = {}
    auth_supabase.apply_auth_payload(state, _auth_payload())
    with (
        patch.object(account_ui.st, "session_state", state),
        patch.object(account_ui, "AUTH_STORAGE_COMPONENT") as component,
        patch.object(account_ui.auth_supabase, "is_configured", return_value=True),
    ):
        result = account_ui.render_durable_auth_bridge(
            config={"url": "https://example.supabase.co", "anon_key": "anon"}
        )
    assert component.call_count == 0
    assert auth_restore_lifecycle.current_hydration_outcome(state).name == "AUTHENTICATED"
    assert state.get(auth_restore_lifecycle.AUTH_LAST_EVENT_KEY) == "SKIP_BRIDGE"
    assert result.get("identical") is True


def test_auth_callback_still_mounts_when_unsigned():
    state: dict = {}
    fake = MagicMock()
    fake.status = None
    fake.stored = None
    fake.auth_callback = None
    with (
        patch.object(account_ui.st, "session_state", state),
        patch.object(account_ui, "AUTH_STORAGE_COMPONENT", return_value=fake) as component,
        patch.object(account_ui.auth_supabase, "is_configured", return_value=True),
    ):
        result = account_ui.render_durable_auth_bridge(
            config={"url": "https://example.supabase.co", "anon_key": "anon"}
        )
    assert component.call_count == 1
    assert result.get("pending") is True
    assert auth_restore_lifecycle.current_hydration_outcome(state).name == "RESTORING"


def test_prepared_frame_fingerprint_stable_for_semantic_inputs():
    a = prepared_player_frame.build_frame_signature(
        public_fingerprint="pub",
        valuation_lens="value_score",
        score_field="value_score",
        league_settings_key="s1",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=10,
    )
    b = prepared_player_frame.build_frame_signature(
        public_fingerprint="pub",
        valuation_lens="value_score",
        score_field="value_score",
        league_settings_key="s1",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=10,
    )
    c = prepared_player_frame.build_frame_signature(
        public_fingerprint="pub",
        valuation_lens="value_score",
        score_field="value_score",
        league_settings_key="s2",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=10,
    )
    assert a == b
    assert a != c
    # No route/auth/viewport/timestamp fields.
    assert "dashboard" not in a
    assert "auth" not in a


def test_prepared_frame_invalidates_only_on_semantic_change():
    prepared_player_frame.clear_process_valued_ranked_frames()
    state: dict = {}
    builds = {"n": 0}
    sig = prepared_player_frame.build_frame_signature(
        public_fingerprint="pub",
        valuation_lens="value_score",
        score_field="value_score",
        league_settings_key="s1",
        scoring_format="PPR",
        scoring_supported=True,
        archetype_id="balanced",
        season="2025",
        row_count=3,
    )

    def builder():
        builds["n"] += 1
        return pd.DataFrame({"player_id": ["1", "2", "3"], "value_score": [1, 2, 3]})

    _, miss = prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=sig, builder=builder
    )
    _, hit = prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=sig, builder=builder
    )
    assert miss is False and hit is True
    assert builds["n"] == 1
    # UI-only session noise
    state["platform_nav_page"] = "trade_analyzer"
    state["dg_card_expanded"] = True
    _, still_hit = prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=sig, builder=builder
    )
    assert still_hit is True
    assert builds["n"] == 1


def test_shell_signature_has_no_time_bucket():
    sig = prepared_player_frame.build_shell_signature(
        frame_signature="frame",
        league_id="L1",
        roster_id="R1",
        score_field="value_score",
        league_settings_key="settings",
        startup_mode=False,
    )
    assert sig.count("|") == 5
    assert not any(part.isdigit() and int(part) > 1_000_000 for part in sig.split("|"))


def test_game_plan_fingerprint_stable_and_semantic():
    base = dict(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame",
        score_field="value_score",
        league_settings_key="settings",
        team_strategy="contender",
        entitlement="free",
        lifecycle_digest="life",
        roster_state_version="rv1",
        pick_score_multiplier=1.05,
    )
    a = game_plan_package.build_package_signature(**base)
    b = game_plan_package.build_package_signature(**base, startup_mode=True)
    c = game_plan_package.build_package_signature(**{**base, "team_strategy": "rebuild"})
    assert a == b  # startup_mode ignored
    assert a != c


def test_game_plan_process_hit_after_session_cold():
    game_plan_package.clear_process_game_plan_packages()
    state: dict = {}
    sig = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame",
        score_field="value_score",
        league_settings_key="settings",
        team_strategy="contender",
        entitlement="free",
        lifecycle_digest="life",
        roster_state_version="rv1",
        pick_score_multiplier=1.0,
    )
    game_plan_package.store_package(
        state,
        signature=sig,
        package={"briefing": {"items": [{"id": "1"}]}, "dashboard_briefing": {}, "snapshot_items": []},
    )
    # New session, same process
    state2: dict = {}
    cached, hit = game_plan_package.lookup_package(state2, signature=sig)
    assert hit is True
    assert cached is not None
    assert state2.get(game_plan_package.PACKAGE_SIG_KEY) == sig
    assert state2.get(game_plan_package.LAST_CACHE_STATUS_KEY) == "process_hit"


def test_dashboard_route_and_trade_analyzer_do_not_clear_caches_in_app():
    ta = APP.index('if current_page == "trade_analyzer":')
    block = APP[ta : APP.index('if current_page == "premium":', ta)]
    assert "clear_prepared_player_frame" not in block
    assert "clear_game_plan_package" not in block
    assert "clear_process_game_plan_packages" not in block


def test_a_b_a_reuses_process_package_and_isolates_session():
    game_plan_package.clear_process_game_plan_packages()
    prepared_player_frame.clear_process_valued_ranked_frames()
    state: dict = {}
    sig_a = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="A",
        roster_id="rA",
        prepared_frame_signature="frameA",
        score_field="value_score",
        league_settings_key="settings-A",
        team_strategy="contender",
        entitlement="free",
        lifecycle_digest="life-A",
        roster_state_version="rvA",
        pick_score_multiplier=1.0,
    )
    sig_b = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="B",
        roster_id="rB",
        prepared_frame_signature="frameB",
        score_field="value_score",
        league_settings_key="settings-B",
        team_strategy="rebuild",
        entitlement="free",
        lifecycle_digest="life-B",
        roster_state_version="rvB",
        pick_score_multiplier=1.0,
    )
    game_plan_package.store_package(
        state, signature=sig_a, package={"briefing": {"items": [{"id": "a"}]}}
    )
    prepared_player_frame.clear_league_scoped_prepared_memos(state, previous_league_id="A")
    assert game_plan_package.PACKAGE_KEY not in state
    cached_b, hit_b = game_plan_package.lookup_package(state, signature=sig_b)
    assert hit_b is False
    assert cached_b is None
    game_plan_package.store_package(
        state, signature=sig_b, package={"briefing": {"items": [{"id": "b"}]}}
    )
    prepared_player_frame.clear_league_scoped_prepared_memos(state, previous_league_id="B")
    cached_a, hit_a = game_plan_package.lookup_package(state, signature=sig_a)
    assert hit_a is True
    assert cached_a["briefing"]["items"][0]["id"] == "a"


def test_logout_clears_process_game_plan_packages():
    game_plan_package.clear_process_game_plan_packages()
    state = {"trade_send_assets": [1]}
    sig = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame",
        score_field="value_score",
        league_settings_key="settings",
        team_strategy="contender",
        entitlement="free",
        lifecycle_digest="life",
        roster_state_version="rv1",
        pick_score_multiplier=1.0,
    )
    game_plan_package.store_package(state, signature=sig, package={"briefing": {}})
    session_integrity.clear_account_bound_transient_state(state)
    prepared_player_frame.clear_prepared_player_frame(state)
    state2: dict = {}
    _, hit = game_plan_package.lookup_package(state2, signature=sig)
    assert hit is False


def test_debug_panel_exposes_critical_path_cache_diagnostics():
    state: dict = {
        auth_restore_lifecycle.AUTH_HYDRATION_OUTCOME_KEY: int(
            auth_restore_lifecycle.AuthHydrationOutcome.AUTHENTICATED
        ),
        auth_restore_lifecycle.AUTH_LAST_EVENT_KEY: "SKIP_BRIDGE",
        auth_restore_lifecycle.AUTH_HYDRATION_DIAG_KEY: {
            "event": "SKIP_BRIDGE",
            "rerun_reason": "already_authenticated",
        },
    }
    diag = performance._critical_path_cache_diagnostics(state)
    assert diag["auth_restore"]["outcome"] == "AUTHENTICATED"
    assert diag["auth_restore"]["event"] == "SKIP_BRIDGE"
    assert "prepared_frame" in diag
    assert "game_plan" in diag


def test_app_prefers_league_season_for_prepared_frame_signature():
    idx = APP.index("prepared_frame_signature = prepared_player_frame.build_frame_signature")
    window = APP[idx - 1200 : idx]
    assert "league_value_settings.get(\"season\")" in window
    # League season must be preferred before stats_season.
    league_pos = window.rfind("league_value_settings.get(\"season\")")
    stats_pos = window.rfind("st.session_state.get(\"stats_season\")")
    assert league_pos != -1 and stats_pos != -1
    assert league_pos < stats_pos


def test_measure_script_targets_pass():
    report = measure_critical_path_caches.run()
    assert report["all_targets_met"] is True
    assert report["targets"]["warm_prepared_hit"] is True
    assert report["targets"]["warm_game_plan_hit"] is True
    assert report["targets"]["process_warm_hits"] is True
    assert report["targets"]["aba_return_game_plan_hit"] is True
    assert report["targets"]["presentation_no_rebuild"] is True
