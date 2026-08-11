"""Executive surface parity and data integrity contracts (PR #134)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import player_eligibility
from modules import waivers_ui
from modules.trade_hub_ui import TRADE_SUMMARY_COMPONENT_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_trade_summary_uses_shared_headshot_helper():
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    helper = source[
        source.index("def _trade_summary_assets_html") : source.index(
            "def trade_hub_display_section"
        )
    ]
    assert "player_profile_ui.avatar_html" in helper
    assert "get_player_image_url" in helper
    assert "trade-summary-avatar compact-player-avatar" in helper
    assert "<img src=" not in helper


def test_waiver_sections_dedupe_across_stash_and_watchlist():
    featured = pd.DataFrame([{"player_id": "a", "name": "A"}])
    stash = pd.DataFrame(
        [
            {"player_id": "a", "name": "A"},
            {"player_id": "b", "name": "B"},
        ]
    )
    watch = pd.DataFrame([{"player_id": "b", "name": "B"}, {"player_id": "c", "name": "C"}])
    faab = pd.DataFrame([{"player_id": "d", "name": "D"}])

    _, stash_out, watch_out, faab_out = waivers_ui._dedupe_waiver_sections(
        featured, stash, watch, faab
    )

    assert stash_out["player_id"].tolist() == ["b"]
    assert watch_out["player_id"].tolist() == ["c"]
    assert faab_out["player_id"].tolist() == ["d"]


def test_executive_unify_normalizes_legacy_card_and_portrait_surfaces():
    css = (ROOT / "modules" / "desktop_executive_layout_styles.py").read_text(encoding="utf-8")
    for selector in (
        ".summary-tile",
        ".free-agent-card",
        ".home-command-card",
    ):
        assert selector in css
    assert ".team-rank-card" not in css


def test_trade_summary_iframe_headshots_use_contain_and_muted_background():
    css = TRADE_SUMMARY_COMPONENT_CSS
    assert "object-fit: contain" in css
    assert "color-surface-muted" in css


def test_scan_renderer_defaults_to_design_system():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    scan = source.split("def render_player_scan_cards(", 1)[1].split("\ndef ", 1)[0]
    compact = source.split("def _compact_player_row_html(", 1)[1].split("\ndef ", 1)[0]
    assert "design_system: bool = True" in scan
    assert "design_system: bool = True" in compact


def test_waiver_featured_fallback_does_not_restore_all_stale_players():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    block = source.split("featured_free_agents = free_agents_ranked[", 1)[1].split(
        "else:\n                featured_free_agents = free_agents_ranked.copy()",
        1,
    )[0]
    assert "is_current_fantasy_eligible" in block
    assert "free_agents_ranked.copy()" not in block.split("if featured_free_agents.empty")[1][:600]


def test_audit_document_exists():
    doc = (ROOT / "docs" / "executive-surface-parity-audit.md").read_text(encoding="utf-8")
    for section in (
        "Legacy component inventory",
        "Surface parity",
        "Desktop spacing audit",
        "Player presentation",
        "Data integrity audit",
        "Visual QA",
        "Explicit confirmation",
    ):
        assert section in doc


def test_no_football_logic_modules_modified_beyond_eligibility_integrity():
    """Eligibility tightening is data integrity; Trust scoring modules stay untouched.

    Valuation calibration audits may intentionally touch rankings / trade_ideas.
    """
    diff_names = {
        line.split("|")[0].strip()
        for line in __import__("subprocess")
        .run(
            ["git", "diff", "--name-only", "main"],
            capture_output=True,
            text=True,
            check=False,
        )
        .stdout.splitlines()
        if line.strip()
    }
    forbidden = {
        "modules/trust_engine.py",
    }
    assert not diff_names.intersection(forbidden)


def test_player_eligibility_module_has_veteran_unsigned_guard():
    source = (ROOT / "modules" / "player_eligibility.py").read_text(encoding="utf-8")
    assert "VETERAN_UNSIGNED_MIN_EXPERIENCE" in source
    assert "news_only_corroboration" in source
