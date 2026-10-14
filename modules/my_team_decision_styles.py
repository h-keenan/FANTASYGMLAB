"""My Team decision-first IA styles — route-owned, not APP_CSS.

Plain CSS only, no embedded ``<style>`` tag: ``modules.html_rendering.
normalized_style_block`` (what ``inject_global_styles`` calls) wraps this
whole string in exactly one ``<style>...</style>`` itself. An extra
``<style>`` tag inside the string (as this file briefly had) makes a
browser's raw-text parser for ``<style>`` stop at that FIRST inner
``</style>``, truncating every rule after it and leaving a stray literal
``<style>`` token inside the live stylesheet text — so none of this file's
own selectors (ring gauge, strategy identity, decision-card rows, ...) ever
actually applied. Keep this file single-wrapped, matching
``modules.player_quick_view_styles.PLAYER_QUICK_VIEW_CSS``'s pattern.
"""

MY_TEAM_DECISION_CSS = """
div[class*="st-key-my_team_alerted_player_focus"] {
    background: color-mix(in srgb, var(--color-warning) 7%, var(--color-surface));
    border: var(--border-width-default) solid color-mix(in srgb, var(--color-warning) 52%, transparent);
    border-radius: var(--radius-panel);
    padding: var(--space-md);
}
div[class*="st-key-my_team_alerted_player_focus"] .player-support-chip-warning {
    background: color-mix(in srgb, var(--color-warning) 18%, transparent);
    border-color: color-mix(in srgb, var(--color-warning) 55%, transparent);
    color: var(--color-warning);
}
.my-team-strategy-identity {
    display: flex;
    flex-direction: column;
    gap: var(--space-2xs);
    margin: 0 0 var(--space-sm);
    max-width: 100%;
    min-width: 0;
}
.my-team-strategy-kicker {
    color: var(--color-text-muted);
    font: var(--type-supporting-metadata);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.my-team-strategy-primary {
    color: var(--color-text-primary);
    font: var(--type-section-title);
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.my-team-strategy-support {
    color: var(--color-text-muted);
    font: var(--type-supporting-metadata);
    line-height: var(--line-height-caption);
    overflow-wrap: anywhere;
}
.my-team-strategy-note {
    color: var(--color-text-muted);
    font: var(--type-supporting-metadata);
    line-height: var(--line-height-caption);
    max-width: 36rem;
}
.st-key-my_team_strategy_gateway [data-testid="stVerticalBlock"] {
    gap: var(--space-xs);
}
.st-key-my_team_strategy_panel {
    margin: 0 0 var(--space-md);
}
/* Team Snapshot — Team Value ring gauge + archetype/power-rank meta,
   matching mobile's My Team Overview header card. Ring is the same
   conic-gradient + punched-out-center technique as player_quick_view's
   .pqv-ovr-ring, own namespace since this is a team-level (not
   player-level) metric. */
.st-key-my_team_team_snapshot {
    margin: 0 0 var(--space-sm);
}
.mt-team-snapshot {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-sm) var(--space-md);
}
.mt-value-ring-wrap {
    display: grid;
    gap: var(--space-2xs);
    justify-items: center;
}
.mt-value-ring {
    --mt-value-tone: var(--color-action);
    align-items: center;
    background: conic-gradient(var(--mt-value-tone) calc(var(--mt-value-pct, 0) * 1%), var(--color-border) 0);
    border-radius: 50%;
    display: grid;
    height: 4rem;
    place-items: center;
    position: relative;
    width: 4rem;
}
.mt-value-ring::after {
    background: var(--surface-1);
    border-radius: 50%;
    content: '';
    inset: 0.5rem;
    position: absolute;
}
.mt-value-ring-value {
    color: var(--mt-value-tone);
    font-size: var(--font-size-card-title);
    font-variant-numeric: tabular-nums;
    font-weight: var(--font-weight-display);
    position: relative;
    z-index: 1;
}
.mt-value-ring-label {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.mt-value-ring--low {
    --mt-value-tone: var(--color-danger);
}
.mt-value-ring--mid {
    --mt-value-tone: var(--color-action);
}
.mt-value-ring--high {
    --mt-value-tone: var(--color-success);
}
.mt-team-snapshot-meta {
    display: grid;
    gap: var(--space-2xs);
    min-width: 0;
}
.mt-team-snapshot-power,
.mt-team-snapshot-value {
    color: var(--color-text-secondary);
    font-size: var(--font-size-body);
}
.st-key-my_team_roster_decisions .compact-player-row,
.st-key-my_team_roster_decisions .dg-football-asset--dense,
div[class*="st-key-my_team_roster_core"] .compact-player-row,
div[class*="st-key-my_team_key_backups"] .compact-player-row {
    min-height: 0;
}
/* Roster Core/Depth previously rendered at football_asset_styles.py's
   --size-roster-core-portrait (5.5rem/88px — "sized for full-width
   contexts like My Team" per trade_analyzer_styles.py's own comment on
   that token), noticeably larger than every other player-row section on
   this exact page (Untouchables/Trade Candidates/Hold/Drop already compact
   to 4.25rem below). coridian_, 2026-10-13: "you don't want to have like
   two players taking up your whole screen whenever you want to see your
   whole team" — this is that oversized avatar, not just extra text; same
   4.25rem compacting as Roster Decisions, reused here rather than a third
   size value, so every player row on My Team now shares one density. */
/* coridian_, 2026-10-13, from a live production screenshot of Hold
   Candidates: wasted space on the right side under and above the player
   name — the generic <=700px collapse below (football_asset_styles.py's
   `.dg-football-asset{grid-template-columns:...minmax(0,1fr)}` media rule)
   folds the value chip under the name/badges, leaving the whole right
   side of every card empty.

   First attempt reserved a persistent 3rd grid column (avatar | identity
   | value) for the chip, matching mobile's RosterPlayerRow trailing value
   column. Measured regression (coridian_, same day, follow-up report):
   that 3rd column's auto width (sized to fit "Value Score 2,888" etc,
   roughly 100-110px of a ~365px mobile card) squeezed the identity column
   down to ~150px, which made the "Why:" paragraph's existing
   -webkit-line-clamp:2 cut off after only a few words instead of its
   previous near-full-width allowance — reported as "the why is now
   clipping." Reverted to the same 2-column template Roster Core/Depth use
   (identity gets the full remaining width again) and moved the value chip
   out of grid flow entirely below instead, so it floats over the identity
   column's top-right corner rather than reserving width from it. */
div[class*="st-key-my_team_decisions_"] .dg-football-asset,
.st-key-my_team_roster_decisions .dg-football-asset {
    align-items: start;
    grid-template-columns: 4.25rem minmax(0, 1fr);
}
div[class*="st-key-my_team_roster_core"] .dg-football-asset,
div[class*="st-key-my_team_key_backups"] .dg-football-asset {
    align-items: start !important;
    grid-template-columns: 4.25rem minmax(0, 1fr) !important;
}
/* !important required here too — measured directly (getComputedStyle) on
   coridian_'s 2026-10-13 Hold Candidates report: the un-scoped
   `.dg-football-asset.compact-player-row .dg-player-portrait` rule in
   football_asset_styles.py (3 class selectors, specificity 0-3-0) beats
   this attribute+class selector (0-2-0) regardless of sheet order, so the
   avatar rendered at the un-overridden --size-roster-core-portrait
   (5.5rem/88px) instead of the intended 4.25rem/68px — 20px wider than its
   reserved 4.25rem grid-template-columns track above, bleeding over the
   name column and visually covering each name's first 1-2 characters
   (Jalen Coker renders as alen Coker, Ty Simpson renders as y Simpson).
   This is the exact same specificity fight the comment below already documents
   for Roster Core/Depth — Roster Decisions just never got the matching
   !important when those sections were compacted to 4.25rem. */
div[class*="st-key-my_team_decisions_"] .dg-player-portrait,
div[class*="st-key-my_team_decisions_"] .dg-football-asset__avatar {
    height: 4.25rem !important;
    width: 4.25rem !important;
}
div[class*="st-key-my_team_roster_core"] .dg-player-portrait,
div[class*="st-key-my_team_roster_core"] .dg-football-asset__avatar,
div[class*="st-key-my_team_key_backups"] .dg-player-portrait,
div[class*="st-key-my_team_key_backups"] .dg-football-asset__avatar {
    height: 4.25rem !important;
    width: 4.25rem !important;
}
div[class*="st-key-my_team_decisions_"] .dg-player-portrait.dg-tier-frame,
div[class*="st-key-my_team_roster_core"] .dg-player-portrait.dg-tier-frame,
div[class*="st-key-my_team_key_backups"] .dg-player-portrait.dg-tier-frame {
    box-shadow: 0 0 0 2px var(--dg-tier-a), 0 0 8px 1px color-mix(in srgb, var(--dg-tier-a) 48%, transparent);
}
div[class*="st-key-my_team_roster_core"] .dg-football-asset__value,
div[class*="st-key-my_team_key_backups"] .dg-football-asset__value {
    grid-column: 2;
    text-align: left;
}
/* Value chip floats in the card's top-right corner instead of taking a
   reserved grid column (see the reverted-to-2-column comment above for
   why a dedicated column squeezed the Why text). `.dg-football-asset`
   already sets `position:relative` as a base style (football_asset_styles.
   py), so this positions against the card's own padding box — matching
   the Waivers Share-button fix (PR #1027) that used the same
   flow-sibling-to-absolute technique to align a trailing element without
   stealing width from the row next to it. */
div[class*="st-key-my_team_decisions_"] .dg-football-asset__value {
    position: absolute;
    top: var(--space-md);
    right: var(--space-lg);
    text-align: right;
}
/* coridian_, 2026-10-14, reviewing Untouchables/Trade/Hold/Drop: the
   prestige tier should read on all four sides, not just the left. The
   shared football_assets.player_card_html() always emits a
   .dg-football-asset__prestige-rail span (football_asset_styles.py), but
   that primitive is a plain 3px left-edge bar everywhere it is used across
   the app (Roster Core, Depth, Waivers, Trade Hub, GM Targets, Dashboard,
   ...), not something unique to this section. Scoped to Roster Decisions
   only rather than changed globally — this request was phrased while
   looking at these four specific card sections, and AGENTS.md calls for
   implementing only the requested scope. The left-only rail still renders
   identically everywhere else on the app; see the PR description for the
   follow-up decision coridian_ can make on a global pass. Border width
   doubled (3px to match the original rail's visual weight, outset 2px
   past the card's own border) rather than reusing `background`, since a
   background can not trace an outline around all four edges of a box. */
div[class*="st-key-my_team_decisions_"] .dg-football-asset__prestige-rail {
    inset: -2px !important;
    width: auto !important;
    height: auto !important;
    background: transparent !important;
    border: 3px solid var(--color-prestige-depth) !important;
    pointer-events: none;
}
div[class*="st-key-my_team_decisions_"] .dg-football-asset__prestige-rail--elite {
    border-color: var(--color-prestige-elite) !important;
    background: transparent !important;
}
div[class*="st-key-my_team_decisions_"] .dg-football-asset__prestige-rail--starter {
    border-color: var(--color-prestige-starter) !important;
    background: transparent !important;
}
div[class*="st-key-my_team_decisions_"] .dg-football-asset__prestige-rail--contributor {
    border-color: var(--color-prestige-contributor) !important;
    background: transparent !important;
}
div[class*="st-key-my_team_decisions_"] .dg-football-asset__prestige-rail--development {
    border-color: var(--color-prestige-development) !important;
    background: transparent !important;
}
div[class*="st-key-my_team_decisions_"] .dg-football-asset__prestige-rail--replacement {
    border-color: var(--color-prestige-replacement) !important;
    background: transparent !important;
}
/* Reserve room for the floating value chip on the name's own line(s) —
   stress-tested with an unusually long name ("Christian McCaffreyington-
   Worthington") that wraps to 2 lines: without this, the wrapped second
   line runs directly under the chip. Scoped to the name only (meta/badges/
   insight sit below the chip's ~2rem height on every real roster name, so
   they don't need the reserve and keep their full width). */
div[class*="st-key-my_team_decisions_"] .dg-football-asset__name {
    padding-right: 7.5rem;
}
/* coridian_, 2026-10-13 (after seeing the trimmed card): "the name takes
   up too much space and everything underneath the name can be moved up so
   that there's not so much space underneath the player picture." The name/
   meta/badges/value stack below the avatar still used
   football_asset_styles.py's default vertical rhythm
   (name/meta margin-top: --space-xs/4px each, badges margin-top:
   --space-sm/8px) — generous for a full decision-card with a reason
   paragraph underneath, but this row has only 3 short lines now, so that
   same rhythm reads as excess air beneath a ~4.25rem/68px avatar. Tightened
   to --space-2xs/2px throughout, scoped to Roster Core/Depth only — every
   other --dg-football-asset context (Live Draft, Trade Analyzer, Roster
   Decisions, Waivers) keeps the original spacing untouched. */
div[class*="st-key-my_team_roster_core"] .dg-football-asset__name,
div[class*="st-key-my_team_roster_core"] .dg-football-asset__meta,
div[class*="st-key-my_team_key_backups"] .dg-football-asset__name,
div[class*="st-key-my_team_key_backups"] .dg-football-asset__meta {
    margin-top: var(--space-2xs) !important;
}
div[class*="st-key-my_team_roster_core"] .dg-football-asset__badges,
div[class*="st-key-my_team_key_backups"] .dg-football-asset__badges {
    margin-top: var(--space-2xs) !important;
}
/* coridian_, 2026-10-13: name still too tall. football_assets.player_card_html
   emits the name as a literal h3 tag, which Streamlit's own runtime
   auto-enhances with its native heading-anchor-link behavior and its own
   much larger default heading font-size, overriding the intended
   font:var(--font-card-title) (14px) and wrapping a short player name onto
   two lines. Forced back to the intended size here; every other
   dg-football-asset__name context is untouched. */
div[class*="st-key-my_team_roster_core"] .dg-football-asset__name,
div[class*="st-key-my_team_key_backups"] .dg-football-asset__name {
    font: var(--font-card-title) !important;
}
/* Same h3-auto-enhancement bug as Roster Core/Depth above, confirmed here
   too via getComputedStyle (28px/33.6px instead of the intended 14px
   --font-card-title) on coridian_'s 2026-10-13 Hold Candidates report —
   PR #1034 scoped its fix to Roster Core/Depth only and never covered
   Roster Decisions (Untouchables/Trade Candidates/Hold/Drop). */
div[class*="st-key-my_team_decisions_"] .dg-football-asset__name {
    font: var(--font-card-title) !important;
}
.st-key-my_team_decisions_hold .dg-football-asset__insight,
.st-key-my_team_decisions_untouchables .dg-football-asset__insight {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
}
.st-key-my_team_decisions_drop .dg-football-asset__insight {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 1;
    overflow: hidden;
}
.st-key-my_team_decisions_trade .dg-football-asset__insight {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    overflow: hidden;
}
.summary-tile-unavailable,
.st-key-my_team_roster_signals .summary-tile-unavailable {
    opacity: 0.58;
}
.summary-tile-unavailable .summary-tile-value {
    color: var(--color-text-muted);
    font-weight: var(--font-weight-body);
}
.st-key-my_team_roster_signals,
.st-key-my_team_roster_decisions {
    margin: 0 0 var(--space-sm);
}
/* "NN OVR" pill — Roster Core/Depth's compact row (player_cards.
   overall_rating_badge_html), same visual language as Waivers' own OVR
   badge (waivers_presentation_styles.py's .waiver-ovr-badge): a continuous
   red->gold->green tint via --dg-ovr-tint, not page-specific class names,
   since this badge is a shared player_cards.py primitive any compact row
   can opt into. */
.dg-ovr-badge {
    align-items: center;
    background: color-mix(in srgb, var(--dg-ovr-tint) 18%, transparent);
    border: var(--border-width-default) solid color-mix(in srgb, var(--dg-ovr-tint) 48%, transparent);
    border-radius: var(--radius-pill);
    color: var(--dg-ovr-tint);
    display: inline-flex;
    font: var(--type-supporting-metadata);
    font-weight: 700;
    letter-spacing: var(--letter-spacing-badge);
    padding: 1px var(--space-xs);
    white-space: nowrap;
}
.dg-ovr-badge--crowned {
    align-items: center;
    flex-direction: column;
    gap: 1px;
    padding-top: 2px;
}
.dg-ovr-badge-crown {
    height: 10px;
    width: 10px;
}
.st-key-my_team_strategy_panel .dg-ui-section-header,
div[class*="st-key-my_team_"] .dg-ui-section-header {
    margin: var(--space-sm) 0 var(--space-xs) !important;
    padding-bottom: var(--space-2xs) !important;
}
@media (max-width: 430px) {
    .my-team-strategy-primary {
        font-size: 1.05rem;
    }
    .st-key-my_team_roster_decisions .dg-football-asset__body {
        min-width: 0;
    }
}
"""
