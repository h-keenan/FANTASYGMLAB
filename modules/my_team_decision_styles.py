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
/* !important on Roster Core/Depth specifically — the pre-existing
   --size-roster-core-portrait rule these two containers used to inherit
   (football_asset_styles.py) is equal-specificity with the same
   `div[class*="st-key-..."] .dg-player-portrait` shape, and empirically
   keeps winning regardless of stylesheet order (Roster Decisions'
   identical-looking rule below has never had this problem because nothing
   upstream targets it at that specificity). Scoped to just these two new
   selectors so Roster Decisions' existing cascade is untouched. */
div[class*="st-key-my_team_decisions_"] .dg-player-portrait,
div[class*="st-key-my_team_decisions_"] .dg-football-asset__avatar {
    height: 4.25rem;
    width: 4.25rem;
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
div[class*="st-key-my_team_decisions_"] .dg-football-asset__value,
div[class*="st-key-my_team_roster_core"] .dg-football-asset__value,
div[class*="st-key-my_team_key_backups"] .dg-football-asset__value {
    grid-column: 2;
    text-align: left;
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
