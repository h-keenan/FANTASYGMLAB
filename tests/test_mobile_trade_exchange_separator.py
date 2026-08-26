from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from modules import trade_hub_ui
from modules.trade_detail_styles import TRADE_DETAIL_CSS


ROOT = Path(__file__).resolve().parents[1]


def _player(player_id: str, name: str) -> dict:
    return {
        "asset_type": "player",
        "player_id": player_id,
        "name": name,
        "position": "WR",
        "team": "BUF",
        "value": 3000,
    }


def _pick(label: str) -> dict:
    return {"asset_type": "pick", "name": label, "value": 1200}


def _detail_html(send_assets: list[dict], receive_assets: list[dict]) -> str:
    idea = {
        "partner_roster_id": "partner-7",
        "partner_team_name": "Lakefront Franchise",
        "tag": "Review Package",
        "my_score": sum(int(asset["value"]) for asset in send_assets),
        "their_score": sum(int(asset["value"]) for asset in receive_assets),
        "trade_gain": 0,
        "fit_grade": "Strong",
        "market_realism_label": "Plausible",
        "trade_confidence_label": "Medium",
        "send_assets": send_assets,
        "receive_assets": receive_assets,
        "reasoning_summary": "Fixture rationale.",
    }
    rendered: list[str] = []

    def dialog(*_args, **_kwargs):
        return lambda fn: fn

    with (
        patch.object(
            trade_hub_ui,
            "TRADE_SUMMARY_TAP_COMPONENT",
            lambda **_kwargs: type("Result", (), {"clicked": {"open": True}})(),
        ),
        patch.object(trade_hub_ui.st, "session_state", {}),
        patch.object(trade_hub_ui.st, "dialog", dialog),
        patch.object(trade_hub_ui, "render_trade_html_with_player_taps", side_effect=lambda html, *_args, **_kwargs: rendered.append(html) or ""),
        patch.object(trade_hub_ui, "render_html_fragment"),
        patch.object(trade_hub_ui.st, "button", return_value=False),
    ):
        trade_hub_ui.render_trade_idea_card(
            idea,
            0,
            key_prefix="mobile-exchange",
            format_score=str,
            tidy_label=str,
            trade_target_reason=lambda _: "Why it helps.",
            trade_partner_reason=lambda _: "Why they consider it.",
            trade_confidence_reason=lambda _: "Confidence context.",
            trade_value_verdict=lambda _: "Fair",
            trade_display_confidence_label=lambda _: "Medium",
            injury_display_context=lambda _: {"risk": False},
            glyph_chip_html=lambda *_args: "",
            assets_html=lambda assets: "".join(f"<div>{asset['name']}</div>" for asset in assets),
            render_tappable_player_html=Mock(),
            open_player_quick_view=Mock(),
        )
    return next(html for html in rendered if "trade-detail-modal" in html)


@pytest.mark.parametrize(
    ("send_assets", "receive_assets"),
    [
        ([_player("p1", "Send One")], [_player("p2", "Receive One")]),
        ([_player("p1", "Send One"), _pick("2027 Round 2")], [_player("p2", "Receive One")]),
        ([_player("p1", "Send One"), _pick("2027 Round 1"), _pick("2028 Round 2")], [_player("p2", "Receive One"), _player("p3", "Receive Two")]),
    ],
)
def test_real_review_package_uses_one_passive_exchange_separator(send_assets, receive_assets):
    html = _detail_html(send_assets, receive_assets)
    assert html.count('class="trade-vs trade-review-exchange-separator"') == 1
    assert 'role="separator"' in html
    assert "<button" not in html
    assert html.index("Lakefront Franchise receives") < html.index(">FOR<span") < html.index("Proposing roster receives")
    for asset in send_assets + receive_assets:
        assert asset["name"] in html


def test_mobile_separator_is_compact_and_desktop_grid_contract_is_preserved():
    compact = "".join(TRADE_DETAIL_CSS.split())
    mobile = compact.split("@media(max-width:700px)", 1)[1].split("@media(min-width:1280px)", 1)[0]
    selector = ".trade-detail-modal.trade-review-exchange-separator"
    assert "grid-template-columns:minmax(0,1fr)automax" not in compact
    assert ".trade-detail-modal.trade-matchup-compact{display:flex!important;flex-direction:column" in mobile
    assert selector + "{align-self:center;background:transparent;border:0;gap:0;" in mobile
    assert "min-height:0" in mobile
    assert "width:auto" in mobile
    assert selector + "::before," + selector + "::after{content:none;display:none" in mobile
    assert "min-height:var(--touch-target-min)" not in mobile.split(selector + "{", 1)[1].split("}", 1)[0]
    assert "width:100%" not in mobile.split(selector + "{", 1)[1].split("}", 1)[0]
