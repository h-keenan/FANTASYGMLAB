from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from modules import alerts_activity
from modules import news_intelligence as ni


ROOT = Path(__file__).resolve().parents[1]
JEANTY_ID = "12527"
JEANTY_HEADLINE = "Ashton Jeanty helped off field with apparent right knee injury"


def _article(title: str = JEANTY_HEADLINE) -> dict:
    return {
        "title": title,
        "summary": title,
        "source": "Fixture Desk",
        "link": "https://example.test/jeanty-injury",
        "published_ts": 1_787_520_000,
    }


def _players(*, team: str | None = "LV") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "player_id": JEANTY_ID,
                "name": "Ashton Jeanty",
                "team": team,
                "status": "Active",
                "injury_status": None,
            },
            {
                "player_id": "other-jeanty",
                "name": "Michael Jeanty",
                "team": "FA",
                "status": "Active",
                "injury_status": None,
            },
        ]
    )


def test_actual_jeanty_record_is_canonical_and_roster_event_is_high_attention():
    sleeper = json.loads((ROOT / "data" / "sleeper_players.json").read_text(encoding="utf-8"))
    actual = sleeper[JEANTY_ID]
    assert actual["full_name"] == "Ashton Jeanty"
    assert actual["active"] is True

    players = _players()
    alert = ni.contextual_news_alert_from_article(
        _article(),
        my_roster_ids=[JEANTY_ID],
        player_name_to_id=ni.canonical_player_name_index(players),
        players_df=players,
    )

    assert alert.event.player_id == JEANTY_ID
    assert alert.event.roster_relationship == ni.REL_MY_BENCH
    assert alert.event.significant_injury_event is True
    assert alert.severity == ni.SEV_HIGH
    assert alert.should_alert is True
    assert "Potentially significant injury event" in alert.body
    assert "Status not yet confirmed" in alert.body


def test_rostered_routine_news_keeps_relationship_without_false_escalation():
    players = _players()
    alert = ni.contextual_news_alert_from_article(
        _article("Ashton Jeanty discusses offseason preparation"),
        my_roster_ids=[JEANTY_ID],
        player_name_to_id=ni.canonical_player_name_index(players),
        players_df=players,
    )
    assert alert.event.player_id == JEANTY_ID
    assert alert.event.roster_relationship == ni.REL_MY_BENCH
    assert alert.event.significant_injury_event is False
    assert alert.severity != ni.SEV_HIGH


def test_non_rostered_severe_injury_is_not_promoted_as_my_roster():
    players = _players()
    alert = ni.contextual_news_alert_from_article(
        _article(),
        opponent_ids=[JEANTY_ID],
        player_name_to_id=ni.canonical_player_name_index(players),
        players_df=players,
    )
    assert alert.event.roster_relationship == ni.REL_OPPONENT_ROSTER
    assert alert.severity == ni.SEV_MEDIUM


def test_unresolved_and_ambiguous_identity_fail_closed():
    unresolved = ni.contextual_news_alert_from_article(
        _article("A rookie running back was helped off field with a knee injury"),
        my_roster_ids=[JEANTY_ID],
        player_name_to_id=ni.canonical_player_name_index(_players()),
    )
    assert unresolved.event.player_id == ""
    assert unresolved.event.roster_relationship == ni.REL_UNKNOWN
    assert unresolved.should_alert is False

    ambiguous_index = {"ashton jeanty": JEANTY_ID, "ashton jeanty jr": "duplicate"}
    ambiguous = ni.contextual_news_alert_from_article(
        _article("Ashton Jeanty Jr and Ashton Jeanty discussed injuries"),
        my_roster_ids=[JEANTY_ID],
        player_name_to_id=ambiguous_index,
    )
    assert ambiguous.event.player_id == ""
    assert ambiguous.event.roster_relationship == ni.REL_UNKNOWN


def test_rostered_player_with_null_nfl_team_still_resolves_from_fantasy_roster():
    players = _players(team=None)
    alert = ni.contextual_news_alert_from_article(
        _article(),
        my_roster_ids=[JEANTY_ID],
        player_name_to_id=ni.canonical_player_name_index(players),
        players_df=players,
    )
    assert alert.event.roster_relationship == ni.REL_MY_BENCH
    assert alert.severity == ni.SEV_HIGH


def test_alerts_cached_pool_uses_league_scoped_roster_context_without_session_leak():
    players = _players()
    index = ni.canonical_player_name_index(players)
    session_a: dict = {}
    session_b: dict = {}
    session_a[ni.ROSTER_CONTEXT_PENDING_KEY] = True
    ni.store_news_roster_context(
        session_a,
        league_id="league-a",
        roster_id="1",
        my_roster_ids=[JEANTY_ID],
        player_name_to_id=index,
    )
    assert ni.ROSTER_CONTEXT_PENDING_KEY not in session_a
    ni.store_news_roster_context(
        session_b,
        league_id="league-b",
        roster_id="2",
        opponent_ids=[JEANTY_ID],
        player_name_to_id=index,
    )

    with patch("modules.news.load_cached_news_pool", return_value=[_article()]):
        rows_a = alerts_activity.compose_activity_timeline(
            session=session_a, league_id="league-a", news_events=None
        )
        rows_b = alerts_activity.compose_activity_timeline(
            session=session_b, league_id="league-b", news_events=None
        )

    jeanty_a = next(row for row in rows_a if row.get("player_id") == JEANTY_ID)
    jeanty_b = next(row for row in rows_b if row.get("player_id") == JEANTY_ID)
    assert jeanty_a["roster_relationship"] == ni.REL_MY_BENCH
    assert jeanty_a["category"] == "URGENT"
    assert jeanty_b["roster_relationship"] == ni.REL_OPPONENT_ROSTER
    assert jeanty_b["category"] == "NEWS"


def test_dashboard_tile_builder_promotes_same_contextual_alert():
    players = _players()
    session: dict = {}
    tiles = ni.build_roster_news_alert_tiles(
        [_article()],
        session=session,
        league_id="league-a",
        my_team_df=players.iloc[[0]],
        players_df=players,
        now=1_787_520_100,
    )
    assert len(tiles) == 1
    assert tiles[0]["player_id"] == JEANTY_ID
    assert tiles[0]["news_roster_relationship"] == ni.REL_MY_BENCH
    assert tiles[0]["news_event_severity"] == ni.SEV_HIGH
    assert tiles[0]["should_alert"] is True
