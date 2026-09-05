"""PQV / Trade Hub / share-card presentation contracts (no football semantics)."""

from __future__ import annotations

from pathlib import Path

from modules import brand_identity
from modules import share_recommendation_cards as share
from modules import trade_hub_ui


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PQV = APP[
    APP.index("def render_player_quick_view_content(") : APP.index(
        "def render_player_detail_content("
    )
]


def test_collapsed_trade_card_stacks_below_700px_iframe_width():
    css = trade_hub_ui.TRADE_SUMMARY_COMPONENT_CSS
    first_package = css.split(".trade-summary-package {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: minmax(0, 1fr);" in first_package
    assert "container-type: inline-size;" in css
    assert "@container trade-summary (min-width: 700px)" in css
    assert "@media (min-width: 360px)" not in css
    assert "max-width: 8rem" not in css


def test_pqv_first_paint_shows_hydrated_season_snapshot_not_deep_tabs():
    assert "current_season_summary_html(" in PQV.split("pqv_first_useful", 1)[0]
    assert "compact_model_summary_html(" in PQV.split("pqv_first_useful", 1)[0]
    assert "compact_career_summary_html(" in PQV.split("pqv_first_useful", 1)[0]
    assert PQV.index("current_season_summary_html(") < PQV.index("pqv_actions_")
    assert PQV.index("season_html=season_snapshot_html") < PQV.index("pqv_first_useful")
    assert PQV.index("model_html=model_summary_html") < PQV.index("pqv_first_useful")
    assert PQV.index("career_html=career_summary_html") < PQV.index("pqv_first_useful")
    assert "load_cached_career_resume(" not in PQV.split("pqv_detail_nav_", 1)[0]
    assert "cached_sleeper_player_directory(" not in PQV.split("pqv_detail_nav_", 1)[0]
    assert "build_player_share_card(" not in PQV.split("if share_eligible and st.session_state.get(share_open_key)", 1)[0]
    assert 'detail_choice == "STATS"' in PQV
    assert PQV.index("render_current_season(") > PQV.index('detail_choice == "STATS"')


def test_pqv_trade_hub_remains_one_script_path_app_rerun():
    assert "trade_hub_clicked = st.button(" in PQV
    assert 'st.rerun(scope="app")' in PQV
    assert PQV.index("trade_hub_clicked = st.button(") < PQV.index(
        "_open_trade_hub_for_player_focus("
    )
    opener = APP[
        APP.index("def _open_trade_hub_for_player_focus(") : APP.index(
            "def render_player_detail_picker("
        )
    ]
    assert "st.rerun(" not in opener
    assert "queue_player_focus(" in opener


def test_pqv_first_paint_defers_season_career_share_and_awards():
    before_useful = PQV.split("pqv_first_useful", 1)[0]
    after_nav = PQV.split("pqv_detail_nav_", 1)[1]
    after_useful = PQV.split("pqv_first_useful", 1)[1]
    assert "current_season_summary_html(" in before_useful
    assert "compact_model_summary_html(" in before_useful
    assert "compact_career_summary_html(" in before_useful
    assert "career_dossier_html(" not in before_useful
    assert "build_player_share_card(" not in before_useful
    assert "pqv_share_open_" in after_useful
    assert "career_dossier_html(" in after_nav
    assert "load_cached_career_resume(" in after_nav
    assert "build_season_cache_index(" not in before_useful
    assert "include_tier_legend=False" in before_useful


def test_pqv_desktop_composition_keeps_compact_modules():
    from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS

    desktop = PLAYER_QUICK_VIEW_CSS.split("@media (min-width: 1024px)", 1)[1]
    compact = desktop.replace(" ", "")
    assert 'grid-template-areas:"identity decision" "season season"' in desktop
    assert "repeat(6,minmax(4.5rem,6.5rem))" in compact
    assert "justify-content:start" in compact
    assert ".pqv-compact-summaries{align-items:stretch;grid-template-columns:minmax(0,1fr)minmax(0,1fr)}" in compact
    assert "max-width:min(54rem,calc(100dvw-4rem))" in compact
    assert ".pqv-workspace{display:grid" in PLAYER_QUICK_VIEW_CSS.replace(" ", "")
    assert "max-width:54rem" in PLAYER_QUICK_VIEW_CSS.split("@media (min-width: 1024px)", 1)[0].replace(" ", "")
    assert "grid-template-columns:repeat(4,minmax(0,1fr))" not in compact
    mobile = PLAYER_QUICK_VIEW_CSS.split("@media (max-width:430px)", 1)[1].split("@media (min-width: 1024px)", 1)[0]
    assert "repeat(3,minmax(0,1fr))" in mobile.replace(" ", "")
    assert "repeat(2,minmax(0,1fr))" in mobile.replace(" ", "")


def test_collapsed_trade_card_omits_fgl_founder_beta_lockup():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    card = source[
        source.index("summary_html = textwrap.dedent(") : source.index(
            "summary_result = TRADE_SUMMARY_TAP_COMPONENT"
        )
    ]
    assert "trade_screenshot_brand_html" not in card
    assert "Founder Beta" not in card
    assert "dg-brand-plate__fgl" not in card
    brand = brand_identity.trade_screenshot_brand_html()
    assert "FantasyGM Lab" in brand
    assert "Founder Beta" not in brand
    assert "dg-brand-plate__fgl" not in brand
    assert "<img" in brand


def test_trade_card_presentation_contract_is_payload_only():
    idea = {
        "send_assets": [{"name": "A", "player_id": "1"}],
        "receive_assets": [{"name": "B", "player_id": "2"}],
        "my_score": 10,
        "their_score": 12,
        "trade_gain": 2,
        "trade_confidence_label": "High",
        "trade_idea_score": 91.2,
    }
    before = dict(idea)
    payload = trade_hub_ui.trade_card_presentation_contract(idea)
    assert idea == before
    assert payload["send_score"] == 10
    assert payload["receive_score"] == 12
    assert payload["trade_gain"] == 2
    assert payload["confidence"] == "High"
    assert payload["ordering_score"] == 91.2


def test_share_labels_are_perspective_safe_with_and_without_team_names():
    named = share.build_trade_share_card(
        {
            "partner_team_name": "Tongue Punchers",
            "trade_gain": 10,
            "send_assets": [{"name": "Send", "player_id": "1"}],
            "receive_assets": [{"name": "Get", "player_id": "2"}],
            "reasoning_summary": "Need-based swap.",
        },
        my_team_name="Harbor Club",
    )
    assert named.send_side_label == "Tongue Punchers receives"
    assert named.receive_side_label == "Harbor Club receives"
    rewritten = share.rewrite_share_reason_sides(
        "You add future flexibility.",
        my_team_name="Harbor Club",
    )
    assert rewritten == "Harbor Club adds future flexibility."
    assert "You " not in rewritten
    payload = share.build_share_text_payload(named)
    assert "YOU GIVE" not in payload
    assert "YOU GET" not in payload
    assert "YOU SEND" not in payload
    assert "Tongue Punchers receives" in payload
    assert "Harbor Club receives" in payload

    unnamed = share.build_trade_share_card(
        {
            "trade_gain": 0,
            "send_assets": [{"name": "Send", "player_id": "1"}],
            "receive_assets": [{"name": "Get", "player_id": "2"}],
            "reasoning_summary": "You add future flexibility.",
        }
    )
    assert unnamed.send_side_label == "Trade partner receives"
    assert unnamed.receive_side_label == "This roster receives"
    assert "YOU GIVE" not in share.build_share_text_payload(unnamed)
    assert "Proposing roster" not in share.build_share_text_payload(unnamed)
    assert "You add" not in unnamed.reason
    assert "This roster adds future flexibility" in unnamed.reason
    assert unnamed.verdict == "Fair"
    payload = share.build_share_text_payload(unnamed)
    assert "Edge:" in payload
    assert payload.index("Fair") < payload.index("Edge:")
    assert "Balance:" not in payload


def test_authenticated_team_name_ignores_league_browse_selection():
    import pandas as pd

    from modules import prepared_player_frame

    session = {
        "selected_team_name": "Wrong Browse Team",
        "my_roster_id": "7",
        "selected_league_id": "L1",
        prepared_player_frame.SHARED_CONTEXT_KEY: {
            "L1-memo": {
                "team_direction_summary": pd.DataFrame(
                    [{"roster_id": "7", "team_name": "Harbor Club"}]
                )
            }
        },
    }
    assert trade_hub_ui.authenticated_team_display_name(session) == "Harbor Club"
    assert trade_hub_ui.authenticated_team_display_name(
        {"selected_team_name": "Wrong"}, idea={"my_team_name": "From Idea"}
    ) == "From Idea"


def test_pqv_actions_sit_under_decision_without_dead_space_label():
    assert "player-quick-view-actions-label" not in PQV
    assert "pqv_actions_tertiary_" in PQV
    assert PQV.index("pqv_actions_strip_") < PQV.index("pqv_detail_nav_")
    assert "type=\"tertiary\"" in PQV[PQV.index("pqv_actions_tertiary_") :]


def test_share_generation_stays_behind_explicit_share_open():
    assert "if share_eligible and st.session_state.get(share_open_key)" in PQV
    dialog = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    body = dialog[
        dialog.index("def render_trade_idea_card(") : dialog.index(
            "def render_trade_idea_player_actions("
        )
    ]
    summary = body.split("if navigation.trade_key == summary_key:")[0]
    assert "build_trade_share_card(" not in summary
    assert "render_share_controls(" not in summary
    assert "build_trade_share_card(" in body.split("if navigation.trade_key == summary_key:")[1]
