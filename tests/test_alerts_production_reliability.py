"""Production-shaped Alerts / roster-news reliability fixtures (post-#421 audit)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from modules import alert_presentation
from modules import alerts_activity
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


def test_a_pending_without_context_still_maps_cached_pool():
    session = {ni.ROSTER_CONTEXT_PENDING_KEY: True, "selected_league_id": "L1"}
    with patch("modules.news.load_cached_news_pool", return_value=[_trade_article()]):
        rows = alerts_activity.compose_activity_timeline(session=session, league_id="L1")
    assert rows
    assert any("Boutte" in str(row.get("headline") or "") for row in rows)


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


def test_cached_news_events_keeps_the_shared_news_cache_warm():
    """coridian_, 2026-10-18 (news audit): Alerts read the same shared news
    cache Dashboard/News already refresh, but never triggered its own
    refresh — a user who only ever opened Alerts would ride entirely on
    other surfaces' traffic to keep it warm. This must call the same
    off-the-critical-path refresh they already do."""

    session = _roster_session()
    with patch("modules.news.load_cached_news_pool", return_value=[]), patch(
        "modules.news.schedule_news_cache_refresh"
    ) as mock_refresh:
        alerts_activity._cached_news_events(session, "L1")

    mock_refresh.assert_called_once_with()


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
