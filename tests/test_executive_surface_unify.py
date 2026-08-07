"""Contracts for unifying the executive command surface (PR follow-up polish)."""

from pathlib import Path

from modules.application_shell_styles import APPLICATION_SHELL_CSS
from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_command_surface_has_no_second_header_divider():
    css = EXECUTIVE_COMMAND_HEADER_CSS
    mobile = css[css.index("@media (max-width: 760px)") :]
    assert "border-block-start: 0" in mobile
    assert (
        'div[class*="st-key-executive_command_actions"] [data-testid="stHorizontalBlock"]'
        in mobile
    )


def test_mobile_shell_hides_redundant_status_band():
    css = APPLICATION_SHELL_CSS
    mobile = css[css.index("@media (max-width: 760px)") :]
    assert ".dg-executive-shell__status" in mobile
    assert "display: none" in mobile[mobile.index(".dg-executive-shell__status") :][
        :120
    ]


def test_notification_panel_targets_mobile_viewport_band():
    css = EXECUTIVE_COMMAND_HEADER_CSS
    assert "60vh" in css
    assert "overflow-y: auto" in css


def test_trade_hub_entitlement_is_quiet_caption_not_titled_callout():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    renderer = source[
        source.index("def render_trade_hub_entitlement_summary(") : source.index(
            "def _trade_idea_identity("
        )
    ]
    assert "st.caption(" in renderer
    assert "Trade Hub access" not in renderer
    assert "render_informational_callout(" not in renderer


def test_docs_describe_one_continuous_command_surface():
    docs = (ROOT / "docs" / "executive-workspace-shell.md").read_text(encoding="utf-8")
    assert "executive command surface" in docs
    assert "not stacked separate headers" in docs
