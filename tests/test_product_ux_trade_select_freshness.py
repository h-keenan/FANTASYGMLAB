"""Product UX polish — Trade Analyzer packages, freshness, selects, posture."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from modules import app_styles
from modules import component_family_styles
from modules import game_plan_package
from modules import my_team_ui
from modules import workspace_ui


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
TOA = (ROOT / "modules" / "trade_analyzer_styles.py").read_text(encoding="utf-8")
FAMILY = component_family_styles.COMPONENT_FAMILY_CSS
VISUAL = (ROOT / "modules" / "visual_identity_styles.py").read_text(encoding="utf-8")
QUICK = (ROOT / "modules" / "founder_beta_quick_fix_styles.py").read_text(encoding="utf-8")


def test_trade_analyzer_supports_multi_asset_package_builder():
    assert "asset_identity" in APP or "analyzer_builder.asset_identity" in APP
    assert "+ Add asset" in APP
    assert "toa-chip" in TOA
    assert "trade_{side}_add_asset_toggle" in APP
    builder = (ROOT / "modules" / "trade_analyzer_builder.py").read_text(encoding="utf-8")
    assert "already on the other side" in builder
    # No artificial one-asset ceiling in analyzer page.
    assert "one player" not in APP.casefold().split("trade analyzer", 1)[-1][:8000]


def test_canonical_select_family_owns_menu_chrome():
    assert "ul[role=\"listbox\"]" in FAMILY
    assert "max-height:min(42vh,18rem)" in FAMILY.replace(" ", "")
    assert "border-accent" in FAMILY
    assert "stSelectboxVirtualDropdown" in FAMILY
    assert 'data-baseweb="popover"' in FAMILY
    # Competing select radius owners removed from visual identity / quick fix.
    assert '[data-baseweb="select"] > div' not in VISUAL
    assert '[data-baseweb="select"] > div' not in QUICK


def test_game_plan_soft_ttl_marks_stale_and_rebuilds():
    state: dict = {}
    sig = "freshness-sig-1"
    payload = {"briefing": {"items": []}, "built_at": time.time() - (6 * 60 * 60)}
    game_plan_package.store_package(state, signature=sig, package={"briefing": {"items": []}})
    # Force-age the stored package.
    state[game_plan_package.PACKAGE_KEY]["built_at"] = time.time() - (6 * 60 * 60)
    game_plan_package._PROCESS_PACKAGE_STORE[sig]["built_at"] = time.time() - (6 * 60 * 60)
    cached, hit = game_plan_package.lookup_package(state, signature=sig)
    assert hit is False
    assert cached is None
    assert state[game_plan_package.LAST_CACHE_STATUS_KEY] == "stale"
    assert state[game_plan_package.LAST_MISS_REASON_KEY] == "soft_ttl_expired"


def test_game_plan_fresh_hit_within_ttl():
    state: dict = {}
    sig = "freshness-sig-2"
    game_plan_package.store_package(state, signature=sig, package={"briefing": {"items": []}})
    cached, hit = game_plan_package.lookup_package(state, signature=sig)
    assert hit is True
    assert cached is not None
    assert state[game_plan_package.LAST_CACHE_STATUS_KEY] == "hit"
    assert game_plan_package.format_package_age_label(cached).startswith("Updated")


def test_manual_refresh_invalidates_recommendation_packages_only():
    state: dict = {"auth_session": {"user_id": "u1"}, "other": 1}
    sig = "freshness-sig-3"
    game_plan_package.store_package(state, signature=sig, package={"briefing": {"items": []}})
    assert sig in game_plan_package._PROCESS_PACKAGE_STORE
    game_plan_package.invalidate_recommendation_packages(state, signature=sig)
    assert game_plan_package.PACKAGE_KEY not in state
    assert sig not in game_plan_package._PROCESS_PACKAGE_STORE
    assert state.get("auth_session", {}).get("user_id") == "u1"
    assert state.get("other") == 1
    assert state[game_plan_package.LAST_CACHE_STATUS_KEY] == "rebuild"


def test_concept_tiles_preserve_comparison_for_posture():
    tiles = workspace_ui.concept_items_as_summary_tiles(
        [
            {
                "label": "Power",
                "title": "#4",
                "body": "Starter unit #5",
                "tone": "power",
                "comparison": {"title": "Power Rank", "rows": []},
            },
            {
                "label": "Outlook",
                "title": "Contender",
                "body": "ok",
                "tone": "franchise",
                "tappable": False,
            },
        ]
    )
    assert tiles[0]["tappable"] is True
    assert isinstance(tiles[0]["comparison"], dict)
    assert tiles[1]["tappable"] is False


def test_roster_posture_uses_league_comparisons_when_available():
    source = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    assert "dashboard_comparison_payloads" in source
    assert 'posture_comparisons.get("Power Rank")' in source
    assert 'posture_comparisons.get("Franchise Rank")' in source


def test_app_css_stays_under_budget_after_select_family():
    assert len(app_styles.APP_CSS) < 400_000
    assert "fgl-landing__hero" not in app_styles.APP_CSS
