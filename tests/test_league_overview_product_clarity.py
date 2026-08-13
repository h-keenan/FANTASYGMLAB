"""League Overview product clarity — presentation only."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import league_workspace_ui


ROOT = Path(__file__).resolve().parents[1]


def test_clarity_audit_doc_exists():
    doc = ROOT / "docs" / "league-overview-product-clarity-audit.md"
    text = doc.read_text(encoding="utf-8")
    assert "Most / Least Draft Capital" in text
    assert "League Insights" in text
    assert "Before section inventory" in text


def test_overview_customer_copy_uses_league_insights():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    rankings = app_source[app_source.index('if league_section == "Rankings":') :]
    assert '"League Insights"' in rankings
    assert "League Intelligence" not in rankings[:14000]
    assert "Best Starter Core" not in rankings[:14000]
    assert 'rank_column="draft_capital_rank"' in rankings
    assert 'client_disclosure_html(\n                        "How to read these boards"' in rankings or (
        'client_disclosure_html(' in rankings and '"How to read these boards"' in rankings
    )
    assert "Team comparison" in rankings
    assert "render_team_comparison_board" in rankings
    assert "Full team metrics" not in rankings


def test_filter_omits_draft_extremes_covered_by_board():
    cards = [
        {"label": "Youngest Roster", "team_name": "A"},
        {"label": "Most Draft Capital", "team_name": "B"},
        {"label": "Least Draft Capital", "team_name": "C"},
        {"label": "Deepest Roster", "team_name": "D"},
    ]
    filtered = league_workspace_ui.filter_league_insight_leader_cards(
        cards,
        omit_labels=("Most Draft Capital", "Least Draft Capital"),
    )
    assert [card["label"] for card in filtered] == [
        "Youngest Roster",
        "Deepest Roster",
    ]


def test_decision_cards_drop_pick_rich_poor_duplicates():
    frame = pd.DataFrame(
        [
            {
                "team_name": "Alpha",
                "power_rank": 1,
                "franchise_rank": 2,
                "draft_capital_rank": 3,
                "draft_capital": 100,
                "first_rounders": 1,
                "pick_count": 3,
                "injury_burden": 0,
                "injured_starters": 0,
                "trade_count": 0,
                "strategy": "contender",
                "mode": "contender",
                "strategy_display": "Compete",
            },
            {
                "team_name": "Beta",
                "power_rank": 6,
                "franchise_rank": 6,
                "draft_capital_rank": 1,
                "draft_capital": 400,
                "first_rounders": 3,
                "pick_count": 8,
                "injury_burden": 2,
                "injured_starters": 1,
                "trade_count": 0,
                "strategy": "rebuild",
                "mode": "rebuild",
                "strategy_display": "Rebuild",
            },
            {
                "team_name": "Gamma",
                "power_rank": 4,
                "franchise_rank": 4,
                "draft_capital_rank": 4,
                "draft_capital": 80,
                "first_rounders": 0,
                "pick_count": 2,
                "injury_burden": 0,
                "injured_starters": 0,
                "trade_count": 0,
                "strategy": "retool",
                "mode": "retool",
                "strategy_display": "Retool",
            },
        ]
    )
    cards = league_workspace_ui.build_league_overview_decision_cards(
        frame,
        team_injury_display_label=lambda _row: "",
    )
    labels = [card["label"] for card in cards]
    assert "Pressure Teams" in labels
    assert "Stuck Middle" in labels
    assert "Partner Types" in labels
    assert "Pick-Rich" not in labels
    assert "Pick-Poor" not in labels


def test_power_board_secondary_omits_own_primary_rank():
    frame = pd.DataFrame(
        [
            {
                "roster_id": "1",
                "team_name": "Alpha",
                "owner_username": "a",
                "owner_name": "A",
                "avatar_url": "",
                "power_rank": 1,
                "power_score": 100,
                "franchise_rank": 2,
                "starter_rank": 1,
                "bench_rank": 3,
                "draft_capital_rank": 4,
                "first_rounders": 1,
                "pick_count": 2,
                "strategy_display": "Compete",
                "archetype_label": "Contender",
                "mode": "competitive",
                "injured_starters": 0,
            }
        ]
    )
    captured = {}

    def _capture(*, html: str, key_prefix: str):
        captured["html"] = html
        return None

    league_workspace_ui.render_power_rankings_board(
        frame,
        "Starter-Weighted Score",
        has_meaningful_team_injury_impact=lambda _row: False,
        team_injury_display_label=lambda _row: "",
        team_tap_markup=lambda _row: ("", ""),
        render_team_card_tap_grid=_capture,
        open_league_team_from_tap=lambda _clicked: False,
        team_logo_html=lambda *_a, **_k: "<div class='dg-ranked-logo'>A</div>",
    )
    secondary = captured["html"]
    assert "Franchise #2" in secondary
    assert "Draft #4" in secondary
    assert "Power #1" not in secondary
