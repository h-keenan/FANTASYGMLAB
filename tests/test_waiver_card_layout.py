from modules import football_assets
from modules.football_asset_styles import FOOTBALL_ASSET_CSS
from modules.waivers_presentation_styles import WAIVERS_PRESENTATION_CSS


def test_player_name_wraps_at_last_token_not_trailing_letter():
    html = football_assets.player_name_html("Garrett Nussmeier")
    assert "Garrett <wbr>Nussmeier" in html
    assert html.count("<wbr>") == 1
    for name in (
        "Equanimeous St. Brown",
        "Amon-Ra St. Brown",
        "D'Andre Swift",
        "Ja'Marr Chase",
    ):
        markup = football_assets.player_name_html(name)
        last = name.split()[-1]
        assert last in markup
        if len(name) >= 16 or len(last) >= 7:
            assert "<wbr>" in markup
    assert "<wbr>" not in football_assets.player_name_html("Player One")


def test_stacked_card_keeps_score_below_status_badge():
    html = football_assets.player_card_html(
        football_assets.FootballPlayerAsset(
            player_id="1",
            display_name="Garrett Nussmeier",
            position="QB",
            team="NO",
            prestige_label="Best Available",
            prestige_level="contributor",
            value_label="Dynasty Score",
            value="4120",
            age="Age 23",
        ),
        stacked=True,
    )
    assert "dg-football-asset--stacked" in html
    assert html.index("dg-football-asset__name") < html.index("dg-football-asset__meta")
    assert "QB · NO · Age 23" in html
    assert html.index("dg-football-asset__badges") < html.index("dg-football-asset__value")
    assert html.index("Best Available") < html.index("dg-football-asset__value")
    assert "player-position-badge" not in html
    assert "title='Garrett Nussmeier'" in html


def test_waiver_mobile_css_separates_badge_and_score():
    assert "dg-football-asset--stacked" in FOOTBALL_ASSET_CSS
    assert "grid-template-columns: minmax(0, 1fr) !important" in WAIVERS_PRESENTATION_CSS or (
        "grid-template-columns: minmax(0, 1fr) !important" in WAIVERS_PRESENTATION_CSS
    )
    assert ".waiver-faab-block" in WAIVERS_PRESENTATION_CSS
    assert ".waiver-faab-block--compact" in WAIVERS_PRESENTATION_CSS
    assert "@media (max-width: 430px)" in WAIVERS_PRESENTATION_CSS
    assert "width: auto;" in WAIVERS_PRESENTATION_CSS
    assert "overflow-wrap: break-word" in FOOTBALL_ASSET_CSS


def test_waiver_card_avatar_ring_matches_dashboard_primitive():
    """Waivers page avatars share the Dashboard's exact circular vivid-green
    ring primitive (modules.daily_gm_briefing_ui's ``.dg-game-plan-card
    .dg-compact-asset-avatar.dg-tier-frame--ring`` rule) — same
    --color-success token, same border-radius:50%, same box-shadow formula —
    scoped to this page's own card classes (``.free-agent-card``/
    ``.free-agent-summary-card``) instead of the Dashboard's, since every
    other surface sharing football_assets.player_card_html's
    dg-player-portrait/dg-tier-frame--ring markup (Live Draft, Trade
    Analyzer, My Team, Trade Hub) must keep its existing per-tier ring."""

    assert ".free-agent-card .dg-player-portrait.dg-tier-frame--ring" in WAIVERS_PRESENTATION_CSS
    assert ".free-agent-summary-card .dg-player-portrait.dg-tier-frame--ring" in WAIVERS_PRESENTATION_CSS
    assert "--dg-tier-a: var(--color-success)" in WAIVERS_PRESENTATION_CSS
    assert "border-radius: 50% !important" in WAIVERS_PRESENTATION_CSS
    assert "word-break: normal" in FOOTBALL_ASSET_CSS
