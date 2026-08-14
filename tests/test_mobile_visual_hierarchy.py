"""Mobile visual hierarchy + perceived-load contracts (#231)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from modules import app_styles
from modules import brand_identity
from modules import daily_gm_briefing_ui
from modules import executive_command_header_styles
from modules import game_plan_process_cache
from modules import mobile_interaction_overlay_styles
from modules import mobile_visual_polish_styles
from modules import perceived_load
from modules import prepared_player_frame
from modules import workspace_ui


ROOT = Path(__file__).resolve().parents[1]


def test_no_legacy_gm_height_zero_collapse():
    css = app_styles.APP_CSS.replace("\r\n", "\n")
    # Legacy collapse that leaked "Open GM menu" as O/PE must stay gone.
    assert "height: 0 !important;\n        margin: 0 !important;\n        min-height: 0 !important;\n        overflow: visible !important;" not in css
    assert "width: auto;\n        z-index: 1001;" not in css
    assert "leaked \"Open GM menu\" as clipped \"O / PE\"" in css or "O / PE" in css


def test_gm_orb_hides_open_gm_menu_text():
    overlay = mobile_interaction_overlay_styles.MOBILE_INTERACTION_OVERLAY_CSS
    assert "width: var(--dg-gm-orb-size) !important" in overlay
    assert "text-indent: -9999px !important" in overlay
    assert "overflow: hidden !important" in overlay
    assert brand_identity.GM_ORB_ARIA_LABEL == "Open GM menu"
    assert "font-size: 0 !important" in overlay


def test_polish_module_loaded_before_overlay():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "MOBILE_VISUAL_POLISH_CSS" in app_source
    assert "inject_global_styles(MOBILE_VISUAL_POLISH_CSS)" in app_source
    # Orb overlay remains last in APP_CSS composition.
    styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert "MOBILE_INTERACTION_OVERLAY_CSS" in styles


def test_surface_levels_and_cta_tiers_present():
    polish = mobile_visual_polish_styles.MOBILE_VISUAL_POLISH_CSS
    for token in (
        ".dg-surface-l0",
        ".dg-surface-l1",
        ".dg-surface-l2",
        "min-height:var(--touch-target-min)",
    ):
        assert token in polish.replace(" ", "")
    from modules.component_family_styles import COMPONENT_FAMILY_CSS

    family = COMPONENT_FAMILY_CSS.replace(" ", "")
    for token in (
        "dg_cta_primary_",
        "dg_cta_secondary_",
        "dg_cta_tertiary_",
        "min-height:var(--touch-target-min)",
    ):
        assert token in family


def test_header_utility_rail_not_heavy_table():
    polish = mobile_visual_polish_styles.MOBILE_VISUAL_POLISH_CSS
    assert "st-key-executive_command_actions" in polish
    assert "opacity:.55" in polish.replace(" ", "") or "opacity: .55" in polish
    header = executive_command_header_styles.EXECUTIVE_COMMAND_HEADER_CSS
    assert "rgba(" not in header


def test_game_plan_primary_hierarchy():
    css = daily_gm_briefing_ui.DAILY_GM_BRIEFING_CSS
    assert "dg-game-plan-card-primary" in css
    assert "color-surface-raised" in css
    ui = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert "dg_cta_{tier}_" in ui or 'f"dg_cta_{tier}_{key_prefix}_{index}"' in ui
    assert 'else "secondary"' in ui


def test_deep_analysis_compact_nav():
    source = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")
    block = source.split("def render_home_quick_actions", 1)[1].split("\ndef ", 1)[0]
    assert "dashboard_deep_analysis_nav" in block
    assert 'type="secondary"' in block
    assert "home-quick-nav-label" not in block
    assert "Quick Actions" not in block
    # #236: empty bordered shell removed; secondary tiles not tertiary text links.
    assert "home-quick-actions-shell" not in block
    assert "dg_cta_secondary_deep_" in block
    assert "dg_cta_tertiary_deep_" not in block
    polish = mobile_visual_polish_styles.MOBILE_VISUAL_POLISH_CSS
    assert "dashboard_deep_analysis_nav" in polish
    assert "color-surface-raised" in polish
    # Must not dual-border the legacy empty shell with the nav container.
    assert (
        '[class*="dashboard_deep_analysis_nav"],.home-quick-actions-shell'
        not in polish
    )


def test_completed_draft_nesting_reduced():
    source = (ROOT / "modules" / "draft_center_ui.py").read_text(encoding="utf-8")
    completed = source.split('"Completed Draft Review"', 1)[1].split(
        "recommendations = draft_assistant.build_recommendation_buckets", 1
    )[0]
    assert "Full available board table" not in completed
    assert "st.dataframe" in completed
    assert "expanded=round_no == 1" in completed


def test_expander_canonical_classes():
    # Expander touch geometry is owned by component_family (not late polish).
    from modules import component_family_styles

    family = component_family_styles.COMPONENT_FAMILY_CSS
    assert 'div[data-testid="stExpander"]' in family
    assert "min-height:var(--touch-target-min)" in family.replace(" ", "")
    polish = mobile_visual_polish_styles.MOBILE_VISUAL_POLISH_CSS
    assert 'div[data-testid="stExpander"]' not in polish


def test_responsive_contracts_320_390():
    polish = mobile_visual_polish_styles.MOBILE_VISUAL_POLISH_CSS
    assert "@media (max-width: 760px)" in polish
    header = executive_command_header_styles.EXECUTIVE_COMMAND_HEADER_CSS
    assert "@media (max-width: 430px)" in header
    shell = (ROOT / "modules" / "application_shell_styles.py").read_text(encoding="utf-8")
    assert "@media (max-width: 760px)" in shell


def test_protobuf_budget_unchanged_ceiling():
    # APP_CSS stays near #230 baseline; polish inject is separate and compact.
    assert len(app_styles.APP_CSS) <= 422_000


def test_perceived_load_bounded_and_opt_in(monkeypatch):
    assert perceived_load.bounded_concurrency(99) == perceived_load.MAX_LOCAL_CONCURRENCY
    monkeypatch.delenv(perceived_load.PRODUCTION_OPT_IN_ENV, raising=False)
    with pytest.raises(PermissionError):
        perceived_load.bounded_concurrency(3, production=True)
    monkeypatch.setenv(perceived_load.PRODUCTION_OPT_IN_ENV, "1")
    assert perceived_load.bounded_concurrency(5, production=True) == 2


def test_perceived_load_no_secret_logging():
    row = perceived_load.sanitize_load_row(
        {
            "elapsed_ms": 12,
            "email": "a@b.com",
            "access_token": "secret",
            "note": "ok",
        }
    )
    assert "email" not in row
    assert "access_token" not in row
    assert row["note"] == "ok"
    assert "@" not in str(row)


def test_throttle_presets_and_schema():
    mid = perceived_load.throttle_preset("MID")
    assert mid["latency_ms"] == 150
    schema = perceived_load.perceived_timeline_schema()
    assert "first_useful" in schema["milestones"]
    assert "SLOW" in schema["throttle_presets"]


def test_cache_stampede_single_flight():
    game_plan_process_cache.clear_process_game_plan_caches()
    builds = {"n": 0}
    sig = "stampede-sig-231"

    def builder():
        builds["n"] += 1
        return {"ok": True}

    def worker():
        return game_plan_process_cache.get_or_build_league_context(
            signature=sig, builder=builder
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker) for _ in range(8)]
        results = [f.result() for f in as_completed(futures)]
    assert builds["n"] == 1
    assert all(row[0].get("ok") for row in results)
    report = perceived_load.stampede_report(
        signature=sig, build_count=builds["n"], concurrent_sessions=8
    )
    assert report["stampede"] is False


def test_failure_rate_reporting():
    summary = perceived_load.summarize_failure_rate(successes=9, failures=1)
    assert summary["failure_rate"] == 0.1
