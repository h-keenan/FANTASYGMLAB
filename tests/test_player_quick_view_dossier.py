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
    assert "Not available" not in html
    assert "&lt;Hold&gt;" in html
    assert "<Hold>" not in html
    assert "Immediate Recommendation" not in html
    assert "Recommendation" in html
    assert "Current Value" in html


def test_career_profile_helper_removed_in_favor_of_resume_timeline():
    from modules.player_history import CareerResume

    assert not hasattr(player_quick_view, "career_profile_html")
    source = (ROOT / "modules" / "player_quick_view.py").read_text(encoding="utf-8")
    assert "def career_profile_html" not in source
    resume = player_quick_view.career_resume_html(
        CareerResume(seasons=(), achievements=(), source_note="fixture")
    )
    assert "Career Resume" in resume


def test_dossier_hierarchy_is_explicit_in_shared_renderer():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    identity = source.index("st.markdown(quick_view_html")
    context = source.index("player_quick_view.recommendation_context_html", identity)
    snapshot_position = source.index("player_quick_view.snapshot_html", context)
    season_summary = source.index(
        "player_quick_view.current_season_summary_html",
        snapshot_position,
    )
    resume = source.index("player_quick_view.career_resume_html", season_summary)
    timeline = source.index("player_quick_view.career_timeline_html", resume)
    complete_stats = source.index(
        'with st.expander("View complete season stats"',
        timeline,
    )
    assert "render_deferred_section_gate(" in source[complete_stats : complete_stats + 500]
    season = source.index("player_quick_view.render_current_season", complete_stats)
    news = source.index('with st.expander("Recent News"', season)
    advanced = source.index('with st.expander("Advanced Details"', news)
    assert "render_deferred_section_gate(" in source[advanced : advanced + 500]
    executive = source.index("player_quick_view.executive_snapshot_html", advanced)
    assert "build_executive_snapshot(" in source[advanced:executive]
    actions = source.index("player-quick-view-actions-label", advanced)
    assert (
        identity
        < context
        < snapshot_position
        < season_summary
        < resume
        < timeline
        < complete_stats
        < season
        < news
        < advanced
        < executive
        < actions
    )
    assert "if history_expanded:" in source[resume:complete_stats]
    assert "include_recommendation=False" in source[snapshot_position : snapshot_position + 120]
    assert "include_achievements=False" in source[timeline : timeline + 200]
    # Executive snapshot must not be built before the Advanced Details gate.
    before_advanced = source[source.index("def render_player_quick_view_content(") : advanced]
    assert "build_executive_snapshot(" not in before_advanced
    assert "pqv_first_useful" in source[snapshot_position:season_summary]


def test_dossier_styles_are_token_backed_responsive_and_reduced_motion_safe():
    for token in (
        "var(--color-surface-muted)",
        "var(--color-border)",
        "var(--space-sm)",
        "var(--radius-none)",
        "var(--color-information)",
    ):
        assert token in PLAYER_QUICK_VIEW_CSS
    assert "@media (max-width: 900px)" in PLAYER_QUICK_VIEW_CSS
    assert "repeat(2, minmax(0, 1fr))" in PLAYER_QUICK_VIEW_CSS
    assert "var(--touch-target-min)" in PLAYER_QUICK_VIEW_CSS
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
    assert "Recommendation" in html
    assert "Why this read matters" not in html
    assert "Recommendation Context" not in html


def test_executive_snapshot_omits_unavailable_values_and_escapes_metadata():
    html = player_quick_view.executive_snapshot_html(
        player_quick_view.ExecutiveSnapshot(
            years_in_league="4 seasons",
            college="<State>",
            contract_status="Not available",
        )
    )
    assert "Executive Summary" in html
    assert "Executive Snapshot" not in html
    assert "4 seasons" in html
    assert "&lt;State&gt;" in html
    assert "Not available" not in html


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
    assert "current_season_summary_html(quick_view_stats)" in renderer
    assert "render_current_season(quick_view_stats)" in renderer
    assert "render_college_production(quick_view_stats)" in renderer
    assert 'st.expander("View complete season stats"' in renderer
    assert 'st.expander("Recent News"' in renderer
    assert "executive_snapshot_html(executive_snapshot)" in renderer
    assert 'f"pqv_complete_season_' in renderer
    assert 'f"pqv_advanced_details_' in renderer
    assert "interaction_latency.get_or_build_fit_context" in renderer
    assert renderer.index("pqv_first_useful") < renderer.index(
        'with st.expander("View complete season stats"'
    )
