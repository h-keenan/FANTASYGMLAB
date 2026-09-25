"""Token-backed styles for the League Intelligence feed.

Row geometry lives in dense_list_styles (canonical). This module only owns
timeline grouping, disclosure prose, and control touch targets.
"""

LEAGUE_INTELLIGENCE_CSS = """
/* League Intelligence — non-row chrome only */
.dg-intelligence-group{display:flex;align-items:center;gap:var(--space-xs);margin:var(--space-xl) 0 var(--space-sm);color:var(--color-text-muted);font-size:var(--font-size-caption);font-weight:var(--font-weight-button);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-intelligence-group::before{content:"";display:inline-block;width:3px;height:0.8em;background:currentColor}
.dg-intelligence-group--attention{color:var(--color-danger)}
.dg-intelligence-group--roster{color:var(--color-accent)}
.dg-intelligence-group--waiver{color:var(--color-opportunity)}
.dg-intelligence-group--league{color:var(--color-text-muted)}
.dg-intelligence-signal--danger{color:var(--color-danger)}
.dg-intelligence-signal--opportunity{color:var(--color-opportunity)}
.dg-intelligence-item.player-card-tappable{cursor:pointer}
.dg-intelligence-item.player-card-tappable:hover{background:var(--color-surface-raised);border-color:var(--color-border-strong)}
.dg-intelligence-item.player-card-tappable:focus-visible{box-shadow:var(--focus-ring);outline:none}
.dg-intelligence-item .dg-dense-identity__secondary .dg-ui-badge{margin-inline-start:var(--space-xs);vertical-align:middle}
.dg-intelligence-explanation{margin:0 0 var(--space-md);padding:var(--space-md);border-left:var(--border-width-semantic) solid var(--color-border-strong);background:var(--color-surface-muted);color:var(--color-text-secondary);font-size:var(--font-size-body);line-height:var(--line-height-body)}
.dg-intelligence-explanation__summary{color:var(--color-text-primary);margin:0 0 var(--space-sm)}
.dg-intelligence-explanation p{margin:0}
div[class*="st-key-league_intelligence_"] button{min-height:var(--touch-target-min)}
""".strip()
