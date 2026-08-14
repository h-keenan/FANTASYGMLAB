"""Concept-band → summary-tile migration contracts (#223)."""

from __future__ import annotations

from pathlib import Path

from modules import workspace_ui


ROOT = Path(__file__).resolve().parents[1]


def test_concept_items_map_to_summary_tiles():
    mapped = workspace_ui.concept_items_as_summary_tiles(
        [
            {
                "label": "Outlook",
                "title": "Contender",
                "body": "Strong current roster.",
                "tone": "franchise",
            }
        ]
    )
    assert mapped == [
        {
            "label": "Outlook",
            "value": "Contender",
            "note": "Strong current roster.",
            "tone": "franchise",
            "comparison": None,
            "tappable": False,
            "hide_icon": False,
        }
    ]


def test_concept_band_html_emits_summary_tiles_only():
    html = workspace_ui.concept_band_html(
        [
            {
                "label": "<Standings>",
                "title": "Actual results",
                "body": "Wins & losses.",
                "tone": "strategy",
            }
        ]
    )
    assert "summary-tile dg-ui-card" in html
    assert "summary-tile-grid" in html
    assert "&lt;Standings&gt;" in html
    assert "concept-chip" not in html
    assert "concept-band" not in html


def test_my_team_uses_summary_tiles_for_posture_and_position_groups():
    source = (ROOT / "modules" / "my_team_ui.py").read_text(encoding="utf-8")
    assert 'key_prefix=f"my_team_posture_' in source
    assert 'key_prefix=f"my_team_position_groups_' in source
    assert "concept_band_html(posture_items)" not in source
    assert "concept_band_html(position_items)" not in source
