"""modules.gm_plan_ui — Trade Opportunities / Roster Construction visual
identity (avatar + tier, in place of a plain-text-only treatment).

Mirrors the established pattern modules.daily_gm_briefing_ui already uses
for Dashboard's Top Priority trade card and Watch card: real
modules.compact_fantasy_assets visuals built from the SAME raw
send_assets/receive_assets/injured_players dicts modules.gm_plan already
carries, not a new design.
"""

from __future__ import annotations

from unittest.mock import Mock

from modules import gm_plan_ui


def _trade_item(**overrides):
    item = {
        "partner_team_name": "Epstein's List",
        "my_player": "Cade Otton",
        "their_player": "Tony Pollard",
        "their_player_injury_display": "",
        "rationale": (
            "This trade fits your declared rebuild stance because Tony Pollard "
            "offers a clearer path to starter touches than Cade Otton behind a "
            "crowded tight end room, and the extra draft capital lets you keep "
            "optionality into next year's class while your competing window stays open."
        ),
        "trade_confidence_label": "Strong",
        "send_assets": [
            {
                "asset_type": "player",
                "player_id": "my-1",
                "name": "Cade Otton",
                "position": "TE",
                "team": "TB",
            }
        ],
        "receive_assets": [
            {
                "asset_type": "player",
                "player_id": "their-1",
                "name": "Tony Pollard",
                "position": "RB",
                "team": "TEN",
            }
        ],
        "trade_gain": 237,
    }
    item.update(overrides)
    return item


# --- _trade_item_text --------------------------------------------------------


def test_trade_item_headline_names_partner_not_player_arrow_when_visual_present():
    # Players are already shown via the avatar row (_trade_item_visual_html);
    # the headline must not also restate "Player A -> Player B" in plain text.
    headline, _detail, _risk = gm_plan_ui._trade_item_text(_trade_item())
    assert "Epstein's List" in headline
    assert "Cade Otton" not in headline
    assert "Tony Pollard" not in headline


def test_trade_item_headline_falls_back_to_player_arrow_without_assets():
    item = _trade_item(send_assets=[], receive_assets=[])
    headline, _detail, _risk = gm_plan_ui._trade_item_text(item)
    assert "Cade Otton" in headline
    assert "Tony Pollard" in headline


def test_trade_item_detail_is_trimmed_to_a_headline_length_verdict():
    headline, detail, _risk = gm_plan_ui._trade_item_text(_trade_item())
    assert len(detail) <= 150
    assert detail  # never silently empties a real rationale


def test_trade_item_marks_risk_when_receive_side_is_injured():
    item = _trade_item(their_player_injury_display="Torn ACL")
    _headline, _detail, is_risk = gm_plan_ui._trade_item_text(item)
    assert is_risk is True


# --- _trade_item_visual_html --------------------------------------------------


def test_trade_item_visual_html_renders_both_sides_with_avatars():
    html = gm_plan_ui._trade_item_visual_html(_trade_item())
    assert "Cade Otton" in html
    assert "Tony Pollard" in html
    assert "You give" in html
    assert "You get" in html
    assert "dg-compact-asset-avatar" in html


def test_trade_item_visual_html_shows_positive_value_edge():
    html = gm_plan_ui._trade_item_visual_html(_trade_item(trade_gain=237))
    assert "+237" in html


def test_trade_item_visual_html_shows_even_for_zero_gain():
    html = gm_plan_ui._trade_item_visual_html(_trade_item(trade_gain=0))
    assert "Even" in html


def test_trade_item_visual_html_empty_when_no_assets():
    html = gm_plan_ui._trade_item_visual_html(_trade_item(send_assets=[], receive_assets=[]))
    assert html == ""


def test_trade_item_visual_html_uses_the_site_wide_position_then_team_identity():
    """Site-wide card audit (coridian_, 2026-10-14): GM Plan's own Trade
    Opportunities card was the one give/get trade teaser still defaulting to
    the plain-text "POSITION · TEAM · Age" meta line while Dashboard's Top
    Priority and League Movement cards (the SAME game_plan_trade_visual_html/
    game_plan_top_priority_trade_html functions, same PR) already render a
    colored position pill ahead of the team text (position_pill=True) with a
    tier-colored avatar ring (avatar_ring=True) — the format mobile's own
    PlayerIdentityRow.tsx established (colored PositionBadge, then team,
    never a plain-text position). This card must match that now-canonical
    treatment instead of staying the one outlier.
    """

    html = gm_plan_ui._trade_item_visual_html(_trade_item())
    assert "dg-compact-asset-meta--pill" in html
    assert "player-position-badge" in html
    assert "dg-tier-frame--ring" in html


# --- tap-through -------------------------------------------------------------


def test_render_focus_item_card_routes_trade_card_through_tap_grid():
    tap_renderer = Mock(return_value="their-1")
    open_quick_view = Mock()
    gm_plan_ui._render_focus_item_card(
        "Trade idea: Epstein's List",
        "Strong fit",
        is_risk=False,
        concept="trade",
        visual_html="<div class='dg-gp-trade-visual'>visual</div>",
        trade_assets=[
            {"asset_type": "player", "player_id": "my-1", "name": "Cade Otton"},
            {"asset_type": "player", "player_id": "their-1", "name": "Tony Pollard"},
        ],
        key_prefix="gm_plan_trade_card_0_0",
        render_tappable_player_html=tap_renderer,
        open_player_quick_view=open_quick_view,
    )
    tap_renderer.assert_called_once()
    open_quick_view.assert_called_once()
    assert open_quick_view.call_args.args[0] == "their-1"


def test_render_focus_item_card_ignores_unrelated_click_results():
    tap_renderer = Mock(return_value="")
    open_quick_view = Mock()
    gm_plan_ui._render_focus_item_card(
        "Trade idea: Epstein's List",
        "Strong fit",
        is_risk=False,
        concept="trade",
        visual_html="<div class='dg-gp-trade-visual'>visual</div>",
        trade_assets=[
            {"asset_type": "player", "player_id": "my-1", "name": "Cade Otton"},
        ],
        key_prefix="gm_plan_trade_card_0_0",
        render_tappable_player_html=tap_renderer,
        open_player_quick_view=open_quick_view,
    )
    tap_renderer.assert_called_once()
    open_quick_view.assert_not_called()


def test_render_focus_item_card_falls_back_without_trade_assets():
    # A non-trade card (e.g. Where You Stand's rank rows) has no trade_assets
    # and must render without attempting a tap grid at all.
    tap_renderer = Mock()
    open_quick_view = Mock()
    gm_plan_ui._render_focus_item_card(
        "Roster Power: 3 of 10",
        "",
        is_risk=False,
        concept="rankings",
        visual_html="",
        trade_assets=None,
        key_prefix="gm_plan_trade_card_0_1",
        render_tappable_player_html=tap_renderer,
        open_player_quick_view=open_quick_view,
    )
    tap_renderer.assert_not_called()
    open_quick_view.assert_not_called()


def test_render_focus_item_card_falls_back_without_tap_callables():
    # Trade assets present but caller hasn't wired the tap callables — must
    # still render without raising and without fabricating a click.
    gm_plan_ui._render_focus_item_card(
        "Trade idea: Epstein's List",
        "Strong fit",
        is_risk=False,
        concept="trade",
        visual_html="<div class='dg-gp-trade-visual'>visual</div>",
        trade_assets=[{"asset_type": "player", "player_id": "my-1", "name": "Cade Otton"}],
        key_prefix="gm_plan_trade_card_0_0",
        render_tappable_player_html=None,
        open_player_quick_view=None,
    )


# --- _injury_item_visual_html -------------------------------------------------


def test_injury_item_visual_html_renders_real_player_identity():
    item = {
        "label": "Injury Exposure",
        "injury_need_positions": ["TE"],
        "injured_players": [
            {
                "asset_type": "player",
                "player_id": "7",
                "name": "My Player 7",
                "position": "TE",
                "team": "KC",
                "injury_status": "Out",
            }
        ],
    }
    html = gm_plan_ui._injury_item_visual_html(item)
    assert "My Player 7" in html
    assert "dg-compact-asset-avatar" in html


def test_injury_item_visual_html_empty_without_injured_players():
    item = {"label": "Injury Exposure", "injury_need_positions": ["RB"], "injured_players": []}
    assert gm_plan_ui._injury_item_visual_html(item) == ""


# --- _item_visual_html dispatch -----------------------------------------------


def test_item_visual_html_dispatches_trade_items_to_trade_visual():
    html = gm_plan_ui._item_visual_html(_trade_item())
    assert "You give" in html


def test_item_visual_html_dispatches_injury_items_to_watch_visual():
    item = {
        "label": "Injury Exposure",
        "injury_need_positions": ["TE"],
        "injured_players": [
            {"asset_type": "player", "player_id": "7", "name": "My Player 7", "position": "TE"}
        ],
    }
    html = gm_plan_ui._item_visual_html(item)
    assert "My Player 7" in html


def test_item_visual_html_returns_empty_for_plain_rank_and_record_items():
    # Where You Stand / the Roster Construction rank rows name no players —
    # these must stay plain text + glyph, no fabricated visual.
    assert gm_plan_ui._item_visual_html({"label": "Roster Power", "rank": 3}) == ""
    assert gm_plan_ui._item_visual_html({"wins": 5, "losses": 2}) == ""
    assert gm_plan_ui._item_visual_html({"playoff_probability": 55}) == ""
