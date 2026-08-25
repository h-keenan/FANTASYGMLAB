"""Token-backed styles for the canonical Football Asset presentation layer."""

from modules.portrait_normalization import card_focus_x

FOOTBALL_ASSET_CSS = """
.dg-football-asset{position:relative;display:grid;grid-template-columns:auto minmax(0, 1fr) auto;gap:var(--space-md);align-items:center;min-width:0;padding:var(--space-md) var(--space-lg);border:var(--border-width-default) solid var(--color-border);border-radius:var(--radius-none);background:var(--color-surface-primary);color:var(--color-text-primary);box-shadow:var(--shadow-surface-inset)}
.dg-football-asset--compact,.dg-football-asset--dense{padding:var(--space-sm) var(--space-md);gap:var(--space-sm)}
.dg-football-asset--interactive{cursor:pointer;min-height:var(--touch-target-min)}
.dg-football-asset--interactive:focus-visible{outline:2px solid var(--color-accent);outline-offset:2px;box-shadow:var(--focus-ring)}
.dg-football-asset__prestige-rail{position:absolute;inset:-1px auto -1px -1px;width:3px;background:var(--color-prestige-depth)}
.dg-football-asset__prestige-rail--elite{background:var(--color-prestige-elite)}
.dg-football-asset__prestige-rail--starter{background:var(--color-prestige-starter)}
.dg-football-asset__prestige-rail--contributor{background:var(--color-prestige-contributor)}
.dg-football-asset__prestige-rail--development{background:var(--color-prestige-development)}
.dg-football-asset__prestige-rail--replacement{background:var(--color-prestige-replacement)}
.dg-football-asset__avatar,.dg-player-portrait{background:var(--color-surface-muted);border:var(--border-width-default) solid transparent;box-sizing:border-box;height:var(--size-asset-standard, 2.75rem);overflow:hidden;position:relative;width:var(--size-asset-standard, 2.75rem)}
.dg-football-asset .compact-player-avatar,.dg-player-portrait .compact-player-avatar{--avatar-size:100%;align-self:stretch;flex:none;height:100%;max-height:100%;max-width:100%;width:100%}
.dg-football-asset__avatar>*,.dg-player-portrait>*{height:100%;width:100%}
.dg-player-portrait>.dg-player-headshot,.dg-player-portrait>.compact-player-avatar,.dg-player-portrait>.player-avatar,.dg-player-portrait>.free-agent-avatar,.dg-player-portrait>.waiver-snapshot-avatar,.dg-player-portrait>.player-quick-view-avatar{--avatar-size:100% !important;align-self:stretch !important;border-radius:0 !important;box-sizing:border-box !important;flex:none !important;height:100% !important;max-height:none !important;max-width:none !important;min-height:0 !important;min-width:0 !important;width:100% !important}
.dg-player-portrait>.dg-player-headshot::before,.dg-player-portrait>.free-agent-avatar::before,.dg-player-portrait>.player-avatar::before,.dg-player-portrait>.compact-player-avatar::before{content:none !important}
.dg-player-portrait .dg-player-headshot,.dg-player-portrait .compact-player-avatar{--avatar-size:100%;height:100%;max-height:100%;max-width:100%;width:100%}
.dg-player-portrait img,.dg-player-portrait .dg-player-headshot-image{height:100% !important;inset:0 !important;left:0 !important;max-height:none !important;max-width:none !important;object-fit:cover !important;object-position:var(--dg-headshot-focus-x,44%) var(--dg-headshot-focus,18%) !important;position:absolute !important;top:0 !important;transform:scale(1.16);transform-origin:var(--dg-headshot-focus-x,44%) var(--dg-headshot-focus,18%);width:100% !important}
.dg-player-portrait:has(img.dg-player-headshot-image) .dg-player-headshot-fallback,.dg-player-portrait:has(.dg-player-headshot-image.is-loaded) .dg-player-headshot-fallback{opacity:0;visibility:hidden}
.dg-football-asset.compact-player-row,.dg-football-asset--standard{align-items:center;grid-template-columns:var(--size-roster-core-portrait) minmax(0, 1fr) auto}
.dg-football-asset.compact-player-row .dg-player-portrait,.dg-football-asset--standard .dg-player-portrait{height:var(--size-roster-core-portrait);width:var(--size-roster-core-portrait)}
.my-team-roster-core .dg-football-asset,div[class*="st-key-my_team_roster_core"] .dg-football-asset{align-items:center;grid-template-columns:var(--size-roster-core-portrait) minmax(0, 1fr) auto}
.my-team-roster-core .dg-player-portrait,div[class*="st-key-my_team_roster_core"] .dg-player-portrait{height:var(--size-roster-core-portrait);width:var(--size-roster-core-portrait)}
.my-team-roster-core .dg-player-portrait,div[class*="st-key-my_team_roster_core"] .dg-player-portrait{transform:translateY(calc(-1 * var(--space-xs)))}
.dg-football-asset__body{min-width:0}
.dg-football-asset__badges{display:flex;align-items:center;gap:var(--space-xs);flex-wrap:wrap;margin-top:var(--space-sm)}
.dg-football-asset__name{margin:var(--space-xs) 0 0;font:var(--font-card-title);overflow-wrap: break-word;word-break: normal;hyphens:none}
.dg-football-asset__meta,.dg-football-asset__insight{margin:var(--space-xs) 0 0;color:var(--color-text-muted);font-size:var(--font-size-caption)}
.dg-football-asset__value{text-align:right;font-variant-numeric:tabular-nums}
.dg-football-asset--stacked{align-items:start;grid-template-columns:auto minmax(0, 1fr)}
.dg-football-asset--stacked .dg-football-asset__value{grid-column:auto;justify-self:stretch;margin-top:var(--space-sm);text-align:left}
.dg-football-asset--stacked .dg-football-value{align-items:flex-start}
.dg-football-prestige,.dg-football-position,.dg-football-team,.dg-football-status,.dg-football-injury{display:inline-flex;align-items:center;justify-content:center;min-height:22px;padding:0 var(--space-sm);border:var(--border-width-default) solid var(--color-border-strong);border-radius:var(--radius-none);font-size:var(--font-size-badge);font-weight:var(--font-weight-button);line-height:var(--line-height-badge);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-football-prestige__rail{width:3px;height:12px;margin-right:var(--space-xs);background:currentColor}
.dg-football-prestige--elite{color:var(--color-prestige-elite)}
.dg-football-prestige--starter{color:var(--color-prestige-starter)}
.dg-football-prestige--contributor{color:var(--color-prestige-contributor)}
.dg-football-prestige--development{color:var(--color-prestige-development)}
.dg-football-prestige--depth{color:var(--color-prestige-depth)}
.dg-football-prestige--replacement{color:var(--color-prestige-replacement)}
.dg-football-injury{width:30px;min-width:30px;padding:0;text-align:center}
.dg-football-injury--success{color:var(--color-success);border-color:var(--color-success)}
.dg-football-injury--caution{color:var(--color-warning);border-color:var(--color-warning)}
.dg-football-injury--danger{color:var(--color-danger);border-color:var(--color-danger)}
.dg-football-value{align-items:flex-end;display:inline-flex;flex-direction:column;gap:0;line-height:1.05;text-align:right}
.dg-football-value__label{color:var(--color-text-muted);font:var(--type-supporting-metadata);text-transform:none;white-space:nowrap}
.dg-football-value__number{color:var(--color-text-primary);font-size:var(--font-size-card-title);font-variant-numeric:tabular-nums;font-weight:var(--font-weight-display);white-space:nowrap}
.dg-tier-frame{--dg-tier-a:var(--color-prestige-depth);position:relative}
.dg-tier-frame--generational{--dg-tier-a:var(--color-accent)}
.dg-tier-frame--elite{--dg-tier-a:var(--color-diagnostic)}
.dg-tier-frame--impact_starter{--dg-tier-a:var(--color-danger)}
.dg-tier-frame--starter{--dg-tier-a:var(--color-prestige-elite)}
.dg-tier-frame--contributor{--dg-tier-a:var(--color-prestige-starter)}
.dg-tier-frame--committee_role{--dg-tier-a:var(--color-warning)}
.dg-player-portrait.dg-tier-frame,.pqv-hero-portrait.dg-tier-frame{box-shadow:0 0 0 1px var(--dg-tier-a),0 0 7px 0 color-mix(in srgb,var(--dg-tier-a) 42%,transparent);overflow:visible}
.dg-player-portrait.dg-tier-frame>*,.pqv-hero-portrait.dg-tier-frame>*{overflow:hidden}
.dg-tier-frame::after{background:var(--dg-tier-a);content:"";display:none;height:3px;left:50%;position:absolute;top:-1px;transform:translateX(-50%);width:14px;z-index:2}
.pqv-hero-portrait.dg-tier-frame,.my-team-roster-core .dg-player-portrait.dg-tier-frame,div[class*="st-key-my_team_roster_core"] .dg-player-portrait.dg-tier-frame,.dg-tier-frame--full{box-shadow:0 0 0 2px var(--dg-tier-a),0 0 10px 1px color-mix(in srgb,var(--dg-tier-a) 52%,transparent)}
.dg-tier-frame--ring{box-shadow:0 0 0 1px var(--dg-tier-a),0 0 6px 0 color-mix(in srgb,var(--dg-tier-a) 34%,transparent)}
.dg-tier-frame--none,.dg-tier-frame--none.dg-player-portrait{box-shadow:none}
.pqv-hero-portrait.dg-tier-frame::after,.my-team-roster-core .dg-player-portrait.dg-tier-frame::after,div[class*="st-key-my_team_roster_core"] .dg-player-portrait.dg-tier-frame::after,.dg-tier-frame--full::after,.dg-tier-legend__swatch::after{display:block}
.dg-tier-frame--generational::after{height:7px;transform:translateX(-50%) rotate(45deg);width:7px}
.dg-tier-frame--elite::after{width:22px}
.dg-tier-frame--depth_developmental::after{display:none}
.dg-tier-frame--none{box-shadow:none}
.dg-tier-frame--none::after{display:none}
.dg-tier-legend__list{display:grid;gap:var(--space-2xs);list-style:none;margin:0;padding:0}
.dg-tier-legend__item{align-items:center;display:flex;gap:var(--space-sm)}
.dg-tier-legend__swatch{box-shadow:0 0 0 2px var(--dg-tier-a);height:12px;width:12px}
@media (max-width: 700px){.dg-football-asset,.dg-football-asset.compact-player-row,.dg-football-asset--standard{grid-template-columns:var(--size-roster-core-portrait) minmax(0, 1fr)}.my-team-roster-core .dg-football-asset,div[class*="st-key-my_team_roster_core"] .dg-football-asset{grid-template-columns:var(--size-roster-core-portrait) minmax(0, 1fr)}.dg-football-asset.compact-player-row{gap:var(--space-sm);padding:var(--space-sm) var(--space-md)}.dg-football-asset .compact-player-avatar{--avatar-size:100%;height:100%;width:100%}.compact-player-tags .player-support-chip-warning,.compact-player-tags .player-support-chip-risk,.scan-card-tags .player-support-chip-warning,.scan-card-tags .player-support-chip-risk{display:inline-flex!important}.dg-football-asset__value{grid-column:2;text-align:left}.dg-football-asset--stacked .dg-football-asset__value{grid-column:auto;text-align:left}.dg-football-asset__insight{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
@media (min-width: 64rem){.my-team-roster-core .dg-football-asset,div[class*="st-key-my_team_roster_core"] .dg-football-asset{grid-template-columns:var(--size-roster-core-portrait-lg) minmax(0, 1fr) auto}.my-team-roster-core .dg-player-portrait,div[class*="st-key-my_team_roster_core"] .dg-player-portrait{height:var(--size-roster-core-portrait-lg);width:var(--size-roster-core-portrait-lg)}}
@media (prefers-reduced-motion: reduce){.dg-football-asset{transition:none !important}}
""".replace("44%", card_focus_x())
