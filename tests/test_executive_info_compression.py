"""Regression coverage for executive information compression (presentation only)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from modules import player_history, player_quick_view, recommendation_trust_ux, ui_modal
from modules import trade_hub_ui
from modules.recommendation_trust_ux import RECOMMENDATION_TRUST_CSS


ROOT = Path(__file__).resolve().parents[1]


def _season_row(**overrides):
    row = {
        "stats_season": 2025,
        "games_played": 16,
        "fantasy_points_ppr": 240.0,
        "ppg": 15.0,
        "receptions": 70,
        "receiving_yards": 950,
        "receiving_tds": 8,
        "targets": 110,
        "target_share": 0.22,
        "position": "WR",
    }
    row.update(overrides)
    return pd.Series(row)


def test_executive_trade_detail_collapses_evidence_and_keeps_all_fields():
    html = recommendation_trust_ux.executive_trade_detail_html(
        {
            "Reason": "Fills the WR need.",
            "Evidence": "Partner has RB surplus.",
            "Risk": "Thin market conditions.",
            "Expected outcome": "Fair · Net +120",
            "Supporting metrics": "Strong fit · High confidence",
        },
        verdict="Fair",
        value_delta="+120",
        confidence="High confidence",
    )
    assert "dg-info-weight-verdict" in html
    assert "Fills the WR need." in html
    assert "Thin market conditions." in html
    assert "Partner has RB surplus." in html
    assert "Strong fit · High confidence" in html
    assert html.index("dg-info-weight-verdict") < html.index(">Reason<")
    assert "<details" in html
    assert "Supporting evidence" in html
    assert "Supporting metrics" in html


def test_executive_trade_detail_can_omit_supporting_for_first_useful():
    html = recommendation_trust_ux.executive_trade_detail_html(
        {
            "Reason": "Fills the WR need.",
            "Evidence": "Partner has RB surplus.",
            "Risk": "Thin market conditions.",
            "Expected outcome": "Fair · Net +120",
            "Supporting metrics": "Strong fit · High confidence",
        },
        verdict="Fair",
        value_delta="+120",
        confidence="High confidence",
        include_supporting=False,
    )
    assert "Fills the WR need." in html
    assert "Thin market conditions." in html
    assert "Fair · Net +120" in html
    assert "Partner has RB surplus." not in html
    assert "Strong fit · High confidence" not in html
    assert "<details" not in html
    supporting = recommendation_trust_ux.supporting_trade_detail_html(
        {
            "Evidence": "Partner has RB surplus.",
            "Supporting metrics": "Strong fit · High confidence",
        }
    )
    assert "Partner has RB surplus." in supporting
    assert "Strong fit · High confidence" in supporting
    assert "<details" in supporting


def test_trade_detail_does_not_emit_duplicate_health_warning():
    warning = Mock()
    state = {}
    with (
        patch.object(
            trade_hub_ui,
            "TRADE_SUMMARY_TAP_COMPONENT",
            return_value=type("Result", (), {"clicked": {"key": "fixture"}})(),
        ),
        patch.object(trade_hub_ui, "render_trade_html_with_player_taps"),
        patch.object(trade_hub_ui, "render_html_fragment"),
        patch.object(trade_hub_ui.st, "dialog", lambda *args, **kwargs: lambda fn: fn),
        patch.object(trade_hub_ui.st, "session_state", state),
        patch.object(trade_hub_ui.st, "warning", warning),
        patch.object(trade_hub_ui.st, "button", Mock(return_value=False)),
    ):
        trade_hub_ui.render_trade_idea_card(
            {
                "partner_roster_id": "r1",
                "partner_team_name": "Partner",
                "my_player": "a",
                "their_player": "b",
                "my_score": 100,
                "their_score": 120,
                "trade_gain": 20,
                "tag": "Fixture",
                "fit_grade": "Strong",
                "market_realism_label": "Likely",
                "trade_confidence_label": "High",
                "send_assets": [],
                "receive_assets": [],
            },
            0,
            key_prefix="fixture",
            format_score=str,
            tidy_label=str,
            trade_target_reason=lambda _i: "Need WR",
            trade_partner_reason=lambda _i: "RB surplus",
            trade_confidence_reason=lambda _i: "Health watch: outbound IR",
            trade_value_verdict=lambda _v: "Fair",
            trade_display_confidence_label=lambda _i: "High",
            injury_display_context=lambda _i: {
                "risk": True,
                "label": "Health watch",
                "note": "outbound IR",
            },
            glyph_chip_html=lambda label, tone: label,
            assets_html=lambda _a: "",
        )
    warning.assert_not_called()


def test_current_season_summary_is_compact_and_full_tables_remain_available():
    stats = player_quick_view.build_stats_view(_season_row())
    summary = player_quick_view.current_season_summary_html(stats)
    assert "Current Snapshot" in summary
    assert "Games" in summary
    assert "PPG" in summary
    assert "player-dossier-season-summary" in summary
    assert "Professional Production" not in summary
    assert "Fantasy Production" not in summary
    # Full verified tables still rendered by the complete-stats path.
    assert stats.seasons[0].key_stats
    assert stats.seasons[0].fantasy
    assert any("PPG" in item.label.upper() for item in stats.seasons[0].fantasy)


def test_career_resume_groups_when_expanded_and_suppresses_current_labels_by_default():
    resume = player_history.build_career_resume(
        [
            {
                "stats_season": 2025,
                "games_played": 16,
                "fantasy_points_ppr": 240,
                "ppg": 15,
                "receptions": 80,
                "receiving_yards": 1100,
                "receiving_tds": 9,
                "position_finish": 4,
            },
            {
                "stats_season": 2024,
                "games_played": 17,
                "fantasy_points_ppr": 320,
                "ppg": 19,
                "receptions": 100,
                "receiving_yards": 1500,
                "receiving_tds": 12,
                "position_finish": 1,
            },
        ],
        position="WR",
        current_season=2025,
        source_note="fixture",
    )
    collapsed = player_quick_view.career_resume_html(resume)
    expanded = player_quick_view.career_resume_html(resume, expanded=True)
    assert "Current season" not in collapsed
    assert "player-dossier-achievement-family" in expanded
    timeline = player_quick_view.career_timeline_html(resume, expanded=True)
    # Timeline no longer restates resume achievement labels by default.
    assert "WR1 fantasy finish" not in timeline or "WR1 fantasy finish" in expanded


def test_snapshot_includes_health_and_recommendation_action_is_dominant():
    html = player_quick_view.snapshot_html(
        player_quick_view.DossierSnapshot(
            dynasty_value="100",
            rank="#10",
            tier="Starter",
            recommendation="Hold",
            trend="Stable",
            recommendation_note="Keep",
            fantasy_ppg="15.2",
            health="Healthy",
        ),
        include_recommendation=False,
    )
    assert "Health" in html
    assert "15.2" in html
    rec = player_quick_view.recommendation_context_html(
        "Keeps starter depth intact.",
        "Fits current roster.",
        action="Hold",
    )
    assert "dg-info-weight-verdict" in rec
    assert "Hold" in rec
    assert "Keeps starter depth intact." in rec


def test_comparative_modal_is_leaderboard_first_with_collapsed_methodology():
    content = ui_modal.ModalContent(
        title="Average Age",
        eyebrow="League Comparison",
        summary="25.1 · #2",
        list_title="League Leaderboard",
        list_items=(
            ui_modal.ModalListItem("Young Core", "23.8", highlighted=False),
            ui_modal.ModalListItem("Active Club", "25.1", highlighted=True),
        ),
        sections=(
            ui_modal.ModalSection("Interpretation", "Balanced age profile."),
            ui_modal.ModalSection("Methodology", "Rank #2 · baseline 25.8", collapsed=True),
        ),
        list_before_sections=True,
    )
    html = ui_modal.modal_content_html(content, surface="test")
    assert html.index("League Leaderboard") < html.index("Interpretation")
    assert "<summary>Methodology</summary>" in html


def test_canonical_quick_view_is_shared_across_major_consumers():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert app_source.count("def render_player_quick_view_content(") == 1
    assert "def render_trade_player_dossier_content(" in app_source
    trade_dossier = app_source[
        app_source.index("def render_trade_player_dossier_content(") :
        app_source.index("def render_player_quick_view_modal(")
    ]
    assert "render_player_quick_view_content(" in trade_dossier
    for path in (
        ROOT / "modules" / "waivers_ui.py",
        ROOT / "modules" / "my_team_ui.py",
        ROOT / "modules" / "live_draft_ui.py",
        ROOT / "modules" / "player_asset_explorer_ui.py",
    ):
        text = path.read_text(encoding="utf-8")
        assert "open_player_quick_view" in text or "enable_quick_view" in text


def test_visual_weight_contract_defines_four_levels():
    html = recommendation_trust_ux.executive_trade_detail_html(
        {
            "Reason": "Need WR",
            "Evidence": "RB surplus",
            "Risk": "Thin market",
            "Expected outcome": "Fair · Net +10",
            "Supporting metrics": "Strong fit",
        },
        verdict="Fair",
        value_delta="+10",
        confidence="High confidence",
    )
    for token in (
        "dg-info-weight-verdict",
        "dg-info-weight-primary",
        "dg-info-weight-support",
        "dg-info-weight-advanced",
    ):
        assert token in html
    assert "dg-info-weight-verdict" in RECOMMENDATION_TRUST_CSS
    styles = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert "RECOMMENDATION_TRUST_CSS" in styles
    assert "EXECUTIVE_INFO_COMPRESSION_CSS" not in styles
    assert not (ROOT / "modules" / "executive_info_compression_styles.py").exists()


def test_no_business_logic_modules_changed_in_this_surface():
    """Guard: compression helpers must stay presentation-only."""

    for relative in (
        "modules/recommendation_trust_ux.py",
        "modules/player_quick_view.py",
        "modules/ui_modal.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        lowered = text.casefold()
        assert "build_trade_ideas(" not in text
        assert "assign_player_tiers(" not in text
        assert "recommend_faab(" not in text
        assert "create_checkout" not in lowered
