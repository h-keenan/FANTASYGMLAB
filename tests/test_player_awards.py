from __future__ import annotations

import json

from modules import player_awards
from modules import player_quick_view
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS


def _row(season: int, position: str = "WR", **overrides):
    values = {
        "stats_season": season,
        "position": position,
        "games_played": 17,
        "fantasy_points_ppr": 200.0,
    }
    values.update(overrides)
    return values


def test_elite_player_multiple_accomplishments_are_normalized():
    badges = player_awards.build_player_awards(
        [
            _row(
                2024,
                position_finish=2,
                overall_finish=4,
                receiving_yards=1540,
                receiving_tds=12,
                targets=148,
            ),
            _row(2025, position_finish=6, receiving_yards=1080, receiving_tds=8, targets=120),
        ],
        position="WR",
    )
    families = {item.family for item in badges}
    assert "positional-finish" in families
    assert "overall-finish" in families
    assert "rec-yards" in families
    assert "rec-td" in families
    assert "targets" in families
    positional = next(item for item in badges if item.family == "positional-finish")
    assert positional.tier == "gold"
    assert positional.occurrence_count == 1
    assert "2×" not in positional.short_label
    assert positional.season == 2024
    rec_yards = next(item for item in badges if item.family == "rec-yards")
    assert rec_yards.tier == "gold"
    assert rec_yards.occurrence_count == 1


def test_positional_top_three_is_gold():
    badges = player_awards.build_player_awards(
        [_row(2025, position_finish=3)],
        position="WR",
    )
    assert len(badges) == 1
    assert badges[0].tier == "gold"
    assert badges[0].short_label == "Top-3 WR"
    assert badges[0].rank == 3
    assert "2025" in badges[0].description


def test_positional_top_five_only_is_silver():
    badges = player_awards.build_player_awards(
        [_row(2025, position_finish=5)],
        position="RB",
    )
    assert len(badges) == 1
    assert badges[0].tier == "silver"
    assert badges[0].short_label == "Top-5 RB"


def test_positional_top_ten_only_is_bronze():
    badges = player_awards.build_player_awards(
        [_row(2025, position_finish=10)],
        position="TE",
    )
    assert len(badges) == 1
    assert badges[0].tier == "bronze"
    assert badges[0].short_label == "Top-10 TE"


def test_milestone_season_uses_strongest_yardage_tier():
    badges = player_awards.build_player_awards(
        [_row(2025, receiving_yards=1510)],
        position="WR",
    )
    assert len(badges) == 1
    assert badges[0].family == "rec-yards"
    assert badges[0].tier == "gold"
    assert "1,000" not in badges[0].title


def test_repeat_accomplishment_collapses_to_count():
    badges = player_awards.build_player_awards(
        [
            _row(2023, receiving_yards=1100),
            _row(2025, receiving_yards=1200),
        ],
        position="WR",
    )
    assert len(badges) == 1
    assert badges[0].occurrence_count == 2
    assert badges[0].season == 2025
    assert "2×" in badges[0].short_label


def test_rookie_without_accolades_returns_empty():
    badges = player_awards.build_player_awards(
        [_row(2025, receiving_yards=420, receiving_tds=2, targets=55, position_finish=48)],
        position="WR",
    )
    assert badges == ()
    assert player_quick_view.accolades_html(badges) == ""
    assert "No badges found" not in player_quick_view.accolades_html(badges)


def test_missing_historical_data_falls_back_to_current_row_only():
    rows = player_awards.award_rows_for_player(
        (),
        player_id="p1",
        current_row=_row(2025, receiving_yards=1100),
        position="WR",
    )
    badges = player_awards.build_player_awards(rows, position="WR")
    assert len(badges) == 1
    assert badges[0].family == "rec-yards"
    empty_rows = player_awards.award_rows_for_player(
        (),
        player_id="missing",
        current_row={},
        position="WR",
    )
    assert player_awards.build_player_awards(empty_rows, position="WR") == ()


def test_position_specific_thresholds_do_not_cross_apply():
    wr_pass = player_awards.build_player_awards(
        [_row(2025, passing_yards=5000, passing_tds=40, receiving_yards=200)],
        position="WR",
    )
    assert wr_pass == ()
    qb = player_awards.build_player_awards(
        [_row(2025, passing_yards=4100, passing_tds=32, receiving_yards=1500)],
        position="QB",
    )
    families = {item.family for item in qb}
    assert families == {"pass-yards", "pass-td"}
    assert all(item.tier == "silver" for item in qb)
    rb = player_awards.build_player_awards(
        [_row(2025, rushing_yards=1600, rushing_tds=16, rush_attempts=290)],
        position="RB",
    )
    families = {item.family for item in rb}
    assert "rush-yards" in families
    assert "rush-td" in families
    assert "workhorse" in families
    te = player_awards.build_player_awards(
        [_row(2025, targets=112)],
        position="TE",
    )
    assert te[0].family == "targets"
    wr_targets = player_awards.build_player_awards(
        [_row(2025, targets=112)],
        position="WR",
    )
    assert wr_targets == ()


def test_no_duplicate_tier_badges_for_the_same_season():
    badges = player_awards.build_player_awards(
        [_row(2025, position_finish=1, overall_finish=3, receiving_yards=1800)],
        position="WR",
    )
    positional = [item for item in badges if item.family == "positional-finish"]
    overall = [item for item in badges if item.family == "overall-finish"]
    yards = [item for item in badges if item.family == "rec-yards"]
    assert len(positional) == 1
    assert positional[0].tier == "gold"
    assert "Top-5" not in positional[0].short_label
    assert "Top-10" not in positional[0].short_label
    assert len(overall) == 1
    assert overall[0].tier == "gold"
    assert len(yards) == 1
    assert yards[0].tier == "gold"


def test_deterministic_ordering_and_display_limit():
    badges = player_awards.build_player_awards(
        [
            _row(
                2024,
                position_finish=2,
                overall_finish=8,
                receiving_yards=1600,
                receiving_tds=13,
                targets=150,
            ),
            _row(2023, position_finish=9, receiving_yards=1010),
        ],
        position="WR",
    )
    again = player_awards.build_player_awards(
        [
            _row(
                2024,
                position_finish=2,
                overall_finish=8,
                receiving_yards=1600,
                receiving_tds=13,
                targets=150,
            ),
            _row(2023, position_finish=9, receiving_yards=1010),
        ],
        position="WR",
    )
    assert [item.badge_id for item in badges] == [item.badge_id for item in again]
    assert [item.family for item in badges] == [
        "positional-finish",
        "overall-finish",
        "rec-yards",
        "rec-td",
        "targets",
    ]
    visible = player_awards.select_display_badges(badges, limit=3)
    overflow = player_awards.remaining_badges(badges, limit=3)
    assert [item.family for item in visible] == [
        "positional-finish",
        "overall-finish",
        "rec-yards",
    ]
    assert [item.family for item in overflow] == ["rec-td", "targets"]
    html = player_quick_view.accolades_html(visible, overflow=overflow)
    assert "View all accomplishments" in html
    assert html.count("pqv-accolade--gold") >= 1


def test_finish_outside_top_ten_is_not_a_badge():
    badges = player_awards.build_player_awards(
        [_row(2025, position_finish=11, overall_finish=12)],
        position="WR",
    )
    assert badges == ()


def test_unknown_position_skips_awards():
    assert player_awards.build_player_awards(
        [_row(2025, position_finish=1, kicking_points=140)],
        position="K",
    ) == ()


def test_local_cache_computes_finishes_without_fetch(tmp_path):
    payload = {
        "alpha": {
            "position": "WR",
            "stats_season": 2024,
            "fantasy_points_ppr": 320.0,
            "receiving_yards": 1600,
        },
        "beta": {
            "position": "WR",
            "stats_season": 2024,
            "fantasy_points_ppr": 210.0,
            "receiving_yards": 900,
        },
        "qb1": {
            "position": "QB",
            "stats_season": 2024,
            "fantasy_points_ppr": 400.0,
        },
    }
    (tmp_path / "sleeper_player_stats_2024.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    index = player_awards.build_season_cache_index(tmp_path)
    rows = player_awards.award_rows_for_player(
        index,
        player_id="alpha",
        current_row={"player_id": "alpha", "position": "WR"},
        position="WR",
    )
    assert rows[0]["position_finish"] == 1
    assert rows[0]["overall_finish"] == 2
    badges = player_awards.build_player_awards(rows, position="WR")
    families = {item.family for item in badges}
    assert "positional-finish" in families
    assert "overall-finish" in families
    missing = player_awards.build_season_cache_index(tmp_path / "empty")
    assert missing == ()


def test_accolades_html_is_visual_seasonal_and_omits_empty():
    badges = player_awards.build_player_awards(
        [_row(2025, position_finish=2, receiving_yards=1100)],
        position="WR",
    )
    html = player_quick_view.accolades_html(player_awards.select_display_badges(badges))
    assert "Accolades" in html
    assert "pqv-accolade-medal" in html
    assert "pqv-accolade--finish" in html
    assert "pqv-accolade--yards" in html
    assert "Top-3 WR" in html
    assert "2025" in html
    assert "1,000+ Rec Yds" in html
    assert "No badges found" not in html
    assert player_quick_view.accolades_html(()) == ""


def test_mobile_accolade_cluster_stays_readable():
    assert "pqv-accolade-cluster{display:grid;gap:var(--space-sm);grid-template-columns:repeat(auto-fill,minmax(9.5rem,1fr))" in PLAYER_QUICK_VIEW_CSS
    assert "min-height:var(--touch-target-min)" in PLAYER_QUICK_VIEW_CSS
    assert "pqv-accolade--gold" in PLAYER_QUICK_VIEW_CSS
    assert "var(--color-prestige-elite)" in PLAYER_QUICK_VIEW_CSS
    html = player_quick_view.accolades_html(
        player_awards.build_player_awards(
            [_row(2025, position_finish=4)],
            position="WR",
        )
    )
    assert "pqv-accolade--silver" in html
    assert "pqv-accolade--finish" in html
    workhorse = player_quick_view.accolades_html(
        player_awards.build_player_awards(
            [_row(2025, position="RB", rush_attempts=290, rushing_yards=1100, rushing_tds=11)],
            position="RB",
        )
    )
    assert "pqv-accolade--workhorse" in workhorse or "pqv-accolade--yards" in workhorse
    assert "pqv-accolade--scores" in workhorse or "Rush TD" in workhorse
    qb = player_quick_view.accolades_html(
        player_awards.build_player_awards(
            [_row(2025, position="QB", passing_yards=4200, passing_tds=32, position_finish=4)],
            position="QB",
        )
    )
    assert "pqv-accolade--finish" in qb
    rookie = player_awards.build_player_awards(
        [_row(2025, receiving_yards=400, position_finish=40)],
        position="WR",
    )
    assert rookie == ()
    assert "font-size:var(--font-size-body)" in PLAYER_QUICK_VIEW_CSS
