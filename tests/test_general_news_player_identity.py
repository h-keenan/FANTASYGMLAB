"""General News feed player-identity surfacing.

coridian_ asked for player photos/cards on News items tied to one clear
player. The general feed (modules.news.general_news_feed) is RSS-sourced
and never carried a player_id — unlike the roster-scoped surfaces (my_news
matched_player, mobile Alerts matched_player_id). These tests cover the
fail-closed resolver added to attach that identity (modules.news.
_attach_general_news_player_identity) and the presentation gate in
modules.general_news_ui that only renders a chip when it is present.
"""

from __future__ import annotations

import pandas as pd

from modules import general_news_ui
from modules import news


def _players_frame(rows):
    return pd.DataFrame(rows)


def _article(title, summary="", **kwargs):
    base = {
        "title": title,
        "summary": summary,
        "description": "",
        "body": "",
        "content": "",
        "link": f"https://example.test/news/{abs(hash(title)) % 10_000_000}",
        "published_ts": 1_700_000_000.0,
    }
    base.update(kwargs)
    return base


PLAYERS = _players_frame(
    [
        {"player_id": "6794", "name": "Justin Jefferson", "position": "WR", "team": "MIN"},
        {"player_id": "2133", "name": "Davante Adams", "position": "WR", "team": "LAR"},
        {"player_id": "1426", "name": "DeAndre Hopkins", "position": "WR", "team": ""},
    ]
)


def test_single_clear_player_resolves_identity_and_lookup_fields():
    items = [_article("Justin Jefferson downgraded to out after practice report")]
    out = news._attach_general_news_player_identity(items, PLAYERS)
    assert out[0]["matched_player"] == "Justin Jefferson"
    assert out[0]["matched_player_id"] == "6794"
    assert out[0]["matched_player_position"] == "WR"
    assert out[0]["matched_player_team"] == "MIN"


def test_two_named_players_fail_closed_to_no_identity():
    items = [_article("Davante Adams and DeAndre Hopkins swap teams in trade")]
    out = news._attach_general_news_player_identity(items, PLAYERS)
    assert "matched_player_id" not in out[0]


def test_team_level_story_has_no_identity():
    items = [_article("Team fires offensive coordinator after bye week")]
    out = news._attach_general_news_player_identity(items, PLAYERS)
    assert "matched_player_id" not in out[0]


def test_empty_players_frame_is_a_no_op():
    items = [_article("Justin Jefferson downgraded to out after practice report")]
    out = news._attach_general_news_player_identity(items, pd.DataFrame())
    assert "matched_player_id" not in out[0]
    out_none = news._attach_general_news_player_identity(items, None)
    assert "matched_player_id" not in out_none[0]


def test_general_news_feed_accepts_players_df_kwarg_without_it(monkeypatch):
    # general_news_feed must keep working exactly as before when callers
    # (e.g. a guest session with no league selected, or an older caller)
    # don't pass players_df at all.
    monkeypatch.setattr(news, "enriched_news_pool", lambda: [])
    assert news.general_news_feed(5) == []


def test_identity_chip_renders_only_when_resolved():
    resolved_item = {
        "matched_player_id": "6794",
        "matched_player": "Justin Jefferson",
        "matched_player_position": "WR",
        "matched_player_team": "MIN",
    }
    html = general_news_ui._news_identity_chip_html(resolved_item)
    assert "data-player-id='6794'" in html
    assert "Justin" in html and "Jefferson" in html
    # Identity-only: no value/score chip, and never the raw h3 tag that
    # leaks Streamlit's native heading size elsewhere in the app.
    assert "dg-compact-asset-value" not in html
    assert "<h3" not in html

    assert general_news_ui._news_identity_chip_html({}) == ""
    assert general_news_ui._news_identity_chip_html({"title": "no player here"}) == ""


def test_news_item_card_includes_identity_row_only_for_resolved_item(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(general_news_ui.st, "markdown", lambda html, **_kwargs: captured.append(html))

    general_news_ui.render_news_item_card(
        {
            "title": "Justin Jefferson downgraded to out",
            "matched_player_id": "6794",
            "matched_player": "Justin Jefferson",
            "matched_player_position": "WR",
            "matched_player_team": "MIN",
        },
        0,
    )
    assert "news-card-identity" in captured[0]
    assert "data-player-id='6794'" in captured[0]

    captured.clear()
    general_news_ui.render_news_item_card({"title": "Team fires offensive coordinator"}, 1)
    assert "news-card-identity" not in captured[0]
