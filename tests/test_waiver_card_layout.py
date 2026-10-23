from modules import football_assets


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
    # Mobile parity (PlayerIdentityRow.tsx metaRow): colored position badge
    # first, team as plain text, no inline age -- same rule for stacked and
    # non-stacked cards alike, so the old plain-text "QB · NO · Age 23" meta
    # string and the stacked-only text-position carve-out are both gone.
    assert html.index("dg-football-position--qb") < html.index("dg-football-asset__meta-team")
    assert "player-position-badge" in html
    assert ">QB<" in html
    assert ">NO<" in html
    assert "Age 23" not in html
    assert html.index("dg-football-asset__badges") < html.index("dg-football-asset__value")
    assert html.index("Best Available") < html.index("dg-football-asset__value")
    assert "title='Garrett Nussmeier'" in html
