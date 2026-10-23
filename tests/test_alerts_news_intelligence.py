"""Alerts first visit, roster impact, toast lifecycle, and presentation contracts."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from modules import alert_presentation
from modules import alerts_activity
from modules import news_intelligence as ni
from modules import notification_center as nc


JEANTY = "12527"
BOUTTE = "boutte-1"


def _article(
    *,
    title="Keyshawn Boutte traded to the Houston Texans",
    player="Keyshawn Boutte",
    player_id=BOUTTE,
    link="https://www.espn.com/nfl/story/_/id/boutte-trade",
):
    return {
        "title": title,
        "summary": "The Patriots traded Boutte to Houston.",
        "link": link,
        "source": "ESPN",
        "published_ts": 1_787_520_100.0,
        "matched_player": player,
        "matched_player_id": player_id,
        "matched_team": "HOU",
    }


def _players():
    return pd.DataFrame(
        [
            {
                "player_id": BOUTTE,
                "name": "Keyshawn Boutte",
                "team": "HOU",
                "position": "WR",
                "injury_status": "",
                "status": "Active",
            },
            {
                "player_id": "nico-1",
                "name": "Nico Collins",
                "team": "HOU",
                "position": "WR",
                "injury_status": "IR",
                "status": "Injured Reserve",
            },
        ]
    )


def test_trade_preserves_headline_and_structured_opportunity_read():
    event = ni.FootballEvent(
        event_type=ni.FT_TRADE,
        player_name="Keyshawn Boutte",
        player_id=BOUTTE,
        team="HOU",
        article_title="Keyshawn Boutte traded to the Houston Texans",
        source="ESPN",
        source_url="https://www.espn.com/nfl/story/_/id/boutte-trade",
        roster_relationship=ni.REL_MY_STARTER,
    )
    impact = alert_presentation.structured_roster_impact(event, _players())
    assert impact["code"] == alert_presentation.IMPACT_OPPORTUNITY_RISING
    assert "Opportunity may rise" in impact["read"]
    assert "HOU" in impact["read"]
    headline = alert_presentation.source_headline(event)
    assert headline == "Keyshawn Boutte traded to HOU"
    assert "valuation" in impact["read"].casefold() or "Monitor role" in impact["read"]


def test_no_unsupported_inference_without_team_or_status():
    event = ni.FootballEvent(
        event_type=ni.FT_TRADE,
        player_name="Keyshawn Boutte",
        player_id=BOUTTE,
        team="",
        article_title="Boutte on the move",
        roster_relationship=ni.REL_MY_BENCH,
    )
    impact = alert_presentation.structured_roster_impact(event, pd.DataFrame())
    assert impact["supported"] == "0"
    assert "Houston" not in impact["read"]


def test_my_players_outrank_generic_news():
    rows = [
        {"id": "g1", "roster_relationship": "", "severity": "LOW", "headline": "League blurb"},
        {
            "id": "m1",
            "roster_relationship": "MY_STARTER",
            "severity": "HIGH",
            "event_type": "TRADE",
            "headline": "Boutte traded",
        },
    ]
    ranked = alert_presentation.rank_timeline_rows(rows)
    assert ranked[0]["id"] == "m1"


def test_league_isolation_and_no_valuation_mutation():
    session = {
        ni.ROSTER_CONTEXT_KEY: {
            "league_id": "league-a",
            "my_roster_ids": [BOUTTE],
            "player_name_to_id": {"keyshawn boutte": BOUTTE},
        }
    }
    rows = alerts_activity.compose_activity_timeline(
        session=session,
        league_id="league-b",
        news_events=[
            {
                "id": "a1",
                "league_id": "league-a",
                "player_id": BOUTTE,
                "news_roster_relationship": "MY_STARTER",
                "value": "leak",
            }
        ],
    )
    assert not any(row.get("id") == "a1" for row in rows)
    tile = ni.NewsAlert(
        event=ni.FootballEvent(event_type=ni.FT_TRADE, player_id=BOUTTE, player_name="Boutte"),
        severity="HIGH",
        should_alert=True,
        title="t",
        body="b",
        why_care="w",
        action_hint="a",
    ).as_tile()
    assert tile["valuation_impact"] == "none_from_article"


def test_filter_timeline_uses_my_roster_ids_on_cold_relationship():
    rows = [
        {
            "id": "m1",
            "player_id": BOUTTE,
            "roster_relationship": "",
            "category": "NEWS",
            "headline": "Boutte traded",
        }
    ]
    visible = alerts_activity.filter_timeline(
        rows, alerts_activity.FILTER_MY_PLAYERS, my_roster_ids=[BOUTTE]
    )
    assert len(visible) == 1
