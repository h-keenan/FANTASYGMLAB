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
   stack of individually-bordered cards. coridian_, 2026-10-13: "there needs
   to be some sort of dividing line in between those" — --color-border (the
   default hairline) barely clears 1.4:1 against this group card's own
   --surface-1 background, well under the 3:1 WCAG non-text-contrast floor
   design_tokens.py's own comment calls out for exactly this boundary role,
   so it reads as almost invisible once the grouped card gives rows a
   shared background instead of floating on page bg. --color-border-strong
   (3.46-4.26:1 against raised/secondary/bg surfaces per that same token
   comment) is the token this codebase already reserves for "an edge that
   must read as intentional" — use it here via the --border-strong semantic
   alias instead of inventing a one-off color. */
div[class*="st-key-waiver_recommendation_"] {
    border-bottom: var(--border-width-default) solid var(--border-strong);
    min-height: var(--touch-target-min);
    padding: var(--space-xs) 0;
}

/* coridian_, 2026-10-13: "there needs to be some sort of dividing line in
   between those" — turned out not to be a contrast problem alone: this
   plain `:last-child` selector never matched the actual last row. Each row
   (st.container(key=f"waiver_recommendation_...")) renders as the ONLY
   child of its own individual Streamlit stLayoutWrapper div, so the row's
   own div is trivially ":last-child" of ITS one-child parent on every
   single row — silently zeroing the divider for the whole list, not just
   the last row. Scoping off the shared group container's own children
   (each one of THOSE wrapper divs is a true sibling of every other row's
   wrapper) is what correctly isolates the genuinely last row instead. */
div[class*="st-key-waiver_group_"] > div:last-child div[class*="st-key-waiver_recommendation_"] {
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

/* "NN OVR" pill — web counterpart to mobile's OverallRatingBadge.tsx (see
   waivers_ui.waiver_overall_rating_badge_html for the Python side that
   builds this markup and picks --waiver-ovr-tint). coridian_, 2026-10-13:
   "I have no clue what the 78/71 and 55 mean... that should be [a labeled
   badge] like the app" — the bare value-score number this chip sits next
   to stays as-is; this badge is the missing OVR context. --waiver-ovr-tint
   is either a literal color-mix() between this app's own danger/premium/
   success tokens (continuous ramp, not 3 flat bands — matches mobile's
   percentileColor) or, for a top-5 league-wide positional rank, one of the
   gold/silver/bronze prestige tokens player_quick_view_styles.py's own
   .pqv-accolade--gold/-silver/-bronze chips already use. */
.waiver-ovr-badge {
    align-items: center;
    background: color-mix(in srgb, var(--waiver-ovr-tint) 18%, transparent);
    border: var(--border-width-default) solid color-mix(in srgb, var(--waiver-ovr-tint) 48%, transparent);
    border-radius: var(--radius-pill);
    color: var(--waiver-ovr-tint);
    display: inline-flex;
    font: var(--type-supporting-metadata);
    font-weight: 700;
    gap: 2px;
    letter-spacing: var(--letter-spacing-badge);
    padding: 1px var(--space-xs);
    white-space: nowrap;
}

/* Crowned (top-5 league-wide positional rank) variant — mobile's
   OverallRatingBadge swaps its usual beside-the-number crown for one
   stacked above the rating so the whole module reads as a distinct
   "league-wide rank" signal, not just a recolored ordinary pill. */
.waiver-ovr-badge--crowned {
    align-items: center;
    flex-direction: column;
    gap: 1px;
    padding-top: 2px;
}

.waiver-ovr-badge-crown {
    height: 10px;
    width: 10px;
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

/* Share: a small, right-aligned button overlaid on the compact row's own
   bottom-right corner, not a full-width row of its own. st.columns was
   tried first and discarded — Streamlit auto-stacks columns on narrow
   viewports, which turns a "small column" right back into a full-width row
   on exactly the 390px target this redesign is for — so this is CSS-only
   instead, the same approach the prior full-decision-card already used for
   this exact button.

   Originally a flow sibling stacked *below* the tap-grid row content
   (align-self:flex-end + margin-top only), which — combined with
   Streamlit's own ~16px inter-element gap inside this column flexbox, plus
   the row's own trailing score/FAAB column being shorter than its 3-line
   main column (identity/chips/confidence) and so leaving blank space of
   its own above that gap — put the button noticeably below the whole row
   instead of beside any part of it (coridian_, 2026-10-13: "the share
   button could be moved up to be level with the low confidence meter").
   Taking it out of flow entirely and pinning it to the row's own
   bottom-right corner instead means it sits over the same "blank space
   below a shorter trailing column" area the old flow approach left empty —
   which is also where the main column's own last line (the confidence
   meter) ends — so the two land level with each other by construction,
   without hand-tuning a fixed offset that would only hold for one specific
   row's line count. use_container_width=False still makes Streamlit size
   the Share button's own element-container to width:fit-content (its
   data-testid="stElementContainer" carries a matching width="fit-content"
   attribute). */
div[class*="st-key-waiver_recommendation_"] {
    position: relative;
}

div[class*="st-key-waiver_recommendation_"] div[data-testid="stElementContainer"][width="fit-content"] {
    bottom: var(--space-xs);
    position: absolute;
    right: 0;
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

/* Waiver Snapshot: the Best Available by position wire-scan grid
   (render_free_agent_summary_cards). coridian_, 2026-10-14: these cards
   take up too much space and look bad -- brought down to the same
   compact density the Priority Adds/Stash/Watchlist/FAAB Shortlist rows
   already got in the prior redesign pass. No explicit height/width rule is set on
   .waiver-snapshot-avatar on purpose: football_asset_styles.py's shared
   .dg-player-portrait>.waiver-snapshot-avatar rule already forces this
   inner element to fill its outer .dg-player-portrait container at
   height/width:100% !important, so the real size is controlled entirely
   by the outer portrait's own size -- which player_card_html's
   density=compact call below now resolves to the shared
   --size-asset-standard token (2.75rem/44px, the same avatar size the
   compact Priority Adds rows already use), not the old density=standard
   call's --size-roster-core-portrait (5.5rem/88px, the full-width hero
   size My Team's roster-core card uses). Setting a competing size here
   would just be dead weight the !important rule always wins over. */
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

/* The trailing slot now holds a small NN OVR badge
   (waiver_overall_rating_badge_html), not the old raw dynasty/value-score
   number -- so it no longer needs its own reserved grid column (a
   reserved trailing column is what clipped a trailing element on My Team
   in an earlier regression, once a narrow viewport's grid ran out of room
   for it). Two
   columns only (avatar, body) at every width, with the badge floated via
   position:absolute instead -- the same pattern this stylesheet's own
   Share button already uses for a trailing element it doesn't want to
   reserve column space for. */
.dg-football-asset.free-agent-summary-card {
    grid-template-columns: auto minmax(0, 1fr);
}

.dg-football-asset.free-agent-summary-card .dg-football-asset__value {
    margin: 0;
    position: absolute;
    right: var(--space-sm);
    text-align: right;
    top: var(--space-sm);
}

/* The shared football_asset_styles.py rule for this literal h3
   (.dg-football-asset__name{font:var(--font-card-title)}) loses to
   Streamlit's own scoped heading rule whenever this grid falls back to a
   plain st.markdown render (no resolvable player_id to drive the tappable
   grid component), the same class-plus-h3-tag-outranks-a-single-class gap
   already fixed on Live Draft (see live_draft_styles.py). Without this
   module-scoped, equal-or-higher-specificity override the Waiver Snapshot
   player name renders at Streamlit's native ~28px/600-weight h3 size
   instead of the compact card-title size every other surface shows. */
.free-agent-summary-card .dg-football-asset__name {
    font: var(--font-card-title) !important;
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
