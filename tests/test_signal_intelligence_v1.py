"""Founder Beta Signal Intelligence v1 — freshness, corroboration, firewall, alerts."""

from __future__ import annotations

from pathlib import Path

from modules import alerts_activity
from modules import news
from modules import news_intelligence as ni
from modules import news_signal
from modules import notification_center as nc
from modules import signal_corroboration as corr
from modules import signal_freshness
from modules.app_styles import APP_CSS
from modules.alerts_activity_styles import ALERTS_ACTIVITY_CSS
from modules.rankings import injury_level, injury_multiplier, risk_multiplier
from modules.ui_architecture import PLATFORM_DESTINATIONS
from scripts.measure_interaction_rerun_architecture import count_explicit_reruns


ROOT = Path(__file__).resolve().parents[1]
NOW = 1_700_000_000.0


def _article(**kwargs):
    base = {
        "title": "Player update",
        "summary": "",
        "link": "https://www.espn.com/story",
        "published_ts": NOW - 120,
        "source": "https://www.espn.com/espn/rss/nfl/news",
        "matched_player": "Star Runner",
        "matched_player_id": "p1",
    }
    base.update(kwargs)
    return base


def test_canonical_news_fetch_ownership():
    source = (ROOT / "modules" / "news.py").read_text(encoding="utf-8")
    assert "Canonical news FETCH / CACHE owner" in source
    assert "def fetch_news(" in source
    assert "def load_cached_news_pool(" in source
    intel = (ROOT / "modules" / "news_intelligence.py").read_text(encoding="utf-8")
    assert "feedparser.parse" not in intel
    assert "NEWS_FEEDS" not in intel


def test_event_classification_and_dedupe():
    text = "Star Runner ruled out Sunday with ankle injury"
    event_type, evidence, _ = ni.classify_fine_grained_event(text)
    assert event_type == ni.FT_INACTIVE
    assert evidence
    a = news_signal.enrich_news_item(_article(title=text, link="https://a.test/1"))
    b = news_signal.enrich_news_item(_article(title=text, link="https://b.test/1", source="https://www.cbssports.com/x"))
    assert a["event_identity"] == b["event_identity"]


def test_roster_relevance_and_general_news_not_header_alert():
    general = ni.football_event_from_article(
        _article(title="NFL roundup: several teams rest starters", matched_player="", matched_player_id="")
    )
    general = ni.FootballEvent(**{**general.as_dict(), "roster_relationship": ni.REL_UNKNOWN, "player_id": ""})
    alert = ni.build_news_alert(general)
    assert alert.should_alert is False
    starter = ni.football_event_from_article(
        _article(title="Star Runner ruled out Sunday")
    )
    starter = ni.FootballEvent(
        **{**starter.as_dict(), "roster_relationship": ni.REL_MY_STARTER, "player_id": "p1"}
    )
    starter_alert = ni.build_news_alert(starter)
    assert starter_alert.should_alert is True


def test_header_max_3_to_6():
    items = [
        nc.NotificationItem(
            id=f"n{i}",
            category="DECISIONS" if i % 2 == 0 else "URGENT",
            title=f"Item {i}",
            body="x",
            unread=True,
            source_kind="canonical",
        )
        for i in range(10)
    ]
    header = alerts_activity.compose_header_alerts(items)
    assert 3 <= len(header) <= 6
    assert len(header) == 6


def test_see_all_timeline_includes_general_news():
    session = {
        nc.ACTIVITY_INBOX_SNAPSHOT_KEY: {
            "league_id": "L1",
            "records": [
                {
                    "id": "urgent-1",
                    "category": "URGENT",
                    "title": "Starter OUT",
                    "body": "Roster impact",
                    "source_kind": "canonical",
                    "age_label": "14m",
                }
            ],
        }
    }
    alerts_activity.store_timeline_events(
        session,
        [
            {
                "recommendation_id": "gen-1",
                "value": "League-wide practice notes",
                "should_alert": False,
                "news_event_severity": "LOW",
                "category": "NEWS",
            }
        ],
        league_id="L1",
    )
    rows = alerts_activity.compose_activity_timeline(session=session, league_id="L1")
    assert any(row["headline"] == "Starter OUT" for row in rows)
    assert any("practice notes" in row["headline"].casefold() for row in rows)
    news_only = alerts_activity.filter_timeline(rows, alerts_activity.FILTER_NEWS)
    assert news_only


def test_dashboard_cache_hit_refresh_uses_cached_pool_not_football_rebuild():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    hit = app.split("if game_plan_package_hit and cached_package:", 1)[1][:2500]
    assert "refresh_news_alerts_for_presentation" in hit
    assert "load_cached_news_pool()" in hit
    assert "build_players_table(" not in hit
    digest = (ROOT / "modules" / "news_intelligence.py").read_text(encoding="utf-8")
    assert "news_freshness_bucket" in digest
    assert "news_corroboration" in digest


def test_news_timestamp_freshness_does_not_invent_published_at():
    item = {"title": "x", "fetched_at": NOW - 90, "source": "RotoWire"}
    meta = signal_freshness.normalize_news_freshness(item, now=NOW)
    assert meta["timestamp_source"] == signal_freshness.SOURCE_FETCHED
    assert meta["published_at"] is None
    assert meta["freshness_bucket"] == signal_freshness.BUCKET_FRESH
    assert "Fetched" in meta["age_label"]
    missing = signal_freshness.normalize_news_freshness({}, now=NOW, cache_mtime=0)
    assert missing["unavailable"] is True
    assert "unavailable" in missing["age_label"].casefold()


def test_status_sync_freshness_wording():
    sync = signal_freshness.status_sync_freshness(now=NOW, synced_at=NOW - 18 * 60)
    assert sync["status_source"] == "Sleeper"
    assert "Player status synced 18m ago" == sync["label"]
    assert "happened" not in sync["label"].casefold()
    missing = signal_freshness.status_sync_freshness(
        now=NOW, synced_at=0, cache_path="/tmp/fantasygm-missing-players-cache.json"
    )
    assert "unavailable" in missing["label"].casefold()


def test_corroborated_awaiting_conflict_and_news_only():
    out_event = ni.football_event_from_article(_article(title="Star Runner ruled out Sunday"))
    agreed = corr.corroborate_news_with_status(out_event, sleeper_status="Out", player_id="p1")
    assert agreed["label"] == corr.LABEL_CORROBORATED
    lag = corr.corroborate_news_with_status(
        ni.football_event_from_article(_article(title="Star Runner expected to miss multiple weeks")),
        sleeper_status="Questionable",
        player_id="p1",
    )
    assert lag["label"] == corr.LABEL_AWAITING
    conflict = corr.corroborate_news_with_status(
        ni.football_event_from_article(_article(title="Star Runner returned to practice")),
        sleeper_status="Out",
        player_id="p1",
    )
    assert conflict["label"] == corr.LABEL_CONFLICT
    news_only = corr.corroborate_news_with_status(
        ni.football_event_from_article(_article(title="Star Runner role update", matched_player_id="")),
        sleeper_status="Active",
        player_id="",
    )
    assert news_only["label"] == corr.LABEL_NEWS_ONLY


def test_no_direct_news_score_mutation_including_opportunity():
    before = {
        "score": 100,
        "dynasty_score": 100,
        "value_score": 100,
        "injury_multiplier": 1.0,
        "risk_multiplier": 1.0,
        "opportunity_score": 50,
        "news_factor": 0.0,
    }
    after = dict(before)
    event = ni.football_event_from_article(_article(title="Star Runner torn ACL out for season"))
    _ = ni.build_news_alert(event)
    assert ni.article_changes_valuation_columns(before, after) == []
    for col in (
        "score",
        "dynasty_score",
        "value_score",
        "injury_multiplier",
        "risk_multiplier",
        "opportunity_score",
    ):
        assert col in ni.VALUATION_COLUMNS


def test_structured_injury_propagation_states():
    cases = (
        ("Active", "", "healthy", 1.0),
        ("Questionable", "", "minor", 0.95),
        ("Doubtful", "", "moderate", 0.80),
        ("Out", "", "moderate", 0.80),
        ("IR", "", "major", 0.68),
        ("PUP", "", "major", 0.68),
    )
    for status, injury, level, multiplier in cases:
        assert injury_level(status, injury) == level
        assert injury_multiplier(status, injury) == multiplier
        healthy_risk = risk_multiplier("Active", "KC", 25, "")
        changed = risk_multiplier(status, "KC", 25, injury)
        if level == "healthy":
            assert changed == healthy_risk
        else:
            assert changed <= healthy_risk


def test_waiver_injury_replacement_fit_stays_structured():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'free_agents["injury_replacement_fit"] = injury_fit' in app
    assert "is_injury_status" in app
    assert "injury_need_positions" in app


def test_trade_injury_guardrail_unchanged_entry():
    source = (ROOT / "modules" / "trade_ideas.py").read_text(encoding="utf-8")
    assert "def _temporary_injury_trade_guardrail" in source
    assert "temporary_injury_need_positions" in source
    assert "headline" not in source[source.index("def _temporary_injury_trade_guardrail") :][
        :800
    ].casefold()


def test_stale_news_and_missing_mapping_fail_soft():
    assert signal_freshness.news_source_unavailable_label() == "News source unavailable"
    event = ni.football_event_from_article(_article(title="Unknown guy limited", matched_player="", matched_player_id=""))
    mapped = corr.corroborate_news_with_status(event, sleeper_status="Q", player_id="")
    assert mapped["label"] == corr.LABEL_NEWS_ONLY


def test_duplicate_headline_collapse_and_escalation_resurfaces():
    session = {}
    q = ni.football_event_from_article(_article(title="Star Runner questionable with ankle"))
    q = ni.FootballEvent(**{**q.as_dict(), "roster_relationship": ni.REL_MY_STARTER, "player_id": "p1"})
    out = ni.football_event_from_article(_article(title="Star Runner now ruled out", link="https://www.espn.com/out"))
    out = ni.FootballEvent(**{**out.as_dict(), "roster_relationship": ni.REL_MY_STARTER, "player_id": "p1"})
    first = ni.apply_dedupe_and_escalation(ni.build_news_alert(q), session, league_id="L1", now=NOW)
    dup = ni.apply_dedupe_and_escalation(ni.build_news_alert(q), session, league_id="L1", now=NOW + 30)
    second = ni.apply_dedupe_and_escalation(ni.build_news_alert(out), session, league_id="L1", now=NOW + 120)
    assert first.should_alert
    assert dup.should_alert is False
    assert second.should_alert
    assert second.escalated_from
    tile_q = first.as_tile()
    tile_out = second.as_tile()
    assert tile_q["recommendation_id"] == tile_out["recommendation_id"]
    read_session: dict = {}
    nc.mark_notification_read(read_session, "rec:news-event:p1:injury_chain", league_id="L1")
    nc.unmark_notification_read(read_session, "rec:news-event:p1:injury_chain", league_id="L1")
    assert nc.is_notification_read(read_session, "rec:news-event:p1:injury_chain", league_id="L1") is False


def test_pqv_recent_news_limit_and_card_fields():
    from modules import player_quick_view

    card = player_quick_view.news_card_html(
        player_quick_view.NewsItem(
            headline="Player limited in practice",
            source="RotoWire",
            freshness="28m",
            event_type="INJURY",
            status_line="STATUS: QUESTIONABLE",
            corroboration_note="News and Sleeper status agree",
        )
    )
    assert "INJURY · 28m" in card
    assert "RotoWire" in card
    assert "STATUS: QUESTIONABLE" in card
    assert "News and Sleeper status agree" in card
    renderer = (ROOT / "modules" / "player_quick_view.py").read_text(encoding="utf-8")
    assert "default_limit: int = 3" in renderer
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "max_items: int = 3" in app.split("def _player_quick_view_news_items", 1)[1][:400]


def test_alerts_route_square_controls_and_css_budget():
    assert any(page.key == "alerts" and page.category == "CORE" for page in PLATFORM_DESTINATIONS)
    assert ALERTS_ACTIVITY_CSS not in APP_CSS
    assert len(APP_CSS) < 390_000
    ui = (ROOT / "modules" / "alerts_activity_ui.py").read_text(encoding="utf-8")
    assert "st.pills(" in ui
    assert "<h2>Alerts</h2>" not in ui
    assert "Priority signals in one timeline" in ui
    assert "border-radius:0" in ALERTS_ACTIVITY_CSS
    assert "st-key-alerts_filter_" in ALERTS_ACTIVITY_CSS
    assert count_explicit_reruns() <= 62


def test_viewport_harness_covers_390_and_1440_alerts():
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    validate = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    assert '"alerts"' in harness or "'alerts'" in harness
    assert '"alerts"' in validate
    assert "390" in validate
    assert "1440" in validate
    assert "Ashton Jeanty status changed" in harness
    assert "expected exactly one Alerts page title owner" in validate


def test_alerts_page_header_has_single_owner():
    from unittest.mock import patch

    from modules import alerts_activity_ui

    app = (ROOT / "app.py").read_text(encoding="utf-8")
    alerts_block = app.split('if current_page == "alerts":', 1)[1].split(
        "# LEAGUE RECAPS", 1
    )[0]
    assert "render_section_header(" not in alerts_block
    assert alerts_block.count("render_section_header=render_section_header") == 2
    ui = (ROOT / "modules" / "alerts_activity_ui.py").read_text(encoding="utf-8")
    assert ui.count('render_section_header(\n            "Alerts"') == 1
    assert "<h2>Alerts</h2>" not in ui
    assert "Not a second History" not in ui

    headers: list[str] = []
    html_chunks: list[str] = []

    def _header(title, **_kwargs):
        headers.append(title)

    class _Session(dict):
        pass

    session = _Session()
    with (
        patch.object(alerts_activity_ui.st, "session_state", session),
        patch.object(alerts_activity_ui, "inject_global_styles"),
        patch.object(
            alerts_activity_ui,
            "render_html_fragment",
            side_effect=lambda html: html_chunks.append(html),
        ),
        patch.object(alerts_activity_ui.st, "container"),
        patch.object(alerts_activity_ui.st, "pills", return_value="All"),
    ):
        alerts_activity_ui.render_alerts_page(
            league_id="L1",
            session=session,
            entitlement="free",
            render_section_header=_header,
        )
    assert headers == ["Alerts"]
    joined = "\n".join(html_chunks)
    assert joined.count("<h2") == 0
    assert "<h2>Alerts</h2>" not in joined
    assert "Not a second History" not in joined


def _jeanty_event(*, league_id: str) -> dict:
    return {
        "recommendation_id": "news-jeanty-out",
        "event_identity": "inactive:jeanty-a",
        "player_id": "jeanty-a",
        "value": "Ashton Jeanty ruled out",
        "should_alert": True,
        "news_event_severity": "CRITICAL",
        "category": "URGENT",
        "league_id": league_id,
    }


def _league_session(league_id: str, *, include_jeanty: bool) -> dict:
    records = []
    events = []
    if include_jeanty:
        records.append(
            {
                "id": "urgent-jeanty-a",
                "category": "URGENT",
                "title": "Ashton Jeanty ruled out",
                "body": "Roster impact",
                "source_kind": "canonical",
                "player_id": "jeanty-a",
                "age_label": "14m",
            }
        )
        events.append(_jeanty_event(league_id=league_id))
    session = {
        "selected_league_id": league_id,
        nc.ACTIVITY_INBOX_SNAPSHOT_KEY: {
            "league_id": league_id,
            "records": records,
        },
        ni.TIMELINE_EVENT_KEY: list(events),
        ni.PRESENTATION_DIGEST_KEY: f"digest-{league_id}",
        ni.ALERT_STATE_KEY: {league_id: {"news-jeanty-out": {"last": 1}}},
        ni.ROSTER_CONTEXT_KEY: {"league_id": league_id, "starter_ids": ["jeanty-a"]},
    }
    if events:
        alerts_activity.store_timeline_events(session, events, league_id=league_id)
    return session


def test_read_time_guard_ignores_other_league_timeline_before_refresh():
    session = _league_session("league-a", include_jeanty=True)
    a_rows = alerts_activity.compose_activity_timeline(session=session, league_id="league-a")
    assert any("Ashton Jeanty ruled out" in row["headline"] for row in a_rows)
    assert any(row.get("player_id") == "jeanty-a" for row in a_rows)

    b_rows = alerts_activity.compose_activity_timeline(session=session, league_id="league-b")
    blob = " ".join(f"{row.get('headline')} {row.get('id')} {row.get('player_id')}" for row in b_rows)
    assert "Ashton Jeanty ruled out" not in blob
    assert "jeanty-a" not in blob
    assert "inactive:jeanty-a" not in blob
    assert alerts_activity.load_timeline_events(session, "league-b") == []

    header = alerts_activity.compose_header_alerts(
        nc.compose_activity_inbox(session=session, league_id="league-b")
    )
    assert all("Jeanty" not in item.title for item in header)
    assert all(item.player_id != "jeanty-a" for item in header)

    session[alerts_activity.TIMELINE_SESSION_KEY] = [
        _jeanty_event(league_id="league-a")
    ]
    leaked = alerts_activity.compose_activity_timeline(
        session=session, league_id="league-b"
    )
    assert not any("Jeanty" in str(row.get("headline")) for row in leaked)
    assert not any(row.get("player_id") == "jeanty-a" for row in leaked)


def test_alerts_timeline_a_to_b_to_a_and_rapid_switch():
    from unittest.mock import patch

    import app

    state = _league_session("league-a", include_jeanty=True)
    state["_effective_entitlement"] = "premium"
    class _State(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

        def __setattr__(self, name, value):
            self[name] = value

        def __delattr__(self, name):
            del self[name]

    session = _State(state)
    rapid_b = alerts_activity.compose_activity_timeline(
        session=session, league_id="league-b"
    )
    assert not any("Jeanty" in str(row.get("headline")) for row in rapid_b)

    with patch.object(app.st, "session_state", session):
        app._clear_league_switch_transient_state(previous_league_id="league-a")
    assert alerts_activity.TIMELINE_SESSION_KEY not in session
    assert ni.TIMELINE_EVENT_KEY not in session
    assert ni.ALERT_STATE_KEY not in session
    assert ni.PRESENTATION_DIGEST_KEY not in session
    assert nc.ACTIVITY_INBOX_SNAPSHOT_KEY not in session
    assert session.get("_effective_entitlement") == "premium"

    b_before_refresh = alerts_activity.compose_activity_timeline(
        session=session, league_id="league-b"
    )
    assert not any("Jeanty" in str(row.get("headline") or "") for row in b_before_refresh)
    header_b = alerts_activity.compose_header_alerts(
        nc.compose_activity_inbox(session=session, league_id="league-b")
    )
    assert all("Jeanty" not in item.title for item in header_b)

    b_event = {
        "recommendation_id": "news-pickens-b",
        "event_identity": "role:pickens-b",
        "player_id": "pickens-b",
        "value": "George Pickens role update",
        "should_alert": False,
        "news_event_severity": "LOW",
        "category": "NEWS",
        "league_id": "league-b",
    }
    session["selected_league_id"] = "league-b"
    session[nc.ACTIVITY_INBOX_SNAPSHOT_KEY] = {
        "league_id": "league-b",
        "records": [
            {
                "id": "news-pickens-b",
                "category": "NEWS",
                "title": "George Pickens role update",
                "body": "B news",
                "source_kind": "canonical",
                "player_id": "pickens-b",
                "age_label": "9m",
            }
        ],
    }
    alerts_activity.store_timeline_events(session, [b_event], league_id="league-b")
    b_rows = alerts_activity.compose_activity_timeline(session=session, league_id="league-b")
    assert any("George Pickens role update" in row["headline"] for row in b_rows)
    assert not any("Jeanty" in row["headline"] for row in b_rows)

    with patch.object(app.st, "session_state", session):
        app._clear_league_switch_transient_state(previous_league_id="league-b")
    a_from_b_leak = alerts_activity.compose_activity_timeline(
        session=session, league_id="league-a"
    )
    blob = " ".join(str(row) for row in a_from_b_leak)
    assert "Jeanty" not in blob
    assert "pickens-b" not in blob

    restored = _league_session("league-a", include_jeanty=True)
    session.update(restored)
    a_restored = alerts_activity.compose_activity_timeline(
        session=session, league_id="league-a"
    )
    assert any("Ashton Jeanty ruled out" in row["headline"] for row in a_restored)
    b_isolated = alerts_activity.compose_activity_timeline(
        session=session, league_id="league-b"
    )
    assert not any("Jeanty" in row["headline"] for row in b_isolated)


def test_signal_intelligence_keys_are_league_scoped():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    keys = app.split("LEAGUE_SWITCH_TRANSIENT_STATE_KEYS = (", 1)[1].split(
        "LEAGUE_SETTINGS_OVERRIDE_KEYS", 1
    )[0]
    for key in (
        "_signal_intelligence_timeline",
        "_news_intelligence_timeline_events",
        "_news_intelligence_alert_state",
        "_news_intelligence_presentation_digest",
        "_news_intelligence_roster_context",
    ):
        assert key in keys
        from modules import session_integrity

        assert session_integrity.SESSION_KEY_LIFETIMES[key] == "LEAGUE"
    clearer = app.split("def _clear_league_switch_transient_state(", 1)[1].split(
        "\ndef _open_notification_destination(", 1
    )[0]
    assert "clear_signal_intelligence_timeline" in clearer
    assert "news_intelligence.clear_alert_state" in clearer
