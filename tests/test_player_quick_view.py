import pandas as pd

from modules import player_quick_view


def _row(**overrides):
    values = {
        "player_id": "fixture-player",
        "position": "WR",
        "stats_season": 2025,
        "games_played": 17,
        "targets": 120,
        "receptions": 80,
        "receiving_yards": 1100,
        "receiving_tds": 8,
        "fantasy_points": 158.0,
        "fantasy_points_half_ppr": 198.0,
        "fantasy_points_ppr": 238.0,
        "ppg": 14.0,
        "snap_share": 0.82,
    }
    values.update(overrides)
    return pd.Series(values)


def test_stats_view_labels_loaded_regular_season_and_games():
    model = player_quick_view.build_stats_view(_row())

    assert len(model.seasons) == 1
    assert model.seasons[0].label == "2025 Regular Season"
    assert model.seasons[0].games == 17
    assert model.career_totals_available is False


def test_missing_season_is_explicit_not_silently_current():
    model = player_quick_view.build_stats_view(_row(stats_season=None))

    assert model.seasons[0].label == "Regular Season (year unavailable)"


def test_missing_values_are_omitted_while_proven_zero_is_preserved():
    model = player_quick_view.build_stats_view(
        _row(targets=0, receptions=pd.NA, receiving_yards=None)
    )
    stats = {item.label: item.value for item in model.seasons[0].key_stats}

    assert stats["Targets"] == "0"
    assert "Receptions" not in stats
    assert "Rec Yards" not in stats


def test_distinct_fantasy_formats_keep_scoring_labels_and_context():
    fantasy = player_quick_view.build_stats_view(_row()).seasons[0].fantasy
    labels = [item.label for item in fantasy]

    assert labels == ["PPR", "Half PPR", "Standard", "PPR PPG"]
    assert all("17 games" in item.note for item in fantasy)


def test_identical_fantasy_formats_collapse_misleading_duplicates():
    model = player_quick_view.build_stats_view(
        _row(
            position="QB",
            fantasy_points=300.0,
            fantasy_points_half_ppr=300.0,
            fantasy_points_ppr=300.0,
        )
    )

    assert [item.label for item in model.seasons[0].fantasy] == [
        "Fantasy Points",
        "PPR PPG",
    ]
    assert "identical across loaded formats" in model.seasons[0].fantasy[0].note


def test_usage_is_part_of_same_selected_season_model():
    season = player_quick_view.build_stats_view(_row()).seasons[0]

    assert season.season == 2025
    assert [(item.label, item.value) for item in season.usage] == [("Snap %", "82%")]


def test_college_production_uses_user_facing_labels():
    model = player_quick_view.build_stats_view(
        _row(college="Texas", college_season=2023, college_receiving_yards=950)
    )

    assert model.college_available is True
    assert {item.label for item in model.college} >= {"College", "Season", "Rec Yards"}
    assert all("college_" not in item.label for item in model.college)


def test_college_unavailable_copy_never_exposes_schema_fields():
    message = player_quick_view.college_unavailable_message()

    assert message == "College production data is not currently available for this player."
    assert "college_" not in message


def test_developer_diagnostics_are_disabled_by_default_and_on_production_host():
    assert player_quick_view.developer_diagnostics_enabled({}) is False
    assert (
        player_quick_view.developer_diagnostics_enabled(
            {
                "DYNASTYGM_DEBUG_UI": "1",
                "APP_BASE_URL": "https://fantasygmlab.com",
            }
        )
        is False
    )


def test_developer_diagnostics_can_be_enabled_locally():
    assert (
        player_quick_view.developer_diagnostics_enabled(
            {
                "DYNASTYGM_DEBUG_UI": "true",
                "APP_BASE_URL": "http://localhost:8501",
            }
        )
        is True
    )


def test_html_escapes_labels_values_and_notes():
    html = player_quick_view.dense_section_html(
        "<Season>",
        (
            player_quick_view.StatItem(
                label="<script>",
                value="<b>1</b>",
                note='"unsafe"',
                tone="reference",
            ),
        ),
    )

    assert "<script>" not in html
    assert "<b>1</b>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;1&lt;/b&gt;" in html


def test_news_url_allows_only_absolute_http_destinations():
    assert player_quick_view.safe_news_url("https://example.com/story") == "https://example.com/story"
    assert player_quick_view.safe_news_url("javascript:alert(1)") == ""
    assert player_quick_view.safe_news_url("//example.com/story") == ""
    assert player_quick_view.safe_news_url("/relative/story") == ""


def test_news_source_normalization_and_card_contract():
    assert (
        player_quick_view.normalize_news_source(
            "https://www.rotowire.com/rss/news.php?sport=NFL"
        )
        == "RotoWire"
    )
    assert player_quick_view.normalize_news_source("Unknown Desk") == "Unknown Desk"
    card = player_quick_view.news_card_html(
        player_quick_view.NewsItem(
            headline="Practice report",
            source="ESPN",
            freshness="35m",
            snippet="Limited snaps.",
            url="https://www.espn.com/story?utm=1",
        )
    )
    assert "ESPN · 35m" in card
    assert "Practice report" in card
    assert "utm=1" not in card
    assert player_quick_view.news_unavailable_html().startswith("<p")


def test_model_is_frozen_and_has_no_cross_invocation_state():
    first = player_quick_view.build_stats_view(_row(targets=1))
    second = player_quick_view.build_stats_view(_row(targets=2))

    assert first != second
    assert first.seasons[0].key_stats != second.seasons[0].key_stats
