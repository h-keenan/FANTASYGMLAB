"""Future picks must not imply a known overall slot."""

from modules.compact_fantasy_assets import compact_asset_html, presentation_asset


def test_future_round_only_pick_does_not_use_year_as_overall_slot():
    html = compact_asset_html(
        {
            "asset_type": "pick",
            "label": "2027 Round 3",
            "season": 2027,
            "round": 3,
            "score": 1400,
        }
    )
    plate = html.split("dg-compact-pick-plate", 1)[1].split("</div>", 1)[0]
    assert "PICK" in plate
    assert "R3" in plate
    assert "27" not in plate
    assert "#27" not in html
    assert "Pick 27" not in html


def test_known_current_slot_can_show_exact_pick_number():
    html = compact_asset_html(
        {
            "asset_type": "pick",
            "label": "2026 Round 1",
            "season": 2026,
            "round": 1,
            "pick_no": 4,
            "is_current_year_pick": True,
            "score": 6500,
        }
    )
    assert "Pick 4" in html
    payload = presentation_asset(
        {
            "asset_type": "pick",
            "season": 2026,
            "round": 1,
            "pick_no": 4,
            "is_current_year_pick": True,
        }
    )
    assert payload["slot_known"] is True
    assert payload["pick_no"] == 4


def test_projected_early_mid_late_is_labeled_projected_not_exact():
    html = compact_asset_html(
        {
            "asset_type": "pick",
            "label": "2028 Round 1",
            "season": 2028,
            "round": 1,
            "pick_tier": "early",
            "score": 5600,
        }
    )
    assert "Early (projected)" in html
    assert "#1" not in html
    assert "Pick 1" not in html
