"""Alerts first visit, roster impact, toast lifecycle, and presentation contracts."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from modules import alert_presentation
from modules import alerts_activity
from modules import alerts_activity_ui
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


def test_cold_alerts_my_players_populated_on_first_visit():
    session = {
        ni.ROSTER_CONTEXT_KEY: {
            "league_id": "L1",
            "my_roster_ids": [BOUTTE],
            "starter_ids": [BOUTTE],
            "taxi_ids": [],
            "ir_ids": [],
            "opponent_ids": [],
            "free_agent_ids": [],
            "player_name_to_id": {"keyshawn boutte": BOUTTE},
        }
    }
    html_chunks: list[str] = []
    pills_calls: list[object] = []

    def _pills(*_args, **_kwargs):
        pills_calls.append(_kwargs.get("key"))
        return None

    with patch("modules.news.load_cached_news_pool", return_value=[_article()]), patch.object(
        alerts_activity_ui.st, "session_state", session
    ), patch.object(alerts_activity_ui, "inject_global_styles"), patch.object(
        alerts_activity_ui, "render_html_fragment", side_effect=lambda html: html_chunks.append(html)
    ), patch.object(alerts_activity_ui.st, "container") as container, patch.object(
        alerts_activity_ui.st, "pills", side_effect=_pills
    ), patch.object(alerts_activity_ui.st, "columns", return_value=[]), patch.object(
        alerts_activity_ui.st, "caption"
    ), patch.object(alerts_activity_ui.st, "button", return_value=False):
        col = MagicMock()
        col.__enter__ = MagicMock(return_value=col)
        col.__exit__ = MagicMock(return_value=False)
        container.return_value = col
        alerts_activity_ui.render_alerts_page(
            league_id="L1",
            session=session,
            fresh_entry=True,
        )
    joined = "\n".join(html_chunks)
    assert "No recent player-specific alerts" not in joined
    assert "Keyshawn Boutte" in joined
    assert session.get("alerts_filter_L1_selected") == alerts_activity.FILTER_MY_PLAYERS
    assert pills_calls


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


def test_toast_once_then_deduped_and_still_in_alerts():
    tile = {
        "label": "News Alert",
        "value": "Keyshawn Boutte traded to HOU",
        "id": "news-boutte-trade",
        "recommendation_id": "news-event:boutte-1:TRADE",
        "player_id": BOUTTE,
        "news_player_name": "Keyshawn Boutte",
        "news_event_type": "TRADE",
        "news_event_severity": "HIGH",
        "news_roster_relationship": "MY_STARTER",
        "news_age_seconds": 120,
        "news_event_time": 1_787_520_100.0,
        "source_url": "https://www.espn.com/nfl/story/_/id/boutte-trade",
        "news_article_title": "Keyshawn Boutte traded to the Houston Texans",
        "should_alert": True,
        "toast_tier": "high",
        "material_signature": "sig-trade-1",
    }
    session: dict = {"account_user_id": "u1", "selected_league_id": "L1"}
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    first = nc.consume_pending_urgent_delivery(session, league_id="L1")
    assert first is not None
    second = nc.consume_pending_urgent_delivery(session, league_id="L1")
    assert second is None
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    third = nc.consume_pending_urgent_delivery(session, league_id="L1")
    assert third is None
    rows = alerts_activity.compose_activity_timeline(session=session, league_id="L1", news_events=[tile])
    assert any(row.get("player_id") == BOUTTE for row in rows)


def test_informational_news_does_not_toast():
    tile = {
        "label": "News Alert",
        "value": "Practice notes",
        "id": "news-notes",
        "recommendation_id": "news-event:x:OTHER",
        "player_id": BOUTTE,
        "news_event_type": "OTHER",
        "news_event_severity": "LOW",
        "news_roster_relationship": "MY_BENCH",
        "news_age_seconds": 60,
        "should_alert": False,
        "toast_tier": "informational",
        "material_signature": "sig-info",
    }
    session: dict = {"account_user_id": "u1", "selected_league_id": "L1"}
    nc.publish_activity_inventory(session, [tile], league_id="L1")
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None


def test_read_and_dismiss_do_not_delete_history():
    tile = {
        "label": "News Alert",
        "value": "Boutte traded",
        "id": "news-boutte-trade",
        "recommendation_id": "news-event:boutte-1:TRADE",
        "player_id": BOUTTE,
        "news_event_type": "TRADE",
        "news_event_severity": "HIGH",
        "news_roster_relationship": "MY_STARTER",
        "news_age_seconds": 90,
        "material_signature": "sig-2",
        "should_alert": True,
    }
    session: dict = {"account_user_id": "u1", "selected_league_id": "L1"}
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    nc.mark_notification_read(session, "news-boutte-trade", league_id="L1")
    nc.dismiss_notification(session, "news-boutte-trade", league_id="L1")
    assert nc.is_notification_read(session, "news-boutte-trade", league_id="L1")
    assert nc.is_notification_dismissed(session, "news-boutte-trade", league_id="L1")
    snap = session[nc.ACTIVITY_INBOX_SNAPSHOT_KEY]
    ids = {str(rec.get("id") or rec.get("recommendation_id") or "") for rec in snap.get("records") or ()}
    assert any("boutte-1:TRADE" in item or "boutte" in item.casefold() for item in ids)


def test_header_count_uses_unread_and_view_all_exists():
    tile = {
        "label": "News Alert",
        "value": "Boutte traded",
        "id": "news-boutte-trade",
        "recommendation_id": "news-event:boutte-1:TRADE",
        "player_id": BOUTTE,
        "news_event_type": "TRADE",
        "news_event_severity": "HIGH",
        "news_roster_relationship": "MY_STARTER",
        "news_age_seconds": 90,
        "should_alert": True,
    }
    session: dict = {"account_user_id": "u1", "selected_league_id": "L1"}
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    items = nc.compose_activity_inbox(session=session, league_id="L1", header_cap=True)
    assert nc.unread_count(items) >= 1
    header = alerts_activity.compose_header_alerts(items)
    assert header
    source = (alerts_activity_ui.__file__)
    ui = open(source, encoding="utf-8").read()
    assert "Read source" in ui


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
