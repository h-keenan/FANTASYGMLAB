import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app
import pandas as pd
from modules import player_cards
from modules.app_styles import APP_CSS


class TestPlayerCards(unittest.TestCase):
    def test_app_exposes_module_tap_helpers(self):
        self.assertTrue(hasattr(player_cards, "render_player_interaction_grid"))
        self.assertIs(
            app._render_tappable_player_html,
            player_cards.render_tappable_player_html,
        )
        self.assertIs(
            app._render_player_interaction_grid,
            player_cards.render_player_interaction_grid,
        )
        self.assertFalse(hasattr(app, "_render_player_scan_tap_grid"))

    def test_tap_grid_preserves_widget_key_and_player_id(self):
        with patch.object(
            player_cards,
            "PLAYER_SCAN_TAP_COMPONENT",
            return_value=SimpleNamespace(
                clicked={"player_id": "player-1"}
            ),
        ) as component:
            clicked = player_cards.render_player_tap_grid(
                html="<div>Player</div>",
                key_prefix="league_roster",
            )

        self.assertEqual(clicked, "player-1")
        self.assertEqual(
            component.call_args.kwargs["key"],
            "league_roster_tap_grid",
        )
        self.assertEqual(
            component.call_args.kwargs["data"],
            {"html": "<div>Player</div>", "rootId": "player-scan-tap-root"},
        )

    def test_interaction_grid_can_return_route_payload(self):
        with patch.object(
            player_cards,
            "PLAYER_SCAN_TAP_COMPONENT",
            return_value=SimpleNamespace(
                clicked={
                    "route": "trade_hub",
                    "player_id": "player-1",
                    "focus_mode": "target_player",
                }
            ),
        ):
            clicked = player_cards.render_player_interaction_grid(
                html="<div class='home-command-route-card' data-route='trade_hub'></div>",
                key_prefix="home",
            )

        self.assertEqual(clicked["route"], "trade_hub")
        self.assertEqual(clicked["player_id"], "player-1")
        self.assertEqual(clicked["focus_mode"], "target_player")

    def test_tap_bridge_targets_compact_rows_and_route_cards(self):
        component_js = Path("modules/interaction_contract.py").read_text(encoding="utf-8")
        self.assertIn(".compact-player-row[data-player-id]", component_js)
        self.assertIn(".home-command-route-card[data-route]", component_js)

    def test_tap_grid_falls_back_to_html_when_component_is_unregistered(self):
        with (
            patch.object(
                player_cards,
                "PLAYER_SCAN_TAP_COMPONENT",
                side_effect=ValueError(
                    "Component 'player_scan_tap_grid' is not registered"
                ),
            ),
            patch.object(player_cards.st, "markdown") as markdown,
        ):
            clicked = player_cards.render_player_tap_grid(
                html="<div>Player</div>",
                key_prefix="dashboard",
            )

        self.assertEqual(clicked, "")
        markdown.assert_called_once_with(
            "<div>Player</div>",
            unsafe_allow_html=True,
        )

    def test_mobile_recommendation_spacing_preserves_tap_and_reason_rules(self):
        self.assertIn(".scan-card-compact.scan-card-recommendation", APP_CSS)
        self.assertIn(".scan-card.scan-card-mobile-row", APP_CSS)
        self.assertIn("grid-template-columns: 44px minmax(0, 1fr)", APP_CSS)
        self.assertIn("-webkit-line-clamp: unset", APP_CSS)
        self.assertIn(".scan-card.scan-card-tappable", APP_CSS)
        self.assertIn("grid-template-columns: 48px minmax(0, 1fr)", APP_CSS)
        self.assertIn("--avatar-size: 44px", APP_CSS)
        self.assertIn(".scan-card-list.scan-card-list-compact", APP_CSS)
        self.assertIn("grid-template-columns: 1fr", APP_CSS)
        self.assertIn("justify-content: flex-start", APP_CSS)
        self.assertIn("min-height: 0", APP_CSS)

    def test_mobile_player_card_css_avoids_tile_dead_space_markers(self):
        compact_block_start = APP_CSS.rindex(".scan-card.scan-card-mobile-row .scan-card-main")
        compact_block = APP_CSS[
            compact_block_start : compact_block_start + APP_CSS[compact_block_start:].index("}")
        ]
        self.assertIn("align-items: flex-start", compact_block)
        self.assertIn("grid-template-columns: 44px minmax(0, 1fr)", compact_block)
        self.assertNotIn("align-items: center", compact_block)
        self.assertNotIn("grid-template-columns: 56px minmax(0, 1fr)", compact_block)

    def test_dashboard_player_card_wrapper_uses_compact_mobile_row(self):
        html = player_cards.player_scan_card_html(
            {
                "player_id": "player-home",
                "name": "Home Player",
                "position": "RB",
                "team": "GB",
                "age": 25,
                "value_score": 73,
                "player_tier": "Starter",
            },
            score_field="value_score",
            score_label="Value",
            player_display_name=lambda row: row["name"],
            format_age=lambda value: str(value),
            format_score=lambda value: str(value),
            cached_headshot_data_url=lambda _player_id: "",
            avatar_html=lambda *_args, **_kwargs: "<div class='scan-card-avatar'></div>",
            asset_initials=lambda _name: "HP",
            is_injury_status=lambda _row: False,
            compact=True,
            interactive=True,
            show_inline_reason=True,
            note_text="Actionable roster fit.",
        )
        self.assertIn("scan-card-mobile-row", html)
        self.assertIn("scan-card-recommendation", html)

    def test_mobile_player_card_forced_row_override_is_present(self):
        self.assertIn("aspect-ratio: auto !important", APP_CSS)
        self.assertIn("height: auto !important", APP_CSS)
        self.assertIn("min-height: 0 !important", APP_CSS)
        self.assertIn("grid-template-columns: 44px minmax(0, 1fr) !important", APP_CSS)
        self.assertIn("justify-content: flex-start !important", APP_CSS)
        self.assertIn("position: static !important", APP_CSS)
        self.assertIn(".scan-card.scan-card-mobile-row .scan-card-copy::before", APP_CSS)
        self.assertIn("display: none !important", APP_CSS)

    def test_mobile_row_cards_do_not_use_bottom_push_layout(self):
        row_start = APP_CSS.index(".scan-card.scan-card-mobile-row .scan-card-copy")
        row_block = APP_CSS[row_start : row_start + 2600]
        self.assertIn(".scan-card.scan-card-mobile-row .scan-card-copy", row_block)
        self.assertIn("justify-content: flex-start !important", row_block)
        self.assertIn("min-height: 0 !important", row_block)
        self.assertNotIn("justify-content: space-between", row_block)
        self.assertNotIn("margin-top: auto", row_block)
        self.assertNotIn("min-height: calc(var(--avatar-size)", row_block)

    def test_compact_recommendation_card_keeps_tap_metadata_and_reason(self):
        html = player_cards.player_scan_card_html(
            {
                "player_id": "player-1",
                "name": "Test Player",
                "position": "WR",
                "team": "DAL",
                "age": 24,
                "value_score": 70,
                "market_score": 68,
                "opportunity_score": 65,
                "player_tier": "Contributor",
            },
            score_field="value_score",
            score_label="Value",
            player_display_name=lambda row: row["name"],
            format_age=lambda value: str(value),
            format_score=lambda value: str(value),
            cached_headshot_data_url=lambda _player_id: "",
            avatar_html=lambda *_args, **_kwargs: "<div class='scan-card-avatar'></div>",
            asset_initials=lambda _name: "TP",
            is_injury_status=lambda _row: False,
            status_label="Trade Candidate",
            note_text="Surplus depth with enough market value to shop.",
            compact=True,
            interactive=True,
            show_inline_reason=True,
        )

        self.assertIn("data-player-id='player-1'", html)
        self.assertIn("scan-card-tappable", html)
        self.assertIn("scan-card-mobile-row", html)
        self.assertIn("scan-card-recommendation", html)
        self.assertIn("Surplus depth with enough market value to shop.", html)

    def test_compact_player_row_renders_metadata_reason_and_tap(self):
        html = player_cards.compact_player_row_html(
            {
                "player_id": "player-row",
                "name": "Row Player",
                "position": "RB",
                "team": "SEA",
                "age": 23,
                "value_score": 74,
                "player_tier": "Starter",
            },
            score_field="value_score",
            score_label="Value",
            player_display_name=lambda row: row["name"],
            format_age=lambda value: str(value),
            format_score=lambda value: str(value),
            cached_headshot_data_url=lambda _player_id: "",
            avatar_html=lambda *_args, **_kwargs: "<div class='compact-player-avatar'></div>",
            asset_initials=lambda _name: "RP",
            is_injury_status=lambda _row: False,
            status_label="Trade Candidate",
            note_text="Clear surplus player with market value.",
            interactive=True,
        )

        self.assertIn("compact-player-row", html)
        self.assertIn("dg-player-portrait", html)
        self.assertIn("compact-player-avatar", html)
        self.assertIn("compact-player-body", html)
        self.assertIn("compact-player-badges", html)
        self.assertIn("compact-player-reason", html)
        self.assertIn("Row Player", html)
        self.assertIn("Value 74", html)
        self.assertIn("player-position-badge", html)
        self.assertIn(">RB<", html)
        self.assertIn("SEA · Age 23", html)
        self.assertNotIn("RB | SEA | Age 23", html)
        self.assertIn("Clear surplus player with market value.", html)
        self.assertIn("data-player-id='player-row'", html)
        self.assertIn("scan-card-tappable", html)

    def test_design_system_compact_row_uses_canonical_card_and_status_badge(self):
        html = player_cards.compact_player_row_html(
            {
                "player_id": "player-row",
                "name": "Row Player",
                "position": "RB",
                "team": "SEA",
                "age": 23,
                "value_score": 74,
            },
            score_field="value_score",
            score_label="Value",
            player_display_name=lambda row: row["name"],
            format_age=lambda value: str(value),
            format_score=lambda value: str(value),
            cached_headshot_data_url=lambda _player_id: "",
            avatar_html=lambda *_args, **_kwargs: "<div class='compact-player-avatar'></div>",
            asset_initials=lambda _name: "RP",
            is_injury_status=lambda _row: False,
            status_label="Starter",
            interactive=True,
            design_system=True,
        )

        self.assertIn("dg-ui-player-card", html)
        self.assertIn("dg-ui-badge", html)
        self.assertIn("Information status: Starter", html)
        self.assertNotIn("player-status-pill", html)

    def test_player_metadata_does_not_duplicate_position_or_slot_position(self):
        html = player_cards.compact_player_row_html(
            {
                "player_id": "player-row",
                "name": "Row Player",
                "position": "WR",
                "slot": "WR/RB",
                "team": "CAR",
                "age": 24,
                "value_score": 74,
                "player_tier": "Starter",
            },
            score_field="value_score",
            score_label="Value",
            player_display_name=lambda row: row["name"],
            format_age=lambda value: str(value),
            format_score=lambda value: str(value),
            cached_headshot_data_url=lambda _player_id: "",
            avatar_html=lambda *_args, **_kwargs: "<div class='compact-player-avatar'></div>",
            asset_initials=lambda _name: "RP",
            is_injury_status=lambda _row: False,
            show_slot=True,
        )

        self.assertIn("player-position-badge", html)
        self.assertIn(">WR<", html)
        self.assertIn("CAR · Age 24", html)
        self.assertNotIn("WR/RB | WR | CAR", html)
        self.assertNotIn("WR | CAR | Age 24", html)

    def test_healthy_player_value_has_no_injury_ring(self):
        html = player_cards.injury_adjusted_value_html(
            "Value",
            "74",
            {"injury_level": "healthy"},
            css_class="compact-player-value",
        )

        self.assertIn("compact-player-value", html)
        self.assertNotIn("injury-adjustment-ring", html)
        self.assertNotIn("player-value-injury-adjusted", html)

    def test_minor_injury_value_uses_subtle_marker(self):
        html = player_cards.injury_adjusted_value_html(
            "Value",
            "74",
            {"injury_level": "minor"},
            css_class="compact-player-value",
        )

        self.assertIn("player-value-injury-minor", html)
        self.assertIn("injury-adjustment-ring", html)
        self.assertIn("Minor injury value note", html)

    def test_major_injury_value_uses_stronger_marker(self):
        html = player_cards.injury_adjusted_value_html(
            "Value",
            "74",
            {"injury_level": "major"},
            css_class="compact-player-value",
        )

        self.assertIn("player-value-injury-major", html)
        self.assertIn("Major injury risk affecting value", html)

    def test_unknown_injury_value_uses_meaningful_marker(self):
        html = player_cards.injury_adjusted_value_html(
            "Value",
            "74",
            {"injury_level": "unknown"},
            css_class="compact-player-value",
        )

        self.assertIn("player-value-injury-moderate", html)
        self.assertIn("Injury adjusted", html)

    def test_player_value_injury_marker_css_exists(self):
        for selector in [
            ".player-value-injury-adjusted",
            ".injury-adjustment-ring",
            ".player-value-injury-minor .injury-adjustment-ring",
            ".player-value-injury-moderate .injury-adjustment-ring",
            ".player-value-injury-major .injury-adjustment-ring",
        ]:
            self.assertIn(selector, APP_CSS)
        moderate_start = APP_CSS.index(".player-value-injury-moderate .injury-adjustment-ring")
        moderate_end = APP_CSS.index(".player-value-injury-major .injury-adjustment-ring")
        moderate_block = APP_CSS[moderate_start:moderate_end]
        major_start = APP_CSS.index(".player-value-injury-major .injury-adjustment-ring")
        major_end = APP_CSS.index(".compact-player-meta")
        major_block = APP_CSS[major_start:major_end]
        self.assertIn("248, 113, 113", moderate_block)
        self.assertIn("239, 68, 68", major_block)

    def test_compact_player_row_css_has_no_tile_height_rules(self):
        row_start = APP_CSS.index(".compact-player-row {")
        row_block = APP_CSS[row_start : row_start + APP_CSS[row_start:].index("}")]
        self.assertIn("height: auto", row_block)
        self.assertIn("min-height: 0", row_block)
        self.assertNotIn("justify-content: space-between", row_block)
        self.assertNotIn("margin-top: auto", row_block)
        self.assertNotIn("min-height: calc", row_block)

    def test_quick_view_uses_rectangular_detail_panel_classes(self):
        source = Path("app.py").read_text(encoding="utf-8")
        pqv = Path("modules/player_quick_view.py").read_text(encoding="utf-8")
        for marker in [
            "dg-quick-view-panel",
            "player-quick-view-header-band",
            "DossierSnapshot",
            "STATS",
            "pqv-model-matrix",
            "pqv-model-cell",
        ]:
            self.assertTrue(marker in source or marker in pqv, marker)

        for selector in [
            ".dg-quick-view-panel.player-quick-view-shell",
            ".player-quick-view-header-band.player-quick-view-hero",
            ".player-quick-view-detail-list",
            ".player-quick-view-detail-row",
            ".player-quick-view-detail-label",
            ".player-quick-view-detail-value",
            ".player-dossier-snapshot",
        ]:
            self.assertIn(selector, APP_CSS)

        self.assertIn('div[data-testid="stDialog"] div[role="dialog"]', APP_CSS)
        self.assertIn("border-radius: var(--radius-pill) !important", APP_CSS)
        self.assertIn("border-radius: 2px !important", APP_CSS)
        self.assertIn("grid-template-columns: minmax(5.6rem, 0.36fr) minmax(0, 1fr)", APP_CSS)

    def test_quick_view_modal_uses_compact_2k_stat_table_rules(self):
        for selector in [
            ".player-detail-panel",
            ".player-detail-header",
            ".player-detail-identity",
            ".player-detail-row",
            ".player-detail-stat-table",
            ".player-detail-section",
            ".player-quick-view-stat-section",
            ".player-quick-view-stat-grid",
            ".player-quick-view-stat-row",
            ".player-quick-view-recommendation-card",
            'div[data-testid="stDialog"] .summary-tile-grid',
            'div[data-testid="stDialog"] .player-detail-score-row',
            'div[data-testid="stDialog"] .player-quick-view-detail-row',
            'div[data-testid="stDialog"] .player-quick-view-stat-row',
        ]:
            self.assertIn(selector, APP_CSS)

        self.assertIn("Compact 2K player detail panels", APP_CSS)
        self.assertIn("grid-template-columns: 1fr !important", APP_CSS)
        self.assertIn("grid-template-columns: minmax(5.25rem, 0.36fr) minmax(0, 1fr) !important", APP_CSS)
        self.assertIn("word-break: keep-all !important", APP_CSS)
        self.assertIn("overflow-wrap: normal !important", APP_CSS)
        self.assertIn("repeat(auto-fit, minmax(94px, 1fr)) !important", APP_CSS)
        self.assertIn("repeat(2, minmax(0, 1fr)) !important", APP_CSS)
        self.assertIn('div[data-testid="stDialog"] .player-quick-view-stat-note', APP_CSS)
        self.assertIn('div[data-testid="stDialog"] .summary-tile-affordance', APP_CSS)
        self.assertIn("display: none !important", APP_CSS)
        self.assertIn("--avatar-size: 58px !important", APP_CSS)
        self.assertIn('div[data-testid="stDialog"] .section-note', APP_CSS)

    def test_quick_view_avatar_is_bounded_inside_modal(self):
        from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS

        for marker in [
            'div[data-testid="stDialog"] .pqv-hero-portrait',
            'div[data-testid="stDialog"] .pqv-hero-portrait img',
            "--pqv-portrait-size",
            "align-self:start !important",
            "object-fit:cover !important",
        ]:
            self.assertIn(marker, PLAYER_QUICK_VIEW_CSS)

        for marker in [
            'div[data-testid="stDialog"] .player-detail-avatar:not(.player-quick-view-avatar) img',
            "flex: 0 0 var(--avatar-size) !important",
            "width: var(--avatar-size) !important",
            "height: var(--avatar-size) !important",
            "max-width: var(--avatar-size) !important",
            "max-height: var(--avatar-size) !important",
            "flex: 0 0 58px !important",
            "height: 58px !important",
            "max-height: 58px !important",
            "max-width: 58px !important",
            "overflow: hidden !important",
            "object-fit: cover !important",
        ]:
            self.assertIn(marker, APP_CSS)
        self.assertNotIn(
            'div[data-testid="stDialog"] .player-detail-avatar.player-quick-view-avatar img',
            APP_CSS,
        )

        self.assertIn(".scan-card-avatar img", APP_CSS)
        self.assertIn(".compact-player-avatar img", APP_CSS)

    def test_avatar_polish_separates_team_logos_from_player_headshots(self):
        for selector in [
            ".team-logo-wrap img",
            ".league-team-avatar img",
            ".team-card-avatar img",
            ".dg-ranked-logo img",
        ]:
            self.assertIn(selector, APP_CSS)
        logo_block_start = APP_CSS.rindex(".sidebar-logo-wrap img,")
        logo_block = APP_CSS[logo_block_start : logo_block_start + 900]
        self.assertIn("object-position: center center !important", logo_block)

        player_block_start = APP_CSS.rindex("Shared player headshots")
        player_block = APP_CSS[player_block_start : player_block_start + 2200]
        self.assertIn(".dg-player-headshot", player_block)
        self.assertIn("object-fit: cover !important", player_block)
        self.assertIn("object-position: var(--dg-headshot-focus-x, 50%) var(--dg-headshot-focus) !important", player_block)
        self.assertIn("--dg-headshot-focus: 18%", player_block)
        self.assertIn("--dg-headshot-focus: 20%", player_block)
        self.assertIn("--dg-headshot-focus: 22%", player_block)
        self.assertNotIn("object-fit: contain !important", player_block)
        self.assertNotIn("player-id", player_block)

    def test_app_scan_renderer_passes_compact_row_builder(self):
        with patch.object(player_cards, "render_player_scan_cards") as renderer:
            app.render_player_scan_cards(
                pd.DataFrame(
                    [
                        {
                            "player_id": "player-1",
                            "name": "Test Player",
                            "position": "WR",
                            "team": "DAL",
                            "age": 24,
                            "value_score": 70,
                        }
                    ]
                ),
                score_field="value_score",
                title="Drop Candidates",
                note="Lowest utility cuts.",
                compact=True,
                show_inline_reason=True,
                enable_quick_view=True,
            )

        self.assertIs(renderer.call_args.kwargs["compact_row_builder"], app._compact_player_row_html)

    def test_app_scan_renderer_forwards_design_system_contract(self):
        with patch.object(player_cards, "render_player_scan_cards") as renderer:
            app.render_player_scan_cards(
                pd.DataFrame([{"player_id": "player-1"}]),
                score_field="value_score",
                title="QB",
                note="Projected starter group.",
                compact=True,
                design_system=True,
                show_header=False,
            )

        self.assertTrue(renderer.call_args.kwargs["design_system"])
        self.assertFalse(renderer.call_args.kwargs["show_header"])

    def test_core_and_untouchable_compact_scans_use_compact_rows(self):
        source = pd.DataFrame(
            [
                {
                    "player_id": "core-1",
                    "name": "Core Player",
                    "position": "WR",
                    "team": "DAL",
                    "age": 24,
                    "value_score": 88,
                }
            ]
        )
        compact_builder = Mock(return_value="<div class='compact-player-row'>Core</div>")
        scan_builder = Mock(return_value="<div class='scan-card'>Core</div>")
        with patch.object(player_cards.st, "markdown") as markdown:
            player_cards.render_player_scan_cards(
                source,
                score_field="value_score",
                title="Core Assets",
                note="Core players.",
                league_score_label=lambda _field: "Value",
                player_display_name=lambda row: row["name"],
                card_html_builder=scan_builder,
                compact_row_builder=compact_builder,
                render_tappable_player_html_callback=lambda **_kwargs: "",
                open_player_quick_view=lambda *_args, **_kwargs: None,
                render_recommendation_feedback=lambda **_kwargs: None,
                compact=True,
                status_label="Core Asset",
            )

        compact_builder.assert_called_once()
        scan_builder.assert_not_called()
        html_calls = "".join(call.args[0] for call in markdown.call_args_list)
        self.assertIn("compact-player-row", html_calls)

    def test_all_compact_scan_sections_use_compact_rows_when_builder_exists(self):
        source = pd.DataFrame(
            [
                {
                    "player_id": "starter-1",
                    "name": "Starter Player",
                    "position": "RB",
                    "team": "DET",
                    "age": 24,
                    "value_score": 82,
                }
            ]
        )
        compact_builder = Mock(return_value="<div class='compact-player-row'>Starter</div>")
        scan_builder = Mock(return_value="<div class='scan-card'>Starter</div>")
        with patch.object(player_cards.st, "markdown"):
            player_cards.render_player_scan_cards(
                source,
                score_field="value_score",
                title="Projected Starters",
                note="Starter players.",
                league_score_label=lambda _field: "Value",
                player_display_name=lambda row: row["name"],
                card_html_builder=scan_builder,
                compact_row_builder=compact_builder,
                render_tappable_player_html_callback=lambda **_kwargs: "",
                open_player_quick_view=lambda *_args, **_kwargs: None,
                render_recommendation_feedback=lambda **_kwargs: None,
                compact=True,
                status_label="Starter",
            )

        compact_builder.assert_called_once()
        scan_builder.assert_not_called()

    def test_injured_player_card_uses_badge_not_name_prefix(self):
        html = player_cards.player_scan_card_html(
            {
                "player_id": "player-2",
                "name": "INJ Test Player",
                "position": "RB",
                "team": "NYG",
                "age": 23,
                "value_score": 72,
                "market_score": 70,
                "opportunity_score": 66,
                "player_tier": "Contributor",
                "injury_level": "major",
                "status": "IR",
            },
            score_field="value_score",
            score_label="Value",
            player_display_name=lambda row: app.player_display_name(row),
            format_age=lambda value: str(value),
            format_score=lambda value: str(value),
            cached_headshot_data_url=lambda _player_id: "",
            avatar_html=lambda *_args, **_kwargs: "<div class='scan-card-avatar'></div>",
            asset_initials=lambda _name: "TP",
            is_injury_status=lambda _row: True,
            compact=True,
            interactive=True,
        )

        self.assertIn("Test Player", html)
        self.assertNotIn(">INJ Test Player<", html)
        self.assertIn("Injury Risk", html)


if __name__ == "__main__":
    unittest.main()
