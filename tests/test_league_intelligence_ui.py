from unittest.mock import Mock, patch

from modules import league_intelligence_ui
from tests.test_league_intelligence import NOW, build, news


def test_item_html_is_escaped_accessible_and_uses_canonical_dense_anatomy():
    item = build(
        [
            {
                **news("My Player", NOW - 60, reason="injury/status"),
                "title": "<script>unsafe</script>",
                "summary": "<b>summary</b>",
            }
        ]
    ).items[0]
    html = league_intelligence_ui.intelligence_item_html(
        item,
        player_html="<article class='dg-football-asset'>Player</article>",
    )
    assert "<script>" not in html
    assert "<b>summary</b>" not in html
    assert "&lt;script&gt;" in html
    assert "dg-dense-row" in html
    assert "dg-dense-identity__primary" in html
    assert "Injury Monitor" in html
    assert "Owned by you" in html
    assert "dg-dense-exception" in html
    assert "dg-intelligence-item__summary" not in html
    assert "data-player-id=" in html
    assert html.index("dg-dense-identity") < html.index("dg-dense-metric")
    assert html.index("dg-dense-metric") < html.index("dg-dense-status")
    assert html.index("dg-dense-status") < html.index("dg-dense-meta")
    assert html.index("dg-dense-meta") < html.index("dg-dense-exception")


def test_renderer_opens_canonical_quick_view_for_clicked_player():
    feed = build([news("My Player", NOW - 60)])
    open_quick_view = Mock()
    player_builder = Mock(return_value="<article class='dg-football-asset'>Player</article>")
    with (
        patch.object(
            league_intelligence_ui,
            "render_tappable_player_html",
            create=True,
        ),
        patch.object(league_intelligence_ui.st, "markdown"),
        patch.object(league_intelligence_ui.st, "button"),
        patch.object(league_intelligence_ui.st, "session_state", {}),
    ):
        league_intelligence_ui.render_league_intelligence_feed(
            feed,
            score_field="value_score",
            score_label="Value",
            player_card_builder=player_builder,
            render_tappable_player_html=lambda **_kwargs: "mine",
            open_player_quick_view=open_quick_view,
        )
    open_quick_view.assert_called_once()
    assert open_quick_view.call_args.args[0] == "mine"
    assert open_quick_view.call_args.kwargs["source_label"] == "News"


def test_renderer_lazily_omits_explanation_while_collapsed():
    feed = build([news("My Player", NOW - 60)])
    markdown = Mock()
    with (
        patch.object(league_intelligence_ui.st, "markdown", markdown),
        patch.object(league_intelligence_ui.st, "button"),
        patch.object(league_intelligence_ui.st, "session_state", {}),
    ):
        league_intelligence_ui.render_league_intelligence_feed(
            feed,
            score_field="value_score",
            score_label="Value",
            player_card_builder=lambda *_args, **_kwargs: "",
            render_tappable_player_html=lambda **_kwargs: "",
            open_player_quick_view=lambda *_args, **_kwargs: None,
        )
    assert not any("dg-intelligence-explanation" in str(call.args[0]) for call in markdown.call_args_list)


def test_first_intelligence_item_is_visually_primary_without_removing_items():
    feed = build([news("My Player", NOW - 60), news("Other Player", NOW - 120)])
    rendered = []
    with (
        patch.object(league_intelligence_ui.st, "markdown"),
        patch.object(league_intelligence_ui.st, "button"),
        patch.object(league_intelligence_ui.st, "session_state", {}),
    ):
        league_intelligence_ui.render_league_intelligence_feed(
            feed,
            score_field="value_score",
            score_label="Value",
            player_card_builder=lambda *_args, **_kwargs: "",
            render_tappable_player_html=lambda **kwargs: rendered.append(kwargs["html"]) or "",
            open_player_quick_view=lambda *_args, **_kwargs: None,
        )
    assert len(rendered) == len(feed.items)
    assert "dg-intelligence-item--primary" in rendered[0]
    assert "dg-dense-row" in rendered[0]
    assert all("dg-intelligence-item--primary" not in item for item in rendered[1:])
