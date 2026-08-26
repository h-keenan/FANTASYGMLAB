from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from modules import alerts_activity, alerts_activity_ui, news, trade_ideas


ROOT = Path(__file__).resolve().parents[1]


def test_trade_detail_shortcut_promotes_fragment_handoff_to_parent_app_rerun():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    grid = app.split("def render_player_detail_button_grid", 1)[1].split("_truncate_text", 1)[0]
    assert "queue_canonical_player_quick_view(" in grid
    assert 'st.rerun(scope="app")' in grid
    assert "shortcut_clicked = st.button(" in grid
    assert "on_click=_open_selected_player" not in grid
    assert "_open_selected_player()" in grid
    assert grid.index("shortcut_clicked = st.button(") < grid.index('st.rerun(scope="app")')


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


def test_cached_alert_preserves_safe_source_and_player_action_contract():
    raw = {
        "id": "news:1",
        "title": "Tyrone Tracy returns to practice",
        "player_id": "11604",
        "link": "https://example.com/tracy",
        "news_age_label": "3h",
    }
    row = alerts_activity._row_from_news_event(raw)
    assert row["player_id"] == "11604"
    assert row["source_url"] == "https://example.com/tracy"
    html = alerts_activity_ui.timeline_row_html(row)
    assert "target='_blank'" in html
    assert "noopener noreferrer" in html


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "//example.com", "data:text/html,x"])
def test_alert_source_link_fails_closed(bad: str):
    html = alerts_activity_ui.timeline_row_html({"headline": "Unsafe", "source_url": bad})
    assert "href=" not in html


def test_team_comparison_has_five_explicit_semantic_owners():
    source = (ROOT / "modules" / "league_workspace_ui.py").read_text(encoding="utf-8")
    row = source.split("def team_comparison_row_html", 1)[1].split(
        "def render_team_comparison_board", 1
    )[0]
    for owner in (
        "lead_html",
        "identity_html",
        "dg-team-comparison-state",
        "dg-team-comparison-tendencies",
        "dg-team-comparison-activity",
    ):
        assert owner in row


def test_auto_help_owns_visible_baseweb_wrapper_radius():
    css = (ROOT / "modules" / "desktop_executive_layout_styles.py").read_text(encoding="utf-8")
    assert '[class*="auto_help"] [data-baseweb="popover"]' in css
    assert '[class*="auto_help"] [data-baseweb="button"]' in css
    assert '[class*="what_is_auto"] button' in css
    assert "border-radius: var(--radius-none) !important" in css


def test_waivers_records_context_first_useful_and_workspace_render_stages():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    block = app.split('if current_page == "waivers":', 1)[1].split("# MY TEAM", 1)[0]
    assert '"waivers_context_and_inventory"' in block
    assert '"waivers_first_useful"' in block
    assert '"waivers_workspace_render"' in block
    assert '"waivers_summary_emit"' in block
    assert '"waivers_priority_adds_build"' in block


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
