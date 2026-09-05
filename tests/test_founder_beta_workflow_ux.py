"""Workflow UX correctness contracts for Founder Beta bug-fix sprint."""

from __future__ import annotations

from pathlib import Path

from modules import trade_detail_navigation


ROOT = Path(__file__).resolve().parents[1]


def test_workflow_ux_report_exists():
    text = (ROOT / "docs" / "founder-beta-workflow-ux-fixes.md").read_text(encoding="utf-8")
    assert "No football logic" in text or "no football logic" in text.casefold()
    assert "render_trade_hub_section_filter" in text
    assert "Dashboard Next Move" in text or "Next Moves" in text


def test_league_switch_closes_trade_detail_navigation():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    clearer = source.split("def _clear_league_switch_transient_state(", 1)[1].split(
        "\ndef ", 1
    )[0]
    assert "trade_detail_navigation.close(" in clearer
    set_selected = source.split("def set_selected_league(", 1)[1].split(
        "def _open_mobile_destination_sheet", 1
    )[0]
    assert "_clear_league_switch_transient_state(previous_league_id=previous_league_id)" in (
        set_selected
    )


def test_trade_detail_close_clears_active_keys():
    state = {
        "dg_trade_detail_active": "trade-key",
        "dg_trade_detail_view": "player",
        "dg_trade_detail_player": "123",
    }
    trade_detail_navigation.close(state)
    assert "dg_trade_detail_active" not in state
    assert "dg_trade_detail_view" not in state
    assert "dg_trade_detail_player" not in state


def test_pqv_spacing_is_not_over_compressed():
    styles = (ROOT / "modules" / "player_quick_view_styles.py").read_text(encoding="utf-8")
    compression = (
        ROOT / "modules" / "executive_workflow_compression_styles.py"
    ).read_text(encoding="utf-8")
    assert '.pqv-workspace{display:grid;gap:var(--space-sm);' in styles
    assert '.pqv-decision-row,.pqv-evidence-row{align-items:start;display:grid;gap:var(--space-md);' in styles
    assert 'min-height:var(--touch-target-min)' in styles
    compact = "".join(compression.split())
    assert "margin:var(--space-md)0!important" in compact
    assert "margin:var(--space-xs)0!important" not in compact
