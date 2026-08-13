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
    assert "Value &amp; Health" in html


def test_career_profile_helper_removed_in_favor_of_resume_timeline():
    from modules.player_history import CareerResume

    assert not hasattr(player_quick_view, "career_profile_html")
    source = (ROOT / "modules" / "player_quick_view.py").read_text(encoding="utf-8")
    assert "def career_profile_html" not in source
    resume = player_quick_view.career_resume_html(
        CareerResume(seasons=(), achievements=(), source_note="fixture")
    )
    assert "Career Context" in resume


def test_dossier_hierarchy_is_explicit_in_shared_renderer():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    identity = source.index("st.markdown(quick_view_html")
    context = source.index("player_quick_view.recommendation_context_html", identity)
    rank_strip = source.index("player_quick_view.rank_strip_html", context)
    season_summary = source.index(
        "player_quick_view.current_season_summary_html",
        rank_strip,
    )
    why = source.index("player_quick_view.why_this_recommendation_html", season_summary)
    first_useful = source.index("pqv_first_useful", why)
    actions = source.index("player-quick-view-actions-label", first_useful)
    news = source.index("_render_pqv_recent_news_auto(", actions)
    more = source.index("pqv_more_details_open_", news)
    season = source.index("player_quick_view.render_current_season", more)
    resume = source.index("player_quick_view.career_resume_html", season)
    timeline = source.index("player_quick_view.career_timeline_html", resume)
    executive = source.index("player_quick_view.executive_snapshot_html", timeline)
    assert (
        identity
        < context
        < rank_strip
        < season_summary
        < why
        < first_useful
        < actions
        < news
        < more
        < season
        < resume
        < timeline
        < executive
    )
    renderer = source[
        source.index("def render_player_quick_view_content(") : source.index(
            "def render_player_detail_content("
        )
    ]
    assert renderer.count("player_quick_view.career_resume_html") == 1
    assert "player_quick_view.snapshot_html(" not in renderer
    assert "include_achievements=False" in source[timeline : timeline + 200]
    # Executive snapshot must not be built before More details is opened.
    before_more = source[source.index("def render_player_quick_view_content(") : more]
    assert "build_executive_snapshot(" not in before_more
    assert "cached_sleeper_player_directory(" not in before_more
    assert "load_cached_career_resume(" not in before_more
    assert "Load recent news" not in source[
        source.index("def render_player_quick_view_content(") : source.index(
            "def render_player_detail_content("
        )
    ]
    assert "Current season production is not available" not in renderer
    assert "tier_chip_html(tier_label)" not in renderer
    assert "Depth-chart role" in renderer
    assert "Fantasy action" in renderer
    assert "Roster impact" in renderer


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
    assert "player-dossier-news-card" in PLAYER_QUICK_VIEW_CSS
    assert "player-dossier-rank-strip" in PLAYER_QUICK_VIEW_CSS
    assert "#" not in PLAYER_QUICK_VIEW_CSS


def test_identity_badges_are_labeled_and_omit_valuation_tier():
    html = player_quick_view.labeled_signal_badges_html(
        (
            ("Health", "Questionable"),
            ("Depth-chart role", "Buried Depth"),
            ("Fantasy action", "Waiver Target"),
        )
    )
    assert "Health" in html
    assert "Depth-chart role" in html
    assert "Fantasy action" in html
    assert "Buried Depth" in html
    assert "Starter" not in html
    assert html.index("Health") < html.index("Depth-chart role") < html.index("Fantasy action")
    assert player_quick_view.labeled_signal_badges_html(()) == ""


def test_why_this_recommendation_caps_four_factors_and_omits_empty():
    html = player_quick_view.why_this_recommendation_html(
        (
            ("Role", "Buried Depth"),
            ("Health", "Questionable"),
            ("Team fit", "Adds depth"),
            ("Production", "14.2 PPR PPG"),
            ("Extra", "Should not render"),
        )
    )
    assert "Why we value him this way" in html
    assert "Buried Depth" in html
    assert "14.2 PPR PPG" in html
    assert "Should not render" not in html
    assert player_quick_view.why_this_recommendation_html(()) == ""


def test_rank_strip_is_the_single_labeled_value_owner():
    html = player_quick_view.rank_strip_html(
        overall_display="#218",
        position_display="WR #83",
        scoring_format="PPR",
        dynasty_value="2,495",
    )
    assert "Dynasty value" in html
    assert "Overall rank" in html
    assert "Position rank" in html
    assert "Format" in html
    assert html.count("2,495") == 1
    assert "Value 2,495" not in html
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


def test_news_card_hides_raw_url_and_normalizes_sources():
    assert (
        player_quick_view.normalize_news_source(
            "https://www.espn.com/espn/rss/nfl/news"
        )
        == "ESPN"
    )
    assert (
        player_quick_view.normalize_news_source("https://obscure.example.com/path?x=1")
        == "obscure.example.com"
    )
    assert player_quick_view.normalize_news_source("NBC Sports") == "NBC Sports"
    html = player_quick_view.news_card_html(
        player_quick_view.NewsItem(
            headline="Wilson limited in practice",
            source="NBC Sports",
            freshness="2h",
            snippet="Returned to limited work.",
            url="https://example.com/story?utm=1",
        )
    )
    assert "NBC Sports · 2h" in html
    assert "Wilson limited in practice" in html
    assert "Returned to limited work." in html
    assert "https://example.com" not in html
    assert "utm=1" not in html


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
    assert "current_season_summary_html(" in renderer
    assert "render_current_season(quick_view_stats, omit_empty=True)" in renderer
    assert "render_college_production(quick_view_stats, omit_empty=True)" in renderer
    assert "_render_pqv_recent_news_auto(" in renderer
    assert 'st.expander("Recent News"' not in renderer
    assert "Load recent news" not in renderer
    assert "pqv_more_details_open_" in renderer
    assert renderer.count("st.columns(2)") >= 1
    assert renderer.index("player-quick-view-actions-label") < renderer.index(
        "pqv_more_details_open_"
    )
