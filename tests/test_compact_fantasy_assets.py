from modules.compact_fantasy_assets import presentation_asset


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
