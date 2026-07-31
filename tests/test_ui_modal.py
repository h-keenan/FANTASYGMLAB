from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from modules import trade_hub_ui
from modules import ui_modal
from modules import workspace_ui
from modules.ui_modal_styles import UI_MODAL_CSS


def _content() -> ui_modal.ModalContent:
    return ui_modal.ModalContent(
        title="League Pulse Detail",
        eyebrow="Metric Detail",
        summary="Contender",
        sections=(
            ui_modal.ModalSection("What It Means", "Existing explanation."),
            ui_modal.ModalSection("Context", "Existing context."),
        ),
        list_title="Supporting Context",
        list_items=(
            ui_modal.ModalListItem(
                "Fixture Team",
                "#1",
                "Existing note.",
                highlighted=True,
            ),
        ),
        footer="Existing footer.",
    )


def test_modal_content_is_frozen_and_escapes_all_text():
    content = ui_modal.ModalContent(
        title="<script>Title</script>",
        summary="<b>Summary</b>",
        sections=(ui_modal.ModalSection("Label", "<img src=x>"),),
    )

    html = ui_modal.modal_content_html(content, surface="dashboard_league_pulse")

    assert "<script>" not in html
    assert "<b>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;Title&lt;/script&gt;" not in html  # title belongs to dialog chrome
    assert "&lt;b&gt;Summary&lt;/b&gt;" in html
    assert "&lt;img src=x&gt;" in html


def test_modal_shell_uses_public_accessible_dialog_contract_and_supported_renderer():
    decorator = Mock()
    rendered = Mock()

    def decorate(function):
        decorator.function = function
        return function

    with (
        patch.object(ui_modal.st, "dialog", return_value=decorate) as dialog,
        patch.object(ui_modal, "render_html_fragment", rendered),
    ):
        ui_modal.render_modal(_content(), surface="dashboard_league_pulse")

    dialog.assert_called_once_with(
        "League Pulse Detail",
        width="large",
        dismissible=True,
        on_dismiss="rerun",
    )
    rendered.assert_called_once()
    assert rendered.call_args.kwargs == {}


def test_modal_dialog_title_is_escaped_before_streamlit_markdown_parsing():
    decorator = Mock(side_effect=lambda function: function)
    content = ui_modal.ModalContent(
        title="<script>Unsafe</script>",
        summary="Safe summary",
    )
    with (
        patch.object(ui_modal.st, "dialog", return_value=decorator) as dialog,
        patch.object(ui_modal, "render_html_fragment"),
    ):
        ui_modal.render_modal(content, surface="dashboard_league_pulse")

    assert dialog.call_args.args[0] == "&lt;script&gt;Unsafe&lt;/script&gt;"


def test_modal_structure_has_summary_sections_list_and_footer():
    html = ui_modal.modal_content_html(
        _content(),
        surface="dashboard_league_pulse",
    )

    assert "dg-modal-header" in html
    assert "dg-modal-summary" in html
    assert html.count("dg-modal-section-body") == 2
    assert "dg-modal-list-row--highlighted" in html
    assert "dg-modal-footer" in html


def test_dashboard_adapter_preserves_existing_summary_detail_meaning():
    item = {
        "label": "Draft Capital Leader",
        "value": "Fixture Team",
        "note": "9000 | 3 firsts",
        "explanation": "Existing explanation.",
        "supporting_context": "Existing supporting detail.",
        "detail_items": [
            {
                "title": "Fixture Team",
                "value": "#1",
                "note": "Score 9000",
                "current": True,
            }
        ],
    }

    content = workspace_ui.canonical_summary_tile_modal_content(item)

    assert content.title == "Draft Capital Leader"
    assert content.summary == "Fixture Team"
    assert [(section.label, section.body) for section in content.sections] == [
        ("What It Means", "Existing explanation."),
        ("Context", "9000 | 3 firsts"),
        ("Supporting Detail", "Existing supporting detail."),
    ]
    assert content.list_items[0].highlighted is True


def test_only_dashboard_league_pulse_uses_canonical_modal_proof():
    app_source = Path("app.py").read_text(encoding="utf-8")
    call = "workspace_ui.render_canonical_summary_tile_detail_dialog"

    assert app_source.count(call) == 1
    assert app_source.index(call) > app_source.index(
        'with st.expander("League Pulse"'
    )
    assert app_source.count("detail_dialog_renderer=") == 1


def test_dashboard_summary_tiles_use_injected_canonical_dialog_path():
    result = type("Result", (), {"clicked": {"index": "0"}})()
    legacy = Mock()
    canonical = Mock()
    with (
        patch.object(workspace_ui, "SUMMARY_TILE_TAP_COMPONENT", return_value=result),
        patch.object(workspace_ui, "_render_summary_tile_detail_dialog", legacy),
    ):
        workspace_ui.render_summary_tiles(
            [{"label": "Power Rank", "value": "#1"}],
            detail_dialog_renderer=canonical,
        )

    canonical.assert_called_once()
    legacy.assert_not_called()


def test_other_summary_tiles_keep_existing_dialog_path_by_default():
    result = type("Result", (), {"clicked": {"index": "0"}})()
    legacy = Mock()
    with (
        patch.object(workspace_ui, "SUMMARY_TILE_TAP_COMPONENT", return_value=result),
        patch.object(workspace_ui, "_render_summary_tile_detail_dialog", legacy),
    ):
        workspace_ui.render_summary_tiles(
            [{"label": "Power Rank", "value": "#1"}],
        )

    legacy.assert_called_once()


def test_modal_and_trade_disclosure_keys_have_disjoint_namespaces():
    modal_key = ui_modal.modal_content_key(
        _content(),
        surface="dashboard_league_pulse",
    )
    trade_key = trade_hub_ui.trade_explanation_disclosure_key(
        {
            "partner_roster_id": "fixture",
            "my_player": "send",
            "their_player": "receive",
            "my_score": 1,
            "their_score": 2,
            "tag": "Fixture",
        },
        key_prefix="trade_hub_fixture",
    )

    assert modal_key.startswith("dg_modal_")
    assert trade_key.startswith("trade_why_")
    assert modal_key != trade_key


def test_modal_styles_are_scoped_and_token_backed():
    assert ".dg-modal-" in UI_MODAL_CSS
    assert "var(--" in UI_MODAL_CSS
    assert "#" not in UI_MODAL_CSS
    assert "rgba(" not in UI_MODAL_CSS
    assert "[data-testid" not in UI_MODAL_CSS
    assert ":root" not in UI_MODAL_CSS


def test_trade_summary_modal_and_crash_fix_contract():
    source = Path("modules/trade_hub_ui.py").read_text(encoding="utf-8")
    renderer = source[
        source.index("def render_trade_idea_card(") :
        source.index("\ndef render_trade_idea_player_actions(")
    ]

    assert "View trade" in renderer
    assert "trade_summary_key(" in renderer
    assert "@st.dialog(" in renderer
    assert "TRADE_SUMMARY_TAP_COMPONENT(" in renderer
    assert "if summary_clicked is True:" in renderer
    assert 'render_html_fragment(explanation_html, label=' not in renderer
