"""Token-backed layout adapters for the canonical Waivers presentation."""

WAIVERS_PRESENTATION_CSS = """
.waiver-section-header .dg-ui-section-header {
    margin-bottom: var(--space-md);
}

/* Priority Adds / Stash Candidates / Watchlist Depth / FAAB Shortlist: one
   shared bordered/padded group card (mobile parity: WaiversScreen's
   AnimatedCard + styles.compactGroupCard) wraps every row in a section —
   not a standalone card per row, but not zero boundary between rows either
   (coridian_, 2026-10-13: "there isn't even a division between those two
   pills or modules... it just looks like one flowing module instead of a
   suggestion"). Same visual weight as this page's own
   .free-agent-summary-card/dg-ui-card family (surface-1 + standard border +
   panel radius), scoped to the group wrapper's own Streamlit container key
   so it never collides with the per-row key below (the row key is a
   substring of nothing here — "waiver_group_" vs "waiver_recommendation_"). */
div[class*="st-key-waiver_group_"] {
    background: var(--surface-1);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-panel);
    padding: var(--space-2xs) var(--space-sm);
}

/* Each row is modules.compact_fantasy_assets.compact_asset_html's compact
   player row (avatar ring, bold name, colored position pill + team) plus
   this module's own tier badge / trending pill / confidence meter /
   recommendation pill / score chrome (see waivers_ui.render_free_agent_cards),
   wrapped in its own Streamlit container so a per-row Share control can sit
   beside it without becoming a full-width row of its own. A hairline
   divider between rows (none after the last) replaces the old boxed
   decision-card so a dense list of rows reads as one grouped list, not a
   stack of individually-bordered cards. */
div[class*="st-key-waiver_recommendation_"] {
    border-bottom: var(--border-width-default) solid var(--color-border);
    min-height: var(--touch-target-min);
    padding: var(--space-xs) 0;
}

div[class*="st-key-waiver_recommendation_"]:last-child {
    border-bottom: 0;
}

/* compact_asset_html defaults to width:max-content outside its own narrow
   chip/trade contexts; a Waivers list row should span the full row width
   so the row's own trailing block sits flush with the row's right edge. */
div[class*="st-key-waiver_recommendation_"] .dg-compact-asset {
    width: 100%;
}

/* Mobile parity (WaiverRecommendationCard's compact branch): identity +
   chips + confidence on the left, score/recommendation/FAAB stacked on the
   right — see waivers_ui.render_free_agent_cards for the exact markup this
   targets. */
.waiver-compact-row {
    align-items: flex-start;
    display: flex;
    gap: var(--space-sm);
    width: 100%;
}

.waiver-compact-row-main {
    display: flex;
    flex: 1 1 auto;
    flex-direction: column;
    gap: var(--space-2xs);
    min-width: 0;
}

.waiver-compact-row-chips {
    align-items: center;
    column-gap: var(--space-2xs);
    display: flex;
    flex-wrap: wrap;
    row-gap: 2px;
}

.waiver-compact-row-trailing {
    align-items: flex-end;
    display: flex;
    flex: 0 0 auto;
    flex-direction: column;
    gap: 2px;
}

.waiver-compact-row-score-line {
    align-items: center;
    display: flex;
    gap: var(--space-2xs);
}

.waiver-compact-score {
    color: var(--color-accent);
    font: var(--font-card-title);
    font-variant-numeric: tabular-nums;
}

.waiver-compact-faab {
    color: var(--color-success);
    font: var(--type-supporting-metadata);
    white-space: nowrap;
}

/* Sleeper global trending-add pill — mobile parity with
   PlayerIdentityRow's trendingPill (accent-muted fill, accent text). */
.waiver-trending-pill {
    background: var(--surface-selected);
    border-radius: var(--radius-pill);
    color: var(--color-accent);
    font: var(--type-supporting-metadata);
    letter-spacing: var(--letter-spacing-badge);
    padding: 1px var(--space-xs);
    white-space: nowrap;
}

/* Same circular ring the Dashboard's Game Plan cards use for shape
   (border-radius:50%, matching box-shadow formula), but — unlike
   Dashboard, which deliberately wants one uniform accent regardless of
   player — Waivers now lets the real per-tier color show through:
   compact_asset_html's avatar_ring=True already adds a
   dg-tier-frame--{tier_id} class (resolved from the row's own player_tier),
   so this override no longer pins --dg-tier-a to --color-success (coridian_,
   2026-10-13: "I don't know what the green ring is behind the players...
   what is that green?"). */
div[class*="st-key-waiver_recommendation_"] .dg-compact-asset-avatar.dg-tier-frame--ring {
    border-radius: 50%;
    box-shadow: 0 0 0 3px var(--dg-tier-a), 0 0 4px 0 color-mix(in srgb, var(--dg-tier-a) 30%, transparent);
}

/* Defensive clamp — an unusually long player name still fits the compact
   row's height budget instead of pushing it taller. */
div[class*="st-key-waiver_recommendation_"] .dg-compact-asset-name {
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    display: -webkit-box;
    overflow: hidden;
}

/* Share: a small, right-aligned button under the compact row, not a
   full-width row of its own. st.columns was tried first and discarded —
   Streamlit auto-stacks columns on narrow viewports, which turns a "small
   column" right back into a full-width row on exactly the 390px target
   this redesign is for — so this is CSS-only instead, the same approach
   the prior full-decision-card already used for this exact button.
   use_container_width=False already makes Streamlit size the Share
   button's own element-container to width:fit-content (its
   data-testid="stElementContainer" carries a matching width="fit-content"
   attribute); the row's own container is a column flexbox
   (.stVerticalBlock), so align-self:flex-end pushes that already-shrunk
   box to the right edge without touching the tap-grid row's own
   full-width element-container next to it. */
div[class*="st-key-waiver_recommendation_"] div[data-testid="stElementContainer"][width="fit-content"] {
    align-self: flex-end;
    margin-top: var(--space-2xs);
}

div[class*="st-key-waiver_recommendation_"] div[data-testid="stButton"] button {
    min-height: var(--touch-target-min);
}

.waiver-faab-block dt {
    align-items: center;
    color: var(--color-text-muted);
    display: flex;
    font-size: var(--font-size-badge);
    gap: var(--space-xs);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.waiver-faab-block dt .dg-glyph {
    margin-right: 0;
}

.waiver-faab-block dd {
    /* FAAB bid dollars are a concrete, positive recommendation, not a caution
       flag — match the mobile FAABGuidance correction (green, not amber). */
    color: var(--color-success);
    font: var(--font-card-title);
    margin: var(--space-2xs) 0 0;
}

.waiver-faab-block p {
    color: var(--color-text-secondary);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    margin: var(--space-2xs) 0 0;
}

.waiver-faab-block--compact {
    margin-top: var(--space-xs);
}

/* Waiver Snapshot: a separate, already-compact "Best Available by
   position" grid (render_free_agent_summary_cards) — untouched by the
   Priority Adds/Stash/Watchlist/FAAB Shortlist compact-row redesign
   above, since it was never the repeating dense list the redesign targets. */
.waiver-snapshot-avatar {
    border-radius: var(--radius-none);
    height: var(--size-roster-core-portrait);
    width: var(--size-roster-core-portrait);
}

.waiver-snapshot-avatar img {
    height: 100%;
    object-fit: cover;
    width: 100%;
}

.free-agent-summary-card {
    border-color: var(--color-border) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-surface-inset) !important;
    clip-path: none !important;
    opacity: 0.96;
}

/* Waiver Snapshot still renders through football_assets.player_card_html
   unchanged (see the comment above), so it keeps the exact green-ring
   override that card markup already had before this redesign — same
   circular vivid-green ring the Dashboard's Game Plan cards use
   (modules/daily_gm_briefing_ui.py's `.dg-game-plan-card .dg-compact-
   asset-avatar.dg-tier-frame--ring` rule): same --color-success token,
   same border-radius:50%, same box-shadow formula, just retargeted at
   football_assets' own `.dg-player-portrait` avatar container (which
   needs the !important/overflow/border overrides below to win against
   that shared component's own styles — every other football_assets
   consumer, e.g. Live Draft/Trade Analyzer/My Team/Trade Hub, keeps its
   existing per-tier ring untouched). */
.free-agent-summary-card .dg-player-portrait.dg-tier-frame--ring {
    --dg-tier-a: var(--color-success);
    border: var(--border-width-default) solid transparent !important;
    border-radius: 50% !important;
    box-shadow: 0 0 0 3px var(--dg-tier-a), 0 0 4px 0 color-mix(in srgb, var(--dg-tier-a) 30%, transparent) !important;
    overflow: hidden !important;
}

.free-agent-summary-grid {
    display: grid;
    gap: var(--space-sm);
    grid-template-columns: minmax(0, 1fr);
    margin: var(--space-sm) 0;
}

@media (min-width: 72rem) {
    .free-agent-summary-grid {
        /* auto-fit so a single remaining free agent doesn't leave a blank
           second column on the summary row. */
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }
}

@media (min-width: 90rem) {
    .free-agent-summary-grid {
        /* auto-fit so 1-2 available targets don't leave a blank trailing
           column on wide desktop viewports. */
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }
}

@media (max-width: 700px) {
    .free-agent-summary-grid {
        grid-template-columns: minmax(0, 1fr) !important;
    }

    .dg-football-asset.free-agent-summary-card {
        align-items: start;
        grid-template-columns: auto minmax(0, 1fr);
    }

    .dg-football-asset.free-agent-summary-card .dg-football-asset__value {
        grid-column: 1 / -1;
        margin-top: var(--space-sm);
        text-align: left;
    }

    .dg-football-asset.free-agent-summary-card .dg-football-asset__name {
        hyphens: none;
        overflow-wrap: break-word;
        word-break: normal;
    }

    .waiver-faab-block {
        margin-top: var(--space-xs);
    }
}

@media (max-width: 430px) {
    div[class*="st-key-waiver_recommendation_"] {
        padding: var(--space-2xs) 0;
    }
}

@media (max-width: 390px) {
    div[class*="st-key-waiver_recommendation_"] .dg-compact-asset-name {
        -webkit-line-clamp: 1;
    }
}
"""
