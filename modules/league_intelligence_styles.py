"""Token-backed styles for the League Intelligence feed.

Row geometry lives in dense_list_styles (canonical). This module only owns
timeline grouping, disclosure prose, and control touch targets.
"""

LEAGUE_INTELLIGENCE_CSS = """
/* League Intelligence — non-row chrome only */
.dg-intelligence-group{margin:var(--space-xl) 0 var(--space-sm);color:var(--color-text-muted);font-size:var(--font-size-caption);font-weight:var(--font-weight-button);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-intelligence-explanation{margin:0 0 var(--space-md);padding:var(--space-md);border-left:var(--border-width-semantic) solid var(--color-border-strong);background:var(--color-surface-muted);color:var(--color-text-secondary);font-size:var(--font-size-body);line-height:var(--line-height-body)}
.dg-intelligence-explanation__summary{color:var(--color-text-primary);margin:0 0 var(--space-sm)}
.dg-intelligence-explanation p{margin:0}
div[class*="st-key-league_intelligence_"] button{min-height:var(--touch-target-min)}
""".strip()
