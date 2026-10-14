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


def test_waiver_compact_rows_share_one_grouped_card():
    """App-parity pass (coridian_, 2026-10-13: "there isn't even a division
    between those two pills or modules... it just looks like one flowing
    module"): every section's compact rows now share one bordered/padded
    group container (mobile parity: WaiversScreen's AnimatedCard +
    compactGroupCard), not zero boundary and not a card per row."""

    assert 'div[class*="st-key-waiver_group_"]' in WAIVERS_PRESENTATION_CSS
    assert ".waiver-compact-row" in WAIVERS_PRESENTATION_CSS
    assert ".waiver-compact-row-trailing" in WAIVERS_PRESENTATION_CSS


def test_waiver_mobile_css_separates_badge_and_score():
    assert "dg-football-asset--stacked" in FOOTBALL_ASSET_CSS
    assert "grid-template-columns: minmax(0, 1fr) !important" in WAIVERS_PRESENTATION_CSS or (
        "grid-template-columns: minmax(0, 1fr) !important" in WAIVERS_PRESENTATION_CSS
    )
    assert ".waiver-faab-block" in WAIVERS_PRESENTATION_CSS
    assert ".waiver-faab-block--compact" in WAIVERS_PRESENTATION_CSS
    assert "@media (max-width: 430px)" in WAIVERS_PRESENTATION_CSS
    # Compact row redesign: Share is a small button filling its own narrow
    # st.columns slot (use_container_width=True in waivers_ui.py) beside
    # the compact row, not a separately-positioned full-width button that
    # needed a width:auto escape hatch — see div[data-testid="stButton"]
    # button's touch-target rule instead.
    assert 'div[data-testid="stButton"] button' in WAIVERS_PRESENTATION_CSS
    assert "overflow-wrap: break-word" in FOOTBALL_ASSET_CSS


def test_waiver_card_avatar_ring_is_circular_and_tier_derived():
    """Waiver Snapshot (football_assets.player_card_html, untouched by this
    pass) keeps its own circular vivid-green ring pin — same --color-success
    token, same border-radius:50%, same box-shadow formula the Dashboard's
    `.dg-game-plan-card .dg-compact-asset-avatar.dg-tier-frame--ring` rule
    uses, retrofit onto `.dg-player-portrait` (every other football_assets
    consumer — Live Draft, Trade Analyzer, My Team, Trade Hub — keeps its
    own per-tier ring untouched).

    Priority Adds/Stash/Watchlist/FAAB Shortlist render through the compact-
    row primitive instead (modules.compact_fantasy_assets.compact_asset_html's
    own avatar_ring=True flag). App-parity pass (coridian_, 2026-10-13: "I
    don't know what the green ring is behind the players... what is that
    green?"): that row's ring override no longer pins --dg-tier-a to a flat
    --color-success — compact_asset_html now resolves a real
    dg-tier-frame--{tier_id} class per player (matching mobile's
    PlayerAvatar.tsx resolvePlayerTier ring), so this rule only keeps the
    shape (circular) and box-shadow formula, not the color."""

    assert ".free-agent-summary-card .dg-player-portrait.dg-tier-frame--ring" in WAIVERS_PRESENTATION_CSS
    assert (
        'div[class*="st-key-waiver_recommendation_"] .dg-compact-asset-avatar.dg-tier-frame--ring'
        in WAIVERS_PRESENTATION_CSS
    )
    # Waiver Snapshot's own pin is untouched.
    assert "--dg-tier-a: var(--color-success)" in WAIVERS_PRESENTATION_CSS
    assert "border-radius: 50% !important" in WAIVERS_PRESENTATION_CSS
    assert "border-radius: 50%;" in WAIVERS_PRESENTATION_CSS
    # The compact-row rule itself (Priority Adds/Stash/Watchlist/FAAB
    # Shortlist) no longer pins a color — only the free-agent-summary-card
    # rule above still sets --dg-tier-a directly.
    compact_row_rule = WAIVERS_PRESENTATION_CSS.split(
        'div[class*="st-key-waiver_recommendation_"] .dg-compact-asset-avatar.dg-tier-frame--ring {'
    )[1].split("}")[0]
    assert "--dg-tier-a:" not in compact_row_rule
    assert "var(--color-success)" not in compact_row_rule
    assert "word-break: normal" in FOOTBALL_ASSET_CSS


def test_waiver_row_divider_uses_strong_border_token_for_contrast():
    """coridian_, 2026-10-13: "there needs to be some sort of dividing
    line in between those" — the hairline divider needs to clear the WCAG
    non-text-contrast floor against the grouped card's own surface, which
    --color-border alone does not (design_tokens.py's own comment on that
    token)."""

    row_rule = WAIVERS_PRESENTATION_CSS.split(
        'div[class*="st-key-waiver_recommendation_"] {'
    )[1].split("}")[0]
    assert "border-bottom: var(--border-width-default) solid var(--border-strong)" in row_rule


def test_waiver_row_divider_last_child_override_is_scoped_to_the_group():
    """A bare `div[class*=...]:last-child` never matches the genuinely
    last row: each row's own container renders as the ONLY child of its
    individual Streamlit layout wrapper, so it is trivially ":last-child"
    of that one-child parent on every row, zeroing the divider everywhere
    instead of only on the actual last row. The override must instead key
    off the shared group container's own children (true siblings)."""

    assert (
        'div[class*="st-key-waiver_group_"] > div:last-child '
        'div[class*="st-key-waiver_recommendation_"] {'
        in WAIVERS_PRESENTATION_CSS
    )
    # The old, broken bare selector must not still be present.
    assert 'div[class*="st-key-waiver_recommendation_"]:last-child {' not in WAIVERS_PRESENTATION_CSS


def test_waiver_share_button_overlays_row_bottom_right_instead_of_stacking_below():
    """coridian_, 2026-10-13: "the share button could be moved up to be
    level with the low confidence meter" — the Share button is taken out
    of normal flow and pinned to the row's own bottom-right corner so it
    lands over the same blank space the row's shorter trailing column
    (score/FAAB) already leaves above the row's taller main column's last
    line (the confidence meter), instead of stacking as a separate
    flow element below the whole row."""

    assert 'div[class*="st-key-waiver_recommendation_"] {\n    position: relative;\n}' in WAIVERS_PRESENTATION_CSS
    share_rule = WAIVERS_PRESENTATION_CSS.split(
        'div[class*="st-key-waiver_recommendation_"] div[data-testid="stElementContainer"][width="fit-content"] {'
    )[1].split("}")[0]
    assert "position: absolute" in share_rule
    assert "right: 0" in share_rule
    # No longer a flow sibling pushed down by align-self/margin-top.
    assert "align-self" not in share_rule
