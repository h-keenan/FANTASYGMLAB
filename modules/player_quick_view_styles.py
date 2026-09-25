"""Token-backed presentation for the canonical Player Quick View dossier."""

# Points By Week (modules/weekly_points_chart.py builds the SVG). Lives
# here so the Player Quick View keeps one owned stylesheet — see
# tests/test_app_css_architecture.py's route-owned CSS contract.
WEEKLY_POINTS_CHART_CSS = """
.wpc{display:grid;gap:var(--space-2xs);margin:0 0 var(--space-sm);max-width:44rem;min-width:0}
.wpc-figure{display:block;margin:0;min-width:0;width:100%}
.wpc-svg{display:block;height:auto;overflow:visible;width:100%}
.wpc-area{stroke:none}
.wpc-grad-top{stop-color:var(--color-accent);stop-opacity:.34}
.wpc-grad-bottom{stop-color:var(--color-accent);stop-opacity:0}
.wpc-line{fill:none;stroke:var(--color-accent-strong);stroke-linecap:round;stroke-linejoin:round;stroke-width:2}
.wpc-dot{fill:var(--color-accent-strong);stroke:var(--color-surface-primary);stroke-width:2}
.wpc-dot--peak{fill:var(--color-accent)}
.wpc-baseline{stroke:var(--color-border-strong);stroke-width:1}
.wpc-grid{stroke:var(--color-border);stroke-dasharray:3 4;stroke-width:1}
.wpc-axis-label{fill:var(--color-text-muted);font-size:11px;letter-spacing:var(--letter-spacing-badge);text-anchor:end}
.wpc-week-label{fill:var(--color-text-muted);font-size:11px;text-anchor:middle}
.wpc-peak-label{fill:var(--color-text-primary);font-size:12px;font-variant-numeric:tabular-nums;text-anchor:middle}
.wpc-caption{color:var(--color-text-secondary);font-size:var(--font-size-caption);line-height:var(--line-height-caption);overflow-wrap:anywhere}
.wpc-caption strong{color:var(--color-text-primary);font-variant-numeric:tabular-nums;font-weight:var(--font-weight-body)}
.wpc-empty{border-left:var(--border-width-semantic) solid var(--color-border-strong);color:var(--color-text-secondary);font-size:var(--font-size-body);margin:0 0 var(--space-sm);max-width:44rem;padding-left:var(--space-sm)}
div[class*="st-key-pqv_weekly_season_rail"]{margin:0 0 var(--space-xs);max-width:22rem}
div[class*="st-key-pqv_weekly_season_rail"] [data-testid="stHorizontalBlock"]{gap:var(--space-xs)!important}
div[class*="st-key-pqv_weekly_season_rail"] [data-testid="stButton"] button,div[class*="st-key-pqv_weekly_season_rail"] button[data-testid^="stBaseButton"]{background:var(--color-surface-raised)!important;border:var(--border-width-default) solid var(--border-standard)!important;border-radius:0!important;color:var(--color-text-secondary)!important;font-size:var(--font-size-badge)!important;letter-spacing:var(--letter-spacing-badge);min-height:var(--touch-target-min)!important;padding-inline:var(--space-sm)!important}
div[class*="st-key-pqv_weekly_season_rail"] button[kind="primary"],div[class*="st-key-pqv_weekly_season_rail"] button[data-testid="stBaseButton-primary"]{border-color:var(--border-accent)!important;color:var(--color-text-primary)!important}
@media (prefers-reduced-motion: reduce){.wpc *{animation:none!important;transition:none!important}}
"""

PLAYER_QUICK_VIEW_CSS = """
.player-quick-view-header-band.player-quick-view-hero,div[data-testid="stDialog"] .player-quick-view-header-band.player-quick-view-hero{align-items:start !important;display:grid;grid-template-columns:auto minmax(0,1fr) !important;justify-content:start;max-width:none;min-height:0}
.pqv-workspace{display:grid;gap:var(--space-sm);max-width:54rem;min-width:0;width:100%}
.pqv-workspace-top{align-items:start;display:grid;gap:var(--space-sm);grid-template-columns:minmax(0,1fr);min-width:0}
.pqv-workspace-top--with-season{grid-template-areas:"identity" "decision" "season"}
.pqv-workspace-top--with-season .pqv-identity{grid-area:identity}
.pqv-workspace-top--with-season .pqv-evidence-season{grid-area:season;min-width:0}
.pqv-workspace-top--with-season .pqv-decision-panel{grid-area:decision}
.pqv-compact-summaries{display:grid;gap:var(--space-sm);grid-template-columns:minmax(0,1fr);min-width:0}
.pqv-compact-model,.pqv-compact-career{min-width:0}
.pqv-evidence-season .player-dossier-section-heading,.pqv-compact-model .player-dossier-section-heading,.pqv-compact-career .player-dossier-section-heading{border:0;margin:0;padding:0 0 var(--space-2xs)}
.pqv-evidence-season .pqv-glance-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
/* Decision is the strongest-emphasis module on this screen (Magna Carta
   §14/§29) at every width, not only the ≥1024px two-column layout — every
   other analytical module in this file (player-dossier-decision, pqv-why-
   factor, pqv-signal-badge) already carries this same accent border. */
.pqv-decision-panel{border-left:var(--border-width-semantic) solid var(--color-information);display:grid;gap:var(--space-sm);min-width:0;padding-left:var(--space-md)}
.pqv-identity{margin:0}
.pqv-decision-row,.pqv-evidence-row{align-items:start;display:grid;gap:var(--space-md);grid-template-columns:minmax(0,1fr);min-width:0}
.pqv-decision-primary .player-dossier-context-summary,.pqv-decision-primary .player-dossier-context-note,.pqv-why-factor strong{overflow-wrap:anywhere;white-space:normal}
div[class*="st-key-pqv_actions_"]{margin:0;max-width:56rem}
div[class*="st-key-pqv_actions_"] [data-testid="stHorizontalBlock"]{align-items:center !important;display:flex !important;flex-wrap:wrap !important;gap:var(--space-xs) !important}
div[class*="st-key-pqv_actions_"] [data-testid="stHorizontalBlock"]>div{flex:0 0 auto !important;min-width:0 !important;width:auto !important}
div[class*="st-key-pqv_actions_"] [data-testid="stButton"] button,div[class*="st-key-pqv_actions_"] button[data-testid^="stBaseButton"],div[class*="st-key-pqv_actions_"] [data-testid="stPopover"] > div[aria-haspopup="true"] > button{background:var(--color-surface-raised)!important;border:var(--border-width-default) solid var(--border-standard)!important;border-radius:0!important;color:var(--color-text-secondary)!important;font-size:var(--font-size-badge)!important;letter-spacing:var(--letter-spacing-badge);min-height:var(--touch-target-min)!important;padding-inline:var(--space-sm)!important;text-transform:uppercase!important;width:auto!important}
div[class*="st-key-pqv_action_bar_primary"] [data-testid="stButton"] button,div[class*="st-key-pqv_action_bar_primary"] button[data-testid^="stBaseButton"]{background:var(--color-surface-interactive, var(--color-surface-raised))!important;border-color:var(--border-accent, var(--color-border-strong))!important;color:var(--color-text-primary)!important}
div[class*="st-key-pqv_detail_nav_rail"]{margin:0;max-width:56rem}
.pqv-hero-portrait{--dg-headshot-focus:22%;--dg-headshot-scale:1.65;--pqv-portrait-size:clamp(3.5rem,16vw,4.5rem);align-self:start !important;background:var(--color-surface-muted);border-radius:var(--radius-none);box-sizing:border-box;display:flex;flex:0 0 var(--pqv-portrait-size) !important;height:var(--pqv-portrait-size) !important;max-height:var(--pqv-portrait-size) !important;max-width:var(--pqv-portrait-size) !important;min-height:0 !important;min-width:0 !important;overflow:hidden;position:relative;width:var(--pqv-portrait-size) !important}
.pqv-hero-portrait.dg-tier-frame{overflow:hidden}
.pqv-hero-portrait .player-quick-view-avatar,.pqv-hero-portrait .player-detail-avatar,.pqv-hero-portrait .dg-player-headshot{--avatar-size:100% !important;align-self:stretch !important;border-radius:0 !important;flex:1 1 auto !important;height:100% !important;max-height:100% !important;max-width:100% !important;min-height:0 !important;min-width:0 !important;overflow:hidden;position:relative;width:100% !important}
.pqv-hero-portrait .dg-player-headshot-image,.pqv-hero-portrait img{height:100% !important;inset:0 !important;left:0 !important;max-height:none !important;max-width:none !important;min-height:0 !important;object-fit:cover !important;object-position:center var(--dg-headshot-focus, 22%) !important;position:absolute !important;top:0 !important;transform:scale(var(--dg-headshot-scale, 1.65)) !important;transform-origin:center var(--dg-headshot-focus, 22%) !important;width:100% !important}
div[data-testid="stDialog"] .pqv-hero-portrait .player-quick-view-avatar,div[data-testid="stDialog"] .pqv-hero-portrait .player-detail-avatar,div[data-testid="stDialog"] .pqv-hero-portrait img{flex:1 1 auto !important;height:100% !important;max-height:none !important;max-width:none !important;min-height:0 !important;min-width:0 !important;width:100% !important}
.pqv-hero-tier,.pqv-hero-role{color:var(--color-text-primary);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin:var(--space-2xs) 0 0;text-transform:uppercase}
.pqv-hero-tier{font-size:var(--font-size-badge);font-weight:var(--font-weight-button);margin:0 0 var(--space-2xs)}
/* Hero tier pill: solid fill in the tier's own color (--dg-tier-fill/--dg-tier-ink
   set inline per player by modules/player_tier_identity.py). Deliberately not the
   translucent dg-tier-* list chip — this is the one hero display for this player. */
.pqv-hero-tier.pqv-hero-tier--solid{align-items:center;align-self:start;background:var(--dg-tier-fill,var(--color-prestige-depth));border-radius:var(--radius-pill);color:var(--dg-tier-ink,var(--color-text-primary));display:inline-flex;justify-self:start;line-height:var(--line-height-badge);min-height:1.25rem;padding:var(--space-2xs) var(--space-sm);width:fit-content}
.player-dossier-rank-strip{display:flex;flex-wrap:wrap;gap:var(--space-sm) var(--space-md);margin:var(--space-xs) 0 0;padding:0}
.player-dossier-rank-cell{display:grid;gap:2px;min-width:0}
.player-dossier-rank-cell span,.pqv-signal-badge-question,.pqv-why-factor span,.pqv-recommendation-confidence,.pqv-glance-cell span,.pqv-career-glance-cell span,.pqv-kicker{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.player-dossier-rank-cell strong,.pqv-signal-badge-answer{color:var(--color-text-primary);font-size:var(--font-size-body);overflow-wrap:anywhere}
.pqv-signal-badge-group{display:flex;flex-wrap:wrap;gap:var(--space-sm);margin:var(--space-xs) 0 0}
.pqv-signal-badge{border-left:var(--border-width-semantic) solid var(--color-border-strong);display:grid;gap:2px;min-width:0;padding-left:var(--space-sm)}
.pqv-signal-badge--risk{border-left-color:var(--color-warning)}
.pqv-signal-badge--risk .pqv-signal-badge-answer{color:var(--color-warning)}
.pqv-why-recommendation,.pqv-fantasy-evidence,.pqv-accolades,.pqv-career-glance,.pqv-career-dossier,.pqv-bio{margin:0 0 var(--space-sm);max-width:none}
.player-quick-view-shell{max-width:54rem;min-width:0;overflow-x:clip}
.player-quick-view-shell .dg-tier-legend{margin:var(--space-2xs) 0 0;max-width:22rem}
.player-quick-view-shell .dg-tier-legend>summary{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);min-height:var(--touch-target-min);text-transform:uppercase}
.pqv-bio-row{display:grid;gap:var(--space-sm);grid-template-columns:repeat(auto-fit,minmax(7rem,1fr))}
.pqv-bio-cell{display:grid;gap:2px;min-width:0}
.pqv-bio-cell span{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.pqv-bio-cell strong{color:var(--color-text-primary);font-size:var(--font-size-body);overflow-wrap:anywhere}
.player-quick-view-detail-list{display:grid;gap:var(--space-sm);margin:0 0 var(--space-sm);max-width:48rem}
.player-quick-view-detail-row{border-left:var(--border-width-semantic) solid var(--color-border-strong);display:grid;gap:2px;min-width:0;padding-left:var(--space-sm)}
.player-quick-view-detail-label{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.player-quick-view-detail-value{color:var(--color-text-primary);font-size:var(--font-size-body);overflow-wrap:anywhere}
.player-quick-view-detail-note{color:var(--color-text-secondary);font-size:var(--font-size-caption);line-height:var(--line-height-caption);overflow-wrap:anywhere}
.pqv-why-grid{display:grid;gap:var(--space-xs)}
.pqv-why-factor{border-left:var(--border-width-semantic) solid var(--color-information);display:grid;gap:1px;min-width:0;padding-left:var(--space-sm)}
.pqv-why-factor--fit{border-left-color:var(--color-opportunity)}
.pqv-why-factor--risk{border-left-color:var(--color-warning)}
.pqv-why-factor strong{color:var(--color-text-primary);font-size:var(--font-size-body);font-weight:var(--font-weight-body);line-height:1.25;overflow-wrap:anywhere}
.pqv-glance-grid{display:grid;gap:var(--space-xs) var(--space-sm);grid-template-columns:repeat(auto-fit,minmax(5.25rem,1fr));min-width:0}
.pqv-model-matrix{display:grid;gap:var(--space-xs);grid-template-columns:repeat(2,minmax(0,1fr));margin:0 0 var(--space-sm);max-width:48rem}
.pqv-model-cell:last-child:nth-child(odd){grid-column:1/-1}
.pqv-model-cell{border-left:var(--border-width-semantic) solid var(--color-border-strong);display:grid;gap:1px;min-width:0;padding:var(--space-xs) var(--space-sm)}
.pqv-model-cell span{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.pqv-model-cell strong{color:var(--color-text-primary);font-size:var(--font-size-body);overflow-wrap:anywhere}
.pqv-model-cell small{color:var(--color-text-secondary);font-size:var(--font-size-caption);line-height:1.25;overflow-wrap:anywhere}
.player-quick-view-stat-grid{display:grid;gap:var(--space-xs);grid-template-columns:repeat(2,minmax(0,1fr))}
.pqv-stat-percentile{align-items:center;display:flex;gap:var(--space-2xs);margin-top:2px}
.pqv-stat-percentile-bar{background:var(--color-surface-muted);border:var(--border-width-default) solid var(--color-border-strong);box-sizing:border-box;display:block;height:6px;max-width:4rem;overflow:hidden;width:100%}
.pqv-stat-percentile-bar>span{display:block;height:100%}
.pqv-stat-percentile-label{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);white-space:nowrap}
.pqv-stat-percentile--low .pqv-stat-percentile-bar>span{background:var(--color-danger)}
.pqv-stat-percentile--mid .pqv-stat-percentile-bar>span{background:var(--color-action)}
.pqv-stat-percentile--high .pqv-stat-percentile-bar>span{background:var(--color-success)}
.player-dossier-rank-cell strong.pqv-ovr--low{color:var(--color-danger)}
.player-dossier-rank-cell strong.pqv-ovr--mid{color:var(--color-action)}
.player-dossier-rank-cell strong.pqv-ovr--high{color:var(--color-success)}
.player-dossier-timeline-metrics{display:grid;gap:var(--space-2xs) var(--space-sm);grid-template-columns:repeat(2,minmax(0,1fr))}
.player-dossier-timeline-metrics span{color:var(--color-text-secondary);font-size:var(--font-size-caption);overflow-wrap:anywhere}
.player-dossier-timeline-year{display:grid;gap:2px}
.pqv-glance-cell{display:grid;gap:2px;min-width:0}
.pqv-glance-cell strong{color:var(--color-text-primary);font-size:var(--font-size-card-title);line-height:var(--line-height-card);overflow-wrap:anywhere}
.pqv-glance-bar{background:var(--color-surface-muted);border:var(--border-width-default) solid var(--color-border-strong);box-sizing:border-box;display:block;height:8px;margin-top:4px;max-width:6.5rem;overflow:hidden;width:100%}
.pqv-glance-bar-fill,.pqv-glance-bar>span{background:var(--color-information);display:block;height:100%;max-width:100%}
.pqv-model-summary-row{display:grid;gap:var(--space-xs) var(--space-sm);grid-template-columns:repeat(4,minmax(0,1fr));min-width:0}
.pqv-model-summary-cell{display:grid;gap:2px;min-width:0}
.pqv-model-summary-cell span{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.pqv-model-summary-cell strong{color:var(--color-text-primary);font-size:var(--font-size-body);overflow-wrap:anywhere}
.pqv-accolade-chips{display:flex;flex-wrap:wrap;gap:var(--space-2xs);list-style:none;margin:var(--space-2xs) 0 0;padding:0}
.pqv-accolade-chip{border:var(--border-width-default) solid var(--color-border-strong);color:var(--color-text-primary);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);padding:2px var(--space-xs);text-transform:uppercase}
.pqv-accolade-chip--gold{border-color:var(--color-prestige-elite)}
.pqv-accolade-chip--silver{border-color:var(--color-prestige-starter)}
.pqv-accolade-chip--bronze{border-color:var(--color-prestige-contributor)}
.pqv-accolade-cluster{display:grid;gap:var(--space-sm);grid-template-columns:repeat(auto-fill,minmax(9.5rem,1fr));list-style:none;margin:0;padding:0}
.pqv-accolade{align-items:center;border:var(--border-width-default) solid var(--color-border);display:grid;gap:var(--space-sm);grid-template-columns:auto minmax(0,1fr);min-height:var(--touch-target-min);min-width:0;padding:var(--space-xs) var(--space-sm);position:relative}
.pqv-accolade--gold{border-color:var(--color-prestige-elite);box-shadow:inset 3px 0 0 var(--color-prestige-elite);color:var(--color-prestige-elite)}
.pqv-accolade--silver{border-color:var(--color-prestige-starter);border-style:double;box-shadow:inset 3px 0 0 var(--color-prestige-starter);color:var(--color-prestige-starter)}
.pqv-accolade--bronze{border-color:var(--color-prestige-contributor);border-bottom-width:3px;box-shadow:inset 3px 0 0 var(--color-prestige-contributor);color:var(--color-prestige-contributor)}
.pqv-accolade--plain{border-left:var(--border-width-semantic) solid var(--color-border-strong);color:var(--color-text-secondary)}
.pqv-accolade-medal,.pqv-accolade-emblem{flex:0 0 1.75rem;height:1.75rem;width:1.75rem}
.pqv-accolade-emblem-wrap{position:relative}
.pqv-accolade-count{background:var(--color-surface-raised);border:var(--border-width-default) solid currentColor;bottom:-4px;color:var(--color-text-primary);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);line-height:1;padding:1px 3px;position:absolute;right:-6px}
.pqv-accolade-copy{display:grid;gap:2px;min-width:0}
.pqv-accolade-copy strong{color:var(--color-text-primary);font-size:var(--font-size-body);line-height:var(--line-height-card);overflow-wrap:anywhere;text-transform:uppercase}
.pqv-accolade-copy small{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge)}
.pqv-accolades-more{margin:var(--space-xs) 0 0}
.pqv-accolade-cluster--all{padding:var(--space-sm) 0 0}
.pqv-career-glance-row{display:grid;gap:var(--space-sm);grid-template-columns:repeat(auto-fit,minmax(6.5rem,1fr))}
.pqv-career-glance-cell{display:grid;gap:var(--space-2xs);min-width:0}
.pqv-career-glance-cell strong{color:var(--color-text-primary);font-size:var(--font-size-body);overflow-wrap:anywhere}
.player-quick-view-actions-label{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);margin:0 0 var(--space-2xs);text-transform:uppercase}
div[class*="st-key-pqv_actions_"] [data-testid="stButton"] button,
div[class*="st-key-pqv_actions_"] button[data-testid^="stBaseButton"]{min-height:var(--touch-target-min)!important;padding-block:var(--space-xs)!important;padding-inline:var(--space-sm)!important;width:auto!important}
div[class*="st-key-pqv_actions_"] [data-testid="stHorizontalBlock"]{align-items:center!important;display:flex!important;flex-direction:row!important;flex-wrap:wrap!important;gap:var(--space-xs)!important}
div[class*="st-key-pqv_actions_"] [data-testid="stHorizontalBlock"]>div{flex:0 0 auto!important;min-width:0!important;width:auto!important}
.pqv-detail-nav-label{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);margin:0 0 var(--space-2xs);text-transform:uppercase}
div[class*="st-key-pqv_detail_nav_rail"] [data-testid="stButton"] button,div[class*="st-key-pqv_detail_nav_rail"] button[data-testid^="stBaseButton"]{background:var(--color-surface-raised)!important;background-image:none!important;border:var(--border-width-default) solid var(--border-standard)!important;border-radius:0!important;color:var(--color-text-secondary)!important;font-size:var(--font-size-badge)!important;letter-spacing:var(--letter-spacing-badge);min-height:var(--touch-target-min)!important;text-transform:uppercase!important}
div[class*="st-key-pqv_actions_tertiary"]{margin:0}
div[class*="st-key-pqv_actions_tertiary"] [data-testid="stButton"] button,div[class*="st-key-pqv_actions_tertiary"] button[data-testid^="stBaseButton"]{background:transparent!important;background-image:none!important;border:0!important;border-block-end:var(--border-width-default) solid var(--color-danger)!important;border-left:0!important;color:var(--color-danger)!important;font-size:var(--font-size-caption)!important;min-height:auto!important;padding-inline:0!important;text-transform:none!important}
.pqv-decision-grid,.pqv-context-grid{display:grid;gap:var(--space-md);margin:0 0 var(--space-sm);max-width:48rem}
.pqv-decision-primary,.pqv-decision-secondary{display:grid;gap:var(--space-sm);min-width:0}
.pqv-fantasy-evidence{margin:0}
.player-dossier-context-action{margin:0;padding:0}
.player-dossier-context-action strong,.pqv-decision-topline .player-dossier-context-action{color:var(--color-text-primary);font-size:var(--font-size-card-title);font-weight:var(--font-weight-title);letter-spacing:0;line-height:var(--line-height-card);text-transform:none}
.pqv-why-factor--fit strong{color:var(--color-text-secondary);font-size:var(--font-size-caption);font-weight:var(--font-weight-body)}
.pqv-recommendation-confidence{margin:0;padding:0}
.pqv-decision-summary{margin:0;max-width:none;padding:0}
.pqv-decision-topline{align-items:baseline;display:flex;flex-wrap:wrap;gap:var(--space-2xs) var(--space-sm);justify-content:space-between;padding:0}
.pqv-decision-summary .player-dossier-section-heading{border:0;padding:0 0 var(--space-2xs)}
.pqv-decision-summary .player-dossier-context-summary{margin:0;padding:0}
.player-dossier-news-meta{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);margin:0 0 var(--space-xs);text-transform:uppercase}
.player-dossier-news-headline{color:var(--color-text-primary);font-size:var(--font-size-body);line-height:var(--line-height-body);margin:0 0 var(--space-xs)}
.player-dossier-news-snippet,.player-dossier-news-quiet{color:var(--color-text-secondary);font-size:var(--font-size-body);line-height:var(--line-height-body);margin:0}
.player-dossier-news-link{margin:0 0 var(--space-sm)}
.player-dossier-news-link a{color:var(--color-text-primary)}
.dg-client-disclosure>summary{cursor:pointer;min-height:var(--touch-target-min);list-style:none}
.dg-client-disclosure-body{padding:var(--space-sm) 0}
.visually-hidden{clip:rect(0 0 0 0);clip-path:inset(50%);height:1px;overflow:hidden;position:absolute;white-space:nowrap;width:1px}

.player-dossier-snapshot,.player-dossier-executive,.player-dossier-career,.player-dossier-recommendation-context,.player-dossier-news-card{margin: var(--space-xs) 0;overflow:hidden}
.player-dossier-recommendation-context{margin:0;max-width:48rem}
.player-dossier-news-card{border-top:var(--border-width-default) solid var(--color-border);margin:0 0 var(--space-sm);padding:var(--space-sm) 0}
.player-dossier-executive-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))}
.player-dossier-executive-metric{border-right:var(--border-width-default) solid var(--color-border);border-top:var(--border-width-default) solid var(--color-border);display:grid;gap:var(--space-sm);min-width:0;padding: var(--space-md)}
.player-dossier-executive-metric:nth-child(3n){border-right:0}
.player-dossier-executive-metric span,.player-dossier-career-metric span,.player-dossier-achievement-copy small,.player-dossier-timeline-context,.player-dossier-timeline-copy small,.player-dossier-career-milestones-title,.player-dossier-career-basis{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge)}
.player-dossier-executive-metric strong,.player-dossier-career-metric strong{color:var(--color-text-primary);font-size:var(--font-size-body);overflow-wrap:anywhere}
.player-dossier-career-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}
.player-dossier-career-metric{border-bottom:var(--border-width-default) solid var(--color-border);border-right:var(--border-width-default) solid var(--color-border);display:grid;gap:2px;min-width:0;padding:var(--space-sm)}
.player-dossier-career-metric:nth-child(4n){border-right:0}
.player-dossier-career-metric span,.player-dossier-career-milestones-title{text-transform:uppercase}
.player-dossier-career-milestones{border-top:var(--border-width-default) solid var(--color-border);padding:var(--space-sm) var(--space-md)}
.player-dossier-career-milestones-title{margin:0 0 var(--space-2xs)}
.player-dossier-career-milestone-line{color:var(--color-text-secondary);font-size:var(--font-size-body);line-height:var(--line-height-body);margin:0;overflow-wrap:anywhere}
.player-dossier-career-basis{margin:0;padding:var(--space-xs) var(--space-md) var(--space-sm)}
.player-dossier-achievement-list,.player-dossier-timeline{list-style:none;margin:0;padding:0}
.player-dossier-achievement,.player-dossier-timeline-season{align-items:start;border-bottom:var(--border-width-default) solid var(--color-border);display:grid;gap:var(--space-sm);grid-template-columns:auto minmax(0,1fr);padding:var(--space-sm) var(--space-md)}
.player-dossier-achievement:last-child,.player-dossier-timeline-season:last-child{border-bottom:0}
.player-dossier-achievement-icon{align-items:center;border:var(--border-width-default) solid currentColor;color:var(--color-prestige-development);display:inline-flex;height:var(--touch-target-min);justify-content:center;width:var(--touch-target-min)}
.player-dossier-achievement--landmark .player-dossier-achievement-icon{color:var(--color-prestige-elite)}
.player-dossier-achievement--elite .player-dossier-achievement-icon{color:var(--color-prestige-starter)}
.player-dossier-achievement--standout .player-dossier-achievement-icon{color:var(--color-prestige-contributor)}
.player-dossier-achievement-copy,.player-dossier-timeline-copy{display:grid;gap:var(--space-xs);min-width:0}
.player-dossier-achievement-copy strong,.player-dossier-timeline-year strong{color:var(--color-text-primary);font-size:var(--font-size-body)}
.player-dossier-achievement-current,.player-dossier-timeline-year span{border-left:var(--border-width-semantic) solid var(--color-opportunity);color:var(--color-text-secondary);font-size:var(--font-size-badge);padding-left:var(--space-xs);text-transform:uppercase}
.player-dossier-timeline-season{grid-template-columns:minmax(4rem,auto) minmax(0,1fr)}
.player-dossier-timeline-year{display:grid;gap:var(--space-xs)}
.player-dossier-timeline-copy p{color:var(--color-text-secondary);font-size:var(--font-size-body);line-height:var(--line-height-body);margin:0;overflow-wrap:anywhere}
@media (max-width: 700px){.player-dossier-executive-grid,.player-dossier-snapshot-grid{grid-template-columns:repeat(2, minmax(0, 1fr))}
.player-dossier-executive-metric:nth-child(2n),.player-dossier-snapshot-metric:nth-child(2n){border-right:0}
.player-dossier-snapshot-metric strong,.player-dossier-executive-metric strong{font-size:var(--font-size-body)}
.player-dossier-timeline-copy p,.player-dossier-section-heading p{overflow-wrap:anywhere}
.pqv-glance-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.pqv-evidence-season .pqv-glance-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
.player-dossier-career-summary{grid-template-columns:repeat(2,minmax(0,1fr))}
.player-dossier-career-metric:nth-child(4n){border-right:var(--border-width-default) solid var(--color-border)}
.player-dossier-career-metric:nth-child(2n){border-right:0}
}
.player-dossier-snapshot-title,.player-dossier-section-heading{padding:0 0 var(--space-xs)}
.pqv-why-recommendation .player-dossier-section-heading,.pqv-fantasy-evidence .player-dossier-section-heading,.pqv-accolades .player-dossier-section-heading,.pqv-career-glance .player-dossier-section-heading,.pqv-career-dossier .player-dossier-section-heading,.pqv-bio .player-dossier-section-heading{border:0;padding:0 0 var(--space-xs)}
.player-dossier-snapshot .player-dossier-snapshot-title,.player-dossier-career .player-dossier-section-heading,.player-dossier-executive .player-dossier-section-heading{border-bottom:var(--border-width-default) solid var(--color-border);border-left:var(--border-width-semantic) solid var(--color-border-strong);padding:var(--space-sm) var(--space-md)}
.player-dossier-recommendation-context .player-dossier-section-heading{border:0;padding:0 0 var(--space-2xs)}
.player-dossier-snapshot-title,.player-dossier-section-heading h3{color:var(--color-text-primary);font-size:var(--font-size-card-title);font-weight:var(--font-weight-title);letter-spacing:var(--letter-spacing-badge);line-height:var(--line-height-card);margin:0;text-transform:uppercase}
.player-dossier-section-heading p{color:var(--color-text-muted);font-size:var(--font-size-caption);line-height:var(--line-height-caption);margin:var(--space-xs) 0 0}
.player-dossier-snapshot-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}
.player-dossier-snapshot-metric{border-right:var(--border-width-default) solid var(--color-border);display:grid;gap:var(--space-xs);min-width:0;padding:var(--space-sm) var(--space-md)}
.player-dossier-snapshot-metric:last-child{border-right:0}
.player-dossier-snapshot-metric span,.player-dossier-decision span{color:var(--color-text-muted);font-size:var(--font-size-badge);font-weight:var(--font-weight-button);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.player-dossier-snapshot-metric strong{color:var(--color-text-primary);font-size:var(--font-size-card-title);line-height:var(--line-height-card);overflow-wrap:anywhere}
.player-dossier-decision{border-left:var(--border-width-semantic) solid var(--color-information);border-top:var(--border-width-default) solid var(--color-border);display:grid;gap:var(--space-xs);padding:var(--space-sm) var(--space-md)}
.player-dossier-decision--opportunity{border-left-color:var(--color-opportunity)}
.player-dossier-decision--risk{border-left-color:var(--color-warning)}
.player-dossier-decision strong{color:var(--color-text-primary);font-size:var(--font-size-section-title)}
.player-dossier-decision p,.player-dossier-context-summary,.player-dossier-context-note,.player-dossier-career-empty{color:var(--color-text-secondary);font-size:var(--font-size-body);line-height:var(--line-height-body);margin:0}
.player-dossier-career-empty,.player-dossier-context-summary,.player-dossier-context-note{padding:var(--space-sm) var(--space-md)}
.player-dossier-context-note{border-top:var(--border-width-default) solid var(--color-border);color:var(--color-text-muted)}
div[data-testid="stDialog"] div[role="dialog"]:has(.player-quick-view-shell){max-height: min(88vh, 920px) !important}
div[data-testid="stDialog"] div[role="dialog"]:has(.player-quick-view-shell)>div:last-child{overflow-y: auto !important;overscroll-behavior:contain}
@media (max-width: 900px){
.pqv-workspace-top,.pqv-decision-row,.pqv-evidence-row{grid-template-columns:minmax(0,1fr)}
.player-dossier-snapshot-grid,.player-dossier-executive-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.player-dossier-rank-strip{gap:var(--space-sm)}
.player-dossier-career-summary{grid-template-columns:repeat(2,minmax(0,1fr))}
.player-dossier-career-metric{border-right:var(--border-width-default) solid var(--color-border)}
.player-dossier-career-metric:nth-child(2n){border-right:0}
.player-dossier-snapshot-metric:nth-child(2){border-right:0}
.player-dossier-snapshot-metric:nth-child(-n+2){border-bottom:var(--border-width-default) solid var(--color-border)}
.player-dossier-section-heading,.player-dossier-snapshot-title,.player-dossier-snapshot-metric,.player-dossier-decision,.player-dossier-career-empty,.player-dossier-context-summary,.player-dossier-context-note,.player-dossier-executive-metric,.player-dossier-career-metric,.player-dossier-achievement,.player-dossier-timeline-season,.player-dossier-rank-cell,.pqv-why-factor,.pqv-signal-badge{padding-left:var(--space-sm);padding-right:var(--space-sm)}
.pqv-why-recommendation .player-dossier-section-heading,.pqv-fantasy-evidence .player-dossier-section-heading,.pqv-accolades .player-dossier-section-heading,.pqv-career-glance .player-dossier-section-heading,.pqv-career-dossier .player-dossier-section-heading,.pqv-bio .player-dossier-section-heading,.player-dossier-rank-cell,.pqv-why-factor,.pqv-signal-badge{padding-left:0;padding-right:0}
}
@media (max-width:430px){
.player-quick-view-shell,.pqv-workspace,.pqv-workspace-top,.pqv-compact-summaries{max-width:100%;min-width:0;overflow-x:clip}
.pqv-hero-portrait{--pqv-portrait-size:clamp(2.75rem,14vw,3.5rem)}
.player-quick-view-name{font-size:var(--font-size-card-title)}
.pqv-decision-summary .player-dossier-section-heading{padding:var(--space-xs) var(--space-sm)}
.pqv-decision-topline{align-items:start;display:grid;gap:var(--space-2xs);grid-template-columns:minmax(0,1fr);padding:var(--space-sm)}
.pqv-recommendation-confidence{justify-self:start}
.pqv-decision-summary .player-dossier-context-summary,.pqv-decision-summary .player-dossier-context-note{padding:var(--space-sm)}
.pqv-accolade-cluster{grid-template-columns:repeat(2,minmax(0,1fr))}
.pqv-glance-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.pqv-evidence-season .pqv-glance-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
.pqv-model-summary-row{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (min-width: 1024px){
div[data-testid="stDialog"] div[role="dialog"]:has(.player-quick-view-shell){max-width:min(54rem,calc(100dvw - 4rem)) !important;width:min(54rem,calc(100dvw - 4rem)) !important}
.player-quick-view-shell,.pqv-workspace{max-width:54rem}
div[class*="st-key-pqv_actions_"],div[class*="st-key-pqv_detail_nav_rail"]{max-width:54rem}
div[class*="st-key-pqv_actions_strip"]{max-width:54rem}
.pqv-hero-portrait{--pqv-portrait-size:clamp(4.75rem,7vw,6.25rem)}
.pqv-workspace-top{align-items:stretch;grid-template-columns:minmax(16rem,0.95fr) minmax(0,1.05fr)}
.pqv-workspace-top--with-season{grid-template-areas:"identity decision" "season season";grid-template-columns:minmax(16rem,0.95fr) minmax(0,1.05fr)}
.pqv-decision-panel{align-content:start}
.player-dossier-rank-strip{display:grid;gap:var(--space-sm) var(--space-lg);grid-template-columns:repeat(3,minmax(0,max-content))}
.pqv-evidence-season,.pqv-compact-model,.pqv-compact-career{border:var(--border-width-default) solid var(--color-border);box-sizing:border-box;min-width:0;padding:var(--space-sm) var(--space-md)}
.pqv-evidence-season .pqv-glance-grid{grid-template-columns:repeat(6,minmax(4.5rem,6.5rem));justify-content:start;max-width:max-content}
.pqv-compact-summaries{align-items:stretch;grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.pqv-compact-model,.pqv-compact-career{display:grid;align-content:start;gap:var(--space-xs)}
.pqv-model-summary-cell strong,.pqv-career-glance-cell strong{font-size:var(--font-size-card-title);line-height:var(--line-height-card)}
.pqv-decision-row,.pqv-evidence-row{grid-template-columns:minmax(0,1.1fr) minmax(0,0.9fr)}
.pqv-why-recommendation,.pqv-fantasy-evidence,.pqv-accolades,.pqv-career-glance,.pqv-career-summary,.pqv-model-summary,.pqv-career-dossier,.pqv-bio,.pqv-decision-grid,.pqv-context-grid,.player-quick-view-detail-list,.pqv-model-matrix{max-width:none}
.pqv-decision-grid,.pqv-context-grid{grid-template-columns:minmax(0,1.15fr) minmax(0,0.85fr);align-items:start}
.pqv-glance-grid{grid-template-columns:repeat(6,minmax(4.5rem,6.5rem));justify-content:start}
.pqv-model-matrix{grid-template-columns:repeat(5,minmax(0,1fr));max-width:56rem}
.pqv-model-cell:last-child:nth-child(odd){grid-column:auto}
.pqv-accolade-cluster{grid-template-columns:repeat(auto-fill,minmax(10rem,1fr))}
.player-quick-view-stat-grid{grid-template-columns:repeat(3,minmax(0,12rem));max-width:42rem}
.player-dossier-timeline{display:grid;gap:var(--space-sm);grid-template-columns:repeat(2,minmax(0,1fr))}
.player-dossier-timeline-season{border:var(--border-width-default) solid var(--color-border);margin:0}
div[class*="st-key-pqv_detail_stats_"]>div[data-testid="stVerticalBlock"],div[class*="st-key-pqv_detail_career_"]>div[data-testid="stVerticalBlock"],div[class*="st-key-pqv_detail_model_"]>div[data-testid="stVerticalBlock"]{align-items:start;display:grid!important;gap:var(--space-lg)!important;grid-template-columns:minmax(0,1.15fr) minmax(16rem,0.85fr)!important}
div[class*="st-key-pqv_actions_"],div[class*="st-key-pqv_detail_nav_rail"]{max-width:54rem}
div[class*="st-key-pqv_actions_strip"]{max-width:54rem}
div[class*="st-key-pqv_actions_strip"] [data-testid="stHorizontalBlock"]{align-items:center!important;display:flex!important;flex-wrap:nowrap!important;gap:var(--space-xs)!important}
div[class*="st-key-pqv_actions_strip"] [data-testid="stHorizontalBlock"]>div{flex:0 0 auto!important;min-width:0!important;width:auto!important}
div[class*="st-key-pqv_actions_"] [data-testid="stButton"] button,div[class*="st-key-pqv_actions_"] button[data-testid^="stBaseButton"]{min-height:var(--touch-target-min)!important;width:auto!important}
div[class*="st-key-pqv_detail_career_"] .player-quick-view-stat-grid,div[class*="st-key-pqv_detail_stats_"] .player-quick-view-stat-grid,div[class*="st-key-pqv_detail_career_"] .player-dossier-timeline{max-width:48rem}
}
@media (max-width: 700px){
div[class*="st-key-pqv_career_actions"]>div[data-testid="stVerticalBlock"]{display:flex!important;flex-direction:column!important}
div[class*="st-key-pqv_detail_stats_"]>div[data-testid="stVerticalBlock"],div[class*="st-key-pqv_detail_career_"]>div[data-testid="stVerticalBlock"],div[class*="st-key-pqv_detail_model_"]>div[data-testid="stVerticalBlock"]{display:flex!important;flex-direction:column!important}
div[class*="st-key-pqv_actions_strip"] [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
div[class*="st-key-pqv_actions_strip"] [data-testid="stHorizontalBlock"]>div{flex:0 0 auto!important;min-width:0!important;width:auto!important}
div[class*="st-key-pqv_detail_model_"]{grid-template-columns:minmax(0,1fr)}
}
@media (prefers-reduced-motion: reduce){.player-dossier-snapshot *,.player-dossier-executive *,.player-dossier-career *,.player-dossier-recommendation-context *,.pqv-why-recommendation *,.pqv-accolades *{animation:none !important;transition:none !important}}
""" + WEEKLY_POINTS_CHART_CSS
