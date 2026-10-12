from modules.compact_fantasy_assets import compact_asset_html, presentation_asset


_PLAYER = {
    "asset_type": "player",
    "player_id": "1234",
    "name": "Test Player",
    "position": "wr",
    "team": "kc",
    "player_tier": "elite",
    "role": "workhorse",
    "injury_status": "Q",
}


def test_rich_identity_renders_tier_ring_and_colored_position_pill():
    """Today's Game Plan cards (and anything else opting in) get the same
    graphical identity treatment as My Team / Waivers / Trade Hub / Draft —
    a tier-colored avatar ring (modules.player_tier_identity's existing
    .dg-tier-frame-- classes) and a colored position pill
    (modules.football_assets.position_badge_html), not plain "POS · TEAM"
    text."""

    html = compact_asset_html(_PLAYER, size="standard", rich_identity=True)

    assert "dg-tier-frame" in html
    assert "dg-tier-frame--ring" in html
    assert "dg-player-portrait" in html
    assert "dg-football-position--wr" in html
    assert "KC" in html


def test_rich_identity_renders_role_and_injury_as_pills_not_plain_text():
    html = compact_asset_html(_PLAYER, size="standard", rich_identity=True)

    assert "tvl-tier" in html
    assert "WORKHORSE" in html
    assert "dg-football-injury" in html


def test_rich_identity_off_by_default_keeps_plain_text_unchanged():
    """Every pre-existing caller of this shared renderer (Trade Analyzer,
    League History, Trade Hub summary, Live Draft) must see no change."""

    html = compact_asset_html(_PLAYER, size="standard")

    assert "dg-tier-frame" not in html
    assert "dg-football-position--wr" not in html
    assert "dg-football-injury" not in html
    assert "WR · KC" in html
    assert "Workhorse" in html


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
