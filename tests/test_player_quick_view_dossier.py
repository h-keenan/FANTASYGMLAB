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
    identity = source.index("player_quick_view.pqv_hero_html")
    context = source.index("player_quick_view.recommendation_context_html", identity)
    season_summary = source.index(
        "player_quick_view.current_season_summary_html",
        context,
    )
    why = source.index("player_quick_view.why_this_recommendation_html", season_summary)
    first_useful = source.index("pqv_first_useful", why)
    career = source.index("player_quick_view.career_dossier_html", first_useful)
    actions = source.index("player-quick-view-actions-label", career)
    more = source.index("pqv_more_details_open_", actions)
    season = source.index("player_quick_view.render_current_season", more)
    timeline = source.index("player_quick_view.career_timeline_html", season)
    bio = source.index("player_quick_view.compact_bio_html", timeline)
    news = source.index("_render_pqv_recent_news_auto(", bio)
    advanced = source.index("Advanced analysis", news)
    assert (
        identity
        < context
        < season_summary
        < why
        < first_useful
        < career
        < actions
        < more
        < season
        < timeline
        < bio
        < news
        < advanced
    )
    renderer = source[
        source.index("def render_player_quick_view_content(") : source.index(
            "def render_player_detail_content("
        )
    ]
    assert renderer.count("player_quick_view.career_resume_html") == 0
    assert "player_quick_view.snapshot_html(" not in renderer
    assert "pqv_hero_html(" in renderer
    assert "include_achievements=False" in source[timeline : timeline + 200]
    assert "include_milestones=False" not in renderer
    # Executive snapshot must not be built before More details is opened.
    before_more = source[source.index("def render_player_quick_view_content(") : more]
    assert "build_executive_snapshot(" not in before_more
    assert "cached_sleeper_player_directory(" not in before_more
    assert "load_cached_career_resume(" not in before_more
    assert "player_awards.build_season_cache_index(" in before_more
    assert "Load recent news" not in source[
        source.index("def render_player_quick_view_content(") : source.index(
            "def render_player_detail_content("
        )
    ]
    assert "Current season production is not available" not in renderer
    assert "tier_chip_html(tier_label)" not in renderer
    assert "role_label=opportunity_label" in renderer
    assert "scoring_format=\"\"" in renderer or 'scoring_format=""' in renderer
    assert "Roster impact" not in renderer
    assert "Fantasy action" not in renderer


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
    assert "pqv-accolade-cluster{display:grid" in PLAYER_QUICK_VIEW_CSS
    assert "flex-wrap:wrap" in PLAYER_QUICK_VIEW_CSS
    assert "minmax(9.5rem,1fr)" in PLAYER_QUICK_VIEW_CSS
    assert "#" not in PLAYER_QUICK_VIEW_CSS


def test_hero_is_the_canonical_identity_and_value_owner():
    html = player_quick_view.pqv_hero_html(
        avatar_html="<div class='player-quick-view-avatar'>BR</div>",
        name="Bijan Robinson",
        position="RB",
        team="ATL",
        age_text="24",
        source_label="Identity",
        role_label="Elite Opportunity",
        overall_display="#1",
        position_display="RB #1",
        dynasty_value="11,228",
        scoring_format="",
        signal_badges=(("Health", "Questionable"), ("Roster impact", "Core")),
    )
    assert "pqv-hero-portrait" in html
    assert "Bijan Robinson" in html
    assert "RB · ATL · Age 24" in html
    assert html.count("Elite Opportunity") == 1
    assert "Dynasty value" in html
    assert "Overall rank" in html
    assert "RB #1" in html
    assert "Format" not in html
    assert "Questionable" in html
    assert "Roster impact" not in html
    assert "Depth-chart role" not in html


def test_at_a_glance_uses_compact_stat_dashboard():
    row = __import__("pandas").Series(
        {
            "position": "RB",
            "stats_season": 2025,
            "games_played": 17,
            "rush_attempts": 287,
            "rushing_yards": 1400,
            "targets": 103,
            "receptions": 79,
            "receiving_yards": 820,
            "fantasy_points_ppr": 370,
            "ppg": 21.8,
            "snap_share": 0.78,
        }
    )
    html = player_quick_view.current_season_summary_html(
        player_quick_view.build_stats_view(row)
    )
    assert "Current Season" in html
    assert "Current fantasy evidence" not in html
    assert "At a glance" not in html
    assert "pqv-glance-grid" in html
    assert "PPR PPG" in html
    assert "pqv-glance-bar" in html
    assert "Rush Yards" in html
    assert "Role" not in html
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


def test_current_season_is_position_aware_and_hides_empty():
    qb = player_quick_view.current_season_summary_html(
        player_quick_view.build_stats_view(
            __import__("pandas").Series(
                {
                    "position": "QB",
                    "stats_season": 2025,
                    "games_played": 15,
                    "passing_yards": 3900,
                    "passing_tds": 28,
                    "rushing_yards": 630,
                    "rushing_tds": 14,
                    "ppg": 22.1,
                    "snap_share": 0.99,
                }
            )
        )
    )
    assert "Pass Yards" in qb
    assert "Rush Yards" in qb
    assert "Targets" not in qb
    wr = player_quick_view.current_season_summary_html(
        player_quick_view.build_stats_view(
            __import__("pandas").Series(
                {
                    "position": "WR",
                    "stats_season": 2025,
                    "games_played": 16,
                    "targets": 140,
                    "receptions": 90,
                    "receiving_yards": 1200,
                    "receiving_tds": 8,
                    "ppg": 16.4,
                }
            )
        )
    )
    assert "Targets" in wr
    assert "Pass Yards" not in wr
    te = player_quick_view.current_season_summary_html(
        player_quick_view.build_stats_view(
            __import__("pandas").Series(
                {
                    "position": "TE",
                    "stats_season": 2025,
                    "games_played": 10,
                    "targets": 70,
                    "receptions": 48,
                    "receiving_yards": 520,
                    "receiving_tds": 4,
                    "ppg": 11.2,
                }
            )
        )
    )
    assert "Receptions" in te
    assert player_quick_view.career_dossier_html(badges=(), years_exp=None) == ""
    rookie = player_quick_view.career_dossier_html(badges=(), years_exp=0)
    assert "Rookie" in rookie
    assert "Accolades" not in rookie


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
    assert "FantasyGM Read" in html
    assert "Buried Depth" in html
    assert "14.2 PPR PPG" in html
    assert "Should not render" not in html
    assert player_quick_view.why_this_recommendation_html(()) == ""
    composed = player_quick_view.compose_fantasygm_read_factors(
        why="Elite workload plus production.",
        team_fit="Elite workload plus production.",
        risk="Questionable",
        skip_values=("Elite Opportunity",),
    )
    assert [label for label, _ in composed] == ["Why", "Risk"]
    redundant = player_quick_view.compose_fantasygm_read_factors(
        why="OVR #70 / QB #10",
        team_fit="Current roster role: Flex",
        risk="Healthy",
        skip_values=("#70", "QB #10", "Flex"),
    )
    assert redundant == [("Risk", "Healthy")]


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


def test_compact_bio_omits_experience_and_unavailable_values():
    html = player_quick_view.compact_bio_html(
        player_quick_view.ExecutiveSnapshot(
            years_in_league="4 seasons",
            college="<State>",
            height="6'1\"",
            weight="223 lb",
            contract_status="Not available",
        )
    )
    assert "Bio" in html
    assert "Experience" not in html
    assert "4 seasons" not in html
    assert "&lt;State&gt;" in html
    assert "6&#x27;1&quot;" in html or "6'1" in html
    assert "Not available" not in html
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
    assert "pqv_actions_strip_" in renderer
    assert "st.columns(2" in renderer
    assert renderer.index("pqv_hero_html") < renderer.index("recommendation_context_html")
    assert renderer.index("recommendation_context_html") < renderer.index("current_season_summary_html")
    assert renderer.index("pqv_career_") < renderer.index("pqv_actions_")
    assert renderer.index("pqv_more_details_open_") < renderer.index(
        "_render_pqv_recent_news_auto("
    )


def test_trade_hub_inspect_fixture_uses_canonical_pqv_not_snapshot():
    source = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    trade = source[source.index("def _trade()") : source.index("def _my_team()")]
    assert "pqv_hero_html" in trade
    assert "data-trade-dossier-player" in trade
    assert "snapshot_html" not in trade
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    dossier = app[
        app.index("def render_trade_player_dossier_content(") : app.index(
            "def render_player_quick_view_modal("
        )
    ]
    assert "render_player_quick_view_content(" in dossier
    assert "render_player_quick_view_modal(" not in dossier
