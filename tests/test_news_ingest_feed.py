"""Scheduled news ingest, identity, dedupe, cursor feed, cold start, UA, injury alarm.

All players/articles are synthetic. No network, no real data/*.db or data/*.json.
"""

from __future__ import annotations

import importlib.util
import os
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from modules import external_news_feed as feed
from modules import news, news_identity, news_ingest, news_signal

NOW = 1_790_000_000.0
ROOT = Path(__file__).resolve().parents[1]


def _entry(title, link, summary="", ts=NOW - 600):
    return {"title": title, "link": link, "summary": summary,
            "published_parsed": time.gmtime(ts)}


class _Feed(SimpleNamespace):
    pass


def _ok(*entries):
    return _Feed(entries=[_FakeEntry(e) for e in entries], bozo=False)


class _FakeEntry(dict):
    def __getattr__(self, k):  # entry.content access in news._entry_to_item
        raise AttributeError(k)


def _bad():
    return _Feed(entries=[], bozo=True, bozo_exception=RuntimeError("503"))


def _players():
    return pd.DataFrame(
        [
            {"player_id": "1", "name": "Test Alpha", "team": "HOU", "position": "WR", "status": "Active", "injury_status": "Questionable"},
            {"player_id": "2", "name": "Mike Sample", "team": "DAL", "position": "WR", "status": "Active", "injury_status": ""},
            {"player_id": "3", "name": "Mike Sample", "team": "KC", "position": "RB", "status": "Active", "injury_status": "Out"},
        ]
    )


DUMP = {"1": {"player_id": "1", "full_name": "Test Alpha", "team": "HOU", "position": "WR", "gsis_id": "00-0012345"}}


# ---- (1)(2) cold start + user agent ---------------------------------------

def test_user_agent_is_honest_and_identifying():
    assert "Mozilla" not in news.NEWS_USER_AGENT
    assert "FantasyDesk" in news.NEWS_USER_AGENT and "fantasydesk.app" in news.NEWS_USER_AGENT
    with patch("modules.news.requests.get") as get:
        get.return_value = SimpleNamespace(raise_for_status=lambda: None, content=b"<rss/>")
        news._parse_feed("https://example.com/rss")
    assert get.call_args.kwargs["headers"]["User-Agent"] == news.NEWS_USER_AGENT


def test_cold_start_status_is_helpful_not_empty(tmp_path):
    missing = tmp_path / "none.json"
    with patch.object(news, "NEWS_CACHE_PATH", str(missing)):
        status = news.news_feed_status(now=NOW)
    assert status["state"] == "warming_up" and "check back" in status["message"].lower()


def test_stale_cache_status(tmp_path):
    cache = tmp_path / "c.json"
    cache.write_text('[{"title":"t","link":"l","published_ts": %d}]' % (NOW - 40 * 86400))
    with patch.object(news, "NEWS_CACHE_PATH", str(cache)):
        assert news.news_feed_status(now=NOW)["state"] == "stale"
        assert news.news_feed_status(now=NOW - 39 * 86400)["state"] == "ok"


def test_stale_news_cache_seed_is_not_tracked():
    out = subprocess.run(["git", "ls-files", "data/news_cache.json"], cwd=ROOT, capture_output=True, text=True)
    assert out.stdout.strip() == ""
    assert "data/news_cache.json" in (ROOT / ".gitignore").read_text()


# ---- (5) dedupe + identity ------------------------------------------------

def test_normalize_title_strips_outlet_and_punctuation():
    assert news_signal.normalize_title("Test Alpha (hamstring) Questionable - ESPN") == "test alpha hamstring questionable"
    assert news_signal.normalize_title("TEST ALPHA: hamstring, questionable | Pro Football Talk") == "test alpha hamstring questionable"


def test_event_identity_ignores_outlet_suffix_and_case():
    a = {"title": "Test Alpha hamstring questionable - ESPN", "matched_player": "Test Alpha", "published_ts": NOW}
    b = {"title": "TEST ALPHA hamstring questionable!", "matched_player": "Test Alpha", "published_ts": NOW}
    assert news_signal.event_identity(a) == news_signal.event_identity(b)


def test_canonical_url_drops_tracking_www_and_slash():
    assert news_signal.canonical_url("https://www.espn.com/nfl/story/x/?utm_source=a#f") == news_signal.canonical_url("http://espn.com/nfl/story/x")


def test_near_duplicate_needs_overlap_and_size():
    a = news_signal.title_tokens("Test Alpha (hamstring) questionable for Sunday")
    b = news_signal.title_tokens("Texans WR Test Alpha questionable Sunday with hamstring injury")
    c = news_signal.title_tokens("Test Alpha signs contract extension through 2030")
    assert news_signal.tokens_near_duplicate(a, b)
    assert not news_signal.tokens_near_duplicate(a, c)
    assert not news_signal.tokens_near_duplicate(news_signal.title_tokens("Alpha out"), news_signal.title_tokens("Alpha out today"))


def test_identity_unique_name_and_gsis():
    idx = news_identity.IdentityIndex(_players(), sleeper_dump=DUMP)
    matches, amb = news_identity.match_article_players({"title": "Test Alpha limited in practice"}, idx)
    assert [(m.player_id, m.method) for m in matches] == [("1", "unique_name")]
    assert idx.gsis("1") == ("00-0012345", None)
    assert idx.gsis("2")[0] is None


def test_identity_shared_name_needs_team_else_ambiguous():
    idx = news_identity.IdentityIndex(_players())
    matches, amb = news_identity.match_article_players({"title": "Mike Sample out for Sunday"}, idx)
    assert matches == [] and amb == ["mike sample"]
    matches, _ = news_identity.match_article_players({"title": "Chiefs RB Mike Sample out for Sunday"}, idx)
    assert [(m.player_id, m.method) for m in matches] == [("3", "name_plus_team")]
    matches, _ = news_identity.match_article_players({"title": "Mike Sample (DAL) questionable"}, idx)
    assert [m.player_id for m in matches] == ["2"]


def test_identity_explicit_ids_win_and_three_names_fail_closed():
    idx = news_identity.IdentityIndex(_players(), sleeper_dump=DUMP)
    matches, _ = news_identity.match_article_players({"title": "x", "gsis_id": "00-0012345"}, idx)
    assert matches[0].player_id == "1" and matches[0].method == "explicit_id"
    matches, _ = news_identity.match_article_players({"title": "x", "player_id": "2"}, idx)
    assert matches[0].player_id == "2"
    many = pd.DataFrame([{"player_id": str(i), "name": n, "team": "HOU", "position": "WR"} for i, n in enumerate(["Aa Bb", "Cc Dd", "Ee Ff"])])
    idx2 = news_identity.IdentityIndex(many)
    assert news_identity.match_article_players({"title": "Aa Bb, Cc Dd and Ee Ff traded"}, idx2)[0] == []


def test_article_names_player_requires_team_when_name_shared():
    df = _players()
    item = {"title": "Mike Sample out for Sunday"}
    assert not news_identity.article_names_player(item, "3", "Mike Sample", df)
    assert news_identity.article_names_player({"title": "Chiefs Mike Sample out"}, "3", "Mike Sample", df)
    assert not news_identity.article_names_player({"title": "Chiefs Mike Sample out"}, "2", "Mike Sample", df)
    assert news_identity.article_names_player({"title": "Test Alpha out"}, "1", "Test Alpha", df)


def test_read_players_frame_is_read_only(tmp_path):
    db = tmp_path / "p.db"
    conn = sqlite3.connect(db)
    conn.execute("create table players (player_id text, name text)")
    conn.execute("insert into players values ('1','A B')")
    conn.commit(); conn.close()
    before = db.read_bytes()
    assert len(news_identity.read_players_frame(str(db))) == 1
    assert db.read_bytes() == before
    assert news_identity.read_players_frame(str(tmp_path / "missing.db")).empty
    assert not (tmp_path / "missing.db").exists()


# ---- (6) ingest ----------------------------------------------------------

def _store(tmp_path):
    return news_ingest.FileNewsStore(str(tmp_path / "items.json"))


FEEDS = ["https://www.espn.com/espn/rss/nfl/news", "https://www.cbssports.com/rss/headlines/nfl/"]


def test_ingest_persists_items_revisions_and_health(tmp_path):
    store = _store(tmp_path)
    espn = _entry("Test Alpha (hamstring) questionable for Sunday", "https://www.espn.com/nfl/story/a", "Limited in practice.")
    fetch = lambda url: _ok(espn) if "espn" in url else _bad()
    stats = news_ingest.ingest_once(store, feeds=FEEDS, fetch=fetch, now=NOW)
    assert stats["ok"] and stats["new_items"] == 1 and stats["failed_sources"] == ["cbssports.com"]
    health = {h["source_key"]: h for h in store.read_health()}
    assert health["espn.com"]["consecutive_failures"] == 0 and health["espn.com"]["last_new_item_count"] == 1
    assert health["cbssports.com"]["consecutive_failures"] == 1 and "503" in health["cbssports.com"]["last_error"]
    # second run: same content -> no new revision; failing source counts up and keeps last_success_at None
    stats2 = news_ingest.ingest_once(store, feeds=FEEDS, fetch=fetch, now=NOW + 900)
    assert stats2["new_items"] == 0 and stats2["new_revisions"] == 0
    health = {h["source_key"]: h for h in store.read_health()}
    assert health["cbssports.com"]["consecutive_failures"] == 2 and health["cbssports.com"]["last_success_at"] is None
    assert len(store.read_revisions(0, 0, 100)) == 1


def test_ingest_all_sources_failing_is_not_ok(tmp_path):
    stats = news_ingest.ingest_once(_store(tmp_path), feeds=FEEDS, fetch=lambda u: _bad(), now=NOW)
    assert not stats["ok"] and len(stats["failed_sources"]) == 2


def test_changed_feed_text_makes_new_revision_with_previous_id(tmp_path):
    store = _store(tmp_path)
    link = "https://www.espn.com/nfl/story/a"
    news_ingest.ingest_once(store, feeds=FEEDS[:1], fetch=lambda u: _ok(_entry("Test Alpha questionable for Sunday", link)), now=NOW)
    news_ingest.ingest_once(store, feeds=FEEDS[:1], fetch=lambda u: _ok(_entry("Test Alpha ruled out for Sunday", link)), now=NOW + 900)
    revs = store.read_revisions(0, 0, 100)
    assert len(revs) == 2 and revs[0]["item_id"] == revs[1]["item_id"]
    assert revs[1]["previous_revision_id"] == revs[0]["revision_id"] and revs[0]["revision_id"] != revs[1]["revision_id"]


def test_cross_outlet_near_duplicates_collapse_into_first_copy(tmp_path):
    store = _store(tmp_path)
    espn = _entry("Test Alpha (hamstring) questionable for Sunday", "https://www.espn.com/nfl/story/a", ts=NOW - 3000)
    cbs = _entry("Texans WR Test Alpha questionable Sunday with hamstring injury", "https://www.cbssports.com/nfl/news/b", ts=NOW - 1000)
    fetch = lambda url: _ok(espn) if "espn" in url else _ok(cbs)
    news_ingest.ingest_once(store, feeds=FEEDS, fetch=fetch, now=NOW)
    items = store._load()["items"]
    dup = [i for i in items.values() if i["duplicate_of"]]
    assert len(items) == 2 and len(dup) == 1 and dup[0]["source_key"] == "cbssports.com"
    page = feed.build_feed(store, players_df=_players(), index=news_identity.IdentityIndex(_players(), sleeper_dump=DUMP), now=NOW + 60)
    assert len(page["items"]) == 1
    domains = {p["publisher_domain"] for p in page["items"][0]["provenance"]}
    assert domains == {"espn.com", "cbssports.com"}


# ---- (7) feed -------------------------------------------------------------

def _seeded(tmp_path):
    store = _store(tmp_path)
    entries = [
        _entry("Test Alpha (hamstring) questionable for Sunday", "https://www.espn.com/nfl/story/a", "Texans WR limited.", ts=NOW - 600),
        _entry("Mike Sample out for Sunday", "https://www.espn.com/nfl/story/b", "", ts=NOW - 500),
        _entry("Coach announces new offensive scheme", "https://www.espn.com/nfl/story/c", "", ts=NOW - 400),
    ]
    news_ingest.ingest_once(store, feeds=FEEDS[:1], fetch=lambda u: _ok(*entries), now=NOW - 300)
    return store


def test_feed_items_honest_fields_and_claims_only_from_sleeper(tmp_path):
    store = _seeded(tmp_path)
    idx = news_identity.IdentityIndex(_players(), sleeper_dump=DUMP)
    page = feed.build_feed(store, players_df=_players(), index=idx, now=NOW)
    assert page["league"] == "NFL" and len(page["items"]) == 3
    alpha = next(i for i in page["items"] if "Alpha" in i["content"]["headline"])
    assert alpha["player_ids"][0]["sleeper"] == "1" and alpha["player_ids"][0]["gsis"] == "00-0012345"
    assert alpha["retracted"] is False and alpha["retraction_detection"] == "not_performed"
    assert alpha["superseded"] is False and alpha["previous_revision_id"] is None
    prov = alpha["provenance"][0]
    assert prov["content_sha256"] is None and prov["checked_at"] is None and prov["excerpt"] is None
    assert prov["first_seen_at"] and prov["retrieval"] == "publisher_rss_feed_only"
    assert alpha["content"]["body"] is None
    fields = {(c["field"], c["value"]) for c in alpha["claims"]}
    assert ("availability_designation", "questionable") in fields and ("team_affiliation", "HOU") in fields
    assert all(c["source"] == "sleeper_api" and c["article_supported"] is False for c in alpha["claims"])
    ambiguous = next(i for i in page["items"] if "Sample" in i["content"]["headline"])
    assert ambiguous["unmatched"] and ambiguous["player_match_unavailable_reason"] == "ambiguous_player_name" and ambiguous["claims"] == []
    other = next(i for i in page["items"] if "scheme" in i["content"]["headline"])
    assert other["unmatched"] and other["claims_unavailable_reason"]
    assert all(i["status"] in ("reported", "speculative", "superseded") for i in page["items"])


def test_cursor_pagination_and_since(tmp_path):
    store = _seeded(tmp_path)
    idx = news_identity.IdentityIndex(_players())
    p1 = feed.build_feed(store, players_df=_players(), index=idx, limit=2, now=NOW)
    assert len(p1["items"]) == 2 and p1["has_more"] and p1["next_cursor"].startswith("c1.")
    p2 = feed.build_feed(store, players_df=_players(), index=idx, cursor=p1["next_cursor"], limit=2, now=NOW)
    assert len(p2["items"]) == 1 and not p2["has_more"]
    p3 = feed.build_feed(store, players_df=_players(), index=idx, cursor=p2["next_cursor"], now=NOW)
    assert p3["items"] == [] and p3["next_cursor"] == p2["next_cursor"]
    future = datetime.fromtimestamp(NOW + 10, tz=timezone.utc).isoformat()
    empty = feed.build_feed(store, players_df=_players(), index=idx, since=future, now=NOW)
    assert empty["items"] == [] and any(u["reason"] == "no_items_in_window" for u in empty["unavailable"])
    with pytest.raises(feed.CursorError):
        feed.decode_cursor("garbage")
    with pytest.raises(feed.CursorError):
        feed.parse_since("yesterday")


def test_superseded_revision_flagged_when_newer_exists(tmp_path):
    store = _store(tmp_path)
    link = "https://www.espn.com/nfl/story/a"
    news_ingest.ingest_once(store, feeds=FEEDS[:1], fetch=lambda u: _ok(_entry("Test Alpha questionable for Sunday", link)), now=NOW - 2000)
    news_ingest.ingest_once(store, feeds=FEEDS[:1], fetch=lambda u: _ok(_entry("Test Alpha ruled out for Sunday", link)), now=NOW - 1000)
    page = feed.build_feed(store, players_df=_players(), index=news_identity.IdentityIndex(_players()), now=NOW)
    first, second = page["items"]
    assert first["superseded"] and first["status"] == "superseded" and first["superseded_by_revision_id"] == second["revision_id"]
    assert not second["superseded"] and second["previous_revision_id"] == first["revision_id"]


def test_empty_store_reports_unavailable_reasons(tmp_path):
    store = news_ingest.FileNewsStore(str(tmp_path / "x.json"), fallback_reason="supabase_not_configured")
    page = feed.build_feed(store, players_df=None, index=None, now=NOW)
    reasons = {u["reason"] for u in page["unavailable"]}
    assert {"no_ingest_data_yet", "durable_store_unavailable_using_local_file", "players_table_unavailable"} <= reasons
    assert page["items"] == [] and page["ingest"]["durable"] is False


def test_open_store_falls_back_when_not_configured_or_tables_missing(tmp_path):
    s = news_ingest.open_store(environ={}, file_path=str(tmp_path / "f.json"))
    assert s.backend == "file" and s.fallback_reason == "supabase_not_configured"
    with patch.object(news_ingest.SupabaseNewsStore, "probe", side_effect=news_ingest.StoreError("404 relation does not exist")):
        s = news_ingest.open_store(
            environ={"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}, file_path=str(tmp_path / "f.json")
        )
    assert s.backend == "file" and "tables_missing" in s.fallback_reason


# ---- route: auth, no load_players on real db, no fetching -----------------

def test_feed_route_requires_key_never_loads_players_or_fetches(tmp_path, monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from services import mobile_api_service as svc

    store = _seeded(tmp_path)
    monkeypatch.setenv("FANTASYDESK_EXTERNAL_API_KEY", "k")
    client = TestClient(svc.app)
    assert client.get("/v1/external/news").status_code in (401, 403)

    def boom(*a, **k):
        raise AssertionError("must not be called")

    with patch("modules.rankings.load_players", boom), patch("modules.rankings.build_players_table", boom), patch(
        "modules.news._parse_feed", boom
    ), patch("modules.news_ingest.open_store", return_value=store), patch(
        "modules.news_identity.load_index", return_value=(_players(), news_identity.IdentityIndex(_players(), sleeper_dump=DUMP))
    ):
        resp = client.get("/v1/external/news?since=1", headers={"Authorization": "Bearer k"})
        assert resp.status_code == 200 and len(resp.json()["items"]) == 3
        assert client.get("/v1/external/news?cursor=bad", headers={"Authorization": "Bearer k"}).status_code == 422
        assert client.get("/v1/external/news?limit=0", headers={"Authorization": "Bearer k"}).status_code == 422


def test_player_news_route_does_not_call_load_players(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from services import mobile_api_service as svc

    def boom(*a, **k):
        raise AssertionError("must not be called")

    monkeypatch.setenv("FANTASYDESK_EXTERNAL_API_KEY", "k")
    client = TestClient(svc.app)
    with patch("modules.rankings.load_players", boom), patch("modules.rankings.build_players_table", boom), patch.object(
        svc, "_external_news_players_frame", return_value=pd.DataFrame()
    ):
        resp = client.get("/v1/external/players/1/news", headers={"Authorization": "Bearer k"})
    assert resp.status_code == 200 and resp.json()["items"] == []


# ---- (3) injury sync zero-patch alarm ------------------------------------

def _sis():
    spec = importlib.util.spec_from_file_location("sync_injury_status_t", ROOT / "scripts" / "sync_injury_status.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_zero_patch_alarm_only_on_game_day_after_threshold():
    sis = _sis()
    sunday = datetime(2026, 10, 25, 18, tzinfo=timezone.utc)
    tuesday = datetime(2026, 10, 27, 18, tzinfo=timezone.utc)
    july_sunday = datetime(2026, 7, 5, 18, tzinfo=timezone.utc)
    old = sunday.timestamp() - 20 * 3600
    recent = sunday.timestamp() - 2 * 3600
    assert sis.evaluate_zero_patch(updated=0, now=sunday, last_patch_ts=old, max_hours=12)[0] is True
    assert sis.evaluate_zero_patch(updated=0, now=sunday, last_patch_ts=recent, max_hours=12)[0] is False
    assert sis.evaluate_zero_patch(updated=3, now=sunday, last_patch_ts=old, max_hours=12)[0] is False
    assert sis.evaluate_zero_patch(updated=0, now=tuesday, last_patch_ts=old, max_hours=12)[0] is False
    assert sis.evaluate_zero_patch(updated=0, now=july_sunday, last_patch_ts=old, max_hours=12)[0] is False
    alarm, msg = sis.evaluate_zero_patch(updated=0, now=sunday, last_patch_ts=None, max_hours=12)
    assert alarm is False and "unknown" in msg


def test_runner_fails_nonzero_when_alarm_and_uses_refresh_true(tmp_path, monkeypatch):
    sis = _sis()
    db = tmp_path / "players.db"
    conn = sqlite3.connect(db)
    conn.execute("create table players (player_id text, status text, injury_status text, name text, value real, score real)")
    conn.execute("insert into players values ('1','Active','','A',1,1)")
    conn.commit(); conn.close()
    seen = {}

    def fake_players(refresh=False):
        seen["refresh"] = refresh
        return {"1": {"player_id": "1", "status": "Active", "injury_status": None}}

    monkeypatch.setattr(sis.sleeper, "get_players", fake_players)
    fixed = datetime(2026, 10, 25, 18, tzinfo=timezone.utc)

    class _DT(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr(sis, "datetime", _DT)
    monkeypatch.setattr(sis, "last_injury_patch_commit_ts", lambda *a, **k: fixed.timestamp() - 30 * 3600)
    assert sis.default_patch_runner(db) == sis.EXIT_ZERO_PATCH_ALARM
    assert seen["refresh"] is True
    monkeypatch.setattr(sis, "last_injury_patch_commit_ts", lambda *a, **k: fixed.timestamp() - 1 * 3600)
    assert sis.default_patch_runner(db) == 0
