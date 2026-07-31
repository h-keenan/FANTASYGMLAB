from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from modules import player_quick_view
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS


ROOT = Path(__file__).resolve().parents[1]


def snapshot(**overrides):
    values = {
        "dynasty_value": "8,420",
        "rank": "#14",
        "tier": "Starter",
        "recommendation": "Hold",
        "trend": "Stable",
        "recommendation_note": "Maintain the current roster position.",
    }
    values.update(overrides)
    return player_quick_view.DossierSnapshot(**values)


def test_dossier_models_are_frozen_and_career_profile_is_future_safe():
    model = snapshot()
    with pytest.raises(FrozenInstanceError):
        model.rank = "#1"
    empty = player_quick_view.CareerProfile()
    populated = player_quick_view.CareerProfile(
        achievements=("Verified achievement",),
        season_highlights=("2025 highlight",),
    )
    assert empty.available is False
    assert populated.available is True


def test_snapshot_is_escaped_semantic_and_does_not_invent_missing_rank():
    html = player_quick_view.snapshot_html(
        snapshot(rank="Not available", recommendation="<Hold>")
    )
    assert "aria-labelledby='player-dossier-snapshot-title'" in html
    assert "Not available" in html
    assert "&lt;Hold&gt;" in html
    assert "<Hold>" not in html
    assert "Immediate Recommendation" in html


def test_career_profile_uses_concise_placeholder_and_escapes_future_content():
    empty_html = player_quick_view.career_profile_html(
        player_quick_view.CareerProfile()
    )
    assert "Career credentials will appear here" in empty_html
    assert "raw" not in empty_html.casefold()
    populated_html = player_quick_view.career_profile_html(
        player_quick_view.CareerProfile(
            achievements=("<All-Pro>",),
            season_highlights=("2025: 1,000 yards",),
        )
    )
    assert "&lt;All-Pro&gt;" in populated_html
    assert "Major Achievements" in populated_html
    assert "Season Highlights" in populated_html


def test_dossier_hierarchy_is_explicit_in_shared_renderer():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    identity = source.index("st.markdown(quick_view_html")
    snapshot_position = source.index("player_quick_view.snapshot_html", identity)
    career = source.index("player_quick_view.career_profile_html", snapshot_position)
    season = source.index("player_quick_view.render_current_season", career)
    news = source.index("player_quick_view.render_news", season)
    context = source.index("player_quick_view.recommendation_context_html", news)
    actions = source.index("player-quick-view-actions-label", context)
    advanced = source.index('with st.expander("Advanced Details"', context)
    assert identity < snapshot_position < career < season < news < context
    assert context < advanced < actions


def test_dossier_styles_are_token_backed_responsive_and_reduced_motion_safe():
    for token in (
        "var(--color-surface-muted)",
        "var(--color-border)",
        "var(--space-sm)",
        "var(--radius-panel)",
        "var(--color-information)",
    ):
        assert token in PLAYER_QUICK_VIEW_CSS
    assert "@media (max-width: 900px)" in PLAYER_QUICK_VIEW_CSS
    assert "repeat(2, minmax(0, 1fr))" in PLAYER_QUICK_VIEW_CSS
    assert "@media (prefers-reduced-motion: reduce)" in PLAYER_QUICK_VIEW_CSS
    assert "max-height: min(88vh, 920px)" in PLAYER_QUICK_VIEW_CSS
    assert "overflow-y: auto" in PLAYER_QUICK_VIEW_CSS
    assert ':has(.player-quick-view-shell)' in PLAYER_QUICK_VIEW_CSS
    assert 'div[role="dialog"] {' not in PLAYER_QUICK_VIEW_CSS
    assert "#" not in PLAYER_QUICK_VIEW_CSS


def test_recommendation_context_is_escaped_and_has_semantic_heading():
    html = player_quick_view.recommendation_context_html(
        "<summary>",
        "<context>",
    )
    assert "aria-labelledby='player-dossier-context-title'" in html
    assert "&lt;summary&gt;" in html
    assert "&lt;context&gt;" in html
    assert "Why this player matters" in html


def test_app_remains_the_only_shared_renderer_and_dossier_does_not_recompute_values():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count("def render_player_quick_view_content(") == 1
    module_source = (ROOT / "modules" / "player_quick_view.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "assign_player_tiers(",
        "build_players_table(",
        "build_trade_ideas(",
        "recommend_faab(",
    ):
        assert forbidden not in module_source
    renderer_start = source.index("def render_player_quick_view_content(")
    renderer_end = source.index("def render_player_detail_content(", renderer_start)
    renderer = source[renderer_start:renderer_end]
    assert renderer.count("player_quick_view.build_stats_view(row)") == 1
    assert "render_current_season(quick_view_stats)" in renderer
    assert "render_college_production(quick_view_stats)" in renderer
