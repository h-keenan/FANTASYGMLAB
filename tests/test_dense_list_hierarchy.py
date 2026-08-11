"""Dense list information hierarchy contracts (presentation only)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import dense_list_primitives, league_workspace_ui
from modules.app_styles import APP_CSS
from modules.component_family_styles import COMPONENT_FAMILY_CSS
from modules.dense_list_styles import DENSE_LIST_CSS
from modules.design_tokens import DESIGN_TOKEN_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_dense_list_css_is_token_backed_and_early():
    assert DENSE_LIST_CSS in APP_CSS
    assert APP_CSS.index(DESIGN_TOKEN_CSS) < APP_CSS.index(COMPONENT_FAMILY_CSS)
    assert APP_CSS.index(COMPONENT_FAMILY_CSS) < APP_CSS.index(DENSE_LIST_CSS)
    assert "#" not in DENSE_LIST_CSS.replace("#257", "")
    # No literal hex colors in dense-list family.
    import re

    assert not re.search(r"#[0-9a-fA-F]{3,8}", DENSE_LIST_CSS)


def test_status_pair_normalization_removes_duplicates():
    assert dense_list_primitives.normalize_status_pair("Contender", "Contender") == (
        "Contender",
        "",
    )
    assert dense_list_primitives.normalize_status_pair("Retool", "Retool Candidate") == (
        "Retool",
        "Candidate",
    )
    assert dense_list_primitives.normalize_status_pair("Contender", "Aging Contender") == (
        "Contender",
        "Aging Contender",
    )
    assert dense_list_primitives.normalize_status_pair("Compete", "Contender") == (
        "Compete",
        "Contender",
    )


def test_exception_html_omits_empty_and_labels_concern():
    assert dense_list_primitives.dense_exception_html("") == ""
    assert dense_list_primitives.dense_exception_html("0") != ""  # non-empty text still renders
    html = dense_list_primitives.dense_exception_html(
        "2 starters",
        label="Starter availability",
    )
    assert "dg-dense-exception" in html
    assert "Starter availability" in html
    assert "2 starters" in html
    assert "role='status'" in html


def test_metric_block_attaches_label_and_compacts_starter_weighted():
    html = dense_list_primitives.dense_metric_html("66,722", "Starter-Weighted Score")
    assert "dg-dense-metric__value" in html
    assert "66,722" in html
    assert "Starter score" in html
    assert "Starter-Weighted Score" not in html
    assert dense_list_primitives.compact_metric_label("Roster Value + Draft Capital") == (
        "Roster + draft"
    )
    assert dense_list_primitives.compact_metric_label("Draft Capital Score") == (
        "Draft capital"
    )


def test_ranked_row_anatomy_order_and_exception_slot():
    html = league_workspace_ui.ranked_leaderboard_row_html(
        rank_label="#1",
        team_name="War Room",
        owner_text="@founder",
        primary_metric="12,400",
        metric_label="Starter-Weighted Score",
        status_category="Contender",
        status_subtype="Aging Contender",
        secondary="Franchise #2 · Draft #3 · Starter #1",
        exception="2 starters",
        logo_html="<div class='dg-ranked-logo'>WR</div>",
        top_three=True,
        is_current=True,
    )
    assert "dg-dense-row" in html
    assert "dg-dense-row--compact" in html
    assert html.index("dg-ranked-rank") < html.index("dg-ranked-team")
    assert html.index("dg-ranked-team") < html.index("dg-dense-metric")
    assert html.index("dg-dense-metric") < html.index("dg-dense-status")
    assert html.index("dg-dense-status") < html.index("dg-dense-meta")
    assert html.index("dg-dense-meta") < html.index("dg-dense-exception")
    assert "dg-dense-exception" in html
    assert "Aging Contender" in html
    # No warning when exception empty
    quiet = league_workspace_ui.ranked_leaderboard_row_html(
        rank_label="#2",
        team_name="Quiet",
        owner_text="@q",
        primary_metric="1",
        metric_label="Score",
        interpretation="Compete",
        secondary="Franchise #1",
        logo_html="<div class='dg-ranked-logo'>Q</div>",
        exception="",
    )
    assert "dg-dense-exception" not in quiet


def test_power_board_keeps_health_out_of_meta_when_exceptional():
    frame = pd.DataFrame(
        [
            {
                "roster_id": "hurt",
                "team_name": "Hurt",
                "owner_username": "h",
                "owner_name": "H",
                "avatar_url": "",
                "power_rank": 1,
                "power_score": 8000,
                "franchise_rank": 2,
                "starter_rank": 1,
                "bench_rank": 1,
                "draft_capital_rank": 1,
                "strategy_display": "Contender",
                "archetype_label": "Contender",
                "mode": "competitive",
                "injured_starters": 2,
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
        has_meaningful_team_injury_impact=lambda _row: True,
        team_injury_display_label=lambda _row: "Injury pressure",
        team_tap_markup=lambda row: ("", ""),
        render_team_card_tap_grid=_capture,
        open_league_team_from_tap=lambda _clicked: False,
        team_logo_html=lambda *_a, **_k: "<div class='dg-ranked-logo'>H</div>",
    )
    html = captured["html"]
    assert "dg-dense-exception" in html
    assert "Injury pressure" in html
    # Meta should not include the injury prose blob as a normal fact.
    meta = html.split("dg-dense-meta", 1)[1].split("</div>", 1)[0]
    assert "Injury pressure" not in meta
    # Duplicate Contender · Contender collapsed to single status primary.
    assert "dg-dense-status__secondary" not in html


def test_app_css_budget_holds_after_dense_lists():
    assert len(APP_CSS) < 390_000


def test_audit_doc_exists():
    doc = ROOT / "docs" / "dense-list-information-hierarchy.md"
    assert doc.exists()
