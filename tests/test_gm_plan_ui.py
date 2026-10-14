"""modules.gm_plan_ui — Trade Opportunities / Roster Construction visual
identity (avatar + tier, in place of a plain-text-only treatment).

Mirrors the established pattern modules.daily_gm_briefing_ui already uses
for Dashboard's Top Priority trade card and Watch card: real
modules.compact_fantasy_assets visuals built from the SAME raw
send_assets/receive_assets/injured_players dicts modules.gm_plan already
carries, not a new design.
"""

from __future__ import annotations

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
