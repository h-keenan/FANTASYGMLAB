"""Dashboard command-center presentation regressions.

Presentation-only: no new football scoring, provider calls, or eager hydration.
"""

from __future__ import annotations

from pathlib import Path

from modules import compact_fantasy_assets as compact
from modules import daily_gm_briefing as dgb
from modules import dashboard_workflow


ROOT = Path(__file__).resolve().parents[1]


def _tile(label: str, value: str, *, rec_id: str = "", note: str = "note", **extra):
    payload = {
        "label": label,
        "value": value,
        "note": note,
        "recommendation_id": rec_id,
    }
    payload.update(extra)
    return payload


def test_trade_top_priority_renders_give_get_portraits_and_edge():
    html = compact.game_plan_trade_visual_html(
        {
            "value_edge": "+237",
            "send": [
                {
                    "asset_type": "player",
                    "player_id": "6794",
                    "name": "Tyrone Tracy",
                    "position": "RB",
                    "team": "NYG",
                    "age": 26,
                }
            ],
            "receive": [
                {
                    "asset_type": "player",
                    "player_id": "8155",
                    "name": "Pat Bryant",
                    "position": "WR",
                    "team": "DEN",
                },
                {
                    "asset_type": "pick",
                    "label": "2027 Round 3",
                    "season": "2027",
                    "round": "3",
                },
            ],
        }
    )
    assert "Tyrone Tracy" in html
    assert "Pat Bryant" in html
    assert "2027 Round 3" in html
    assert "You give" in html
    assert "You get" in html
    assert "dg-gp-trade-for" in html
    assert "FOR" in html.upper()
    assert "+237 VALUE EDGE" in html
    assert "dg-compact-asset-avatar" in html
    assert "dg-compact-asset--standard" in html
    assert "fetch_player_headshot_bytes" not in Path(
        "modules/compact_fantasy_assets.py"
    ).read_text(encoding="utf-8")


def test_waiver_opportunity_renders_player_identity_and_role():
    html = compact.compact_asset_html(
        {
            "asset_type": "player",
            "player_id": "8134",
            "name": "Emanuel Wilson",
            "position": "RB",
            "team": "GB",
            "role": "Handcuff",
        },
        size="compact",
        show_value=False,
    )
    assert "Emanuel Wilson" in html
    assert "RB" in html
    assert "Handcuff" in html
    assert "dg-compact-asset-avatar" in html
