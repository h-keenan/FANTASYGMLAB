from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import Mock, patch

from modules import trade_hub_ui


def _idea(partner: str, *, send_count: int = 1, receive_count: int = 1) -> dict:
    return {
        "partner_roster_id": partner,
        "partner_team_name": f"Team {partner}",
        "tag": "Upgrade the starting lineup",
        "my_score": 5000,
        "their_score": 5200,
        "trade_gain": 200,
        "fit_grade": "Strong",
        "market_realism_label": "Plausible",
        "trade_confidence_label": "Medium",
        "send_assets": [
            {"asset_type": "player", "player_id": f"send-{partner}-{index}", "name": f"Send {index}"}
            for index in range(send_count)
        ],
        "receive_assets": [
            {"asset_type": "player", "player_id": f"get-{partner}-{index}", "name": f"Get {index}"}
            for index in range(receive_count)
        ],
        "reasoning_summary": "Adds a stronger weekly starter without abandoning roster balance.",
    }


def _render(
    idea: dict,
    *,
    button: Mock,
    summary: Mock,
    detail: Mock,
    idea_idx: int = 0,
) -> None:
    def summary_component(**kwargs):
        summary(kwargs["data"]["html"])
        return type(
            "Result",
            (),
            {"clicked": {"key": kwargs["data"]["key"]} if button.return_value else None},
        )()

    with (
        patch.object(trade_hub_ui, "TRADE_SUMMARY_TAP_COMPONENT", summary_component),
        patch.object(trade_hub_ui, "render_trade_html_with_player_taps", detail),
        patch.object(trade_hub_ui, "render_html_fragment"),
        patch.object(trade_hub_ui.st, "button", button),
        patch.object(trade_hub_ui.st, "dialog", lambda *args, **kwargs: lambda fn: fn),
        patch.object(trade_hub_ui.st, "warning"),
    ):
        trade_hub_ui.render_trade_idea_card(
            idea,
            idea_idx,
            key_prefix="trade_hub_headline",
            format_score=str,
            tidy_label=str,
            trade_target_reason=lambda current: trade_hub_ui.trade_target_reason(
                current,
                recommendation_reason_text=lambda value, limit: str(value)[:limit],
            ),
            trade_partner_reason=lambda _: "Partner reason.",
            trade_confidence_reason=lambda _: "Confidence reason.",
            trade_value_verdict=lambda _: "Fair",
            trade_display_confidence_label=lambda _: "Medium",
            injury_display_context=lambda _: {"risk": False},
            glyph_chip_html=lambda *args: "",
            assets_html=lambda assets: "<div class='full-assets'>Full detail</div>",
        )


def test_multiple_trade_ideas_have_unique_page_scoped_component_keys():
    first = _idea("a")
    second = _idea("b")
    first_key = trade_hub_ui.trade_summary_key(first, page_context="trade_hub_headline")
    second_key = trade_hub_ui.trade_summary_key(second, page_context="trade_hub_headline")

    assert first_key != second_key
    assert first_key != trade_hub_ui.trade_summary_key(first, page_context="trade_return_explorer")

    components = Mock(return_value=False)
    first_summary = Mock()
    second_summary = Mock()
    _render(first, button=components, summary=first_summary, detail=Mock())
    _render(second, button=components, summary=second_summary, detail=Mock())
    keys = [
        html.call_args.args[0].split('data-trade-summary-key="', 1)[1].split('"', 1)[0]
        for html in (first_summary, second_summary)
    ]
    assert len(keys) == len(set(keys)) == 2
    assert all(key.startswith("trade_summary_") for key in keys)


def test_duplicate_trade_payloads_still_receive_unique_instance_keys():
    duplicate = _idea("same")
    first_summary = Mock()
    second_summary = Mock()
    _render(
        duplicate,
        idea_idx=0,
        button=Mock(return_value=False),
        summary=first_summary,
        detail=Mock(),
    )
    _render(
        dict(duplicate),
        idea_idx=1,
        button=Mock(return_value=False),
        summary=second_summary,
        detail=Mock(),
    )
    first_key = first_summary.call_args.args[0].split('data-trade-summary-key="', 1)[1].split('"', 1)[0]
    second_key = second_summary.call_args.args[0].split('data-trade-summary-key="', 1)[1].split('"', 1)[0]
    assert first_key != second_key


def test_multiple_assets_remain_names_only_in_collapsed_summary():
    summary = Mock()
    _render(
        _idea("multi", send_count=2, receive_count=3),
        button=Mock(return_value=False),
        summary=summary,
        detail=Mock(),
    )
    html = summary.call_args.args[0]
    assert all(name in html for name in ("Send 0", "Send 1", "Get 0", "Get 1", "Get 2"))
    assert html.count("trade-summary-asset-chip") == 5
    assert "loading='lazy'" in html
    assert "dg-player-headshot" in html
    assert "full-assets" not in html
    assert "trade-avatar" not in html
    assert "football-player-asset" not in html


def test_tapping_one_summary_opens_only_its_trade_detail():
    summary = Mock()
    detail = Mock()
    _render(
        _idea("selected"),
        button=Mock(return_value=True),
        summary=summary,
        detail=detail,
    )
    assert detail.call_count == 1
    detail_html = detail.call_args.args[0]
    assert "Team selected" in detail_html
    assert "full-assets" in detail_html
    assert "trade-detail-modal" in detail_html


def test_detail_content_remains_lazy_until_summary_is_tapped():
    detail = Mock()
    _render(
        _idea("lazy"),
        button=Mock(return_value=False),
        summary=Mock(),
        detail=detail,
    )
    detail.assert_not_called()


def test_mobile_contract_is_compact_from_320_through_430_pixels():
    css = trade_hub_ui.TRADE_SUMMARY_COMPONENT_CSS
    mobile = css[css.index("@media (max-width: 430px)") :]
    assert "min-height: 0;" in mobile
    assert "grid-template-columns: minmax(0, 1fr);" in mobile
    assert "height: 2.75rem;" in mobile
    assert "width: 2.75rem;" in mobile
    assert ".trade-summary-signals { display: none; }" in mobile
    assert ".trade-summary-category," in mobile
    assert ".trade-summary-side-label," in mobile
    assert ".trade-summary-why," in mobile
    assert "display: none;" in mobile
    narrow = mobile[mobile.index("@media (max-width: 340px)") :]
    assert "grid-template-columns: minmax(0, 1fr);" in narrow
    assert ".trade-summary-title { font-size: var(--font-size-body); }" in narrow
    assert "white-space: normal;" in css
    assert "text-overflow: ellipsis;" not in css
    assert "max-width: 100%;" in css
    assert "width: 100%;" in css
    assert "white-space: nowrap;" in css
    assert "overflow-wrap: break-word;" in css
    assert "min-height: var(--touch-target-min);" in css
    assert not re.search(r"font-size:\s*(?:[0-9]|10)px", css)
    assert "writing-mode" not in css


def test_mobile_target_widths_share_the_same_full_width_card_contract():
    css = trade_hub_ui.TRADE_SUMMARY_COMPONENT_CSS
    assert all(width <= 430 for width in (320, 390, 430))
    assert "@media (max-width: 430px)" in css
    assert ".trade-summary-card { gap: 0.22rem; min-height: 0; padding: 0.45rem 0.65rem; }" in css


def test_isolated_trade_component_receives_design_token_styles():
    css = trade_hub_ui.TRADE_SUMMARY_COMPONENT_CSS
    assert "DynastyGM semantic design tokens" in css
    assert ".trade-summary-card" in css
    assert "border-left: var(--border-width-semantic) solid var(--color-information);" in css
    assert "font-size: var(--font-size-display);" in css
    assert "@media (max-width: 430px)" in css
    assert "flex: 0 0 3.25rem;" in css
    assert "max-width: 100%;" in css
    assert "width: 100%;" in css


def test_summary_component_card_is_pointer_and_keyboard_tappable():
    source = Path("modules/trade_hub_ui.py").read_text(encoding="utf-8")
    component = source[source.index("TRADE_SUMMARY_TAP_COMPONENT") - 600 : source.index("TRADE_STRATEGY_OPTIONS")]
    assert 'card.setAttribute("role", "button")' in component
    assert 'card.setAttribute("tabindex", "0")' in component
    assert 'event.key !== "Enter" && event.key !== " "' in component
    assert 'setTriggerValue("clicked"' in component


def test_pick_summary_uses_visual_pick_marker_without_detail_fields():
    html = trade_hub_ui._trade_summary_assets_html(
        [{"asset_type": "pick", "name": "2027 1st", "score": 4200, "round": 1}]
    )
    assert "trade-summary-avatar--pick" in html
    assert "2027 1st" in html
    assert "4200" not in html
    assert "round" not in html.lower()


def test_summary_identity_is_stable_across_cached_and_uncached_copies():
    idea = _idea("stable", send_count=2, receive_count=2)
    assert trade_hub_ui.trade_summary_key(
        idea, page_context="trade_hub"
    ) == trade_hub_ui.trade_summary_key(dict(idea), page_context="trade_hub")


def test_summary_uses_one_sentence_and_omits_repeated_section_kicker():
    idea = _idea("concise")
    idea["reasoning_summary"] = (
        "Adds a reliable weekly starter. Full partner and confidence reasoning stays in detail."
    )
    summary = Mock()
    _render(
        idea,
        button=Mock(return_value=False),
        summary=summary,
        detail=Mock(),
    )

    html = summary.call_args.args[0]
    assert "Adds a reliable weekly starter." in html
    assert "Full partner and confidence reasoning" not in html
    assert "trade-summary-kicker" not in html
