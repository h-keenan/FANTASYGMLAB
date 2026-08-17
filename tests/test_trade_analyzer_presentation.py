"""Trade Analyzer presentation contracts — UI only, assembly architecture preserved."""

from __future__ import annotations

from pathlib import Path

from modules import trade_analyzer_builder as builder
from modules.trade_analyzer_styles import TRADE_ANALYZER_CSS


ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "modules" / "trade_analyzer_ui.py").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")
ASSEMBLY = (ROOT / "modules" / "trade_analyzer_assembly.py").read_text(encoding="utf-8")


def test_builder_hierarchy_is_send_receive_workspace():
    assert "data-toa-workspace" in UI
    assert "Build the trade" in UI
    assert "You send" in UI
    assert "You receive" in UI
    assert "st.columns(2)" in UI
    send_at = UI.index('title="You send"')
    receive_at = UI.index('title="You receive"')
    assert send_at < receive_at
    assert "@st.fragment" in UI
    assert "st.rerun(" not in UI
    assert "evaluate_trade_analyzer_fit" not in UI
    assert "evaluate_trade_analyzer_fit" not in ASSEMBLY


def test_partner_selector_is_compact_not_full_bleed():
    css = TRADE_ANALYZER_CSS
    assert "toa-partner-block" in css
    assert "max-width: 28rem" in css
    block = APP[APP.index('if current_page == "trade_analyzer":') : APP.index('if current_page == "premium":')]
    assert 'key="trade_receive_partner"' in block
    assert "st.selectbox(" in block
    assert "Team that sent this offer" not in block


def test_player_and_pick_rows_use_compact_identity_with_attached_action():
    assert "result_row_html(asset, selected=selected)" in UI
    assert 'key=f"toa_add_{side}_{token}"' in UI
    html = builder.result_row_html(
        {
            "asset_type": "player",
            "player_id": "1",
            "name": "Ashton Jeanty",
            "position": "RB",
            "team": "LV",
            "age": 22,
            "opportunity_label": "Elite Opportunity",
        },
        selected=True,
    )
    assert "toa-result-row--selected" in html
    assert "data-toa-selected='1'" in html
    assert "dg-compact-asset" in html
    pick = builder.result_row_html(
        {
            "asset_type": "pick",
            "label": "2027 1st",
            "season": 2027,
            "round": 1,
            "owner_team_name": "Lakefront",
        }
    )
    assert "dg-compact-pick-plate" in pick
    assert "dg-compact-asset--pick" in pick
    assert "flex: 0 0 5.25rem" in TRADE_ANALYZER_CSS
    assert "width: max-content" in TRADE_ANALYZER_CSS


def test_analyze_cta_is_gated_and_not_full_bleed():
    block = APP[APP.index('if current_page == "trade_analyzer":') : APP.index('if current_page == "premium":')]
    assert "can_analyze" in block
    assert 'type="primary" if can_analyze else "secondary"' in block
    assert "use_container_width=False" in block
    assert "Reviewed package" in block
    assert "Queue send and receive assets" in block


def test_mobile_workspace_stacks_and_desktop_is_capped():
    css = TRADE_ANALYZER_CSS
    assert "@media (max-width: 1023px)" in css
    assert "max-width: 72rem" in css
    assert "min-height: var(--touch-target-min, 44px)" in css


def test_empty_copy_is_builder_guidance():
    assert "Nothing queued to send" in UI
    assert "Nothing queued to receive" in UI
    assert "No assets selected to receive." not in UI
    assert "No assets selected to send." not in UI
