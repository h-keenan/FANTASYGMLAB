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
