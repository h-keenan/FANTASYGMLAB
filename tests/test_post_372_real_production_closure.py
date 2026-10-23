from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from modules import alerts_activity, news, trade_ideas


ROOT = Path(__file__).resolve().parents[1]


def test_deploy_mtime_cannot_make_old_articles_fresh(tmp_path: Path, monkeypatch):
    cache = tmp_path / "news_cache.json"
    cache.write_text(
        json.dumps([{"title": "Old", "link": "https://example.com/old", "published_ts": 1.0}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(news.time, "time", lambda: 10_000.0)
    monkeypatch.setattr(news.os.path, "getmtime", lambda _path: 9_999.0)
    assert news._cache_is_fresh(str(cache), ttl_seconds=1200) is False


def test_current_article_and_file_timestamp_are_both_required(tmp_path: Path, monkeypatch):
    cache = tmp_path / "news_cache.json"
    cache.write_text(
        json.dumps([{"title": "Current", "link": "https://example.com/current", "published_ts": 9_500.0}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(news.time, "time", lambda: 10_000.0)
    monkeypatch.setattr(news.os.path, "getmtime", lambda _path: 9_900.0)
    assert news._cache_is_fresh(str(cache), ttl_seconds=1200) is True


def test_deferred_news_refresh_is_single_flight_and_nonblocking(monkeypatch):
    started: list[bool] = []

    class _Thread:
        def __init__(self, *, target, name, daemon):
            self.target = target
            self.name = name
            self.daemon = daemon
            self._alive = False

        def start(self):
            self._alive = True
            started.append(True)

        def is_alive(self):
            return self._alive

    monkeypatch.setattr(news, "_NEWS_REFRESH_THREAD", None)
    monkeypatch.setattr(news, "_cache_is_fresh", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(news.threading, "Thread", _Thread)
    assert news.schedule_news_cache_refresh() is True
    assert news.schedule_news_cache_refresh() is False
    assert started == [True]


def test_elite_search_zero_state_exposes_sanitized_closest_rejections():
    report = trade_ideas.player_hub_rejection_diagnostic(
        {
            "ideas": [],
            "fallback_used": True,
            "diagnostics": {
                "candidate_generated": 7,
                "closest_rejections": [
                    {
                        "assets": ["Starter RB", "2027 Round 1"],
                        "send_value": 9200,
                        "receive_value": 9730,
                        "difference": -530,
                        "ratio": 0.9455,
                        "stage": "partner_fit",
                        "reason": "partner-fit score -4 is not positive",
                    }
                ],
            },
        }
    )
    assert report["counts"]["candidate_generated"] == 7
    assert report["visible_ideas"] == 0
    assert report["closest_rejections"][0]["constraint"] == "soft"
