"""General News feed player-identity surfacing.

coridian_ asked for player photos/cards on News items tied to one clear
player. The general feed (modules.news.general_news_feed) is RSS-sourced
and never carried a player_id — unlike the roster-scoped surfaces (my_news
matched_player, mobile Alerts matched_player_id). These tests cover the
fail-closed resolver added to attach that identity (modules.news.
_attach_general_news_player_identity) and the presentation gate in
modules.general_news_ui that only renders a chip when it is present.

coridian_'s follow-up feedback ("all of the news/alerts articles need the
player PFP is not just one") extended coverage one step further: a
two-player story (e.g. a two-player trade) now also resolves, to both
named players (``matched_players``), rather than being discarded the same
way a genuinely player-less, team-level story still is. Three or more
named players stays a hard fail-closed case -- too ambiguous to guess which
two of several are the real subject.
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


def test_two_named_players_resolves_both_identities():
    items = [_article("Davante Adams and DeAndre Hopkins swap teams in trade")]
    out = news._attach_general_news_player_identity(items, PLAYERS)
    assert "matched_player_id" not in out[0]
    pair = out[0]["matched_players"]
    assert len(pair) == 2
    ids = {entry["matched_player_id"] for entry in pair}
    assert ids == {"2133", "1426"}
    by_id = {entry["matched_player_id"]: entry for entry in pair}
    assert by_id["2133"]["matched_player"] == "Davante Adams"
    assert by_id["2133"]["matched_player_position"] == "WR"
    assert by_id["2133"]["matched_player_team"] == "LAR"
    # Hopkins' fixture row carries no team -- left unset, not fabricated.
    assert "matched_player_team" not in by_id["1426"]


def test_three_named_players_fail_closed_to_no_identity():
    items = [
        _article(
            "Justin Jefferson, Davante Adams, and DeAndre Hopkins all "
            "feature in blockbuster three-team trade talks"
        )
    ]
    out = news._attach_general_news_player_identity(items, PLAYERS)
    assert "matched_player_id" not in out[0]
    assert "matched_players" not in out[0]


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


_TWO_PLAYER_ITEM = {
    "title": "Davante Adams and DeAndre Hopkins swap teams in trade",
    "matched_players": [
        {
            "matched_player": "Davante Adams",
            "matched_player_id": "2133",
            "matched_player_position": "WR",
            "matched_player_team": "LAR",
        },
        {
            "matched_player": "DeAndre Hopkins",
            "matched_player_id": "1426",
            "matched_player_position": "WR",
        },
    ],
}


def test_two_player_identity_renders_both_chips_stacked():
    html = general_news_ui._news_two_player_identity_html(_TWO_PLAYER_ITEM)
    assert "news-card-identity-pair" in html
    assert "data-player-id='2133'" in html
    assert "data-player-id='1426'" in html
    assert "Davante" in html and "Adams" in html
    assert "DeAndre" in html and "Hopkins" in html
    # Each chip is the same identity primitive the single-player case uses.
    assert html.count("dg-compact-asset") >= 2


def test_two_player_identity_returns_empty_for_malformed_or_missing_pair():
    assert general_news_ui._news_two_player_identity_html({}) == ""
    assert general_news_ui._news_two_player_identity_html({"matched_players": []}) == ""
    assert general_news_ui._news_two_player_identity_html({"matched_players": [{"matched_player_id": "1"}]}) == ""
    assert (
        general_news_ui._news_two_player_identity_html(
            {"matched_players": [{"matched_player_id": "1"}, {}]}
        )
        == ""
    )


def test_news_identity_html_dispatches_single_vs_pair_vs_none():
    single_item = {
        "matched_player_id": "6794",
        "matched_player": "Justin Jefferson",
        "matched_player_position": "WR",
        "matched_player_team": "MIN",
    }
    assert "news-card-identity-pair" not in general_news_ui._news_identity_html(single_item)
    assert "data-player-id='6794'" in general_news_ui._news_identity_html(single_item)
    assert "news-card-identity-pair" in general_news_ui._news_identity_html(_TWO_PLAYER_ITEM)
    assert general_news_ui._news_identity_html({"title": "Team fires offensive coordinator"}) == ""


def test_news_item_card_renders_both_chips_for_a_two_player_item(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(general_news_ui.st, "markdown", lambda html, **_kwargs: captured.append(html))

    general_news_ui.render_news_item_card(_TWO_PLAYER_ITEM, 0)
    assert "news-card-identity" in captured[0]
    assert "news-card-identity-pair" in captured[0]
    assert "data-player-id='2133'" in captured[0]
    assert "data-player-id='1426'" in captured[0]


def test_resolve_article_player_identities_handles_zero_one_two_and_three_plus():
    from modules import news_intelligence

    name_index = news_intelligence.canonical_player_name_index(PLAYERS)

    none_item = _article("Team fires offensive coordinator after bye week")
    assert news_intelligence.resolve_article_player_identities(none_item, player_name_to_id=name_index) == []

    one_item = _article("Justin Jefferson downgraded to out after practice report")
    one = news_intelligence.resolve_article_player_identities(one_item, player_name_to_id=name_index)
    assert one == [("Justin Jefferson", "6794")]

    two_item = _article("Davante Adams and DeAndre Hopkins swap teams in trade")
    two = news_intelligence.resolve_article_player_identities(two_item, player_name_to_id=name_index)
    assert set(two) == {("Davante Adams", "2133"), ("Deandre Hopkins", "1426")}

    three_item = _article(
        "Justin Jefferson, Davante Adams, and DeAndre Hopkins all feature in "
        "blockbuster three-team trade talks"
    )
    assert (
        news_intelligence.resolve_article_player_identities(three_item, player_name_to_id=name_index)
        == []
    )

    # max_candidates=1 reduces to the same single-match-only contract
    # resolve_article_player_identity's own free-text scan uses.
    assert (
        news_intelligence.resolve_article_player_identities(
            two_item, player_name_to_id=name_index, max_candidates=1
        )
        == []
    )
