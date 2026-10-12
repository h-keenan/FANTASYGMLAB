from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from modules import dashboard_workflow


ROOT = Path(__file__).resolve().parents[1]


def _item(label: str, value: str = "Fixture") -> dict:
    return {"label": label, "value": value, "note": "Synthetic presentation input."}


def test_briefing_selects_one_actionable_recommendation_and_separates_intelligence():
    items = [
        _item("Roster Pressure", "Within Limit"),
        _item("Biggest Team Need", "QB"),
        _item("Top Trade Opportunity", "Partner"),
        _item("Top Waiver Opportunity", "Player"),
        _item("Injury Alert", "Stable"),
    ]

    briefing = dashboard_workflow.organize_dashboard_items(items)

    assert briefing.immediate == ()
    assert briefing.primary["label"] == "Biggest Team Need"
    assert [item["label"] for item in briefing.intelligence] == [
        "Top Trade Opportunity",
        "Top Waiver Opportunity",
    ]
    assert briefing.additional == ()


def test_active_attention_items_do_not_duplicate_the_primary_recommendation():
    roster = _item("Roster Pressure", "2 Over")
    injury = _item("Injury Alert", "2 injured starters")
    trade = _item("Top Trade Opportunity", "Partner")

    briefing = dashboard_workflow.organize_dashboard_items(
        [roster, injury, trade],
        immediate_labels=frozenset({"Roster Pressure", "Injury Alert"}),
    )

    assert [item["label"] for item in briefing.immediate] == [
        "Roster Pressure",
        "Injury Alert",
    ]
    assert briefing.primary == trade
    assert not briefing.additional
    assert not briefing.intelligence


def test_startup_status_cards_do_not_displace_the_first_real_next_move():
    briefing = dashboard_workflow.organize_dashboard_items(
        [
            _item("Roster Quality"),
            _item("Biggest Team Need", "WR"),
            _item("Top Trade Opportunity"),
            _item("Lineup Construction"),
        ]
    )

    assert briefing.primary["label"] == "Biggest Team Need"
    assert [item["label"] for item in briefing.intelligence] == [
        "Top Trade Opportunity"
    ]


def test_briefing_model_is_frozen():
    briefing = dashboard_workflow.organize_dashboard_items([_item("Biggest Team Need")])
    with pytest.raises(FrozenInstanceError):
        briefing.primary = None


def test_workflow_has_game_plan_then_zone_order_and_progressive_disclosure_contract():
    source = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    assert source.index("render_page_context()") < source.index("render_todays_game_plan()")
    assert "render_todays_game_plan()" in source
    assert "render_what_changed()" in source
    positions = [
        source.index(marker)
        for marker in (
            "render_todays_game_plan()",
            "render_what_changed()",
            'render_section_header("League Insights"',
            'render_section_header("Team Snapshot"',
            '"Explore"',
        )
    ]

    assert positions == sorted(positions)
    assert "@st.fragment" not in source
    assert "_deferred_post_useful_sections" not in source
    assert source.index("render_todays_game_plan()") < source.index(
        "_render_post_useful_sections()"
    )
    assert "game_plan_present" in source
    assert "if not game_plan_present:" in source
    assert "League Pulse and supporting trends" in source
    # With Game Plan present, Immediate Action / Your Next Move boards are omitted.
    assert source.count('"Immediate Action"') == 1
    assert source.count('"Your Next Move"') == 1
    gate = source.index("if not game_plan_present:")
    assert gate < source.index('"Immediate Action"')
    assert gate < source.index('"Your Next Move"')


def test_mobile_layout_is_scoped_token_backed_and_overflow_safe():
    css = (ROOT / "modules" / "dashboard_workflow_styles.py").read_text(
        encoding="utf-8"
    )

    assert ".st-key-dashboard_workflow" in css
    assert "@media (max-width: 700px)" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert "min-width: 0" in css
    assert "width: 100%" in css
    assert "white-space: normal" in css
    assert "var(--touch-target-min)" in css
    assert "gap: var(--space-lg);" in css
    assert "gap: var(--space-md);" in css
    assert "#" not in css


def test_app_preserves_entitlement_slice_and_existing_dashboard_inputs():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    dashboard = source.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]

    assert (
        "visible_action_items = action_center_items if is_premium else action_center_items[:4]"
        in dashboard
    )
    assert "cached_dashboard_trade_headline(" in dashboard
    assert "select_top_waiver_opportunity(" in dashboard
    assert "build_my_team_advice(" in dashboard
    assert "dashboard_workflow.organize_dashboard_items(" in dashboard
    assert "dashboard_workflow.render_dashboard_workflow(" in dashboard
    assert "render_home_command_hero(" not in dashboard
    # Bounded on the literal list's own closing bracket (not "]\n\n", which
    # doesn't actually occur right after this list and previously let the
    # match run on into unrelated later code) so this only inspects Team
    # Snapshot's own five tiles -- the ones snapshot_items builds. League
    # Snapshot (the mobile-parity feature) is a deliberately separate list
    # (league_snapshot_items, right below this one) that does carry
    # Power Rank/Franchise Rank -- see
    # test_league_snapshot_is_separate_from_team_snapshot below.
    snapshot = dashboard.split("snapshot_items = [", 1)[1].split("]", 1)[0]
    assert '"Power Rank"' not in snapshot
    assert '"Franchise Rank"' not in snapshot
    assert '"Average Age"' in snapshot


def test_league_snapshot_is_separate_from_team_snapshot():
    """New mobile-parity section: Record/Power Rank/Franchise Rank/Avg Age/
    Injuries, built from real already-computed data (team_row power_rank/
    franchise_rank, record_label, average_age_label, injured_starters) --
    not fabricated, and not merged into Team Snapshot's own five tiles
    (which intentionally exclude Power/Franchise Rank; see the test above).
    """

    source = (ROOT / "app.py").read_text(encoding="utf-8")
    dashboard = source.split("def render_home_dashboard(", 1)[1].split(
        "STARTUP_DRAFT_STRATEGIES", 1
    )[0]
    league_snapshot = dashboard.split("league_snapshot_items = [", 1)[1].split(
        "]", 1
    )[0]
    assert '"Power Rank"' in league_snapshot
    assert '"Franchise Rank"' in league_snapshot
    assert '"Injuries"' in league_snapshot
    assert "team_row.get(\"power_rank\")" in league_snapshot
    assert "team_row.get(\"franchise_rank\")" in league_snapshot
    assert "league_snapshot_items=league_snapshot_items" in dashboard
