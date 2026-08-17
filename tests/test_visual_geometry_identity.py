"""Visual geometry contracts for compact player/pick identity and packages."""

from __future__ import annotations

from pathlib import Path

from modules import compact_fantasy_assets as compact
from modules import trade_hub_ui
from modules.trade_detail_styles import TRADE_DETAIL_CSS


ROOT = Path(__file__).resolve().parents[1]


def _player(**kwargs):
    base = {
        "asset_type": "player",
        "player_id": "6794",
        "name": "Tyrone Tracy",
        "position": "RB",
        "team": "NYG",
        "age": 26,
        "score": 3100,
    }
    base.update(kwargs)
    return base


def _pick(**kwargs):
    base = {
        "asset_type": "pick",
        "label": "2027 Round 3",
        "name": "2027 Round 3",
        "season": 2027,
        "round": 3,
        "score": 1800,
    }
    base.update(kwargs)
    return base


def test_compact_player_identity_uses_fixed_box_and_text_anchor():
    css = compact.COMPACT_FANTASY_ASSET_CSS.replace(" ", "")
    assert "grid-template-columns:var(--size-asset-compact)minmax(0,1fr)max-content" in css
    assert ".dg-compact-asset-copy{align-content:center" in css
    assert "justify-items:start" in css
    html = compact.compact_asset_html(_player())
    assert "dg-compact-asset-avatar" in html
    assert "trade-avatar" not in html
    assert "Tyrone Tracy" in html
    assert "RB · NYG" in html
    assert "dg-compact-asset-copy" in html


def test_compact_pick_plate_shares_player_box_token():
    css = compact.COMPACT_FANTASY_ASSET_CSS.replace(" ", "")
    assert (
        ".dg-compact-asset-avatar,.dg-compact-pick-plate{" in css
        or ".dg-compact-asset-avatar,.dg-compact-pick-plate{" in compact.COMPACT_FANTASY_ASSET_CSS.replace(" ", "")
    )
    assert "height:var(--size-asset-compact);justify-content:center" in css
    html = compact.compact_asset_html(_pick())
    assert "dg-compact-pick-plate" in html
    assert "PICK" in html
    assert "2027 Round 3" in html
    assert "Draft pick" not in html


def test_compact_stack_does_not_claim_full_desktop_width():
    css = compact.COMPACT_FANTASY_ASSET_CSS.replace(" ", "")
    assert ".dg-compact-asset-stack{" in css
    assert "width:max-content" in css
    html = compact.compact_asset_stack_html([_player(), _pick()], show_value=False)
    assert html.count("dg-compact-asset-sep") == 1
    assert "3100" not in html
    assert "1800" not in html


def test_game_plan_trade_visual_is_give_for_get_package():
    html = compact.game_plan_trade_visual_html(
        {
            "value_edge": "+180",
            "send": [_player()],
            "receive": [_player(player_id="8155", name="Pat Bryant", position="WR", team="DEN"), _pick()],
        }
    )
    assert "You give" in html
    assert ">FOR<" in html
    assert "You get" in html
    give_at = html.index("dg-gp-trade-side--give")
    for_at = html.index("dg-gp-trade-for")
    get_at = html.index("dg-gp-trade-side--get")
    assert give_at < for_at < get_at
    css = compact.COMPACT_FANTASY_ASSET_CSS.replace(" ", "")
    assert "grid-template-columns:minmax(0,max-content)autominmax(0,max-content)" in css
    assert "max-width:40rem" in css
    assert "width:max-content" in css
    assert "justify-content:space-between" not in css


def test_trade_summary_package_reuses_compact_identity_without_space_between():
    html = trade_hub_ui._trade_summary_assets_html(
        [_player(), _pick(name="2027 3rd", label="2027 3rd")]
    )
    assert "dg-compact-asset--player" in html
    assert "dg-compact-asset--pick" in html
    assert "trade-avatar" not in html
    css = trade_hub_ui.TRADE_SUMMARY_COMPONENT_CSS
    assert "justify-content: space-between;" not in css.split(".trade-summary-impact-row")[1][:400]
    assert "justify-content: flex-start;" in css
    assert "max-width: min(100%, 42rem);" in css
    assert ".trade-summary-side { align-items: start;" in css
    assert "grid-template-columns: 4.75rem minmax(0, max-content);" in css


def test_review_package_compact_identity_geometry_is_unchanged():
    css = TRADE_DETAIL_CSS
    assert "grid-template-columns: 2.5rem minmax(0, 1fr);" in css
    assert "height: var(--size-asset-compact, 2.25rem);" in css
    assert ".trade-asset-row-compact .trade-asset-name" in css
    source = (ROOT / "modules" / "trade_hub_ui.py").read_text(encoding="utf-8")
    dialog = source[source.index("def _trade_detail_dialog") : source.index("render_trade_idea_player_actions")]
    assert "trade-matchup trade-matchup-compact" in dialog
    assert "You send" in dialog
    assert "You receive" in dialog
    assert "compact_assets_html or assets_html" in dialog


def test_dashboard_secondary_cards_share_game_plan_padding_owner():
    css = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert ".dg-game-plan-card{" in css.replace("\n", "") or ".dg-game-plan-card{" in css
    assert "gap:var(--space-sm)" in css.replace(" ", "")
    assert "compact_fantasy_assets.COMPACT_FANTASY_ASSET_CSS" in css
    assert "watch_attention_html" in css
    assert "size=\"compact\"" in css or "size='compact'" in css
    assert "dg-gp-identity-row" in css
