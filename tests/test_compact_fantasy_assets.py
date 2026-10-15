from modules.compact_fantasy_assets import compact_asset_html, presentation_asset


def test_presentation_asset_carries_overall_rating_through():
    payload = presentation_asset(
        {
            "asset_type": "player",
            "player_id": "1234",
            "name": "Test Player",
            "overall_rating": 82,
        }
    )

    assert payload["overall_rating"] == 82


def test_presentation_asset_carries_player_tier_for_the_avatar_ring():
    payload = presentation_asset(
        {
            "asset_type": "player",
            "player_id": "1234",
            "name": "Test Player",
            "position": "wr",
            "team": "kc",
            "player_tier": "elite",
        }
    )

    assert payload["tier"] == "elite"


def test_presentation_asset_tier_is_empty_string_when_missing():
    payload = presentation_asset(
        {
            "asset_type": "player",
            "player_id": "1234",
            "name": "Test Player",
        }
    )

    assert payload["tier"] == ""


def test_compact_asset_html_renders_ovr_gauge_when_opted_in():
    html = compact_asset_html(
        {
            "asset_type": "player",
            "player_id": "1234",
            "name": "Test Player",
            "position": "WR",
            "team": "KC",
            "overall_rating": 82,
        },
        show_overall_rating=True,
    )

    assert "dg-ovr-gauge" in html
    assert "82" in html


def test_compact_asset_html_omits_ovr_gauge_by_default():
    html = compact_asset_html(
        {
            "asset_type": "player",
            "player_id": "1234",
            "name": "Test Player",
            "overall_rating": 82,
        }
    )

    assert "dg-ovr-gauge" not in html


def test_compact_asset_html_omits_ovr_gauge_when_rating_missing():
    html = compact_asset_html(
        {
            "asset_type": "player",
            "player_id": "1234",
            "name": "Test Player",
        },
        show_overall_rating=True,
    )

    assert "dg-ovr-gauge" not in html


def test_compact_asset_html_pick_ignores_overall_rating_flag():
    html = compact_asset_html(
        {
            "asset_type": "pick",
            "season": "2027",
            "round": "1",
        },
        show_overall_rating=True,
    )

    assert "dg-ovr-gauge" not in html
