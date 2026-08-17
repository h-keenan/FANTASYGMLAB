"""Draft Capital four-card and adjacent ranking graphics."""

from __future__ import annotations

from pathlib import Path

from modules import draft_center_ui
from modules.app_styles import APP_CSS


ROOT = Path(__file__).resolve().parents[1]


def _four_cards(**overrides):
    payload = dict(
        owners=12,
        team_count=12,
        missing_count=0,
        missing_names="None",
        top_pick_team="AI Cumbot",
        top_pick_count=9,
        firsts=24,
        seconds=24,
        thirds=12,
        ownership_note="Current-year picks excluded after completed rookie draft",
    )
    payload.update(overrides)
    return draft_center_ui.build_draft_summary_metric_tiles(**payload)


def test_four_card_full_coverage_and_healthy_gaps():
    tiles = _four_cards()
    by_label = {item["label"]: item for item in tiles}
    assert list(by_label) == [
        "Tracked Pick Owners",
        "Teams Missing Key Picks",
        "Most Picks",
        "1st / 2nd Ownership",
    ]
    owners = by_label["Tracked Pick Owners"]
    assert owners["value"] == "12"
    assert "12 teams" in owners["note"]
    assert "dg-mg-strip" in owners["graphic"]
    assert owners["graphic"].count("is-on") == 12

    gaps = by_label["Teams Missing Key Picks"]
    assert gaps["value"] == "0"
    assert gaps["note"] == "No major gaps"
    assert "dg-mg-status--ok" in gaps["graphic"]
    assert "dg-mg-status__meter" not in gaps["graphic"]

    most = by_label["Most Picks"]
    assert most["value"] == "AI Cumbot"
    assert "9 picks" in most["note"]
    assert "dg-mg-rank--gold" in most["graphic"]
    assert "dg-mg-stack" in most["graphic"]

    rounds = by_label["1st / 2nd Ownership"]
    assert rounds["value"] == "24 / 24"
    assert "dg-mg-podium" in rounds["graphic"]
    assert "dg-mg-podium__step--1" in rounds["graphic"]
    assert "dg-mg-podium__step--2" in rounds["graphic"]


def test_four_card_partial_ownership_and_missing_key_picks():
    tiles = _four_cards(
        owners=7,
        team_count=12,
        missing_count=3,
        missing_names="Alpha, Bravo, Charlie",
        firsts=10,
        seconds=8,
        thirds=4,
    )
    by_label = {item["label"]: item for item in tiles}
    assert by_label["Tracked Pick Owners"]["value"] == "7"
    assert by_label["Tracked Pick Owners"]["graphic"].count("is-on") == 7
    assert by_label["Teams Missing Key Picks"]["value"] == "3"
    assert "Alpha" in by_label["Teams Missing Key Picks"]["note"]
    assert "dg-mg-status--alert" in by_label["Teams Missing Key Picks"]["graphic"]
    assert by_label["1st / 2nd Ownership"]["value"] == "10 / 8"


def test_headline_top_and_future_capital_treatments():
    tiles = draft_center_ui.build_draft_summary_headline_tiles(
        draft_completed=True,
        current_draft_year=2026,
        draft_status="complete",
        top_team={
            "team_name": "patrickshea",
            "draft_capital": 29805,
            "pick_count": 8,
        },
        best_future={
            "team_name": "patrickshea",
            "future_draft_capital": 29805,
        },
        peak_capital=29805,
        peak_future=29805,
        pick_status_note="Current-year picks excluded after completed rookie draft",
    )
    by_label = {item["label"]: item for item in tiles}
    top = by_label["Top Draft Capital Team"]
    assert top["value"] == "patrickshea"
    assert "29,805" in top["note"] or "29805" in top["note"].replace(",", "")
    assert "8 picks" in top["note"]
    assert "dg-mg-rank--gold" in top["graphic"]
    assert "dg-mg-bar" in top["graphic"]
    assert "width:100%" in top["graphic"]

    future = by_label["Best Future Capital"]
    assert future["value"] == "patrickshea"
    assert "beyond 2026" in future["note"]
    assert "dg-mg-timeline" in future["graphic"]
    assert "is-future" in future["graphic"]
    assert "2027+" in future["graphic"]
    assert "dg-mg-bar" in future["graphic"]


def test_dashboard_tiles_are_sparse_and_keep_comparison():
    tiles = draft_center_ui.build_draft_capital_dashboard_metric_tiles(
        most_name="Alpha",
        most_capital=100,
        least_name="Omega",
        least_capital=10,
        peak_capital=100,
        no_first_count=0,
        no_first_names="",
        hoarder_name="Alpha",
        hoarder_picks=9,
        hoarder_names="Alpha",
        lowest_name="Omega",
        lowest_note="10",
    )
    by_label = {item["label"]: item for item in tiles}
    assert "dg-mg-rank--gold" in by_label["Most Draft Capital"]["graphic"]
    assert "dg-mg-bar" in by_label["Least Draft Capital"]["graphic"]
    assert "width:10%" in by_label["Least Draft Capital"]["graphic"]
    assert "dg-mg-status--ok" in by_label["Teams With No 1sts"]["graphic"]
    assert "dg-mg-stack" in by_label["Pick Hoarders"]["graphic"]
    assert not by_label["Low Future Assets"].get("graphic")


def test_empty_and_long_name_states_keep_text():
    empty = _four_cards(
        owners=0,
        team_count=12,
        missing_count=12,
        missing_names="Everyone",
        top_pick_team="—",
        top_pick_count=0,
        firsts=0,
        seconds=0,
        thirds=0,
    )
    by_label = {item["label"]: item for item in empty}
    assert by_label["Tracked Pick Owners"]["value"] == "0"
    assert by_label["Tracked Pick Owners"]["graphic"].count("is-on") == 0
    assert by_label["Most Picks"]["graphic"].count("dg-mg-stack__plate") == 0

    long_name = "A" * 48 + " Dynasty Club"
    long_tiles = _four_cards(top_pick_team=long_name)
    assert long_tiles[2]["value"] == long_name


def test_draft_center_wires_builders_not_chart_libraries():
    source = (ROOT / "modules" / "draft_center_ui.py").read_text(encoding="utf-8")
    assert "build_draft_summary_metric_tiles" in source
    assert "build_draft_summary_headline_tiles" in source
    assert "coverage_strip_html" in source
    assert "round_podium_html" in source
    assert "plotly" not in source
    assert "chart.js" not in source.lower()
    league = (ROOT / "modules" / "league_workspace_ui.py").read_text(encoding="utf-8")
    assert "rank_badge_html" in league
    assert "Most Draft Capital" in league
    assert "leader_identity_html" in league
    assert "dg-mg" in APP_CSS
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    assert "build_draft_summary_metric_tiles" in harness
    assert "Tracked Pick Owners" not in harness or "owners=12" in harness
