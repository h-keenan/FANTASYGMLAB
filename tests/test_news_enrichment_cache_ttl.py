"""modules.news's enriched-pool cache: bounded by a TTL, not recomputed every call.

enrich_news_item() re-classifies every article in the pool on every call —
cheap for a single Streamlit rerun, expensive when
services/mobile_api_service.py's GET /v1/news re-runs it on every request.
These tests pin the fix: an automatic time-bucketed cache around the
load + enrich step.
"""

from __future__ import annotations

from unittest.mock import patch

from modules import news


def _article(link: str, title: str = "Star RB (knee) questionable for Sunday") -> dict:
    return {
        "title": title,
        "summary": "The team's RB1 was limited in practice with a knee issue.",
        "link": link,
        "source": "https://www.espn.com/espn/rss/nfl/news",
        "published_ts": 1000.0,
    }


def test_enriched_news_pool_hits_cache_within_the_same_ttl_bucket():
    news.clear_enriched_news_pool_cache()
    with patch("modules.news.load_cached_news_pool", return_value=[_article("https://example.com/a")]) as mock_load:
        with patch("modules.news._enriched_news_pool_bucket", return_value=42):
            first = news.enriched_news_pool()
            second = news.enriched_news_pool()
    assert first == second
    assert len(first) == 1
    # One load_cached_news_pool() call covers both — the second is a cache hit.
    assert mock_load.call_count == 1


def test_enriched_news_pool_refetches_once_the_ttl_bucket_advances():
    news.clear_enriched_news_pool_cache()
    with patch("modules.news.load_cached_news_pool", return_value=[_article("https://example.com/a")]):
        with patch("modules.news._enriched_news_pool_bucket", return_value=1):
            first = news.enriched_news_pool()
    with patch(
        "modules.news.load_cached_news_pool",
        return_value=[_article("https://example.com/a"), _article("https://example.com/b")],
    ):
        with patch("modules.news._enriched_news_pool_bucket", return_value=2):
            second = news.enriched_news_pool()
    assert len(first) == 1
    assert len(second) == 2


def test_enriched_news_pool_items_carry_signal_classification():
    news.clear_enriched_news_pool_cache()
    with patch("modules.news.load_cached_news_pool", return_value=[_article("https://example.com/a")]):
        with patch("modules.news._enriched_news_pool_bucket", return_value=99):
            [item] = news.enriched_news_pool()
    assert "signal_primary_event" in item
    assert "signal_events" in item


def test_clear_enriched_news_pool_cache_does_not_raise():
    news.clear_enriched_news_pool_cache()
