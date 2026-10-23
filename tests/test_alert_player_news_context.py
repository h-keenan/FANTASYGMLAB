"""Canonical Alert -> player focus -> PQV news-context contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from modules import news_intelligence
from modules import notification_center as nc
from modules import player_cards
from modules import alerts_activity


ROOT = Path(__file__).resolve().parents[1]
JEANTY_ID = "12527"


def _tile(*, source_url: str = "https://example.com/jeanty-report") -> dict:
    return {
        "label": "News Alert",
        "value": "Ashton Jeanty injury update",
        "note": "A potentially significant injury was reported.",
        "recommendation_id": "news-event:12527:injury_chain",
        "route_key": "my_team",
        "route_player_id": JEANTY_ID,
        "player_id": JEANTY_ID,
        "news_player_name": "Ashton Jeanty",
        "news_event_type": "INJURY",
        "news_event_severity": "HIGH",
        "news_roster_relationship": "MY_STARTER",
        "news_event_time": 2_000_000_000.0,
        "news_age_seconds": 120,
        "news_age_label": "2m",
        "news_corroboration": "AWAITING STATUS UPDATE",
        "news_corroboration_note": "Player status has not yet been confirmed.",
        "news_significant_injury_event": True,
        "news_source": "Fixture Wire",
        "source_url": source_url,
        "news_article_title": "Ashton Jeanty injury update",
        "should_alert": True,
    }


def _state(tile: dict | None = None) -> dict:
    state = {"account_user_id": "founder", "selected_league_id": "L1"}
    nc.publish_activity_inventory(state, [tile or _tile()], league_id="L1")
    return state


def test_news_alert_tile_preserves_existing_canonical_source_fields():
    event = news_intelligence.FootballEvent(
        event_type="INJURY",
        player_name="Ashton Jeanty",
        player_id=JEANTY_ID,
        source="Fixture Wire",
        source_url="https://example.com/jeanty-report",
        article_title="Ashton Jeanty injury update",
    )
    tile = news_intelligence.NewsAlert(
        event=event,
        severity="HIGH",
        should_alert=True,
        title="Ashton Jeanty injury update",
        body="Report",
        why_care="Affects your starter.",
        action_hint="Review roster.",
    ).as_tile()
    assert tile["news_source"] == "Fixture Wire"
    assert tile["source_url"] == "https://example.com/jeanty-report"
    assert tile["news_article_title"] == "Ashton Jeanty injury update"


def test_news_alert_tile_sets_route_player_name_alongside_route_player_id():
    # coridian_: a free-agent injury watch tile ("KaVontae Turpin ruled
    # out") had no player card despite a resolved player_id, because this
    # tile only ever put the name in the display-only news_player_name
    # field. BriefingItemPlayers.tsx requires route_player_name AND
    # route_player_id truthy together to render an identity card.
    event = news_intelligence.FootballEvent(
        event_type="INJURY",
        player_name="KaVontae Turpin",
        player_id="turpin-1",
        source="Fixture Wire",
    )
    tile = news_intelligence.NewsAlert(
        event=event,
        severity="HIGH",
        should_alert=True,
        title="KaVontae Turpin ruled out",
        body="Report",
        why_care="Affects the free-agent pool.",
        action_hint="Monitor.",
    ).as_tile()
    assert tile["route_player_id"] == "turpin-1"
    assert tile["route_player_name"] == "KaVontae Turpin"
