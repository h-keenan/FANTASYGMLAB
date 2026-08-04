from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

from modules import comparative_metrics, workspace_ui


def _league_frame():
    return pd.DataFrame(
        [
            {"roster_id": "3", "team_name": "Old Guard", "owner_name": "Casey", "avg_age": 28.4, "age_rank": 3},
            {"roster_id": "1", "team_name": "Young Core", "owner_name": "Alex", "avg_age": 23.8, "age_rank": 1},
            {"roster_id": "2", "team_name": "Active Club", "owner_name": "Jordan", "avg_age": 25.1, "age_rank": 2},
        ]
    )


def test_comparison_model_is_frozen_and_orders_age_deterministically():
    comparison = comparative_metrics.build_metric_comparison(
        _league_frame(), metric_key="avg_age", title="Average Age",
        active_roster_id="2", ascending=True, baseline="average",
        interpretation="Balanced age profile.",
    )
    assert comparison is not None
    assert [row.team_name for row in comparison.rows] == ["Young Core", "Active Club", "Old Guard"]
    assert comparison.active_rank == 2
    assert comparison.rows[1].active is True
    with pytest.raises(FrozenInstanceError):
        comparison.active_rank = 1


def test_comparison_payload_marks_active_team_and_exposes_league_context():
    comparison = comparative_metrics.build_metric_comparison(
        _league_frame(), metric_key="avg_age", title="Average Age",
        active_roster_id="2", ascending=True, baseline="average",
        interpretation="Balanced age profile.",
    )
    payload = comparative_metrics.comparison_payload(comparison)
    content = workspace_ui.canonical_summary_tile_modal_content(
        {"label": "Average Age", "value": "25.1", "comparison": payload}
    )
    assert content.eyebrow == "League Comparison"
    assert content.list_title == "League Leaderboard"
    assert content.list_before_sections is True
    assert [item.title for item in content.list_items] == ["Young Core", "Active Club", "Old Guard"]
    assert content.list_items[1].highlighted is True
    assert [section.label for section in content.sections] == ["Interpretation", "Methodology"]
    assert all(section.label != "What It Means" for section in content.sections)
    assert all(section.label != "Front Office Read" for section in content.sections)
    html = __import__("modules.ui_modal", fromlist=["ui_modal"]).modal_content_html(
        content, surface="test"
    )
    assert html.index("League Leaderboard") < html.index("Interpretation")
    assert html.index("Interpretation") < html.index("Methodology")


def test_missing_comparative_values_fail_honestly():
    frame = pd.DataFrame([{"roster_id": "1", "team_name": "No Data", "avg_age": None}])
    assert comparative_metrics.build_metric_comparison(
        frame, metric_key="avg_age", title="Average Age",
        active_roster_id="1", ascending=True, interpretation="Unavailable.",
    ) is None
