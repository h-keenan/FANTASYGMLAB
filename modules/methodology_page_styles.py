"""Token-backed styles for the static methodology / trust surface."""

METHODOLOGY_PAGE_CSS = """
.methodology-page{display:grid;gap:var(--space-lg);margin-inline:auto;max-width:40rem;min-width:0;padding-block:var(--space-sm) var(--space-lg)}
.methodology-hero,.methodology-card,.methodology-strategy,.methodology-faq-item{border:var(--border-width-default) solid var(--border-subtle);border-radius:var(--radius-panel);min-width:0;padding:var(--space-md)}
.methodology-kicker{color:var(--text-accent);font-size:var(--font-size-badge);font-weight:var(--font-weight-metadata);letter-spacing:var(--letter-spacing-badge);margin:0 0 var(--space-xs);text-transform:uppercase}
.methodology-title,.methodology-heading{color:var(--text-primary);font-weight:var(--font-weight-display);letter-spacing:-0.03em;margin:0 0 var(--space-sm);text-transform:none}
.methodology-title{font-size:clamp(1.35rem, 4.6vw, 1.85rem);line-height:1.15}
.methodology-heading{font-size:clamp(1.05rem, 3.4vw, 1.28rem);line-height:1.25}
.methodology-lede,.methodology-copy{color:var(--text-secondary);font-size:var(--font-size-body);line-height:1.45;margin:0;max-width:40rem;overflow-wrap:anywhere}
.methodology-lede{color:var(--text-primary)}
.methodology-section{display:grid;gap:var(--space-sm);min-width:0}
.methodology-factor-grid,.methodology-strategy-list{display:grid;gap:var(--space-sm);grid-template-columns: 1fr;min-width:0}
.methodology-card-title,.methodology-strategy-label{color:var(--text-primary);font-size:var(--font-size-caption);font-weight:var(--font-weight-title);letter-spacing:0.01em;margin:0 0 var(--space-xs)}
.methodology-list{color:var(--text-secondary);display:grid;gap:var(--space-xs);margin:0;padding-inline-start:1.1rem}
.methodology-faq{display:grid;gap:var(--space-sm);min-width:0}
.methodology-faq-item summary{color:var(--text-primary);cursor:pointer;font-size:var(--font-size-caption);font-weight:var(--font-weight-title);list-style:none;min-height: var(--touch-target-min);padding-block:var(--space-xs)}
.methodology-faq-item summary::-webkit-details-marker{display:none}
.methodology-faq-item[open] summary{margin-bottom:var(--space-xs)}
.methodology-limits{border-left:var(--border-width-semantic) solid var(--border-strong);padding-left:var(--space-sm)}
@media (min-width: 700px){.methodology-page{max-width:56rem}.methodology-factor-grid{grid-template-columns:1fr 1fr}.methodology-strategy-list{grid-template-columns:1fr 1fr}}
@media (max-width: 430px){.methodology-page{gap:var(--space-md);padding-inline:0}.methodology-hero,.methodology-card,.methodology-strategy,.methodology-faq-item{padding:var(--space-sm) var(--space-md)}}
"""
