"""Mobile resume, Dashboard first-useful, and Trade Hub modal open contracts."""

from pathlib import Path
from unittest.mock import Mock, patch

from modules.navigation_state import (
    PENDING_ROUTE_SOURCE_KEY,
    queue_destination_navigation,
    resolve_resume_destination,
)
from modules import trade_detail_navigation, trade_hub_ui


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
ALLOWED = {"dashboard", "trade_hub", "my_team", "waivers"}


def test_league_auto_resume_does_not_queue_dashboard():
    resume = APP.split("def _resume_saved_supabase_league(", 1)[1].split(
        "def _maybe_auto_resume_supabase_league", 1
    )[0]
    auto = APP.split("def _maybe_auto_resume_supabase_league", 1)[1].split(
        "def _refresh_supabase_account_profile", 1
    )[0]
    assert "route_to_dashboard: bool = True" in resume
    assert "_resume_saved_supabase_league(default_league, route_to_dashboard=False)" in auto


def test_league_hydrate_pending_yields_to_trade_hub_query():
    assert (
        resolve_resume_destination(
            pending_page="dashboard",
            pending_source="league_selection",
            query_page="trade_hub",
            session_page="",
            allowed=ALLOWED,
        )
        == "trade_hub"
    )
    assert (
        resolve_resume_destination(
            pending_page="dashboard",
            pending_source="league_selection",
            query_page="",
            session_page="trade_hub",
            allowed=ALLOWED,
        )
        == "trade_hub"
    )


def test_sidebar_pending_still_wins_over_stale_query():
    assert (
        resolve_resume_destination(
            pending_page="waivers",
            pending_source="sidebar_destination",
            query_page="trade_hub",
            session_page="trade_hub",
            allowed=ALLOWED,
        )
        == "waivers"
    )


def test_empty_pending_uses_query_then_leaves_session_when_absent():
    assert (
        resolve_resume_destination(
            pending_page="",
            pending_source="",
            query_page="trade_hub",
            session_page="dashboard",
            allowed=ALLOWED,
        )
        == "trade_hub"
    )
    assert (
        resolve_resume_destination(
            pending_page="",
            pending_source="",
            query_page="",
            session_page="trade_hub",
            allowed=ALLOWED,
        )
        == ""
    )


def test_queue_destination_records_pending_source():
    state = {"platform_nav_page": "trade_hub"}
    queue_destination_navigation(
        state,
        "dashboard",
        current_destination="trade_hub",
        source="league_selection",
        force_scroll=True,
    )
    assert state["_pending_platform_route"] == "dashboard"
    assert state[PENDING_ROUTE_SOURCE_KEY] == "league_selection"


def test_app_restore_prefers_resolve_resume_destination():
    restore = APP.split("pending_page = _normalize_platform_page(", 1)[1][:1200]
    assert "resolve_resume_destination(" in restore
    assert "PENDING_ROUTE_SOURCE_KEY" in restore
    assert "if pending_page in destination_lookup:" not in restore


def test_dashboard_skips_cosmetic_query_param_rerun():
    assert (
        'if _query_param_page() or current_page != "dashboard":\n'
        '            st.query_params["page"] = current_page'
    ) in APP


def test_trade_hub_skips_search_and_other_cards_while_modal_open():
    feed = APP.split("def _trade_hub_visible_feed()", 1)[1].split(
        "_trade_hub_visible_feed()", 1
    )[0]
    assert "open_trade_key" in feed
    assert "if card_key != open_trade_key:" in feed
    after_board = APP.split("def _render_search_around_player_body()", 1)[1]
    call_site = after_board.split("trade_hub_first_useful.mark_trade_hub_milestone", 1)[0]
    assert "render_top_trade_opportunities()" in call_site
    assert "if not trade_detail_navigation.current(st.session_state).trade_key:" in call_site
    assert "render_search_around_player()" in call_site
    assert call_site.index("render_top_trade_opportunities()") < call_site.index(
        "render_search_around_player()"
    )
    assert "note_skip(\"trade_dialog_open\")" in call_site
    assert "trade_detail_open = bool(" not in call_site


def test_modal_open_does_not_render_share_png_until_share_active():
    ui = (ROOT / "modules" / "share_recommendation_ui.py").read_text(encoding="utf-8")
    detail = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    assert "render_share_card_png" in ui
    assert "share_active" in ui
    assert "render_share_controls(" in detail
    assert "render_share_card_png" not in detail


def test_compact_modal_assets_use_cdn_url_before_byte_headshots():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    block = source.split("def trade_asset_html(", 1)[1].split(
        "def trade_assets_html(", 1
    )[0]
    assert "if compact:" in block
    assert "get_player_image_url(player_id)" in block
    compact_idx = block.index("if compact:")
    data_idx = block.index("cached_headshot_data_url(player_id)")
    assert compact_idx < data_idx


def _idea(partner: str = "Lakefront Franchise") -> dict:
    return {
        "partner_roster_id": f"partner-{partner}",
        "partner_team_name": partner,
        "tag": f"Get Younger {partner}",
        "my_score": 8500,
        "their_score": 9000,
        "trade_gain": 500,
        "fit_grade": "Strong",
        "market_realism_label": "Plausible",
        "trade_confidence_label": "Medium",
        "send_assets": [
            {"asset_type": "player", "player_id": "sent-player", "name": "Sent Player"},
        ],
        "receive_assets": [
            {"asset_type": "player", "player_id": "received-player", "name": "Received Player"},
        ],
        "reasoning_summary": "A bounded fixture rationale.",
    }


def test_open_trade_skips_other_cards_without_narrative_rebuild():
    state = {}
    first = _idea("Alpha")
    second = _idea("Beta")
    first_key = trade_hub_ui.trade_summary_key(
        first, page_context="trade_hub_feed", instance_token=0
    )
    trade_detail_navigation.open_trade(state, first_key)

    def component(**_kwargs):
        return type("Result", (), {"clicked": None})()

    with (
        patch.object(trade_hub_ui, "TRADE_SUMMARY_TAP_COMPONENT", component),
        patch.object(trade_hub_ui, "render_html_fragment", Mock()),
        patch.object(trade_hub_ui.st, "session_state", state),
        patch.object(trade_hub_ui.st, "dialog", lambda *_a, **_k: (lambda fn: fn)),
        patch.object(
            trade_hub_ui.canonical_recommendation_narrative,
            "build_trade_narrative",
        ) as build_narrative,
    ):
        trade_hub_ui.render_trade_idea_card(
            second,
            1,
            key_prefix="trade_hub_feed",
            format_score=str,
            tidy_label=str,
            trade_target_reason=lambda _: "Why it helps.",
            trade_partner_reason=lambda _: "Why they consider it.",
            trade_confidence_reason=lambda _: "Confidence context.",
            trade_value_verdict=lambda _: "Fair",
            trade_display_confidence_label=lambda _: "Medium",
            injury_display_context=lambda _: {"risk": False},
            glyph_chip_html=lambda *_args: "",
            assets_html=lambda _assets: "<div class='assets'></div>",
        )
    build_narrative.assert_not_called()
    assert trade_detail_navigation.current(state).trade_key == first_key
