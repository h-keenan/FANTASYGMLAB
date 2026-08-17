"""Token-backed presentation for the canonical Player Quick View dossier."""

PLAYER_QUICK_VIEW_CSS = """
.pqv-hero-portrait{display:flex;flex:0 0 auto;position:relative;border-radius:var(--radius-none);overflow:hidden;height:clamp(5.25rem,18vw,7.25rem);width:clamp(5.25rem,18vw,7.25rem)}
.pqv-hero-portrait .player-quick-view-avatar,.pqv-hero-portrait .dg-player-headshot{height:100%;position:relative;width:100%;z-index:1}
.pqv-hero-portrait .dg-player-headshot-image,.pqv-hero-portrait img{height:100% !important;max-height:100%;max-width:100%;object-fit:cover !important;object-position:center 18% !important;transform:none !important;width:100% !important}
.pqv-hero-tier,.pqv-hero-role{color:var(--color-text-primary);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin:var(--space-2xs) 0 0;text-transform:uppercase}
.pqv-hero-tier{font-size:var(--font-size-badge);font-weight:var(--font-weight-button);margin:0 0 var(--space-2xs)}
.player-dossier-rank-strip{display:flex;flex-wrap:wrap;gap:var(--space-sm) var(--space-md);margin:var(--space-xs) 0 0;padding:0}
.player-dossier-rank-cell{display:grid;gap:2px;min-width:0}
.player-dossier-rank-cell span,.pqv-signal-badge-question,.pqv-why-factor span,.pqv-recommendation-confidence,.pqv-glance-cell span,.pqv-career-glance-cell span,.pqv-kicker{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.player-dossier-rank-cell strong,.pqv-signal-badge-answer{color:var(--color-text-primary);font-size:var(--font-size-body);overflow-wrap:anywhere}
.pqv-signal-badge-group{display:flex;flex-wrap:wrap;gap:var(--space-sm);margin:var(--space-xs) 0 0}
.pqv-signal-badge{border-left:var(--border-width-semantic) solid var(--color-border-strong);display:grid;gap:2px;min-width:0;padding-left:var(--space-sm)}
.pqv-why-recommendation,.pqv-fantasy-evidence,.pqv-accolades,.pqv-career-glance,.pqv-career-dossier,.pqv-bio{margin:0 0 var(--space-sm);max-width:48rem}
.player-quick-view-shell{max-width:48rem}
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
.pqv-why-grid{display:grid;gap:var(--space-sm)}
.pqv-why-factor{border-left:var(--border-width-semantic) solid var(--color-information);display:grid;gap:2px;min-width:0;padding-left:var(--space-sm)}
.pqv-why-factor strong{color:var(--color-text-primary);font-size:var(--font-size-body);font-weight:var(--font-weight-body);line-height:var(--line-height-body);overflow-wrap:anywhere}
.pqv-glance-grid{display:grid;gap:var(--space-sm);grid-template-columns:repeat(3,minmax(0,1fr));min-width:0}
.pqv-glance-cell{display:grid;gap:2px;min-width:0}
.pqv-glance-cell strong{color:var(--color-text-primary);font-size:var(--font-size-card-title);line-height:var(--line-height-card);overflow-wrap:anywhere}
.pqv-glance-bar{background:var(--color-surface-muted);display:block;height:4px;margin-top:2px;max-width:4.5rem}
.pqv-glance-bar>span{background:var(--color-text-secondary);display:block;height:100%;max-width:100%}
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
.pqv-career-glance-cell strong{color:var(--color-text-primary);font-size:var(--font-size-body);overflow-wrap:anywhere}
.pqv-decision-grid,.pqv-context-grid{display:grid;gap:var(--space-md);margin:0 0 var(--space-sm);max-width:48rem}
.pqv-decision-primary,.pqv-decision-secondary{display:grid;gap:var(--space-sm);min-width:0}
.pqv-fantasy-evidence{margin:0}
.player-dossier-context-action{margin:0;padding:var(--space-sm) var(--space-md) 0}
.player-dossier-context-action strong{color:var(--color-text-primary);font-size:var(--font-size-section-title);letter-spacing:var(--letter-spacing-badge);line-height:var(--line-height-card);text-transform:uppercase}
.pqv-recommendation-confidence{margin:0;padding:0 var(--space-md) var(--space-sm)}
.player-dossier-news-meta{color:var(--color-text-muted);font-size:var(--font-size-badge);letter-spacing:var(--letter-spacing-badge);margin:0 0 var(--space-xs);text-transform:uppercase}
.player-dossier-news-headline{color:var(--color-text-primary);font-size:var(--font-size-body);line-height:var(--line-height-body);margin:0 0 var(--space-xs)}
.player-dossier-news-snippet,.player-dossier-news-quiet{color:var(--color-text-secondary);font-size:var(--font-size-body);line-height:var(--line-height-body);margin:0}
.player-dossier-news-link{margin:0 0 var(--space-sm)}
.player-dossier-news-link a{color:var(--color-text-primary)}
.dg-client-disclosure>summary{cursor:pointer;min-height:var(--touch-target-min);list-style:none}
.dg-client-disclosure-body{padding:var(--space-sm) 0}
.visually-hidden{clip:rect(0 0 0 0);clip-path:inset(50%);height:1px;overflow:hidden;position:absolute;white-space:nowrap;width:1px}

.player-dossier-snapshot,.player-dossier-executive,.player-dossier-career,.player-dossier-recommendation-context,.player-dossier-news-card{margin: var(--space-md) 0;overflow:hidden}
.player-dossier-recommendation-context{margin:0 0 var(--space-sm);max-width:48rem}
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
div[data-testid="stDialog"] .pqv-hero-portrait .player-quick-view-avatar{height:clamp(5.25rem,18vw,7.25rem) !important;width:clamp(5.25rem,18vw,7.25rem) !important}
@media (max-width: 700px){.player-dossier-executive-grid,.player-dossier-snapshot-grid{grid-template-columns:repeat(2, minmax(0, 1fr))}
.player-dossier-executive-metric:nth-child(2n),.player-dossier-snapshot-metric:nth-child(2n){border-right:0}
.player-dossier-snapshot-metric strong,.player-dossier-executive-metric strong{font-size:var(--font-size-body)}
.player-dossier-timeline-copy p,.player-dossier-section-heading p{overflow-wrap:anywhere}
.pqv-glance-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.player-dossier-career-summary{grid-template-columns:repeat(2,minmax(0,1fr))}
.player-dossier-career-metric:nth-child(4n){border-right:var(--border-width-default) solid var(--color-border)}
.player-dossier-career-metric:nth-child(2n){border-right:0}
}
.player-dossier-snapshot-title,.player-dossier-section-heading{padding:0 0 var(--space-xs)}
.pqv-why-recommendation .player-dossier-section-heading,.pqv-fantasy-evidence .player-dossier-section-heading,.pqv-accolades .player-dossier-section-heading,.pqv-career-glance .player-dossier-section-heading,.pqv-career-dossier .player-dossier-section-heading,.pqv-bio .player-dossier-section-heading{border:0;padding:0 0 var(--space-xs)}
.player-dossier-snapshot .player-dossier-snapshot-title,.player-dossier-career .player-dossier-section-heading,.player-dossier-executive .player-dossier-section-heading,.player-dossier-recommendation-context .player-dossier-section-heading{border-bottom:var(--border-width-default) solid var(--color-border);border-left:var(--border-width-semantic) solid var(--color-border-strong);padding:var(--space-sm) var(--space-md)}
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
@media (max-width: 900px){.player-dossier-snapshot-grid,.player-dossier-executive-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
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
.pqv-accolade-cluster{grid-template-columns:repeat(2,minmax(0,1fr))}
.pqv-glance-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (min-width: 1024px){
.pqv-decision-grid,.pqv-context-grid{grid-template-columns:minmax(0,1.15fr) minmax(0,0.85fr);align-items:start}
.pqv-glance-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
.pqv-accolade-cluster{grid-template-columns:repeat(3,minmax(0,1fr))}
}
@media (prefers-reduced-motion: reduce){.player-dossier-snapshot *,.player-dossier-executive *,.player-dossier-career *,.player-dossier-recommendation-context *,.pqv-why-recommendation *,.pqv-accolades *{animation:none !important;transition:none !important}}
"""
