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


def _render_alerts(
    session: dict,
    articles: list,
    *,
    fresh_entry: bool = True,
    players_df=None,
    my_roster_ids=None,
    open_player=None,
    button_pressed=None,
):
    html_chunks: list[str] = []
    button_labels: list[str] = []
    button_regs: list[dict] = []

    def _pills(*_args, **_kwargs):
        return None

    def _button(label, **kwargs):
        key = str(kwargs.get("key") or "")
        button_labels.append(str(label))
        button_regs.append({"label": str(label), "key": key})
        if callable(button_pressed):
            return bool(button_pressed(str(label), key))
        return bool(session.get(key))

    def _columns(spec, **_kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        cols = []
        for _ in range(count):
            col = MagicMock()
            col.__enter__ = MagicMock(return_value=col)
            col.__exit__ = MagicMock(return_value=False)
            cols.append(col)
        return cols

    with patch("modules.news.load_cached_news_pool", return_value=articles), patch.object(
        alerts_activity_ui.st, "session_state", session
    ), patch.object(alerts_activity_ui, "inject_global_styles"), patch.object(
        alerts_activity_ui, "render_html_fragment", side_effect=lambda html: html_chunks.append(html)
    ), patch.object(alerts_activity_ui.st, "container") as container, patch.object(
        alerts_activity_ui.st, "pills", side_effect=_pills
    ), patch.object(alerts_activity_ui.st, "columns", side_effect=_columns), patch.object(
        alerts_activity_ui.st, "caption"
    ), patch.object(alerts_activity_ui.st, "button", side_effect=_button):
        col = MagicMock()
        col.__enter__ = MagicMock(return_value=col)
        col.__exit__ = MagicMock(return_value=False)
        container.return_value = col
        alerts_activity_ui.render_alerts_page(
            league_id="L1",
            session=session,
            fresh_entry=fresh_entry,
            players_df=players_df if players_df is not None else session.get(prepared_player_frame.FRAME_KEY),
            my_roster_ids=my_roster_ids,
            open_player_quick_view=open_player,
        )
    return "\n".join(html_chunks), button_labels, button_regs


def test_a_roster_player_traded_first_render_my_players():
    session = _roster_session()
    joined, _buttons, _regs = _render_alerts(session, [_trade_article(), _generic_article(1)])
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
    joined, _buttons, _regs = _render_alerts(session, [_trade_article()])
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
        joined, _buttons, _regs = _render_alerts(_roster_session(), [article, _generic_article(9)])
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
    joined, _buttons, _regs = _render_alerts(session, [_teammate_ir_article()])
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
    joined, _buttons, _regs = _render_alerts(session, [generic])
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


def test_first_navigation_cached_news_uses_process_frame_without_reload():
    prepared_player_frame.clear_process_valued_ranked_frames()
    prepared_player_frame._PROCESS_FRAME_STORE["alerts-first-paint"] = _players()
    session = {
        ni.ROSTER_CONTEXT_PENDING_KEY: True,
        "account_user_id": "u1",
        "selected_league_id": "L1",
    }
    with patch("modules.news.load_cached_news_pool", return_value=[_trade_article()]):
        alerts_activity.hydrate_alerts_first_paint(
            session,
            league_id="L1",
            roster_id="1",
            my_roster_ids=[BOUTTE],
            starter_ids=[BOUTTE],
            player_name_to_id={},
            players_df=None,
        )
        rows = alerts_activity.compose_activity_timeline(session=session, league_id="L1")
        visible = alerts_activity.filter_timeline(
            rows,
            alerts_activity.FILTER_MY_PLAYERS,
            my_roster_ids=[BOUTTE],
            session=session,
            league_id="L1",
        )
    prepared_player_frame.clear_process_valued_ranked_frames()
    assert visible
    assert any(row.get("player_id") == BOUTTE for row in visible)
    stats = session.get(alerts_activity.PIPELINE_STATS_KEY) or {}
    assert stats.get("alerts_route_first_render") is True
    assert int(stats.get("roster_ids_count_after_store") or 0) >= 1
    assert int(stats.get("cached_pool_count") or stats.get("provider_event_count") or 0) >= 1
    assert int(stats.get("my_players_visible_count") or 0) >= 1
    joined, buttons, _regs = _render_alerts(
        session,
        [_trade_article()],
        my_roster_ids=[BOUTTE],
        players_df=_players(),
    )
    assert "No recent player-specific alerts" not in joined
    assert "Mark read" in buttons
    assert "Dismiss" in buttons


def test_read_interaction_updates_header_and_suppresses_toast():
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
        "toast_tier": "high",
        "material_signature": "sig-read-ui",
    }
    session: dict = {"account_user_id": "u1", "selected_league_id": "L1"}
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    before_unread = nc.unread_count(nc.compose_activity_inbox(session=session, league_id="L1"))
    row = {"id": "news-boutte-trade", "recommendation_id": "news-event:boutte-1:TRADE"}
    nc.mark_alert_read(session, row, league_id="L1")
    after = nc.compose_activity_inbox(session=session, league_id="L1")
    assert nc.unread_count(after) < before_unread
    assert any(item.player_id == BOUTTE for item in after)
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None
    rows = alerts_activity.compose_activity_timeline(
        session=session, league_id="L1", news_events=[tile]
    )
    mine = alerts_activity.filter_timeline(
        rows, alerts_activity.FILTER_MY_PLAYERS, my_roster_ids=[BOUTTE], session=session, league_id="L1"
    )
    assert mine
    assert all(row.get("unread") is False for row in mine if row.get("player_id") == BOUTTE)
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None


def test_dismiss_interaction_clears_inbox_keeps_snapshot_and_suppresses_toast():
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
        "toast_tier": "high",
        "material_signature": "sig-dismiss-ui",
    }
    session: dict = {"account_user_id": "u1", "selected_league_id": "L1"}
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    before_unread = nc.unread_count(nc.compose_activity_inbox(session=session, league_id="L1"))
    assert before_unread >= 1
    nc.dismiss_alert(
        session,
        {"id": "news-boutte-trade", "recommendation_id": "news-event:boutte-1:TRADE"},
        league_id="L1",
    )
    inbox = nc.compose_activity_inbox(session=session, league_id="L1")
    assert all("boutte-1:TRADE" not in (item.id or "") + (item.recommendation_id or "") for item in inbox)
    assert nc.unread_count(inbox) < before_unread
    assert session[nc.ACTIVITY_INBOX_SNAPSHOT_KEY].get("records")
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None
    rows = alerts_activity.compose_activity_timeline(
        session=session, league_id="L1", news_events=[tile]
    )
    mine = alerts_activity.filter_timeline(
        rows, alerts_activity.FILTER_MY_PLAYERS, my_roster_ids=[BOUTTE], session=session, league_id="L1"
    )
    assert not any(row.get("player_id") == BOUTTE for row in mine)
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None


def test_generic_news_relationship_kind_stays_out_of_my_players():
    session = _roster_session()
    with patch("modules.news.load_cached_news_pool", return_value=[_generic_article(4)]):
        rows = alerts_activity.compose_activity_timeline(session=session, league_id="L1")
    kinds = {alerts_activity.row_relationship_kind(row, [BOUTTE]) for row in rows}
    assert alerts_activity.KIND_GENERIC in kinds or rows
    mine = alerts_activity.filter_timeline(
        rows, alerts_activity.FILTER_MY_PLAYERS, my_roster_ids=[BOUTTE]
    )
    assert not any("power rankings" in str(row.get("headline") or "").casefold() for row in mine)


def _open_player(_pid, **_kwargs):
    return None


def test_render_path_registers_unread_and_read_action_buttons():
    session = _roster_session()
    joined, labels, regs = _render_alerts(
        session,
        [_trade_article()],
        open_player=_open_player,
        my_roster_ids=[BOUTTE],
        players_df=_players(),
    )
    assert "Keyshawn Boutte" in joined
    assert "data-dg-alerts-source='1'" in joined or 'data-dg-alerts-source="1"' in joined
    assert "Mark read" in labels
    assert "Dismiss" in labels
    assert "Open player" in labels
    keys = [item["key"] for item in regs]
    assert len(keys) == len(set(keys))
    assert all(key.startswith("alerts_action_") for key in keys)
    assert ":" not in "".join(keys)
    stats = session.get(alerts_activity.PIPELINE_STATS_KEY) or {}
    assert int(stats.get("mark_read_button_eligible_count") or 0) >= 1
    assert int(stats.get("dismiss_button_eligible_count") or 0) >= 1
    assert int(stats.get("duplicate_event_id_count") or 0) == 0

    row = {
        "id": "news-boutte-trade",
        "recommendation_id": "news-event:boutte-1:TRADE",
        "event_identity": "identity-boutte-trade",
        "player_id": BOUTTE,
        "unread": False,
        "dismissed": False,
        "attention_id": "identity-boutte-trade",
        "headline": "Keyshawn Boutte traded to the Houston Texans",
        "source_url": "https://www.espn.com/nfl/story/_/id/boutte-trade",
        "roster_relationship": "MY_STARTER",
        "relationship_kind": alerts_activity.KIND_MY_PLAYER,
        "kind": "news",
        "category": "URGENT",
        "alert_worthy": True,
    }
    with patch.object(alerts_activity, "compose_activity_timeline", return_value=(row,)), patch.object(
        alerts_activity, "hydrate_alerts_first_paint", return_value={}
    ):
        _joined, read_labels, read_regs = _render_alerts(
            session,
            [_trade_article()],
            open_player=_open_player,
            my_roster_ids=[BOUTTE],
            players_df=_players(),
        )
    assert "Open player" in read_labels
    assert "Mark read" not in read_labels
    assert "Dismiss" in read_labels
    assert len({item["key"] for item in read_regs}) == len(read_regs)


def test_dismissed_row_is_absent_from_active_my_players():
    row = {
        "id": "news-boutte-trade",
        "recommendation_id": "news-event:boutte-1:TRADE",
        "event_identity": "identity-boutte-trade",
        "player_id": BOUTTE,
        "unread": False,
        "dismissed": True,
        "relationship_kind": alerts_activity.KIND_MY_PLAYER,
        "roster_relationship": "MY_STARTER",
        "category": "URGENT",
        "alert_worthy": True,
        "kind": "news",
    }
    visible = alerts_activity.filter_timeline(
        [row],
        alerts_activity.FILTER_MY_PLAYERS,
        my_roster_ids=[BOUTTE],
        session={},
        league_id="L1",
    )
    assert visible == ()


def test_event_identity_uniqueness_for_cached_live_style_rows():
    session = _roster_session()
    ctx = dict(session[ni.ROSTER_CONTEXT_KEY])
    ctx["my_roster_ids"] = [BOUTTE, NICO]
    session[ni.ROSTER_CONTEXT_KEY] = ctx
    articles = [_trade_article(), _teammate_ir_article(), _generic_article(3)]
    with patch("modules.news.load_cached_news_pool", return_value=articles):
        rows = alerts_activity.compose_activity_timeline(session=session, league_id="L1")
        visible = alerts_activity.filter_timeline(
            rows,
            alerts_activity.FILTER_MY_PLAYERS,
            my_roster_ids=[BOUTTE, NICO],
            session=session,
            league_id="L1",
        )
    report = alerts_activity.action_rail_diagnostics(visible, player_button_available=True)
    identities = [alert_presentation.canonical_alert_identity(row) for row in visible]
    assert report["visible_row_count"] == len(visible) >= 2
    assert report["blank_event_id_count"] == 0
    assert report["unique_event_id_count"] == len(visible)
    assert report["duplicate_event_id_count"] == 0
    assert len(identities) == len(set(identities))
    signatures = [str(row.get("material_signature") or "") for row in visible]
    nonempty = [item for item in signatures if item]
    assert len(nonempty) == len(set(nonempty)) or not nonempty


def test_source_link_mark_read_dismiss_isolation_and_reload():
    session = _roster_session()
    ctx = dict(session[ni.ROSTER_CONTEXT_KEY])
    ctx["my_roster_ids"] = [BOUTTE, NICO]
    ctx["ir_ids"] = [NICO]
    session[ni.ROSTER_CONTEXT_KEY] = ctx
    articles = [_trade_article(), _teammate_ir_article(), _injury_article(
        title="Keyshawn Boutte questionable with ankle",
        status_phrase="questionable",
        slug="boutte-questionable",
    )]
    # Two Boutte articles would share family TRADE vs injury; keep Boutte+Nico+second Boutte injury
    # as three distinct identities. Use a third unique player via Nico + Boutte trade + Boutte injury.

    def _visible(state):
        rows = alerts_activity.compose_activity_timeline(session=state, league_id="L1")
        return alerts_activity.filter_timeline(
            rows,
            alerts_activity.FILTER_MY_PLAYERS,
            my_roster_ids=[BOUTTE, NICO],
            session=state,
            league_id="L1",
        )

    with patch("modules.news.load_cached_news_pool", return_value=articles):
        joined, _labels, _regs = _render_alerts(
            session,
            articles,
            open_player=_open_player,
            my_roster_ids=[BOUTTE, NICO],
            players_df=_players(),
        )
        assert "Read source" in joined
        first = _visible(session)
        assert len(first) >= 3
        unread_before = sum(1 for row in first if row.get("unread"))
        read_store = dict(session.get(nc.NOTIFICATION_READ_IDS_KEY) or {})
        dismiss_store = dict(session.get(nc.NOTIFICATION_DISMISSED_IDS_KEY) or {})
        # Opening source is a plain anchor: no Python mutation.
        assert session.get(nc.NOTIFICATION_READ_IDS_KEY) == read_store or not session.get(
            nc.NOTIFICATION_READ_IDS_KEY
        )
        rebuilt = _visible(session)
        assert len(rebuilt) == len(first)
        assert sum(1 for row in rebuilt if row.get("unread")) == unread_before
        ordered = list(rebuilt)
        nc.mark_alert_read(session, dict(ordered[0]), league_id="L1")
        after_read = _visible(session)
        assert len(after_read) == len(first)
        assert sum(1 for row in after_read if row.get("unread")) == unread_before - 1
        first_id = alert_presentation.canonical_alert_identity(ordered[0])
        matching = [
            row
            for row in after_read
            if alert_presentation.canonical_alert_identity(row) == first_id
        ]
        assert matching and matching[0].get("unread") is False
        nc.dismiss_alert(session, dict(ordered[1]), league_id="L1")
        after_dismiss = _visible(session)
        assert len(after_dismiss) == len(first) - 1
        dismissed_id = alert_presentation.canonical_alert_identity(ordered[1])
        assert all(
            alert_presentation.canonical_alert_identity(row) != dismissed_id for row in after_dismiss
        )
        history_rows = alerts_activity.compose_activity_timeline(session=session, league_id="L1")
        assert any(
            alert_presentation.canonical_alert_identity(row) == dismissed_id for row in history_rows
        )
        remaining_unread = [row for row in after_dismiss if row.get("unread")]
        remaining_read = [row for row in after_dismiss if not row.get("unread")]
        assert remaining_read
        assert remaining_unread
        assert session.get(nc.NOTIFICATION_READ_IDS_KEY) != read_store
        assert session.get(nc.NOTIFICATION_DISMISSED_IDS_KEY) != dismiss_store


def test_family_recommendation_id_does_not_mass_dismiss():
    shared_family = "news-event:unknown:injury_chain"
    rows = [
        {
            "id": f"news:{identity}",
            "recommendation_id": shared_family,
            "event_identity": identity,
            "player_id": player,
            "unread": True,
            "dismissed": False,
            "relationship_kind": alerts_activity.KIND_MY_PLAYER,
            "roster_relationship": "MY_STARTER",
            "category": "URGENT",
            "alert_worthy": True,
            "kind": "news",
            "headline": headline,
            "source_url": url,
        }
        for identity, player, headline, url in (
            ("hash-a", BOUTTE, "Boutte ankle", "https://www.espn.com/a"),
            ("hash-b", BOUTTE, "Boutte follow-up", "https://www.espn.com/b"),
            ("hash-c", NICO, "Nico IR", "https://www.cbssports.com/c"),
        )
    ]
    session: dict = {"account_user_id": "u1", "selected_league_id": "L1"}
    nc.dismiss_alert(session, rows[0], league_id="L1")
    visible = alerts_activity.filter_timeline(
        [_apply(row, session) for row in rows],
        alerts_activity.FILTER_MY_PLAYERS,
        my_roster_ids=[BOUTTE, NICO],
        session=session,
        league_id="L1",
    )
    assert len(visible) == 2
    remaining = {str(row.get("event_identity") or "") for row in visible}
    assert remaining == {"hash-b", "hash-c"}
    ids = {alert_presentation.canonical_alert_identity(row) for row in visible}
    assert len(ids) == 2


def _apply(row, session):
    return alerts_activity._apply_attention_state(row, session, "L1")


def test_source_open_does_not_suppress_toast():
    tile = {
        "label": "News Alert",
        "value": "Boutte traded",
        "id": "news-boutte-trade",
        "recommendation_id": "news-event:boutte-1:TRADE",
        "event_identity": "toast-boutte-1",
        "player_id": BOUTTE,
        "news_event_type": "TRADE",
        "news_event_severity": "HIGH",
        "news_roster_relationship": "MY_STARTER",
        "news_age_seconds": 90,
        "should_alert": True,
        "toast_tier": "high",
        "material_signature": "sig-source-toast",
    }
    session: dict = {"account_user_id": "u1", "selected_league_id": "L1"}
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    first = nc.consume_pending_urgent_delivery(session, league_id="L1")
    assert first is not None
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None
    # Source open is a no-op; toast stays consumed for this session but event remains unread.
    inbox = nc.compose_activity_inbox(session=session, league_id="L1")
    assert any(item.unread for item in inbox)
    nc.mark_alert_read(session, tile, league_id="L1")
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None
    nc.dismiss_alert(session, tile, league_id="L1")
    nc.publish_activity_inventory(session, [tile], league_id="L1", inventory_complete=True)
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None


def test_action_rail_css_contract_no_item_button_overlap():
    from modules.alerts_activity_styles import ALERTS_ACTIVITY_CSS

    css = ALERTS_ACTIVITY_CSS
    assert "st-key-alerts_actions_" in css
    assert "flex-wrap:wrap" in css
    assert 'div[class*="st-key-alerts_item_"] [data-testid="stButton"]' not in css
    assert "nth-child" not in css
    html = alerts_activity_ui.timeline_row_html(
        {
            "headline": "Keyshawn Boutte traded to the Houston Texans in a multi-team deal with extra words",
            "context": "Starter · Status not yet confirmed",
            "fantasygm_read": "Opportunity may rise in HOU if the role holds.",
            "player_id": BOUTTE,
            "player_name": "Keyshawn Boutte",
            "unread": True,
            "roster_relationship": "MY_STARTER",
            "event_type": "TRADE",
            "severity": "HIGH",
            "source": "ESPN",
            "source_url": "https://www.espn.com/nfl/story/_/id/boutte-trade",
            "freshness": "28m",
            "glyph": "URGENT",
        }
    )
    assert "Read source" in html
    assert "dg-alerts-source" in html
    assert "Open player" not in html


def _three_alert_articles():
    return [
        _trade_article(),
        _teammate_ir_article(),
        _injury_article(
            title="Keyshawn Boutte questionable with ankle",
            status_phrase="questionable",
            slug="boutte-questionable",
        ),
    ]


def _my_players_visible(session, articles):
    with patch("modules.news.load_cached_news_pool", return_value=articles):
        rows = alerts_activity.compose_activity_timeline(session=session, league_id="L1")
        return alerts_activity.filter_timeline(
            rows,
            alerts_activity.FILTER_MY_PLAYERS,
            my_roster_ids=[BOUTTE, NICO],
            session=session,
            league_id="L1",
        )


def _prepare_three_alert_session():
    session = _roster_session()
    ctx = dict(session[ni.ROSTER_CONTEXT_KEY])
    ctx["my_roster_ids"] = [BOUTTE, NICO]
    ctx["ir_ids"] = [NICO]
    session[ni.ROSTER_CONTEXT_KEY] = ctx
    return session, _three_alert_articles()


def test_hard_refresh_does_not_auto_mark_alerts_read():
    session, articles = _prepare_three_alert_session()
    _render_alerts(
        session,
        articles,
        open_player=_open_player,
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
    )
    first = _my_players_visible(session, articles)
    assert len(first) >= 3
    ordered = list(first)
    unread_id = alert_presentation.canonical_alert_identity(ordered[0])
    read_id = alert_presentation.canonical_alert_identity(ordered[1])
    dismissed_id = alert_presentation.canonical_alert_identity(ordered[2])
    nc.mark_alert_read(session, dict(ordered[1]), league_id="L1")
    nc.dismiss_alert(session, dict(ordered[2]), league_id="L1")
    after = _my_players_visible(session, articles)
    by_id = {alert_presentation.canonical_alert_identity(row): row for row in after}
    assert by_id[unread_id].get("unread") is True
    assert by_id[read_id].get("unread") is False
    assert dismissed_id not in by_id

    # New Streamlit session: handled state is in-session only, so rebuild unread/active.
    fresh, _articles = _prepare_three_alert_session()
    _render_alerts(
        fresh,
        articles,
        fresh_entry=True,
        open_player=_open_player,
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
    )
    rebuilt = _my_players_visible(fresh, articles)
    assert len(rebuilt) >= 3
    assert all(row.get("unread") for row in rebuilt)
    assert not any(row.get("has_explicit_read_state") for row in rebuilt)
    fresh_stats = fresh.get(alerts_activity.PIPELINE_STATS_KEY) or {}
    assert int(fresh_stats.get("computed_unread_count") or 0) >= 3
    assert int(fresh_stats.get("explicit_read_state_count") or 0) == 0

    # Reconnect-shaped refresh: explicit handled state survives, widget triggers replay.
    session.pop(alerts_activity.ACTIONS_ARMED_KEY, None)
    session.pop(f"{alerts_activity.SURFACE_SEEN_KEY}:L1", None)
    mapping = session.get(alerts_activity.ROW_ACTION_MAP_KEY) or {}
    for key in mapping:
        session[key] = True
    _render_alerts(
        session,
        articles,
        fresh_entry=False,
        open_player=_open_player,
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
    )
    replayed = _my_players_visible(session, articles)
    replayed_by_id = {alert_presentation.canonical_alert_identity(row): row for row in replayed}
    assert replayed_by_id[unread_id].get("unread") is True
    assert replayed_by_id[read_id].get("unread") is False
    assert dismissed_id not in replayed_by_id
    assert session.get(alerts_activity.MASS_REPLAY_IGNORED_KEY) is True
    replay_stats = session.get(alerts_activity.PIPELINE_STATS_KEY) or {}
    assert int(replay_stats.get("computed_unread_count") or 0) >= 1
    assert replayed_by_id[unread_id].get("has_explicit_read_state") is False


def test_dashboard_return_preserves_read_dismiss_and_unread():
    session, articles = _prepare_three_alert_session()
    _render_alerts(
        session,
        articles,
        fresh_entry=True,
        open_player=_open_player,
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
    )
    ordered = list(_my_players_visible(session, articles))
    nc.mark_alert_read(session, dict(ordered[0]), league_id="L1")
    nc.dismiss_alert(session, dict(ordered[1]), league_id="L1")
    mid = _my_players_visible(session, articles)
    unread_after = sum(1 for row in mid if row.get("unread"))
    _render_alerts(
        session,
        articles,
        fresh_entry=True,
        open_player=_open_player,
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
    )
    back = _my_players_visible(session, articles)
    assert len(back) == len(mid)
    assert sum(1 for row in back if row.get("unread")) == unread_after
    ids_mid = {alert_presentation.canonical_alert_identity(row) for row in mid}
    ids_back = {alert_presentation.canonical_alert_identity(row) for row in back}
    assert ids_mid == ids_back


def test_armed_single_mark_read_and_dismiss_via_widgets():
    session, articles = _prepare_three_alert_session()
    _render_alerts(
        session,
        articles,
        open_player=_open_player,
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
    )
    before = list(_my_players_visible(session, articles))
    unread_before = sum(1 for row in before if row.get("unread"))
    mapping = session.get(alerts_activity.ROW_ACTION_MAP_KEY) or {}
    read_key = next(key for key, spec in mapping.items() if spec.get("kind") == "mark_read")
    session[read_key] = True
    _render_alerts(
        session,
        articles,
        fresh_entry=False,
        open_player=_open_player,
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
    )
    after_read = list(_my_players_visible(session, articles))
    assert len(after_read) == len(before)
    assert sum(1 for row in after_read if row.get("unread")) == unread_before - 1
    mapping = session.get(alerts_activity.ROW_ACTION_MAP_KEY) or {}
    dismiss_key = next(key for key, spec in mapping.items() if spec.get("kind") == "dismiss")
    session[dismiss_key] = True
    _render_alerts(
        session,
        articles,
        fresh_entry=False,
        open_player=_open_player,
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
    )
    after_dismiss = list(_my_players_visible(session, articles))
    assert len(after_dismiss) == len(after_read) - 1


def test_unarmed_bootstrap_and_mass_replay_do_not_mark_read():
    session, articles = _prepare_three_alert_session()
    _render_alerts(
        session,
        articles,
        open_player=_open_player,
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
    )
    unread_before = sum(1 for row in _my_players_visible(session, articles) if row.get("unread"))
    read_store = dict(session.get(nc.NOTIFICATION_READ_IDS_KEY) or {})
    mapping = dict(session.get(alerts_activity.ROW_ACTION_MAP_KEY) or {})
    session.pop(alerts_activity.ACTIONS_ARMED_KEY, None)
    for key in mapping:
        session[key] = True
    _render_alerts(
        session,
        articles,
        fresh_entry=True,
        open_player=_open_player,
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
        button_pressed=lambda _label, _key: True,
    )
    assert sum(1 for row in _my_players_visible(session, articles) if row.get("unread")) == unread_before
    assert session.get(nc.NOTIFICATION_READ_IDS_KEY) == read_store or not session.get(
        nc.NOTIFICATION_READ_IDS_KEY
    )
    session[alerts_activity.ACTIONS_ARMED_KEY] = True
    for key in mapping:
        session[key] = True
    _render_alerts(
        session,
        articles,
        fresh_entry=False,
        open_player=_open_player,
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
        button_pressed=lambda _label, _key: True,
    )
    assert sum(1 for row in _my_players_visible(session, articles) if row.get("unread")) == unread_before
    assert session.get(alerts_activity.MASS_REPLAY_IGNORED_KEY) is True


def test_open_player_widget_does_not_mutate_read_state():
    opened: list[str] = []
    session, articles = _prepare_three_alert_session()
    _render_alerts(
        session,
        articles,
        open_player=lambda pid, **_k: opened.append(str(pid)),
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
    )
    mapping = session.get(alerts_activity.ROW_ACTION_MAP_KEY) or {}
    player_key = next(key for key, spec in mapping.items() if spec.get("kind") == "open_player")
    read_store = dict(session.get(nc.NOTIFICATION_READ_IDS_KEY) or {})
    dismiss_store = dict(session.get(nc.NOTIFICATION_DISMISSED_IDS_KEY) or {})
    session[player_key] = True
    _render_alerts(
        session,
        articles,
        fresh_entry=False,
        open_player=lambda pid, **_k: opened.append(str(pid)),
        my_roster_ids=[BOUTTE, NICO],
        players_df=_players(),
    )
    assert opened
    assert session.get(nc.NOTIFICATION_READ_IDS_KEY) == read_store or not session.get(
        nc.NOTIFICATION_READ_IDS_KEY
    )
    assert session.get(nc.NOTIFICATION_DISMISSED_IDS_KEY) == dismiss_store or not session.get(
        nc.NOTIFICATION_DISMISSED_IDS_KEY
    )


def test_select_explicit_alert_actions_ignores_unarmed_and_mass():
    session: dict = {}
    one = [{"kind": "mark_read", "key": "a", "row": {"id": "1"}}]
    assert alerts_activity.select_explicit_alert_actions(one, session) == ()
    session[alerts_activity.ACTIONS_ARMED_KEY] = True
    accepted = alerts_activity.select_explicit_alert_actions(one, session)
    assert len(accepted) == 1
    many = one + [{"kind": "mark_read", "key": "b", "row": {"id": "2"}}]
    assert alerts_activity.select_explicit_alert_actions(many, session) == ()
    assert session.get(alerts_activity.MASS_REPLAY_IGNORED_KEY) is True
