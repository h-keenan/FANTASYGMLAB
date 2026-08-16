"""Game Plan package memo — fingerprint, hit≡miss, invalidation (#219)."""

from __future__ import annotations

from pathlib import Path

from modules import daily_gm_briefing
from modules import dashboard_workflow
from modules import game_plan_package
from modules import prepared_player_frame
from modules import session_integrity
from modules import startup_coordinator


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PACKAGE = (ROOT / "modules" / "game_plan_package.py").read_text(encoding="utf-8")


def _sample_briefing(*, entitlement: str = "free") -> daily_gm_briefing.DailyGmBriefing:
    briefing = dashboard_workflow.DashboardBriefing(
        immediate=(
            {
                "label": "Injury Alert",
                "value": "1 starter",
                "note": "Watch availability",
                "tone": "risk",
                "route_key": "my_team",
                "recommendation_id": "watch-injury-1",
            },
        ),
        primary={
            "label": "Trade Opportunity",
            "value": "Partner A",
            "note": "Best approved path",
            "tone": "opportunity",
            "route_key": "trade_hub",
            "recommendation_id": "trade-rec-1",
        },
        additional=(),
        intelligence=(
            {
                "label": "Waiver Target",
                "value": "FA WR",
                "note": "Need WR depth",
                "tone": "opportunity",
                "route_key": "waivers",
                "recommendation_id": "waiver-rec-1",
            },
        ),
    )
    return daily_gm_briefing.compose_daily_gm_briefing(
        briefing,
        league_id="L1",
        roster_id="R1",
        valuation_lens="value_score",
        scoring_format="PPR",
        entitlement=entitlement,
        context_fingerprint="fp-1",
    )


def test_game_plan_context_flags_disable_full_intelligence():
    flags = game_plan_package.GAME_PLAN_CONTEXT_FLAGS
    assert flags[0] is False
    assert flags[1] is True
    assert flags[2] is True
    assert flags[3] is True
    assert "GAME_PLAN_CONTEXT_FLAGS" in APP
    assert "include_intelligence=flags[0]" in APP


def test_dashboard_defers_league_context_until_package_miss():
    assert "league_context_loader=" in APP
    assert "_load_game_plan_league_context" in APP
    assert "game_plan_package_cache_lookup" in APP
    assert "lookup_package(" in APP
    assert "store_package(" in APP


def test_package_miss_equals_hit_recommendation_ids_and_order():
    daily_gm_briefing.clear_compose_memo()
    plan = _sample_briefing(entitlement="premium")
    zones = dashboard_workflow.DashboardBriefing(
        immediate=(
            {
                "label": "Injury Alert",
                "value": "1 starter",
                "note": "Watch availability",
                "tone": "risk",
                "route_key": "my_team",
                "recommendation_id": "watch-injury-1",
            },
        ),
        primary={
            "label": "Trade Opportunity",
            "value": "Partner A",
            "note": "Best approved path",
            "tone": "opportunity",
            "route_key": "trade_hub",
            "recommendation_id": "trade-rec-1",
        },
        additional=(),
        intelligence=(
            {
                "label": "Waiver Target",
                "value": "FA WR",
                "note": "Need WR depth",
                "tone": "opportunity",
                "route_key": "waivers",
                "recommendation_id": "waiver-rec-1",
            },
        ),
    )
    signature = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame-a",
        score_field="value_score",
        league_settings_key="settings-a",
        team_strategy="contend",
        role_items=(("p1", "Core"),),
        untouchables=("Alpha",),
        entitlement="premium",
        lifecycle_digest="fp-1",
        roster_state_version="rv1",
        startup_mode=False,
        pick_score_multiplier=1,
    )
    state: dict = {}
    miss_package = game_plan_package.store_package(
        state,
        signature=signature,
        package={
            "briefing": game_plan_package.serialize_daily_briefing(plan),
            "dashboard_briefing": game_plan_package.serialize_dashboard_briefing(zones),
            "snapshot_items": [{"label": "Record", "value": "3-1"}],
            "recommendation_ids": [item.recommendation_id for item in plan.items],
            "entitlement": "premium",
            "league_id": "L1",
            "roster_id": "R1",
            "account_user_id": "u1",
        },
    )
    hit_package, hit = game_plan_package.lookup_package(state, signature=signature)
    assert hit is True
    assert hit_package is not None
    restored = game_plan_package.briefing_from_package(hit_package)
    assert [item.recommendation_id for item in restored.items] == [
        item.recommendation_id for item in plan.items
    ]
    assert [item.category for item in restored.items] == [
        item.category for item in plan.items
    ]
    assert [item.headline for item in restored.items] == [
        item.headline for item in plan.items
    ]
    assert [item.destination for item in restored.items] == [
        item.destination for item in plan.items
    ]
    assert [item.presentation for item in restored.items] == [
        item.presentation for item in plan.items
    ]
    assert restored.entitlement == plan.entitlement
    assert miss_package["recommendation_ids"] == hit_package["recommendation_ids"]


def test_package_fingerprint_ignores_ui_chrome_noise():
    base = dict(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame-a",
        score_field="value_score",
        league_settings_key="settings-a",
        team_strategy="contend",
        role_items=(("p1", "Core"),),
        untouchables=(),
        entitlement="free",
        lifecycle_digest="fp-1",
        roster_state_version="rv1",
        startup_mode=False,
        pick_score_multiplier=1,
    )
    a = game_plan_package.build_package_signature(**base)
    b = game_plan_package.build_package_signature(**base)
    assert a == b
    changed_league = game_plan_package.build_package_signature(
        **{**base, "league_id": "L2"}
    )
    assert changed_league != a
    changed_roles = game_plan_package.build_package_signature(
        **{**base, "role_items": (("p1", "Bench"),)}
    )
    assert changed_roles != a
    # Fingerprint payload does not include alert/gm/pqv widget keys.
    assert "alerts" not in PACKAGE.casefold()
    assert "pqv" not in PACKAGE.casefold()


def test_league_and_account_hygiene_clear_package():
    state = {
        game_plan_package.PACKAGE_KEY: {"briefing": {}},
        game_plan_package.PACKAGE_SIG_KEY: "sig",
    }
    prepared_player_frame.clear_league_scoped_prepared_memos(state, previous_league_id="L1")
    assert game_plan_package.PACKAGE_KEY not in state
    state = {
        game_plan_package.PACKAGE_KEY: {"briefing": {}},
        game_plan_package.PACKAGE_SIG_KEY: "sig",
    }
    session_integrity.clear_account_bound_transient_state(state)
    assert game_plan_package.PACKAGE_KEY not in state


def test_compose_memo_hit_equals_miss():
    daily_gm_briefing.clear_compose_memo()
    first = _sample_briefing()
    second = _sample_briefing()
    assert [item.recommendation_id for item in first.items] == [
        item.recommendation_id for item in second.items
    ]
    assert first is second  # process memo returns identical object on hit


def test_free_premium_entitlement_membership_in_package():
    daily_gm_briefing.clear_compose_memo()
    free_plan = _sample_briefing(entitlement="free")
    premium_plan = _sample_briefing(entitlement="premium")
    assert free_plan.entitlement == "free"
    assert premium_plan.entitlement == "premium"
    free_sig = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame-a",
        entitlement="free",
    )
    premium_sig = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame-a",
        entitlement="premium",
    )
    assert free_sig != premium_sig


def test_startup_milestones_include_package_cache_events():
    labels = startup_coordinator.STARTUP_MILESTONE_LABELS
    assert "game_plan_package_cache_lookup" in labels
    assert "game_plan_context_ready" in labels
    assert "game_plan_package_ready" in labels
    assert "game_plan_trade_inventory_ready" in labels
    assert "game_plan_first_useful" in labels


def test_game_plan_first_useful_survives_startup_complete_origin():
    state: dict = {}
    from modules import auth_restore_lifecycle

    auth_restore_lifecycle.ensure_startup_session(state)
    origin = startup_coordinator.startup_session_origin(state)
    coordinator = startup_coordinator.StartupCoordinator(session_state=state, active=True)
    coordinator.complete()
    assert startup_coordinator.startup_session_origin(state) == origin
    # Contract: Dashboard useful marker still ties to preserved origin.
    useful = APP.index('data-fgl-dashboard-useful="1"')
    block = APP[useful : useful + 1400]
    assert "startup_session_origin" in block


def test_post_ready_package_hit_skips_trade_inventory_path():
    # Hit restores package; trade inventory only runs in the miss (else) branch.
    hit_marker = APP.index("game_plan_package_hit")
    else_branch = APP.index("else:", hit_marker)
    trade_call = APP.index("cached_dashboard_trade_headline(", else_branch)
    store_call = APP.index("game_plan_package.store_package(", else_branch)
    assert trade_call > else_branch
    assert store_call > trade_call
    assert "game_plan_package_ready" in APP[hit_marker:else_branch]
