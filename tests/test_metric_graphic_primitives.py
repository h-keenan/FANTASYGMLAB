"""Graphical metric primitives — structure supplements, not replacement values."""

from __future__ import annotations

from pathlib import Path

from modules import metric_graphic_primitives as mgp
from modules.app_styles import APP_CSS
from modules.metric_graphic_styles import METRIC_GRAPHIC_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.workspace_ui import summary_tiles_html
from modules.executive_table_ui import executive_table_row_html


ROOT = Path(__file__).resolve().parents[1]


def test_coverage_strip_empty_partial_and_full():
    empty = mgp.coverage_strip_html(filled=0, total=0)
    assert "No teams tracked" in empty
    assert "dg-mg-strip__cell" not in empty

    partial = mgp.coverage_strip_html(filled=7, total=12)
    assert partial.count("dg-mg-strip__cell") == 12
    assert partial.count("is-on") == 7
    assert "7 of 12" in partial

    full = mgp.coverage_strip_html(filled=12, total=12)
    assert full.count("is-on") == 12
    assert "12 of 12" in full

    oversized = mgp.coverage_strip_html(filled=18, total=18)
    assert oversized.count("dg-mg-strip__cell") == 16
    assert "+2" in oversized


def test_gap_status_quiet_zero_and_severity():
    ok = mgp.gap_status_html(count=0)
    assert "dg-mg-status--ok" in ok
    assert "dg-mg-status__meter" not in ok
    assert "No major pick gaps" in ok

    warn = mgp.gap_status_html(count=2)
    assert "dg-mg-status--warn" in warn
    assert "dg-mg-status__meter" in warn
    assert "2 teams missing" in warn

    alert = mgp.gap_status_html(count=5)
    assert "dg-mg-status--alert" in alert
    assert "width:100%" in alert


def test_rank_badge_top_three_and_empty():
    assert mgp.rank_badge_html(0) == ""
    gold = mgp.rank_badge_html(1)
    assert "dg-mg-rank--gold" in gold and ">1</span>" in gold
    assert "dg-mg-rank--silver" in mgp.rank_badge_html(2)
    assert "dg-mg-rank--bronze" in mgp.rank_badge_html(3)
    assert "dg-mg-rank--rest" in mgp.rank_badge_html(4)


def test_pick_stack_empty_and_overflow():
    empty = mgp.pick_stack_html(count=0)
    assert "dg-mg-stack__empty" in empty
    assert "0 picks" in empty
    stacked = mgp.pick_stack_html(count=9, cap=8)
    assert stacked.count("dg-mg-stack__plate") == 8
    assert "+1" in stacked


def test_round_podium_distinguishes_firsts_and_seconds():
    html = mgp.round_podium_html(firsts=24, seconds=18, thirds=6)
    assert "dg-mg-podium__step--1" in html
    assert "dg-mg-podium__step--2" in html
    assert "dg-mg-podium__step--3" in html
    assert html.index("dg-mg-podium__step--2") < html.index("dg-mg-podium__step--1")
    assert "24 first-round" in html
    two = mgp.round_podium_html(firsts=0, seconds=0)
    assert "dg-mg-podium__step--3" not in two
    assert ">0</span>" in two


def test_capital_bar_and_future_timeline():
    bar = mgp.capital_bar_html(value=15000, peak=30000)
    assert "width:50%" in bar
    assert "percent of the league-leading" in bar
    empty = mgp.capital_bar_html(value=0, peak=0)
    assert "width:0%" in empty
    timeline = mgp.future_timeline_html(beyond_year=2026)
    assert ">2026<" in timeline
    assert "is-future" in timeline
    assert "2027+" in timeline


def test_graphics_do_not_replace_text_values_in_tiles():
    long_name = "Very Long Dynasty Franchise Name That Should Wrap"
    html = executive_table_row_html(
        primary="Most Picks",
        secondary=long_name,
        meta="9 picks",
        graphic=mgp.leader_identity_html(rank=1) + mgp.pick_stack_html(count=9),
    )
    assert long_name in html
    assert "9 picks" in html
    assert "dg-mg-rank--gold" in html
    assert "dg-mg-stack" in html
    assert "&lt;div" not in html

    tiles = summary_tiles_html(
        [
            {
                "label": "Top Draft Capital Team",
                "value": long_name,
                "note": "29,805 total | 8 picks",
                "graphic": mgp.capital_bar_html(value=29805, peak=29805),
                "tappable": False,
            }
        ]
    )
    assert long_name in tiles
    assert "dg-mg-bar" in tiles


def test_metric_graphic_css_ships_before_overlay_and_stays_compact():
    assert METRIC_GRAPHIC_CSS in APP_CSS
    assert APP_CSS.index(METRIC_GRAPHIC_CSS) < APP_CSS.index(
        MOBILE_INTERACTION_OVERLAY_CSS
    )
    assert "@media (max-width:430px)" in METRIC_GRAPHIC_CSS
    assert "@media (min-width:1024px)" in METRIC_GRAPHIC_CSS
    assert "chart.js" not in METRIC_GRAPHIC_CSS.lower()
    assert "plotly" not in METRIC_GRAPHIC_CSS.lower()
    source = (ROOT / "modules" / "metric_graphic_primitives.py").read_text(
        encoding="utf-8"
    )
    assert "st.rerun" not in source
    assert "sleeper" not in source.lower()
