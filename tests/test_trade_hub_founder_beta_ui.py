from contextlib import contextmanager
from pathlib import Path

from modules import trade_hub_ui


def _idea(
    *,
    tag="Trade idea",
    confidence="Medium",
    strategy="retool",
    my_player="Send",
    their_player="Get",
    gain=100,
):
    return {
        "partner_roster_id": "2",
        "partner_team_name": "Partner",
        "my_player": my_player,
        "their_player": their_player,
        "my_score": 1000,
        "their_score": 1000 + gain,
        "trade_gain": gain,
        "tag": tag,
        "my_strategy": strategy,
        "partner_strategy": "retool",
        "trade_confidence_label": confidence,
        "market_realism_label": "Plausible",
        "fit_grade": "Solid",
        "send_assets": [{"asset_type": "player", "player_id": "1", "name": my_player}],
        "receive_assets": [{"asset_type": "player", "player_id": "2", "name": their_player}],
    }


def test_trade_hub_sections_preserve_existing_order_and_headline():
    headline = _idea(tag="Top path", confidence="High", my_player="A")
    contender = _idea(tag="Win-now upgrade", strategy="contender", my_player="B")
    picks = _idea(tag="Add draft capital", my_player="C")
    grouped = trade_hub_ui.group_trade_hub_ideas(
        [headline, contender, picks],
        headline_idea=headline,
    )

    assert list(grouped) == [
        "Headline Recommendation",
        "Contender",
        "Draft Capital",
    ]
    assert grouped["Headline Recommendation"] == [headline]
    assert grouped["Contender"] == [contender]
    assert grouped["Draft Capital"] == [picks]
    assert sum(len(items) for items in grouped.values()) == 3


def test_trade_hub_empty_sections_are_collapsed():
    grouped = trade_hub_ui.group_trade_hub_ideas(
        [_idea(tag="Address roster need")],
    )
    assert list(grouped) == ["Need-Based"]
    assert "Health Relief" not in grouped
    assert "High Confidence" not in grouped


def test_trade_hub_display_categories_do_not_change_scores():
    ideas = [
        _idea(tag="Health relief for injured depth", gain=-40),
        _idea(tag="Younger age pivot", gain=25),
        _idea(tag="Rebuild value path", gain=10),
        _idea(tag="Normal path", confidence="High", gain=5),
    ]
    before = [(idea["my_score"], idea["their_score"], idea["trade_gain"]) for idea in ideas]
    grouped = trade_hub_ui.group_trade_hub_ideas(ideas)
    after = [
        (idea["my_score"], idea["their_score"], idea["trade_gain"])
        for section in grouped.values()
        for idea in section
    ]
    assert sorted(after) == sorted(before)
    assert "Health Relief" in grouped
    assert "Age Optimization" in grouped
    assert "Rebuild" in grouped
    assert "High Confidence" in grouped


def test_compact_trade_card_is_summary_first(monkeypatch):
    captured = {"html": "", "expanders": []}

    def capture_html(html, assets, **kwargs):
        captured["html"] = html

    def capture_summary(**kwargs):
        captured["html"] = kwargs["data"]["html"]
        return type("Result", (), {"clicked": None})()

    @contextmanager
    def fake_expander(label, **kwargs):
        captured["expanders"].append(label)
        yield

    monkeypatch.setattr(trade_hub_ui, "TRADE_SUMMARY_TAP_COMPONENT", capture_summary)
    monkeypatch.setattr(trade_hub_ui.st, "expander", fake_expander)
    monkeypatch.setattr(trade_hub_ui.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(trade_hub_ui.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(trade_hub_ui.st, "warning", lambda *args, **kwargs: None)

    idea = _idea(tag="Compact recommendation", gain=125)
    idea["_display_section"] = "Headline Recommendation"
    trade_hub_ui.render_trade_idea_card(
        idea,
        0,
        format_score=lambda value: str(value),
        tidy_label=str.title,
        trade_target_reason=lambda value: "Target fits the roster.",
        trade_partner_reason=lambda value: "Partner has a matching need.",
        trade_confidence_reason=lambda value: "Value and fit clear the bar.",
        trade_value_verdict=lambda value: "Fair",
        trade_display_confidence_label=lambda value: "High",
        injury_display_context=lambda value: {"risk": False},
        glyph_chip_html=lambda label, tone: f"<span>{label}</span>",
        assets_html=lambda assets: "<div class='assets'>Assets</div>",
    )

    assert "trade-summary-card" in captured["html"]
    assert "trade-summary-package" in captured["html"]
    assert "trade-summary-value" in captured["html"]
    assert 'trade-summary-side-label">Sending' in captured["html"]
    assert 'trade-summary-side-label">Receiving' in captured["html"]
    assert "trade-summary-asset-chip" in captured["html"]
    assert "Send" in captured["html"]
    assert "Get" in captured["html"]
    assert "trade-avatar" not in captured["html"]
    assert "football-player-asset" not in captured["html"]
    assert "trade-matchup" not in captured["html"]
    assert captured["expanders"] == []


def test_trade_hub_css_is_sticky_compact_and_mobile_contained():
    css = Path("modules/app_styles.py").read_text(encoding="utf-8")
    assert "st-key-trade_hub_board_section_" not in css
    assert ".trade-idea-card-compact" not in css
    assert ".trade-idea-card" in css
    assert "max-width: 100%;" in css
    assert ".trade-matchup-compact" in css
    assert "grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);" in css
    assert "display: block;" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ".trade-summary-category" in css


def test_trade_hub_route_renders_only_active_cached_section():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "group_trade_hub_ideas(" in source
    assert "annotate_trade_hub_feed_categories(" in source
    assert "ranked_feed[:visible_count]" in source
    assert "render_trade_hub_section_filter(" not in source
    assert "cached_trade_ideas(" in source
    assert "Switching sections reuses the cached board." not in source


def test_trade_hub_empty_state_explains_why_and_next_step():
    copy = trade_hub_ui.trade_hub_empty_state_copy("Draft Capital")
    assert "draft capital" in copy["title"].lower()
    assert "fair enough for both sides" in copy["reason"].lower()
    assert "strategy focus" in copy["suggestion"].lower()
