import unittest
import inspect
from pathlib import Path
from unittest.mock import Mock, patch

import app
from modules import trade_hub_ui


class TestTradeHubUI(unittest.TestCase):
    def test_trade_strategy_selector_public_export_is_available(self):
        self.assertTrue(hasattr(trade_hub_ui, "render_trade_strategy_selector"))
        self.assertIs(
            app.trade_hub_ui.render_trade_strategy_selector,
            trade_hub_ui.render_trade_strategy_selector,
        )

    def test_app_trade_builder_binding_supports_team_archetype(self):
        self.assertIs(app.build_trade_ideas, app.trade_ideas_module.build_trade_ideas)
        self.assertIn(
            "team_archetype",
            inspect.signature(app.build_trade_ideas).parameters,
        )

    def test_strategy_selector_exposes_required_options(self):
        self.assertEqual(
            trade_hub_ui.TRADE_STRATEGY_OPTIONS,
            (
                "Auto / Best guess",
                "Contender / Win-now",
                "Rebuild / Tank",
                "Retool",
                "Balanced",
                "Young powerhouse / Consolidate",
                "Aging contender",
            ),
        )

    def test_auto_strategy_selector_uses_automatic_team_lens(self):
        resolved = trade_hub_ui.resolve_trade_strategy_selection(
            "Auto / Best guess",
            automatic_strategy="rebuild",
            automatic_archetype="Full Rebuild",
        )

        self.assertEqual(resolved["strategy"], "rebuild")
        self.assertEqual(resolved["archetype"], "Full Rebuild")
        self.assertFalse(resolved["manual"])

    def test_manual_strategy_selector_overrides_automatic_team_lens(self):
        resolved = trade_hub_ui.resolve_trade_strategy_selection(
            "Young powerhouse / Consolidate",
            automatic_strategy="rebuild",
            automatic_archetype="Full Rebuild",
        )

        self.assertEqual(resolved["strategy"], "fringe_contender")
        self.assertEqual(resolved["archetype"], "Young Competitive Team")
        self.assertTrue(resolved["manual"])

    def test_strategy_selector_renders_current_lens_context(self):
        with (
            patch.object(
                trade_hub_ui.st,
                "selectbox",
                return_value="Aging contender",
            ) as selector,
            patch.object(trade_hub_ui.st, "caption") as caption,
        ):
            resolved = trade_hub_ui.render_trade_strategy_selector(
                automatic_strategy="rebuild",
                automatic_strategy_label="Rebuild",
                automatic_archetype="Full Rebuild",
                key="trade-lens-test",
            )

        self.assertEqual(selector.call_args.args[0], "Trade Strategy / Team Focus")
        self.assertEqual(resolved["strategy"], "contender")
        self.assertEqual(resolved["archetype"], "Aging Contender")
        self.assertIn("Strategy focus: Aging contender", caption.call_args.args[0])

    def test_cached_trade_ideas_forwards_selected_strategy_and_archetype(self):
        cached_callable = getattr(app.cached_trade_ideas, "__wrapped__", app.cached_trade_ideas)
        with patch("app.build_trade_ideas", return_value=[]) as builder:
            cached_callable(
                df_players=app.pd.DataFrame(),
                league_id="",
                df_summary=app.pd.DataFrame(),
                my_roster_id=1,
                untouchables=(),
                role_items=(),
                score_field="value_score",
                pick_score_multiplier=1.0,
                team_strategy="contender",
                team_archetype="Aging Contender",
                draft_status_items=(("complete", True),),
            )

        self.assertEqual(builder.call_args.kwargs["team_strategy"], "contender")
        self.assertEqual(builder.call_args.kwargs["team_archetype"], "Aging Contender")

    def test_team_direction_summary_excludes_unhashable_display_lists(self):
        cached_callable = getattr(
            app.cached_team_direction_summary,
            "__wrapped__",
            app.cached_team_direction_summary,
        )
        base_summary = app.pd.DataFrame(
            [
                {
                    "league_id": "league-1",
                    "roster_id": 1,
                    "owner_id": "owner-1",
                    "team_name": "Test Team",
                    "owner_name": "Test Manager",
                    "total_score": 100.0,
                    "mode": "unknown",
                    "strategy": "retool",
                    "strategy_label": "Retool",
                }
            ]
        )
        refined_frame = app.pd.DataFrame(
            [
                {
                    "roster_id": 1,
                    "mode": "rebuild",
                    "strategy": "rebuild",
                    "strategy_label": "Rebuild",
                    "archetype": "rebuild",
                    "archetype_label": "Full Rebuild",
                    "archetype_explanation": "Needs future value.",
                    "archetype_strengths": ["Picks"],
                    "archetype_risks": ["Low starters"],
                    "archetype_recommendations": ["Sell veterans"],
                    "top_injury_impact_summary": "Major Starter",
                    "top_injury_impact_players": [{"name": "Major Starter"}],
                    "manager_tendencies_summary": "Active manager.",
                    "manager_evidence": ["Trade activity"],
                    "manager_evidence_text": "Trade activity",
                }
            ]
        )

        with (
            patch(
                "app.cached_league_core_context",
                return_value={
                    "league_summary": base_summary,
                    "league_intelligence_frame": refined_frame,
                },
            ),
            patch("app.refine_team_directions", return_value=refined_frame),
        ):
            output = cached_callable(
                app.pd.DataFrame(),
                "league-1",
                score_field="value_score",
                lineup_settings={},
            )

        for column in [
            "archetype_strengths",
            "archetype_risks",
            "archetype_recommendations",
            "top_injury_impact_players",
            "manager_evidence",
        ]:
            self.assertNotIn(column, output.columns)
        self.assertIn("top_injury_impact_summary", output.columns)
        self.assertIn("manager_evidence_text", output.columns)
        app.pd.util.hash_pandas_object(output, index=True)

    def test_public_asset_initials_compatibility_export(self):
        self.assertTrue(hasattr(trade_hub_ui, "asset_initials"))
        self.assertIs(trade_hub_ui.asset_initials, trade_hub_ui._asset_initials)
        self.assertEqual(trade_hub_ui.asset_initials("Player One"), "PO")

    def test_normalizer_wrapper_preserves_output(self):
        raw_html = """
            <div class="trade-idea-card">
                <div class="trade-matchup">Assets</div>
            </div>
        """

        module_output = trade_hub_ui.normalize_trade_html(raw_html)

        self.assertTrue(module_output.startswith('<div class="trade-idea-card">'))
        self.assertFalse(
            any(line.startswith(("    ", "\t")) for line in module_output.splitlines())
        )
        self.assertFalse(hasattr(app, "_normalize_trade_html"))
        self.assertFalse(hasattr(app, "_render_trade_html"))

    def test_asset_list_wrapper_preserves_empty_and_rendered_markup(self):
        self.assertEqual(
            app._trade_assets_html([]),
            (
                "<div class='trade-asset-row'>"
                "<div class='trade-asset-copy'>No assets</div>"
                "</div>"
            ),
        )
        with patch("app._trade_asset_html", side_effect=lambda asset: f"<span>{asset['label']}</span>"):
            self.assertEqual(
                app._trade_assets_html([{"label": "Player One"}]),
                "<div class='trade-assets'><span>Player One</span></div>",
            )

    def test_confidence_wrapper_preserves_injury_context(self):
        idea = {
            "trade_confidence_label": "High",
            "trade_confidence_summary": "Strong fit and partner motivation.",
            "receive_assets": [
                {
                    "asset_type": "player",
                    "status": "IR",
                    "injury_status": "season-ending",
                    "injury_level": "major",
                }
            ],
        }

        self.assertEqual(
            app._trade_display_confidence_label(idea),
            "High (Major Health Risk)",
        )
        self.assertIn("Health caveat", app._trade_confidence_reason(idea))

    def test_render_wrapper_uses_normalized_html_renderer(self):
        with patch("modules.html_rendering.st.markdown") as html_renderer:
            trade_hub_ui.render_trade_html("    <div class='trade-matchup'>Test</div>")

        html_renderer.assert_called_once_with(
            "<div class='trade-matchup'>Test</div>",
            unsafe_allow_html=True,
        )

    def test_asset_bundle_summary_wrapper_preserves_labels(self):
        assets = [
            {"label": "Player One"},
            {"name": "Player Two"},
            {"label": "2027 1st"},
        ]
        self.assertEqual(
            app._asset_bundle_summary(assets),
            "Player One + Player Two + +1 more",
        )

    def test_player_actions_use_injected_callbacks(self):
        idea = {
            "tag": "Test path",
            "send_assets": [
                {
                    "asset_type": "player",
                    "player_id": "send-1",
                    "name": "Send Player",
                }
            ],
            "receive_assets": [
                {
                    "asset_type": "player",
                    "player_id": "get-1",
                    "name": "Get Player",
                }
            ],
        }

        with (
            patch("modules.trade_hub_ui.st") as _,
            patch("app.render_player_detail_button_grid") as player_actions,
            patch("app.render_recommendation_feedback") as feedback,
        ):
            app.render_trade_idea_player_actions(
                idea,
                key_prefix="trade-test",
                return_page="trade_hub",
                source_label="Trade Hub",
            )

        self.assertEqual(
            [row["player_id"] for row in player_actions.call_args.args[0]],
            ["send-1", "get-1"],
        )
        self.assertEqual(
            feedback.call_args.kwargs["player_ids"],
            ["send-1", "get-1"],
        )

    def test_player_asset_markup_exposes_tap_metadata_but_pick_does_not(self):
        shared = {
            "injury_marker": "INJ",
            "is_injury_status": lambda asset: False,
            "format_score": lambda value: str(value),
            "resolve_player_status": lambda asset: {"label": "Starter", "tone": "starter"},
            "asset_injury_context": lambda asset: {
                "risk": False,
                "level": "healthy",
                "label": "",
                "note": "",
            },
            "cached_headshot_data_url": lambda player_id: "",
            "avatar_html": lambda *args, **kwargs: "<div class='avatar'></div>",
            "format_age": lambda value: str(value or ""),
            "canonical_player_status": lambda value: str(value),
            "tier_chip_html": lambda value: "",
            "player_support_chip_html": lambda *args: "",
            "player_status_pill_html": lambda value: "",
        }
        player_html = trade_hub_ui.trade_asset_html(
            {
                "asset_type": "player",
                "player_id": "player-1",
                "label": "Player One",
                "position": "RB",
                "team": "LV",
                "age": 22,
                "score": 100,
            },
            **shared,
        )
        pick_html = trade_hub_ui.trade_asset_html(
            {
                "asset_type": "pick",
                "label": "2027 Round 1",
                "score": 50,
            },
            **shared,
        )

        self.assertIn("player-card-tappable", player_html)
        self.assertIn("data-player-id='player-1'", player_html)
        self.assertIn("player-position-badge trade-asset-position-badge", player_html)
        self.assertEqual(player_html.count("LV · Age 22"), 1)
        self.assertEqual(
            player_html.split(">", 1)[0].count("player-card-tappable"),
            1,
        )
        self.assertIn(">RB<", player_html)
        self.assertIn("LV · Age 22", player_html)
        self.assertNotIn("RB | LV | Age 22", player_html)
        self.assertNotIn("player-card-tappable", pick_html)
        self.assertNotIn("data-player-id", pick_html)

    def test_injured_trade_asset_uses_health_badge_not_name_prefix(self):
        shared = {
            "injury_marker": "INJ",
            "is_injury_status": lambda asset: True,
            "format_score": lambda value: str(value),
            "resolve_player_status": lambda asset: {"label": "Starter", "tone": "starter"},
            "asset_injury_context": lambda asset: {
                "risk": True,
                "level": "major",
                "label": "Health Risk",
                "note": "Major injury context.",
            },
            "cached_headshot_data_url": lambda player_id: "",
            "avatar_html": lambda *args, **kwargs: "<div class='avatar'></div>",
            "format_age": lambda value: str(value or ""),
            "canonical_player_status": lambda value: str(value),
            "tier_chip_html": lambda value: "",
            "player_support_chip_html": lambda label, tone: f"<span>{label}</span>",
            "player_status_pill_html": lambda value: "",
        }
        html = trade_hub_ui.trade_asset_html(
            {
                "asset_type": "player",
                "player_id": "player-1",
                "label": "Player One",
                "score": 100,
            },
            **shared,
        )

        self.assertIn(">Player One<", html)
        self.assertNotIn(">INJ Player One<", html)
        self.assertIn("Health Risk", html)
        self.assertIn("Major injury context.", html)

    def test_trade_html_tap_opens_quick_view_for_player_only(self):
        tap_renderer = Mock(return_value="player-1")
        open_quick_view = Mock()
        trade_hub_ui.render_trade_html_with_player_taps(
            "<div class='trade-asset-row player-card-tappable' data-player-id='player-1'></div>",
            [
                {
                    "asset_type": "player",
                    "player_id": "player-1",
                    "name": "Player One",
                    "role": "Starter",
                },
                {
                    "asset_type": "pick",
                    "label": "2027 Round 1",
                },
            ],
            key_prefix="trade-card",
            source_label="Trade Hub",
            render_tappable_player_html=tap_renderer,
            open_player_quick_view=open_quick_view,
        )

        tap_renderer.assert_called_once()
        open_quick_view.assert_called_once_with(
            "player-1",
            source_label="Trade Hub",
            source_note="Inspect Player One from this trade package.",
            status_label="Starter",
        )

    def test_trade_card_keeps_strategy_context_compact_and_reasoning_disclosed(self):
        idea = {
            "partner_team_name": "Partner",
            "tag": "Contender upgrade",
            "my_strategy": "Contender",
            "partner_strategy": "Rebuild",
            "my_score": 5000,
            "their_score": 5400,
            "trade_gain": 400,
            "fit_grade": "Strong",
            "market_realism_label": "Likely",
            "trade_confidence_label": "High",
            "trade_surface_tier": "primary",
            "strategy_archetype": "Aging Contender",
            "reasoning_summary": "Acquire the stronger starter without giving up the long-term core.",
            "fit_summary": "Improves the weakest starting position for this roster.",
            "strategy_fit_reason": "This path provides enough immediate production to justify the window.",
            "strategy_risk_label": "Age-Cliff / Future Value Risk",
            "send_assets": [],
            "receive_assets": [],
        }
        captured = {}

        def capture_html(html, *_args, **_kwargs):
            captured["html"] = html

        with (
            patch.object(
                trade_hub_ui,
                "TRADE_SUMMARY_TAP_COMPONENT",
                side_effect=lambda **kwargs: (
                    capture_html(kwargs["data"]["html"])
                    or type("Result", (), {"clicked": None})()
                ),
            ),
            patch.object(trade_hub_ui.st, "button") as disclosure,
            patch.object(trade_hub_ui.st, "markdown"),
            patch.object(trade_hub_ui.st, "caption"),
        ):
            trade_hub_ui.render_trade_idea_card(
                idea,
                0,
                format_score=lambda value: str(value),
                tidy_label=lambda value: str(value),
                trade_target_reason=lambda current: trade_hub_ui.trade_target_reason(
                    current,
                    recommendation_reason_text=lambda value, limit: str(value)[:limit],
                ),
                trade_partner_reason=lambda _idea: "Partner reason",
                trade_confidence_reason=lambda _idea: "Confidence reason",
                trade_value_verdict=lambda _value: "Fair",
                trade_display_confidence_label=lambda _idea: "High",
                injury_display_context=lambda _idea: {
                    "risk": False,
                    "label": "",
                    "note": "",
                },
                glyph_chip_html=lambda label, tone: f"<span>{label}:{tone}</span>",
                assets_html=lambda assets: "<div>Assets</div>",
            )

        self.assertIn("trade-summary-card", captured["html"])
        self.assertIn("dg-ui-card dg-ui-card--elevated", captured["html"])
        self.assertIn("Improves the weakest starting position", captured["html"])
        self.assertIn("dg-ui-badge", captured["html"])
        self.assertIn(">Value change<", captured["html"])
        self.assertIn("trade-summary-why", captured["html"])
        self.assertIn("Review package →", captured["html"])
        self.assertEqual(captured["html"].count("trade-summary-value"), 1)
        self.assertNotIn("Estimated value difference", captured["html"])
        self.assertNotIn("Acquire the stronger starter", captured["html"])
        self.assertNotIn("trade-matchup", captured["html"])
        self.assertNotIn("trade-avatar", captured["html"])
        self.assertNotIn("trade-card-value-strip", captured["html"])
        self.assertNotIn("trade-delta-pill", captured["html"])
        self.assertNotIn("trade-detail-summary", captured["html"])
        self.assertNotIn("trade-explain-card", captured["html"])
        self.assertNotIn("enough immediate production", captured["html"])
        disclosure.assert_not_called()

    def test_trade_hub_empty_states_use_canonical_condition_specific_panel(self):
        with patch.object(
            trade_hub_ui.ui_primitives,
            "render_empty_state_panel",
        ) as empty_state:
            trade_hub_ui.render_trade_hub_empty_state("High Confidence")

        empty_state.assert_called_once()
        self.assertEqual(empty_state.call_args.args[0], "No high confidence trades right now")
        self.assertEqual(empty_state.call_args.kwargs["kind"], "filtered-empty")
        self.assertIn(
            "Try a different strategy focus, or search around one of your players.",
            empty_state.call_args.kwargs["recovery_guidance"],
        )

    def test_trade_hub_section_header_uses_canonical_primitive(self):
        with patch.object(
            trade_hub_ui.ui_primitives,
            "render_section_header",
        ) as section_header:
            trade_hub_ui.render_trade_hub_section_header(
                "Best Trade Ideas",
                eyebrow="Main Board",
                subtitle="Strongest current paths.",
            )

        section_header.assert_called_once_with(
            "Best Trade Ideas",
            eyebrow="Main Board",
            subtitle="Strongest current paths.",
            heading_level=2,
        )

    def test_trade_asset_uses_canonical_status_badge_without_changing_identity(self):
        html = trade_hub_ui.trade_asset_html(
            {
                "asset_type": "player",
                "player_id": "player-1",
                "label": "Player One",
                "position": "WR",
                "team": "DET",
                "age": 24,
                "score": 88,
            },
            injury_marker="INJ",
            is_injury_status=lambda _asset: False,
            format_score=lambda value: str(value),
            resolve_player_status=lambda _asset: {"label": "Starter", "tone": "starter"},
            asset_injury_context=lambda _asset: {
                "risk": False,
                "level": "healthy",
                "label": "",
                "note": "",
            },
            cached_headshot_data_url=lambda _player_id: "",
            avatar_html=lambda *_args, **_kwargs: "<div class='avatar'></div>",
            format_age=lambda value: str(value),
            canonical_player_status=lambda value: str(value),
            tier_chip_html=lambda _value: "",
            player_support_chip_html=lambda *_args: "",
            player_status_pill_html=lambda _value: "legacy-pill",
        )

        self.assertIn("dg-ui-badge", html)
        self.assertIn("Information status: Starter", html)
        self.assertNotIn("legacy-pill", html)
        self.assertIn("data-player-id='player-1'", html)

    def test_trade_hub_mobile_hierarchy_renders_active_board_before_secondary_search(self):
        source = Path("app.py").read_text(encoding="utf-8")

        feed_idx = source.index("annotate_trade_hub_feed_categories(")
        active_loop_idx = source.index(
            "ranked_feed[:local_visible]",
            feed_idx,
        )
        premium_lock_idx = source.index('"Player-focused trade search"', active_loop_idx)
        secondary_search_idx = source.index(
            'with st.expander("Search return paths from one of your players"',
            active_loop_idx,
        )

        self.assertLess(feed_idx, active_loop_idx)
        self.assertLess(active_loop_idx, premium_lock_idx)
        self.assertLess(active_loop_idx, secondary_search_idx)
        self.assertIn("def _trade_hub_visible_feed()", source)
        self.assertNotIn("render_trade_hub_section_filter(", source)
        self.assertNotIn("Switching sections reuses the cached board.", source)

    def test_trade_hub_mobile_asset_cards_have_compact_css(self):
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")

        self.assertIn(".trade-asset-row .trade-avatar", css)
        self.assertIn("--avatar-size: 42px", css)
        self.assertIn("padding: 0.28rem 0.34rem", css)
        self.assertIn("min-height: 0", css)
        self.assertIn(".trade-asset-tags .player-support-chip:nth-child(n+3)", css)

    def test_migrated_trade_card_styles_use_semantic_tokens(self):
        css = Path("modules/app_styles.py").read_text(encoding="utf-8")
        start = css.index("/* Trade Hub mobile hierarchy: presentation only. */")
        end = css.index("</style>", start)
        migrated = css[start:end]

        self.assertNotIn("st-key-trade_hub_board_section_", migrated)
        self.assertIn("var(--color-surface-muted)", migrated)
        self.assertIn("var(--font-size-section-title)", migrated)
        self.assertIn("var(--touch-target-min)", migrated)
        self.assertIn("var(--focus-ring)", migrated)
        self.assertNotIn("#f8fafc", migrated)
        self.assertNotIn("#fca5a5", migrated)
        self.assertNotIn("#86efac", migrated)
        self.assertNotIn("rgba(", migrated)

    def test_trade_hub_espn_limited_mode_has_degraded_state(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn('"Trade Hub is gated for ESPN until free-agent', source)
        self.assertIn("st.session_state.get(\"active_platform\") == \"espn\"", source)
        self.assertIn("st.session_state.get(\"espn_limited_mode\")", source)
        self.assertIn("app-degraded-state", source)
        self.assertIn("Sleeper remains the full Trade Hub path", source)


if __name__ == "__main__":
    unittest.main()
