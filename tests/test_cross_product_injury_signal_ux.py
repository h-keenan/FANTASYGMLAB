"""Canonical roster-injury attention projected across Alerts and My Team."""

from __future__ import annotations

import pandas as pd

from modules import alerts_activity
from modules import alerts_activity_styles
from modules import alerts_activity_ui
from modules import dashboard_workflow
from modules import news_intelligence
from modules import notification_center as nc
from modules import player_cards
from modules import player_injury_attention


NOW = 2_000_000_000.0
JEANTY_ID = "12527"


def _jeanty_tile(*, relationship: str = "MY_BENCH", age_seconds: int = 1260):
    return {
        "label": "News Alert",
        "value": "Ashton Jeanty: Injury update",
        "note": (
            "News reports a potentially significant right-knee injury. "
            "Structured Sleeper status has not caught up yet."
        ),
        "recommendation_id": "news-event:12527:injury_chain",
        "route_key": "my_team",
        "route_player_id": JEANTY_ID,
        "player_id": JEANTY_ID,
        "news_player_name": "Ashton Jeanty",
        "news_event_type": "INJURY",
        "news_event_severity": "HIGH",
        "news_roster_relationship": relationship,
        "news_event_time": NOW - age_seconds,
        "news_age_seconds": age_seconds,
        "news_age_label": "21 minutes ago",
        "news_corroboration": "AWAITING STATUS UPDATE",
        "news_significant_injury_event": True,
        "should_alert": True,
    }


def _publish(tile=None):
    state = {"account_user_id": "founder", "selected_league_id": "L1"}
    nc.publish_activity_inventory(state, [tile or _jeanty_tile()], league_id="L1")
    return state


def test_jeanty_alert_has_canonical_portrait_urgency_and_uncertainty():
    state = _publish()
    item = next(
        item
        for item in nc.compose_activity_inbox(session=state, league_id="L1")
        if item.player_id == JEANTY_ID
    )
    row = alerts_activity._row_from_notification(item)
    html = alerts_activity_ui.timeline_row_html(row)

    assert "dg-alerts-row--urgent" in html
    assert "dg-alerts-row--player" in html
    assert "sleepercdn.com/content/nfl/players/12527.jpg" in html
    assert "Ashton Jeanty" in html
    assert "MY PLAYER" in html
    assert "POTENTIALLY SIGNIFICANT INJURY" in html
    assert "STATUS NOT YET CONFIRMED" in html
    assert "URGENT" in html
    assert "21m" in html


def test_my_team_projection_adds_attention_without_fabricating_official_status():
    state = _publish()
    attention = nc.active_roster_injury_attention(state, league_id="L1", now=NOW)
    roster = pd.DataFrame(
        [{"player_id": JEANTY_ID, "name": "Ashton Jeanty", "injury_status": "", "status": "Active"}]
    )
    projected = player_injury_attention.annotate_player_frame(
        roster,
        attention,
        has_structured_injury=lambda row: bool(str(row.get("injury_status") or "").strip()),
    )
    row = projected.iloc[0]

    assert row["injury_attention_label"] == "Injury Alert"
    assert bool(row["injury_attention_pending"]) is True
    assert row["injury_status"] == ""
    tags = player_cards.player_scan_tags(
        row,
        primary_status="Elite",
        is_injury_status=lambda _: False,
    )
    assert "Injury Alert" in tags
    for fabricated in ("OUT", "Questionable", "Doubtful"):
        assert fabricated not in tags

    card = player_cards.compact_player_row_html(
        row,
        score_field="value_score",
        score_label="Dynasty Score",
        player_display_name=lambda item: str(item.get("name") or "Player"),
        format_age=lambda value: str(value or "-"),
        format_score=lambda value: f"{int(value or 0):,}",
        cached_headshot_data_url=lambda _player_id: "",
        avatar_html=lambda _url, initials, css_class="": (
            f"<div class='{css_class}'>{initials}</div>"
        ),
        asset_initials=lambda name: "".join(part[0] for part in name.split()[:2]),
        is_injury_status=lambda _: False,
    )
    assert "Injury Alert" in card


def test_structured_status_takes_precedence_without_conflicting_attention():
    state = _publish()
    attention = nc.active_roster_injury_attention(state, league_id="L1", now=NOW)
    roster = pd.DataFrame(
        [{"player_id": JEANTY_ID, "name": "Ashton Jeanty", "injury_status": "Questionable"}]
    )
    projected = player_injury_attention.annotate_player_frame(
        roster,
        attention,
        has_structured_injury=lambda row: bool(str(row.get("injury_status") or "").strip()),
    )
    assert projected.iloc[0]["injury_attention_label"] == ""
    assert projected.iloc[0]["injury_status"] == "Questionable"


def test_attention_expires_and_isolated_league_or_opponent_does_not_project():
    state = _publish()
    assert nc.active_roster_injury_attention(state, league_id="L2", now=NOW) == {}
    assert nc.active_roster_injury_attention(
        state,
        league_id="L1",
        now=NOW + nc.ACTIVE_INJURY_ATTENTION_MAX_AGE_SECONDS + 1,
    ) == {}

    opponent = _publish(_jeanty_tile(relationship="OPPONENT_STARTER"))
    assert nc.active_roster_injury_attention(opponent, league_id="L1", now=NOW) == {}

    roster_without_player = pd.DataFrame(
        [{"player_id": "other", "name": "Other Player", "injury_status": ""}]
    )
    projected = player_injury_attention.annotate_player_frame(
        roster_without_player,
        {JEANTY_ID: {"label": "Injury Alert", "status_pending": True}},
        has_structured_injury=lambda _: False,
    )
    assert projected.iloc[0]["injury_attention_label"] == ""


def test_cache_hit_publishes_unchanged_news_inventory_for_my_team_projection():
    source = open("app.py", encoding="utf-8").read()
    cache_hit = source.split("if game_plan_package_hit and cached_package:", 1)[1]
    cache_hit = cache_hit.split(
        'startup_coordinator.log_startup_milestone(\n            st.session_state,\n            "game_plan_package_ready"',
        1,
    )[0]
    assert '            _news_tiles = list(_news_refresh.get("tiles") or [])' in cache_hit
    assert '            notification_center.publish_activity_inventory(' in cache_hit

    state = {"account_user_id": "founder", "selected_league_id": "L1"}
    nc.publish_activity_inventory(state, [_jeanty_tile()], league_id="L1")
    attention = nc.active_roster_injury_attention(state, league_id="L1", now=NOW)
    assert attention[JEANTY_ID]["label"] == "Injury Alert"


def test_same_canonical_event_is_consistent_across_header_alerts_and_my_team():
    state = _publish()
    header = nc.compose_activity_inbox(
        session=state,
        league_id="L1",
        include_product_update=True,
        header_cap=True,
    )
    header_jeanty = [item for item in header if item.player_id == JEANTY_ID]
    assert len(header_jeanty) == 1
    assert header_jeanty[0].recommendation_id == "news-event:12527:injury_chain"
    assert alerts_activity.header_glyph(header_jeanty[0]) == "INJURY ALERT"
    assert "All caught up" not in nc._inbox_header_html(unread=0, active=1)

    timeline = alerts_activity.compose_activity_timeline(
        session=state,
        league_id="L1",
        news_events=[_jeanty_tile()],
    )
    timeline_jeanty = [row for row in timeline if row.get("player_id") == JEANTY_ID]
    assert len(timeline_jeanty) == 1
    assert timeline_jeanty[0]["recommendation_id"] == header_jeanty[0].recommendation_id

    attention = nc.active_roster_injury_attention(state, league_id="L1", now=NOW)
    roster = pd.DataFrame(
        [{"player_id": JEANTY_ID, "name": "Ashton Jeanty", "injury_status": ""}]
    )
    projected = player_injury_attention.annotate_player_frame(
        roster,
        attention,
        has_structured_injury=lambda row: bool(
            str(row.get("injury_status") or "").strip()
        ),
    )
    assert projected.iloc[0]["injury_attention_label"] == "Injury Alert"


def test_preconsumer_news_publication_is_idempotent_and_preserves_non_news():
    decision = {
        "label": "Top Trade Opportunity",
        "value": "Trade with KING TITUS",
        "note": "Existing canonical decision",
        "recommendation_id": "trade:one",
    }
    state = {"account_user_id": "founder", "selected_league_id": "L1"}
    nc.publish_activity_inventory(state, [decision], league_id="L1")
    nc.publish_activity_inventory(
        state,
        [_jeanty_tile()],
        league_id="L1",
        preserve_existing_non_news=True,
    )
    nc.publish_activity_inventory(
        state,
        [_jeanty_tile()],
        league_id="L1",
        preserve_existing_non_news=True,
    )
    items = nc.compose_activity_inbox(
        session=state,
        league_id="L1",
        include_product_update=False,
        header_cap=False,
    )
    assert [item.recommendation_id for item in items].count(
        "news-event:12527:injury_chain"
    ) == 1
    assert any(item.recommendation_id == "trade:one" for item in items)


def test_preconsumer_sync_runs_before_header_and_is_league_scoped():
    source = open("app.py", encoding="utf-8").read()
    sync_call = source.index("preserve_existing_non_news=True")
    header_call = source.index(
        "        render_platform_topbar(",
        sync_call,
    )
    assert sync_call < header_call

    state = _publish()
    nc.publish_activity_inventory(
        state,
        [],
        league_id="L2",
        preserve_existing_non_news=True,
    )
    assert not any(
        item.player_id == JEANTY_ID
        for item in nc.compose_activity_inbox(
            session=state,
            league_id="L2",
            include_product_update=False,
            header_cap=False,
        )
    )
    assert nc.active_roster_injury_attention(state, league_id="L1", now=NOW) == {}


def test_alert_portrait_uses_canonical_compact_dimensions_without_double_box():
    html = alerts_activity_ui.timeline_row_html(
        alerts_activity._row_from_notification(
            next(
                item
                for item in nc.compose_activity_inbox(
                    session=_publish(), league_id="L1"
                )
                if item.player_id == JEANTY_ID
            )
        )
    )
    assert html.count("dg-alerts-portrait") == 1
    assert "dg-alerts-player-visual" not in html
    css = alerts_activity_styles.ALERTS_ACTIVITY_CSS
    assert "--avatar-size:3.25rem" in css
    assert "--avatar-size:2.75rem" in css


def test_dashboard_immediate_and_notification_dedupe_contracts_remain():
    tile = _jeanty_tile()
    briefing = news_intelligence.merge_news_tiles_into_dashboard_briefing(
        dashboard_workflow.organize_dashboard_items([]),
        [tile],
    )
    assert tuple(briefing.immediate) == (tile,)

    state = _publish(tile)
    assert nc.consume_pending_urgent_delivery(state, league_id="L1") is not None
    nc.publish_activity_inventory(state, [tile], league_id="L1")
    assert nc.consume_pending_urgent_delivery(state, league_id="L1") is None
