"""Canonical dense-list row families for ranked / result / candidate surfaces.

Owner: dense list information hierarchy.
Consumed early via APP_CSS (after component families). Do not append a late
override sheet for list density.
"""

from __future__ import annotations

# Compact form — keep Founder Beta APP_CSS budget headroom. Token-backed only.
DENSE_LIST_CSS = """
/* Dense list row anatomy */
.dg-ranked-board,.dg-dense-board,.live-rank-list,.live-draft-board,.explorer-pick-grid{display:grid;gap:var(--space-xs);margin:0 0 var(--space-md);max-width:min(100%,90rem)}
.explorer-pick-grid{grid-template-columns:1fr}
.dg-ranked-row.dg-dense-row{align-items:start;background:var(--surface-1);border:var(--border-width-default) solid var(--border-standard);border-radius:var(--radius-panel);box-shadow:var(--shadow-none);display:grid;gap:var(--space-xs) var(--space-sm);grid-template-columns:auto minmax(0,1.4fr) minmax(5.25rem,7rem) minmax(0,1fr);min-height:0;overflow:hidden;padding:var(--space-xs) var(--space-sm);position:relative}
.dg-ranked-row.dg-dense-row--no-lead{grid-template-columns:minmax(0,1.4fr) minmax(5.25rem,7rem) minmax(0,1fr)}
.dg-ranked-row.dg-dense-row--standard{padding:var(--space-sm)}.dg-ranked-row.dg-dense-row--rich{padding:var(--space-sm) var(--space-md)}
.dg-ranked-row--current,.dg-intel-card.dg-ranked-row--current{border-inline-start:var(--border-width-semantic) solid var(--color-accent)}
.dg-ranked-row--top,.dg-dense-row--emphasis{border-color:var(--border-accent)}
.dg-ranked-rank,.dg-dense-lead{align-items:center;background:var(--surface-raised);border:var(--border-width-default) solid var(--border-standard);border-radius:var(--radius-control);color:var(--text-primary);display:flex;font:var(--font-weight-display) var(--font-size-badge)/1 var(--font-family-sans);height:1.75rem;justify-content:center;min-width:1.75rem;padding:0 var(--space-2xs)}
.dg-dense-dual-rank{align-content:center;display:grid;gap:1px;height:auto;justify-items:start;min-width:4.75rem;padding:var(--space-2xs) var(--space-xs)}
.dg-dense-dual-rank__item{color:var(--text-muted);font:var(--type-supporting-metadata);font-variant-numeric:tabular-nums;letter-spacing:.02em;line-height:1.2;text-transform:uppercase;white-space:nowrap}
.dg-team-comparison-board{max-height:none;overflow:visible}
.dg-dense-dual-rank__item strong{color:var(--text-primary);font-weight:var(--font-weight-display)}
.dg-ranked-identity,.dg-dense-identity{align-items:center;display:flex;gap:var(--space-xs);min-width:0}
.dg-ranked-copy,.dg-dense-identity__copy{display:grid;gap:0;min-width:0}
.dg-ranked-team,.dg-dense-identity__primary{color:var(--text-primary);font:var(--type-card-title);overflow-wrap:anywhere}
.dg-ranked-owner,.dg-dense-identity__secondary{color:var(--text-muted);font:var(--type-supporting-metadata);margin-top:1px;overflow-wrap:anywhere}
.dg-dense-identity__secondary a{color:inherit;text-decoration-thickness:1px;text-underline-offset:2px}
.dg-ranked-logo{align-items:center;background:var(--surface-raised);border:var(--border-width-default) solid var(--border-standard);border-radius:50%;color:var(--text-primary);display:flex;flex:0 0 2rem;font:var(--font-weight-display) var(--font-size-badge)/1 var(--font-family-sans);height:2rem;justify-content:center;overflow:hidden;width:2rem}
.dg-ranked-logo img{height:100%;object-fit:cover;width:100%}
.dg-dense-metric,.dg-ranked-metric{align-content:start;display:grid;gap:0;justify-items:end;min-width:0}
.dg-dense-metric__value,.dg-ranked-metric-value{color:var(--text-primary);font:var(--type-primary-metric);font-variant-numeric:tabular-nums;letter-spacing:-.02em;line-height:1.05;max-width:none;min-width:max-content;overflow:visible;text-overflow:clip;white-space:nowrap}
.dg-dense-metric__label,.dg-ranked-metric-label{color:var(--text-muted);font:var(--type-supporting-metadata);max-width:7rem;text-align:right}
.dg-dense-trail{display:grid;gap:var(--space-2xs);min-width:0}
.dg-dense-status,.dg-ranked-interp{color:var(--text-secondary);display:inline-flex;flex-wrap:wrap;font:var(--font-weight-metadata) var(--font-size-caption)/1.25 var(--font-family-sans);gap:0 var(--space-2xs);min-width:0}
.dg-dense-status__primary{color:var(--text-primary);font-weight:var(--font-weight-title)}
.dg-dense-status__secondary{color:var(--text-secondary)}
.dg-dense-status__secondary::before{color:var(--text-muted);content:"·";margin-inline-end:var(--space-2xs)}
.dg-dense-meta,.dg-ranked-secondary{color:var(--text-muted);display:flex;flex-wrap:wrap;font:var(--type-supporting-metadata);gap:0 var(--space-2xs);margin:0}
.dg-dense-meta__sep{color:var(--color-border)}
.dg-dense-exception{align-items:center;background:var(--color-danger-soft);border:var(--border-width-default) solid var(--color-danger);border-radius:var(--radius-pill);color:var(--color-danger);display:inline-flex;flex-wrap:wrap;font:var(--font-weight-metadata) var(--font-size-badge)/1.25 var(--font-family-sans);gap:var(--space-2xs);max-width:100%;padding:1px var(--space-xs);width:fit-content}
.dg-dense-exception__label::after{content:": "}
.dg-dense-exception__value{font-variant-numeric:tabular-nums}
@media (max-width:900px){.dg-ranked-row.dg-dense-row{grid-template-areas:"lead id metric" "lead trail trail";grid-template-columns:auto minmax(0,1fr) minmax(4.75rem,6.25rem)}.dg-ranked-row.dg-dense-row--no-lead{grid-template-areas:"id metric" "trail trail";grid-template-columns:minmax(0,1fr) minmax(4.75rem,6.25rem)}.dg-ranked-rank,.dg-dense-lead{grid-area:lead}.dg-ranked-identity,.dg-dense-identity{grid-area:id}.dg-dense-metric,.dg-ranked-metric{grid-area:metric}.dg-dense-trail{grid-area:trail}}
@media (max-width:640px){.dg-ranked-row.dg-dense-row{gap:var(--space-2xs) var(--space-xs);grid-template-areas:"lead id metric" "trail trail trail";padding:var(--space-xs)}.dg-ranked-row.dg-dense-row--no-lead{grid-template-areas:"id metric" "trail trail"}.dg-ranked-logo{flex-basis:1.75rem;height:1.75rem;width:1.75rem}.dg-dense-metric__label,.dg-ranked-metric-label{max-width:5.5rem}.dg-dense-dual-rank{min-width:4.25rem}.dg-dense-dual-rank__item{white-space:normal}.dg-team-comparison-board .dg-ranked-row.dg-dense-row{grid-template-areas:"lead id" "trail trail";grid-template-columns:auto minmax(0,1fr)}.dg-team-comparison-board .dg-dense-metric{display:none}.dg-team-comparison-board .dg-dense-status{display:grid;gap:var(--space-2xs)}.dg-team-comparison-board .dg-dense-status__secondary::before{content:none;margin:0}.dg-team-comparison-board .dg-dense-status__primary,.dg-team-comparison-board .dg-dense-status__secondary{overflow:visible;text-overflow:clip;white-space:normal}}
@media (min-width:901px){.dg-team-comparison-board .dg-ranked-row.dg-dense-row{grid-template-columns:auto minmax(0,1.4fr) minmax(6.5rem,8rem) minmax(0,1fr)}}
""".strip()
