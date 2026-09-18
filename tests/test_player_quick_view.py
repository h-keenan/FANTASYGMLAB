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


def test_efficiency_computes_per_game_and_per_touch_rates():
    season = player_quick_view.build_stats_view(_row()).seasons[0]
    efficiency = {item.label: item.value for item in season.efficiency}

    # 120 targets / 17 games, 80 receptions / 17 games, 1100 yards / 80 catches.
    assert efficiency["Targets/Gm"] == "7.1"
    assert efficiency["Rec/Gm"] == "4.7"
    assert efficiency["Yards/Catch"] == "13.8"
    # No rush_attempts/rushing_yards in the fixture — rushing rates are
    # omitted entirely rather than showing a misleading 0.0.
    assert "Carries/Gm" not in efficiency
    assert "Yards/Carry" not in efficiency


def test_efficiency_includes_rushing_rates_when_present():
    season = player_quick_view.build_stats_view(
        _row(position="RB", rush_attempts=200, rushing_yards=900)
    ).seasons[0]
    efficiency = {item.label: item.value for item in season.efficiency}

    assert efficiency["Carries/Gm"] == "11.8"
    assert efficiency["Yards/Carry"] == "4.5"


def test_efficiency_omits_a_rate_with_a_zero_denominator():
    season = player_quick_view.build_stats_view(_row(games_played=0)).seasons[0]
    efficiency = {item.label: item.value for item in season.efficiency}

    assert "Targets/Gm" not in efficiency
    assert "Rec/Gm" not in efficiency
    # Per-catch is denominated on receptions, not games, so it's unaffected.
    assert efficiency["Yards/Catch"] == "13.8"


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


def _pool(count: int, *, position: str = "WR", eligible: bool = True):
    """A ranking pool shaped like rankings.load_players' output: already
    carrying the canonical eligibility annotation columns, so
    filter_current_fantasy_players masks rather than re-validates."""

    rows = []
    for index in range(count):
        rows.append(
            {
                "player_id": f"pool-{index}",
                "name": f"Pool Player {index}",
                "position": position,
                "team": "NYJ",
                "status": "Active",
                "active": True,
                "stats_season": 2025,
                "games_played": 17,
                "targets": 10 * index,
                "receptions": 6 * index,
                "receiving_yards": 70 * index,
                "receiving_tds": index,
                "fantasy_points": 10.0 * index,
                "fantasy_points_half_ppr": 12.0 * index,
                "fantasy_points_ppr": 14.0 * index,
                "ppg": 1.0 * index,
                "snap_share": 0.05 * index,
                "is_current_fantasy_eligible": eligible,
                "player_eligibility_reason": "active_fantasy_player",
                "trust_enforcement": "pass",
                "trust_evidence_confidence": 1.0,
                "trust_block_reason": "",
                "trust_validation_fingerprint": f"fp-{index}",
            }
        )
    return pd.DataFrame(rows)


def _pool_with_subject(count: int, **overrides):
    """The fixture player appended to a pool of `count` same-position peers."""

    frame = _pool(count)
    subject = dict(frame.iloc[0])
    subject.update(
        {
            "player_id": "fixture-player",
            "name": "Fixture Player",
            # Clear of every peer in `_pool` (whose top row is index-scaled),
            # so the expected percentile is unambiguously the ceiling.
            "targets": 400,
            "receptions": 260,
            "receiving_yards": 3200,
            "receiving_tds": 30,
            "fantasy_points": 380.0,
            "fantasy_points_half_ppr": 440.0,
            "fantasy_points_ppr": 520.0,
            "ppg": 40.0,
            "snap_share": 0.99,
        }
    )
    subject.update(overrides)
    return pd.concat([frame, pd.DataFrame([subject])], ignore_index=True)


def _subject_row(players):
    return players[players["player_id"] == "fixture-player"].iloc[0]


def _percentiles(items):
    return {item.label: item.percentile for item in items}


def test_percentiles_absent_without_a_pool():
    season = player_quick_view.build_stats_view(_row()).seasons[0]

    assert all(item.percentile is None for item in season.key_stats)
    assert all(item.percentile is None for item in season.fantasy)
    assert all(item.percentile is None for item in season.efficiency)


def test_percentiles_rank_the_player_inside_their_position_group():
    players = _pool_with_subject(20)

    season = player_quick_view.build_stats_view(_subject_row(players), players).seasons[0]
    key = _percentiles(season.key_stats)

    # Best receiving line in the pool -> top of the distribution.
    assert key["Rec Yards"] == 100
    assert key["Targets"] == 100
    # Availability is not a performance stat, so Games is never ranked.
    assert key["Games"] is None
    assert _percentiles(season.fantasy)["PPR PPG"] == 100
    # Derived rate stats are ranked as displayed, not inferred from inputs.
    assert _percentiles(season.efficiency)["Yards/Catch"] is not None


def test_percentile_is_mid_pack_for_a_mid_pack_line():
    players = _pool_with_subject(20, receiving_yards=70 * 10, targets=10 * 10)

    season = player_quick_view.build_stats_view(_subject_row(players), players).seasons[0]
    rec_yards = _percentiles(season.key_stats)["Rec Yards"]

    assert rec_yards is not None
    assert 40 <= rec_yards <= 60


def test_percentiles_omitted_when_the_position_pool_is_too_small():
    players = _pool_with_subject(player_quick_view.PERCENTILE_MIN_POOL - 2)

    season = player_quick_view.build_stats_view(_subject_row(players), players).seasons[0]

    assert all(item.percentile is None for item in season.key_stats)
    assert all(item.percentile is None for item in season.efficiency)


def test_percentiles_use_the_shared_eligibility_filter_for_the_pool():
    players = _pool_with_subject(20)
    # Enough rows for a pool, but only the subject survives the canonical
    # current-fantasy-asset filter — ineligible rows must not pad the sample
    # up to the minimum.
    others = players["player_id"] != "fixture-player"
    players.loc[others, "is_current_fantasy_eligible"] = False

    season = player_quick_view.build_stats_view(_subject_row(players), players).seasons[0]

    assert all(item.percentile is None for item in season.key_stats)


def test_percentiles_only_compare_within_the_same_position():
    wr_pool = _pool_with_subject(20)
    rb_pool = _pool(20, position="RB")
    rb_pool["player_id"] = [f"rb-{index}" for index in range(len(rb_pool))]
    # Every RB out-produces the whole WR pool; a cross-position pool would
    # sink the subject's percentile, a per-position one must not move it.
    rb_pool["receiving_yards"] = 5000
    rb_pool["targets"] = 400
    players = pd.concat([wr_pool, rb_pool], ignore_index=True)

    season = player_quick_view.build_stats_view(_subject_row(players), players).seasons[0]

    assert _percentiles(season.key_stats)["Rec Yards"] == 100


def test_percentiles_are_omitted_for_a_player_outside_the_eligible_pool():
    players = _pool_with_subject(20)
    players.loc[players["player_id"] == "fixture-player", "is_current_fantasy_eligible"] = False

    season = player_quick_view.build_stats_view(_subject_row(players), players).seasons[0]

    assert all(item.percentile is None for item in season.key_stats)
