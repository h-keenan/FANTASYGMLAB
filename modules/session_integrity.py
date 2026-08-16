"""Production session integrity — account/league-bound transient cleanup.

Presentation and state-correctness only. Does not change football logic,
rankings, valuations, recommendation generation/ordering, Trust, Sleeper,
Stripe, Supabase schema, authentication rules, entitlements, or business rules.
"""

from __future__ import annotations

from typing import Any, MutableMapping

from modules import prepared_player_frame
from modules import recommendation_lifecycle
from modules import session_isolation
from modules import trade_hub_first_useful

# Overlay / recommendation / workflow state that must not survive logout or
# account switch. League switch already clears most of these via app.py.
ACCOUNT_BOUND_TRANSIENT_KEYS: tuple[str, ...] = (
    "player_quick_view_player_id",
    "player_quick_view_source_label",
    "player_quick_view_source_note",
    "player_quick_view_status_label",
    "player_detail_player_id",
    "player_detail_return_page",
    "player_detail_source_label",
    "selected_team_roster_id",
    "selected_team_name",
    "_pending_selected_team_roster_id",
    "role_map",
    "trade_hub_player_id",
    "canonical_recommendation_narrative",
    "executive_workflow_return",
    "dg_trade_detail_active",
    "dg_trade_detail_view",
    "dg_trade_detail_player",
    "_identity_established",
    "_effective_entitlement",
    "leagues_for_user",
    "leagues_for_user_username",
    "last_league_option_id",
    "league_lookup_attempted",
    "league_lookup_status",
    "_pending_platform_route",
    "_pending_platform_route_source",
    "_mobile_destination_sheet_open",
    "account_resume_notice",
    "_persisted_account_context_fingerprint",
    "_canonical_rank_context_key",
    "_cached_live_draft_active",
    "_live_draft_discovery_at",
    "_live_draft_discovery_league_id",
    prepared_player_frame.FRAME_KEY,
    prepared_player_frame.SIGNATURE_KEY,
    prepared_player_frame.SHELL_BUNDLE_KEY,
    prepared_player_frame.SHELL_SIGNATURE_KEY,
    prepared_player_frame.SHARED_CONTEXT_KEY,
    trade_hub_first_useful.PRESENTATION_CACHE_KEY,
    trade_hub_first_useful.STRATEGY_FRAME_CACHE_KEY,
    recommendation_lifecycle.LIFECYCLE_CONTEXT_FINGERPRINT_KEY,
    recommendation_lifecycle.LIFECYCLE_INVENTORY_SIGNATURES_KEY,
    recommendation_lifecycle.LIFECYCLE_BRIEFING_SIGNATURE_KEY,
    recommendation_lifecycle.LIFECYCLE_PRIOR_TOP_RECOMMENDATION_KEY,
    recommendation_lifecycle.ROSTER_STATE_VERSION_SESSION_KEY,
    "_decision_change_history_events",
    "_decision_change_history_prior_snapshot",
    "_decision_change_history_account_scope",
    "_decision_change_history_league_scope",
    "_decision_memory_cache_events",
    "_decision_memory_cache_league",
    "_decision_memory_hydrated_league",
    "_decision_memory_unavailable",
    "_gm_targets_cache_ids",
    "_gm_targets_cache_rows",
    "_gm_targets_cache_league",
    "_gm_targets_hydrated_league",
    "_gm_targets_unavailable",
    "_premium_checkout_intent",
    "_premium_resume_checkout",
    "_premium_run_founder_checkout",
    session_isolation.GUEST_LEAGUE_ORIGIN_KEY,
    session_isolation.ISOLATION_DIAGNOSTICS_KEY,
)

TRADE_ANALYZER_PACKAGE_KEYS: tuple[str, ...] = (
    "trade_send_assets",
    "trade_receive_assets",
    "trade_receive_notice",
    "trade_asset_score_field",
    "trade_asset_strategy_context",
    "trade_send_search_query",
    "trade_receive_search_query",
    "_reset_trade_send_search_query",
    "_reset_trade_receive_search_query",
    "trade_send_asset_filter",
    "trade_receive_asset_filter",
    "trade_send_pick_year",
    "trade_send_pick_round",
    "trade_receive_pick_year",
    "trade_receive_pick_round",
    "trade_receive_partner",
    "trade_partner_roster_id",
    "trade_analyzer_analyzed_signature",
    "trade_analyzer_result_payload",
    "trade_analyzer_last_partner",
    "trade_receive_adder_open",
    "trade_send_adder_open",
    "trade_analyzer_add_feedback",
    "toa_catalog_key",
    "toa_catalog_players_me",
    "toa_catalog_picks_me",
    "toa_catalog_players_partner",
    "toa_catalog_picks_partner",
    "toa_last_matchup_key",
    "toa_receive_kind",
    "toa_send_kind",
    "toa_receive_pos",
    "toa_send_pos",
    "toa_assembly_notice",
)

# League-scoped Trade Hub focus / mode namespaces.
TRADE_HUB_NAMESPACE_PREFIXES: tuple[str, ...] = (
    "trade_hub_focus_player_id_",
    "trade_hub_focus_mode_",
    "trade_hub_home_source_label_",
    "trade_hub_home_source_note_",
    "trade_hub_focus_recommendation_id_",
    "trade_hub_focus_recommendation_status_",
    "trade_hub_mode_",
    "player_trade_hub_mode_",
    "player_trade_hub_target_player_",
)

# Caches keyed by draft / league / player that bind to a prior workspace.
WORKSPACE_CACHE_PREFIXES: tuple[str, ...] = (
    "live_draft_last_state_",
    "live_draft_state_signature_",
    "live_draft_last_picks_",
    "live_draft_previous_ranks_",
    "live_draft_previous_team_ranks_",
    "draft_assistant_",
    "untouchables_ms_",
    "roster_news_",
    "deferred_section_ready__",
    "player_dossier_history_",
    "_dg_dashboard_orientation_",
)


def clear_trade_analyzer_package(state: MutableMapping[str, Any]) -> None:
    """Drop Trade Analyzer package state so it cannot bleed across leagues."""

    for key in TRADE_ANALYZER_PACKAGE_KEYS:
        state.pop(key, None)


def clear_trade_hub_namespaces(
    state: MutableMapping[str, Any],
    *,
    league_id: str = "",
) -> None:
    """Clear Trade Hub namespaced keys for one league, or all when league_id empty."""

    league_key = str(league_id or "").strip()
    if league_key:
        for prefix in TRADE_HUB_NAMESPACE_PREFIXES:
            state.pop(f"{prefix}{league_key}", None)
        return
    for key in list(state.keys()):
        text = str(key)
        if any(text.startswith(prefix) for prefix in TRADE_HUB_NAMESPACE_PREFIXES):
            state.pop(key, None)


def clear_account_bound_transient_state(state: MutableMapping[str, Any]) -> None:
    """Clear overlays, recommendation, workflow, and identity caches for account hygiene.

    Does not clear auth tokens / durable-auth bridge keys — callers that need a
    full logout must also clear auth via clear_auth_session.
    """

    for key in ACCOUNT_BOUND_TRANSIENT_KEYS:
        state.pop(key, None)
    clear_trade_analyzer_package(state)
    clear_trade_hub_namespaces(state)
    try:
        from modules import game_plan_package

        game_plan_package.clear_process_game_plan_packages()
    except Exception:
        pass
    try:
        from modules import notification_center as _notification_center

        _notification_center.clear_notification_session_state(state)
    except Exception:
        state.pop("activity_inbox_snapshot", None)
        state.pop("notification_center_read_ids", None)
        state.pop("notification_center_account_scope", None)
    recommendation_lifecycle.clear_lifecycle_session_state(state)
    trade_hub_first_useful.clear_trade_hub_computation_caches(state)
    try:
        from modules import game_plan_package

        game_plan_package.clear_game_plan_package(state)
    except Exception:
        state.pop("_game_plan_package_bundle", None)
        state.pop("_game_plan_package_signature", None)
    try:
        from modules import game_plan_truth_canon

        game_plan_truth_canon.clear_canon(state)
    except Exception:
        state.pop("_game_plan_truth_canon", None)
    try:
        from modules import daily_gm_briefing

        daily_gm_briefing.clear_compose_memo()
    except Exception:
        pass
    try:
        from modules import decision_memory

        decision_memory.clear_decision_memory_session(state)
    except Exception:
        state.pop("_decision_memory_cache_events", None)
        state.pop("_decision_memory_cache_league", None)
        state.pop("_decision_memory_hydrated_league", None)
        state.pop("_decision_memory_unavailable", None)
    try:
        from modules import gm_targets

        gm_targets.clear_gm_targets_session(state)
    except Exception:
        state.pop("_gm_targets_cache_ids", None)
        state.pop("_gm_targets_cache_rows", None)
        state.pop("_gm_targets_cache_league", None)
        state.pop("_gm_targets_hydrated_league", None)
        state.pop("_gm_targets_unavailable", None)
    try:
        from modules import launch_analytics

        launch_analytics.clear_analytics_session(state)
    except Exception:
        pass
    try:
        from modules import interaction_latency

        interaction_latency.clear_interaction_memos(state)
    except Exception:
        state.pop("_prepared_player_fit_contexts", None)
    for key in list(state.keys()):
        text = str(key)
        if any(text.startswith(prefix) for prefix in WORKSPACE_CACHE_PREFIXES):
            state.pop(key, None)
