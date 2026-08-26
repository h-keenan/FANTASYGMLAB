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
    assert "current_season_summary_html(" not in before_useful
    assert "career_dossier_html(" not in before_useful
    assert "build_player_share_card(" not in before_useful
    assert "pqv_share_open_" in after_useful
    assert "current_season_summary_html(" in after_nav
    assert "career_dossier_html(" in after_nav
    assert "build_season_cache_index(" not in before_useful
    assert "include_tier_legend=False" in before_useful


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
            "reasoning_summary": "Even swap.",
        }
    )
    assert unnamed.send_side_label == "Trade partner receives"
    assert unnamed.receive_side_label == "Proposing roster receives"
    assert "YOU GIVE" not in share.build_share_text_payload(unnamed)


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
