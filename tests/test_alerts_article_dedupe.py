"""Exact-article identity: one source article → one Alerts row and one attention id."""

from __future__ import annotations

from modules import alert_presentation
from modules import alerts_activity
from modules import news_intelligence as ni
from modules import notification_center as nc


BOUTTE = "boutte-1"
NICO = "nico-1"
JEANTY_HEADLINE = (
    "Latest NFL injury updates: Ashton Jeanty avoids major injury, "
    "other running backs uncertain for Week 1"
)
CBS_URL = (
    "https://www.cbssports.com/nfl/news/"
    "latest-nfl-injury-updates-ashton-jeanty-avoids-major-injury-other-running-backs-uncertain/"
)
CBS_URL_TRACKED = CBS_URL.rstrip("/") + "/?utm_source=twitter&fbclid=abc.123&ref=share"


def _roster_session() -> dict:
    return {
        ni.ROSTER_CONTEXT_KEY: {
            "league_id": "L1",
            "my_roster_ids": [BOUTTE, NICO],
            "starter_ids": [BOUTTE],
            "taxi_ids": [],
            "ir_ids": [],
            "opponent_ids": [],
            "player_name_to_id": {},
        },
        "account_user_id": "u1",
        "selected_league_id": "L1",
    }


def _row(
    *,
    event_identity: str,
    player_id: str,
    relationship: str,
    url: str = CBS_URL,
    recommendation_id: str = "",
    unread: bool = True,
    kind: str = alerts_activity.KIND_MY_PLAYER,
    headline: str = JEANTY_HEADLINE,
    source: str = "CBS",
    published_ts: float = 1_787_520_400.0,
) -> dict:
    return {
        "label": "News Alert",
        "value": headline,
        "title": headline,
        "headline": headline,
        "news_article_title": headline,
        "id": f"news:{event_identity}",
        "recommendation_id": recommendation_id or f"news-event:{player_id or 'unknown'}:INJURY",
        "event_identity": event_identity,
        "player_id": player_id,
        "beneficiary_player_id": player_id,
        "news_player_name": "Ashton Jeanty" if player_id == BOUTTE else "Nico Collins",
        "news_event_type": "INJURY",
        "event_type": "INJURY",
        "news_event_severity": "HIGH",
        "severity": "HIGH",
        "news_roster_relationship": relationship,
        "roster_relationship": relationship,
        "relationship_kind": kind,
        "news_age_seconds": 90,
        "news_event_time": published_ts,
        "event_time": published_ts,
        "published_ts": published_ts,
        "source_url": url,
        "link": url,
        "source": source,
        "news_source": source,
        "should_alert": True,
        "toast_tier": "high",
        "news_significant_injury_event": True,
        "significant_injury_event": True,
        "material_signature": f"sig-{event_identity}",
        "unread": unread,
        "alert_worthy": True,
        "kind": "news",
        "category": "URGENT",
        "fantasygm_read": "Starter availability is in question until the status is confirmed.",
    }


def _visible(session, events):
    rows = alerts_activity.compose_activity_timeline(
        session=session, league_id="L1", news_events=events
    )
    return alerts_activity.filter_timeline(
        rows,
        alerts_activity.FILTER_MY_PLAYERS,
        my_roster_ids=[BOUTTE, NICO],
        session=session,
        league_id="L1",
    )


def test_same_cbs_article_collapses_to_one_row_and_shared_attention():
    session = _roster_session()
    row_a = _row(event_identity="ident-a", player_id=BOUTTE, relationship="MY_STARTER")
    row_b = _row(
        event_identity="ident-b",
        player_id=NICO,
        relationship="OPPONENT_ROSTER",
        url=CBS_URL_TRACKED,
        recommendation_id="news-event:unknown:injury_chain",
        kind=alerts_activity.KIND_MY_TEAMMATE,
    )
    merged, stats = alert_presentation.merge_exact_article_rows([row_a, row_b])
    assert stats["pre_dedupe_event_count"] == 2
    assert stats["post_dedupe_event_count"] == 1
    assert stats["duplicate_article_count"] == 1
    assert len(merged) == 1
    winner = merged[0]
    assert winner.get("roster_relationship") == "MY_STARTER"
    assert winner.get("player_id") == BOUTTE
    assert BOUTTE in (winner.get("affected_player_ids") or (BOUTTE,))
    assert NICO in (winner.get("affected_player_ids") or ())
    assert alert_presentation.normalize_article_url(winner.get("source_url")) == (
        alert_presentation.normalize_article_url(CBS_URL)
    )
    assert winner["fantasygm_read"].count("Starter availability") == 1

    nc.publish_activity_inventory(session, [row_a, row_b], league_id="L1", inventory_complete=True)
    inbox = nc.compose_activity_inbox(session=session, league_id="L1", header_cap=False)
    news_items = [item for item in inbox if item.source_url]
    assert len(news_items) == 1
    assert nc.unread_count(inbox) == 1
    toast = nc.consume_pending_urgent_delivery(session, league_id="L1")
    assert toast is not None
    assert nc.consume_pending_urgent_delivery(session, league_id="L1") is None
    assert int((session.get(alerts_activity.PIPELINE_STATS_KEY) or {}).get("toast_candidates") or 0) <= 1

    visible = _visible(session, [row_a, row_b])
    assert len(visible) == 1
    assert visible[0].get("unread") is True
    nc.mark_alert_read(session, dict(visible[0]), league_id="L1")
    after_read = _visible(session, [row_a, row_b])
    assert len(after_read) == 1
    assert after_read[0].get("unread") is False
    assert nc.unread_count(nc.compose_activity_inbox(session=session, league_id="L1")) == 0
    nc.dismiss_alert(session, dict(after_read[0]), league_id="L1")
    after_dismiss = _visible(session, [row_a, row_b])
    assert after_dismiss == ()
    history = alerts_activity.compose_activity_timeline(
        session=session, league_id="L1", news_events=[row_a, row_b]
    )
    assert any(
        alert_presentation.canonical_article_identity(row)
        == alert_presentation.canonical_article_identity(row_a)
        for row in history
    )


def test_tracking_query_urls_collapse():
    a = {"source_url": CBS_URL, "headline": JEANTY_HEADLINE, "source": "CBS"}
    b = {"source_url": CBS_URL_TRACKED, "headline": JEANTY_HEADLINE, "source": "CBS"}
    assert alert_presentation.canonical_article_identity(a) == (
        alert_presentation.canonical_article_identity(b)
    )
    merged, stats = alert_presentation.merge_exact_article_rows([a, b])
    assert stats["post_dedupe_event_count"] == 1
    assert len(merged) == 1


def test_different_canonical_urls_do_not_collapse_on_headline():
    espn = {
        "source_url": "https://www.espn.com/nfl/story/_/id/111/jeanty-injury-notes",
        "headline": JEANTY_HEADLINE,
        "source": "ESPN",
        "event_identity": "espn-1",
    }
    cbs = {
        "source_url": CBS_URL,
        "headline": JEANTY_HEADLINE,
        "source": "CBS",
        "event_identity": "cbs-1",
    }
    merged, stats = alert_presentation.merge_exact_article_rows([espn, cbs])
    assert stats["post_dedupe_event_count"] == 2
    assert len(merged) == 2


def test_no_url_fallback_collapses_same_source_headline_bucket():
    a = {
        "source": "CBS",
        "headline": JEANTY_HEADLINE,
        "published_ts": 1_787_520_000.0,
        "event_identity": "fallback-a",
    }
    b = {
        "source": "CBS",
        "headline": JEANTY_HEADLINE,
        "published_ts": 1_787_520_100.0,
        "event_identity": "fallback-b",
    }
    assert alert_presentation.canonical_article_identity(a)
    assert alert_presentation.canonical_article_identity(a) == (
        alert_presentation.canonical_article_identity(b)
    )
    merged, stats = alert_presentation.merge_exact_article_rows([a, b])
    assert stats["post_dedupe_event_count"] == 1


def test_multi_roster_player_article_keeps_one_row_and_direct_relationship():
    direct = _row(event_identity="direct", player_id=BOUTTE, relationship="MY_STARTER")
    teammate = _row(
        event_identity="teammate",
        player_id=NICO,
        relationship="MY_BENCH",
        kind=alerts_activity.KIND_MY_PLAYER,
    )
    # Process teammate-context copy first so merge must not lose direct starter.
    teammate_first = dict(teammate)
    teammate_first["relationship_kind"] = alerts_activity.KIND_MY_TEAMMATE
    teammate_first["roster_relationship"] = "UNKNOWN"
    teammate_first["news_roster_relationship"] = "UNKNOWN"
    merged, _stats = alert_presentation.merge_exact_article_rows([teammate_first, direct])
    assert len(merged) == 1
    assert merged[0].get("roster_relationship") == "MY_STARTER"
    assert merged[0].get("player_id") == BOUTTE
    assert set(merged[0].get("affected_player_ids") or ()) >= {BOUTTE, NICO}


def test_explicit_read_on_one_clone_wins_for_canonical_article():
    unread = _row(event_identity="clone-unread", player_id=BOUTTE, relationship="MY_STARTER")
    read = _row(
        event_identity="clone-read",
        player_id=NICO,
        relationship="MY_BENCH",
        unread=False,
    )
    read["has_explicit_read_state"] = True
    merged, _stats = alert_presentation.merge_exact_article_rows([unread, read])
    assert len(merged) == 1
    assert merged[0].get("unread") is False


def test_canonical_alert_identity_follows_article_not_player_event():
    a = _row(event_identity="ident-a", player_id=BOUTTE, relationship="MY_STARTER")
    b = _row(event_identity="ident-b", player_id=NICO, relationship="MY_BENCH")
    assert alert_presentation.canonical_alert_identity(a) == (
        alert_presentation.canonical_alert_identity(b)
    )
    aliases = set(alert_presentation.attention_aliases(a))
    assert "ident-a" in aliases
    assert alert_presentation.canonical_article_identity(a) in aliases
