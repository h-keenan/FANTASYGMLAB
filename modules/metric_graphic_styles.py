"""Compact metric-graphic primitives — structure, not decoration."""

METRIC_GRAPHIC_CSS = """
.dg-mg{display:flex;align-items:center;gap:var(--space-2xs);margin:var(--space-2xs) 0 var(--space-xs);max-width:100%;min-width:0}
.dg-mg-strip{display:flex;flex:1;gap:2px;height:8px;max-width:12.5rem;min-width:0}
.dg-mg-strip__cell{background:var(--color-border);border-radius:1px;flex:1 1 0;min-width:3px}
.dg-mg-strip__cell.is-on{background:var(--color-accent)}
.dg-mg-strip__more{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
.dg-mg-status{width:100%}
.dg-mg-status__mark{border:var(--border-width-default) solid var(--color-border-strong);border-radius:50%;box-sizing:border-box;display:inline-block;flex:0 0 10px;height:10px;width:10px}
.dg-mg-status--ok .dg-mg-status__mark{background:var(--color-success);border-color:var(--color-success)}
.dg-mg-status--warn .dg-mg-status__mark,.dg-mg-status--alert .dg-mg-status__mark{background:transparent;border-color:var(--color-warning)}
.dg-mg-status--alert .dg-mg-status__mark{border-color:var(--color-danger)}
.dg-mg-status__meter{background:var(--color-border);border-radius:1px;flex:1;height:6px;min-width:0;overflow:hidden}
.dg-mg-status__fill{background:var(--color-warning);display:block;height:100%;min-width:0}
.dg-mg-status--ok .dg-mg-status__fill{background:var(--color-success);width:8%!important}
.dg-mg-status--alert .dg-mg-status__fill{background:var(--color-danger)}
.dg-mg-rank{align-items:baseline;background:var(--color-surface-raised);border:var(--border-width-default) solid var(--color-border-strong);border-radius:var(--radius-none);color:var(--color-text-primary);display:inline-flex;font:var(--type-supporting-metadata);gap:1px;letter-spacing:var(--letter-spacing-badge);line-height:1;padding:2px 5px}
.dg-mg-rank--gold{border-color:var(--color-accent);color:var(--color-accent)}
.dg-mg-rank--silver{color:var(--color-text-secondary)}
.dg-mg-rank--bronze{color:var(--color-text-muted)}
.dg-mg-rank__hash{font-size:.7em;opacity:.8}
.dg-mg-rank__n{font-weight:var(--font-weight-title)}
.dg-mg-stack{flex-wrap:wrap;height:auto}
.dg-mg-stack__plate{background:var(--color-surface-raised);border:var(--border-width-default) solid var(--color-border-strong);border-radius:1px;display:block;height:7px;width:1.15rem}
.dg-mg-stack__plate.is-lead{border-color:var(--color-accent)}
.dg-mg-stack__more,.dg-mg-stack__empty{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
.dg-mg-podium{align-items:flex-end;height:2.35rem;justify-content:flex-start;max-width:9.5rem}
.dg-mg-podium__step{align-items:center;background:var(--color-surface-muted);border:var(--border-width-default) solid var(--color-border);box-sizing:border-box;display:flex;flex:1 1 0;flex-direction:column;height:70%;justify-content:flex-end;min-width:1.4rem;padding:1px;position:relative}
.dg-mg-podium__step--1{border-color:var(--color-accent);height:100%}
.dg-mg-podium__step--2{height:78%}
.dg-mg-podium__step--3{height:62%}
.dg-mg-podium__fill{background:var(--color-accent);bottom:0;left:0;opacity:.35;position:absolute;right:0}
.dg-mg-podium__step--2 .dg-mg-podium__fill,.dg-mg-podium__step--3 .dg-mg-podium__fill{background:var(--color-text-muted);opacity:.28}
.dg-mg-podium__count,.dg-mg-podium__cap{position:relative;z-index:1}
.dg-mg-podium__count{color:var(--color-text-primary);font:var(--type-supporting-metadata);font-weight:var(--font-weight-title)}
.dg-mg-podium__cap{color:var(--color-text-muted);font-size:.58rem;letter-spacing:var(--letter-spacing-badge);line-height:1;text-transform:uppercase}
.dg-mg-bar{width:100%}
.dg-mg-bar__track{background:var(--color-border);border-radius:1px;display:block;flex:1;height:7px;overflow:hidden}
.dg-mg-bar__fill{background:var(--color-accent);display:block;height:100%}
.dg-mg-timeline{gap:var(--space-xs)}
.dg-mg-timeline__node{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge)}
.dg-mg-timeline__node.is-future{color:var(--color-accent);font-weight:var(--font-weight-title)}
.dg-mg-timeline__rail{background:var(--color-border);flex:0 0 1.75rem;height:2px}
.dg-mg-leader{margin-bottom:0}
.dg-ui-table-row .dg-mg,.summary-tile .dg-mg,.dg-intel-card .dg-mg{max-width:100%}
.dg-ui-table-row .dg-ui-card-body,.summary-tile-value{min-width:0;overflow-wrap:anywhere}
.dg-mg-status--ok{gap:0}
@media (min-width:1024px){
.dg-mg-strip{max-width:14rem}
.dg-mg-podium{height:2.5rem;max-width:10.5rem}
}
@media (max-width:430px){
.dg-mg-podium{height:2.15rem;max-width:100%}
.dg-mg-strip{max-width:100%}
}
"""
