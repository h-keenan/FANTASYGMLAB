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
    assert "border-radius:0" in ALERTS_ACTIVITY_CSS
    assert "st-key-alerts_filter_" in ALERTS_ACTIVITY_CSS
    assert count_explicit_reruns() <= 58


def test_viewport_harness_covers_390_and_1440_alerts():
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    validate = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    assert '"alerts"' in harness or "'alerts'" in harness
    assert '"alerts"' in validate
    assert "390" in validate
    assert "1440" in validate
    assert "Ashton Jeanty status changed" in harness
