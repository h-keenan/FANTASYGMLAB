from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from modules import trade_detail_navigation, trade_hub_ui


ROOT = Path(__file__).resolve().parents[1]


def _idea() -> dict:
    return {
        "partner_roster_id": "partner-7",
        "partner_team_name": "Lakefront Franchise",
        "tag": "Get Younger + Pick",
        "my_score": 8500,
        "their_score": 9000,
        "trade_gain": 500,
        "fit_grade": "Strong",
        "market_realism_label": "Plausible",
        "trade_confidence_label": "Medium",
        "send_assets": [
            {"asset_type": "player", "player_id": "sent-player", "name": "Sent Player"},
            {"asset_type": "pick", "name": "2027 2nd"},
        ],
        "receive_assets": [
            {"asset_type": "player", "player_id": "received-player", "name": "Received Player"},
        ],
        "reasoning_summary": "A bounded fixture rationale.",
    }


def _render(
    *,
    state: dict,
    summary_clicked: bool,
    clicked_player: str = "",
    dossier: Mock | None = None,
    back_clicked: bool = False,
    html_renderer: Mock | None = None,
):
    dialog_callbacks = []

    def component(**_kwargs):
        return type("Result", (), {"clicked": {"open": True} if summary_clicked else None})()

    def dialog(*_args, **kwargs):
        dialog_callbacks.append(kwargs.get("on_dismiss"))
        return lambda fn: fn

    def button(*_args, **kwargs):
        if back_clicked and callable(kwargs.get("on_click")):
            kwargs["on_click"](*kwargs.get("args", ()), **kwargs.get("kwargs", {}))
        return back_clicked

    with (
        patch.object(trade_hub_ui, "TRADE_SUMMARY_TAP_COMPONENT", component),
        patch.object(trade_hub_ui, "render_trade_html_with_player_taps", return_value=clicked_player),
        patch.object(trade_hub_ui, "render_html_fragment", html_renderer or Mock()),
        patch.object(trade_hub_ui.st, "session_state", state),
        patch.object(trade_hub_ui.st, "dialog", dialog),
        patch.object(trade_hub_ui.st, "button", side_effect=button),
        patch.object(trade_hub_ui.st, "rerun") as rerun,
    ):
        trade_hub_ui.render_trade_idea_card(
            _idea(),
            0,
            key_prefix="trade_board",
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
            render_tappable_player_html=Mock(),
            render_player_dossier=dossier,
        )
    return rerun, dialog_callbacks


@pytest.mark.parametrize("player_id", ["sent-player", "received-player"])
def test_player_tap_replaces_trade_body_with_canonical_dossier(player_id):
    state = {}
    dossier = Mock()
    rerun, _ = _render(
        state=state,
        summary_clicked=True,
        clicked_player=player_id,
        dossier=dossier,
    )
    assert trade_detail_navigation.current(state).player_id == player_id
    rerun.assert_called_once()

    _render(state=state, summary_clicked=False, dossier=dossier)
    dossier.assert_called_once_with(
        player_id,
        source_label="Trade Hub",
        source_note="Inspect this player without leaving the active trade.",
    )


def test_back_returns_to_same_trade_and_close_clears_the_entire_dialog():
    state = {}
    dossier = Mock()
    _render(state=state, summary_clicked=True, clicked_player="sent-player", dossier=dossier)
    original_trade = trade_detail_navigation.current(state).trade_key

    rerun, callbacks = _render(
        state=state,
        summary_clicked=False,
        dossier=dossier,
        back_clicked=True,
    )
    assert trade_detail_navigation.current(state).trade_key == original_trade
    assert trade_detail_navigation.current(state).view == "trade"
    rerun.assert_not_called()

    trade_detail_navigation.open_player(
        state,
        trade_key=original_trade,
        player_id="received-player",
    )
    _, callbacks = _render(state=state, summary_clicked=False, dossier=dossier)
    callbacks[-1]()
    assert trade_detail_navigation.current(state).trade_key == ""


def test_trade_explanation_rows_never_render_as_indented_markdown_code():
    state = {}
    html_renderer = Mock()
    _render(state=state, summary_clicked=True, html_renderer=html_renderer)

    rendered = [call.args[0] for call in html_renderer.call_args_list]
    explanation = next(value for value in rendered if "trade-reason-panel" in value)
    assert "Expected outcome" in explanation
    assert "Value summary" not in explanation
    assert "\n    <div class=\"trade-reason-row\"" not in explanation

def test_draft_pick_is_not_tappable_or_promoted_to_player_navigation():
    tap = Mock(return_value="2027-2")
    with patch.object(trade_hub_ui, "render_trade_html") as render:
        selected = trade_hub_ui.render_trade_html_with_player_taps(
            "<div>2027 2nd</div>",
            [{"asset_type": "pick", "player_id": "2027-2", "name": "2027 2nd"}],
            key_prefix="pick-only",
            source_label="Trade Hub",
            render_tappable_player_html=tap,
        )
    assert selected == ""
    tap.assert_not_called()
    render.assert_called_once()


def test_navigation_keys_are_deterministic_unique_and_namespace_isolated():
    first = trade_detail_navigation.control_key("trade-a", "back")
    assert first == trade_detail_navigation.control_key("trade-a", "back")
    assert first != trade_detail_navigation.control_key("trade-b", "back")
    assert first.startswith("trade_detail_nav_")
    assert not first.startswith("dg_modal_")
    assert not first.startswith("trade_why_")


def test_trade_dossier_reuses_canonical_renderer_without_nested_dialog():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    helper = app_source[
        app_source.index("def render_trade_player_dossier_content(") :
        app_source.index("def render_player_quick_view_modal(")
    ]
    trade_source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    dialog_body = trade_source[
        trade_source.index("def _trade_detail_dialog()") :
        trade_source.index("def render_trade_idea_player_actions(")
    ]
    assert "render_player_quick_view_content(" in helper
    assert "render_player_quick_view_modal(" not in helper
    assert dialog_body.count("@st.dialog") == 0
    assert "render_player_dossier(" in dialog_body


def test_trade_detail_styles_use_tokens_and_preserve_touch_and_focus_contracts():
    css = (ROOT / "modules" / "trade_detail_styles.py").read_text(encoding="utf-8")
    assert "var(--touch-target-min)" in css
    assert "var(--focus-ring)" in css
    assert "var(--color-danger)" in css
    assert "var(--color-success)" in css
    assert "@media (max-width: 700px)" in css
    assert "grid-template-columns: minmax(0, 1fr)" in css
    assert "#" not in css
