"""Production-shaped Alerts / roster-news reliability fixtures (post-#421 audit)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from modules import alert_presentation
from modules import alerts_activity
from modules import alerts_activity_ui
from modules import news as news_mod
from modules import news_intelligence as ni
from modules import notification_center as nc
from modules import prepared_player_frame


BOUTTE = "boutte-1"
NICO = "nico-1"
GENERIC_LINK = "https://www.espn.com/nfl/story/_/id/generic-{i}"


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
                "player_id": NICO,
                "name": "Nico Collins",
                "team": "HOU",
                "position": "WR",
                "injury_status": "IR",
                "status": "Injured Reserve",
            },
        ]
    )


def _roster_session(*, pending: bool = False) -> dict:
    session = {
        ni.ROSTER_CONTEXT_KEY: {
            "league_id": "L1",
            "my_roster_ids": [BOUTTE],
            "starter_ids": [BOUTTE],
            "taxi_ids": [],
            "ir_ids": [],
            "opponent_ids": [],
            "free_agent_ids": [],
            "player_name_to_id": {
                "keyshawn boutte": BOUTTE,
                "nico collins": NICO,
            },
        },
        prepared_player_frame.FRAME_KEY: _players(),
        prepared_player_frame.SIGNATURE_KEY: "alerts-reliability-frame",
        "account_user_id": "u1",
        "selected_league_id": "L1",
    }
    if pending:
        session[ni.ROSTER_CONTEXT_PENDING_KEY] = True
    return session


def _trade_article():
    return {
        "title": "Keyshawn Boutte traded to the Houston Texans",
        "summary": "The Patriots traded Boutte to Houston.",
        "link": "https://www.espn.com/nfl/story/_/id/boutte-trade",
        "source": "ESPN",
        "published_ts": 1_787_520_100.0,
        "matched_player": "Keyshawn Boutte",
        "matched_player_id": BOUTTE,
        "matched_team": "HOU",
    }


def _injury_article(*, title: str, status_phrase: str, slug: str):
    return {
        "title": title,
        "summary": f"Keyshawn Boutte {status_phrase}.",
        "link": f"https://www.rotowire.com/nfl/{slug}",
        "source": "RotoWire",
        "published_ts": 1_787_520_200.0,
        "matched_player": "Keyshawn Boutte",
        "matched_player_id": BOUTTE,
        "matched_team": "HOU",
    }


def _teammate_ir_article():
    return {
        "title": "Nico Collins placed on injured reserve",
        "summary": "Houston placed Nico Collins on injured reserve.",
        "link": "https://www.cbssports.com/nfl/nico-ir",
        "source": "CBS",
        "published_ts": 1_787_520_300.0,
        "matched_player": "Nico Collins",
        "matched_player_id": NICO,
        "matched_team": "HOU",
    }


def _generic_article(index: int):
    return {
        "title": f"NFL power rankings blurb {index}",
        "summary": "League-wide notes.",
        "link": GENERIC_LINK.format(i=index),
        "source": "ESPN",
        "published_ts": 1_787_520_000.0 + index,
    }


def _render_alerts(session: dict, articles: list, *, fresh_entry: bool = True) -> str:
    html_chunks: list[str] = []

    def _pills(*_args, **_kwargs):
        return None

    with patch("modules.news.load_cached_news_pool", return_value=articles), patch.object(
        alerts_activity_ui.st, "session_state", session
    ), patch.object(alerts_activity_ui, "inject_global_styles"), patch.object(
        alerts_activity_ui, "render_html_fragment", side_effect=lambda html: html_chunks.append(html)
    ), patch.object(alerts_activity_ui.st, "container") as container, patch.object(
        alerts_activity_ui.st, "pills", side_effect=_pills
    ), patch.object(alerts_activity_ui.st, "button", return_value=False):
        col = MagicMock()
        col.__enter__ = MagicMock(return_value=col)
        col.__exit__ = MagicMock(return_value=False)
        container.return_value = col
        alerts_activity_ui.render_alerts_page(
            league_id="L1",
            session=session,
            fresh_entry=fresh_entry,
        )
    return "\n".join(html_chunks)


def test_a_roster_player_traded_first_render_my_players():
    session = _roster_session()
    joined = _render_alerts(session, [_trade_article(), _generic_article(1)])
    assert "No recent player-specific alerts" not in joined
    assert "Keyshawn Boutte" in joined
    assert "ESPN" in joined
    assert "https://www.espn.com/nfl/story/_/id/boutte-trade" in joined
    assert session.get("alerts_filter_L1_selected") == alerts_activity.FILTER_MY_PLAYERS
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
    impact = alert_presentation.structured_roster_impact(
        event, _players(), my_roster_ids=[BOUTTE]
    )
    assert impact["code"] in {
        alert_presentation.IMPACT_OPPORTUNITY_RISING,
        alert_presentation.IMPACT_TEAM_CHANGE,
    }
    assert "target share" not in impact["read"].casefold()
    assert "fantasy point" not in impact["read"].casefold()
    stats = session.get(alerts_activity.PIPELINE_STATS_KEY) or {}
    assert int(stats.get("my_players_visible_count") or 0) >= 1
    assert int(stats.get("provider_event_count") or 0) == 2


def test_a_pending_flag_does_not_blank_first_render_when_context_exists():
    session = _roster_session(pending=True)
    joined = _render_alerts(session, [_trade_article()])
    assert "Keyshawn Boutte" in joined
    assert "No recent player-specific alerts" not in joined


def test_a_pending_without_context_still_maps_cached_pool():
    session = {ni.ROSTER_CONTEXT_PENDING_KEY: True, "selected_league_id": "L1"}
    with patch("modules.news.load_cached_news_pool", return_value=[_trade_article()]):
        rows = alerts_activity.compose_activity_timeline(session=session, league_id="L1")
    assert rows
    assert any("Boutte" in str(row.get("headline") or "") for row in rows)


def test_b_injury_status_first_render_and_deterministic_context():
    for title, phrase, slug, expected_type in (
        ("Keyshawn Boutte ruled out", "ruled out", "boutte-out", ni.FT_INACTIVE),
        ("Keyshawn Boutte placed on injured reserve", "placed on IR", "boutte-ir", ni.FT_IR_PUP_NFI),
        ("Keyshawn Boutte lands on PUP list", "PUP list", "boutte-pup", ni.FT_IR_PUP_NFI),
    ):
        article = _injury_article(title=title, status_phrase=phrase, slug=slug)
        alert = ni.contextual_news_alert_from_article(
            article,
            my_roster_ids=[BOUTTE],
            my_starter_ids=[BOUTTE],
            player_name_to_id={"keyshawn boutte": BOUTTE},
            players_df=_players(),
        )
        assert alert.event.player_id == BOUTTE
        assert alert.event.roster_relationship in {ni.REL_MY_STARTER, ni.REL_MY_BENCH}
        assert alert.event.event_type == expected_type
        impact = alert_presentation.structured_roster_impact(
            alert.event, _players(), my_roster_ids=[BOUTTE]
        )
        assert impact["supported"] == "1"
        assert "Availability" in impact["read"] or "status" in impact["read"].casefold()
        assert "depth-chart" not in impact["read"].casefold()
        joined = _render_alerts(_roster_session(), [article, _generic_article(9)])
        assert "Keyshawn Boutte" in joined
        assert "No recent player-specific alerts" not in joined


def test_c_teammate_opportunity_maps_without_article_usage_claim():
    alert = ni.contextual_news_alert_from_article(
        _teammate_ir_article(),
        my_roster_ids=[BOUTTE],
        my_starter_ids=[BOUTTE],
        player_name_to_id={"nico collins": NICO, "keyshawn boutte": BOUTTE},
        players_df=_players(),
    )
    tile = alert_presentation.enrich_tile(
        alert.as_tile(), players_df=_players(), my_roster_ids=[BOUTTE]
    )
    assert tile["player_id"] == NICO
    assert tile["beneficiary_player_id"] == BOUTTE
    assert tile["news_roster_relationship"] not in {
        ni.REL_MY_STARTER,
        ni.REL_MY_BENCH,
        ni.REL_MY_TAXI,
        ni.REL_MY_IR,
    }
    assert "Opportunity may rise" in (tile.get("fantasygm_read") or "")
    assert "target share" not in (tile.get("fantasygm_read") or "").casefold()
    session = _roster_session()
    joined = _render_alerts(session, [_teammate_ir_article()])
    assert "Nico Collins" in joined
    assert "Opportunity" in joined
    with patch("modules.news.load_cached_news_pool", return_value=[_teammate_ir_article()]):
        visible = alerts_activity.filter_timeline(
            alerts_activity.compose_activity_timeline(session=session, league_id="L1"),
            alerts_activity.FILTER_MY_PLAYERS,
            my_roster_ids=[BOUTTE],
        )
    assert any(row.get("beneficiary_player_id") == BOUTTE for row in visible)
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None


def test_d_non_roster_league_news_stays_off_my_players_and_does_not_toast():
    session = _roster_session()
    generic = _generic_article(3)
    joined = _render_alerts(session, [generic])
    assert "power rankings blurb" not in joined
    with patch("modules.news.load_cached_news_pool", return_value=[generic]):
        rows = alerts_activity.compose_activity_timeline(session=session, league_id="L1")
        news_filter = alerts_activity.filter_timeline(rows, alerts_activity.FILTER_NEWS)
        my_players = alerts_activity.filter_timeline(
            rows, alerts_activity.FILTER_MY_PLAYERS, my_roster_ids=[BOUTTE]
        )
    assert any("power rankings" in str(row.get("headline") or "").casefold() for row in news_filter)
    assert not any("power rankings" in str(row.get("headline") or "").casefold() for row in my_players)
    tile = {
        "label": "News Alert",
        "value": generic["title"],
        "id": "news-generic-3",
        "recommendation_id": "news-event:generic:OTHER",
        "player_id": "",
        "news_event_type": "OTHER",
        "news_event_severity": "LOW",
        "news_roster_relationship": "",
        "news_age_seconds": 60,
        "should_alert": False,
        "toast_tier": "informational",
        "material_signature": "sig-generic",
    }
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None


def test_e_duplicate_event_does_not_repeat_toast_or_inflate_unread():
    tile = {
        "label": "News Alert",
        "value": "Keyshawn Boutte traded to HOU",
        "id": "news-boutte-trade",
        "recommendation_id": "news-event:boutte-1:TRADE",
        "player_id": BOUTTE,
        "news_event_type": "TRADE",
        "news_event_severity": "HIGH",
        "news_roster_relationship": "MY_STARTER",
        "news_age_seconds": 120,
        "should_alert": True,
        "toast_tier": "high",
        "material_signature": "sig-trade-prod",
        "event_identity": "news-event:boutte-1:TRADE",
    }
    session: dict = {"account_user_id": "u1", "selected_league_id": "L1"}
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    first_unread = nc.unread_count(nc.compose_activity_inbox(session=session, league_id="L1"))
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is not None
    nc.publish_activity_inventory(session, [tile, tile], league_id="L1", inventory_complete=True)
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None
    second_unread = nc.unread_count(nc.compose_activity_inbox(session=session, league_id="L1"))
    assert second_unread == first_unread
    stats = session.get(alerts_activity.PIPELINE_STATS_KEY) or {}
    assert int(stats.get("toast_suppressed_dedupe") or 0) >= 1


def test_f_read_keeps_history_dismiss_suppresses_header_attention():
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
        "material_signature": "sig-read-dismiss",
        "should_alert": True,
        "toast_tier": "high",
    }
    session: dict = {"account_user_id": "u1", "selected_league_id": "L1"}
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    inbox = nc.compose_activity_inbox(session=session, league_id="L1")
    target = next(
        item
        for item in inbox
        if item.player_id == BOUTTE or "boutte" in str(item.title or "").casefold()
    )
    assert target.unread is True
    nc.mark_notification_read(session, target.id, league_id="L1")
    after_read = next(item for item in nc.compose_activity_inbox(session=session, league_id="L1") if item.id == target.id)
    assert after_read.unread is False
    snap_ids = {
        str(rec.get("id") or rec.get("recommendation_id") or "")
        for rec in (session[nc.ACTIVITY_INBOX_SNAPSHOT_KEY].get("records") or ())
    }
    assert any("boutte" in item.casefold() for item in snap_ids)
    nc.dismiss_notification(session, target.id, league_id="L1")
    inbox = nc.compose_activity_inbox(session=session, league_id="L1")
    assert all(item.id != target.id for item in inbox)
    header = alerts_activity.compose_header_alerts(inbox)
    assert all(item.id != target.id for item in header)
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None
    assert session[nc.ACTIVITY_INBOX_SNAPSHOT_KEY].get("records")


def test_cap_keeps_roster_event_ahead_of_generic_volume():
    pool = [_generic_article(i) for i in range(45)] + [_trade_article()]
    session = _roster_session()
    with patch("modules.news.load_cached_news_pool", return_value=pool):
        extra = alerts_activity._cached_news_events(session, "L1")
    stats = session.get(alerts_activity.PIPELINE_STATS_KEY) or {}
    assert int(stats.get("provider_event_count") or 0) == 46
    assert int(stats.get("roster_related_event_count") or 0) >= 1
    assert len(extra) <= alerts_activity.MAX_TIMELINE_ITEMS
    assert int(stats.get("post_cap_count") or 0) <= alerts_activity.MAX_TIMELINE_ITEMS
    assert any(
        str(row.get("player_id") or "") == BOUTTE
        or "Boutte" in str(row.get("title") or row.get("headline") or row.get("value") or "")
        for row in extra
    )


def test_warm_header_does_not_call_fetch_news():
    news_mod.reset_provider_call_counters()
    session: dict = {"account_user_id": "u1", "selected_league_id": "L1"}
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
    with patch.object(news_mod, "fetch_news", side_effect=AssertionError("header must not fetch")):
        nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
        items = nc.list_founder_beta_notifications(session=session)
        alerts_activity.compose_header_alerts(items)
        nc.unread_count(items)
    assert news_mod.provider_call_snapshot()["rss_fetch"] == 0


def test_news_ttl_remains_twenty_minutes():
    assert news_mod.NEWS_CACHE_TTL_SECONDS == 20 * 60


def test_source_headline_stays_separate_from_fantasygm_read():
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
    headline = alert_presentation.source_headline(event)
    impact = alert_presentation.structured_roster_impact(
        event, _players(), my_roster_ids=[BOUTTE]
    )
    assert headline == "Keyshawn Boutte traded to HOU"
    assert impact["read"]
    assert headline not in impact["read"] or "Opportunity" in impact["read"] or "Team change" in impact["read"]
