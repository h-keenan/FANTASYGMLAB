from __future__ import annotations

import re
from pathlib import Path

from modules.navigation_state import (
    SCROLL_RESET_PENDING_KEY,
    commit_destination_navigation,
    consume_scroll_reset,
    queue_destination_navigation,
    synchronize_destination_change,
)
from modules.player_profile_ui import avatar_html, player_headshot_preset
from modules.trade_hub_ui import trade_card_presentation_contract


ROOT = Path(__file__).resolve().parents[1]


def test_destination_change_requests_and_consumes_exactly_one_reset():
    state = {"platform_nav_page": "rankings"}
    assert queue_destination_navigation(
        state,
        "trade_hub",
        current_destination="rankings",
        source="gm_destination",
    )
    first = consume_scroll_reset(state, "trade_hub")
    assert first == {
        "token": 1,
        "destination": "trade_hub",
        "reason": "gm_destination",
        "mode": "reset",
    }
    assert consume_scroll_reset(state, "trade_hub") is None


def test_same_destination_local_rerun_preserves_scroll():
    state = {"platform_nav_page": "trade_hub"}
    assert not queue_destination_navigation(
        state,
        "trade_hub",
        current_destination="trade_hub",
        source="trade_hub_filter",
    )
    assert SCROLL_RESET_PENDING_KEY not in state


def test_callback_commit_sets_route_before_automatic_rerun():
    state = {"platform_nav_page": "dashboard"}

    assert commit_destination_navigation(
        state,
        "my_team",
        current_destination="dashboard",
        source="sidebar_destination",
    )

    assert state["platform_nav_page"] == "my_team"
    assert state["_pending_platform_route"] == "my_team"
    assert consume_scroll_reset(state, "my_team")["reason"] == "sidebar_destination"


def test_callback_commit_same_route_is_harmless_without_scroll_reset():
    state = {"platform_nav_page": "waivers"}

    assert not commit_destination_navigation(
        state,
        "waivers",
        current_destination="waivers",
        source="sidebar_destination",
    )

    assert state["platform_nav_page"] == "waivers"
    assert state["_pending_platform_route"] == "waivers"
    assert consume_scroll_reset(state, "waivers") is None


def test_rapid_callback_navigation_last_destination_wins_cleanly():
    state = {"platform_nav_page": "dashboard"}

    commit_destination_navigation(state, "my_team", source="sidebar_destination")
    commit_destination_navigation(state, "waivers", source="sidebar_destination")
    commit_destination_navigation(state, "rankings", source="sidebar_destination")

    assert state["platform_nav_page"] == "rankings"
    assert state["_pending_platform_route"] == "rankings"
    reset = consume_scroll_reset(state, "rankings")
    assert reset["destination"] == "rankings"
    assert reset["token"] == 3


def test_empty_callback_destination_does_not_corrupt_route_state():
    state = {"platform_nav_page": "dashboard"}

    assert not commit_destination_navigation(state, "  ")
    assert state == {"platform_nav_page": "dashboard"}


def test_navigation_entry_points_share_scroll_reset_contract():
    for source in (
        "gm_destination",
        "sidebar_destination",
        "dashboard_quick_action",
        "league_actions",
        "support_destination",
    ):
        state = {"platform_nav_page": "dashboard"}
        assert queue_destination_navigation(
            state,
            "trade_hub",
            current_destination="dashboard",
            source=source,
        )
        assert consume_scroll_reset(state, "trade_hub")["reason"] == source


def test_league_switch_preserves_route_and_forces_one_reset():
    state = {"platform_nav_page": "live_draft"}
    assert queue_destination_navigation(
        state,
        "live_draft",
        current_destination="live_draft",
        source="league_switch",
        force_scroll=True,
    )
    reset = consume_scroll_reset(state, "live_draft")
    assert reset["reason"] == "league_switch"
    assert consume_scroll_reset(state, "live_draft") is None


def test_canonical_destination_change_catches_query_and_back_navigation():
    state = {}
    assert not synchronize_destination_change(state, "dashboard")
    assert synchronize_destination_change(state, "waivers")
    assert consume_scroll_reset(state, "waivers")["reason"] == (
        "canonical_destination_change"
    )


def test_local_filters_expanders_and_polling_do_not_request_scroll():
    for interaction in (
        "trade_hub_filter",
        "trade_explanation",
        "quick_view",
        "live_draft_poll",
    ):
        state = {"platform_nav_page": "live_draft"}
        assert not queue_destination_navigation(
            state,
            "live_draft",
            current_destination="live_draft",
            source=interaction,
        )
        assert consume_scroll_reset(state, "live_draft") is None


def test_app_uses_one_navigation_scroll_reset_component():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count('st.components.v2.component(\n    "navigation_scroll_reset"') == 1
    assert "_render_navigation_scroll_reset(current_page, league_id=" in source
    assert 'source="gm_destination"' in source
    assert '"source": "sidebar_destination"' in source
    assert 'dashboard_quick_action' in source
    assert "_queue_platform_route(route_key, source=" in source
    assert 'reason="league_switch"' in source
    assert "scrollIntoView" not in source


def test_desktop_and_mobile_destination_controls_use_pre_rerun_callbacks():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    desktop = source.split('st.markdown("<div class=\'desktop-sidebar-nav\'>"', 1)[
        1
    ].split('st.markdown("</div>"', 1)[0]
    mobile = source.split("def render_mobile_destination_sheet", 1)[1].split(
        "def render_mobile_navigation_shell",
        1,
    )[0]

    assert "on_click=_commit_platform_destination" in desktop
    assert 'kwargs={"source": "sidebar_destination"}' in desktop
    assert "st.rerun()" not in desktop
    assert "on_click=_navigate_from_mobile_destination" in mobile
    assert "_commit_platform_destination(page_key, source=\"gm_destination\")" in source
    assert "st.rerun()" not in mobile


def test_unrelated_explicit_rerun_transitions_remain_present():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    # Legacy player_detail route is archived; profile opens go through Quick View.
    assert "open_player_quick_view(" in source
    assert '_queue_platform_route("player_detail")\n    st.rerun()' not in source
    assert '_queue_platform_route("trade_hub")\n    st.rerun()' in source
    assert "if auth_restore.get(\"restored\"):" in source
    assert "startup_critical_path.clear_auth_pending_wait(st.session_state)" in source
    # Auth restore continues into profile/league; durable save reruns only after
    # first-usable dismiss — not immediately after restore / league resume.
    auth_block = source[
        source.index('if auth_restore.get("restored"):') : source.index(
            'if auth_restore.get("pending")'
        )
    ]
    assert "st.rerun()" not in auth_block
    assert "_maybe_auto_resume_supabase_league()" in source
    assert "if _maybe_auto_resume_supabase_league():\n            st.rerun()" not in source


def test_trade_presentation_contract_preserves_assets_values_and_ordering():
    idea = {
        "send_assets": [{"player_id": "1", "name": "Send"}],
        "receive_assets": [
            {"player_id": "2", "name": "Receive"},
            {"asset_type": "pick", "label": "2027 Round 3"},
        ],
        "my_score": 5000,
        "their_score": 5488,
        "trade_gain": 488,
        "trade_confidence_label": "High",
        "trade_idea_score": 91.25,
    }
    before = {
        key: value.copy() if isinstance(value, list) else value
        for key, value in idea.items()
    }
    presentation = trade_card_presentation_contract(idea)
    assert presentation["send_assets"] == idea["send_assets"]
    assert presentation["receive_assets"] == idea["receive_assets"]
    assert presentation["send_score"] == 5000
    assert presentation["receive_score"] == 5488
    assert presentation["trade_gain"] == 488
    assert presentation["confidence"] == "High"
    assert presentation["ordering_score"] == 91.25
    assert idea == before


def test_trade_card_has_one_canonical_net_result_and_no_gain_circle():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    renderer = source[
        source.index("def render_trade_idea_card(") :
        source.index("\ndef render_trade_idea_player_actions(")
    ]
    assert 'class="trade-card-net-strip"' not in renderer
    assert "value_delta=delta_text" in renderer
    assert "trade-delta-stack" not in renderer
    assert "trade-card-value-strip" not in renderer
    assert "You receive" in renderer


def test_trade_detail_is_lazy_and_instrumented():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    renderer = source[
        source.index("def render_trade_idea_card(") :
        source.index("\ndef render_trade_idea_player_actions(")
    ]
    assert "TRADE_SUMMARY_TAP_COMPONENT(" in renderer
    assert "View trade" in renderer
    assert 'width="stretch"' in renderer
    assert "trade_summary_key(" in renderer
    assert "st.toggle(" not in renderer
    assert "if summary_clicked is True:" in renderer
    assert '"trade_hub_detail_modal"' in renderer
    assert "explanation_fields" in renderer
    assert "executive_trade_detail_html" in renderer
    assert "include_supporting=False" in renderer
    assert "supporting_trade_detail_html" in renderer
    assert "build_trade_narrative" in renderer
    assert "trade_review_first_useful" in renderer


def test_trade_hub_filters_still_use_cached_section_board():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    # Unified ranked feed — no category pill selector; strategy lens + show more remain.
    assert "trade_hub_board_section_" not in app_source
    assert "trade_hub_unified_feed_" in app_source
    assert "annotate_trade_hub_feed_categories" in app_source
    assert "cached_trade_ideas(" in app_source
    assert '"trade_hub_visible_cards_render"' in app_source


def test_headshot_presets_are_shared_and_bounded():
    assert player_headshot_preset("trade-avatar") == "compact"
    assert player_headshot_preset("compact-player-row") == "compact"
    assert player_headshot_preset("player-avatar") == "standard"
    assert player_headshot_preset("player-profile-hero") == "profile"
    html = avatar_html("https://example.com/player.png", "AB", "trade-avatar")
    assert "dg-player-headshot" in html
    assert "dg-player-headshot--compact" in html
    assert "dg-player-headshot-image" in html


def test_headshot_fallback_remains_centered_and_uses_shared_preset():
    html = avatar_html("", "AB", "player-avatar")
    assert "dg-player-headshot--standard" in html
    assert "dg-player-headshot-fallback" in html
    assert ">AB<" in html
    assert "<img" not in html


def test_final_headshot_css_has_no_extreme_crop_or_offsets():
    source = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    final = source[source.rindex("/* Shared player headshots.") :]
    scales = [float(value) for value in re.findall(r"--dg-headshot-scale:\s*([0-9.]+)", final)]
    assert scales
    assert min(scales) >= 1.0
    assert max(scales) <= 1.22
    assert "object-fit: contain !important" in final
    assert "object-position: center bottom !important" in final
    assert "translate(" not in final
    assert re.search(r"top:\s*-", final) is None
    assert re.search(r"bottom:\s*-", final) is None


def test_player_headshot_rules_do_not_target_team_or_league_avatars():
    source = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    final = source[source.rindex("/* Shared player headshots.") :]
    headshot_block = final[: final.index("/* Trade Hub mobile hierarchy")]
    assert "team-logo" not in headshot_block
    assert "league-avatar" not in headshot_block
    assert "manager-avatar" not in headshot_block


def test_trade_mobile_css_reduces_nested_wrappers_and_overflow():
    source = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    final = source[source.rindex("/* Trade Hub mobile hierarchy") :]
    assert ".trade-card-net-strip" in final
    assert ".trade-reason-panel" in final
    assert "overflow-wrap: anywhere" in final
    assert "trade-delta-stack" not in final
    assert "trade-card-value-strip" not in final
    assert 'div[class*="st-key-trade_why_"]' in final
    assert "min-height: var(--touch-target-min)" in final
