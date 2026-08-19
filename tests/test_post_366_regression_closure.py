from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from modules import alerts_activity
from modules import player_history
from modules import trade_hub_player_search
from modules import trade_ideas
from modules import transaction_grades


ROOT = Path(__file__).resolve().parents[1]


def test_real_component_player_event_crosses_parent_window_boundary():
    source = (ROOT / "modules" / "interaction_contract.py").read_text(encoding="utf-8")
    assert "window.parent && window.parent !== window" in source
    assert "bridgeWindow.dispatchEvent" in source
    trade = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    assert '"bridgePlayerOpens": True' in trade
    assert '"sourceLabel": "Trade Hub"' in trade


def test_alerts_compose_session_and_cached_news_instead_of_short_circuiting():
    session = {
        alerts_activity.TIMELINE_SESSION_KEY: {
            "league_id": "L1",
            "items": [{"id": "old", "title": "Older mapped update", "category": "NEWS"}],
        }
    }

    class Alert:
        def __init__(self, title: str):
            self.title = title

        def as_tile(self):
            return {"id": self.title, "title": self.title, "category": "NEWS"}

    with (
        patch("modules.news.load_cached_news_pool", return_value=[
            {"title": "Current league-wide headline", "link": "https://example.test/1"},
            {"title": "Second useful headline", "link": "https://example.test/2"},
        ]),
        patch("modules.news_intelligence.football_event_from_article", side_effect=lambda raw: raw),
        patch("modules.news_intelligence.build_news_alert", side_effect=lambda raw: Alert(raw["title"])),
    ):
        rows = alerts_activity.compose_activity_timeline(session=session, league_id="L1")

    headlines = {row["headline"] for row in rows}
    assert "Older mapped update" in headlines
    assert "Current league-wide headline" in headlines
    assert "Second useful headline" in headlines


def test_unmapped_cached_news_keeps_unique_honest_headlines():
    class GenericAlert:
        def as_tile(self):
            return {
                "id": "news-event:unknown:OTHER",
                "value": "Player: OTHER",
                "news_event_type": "OTHER",
                "category": "NEWS",
            }

    cached = [
        {"title": "Wide receiver role competition intensifies", "link": "https://example.test/a"},
        {"title": "Veteran running back clears waivers", "link": "https://example.test/b"},
    ]
    with (
        patch("modules.news.load_cached_news_pool", return_value=cached),
        patch("modules.news_intelligence.build_news_alert", return_value=GenericAlert()),
    ):
        rows = alerts_activity.compose_activity_timeline(session={}, league_id="L1")

    news = [row for row in rows if row["category"] == "NEWS"]
    assert {row["headline"] for row in news} == {
        "Wide receiver role competition intensifies",
        "Veteran running back clears waivers",
    }
    assert len({row["id"] for row in news}) == 2


def test_internal_corroboration_copy_is_humanized():
    row = alerts_activity._row_from_news_event({
        "id": "n1",
        "title": "Player update",
        "news_corroboration_note": "News only — structured status not compared.",
    })
    assert row["context"] == "Player status has not yet been confirmed."
    assert "structured status" not in row["context"]


def test_trade_hub_player_focus_replaces_and_is_league_scoped():
    state = {}
    trade_hub_player_search.queue_player_focus(state, league_id="A", player_id="p1")
    trade_hub_player_search.queue_player_focus(state, league_id="A", player_id="p2")
    assert not trade_hub_player_search.consume_player_focus(state, league_id="A", player_id="p1")
    assert trade_hub_player_search.consume_player_focus(state, league_id="A", player_id="p2")
    trade_hub_player_search.queue_player_focus(state, league_id="A", player_id="p3")
    assert not trade_hub_player_search.consume_player_focus(state, league_id="B", player_id="p3")


def test_multi_season_dossier_cache_preserves_2023_2024_2025(tmp_path):
    for season, points in ((2023, 200), (2024, 250), (2025, 300)):
        (tmp_path / f"sleeper_player_stats_{season}.json").write_text(
            json.dumps({"p1": {"stats_season": season, "fantasy_points_ppr": points, "games_played": 17}}),
            encoding="utf-8",
        )
    resume = player_history.load_cached_career_resume(
        player_id="p1",
        current_row={"player_id": "p1", "position": "WR", "stats_season": 2025},
        position_lookup={"p1": "WR"},
        cache_dir=tmp_path,
    )
    assert [season.season for season in resume.seasons] == [2025, 2024, 2023]
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "season_stats_history_html(stats_resume)" in app_source


def _pick_trade(picks):
    return {
        "type": "trade",
        "week": 1,
        "sides": [
            {"team_name": "A", "receives": picks},
            {"team_name": "B", "receives": [{"kind": "player", "player_id": "p1", "name": "Player"}]},
        ],
    }


def test_future_round_pick_receives_provisional_grade():
    report = transaction_grades.grade_trade(
        _pick_trade([{"kind": "pick", "season": "2027", "round": 1, "name": "2027 Round 1"}]),
        player_lookup={"p1": {"value_score": 6500}},
        current_week=10,
    )
    assert not report["pending"]
    assert report["provisional"]
    assert all(side["letter"] != transaction_grades.PENDING for side in report["sides"])
    assert "estimated until the selection is known" in report["sides"][0]["why"]


def test_multiple_future_picks_and_player_receive_a_provisional_grade():
    report = transaction_grades.grade_trade(
        _pick_trade([
            {"kind": "player", "player_id": "p2", "name": "Second Player"},
            {"kind": "pick", "season": "2027", "round": 2, "name": "2027 Round 2"},
            {"kind": "pick", "season": "2028", "round": 3, "name": "2028 Round 3"},
        ]),
        player_lookup={"p1": {"value_score": 6500}, "p2": {"value_score": 4200}},
        current_week=10,
    )
    assert not report["pending"]
    assert report["provisional"]
    assert "Received" in report["sides"][0]["why"]


def test_explicit_and_projected_pick_identity_use_canonical_pick_owner():
    exact = transaction_grades.grade_trade(
        _pick_trade([{"kind": "pick", "season": "2027", "round": 1, "value_score": 6100}]),
        player_lookup={"p1": {"value_score": 6500}},
        current_week=10,
    )
    projected = transaction_grades.grade_trade(
        _pick_trade([{"kind": "pick", "season": "2027", "round": 1, "projected_slot": "early"}]),
        player_lookup={"p1": {"value_score": 6500}},
        current_week=10,
    )
    assert trade_ideas.canonical_pick_identity_value(
        {"season": "2027", "round": 1, "value_score": 6100}
    ) == 6100
    assert trade_ideas.canonical_pick_identity_value(
        {"season": "2027", "round": 1, "projected_slot": "early"}
    ) > 0
    assert exact["provisional"] and projected["provisional"]


def test_resolved_pick_uses_player_value_and_is_not_provisional():
    report = transaction_grades.grade_trade(
        _pick_trade([{"kind": "pick", "player_id": "rookie", "season": "2025", "round": 1, "name": "Resolved pick"}]),
        player_lookup={"p1": {"value_score": 6500}, "rookie": {"value_score": 7200}},
        current_week=10,
    )
    assert not report["pending"]
    assert not report["provisional"]


def test_pick_missing_all_identity_remains_pending():
    report = transaction_grades.grade_trade(
        _pick_trade([{"kind": "pick", "name": "Unknown pick"}]),
        player_lookup={"p1": {"value_score": 6500}},
        current_week=10,
    )
    assert report["pending"]


def test_header_and_team_comparison_mobile_contracts_are_square_and_unclipped():
    header = (ROOT / "modules" / "executive_command_header_styles.py").read_text(encoding="utf-8")
    assert "border-radius: 0 !important" in header
    dense = (ROOT / "modules" / "dense_list_styles.py").read_text(encoding="utf-8")
    assert '.dg-team-comparison-board .dg-dense-status__secondary::before{content:none' in dense
    assert "text-overflow:clip;white-space:normal" in dense


def test_bridge_has_no_layout_height_below_command_header():
    source = (ROOT / "modules" / "player_quick_view_bridge.py").read_text(encoding="utf-8")
    assert "width=1" in source
    assert 'height="content"' in source
