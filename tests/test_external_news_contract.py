"""Source-backed contract fields on GET /v1/external/players/{id}/news."""

from __future__ import annotations

import os
import time
from unittest.mock import patch

import pandas as pd
import pytest

from modules import external_news_contract as enc


def _get(pool, players_frame, player_id="9001"):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from modules import news as news_module
    from services import mobile_api_service

    os.environ["FANTASYDESK_EXTERNAL_API_KEY"] = "k"
    client = TestClient(mobile_api_service.app)
    news_module.clear_enriched_news_pool_cache()
    try:
        with patch("services.mobile_api_service._external_news_players_frame", return_value=players_frame):
            with patch("modules.news.schedule_news_cache_refresh", return_value=False):
                with patch("modules.news.load_cached_news_pool", return_value=pool):
                    return client.get(
                        f"/v1/external/players/{player_id}/news", headers={"Authorization": "Bearer k"}
                    ).json()
    finally:
        os.environ.pop("FANTASYDESK_EXTERNAL_API_KEY", None)
        news_module.clear_enriched_news_pool_cache()


def _frame(**extra):
    row = {"player_id": "9001", "name": "Nico Collins", "team": "HOU", "status": "Questionable", "injury_status": "Hamstring"}
    row.update(extra)
    return pd.DataFrame([row])


def _article(now, **kw):
    base = {
        "title": "Nico Collins (hamstring) questionable for Sunday",
        "summary": "The Texans WR was limited in practice.",
        "link": "https://www.espn.com/nfl/story/collins",
        "source": "https://www.espn.com/espn/rss/nfl/news",
        "published_ts": now - 3600,
    }
    base.update(kw)
    return base


def test_item_carries_contract_fields_and_is_honestly_review_only():
    now = time.time()
    body = _get([_article(now)], _frame())
    item = body["items"][0]
    for legacy in ("player_id", "event_identity", "event_type", "description", "source_urls", "published_at",
                   "checked_at", "supported_claims", "confidence", "corroboration_label", "superseded_by",
                   "retraction_status"):
        assert legacy in item
    assert item["league"] == "NFL"
    assert item["id"] == item["event_identity"]
    assert len(item["revision_id"]) == 16
    assert item["player_ids"]["sleeper"] == "9001"
    assert item["player_ids"]["gsis"] is None
    assert item["player_ids"]["gsis_unavailable_reason"] == "no_gsis_crosswalk_available"
    assert item["player"] == {"name": "Nico Collins", "team": "HOU"}
    assert isinstance(item["published_ts"], int) and abs(item["published_ts"] - (now - 3600)) < 2
    assert item["status"] == "reported"
    assert item["retracted"] is False
    prov = item["provenance"]
    assert len(prov) == 1
    assert prov[0]["content_sha256"] is None
    assert prov[0]["checked_at"] is None
    assert prov[0]["excerpt"] is None
    assert prov[0]["document_type"] == "headline_only_feed_item"
    assert prov[0]["original_url"] == "https://www.espn.com/nfl/story/collins"
    assert prov[0]["allowlist_status"] == "allowlisted"
    assert item["content"]["kind"] == "headline_only" and item["content"]["body"] is None
    assert item["evidence"]["status"] == "unavailable"
    assert item["review_only"] is True
    assert "document_not_fetched_headline_only" in item["review_only_reasons"]
    assert item["freshness"]["class"] == "urgent_availability"
    assert item["freshness"]["published_within_limit"] is True
    assert item["freshness"]["checked_within_limit"] is None
    fields = {c["field"]: c for c in item["claims"]}
    assert fields["event_type"]["value"] == "INJURY"
    assert fields["availability_designation"]["value"] == "questionable"
    assert fields["team_affiliation"]["value"] == "HOU"
    for c in item["claims"]:
        assert c["source_ids"] == [prov[0]["id"]]


def test_revision_id_is_stable_across_calls():
    now = time.time()
    a = _get([_article(now)], _frame())["items"][0]
    b = _get([_article(now)], _frame())["items"][0]
    assert a["id"] == b["id"] and a["revision_id"] == b["revision_id"]


def test_non_allowlisted_domain_is_reported_not_trusted():
    now = time.time()
    item = _get([_article(now, link="https://random-blog.example/collins")], _frame())["items"][0]
    assert item["provenance"][0]["allowlist_status"] == "not_allowlisted"
    assert item["domain_review"] == ["random-blog.example"]
    assert "non_allowlisted_domain" in item["review_only_reasons"]


def test_two_hosts_listed_but_independence_unverified():
    now = time.time()
    pool = [
        _article(now),
        _article(now, link="https://www.cbssports.com/nfl/collins", source="https://www.cbssports.com/rss/headlines/nfl/"),
    ]
    item = _get(pool, _frame())["items"][0]
    assert len(item["provenance"]) == 2
    assert item["corroboration"]["independent_publisher_count"] == 2
    assert item["corroboration"]["independence_verified"] is False
    assert item["status"] != "confirmed"


def test_stale_article_fails_freshness_window():
    now = time.time()
    item = _get([_article(now, published_ts=now - 10 * 3600)], _frame())["items"][0]
    assert item["freshness"]["published_within_limit"] is False


def test_gsis_only_when_unambiguous():
    ok = enc.resolve_player_identity(_frame(gsis_id="00-0033280"), "9001", "Nico Collins")
    assert ok["player_ids"]["gsis"] == "00-0033280"
    dup = pd.concat([_frame(gsis_id="00-0033280"), _frame(gsis_id="00-0099999").assign(player_id="9002")])
    amb = enc.resolve_player_identity(dup, "9001", "Nico Collins")
    assert amb["player_ids"]["gsis"] is None
    assert amb["player_ids"]["gsis_unavailable_reason"] == "ambiguous_name_team_mapping"
    bad = enc.resolve_player_identity(_frame(gsis_id="123"), "9001", "Nico Collins")
    assert bad["player_ids"]["gsis_unavailable_reason"] == "gsis_malformed"
    missing = enc.resolve_player_identity(_frame(gsis_id=""), "9001", "Nico Collins")
    assert missing["player_ids"]["gsis_unavailable_reason"] == "gsis_not_mapped_for_player"


def test_superseded_item_flags_status_claims_and_revision_changes():
    now = time.time()
    pool = [
        _article(now, title="Nico Collins ruled out for Sunday with hamstring injury",
                 summary="Texans WR is out.", published_ts=now - 5 * 86400, link="https://www.espn.com/a"),
        _article(now, title="Nico Collins activated from injured reserve, cleared to play Sunday",
                 summary="Collins is back.", published_ts=now - 3 * 86400,
                 link="https://www.rotowire.com/b", source="https://www.rotowire.com/rss/news.php?sport=NFL"),
    ]
    items = _get(pool, _frame())["items"]
    sup = [i for i in items if i["superseded_by"]]
    assert sup, items
    s = sup[0]
    assert s["status"] == "superseded"
    assert all(c["status"] == "superseded" and c["superseded_by"] == s["superseded_by"] for c in s["claims"])
    assert "status_superseded" in s["review_only_reasons"]
    live = [i for i in items if not i["superseded_by"]][0]
    assert live["revision_id"] != s["revision_id"]


def test_freshness_windows_general_vs_urgent():
    urgent = enc.build_freshness(event_type="INJURY", published_ts=1000, checked_ts=1000, now_ts=1000 + 6 * 3600 + 1)
    assert urgent["published_within_limit"] is False and urgent["checked_within_limit"] is False
    general = enc.build_freshness(event_type="TRADE", published_ts=1000, checked_ts=1000, now_ts=1000 + 3000)
    assert general["class"] == "general"
    assert general["published_within_limit"] is True and general["checked_within_limit"] is True
