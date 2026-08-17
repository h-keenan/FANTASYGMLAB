"""Token-backed styles for the canonical Football Asset presentation layer."""

FOOTBALL_ASSET_CSS = """

.dg-football-asset {
    position: relative;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: var(--space-md);
    align-items: center;
    min-width: 0;
    padding: var(--space-md) var(--space-lg);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-none);
    background: var(--color-surface-primary);
    color: var(--color-text-primary);
    box-shadow: var(--shadow-surface-inset);
}
.dg-football-asset--compact,
.dg-football-asset--dense { padding: var(--space-sm) var(--space-md); gap: var(--space-sm); }
.dg-football-asset--interactive { cursor: pointer; min-height: var(--touch-target-min); }
.dg-football-asset--interactive:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    box-shadow: var(--focus-ring);
}
.dg-football-asset__prestige-rail {
    position: absolute; inset: -1px auto -1px -1px; width: 3px; background: var(--color-prestige-depth);
}
.dg-football-asset__prestige-rail--elite { background: var(--color-prestige-elite); }
.dg-football-asset__prestige-rail--starter { background: var(--color-prestige-starter); }
.dg-football-asset__prestige-rail--contributor { background: var(--color-prestige-contributor); }
.dg-football-asset__prestige-rail--development { background: var(--color-prestige-development); }
.dg-football-asset__prestige-rail--replacement { background: var(--color-prestige-replacement); }
.dg-football-asset__avatar,
.dg-player-portrait {
    background: var(--color-surface-muted);
    border: var(--border-width-default) solid transparent;
    box-sizing: border-box;
    height: var(--size-asset-standard, 2.75rem);
    overflow: hidden;
    position: relative;
    width: var(--size-asset-standard, 2.75rem);
}
.dg-football-asset__avatar > *,
.dg-player-portrait > * { height: 100%; width: 100%; }
.dg-player-portrait .dg-player-headshot,
.dg-player-portrait .compact-player-avatar {
    --avatar-size: 100%;
    --dg-headshot-scale: 1;
    height: 100%;
    max-height: 100%;
    max-width: 100%;
    width: 100%;
}
.dg-player-portrait img,
.dg-player-portrait .dg-player-headshot-image {
    height: 100%;
    max-height: 100%;
    max-width: 100%;
    object-fit: contain;
    object-position: center bottom;
    transform: none;
    width: 100%;
}
.dg-player-portrait:has(img.dg-player-headshot-image) .dg-player-headshot-fallback,
.dg-player-portrait:has(.dg-player-headshot-image.is-loaded) .dg-player-headshot-fallback {
    opacity: 0;
    visibility: hidden;
}
.my-team-roster-core .dg-football-asset,
div[class*="st-key-my_team_roster_core"] .dg-football-asset {
    align-items: start;
    grid-template-columns: var(--size-roster-core-portrait) minmax(0, 1fr) auto;
}
.my-team-roster-core .dg-player-portrait,
div[class*="st-key-my_team_roster_core"] .dg-player-portrait {
    height: var(--size-roster-core-portrait);
    width: var(--size-roster-core-portrait);
}
.dg-football-asset__body { min-width: 0; }
.dg-football-asset__badges { display: flex; align-items: center; gap: var(--space-xs); flex-wrap: wrap; margin-top: var(--space-sm); }
.dg-football-asset__name { margin: var(--space-xs) 0 0; font: var(--font-card-title); overflow-wrap: break-word; word-break: normal; hyphens: none; }
.dg-football-asset__meta,
.dg-football-asset__insight { margin: var(--space-xs) 0 0; color: var(--color-text-muted); font-size: var(--font-size-caption); }
.dg-football-asset__value { text-align: right; font-variant-numeric: tabular-nums; }
.dg-football-asset--stacked {
    align-items: start;
    grid-template-columns: auto minmax(0, 1fr);
}
.dg-football-asset--stacked .dg-football-asset__value {
    grid-column: auto;
    justify-self: stretch;
    margin-top: var(--space-sm);
    text-align: left;
}
.dg-football-asset--stacked .dg-football-value { align-items: flex-start; }
.dg-football-prestige,
.dg-football-position,
.dg-football-team,
.dg-football-status,
.dg-football-injury {
    display: inline-flex; align-items: center; justify-content: center;
    min-height: 22px; padding: 0 var(--space-sm);
    border: var(--border-width-default) solid var(--color-border-strong);
    border-radius: var(--radius-none); font-size: var(--font-size-badge);
    font-weight: var(--font-weight-button); line-height: var(--line-height-badge);
    letter-spacing: var(--letter-spacing-badge); text-transform: uppercase;
}
.dg-football-prestige__rail { width: 3px; height: 12px; margin-right: var(--space-xs); background: currentColor; }
.dg-football-prestige--elite { color: var(--color-prestige-elite); }
.dg-football-prestige--starter { color: var(--color-prestige-starter); }
.dg-football-prestige--contributor { color: var(--color-prestige-contributor); }
.dg-football-prestige--development { color: var(--color-prestige-development); }
.dg-football-prestige--depth { color: var(--color-prestige-depth); }
.dg-football-prestige--replacement { color: var(--color-prestige-replacement); }
.dg-football-injury { width: 30px; min-width: 30px; padding: 0; text-align: center; }
.dg-football-injury--success { color: var(--color-success); border-color: var(--color-success); }
.dg-football-injury--caution { color: var(--color-warning); border-color: var(--color-warning); }
.dg-football-injury--danger { color: var(--color-danger); border-color: var(--color-danger); }
.dg-football-value { align-items: flex-end; display: inline-flex; flex-direction: column; gap: 0; line-height: 1.05; text-align: right; }
.dg-football-value__label { color: var(--color-text-muted); font: var(--type-supporting-metadata); text-transform: none; white-space: nowrap; }
.dg-football-value__number { color: var(--color-text-primary); font-size: var(--font-size-card-title); font-variant-numeric: tabular-nums; font-weight: var(--font-weight-display); white-space: nowrap; }
@media (max-width: 640px) {
    .dg-football-asset { grid-template-columns: auto minmax(0, 1fr); }
    .my-team-roster-core .dg-football-asset,
    div[class*="st-key-my_team_roster_core"] .dg-football-asset {
        grid-template-columns: var(--size-roster-core-portrait) minmax(0, 1fr);
    }
    .dg-football-asset__value { grid-column: 2; text-align: left; }
    .dg-football-asset--stacked .dg-football-asset__value { grid-column: auto; text-align: left; }
    .dg-football-asset__insight { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
}
@media (min-width: 64rem) {
    .my-team-roster-core .dg-football-asset,
    div[class*="st-key-my_team_roster_core"] .dg-football-asset {
        grid-template-columns: var(--size-roster-core-portrait-lg) minmax(0, 1fr) auto;
    }
    .my-team-roster-core .dg-player-portrait,
    div[class*="st-key-my_team_roster_core"] .dg-player-portrait {
        height: var(--size-roster-core-portrait-lg);
        width: var(--size-roster-core-portrait-lg);
    }
}
@media (prefers-reduced-motion: reduce) {
    .dg-football-asset { transition: none !important; }
}
"""
