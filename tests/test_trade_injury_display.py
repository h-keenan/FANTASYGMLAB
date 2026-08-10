import time
import unittest
import re
from pathlib import Path

import app
from modules import workspace_ui


class TestTradeInjuryDisplay(unittest.TestCase):
    def _elite_asset(self, **overrides):
        asset = {
            "asset_type": "player",
            "player_id": "fixture-player",
            "label": "Fixture Player",
            "name": "Fixture Player",
            "position": "WR",
            "team": "NYG",
            "status": "Active",
            "injury_status": "",
            "injury_level": "healthy",
            "news_updated": int(time.time() * 1000),
            "player_tier": "Elite",
            "opportunity_label": "Elite Opportunity",
            "score": 9000,
        }
        asset.update(overrides)
        return asset

    def test_injured_elite_asset_gets_qualified_opportunity_and_confidence(self):
        injured_asset = self._elite_asset(
            status="Injured Reserve",
            injury_status="season-ending",
            injury_level="major",
        )
        idea = {
            "receive_assets": [injured_asset],
            "trade_confidence_label": "High",
            "trade_confidence_summary": "Strong fit and partner motivation.",
        }

        asset_html = app._trade_asset_html(injured_asset)

        self.assertIn("Elite Opportunity (Health Risk)", asset_html)
        self.assertIn("Major Injury Risk", asset_html)
        self.assertIn("injury-discount dynasty target", asset_html)
        self.assertEqual(
            app._trade_display_confidence_label(idea),
            "High (Major Health Risk)",
        )
        self.assertIn("Health caveat", app._trade_confidence_reason(idea))

    def test_healthy_elite_asset_keeps_normal_opportunity_language(self):
        healthy_asset = self._elite_asset()
        idea = {
            "receive_assets": [healthy_asset],
            "trade_confidence_label": "High",
            "trade_confidence_summary": "Strong fit and partner motivation.",
        }

        asset_html = app._trade_asset_html(healthy_asset)

        self.assertIn(">Elite Opportunity<", asset_html)
        self.assertNotIn("Elite Opportunity (Health Risk)", asset_html)
        self.assertNotIn("Major Injury Risk", asset_html)
        self.assertEqual(app._trade_display_confidence_label(idea), "High")

    def test_minor_injury_does_not_add_trade_hub_risk_badge(self):
        minor_asset = self._elite_asset(
            status="Questionable",
            injury_status="limited",
            injury_level="minor",
        )

        asset_html = app._trade_asset_html(minor_asset)

        self.assertNotIn("Injury Watch", asset_html)
        self.assertNotIn("Health Risk", asset_html)
        self.assertIn(">Elite Opportunity<", asset_html)

    def test_feedback_popovers_are_not_globally_fixed_on_mobile(self):
        self.assertIsNone(
            re.search(
                r'(?ms)^\s*div\[data-testid="stPopover"\]\s*\{[^}]*position:\s*fixed',
                app.APP_CSS,
            )
        )
        self.assertIn(
            'div[class*="st-key-mobile_gm_sheet_trigger_"] [data-testid="stButton"] button',
            app.APP_CSS,
        )

    def test_mobile_gm_nav_is_bottom_left_and_content_safe(self):
        self.assertIn("padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 13.8rem)", app.APP_CSS)
        self.assertIn("bottom: max(16px, env(safe-area-inset-bottom))", app.APP_CSS)
        self.assertIn("min-height: 34px", app.APP_CSS)
        self.assertIn("left: max(16px, env(safe-area-inset-left))", app.APP_CSS)
        self.assertIn("right: auto", app.APP_CSS)
        self.assertIn("height: auto !important", app.APP_CSS)
        self.assertIn("overflow: visible !important", app.APP_CSS)
        self.assertIn("border-radius: 0 2px 2px 0", app.APP_CSS)
        self.assertIn("mobile-gm-sheet-marker", app.APP_CSS)
        self.assertIn("mobile-gm-floating-trigger-marker", app.APP_CSS)
        overlay = Path("modules/mobile_interaction_overlay_styles.py").read_text(encoding="utf-8")
        self.assertIn("text-indent: -9999px !important", overlay)
        self.assertIn("overflow: hidden !important", overlay)
        self.assertIn(
            'div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker)',
            app.APP_CSS,
        )
        self.assertIn(
            'div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker) [data-testid="stButton"]',
            app.APP_CSS,
        )
        self.assertIn("pointer-events: auto !important", app.APP_CSS)

    def test_shared_mobile_visual_system_classes_exist(self):
        for selector in [
            ".app-card",
            ".app-section",
            ".app-section-title",
            ".app-subtitle",
            ".app-chip",
            ".app-chip-warning",
            ".app-chip-success",
            ".app-chip-muted",
            ".app-empty-state",
            ".app-degraded-state",
        ]:
            self.assertIn(selector, app.APP_CSS)

        self.assertIn(".draft-review-pick-card", app.APP_CSS)
        self.assertIn(".draft-review-chip.unmatched", app.APP_CSS)
        self.assertIn(".launch-league-chip", app.APP_CSS)
        self.assertIn(".news-badge-warning", app.APP_CSS)
        self.assertIn('div[class*="st-key-mobile_gm_sheet_trigger_"]', app.APP_CSS)
        self.assertNotIn('div[class*="st-key-mobile_gm_command_menu_"]', app.APP_CSS)

    def test_next_gen_design_system_tokens_exist(self):
        for token in [
            "--dg-shell-black",
            "--dg-shell-graphite",
            "--dg-glass-panel",
            "--dg-radius-card",
            "--dg-radius-control",
            "--dg-radius-chip",
        ]:
            self.assertIn(token, app.APP_CSS)

        self.assertIn(".app-glass-panel", app.APP_CSS)
        self.assertIn(".dg-glass-panel", app.APP_CSS)
        self.assertIn("clip-path: polygon", app.APP_CSS)
        self.assertIn("linear-gradient(180deg, var(--dg-shell-black)", app.APP_CSS)

    def test_visible_card_classes_use_last_mile_angular_system(self):
        for selector in [
            ".home-command-card",
            ".team-identity-card",
            ".summary-tile",
            ".trade-idea-card",
            ".free-agent-card",
            ".draft-review-pick-card",
        ]:
            self.assertIn(selector, app.APP_CSS)

        self.assertIn(".team-identity-card", app.APP_CSS)
        self.assertIn(".home-command-hero", app.APP_CSS)
        self.assertIn("border-radius: 8px !important", app.APP_CSS)
        self.assertIn("border-color: rgba(226, 232, 240, 0.09) !important", app.APP_CSS)
        self.assertIn("inset 3px 0 0 var(--player-accent", app.APP_CSS)

    def test_normal_card_top_strips_are_suppressed_but_alerts_remain(self):
        self.assertIn(".home-command-card::after", app.APP_CSS)
        self.assertIn("display: none !important", app.APP_CSS)
        self.assertIn(".dg-alert-banner::after", app.APP_CSS)
        self.assertIn("display: block !important", app.APP_CSS)
        self.assertIn(".roster-limit-strip", app.APP_CSS)
        self.assertIn(".roster-limit-stat", app.APP_CSS)

    def test_mobile_slab_layout_overrides_visible_pages(self):
        self.assertIn("padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 13.8rem)", app.APP_CSS)
        self.assertIn("border-radius: 2px !important", app.APP_CSS)
        self.assertIn("border-radius: 4px !important", app.APP_CSS)
        self.assertIn("box-shadow: none !important", app.APP_CSS)
        self.assertIn("clip-path: none !important", app.APP_CSS)
        for selector in [
            ".home-command-card",
            ".team-identity-card",
            ".trade-idea-card",
            ".free-agent-summary-card",
            ".draft-review-pick-card",
            ".decision-panel",
        ]:
            self.assertIn(selector, app.APP_CSS)

    def test_mobile_panel_list_rhythm_overrides_card_stacks(self):
        self.assertIn(".dg-panel-list", app.APP_CSS)
        self.assertIn(".dg-panel-list", app.APP_CSS)
        self.assertIn(".dg-panel-row", app.APP_CSS)
        self.assertIn("flex-direction: column !important", app.APP_CSS)
        self.assertIn("border-width: 0 0 1px 0 !important", app.APP_CSS)
        self.assertIn("grid-template-columns: minmax(3.2rem, auto) minmax(0, 1fr)", app.APP_CSS)
        self.assertIn("display: contents !important", app.APP_CSS)

    def test_black_white_theme_tokens_and_semantic_classes_exist(self):
        for token in [
            "--dg-theme-bg",
            "--dg-theme-shell",
            "--dg-theme-surface-primary",
            "--dg-theme-surface-secondary",
            "--dg-theme-surface-raised",
            "--dg-theme-surface-muted",
            "--dg-theme-accent-silver",
            "--dg-theme-diagnostic",
        ]:
            self.assertIn(token, app.APP_CSS)

        for selector in [
            ".dg-theme-shell",
            ".dg-surface-primary",
            ".dg-surface-secondary",
            ".dg-semantic-critical",
            ".dg-semantic-action",
            ".dg-semantic-opportunity",
            ".dg-semantic-caution",
            ".dg-semantic-muted",
            ".dg-semantic-diagnostic",
            ".dg-semantic-grade-a",
            ".dg-semantic-grade-b",
            ".dg-semantic-grade-c",
            ".dg-semantic-grade-d",
        ]:
            self.assertIn(selector, app.APP_CSS)

        self.assertIn("linear-gradient(180deg, var(--dg-theme-bg)", app.APP_CSS)

    def test_visible_components_receive_semantic_treatments(self):
        for selector in [
            ".dg-alert-warning",
            ".roster-limit-stat-danger",
            ".home-command-card-trade",
            ".home-command-card-waiver",
            ".home-command-card-risk",
            ".home-command-card-need",
            ".decision-panel-strength",
            ".decision-panel-risk",
            ".trade-idea-positive",
            ".trade-idea-negative",
            ".free-agent-card-tone-core",
            ".free-agent-card-tone-drop",
            ".app-degraded-state",
        ]:
            self.assertIn(selector, app.APP_CSS)

        self.assertIn("border-left: 3px solid var(--dg-theme-danger)", app.APP_CSS)
        self.assertIn("border-left: 3px solid var(--dg-theme-opportunity)", app.APP_CSS)
        self.assertIn("border-left: 3px solid var(--dg-theme-diagnostic)", app.APP_CSS)
        self.assertIn(".draft-review-grade.grade-strong", app.APP_CSS)
        self.assertIn(".draft-review-grade.grade-watch", app.APP_CSS)
        self.assertIn(".draft-review-grade.grade-risk", app.APP_CSS)

    def test_mobile_gm_orb_uses_single_all_destinations_sheet(self):
        source = open("app.py", encoding="utf-8").read()
        for marker in [
            "mobile-gm-destination-panel",
            "gm_orb_floating_trigger_html()",
            "mobile_gm_sheet_trigger_",
            "mobile_gm_sheet_open_",
            "mobile_sheet_nav_",
        ]:
            self.assertIn(marker, source)
        self.assertNotIn("mobile-gm-command-panel", source)
        self.assertNotIn("mobile_gm_nav_", source)
        self.assertNotIn("mobile-gm-command-row", source)
        self.assertNotIn("is-active", source)
        self.assertNotIn("mobile-gm-command-list", source)
        self.assertNotIn("st.popover(\"GM\"", source)
        self.assertNotIn("Open GM command menu", source)

        for selector in [
            ".mobile-gm-destination-panel",
            'div[class*="st-key-mobile_gm_sheet_trigger_"] [data-testid="stButton"] button',
        ]:
            self.assertIn(selector, app.APP_CSS)

        self.assertIn("max-width: min(82vw, 286px)", app.APP_CSS)
        self.assertIn("border-left: 3px solid transparent", app.APP_CSS)
        self.assertIn("border-left-color: var(--dg-theme-accent-cyan)", app.APP_CSS)
        self.assertIn('key=f"mobile_sheet_nav_{page.key}"', source)

    def test_smoky_slab_tokens_and_player_image_centering_exist(self):
        for token in [
            "--dg-smoke-dark",
            "--dg-smoke-mid",
            "--dg-smoke-ash",
            "--dg-smoke-border",
            "--dg-smoke-light-ready",
            "--dg-smoke-light-border-ready",
        ]:
            self.assertIn(token, app.APP_CSS)

        for selector in [
            ".dg-smoky-slab",
            ".dg-smoky-panel",
            ".home-command-card",
            ".trade-idea-card",
            ".free-agent-card",
            ".draft-review-pick-card",
        ]:
            self.assertIn(selector, app.APP_CSS)

        self.assertIn(".scan-card-avatar img", app.APP_CSS)
        self.assertIn(".compact-player-avatar img", app.APP_CSS)
        self.assertIn(".player-quick-view-avatar img", app.APP_CSS)
        self.assertIn("object-fit: cover !important", app.APP_CSS)
        self.assertIn("object-position: center center !important", app.APP_CSS)

    def test_mobile_alignment_command_rows_and_detail_consistency_exist(self):
        self.assertIn("--dg-player-image-position: center 42%", app.APP_CSS)
        self.assertIn("object-position: var(--dg-player-image-position)", app.APP_CSS)
        self.assertIn(".team-logo-wrap img", app.APP_CSS)
        self.assertIn(".league-team-avatar img", app.APP_CSS)

        for selector in [
            ".app-section-title",
            ".player-quick-view-detail-label",
            ".player-quick-view-detail-value",
            ".player-quick-view-detail-note",
        ]:
            self.assertIn(selector, app.APP_CSS)

        self.assertIn("justify-content: flex-start !important", app.APP_CSS)
        self.assertIn('content: "›"', app.APP_CSS)
        self.assertIn('content: "▌"', app.APP_CSS)
        self.assertIn(".player-quick-view-panel-body", app.APP_CSS)
        self.assertIn("gap: 0.44rem !important", app.APP_CSS)

    def test_mobile_section_hierarchy_classes_and_mappings_exist(self):
        for selector in [
            ".dg-section-command",
            ".dg-section-alert",
            ".dg-section-primary-action",
            ".dg-section-opportunity-list",
            ".dg-section-metrics",
            ".dg-section-secondary",
            ".dg-section-diagnostic",
            ".dg-command-row",
            ".dg-ranked-row",
        ]:
            self.assertIn(selector, app.APP_CSS)

        for visible_selector in [
            ".home-command-card-risk",
            ".roster-limit-strip",
            ".home-command-card-wide",
            ".home-command-card-trade",
            ".home-command-card-waiver",
            ".summary-tile",
            ".dg-ranked-row",
            ".dg-ranked-row--top",
        ]:
            self.assertIn(visible_selector, app.APP_CSS)

        self.assertIn("border-left: 4px solid rgba(245, 158, 11, 0.78)", app.APP_CSS)
        self.assertIn("border-left: 5px solid var(--dg-theme-accent-cyan)", app.APP_CSS)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", app.APP_CSS)
        self.assertNotIn(".team-rank-card", app.APP_CSS)
        self.assertNotIn(".power-row", app.APP_CSS)

    def test_mobile_visual_hierarchy_presets_are_mapped_to_visible_sections(self):
        self.assertIn(".dg-preset-command", app.APP_CSS)
        for selector in [
            ".dg-preset-command",
            ".dg-preset-alert",
            ".dg-preset-primary-action",
            ".dg-preset-opportunity",
            ".dg-preset-player-list",
            ".dg-preset-metrics",
            ".dg-preset-secondary",
        ]:
            self.assertIn(selector, app.APP_CSS)

        for visible_mapping in [
            ".home-command-shell",
            ".dg-alert-warning",
            ".home-command-card-wide",
            ".home-command-card-trade",
            ".home-command-card-waiver",
            ".decision-panel",
            ".free-agent-list",
            ".scan-card-list",
            ".summary-tile",
            ".roster-limit-stat",
            ".summary-tile-grid-compact .summary-tile-power",
            ".trade-idea-secondary",
        ]:
            self.assertIn(visible_mapping, app.APP_CSS)

        self.assertIn("border-left: 4px solid rgba(248, 250, 252, 0.64)", app.APP_CSS)
        self.assertIn("border-left: 5px solid rgba(103, 232, 249, 0.88)", app.APP_CSS)
        self.assertIn("border-left: 3px solid rgba(45, 212, 191, 0.74)", app.APP_CSS)
        self.assertIn("border-left: 2px solid rgba(229, 231, 235, 0.15)", app.APP_CSS)

    def test_premium_lock_styles_and_page_gates_are_test_mode_only(self):
        source = open("app.py", encoding="utf-8").read()
        for marker in [
            "current_user_is_premium",
            "render_premium_lock",
            "Premium Trade Hub",
            "Premium Waivers",
            "Premium Dashboard",
            "Premium My Team",
        ]:
            self.assertIn(marker, source)

        for selector in [
            ".premium-lock",
            ".premium-badge",
            ".premium-lock-title",
            ".premium-lock-body",
        ]:
            self.assertIn(selector, app.APP_CSS)

        self.assertIn("Free and Premium plan preview for FantasyGM Lab.", source)
        for blocked in ("sk_live_", "pk_live_", "payment link", "Subscribe now"):
            self.assertNotIn(blocked.casefold(), source.casefold())

    def test_semantic_glyph_system_is_applied_to_visible_surfaces(self):
        self.assertEqual(workspace_ui.semantic_icon("trade_hub"), "$")
        self.assertEqual(workspace_ui.semantic_icon("waivers"), "+")
        self.assertEqual(workspace_ui.semantic_icon("draft_summary"), "#")
        self.assertIn("SEMANTIC_ICONS", open("modules/workspace_ui.py", encoding="utf-8").read())

        source = open("app.py", encoding="utf-8").read()
        self.assertIn("Where to go", source)
        self.assertNotIn("_mobile_command_label", source)
        self.assertNotIn("return f\"{glyph}  {label}\"", source)

        for marker in [
            ".dg-semantic-icon",
            ".sr-only",
            ".section-kicker .dg-semantic-icon",
            ".home-command-card-label .dg-semantic-icon",
            ".summary-tile-label .dg-semantic-icon",
            ".decision-panel-label .dg-semantic-icon",
            ".roster-limit-stat .dg-semantic-icon",
            "h3 .dg-semantic-icon",
        ]:
            self.assertIn(marker, app.APP_CSS)

        self.assertIn("dg-semantic-icon", open("modules/my_team_ui.py", encoding="utf-8").read())
        self.assertIn(
            "ui_primitives.section_header_html",
            open("modules/waivers_ui.py", encoding="utf-8").read(),
        )


if __name__ == "__main__":
    unittest.main()
