"""Token-backed presentation for the head-to-head Player Compare surface.

Route-owned CSS (see tests/test_app_css_architecture.py) — injected alongside
PLAYER_QUICK_VIEW_CSS wherever Compare renders, since Compare is reached from
and shares the Player Quick View dialog family. No page-specific colors: every
value below is an existing modules/design_tokens.py token.
"""

PLAYER_COMPARE_CSS = """
.pqv-compare-shell{display:grid;gap:var(--space-md);max-width:44rem;min-width:0;width:100%}
.pqv-compare-identity{align-items:start;display:grid;gap:var(--space-sm);grid-template-columns:1fr auto 1fr}
.pqv-compare-vs{align-items:center;color:var(--color-text-muted);display:flex;font-size:var(--font-size-badge);font-weight:700;justify-content:center;letter-spacing:var(--letter-spacing-badge);padding-top:var(--space-xl)}
.pqv-compare-rows{display:grid;gap:0}
.pqv-compare-row{align-items:center;border-bottom:var(--border-width-default) solid var(--color-border);display:grid;gap:var(--space-xs);grid-template-columns:1fr auto 1fr;padding-block:var(--space-xs)}
.pqv-compare-row:last-child{border-bottom:none}
.pqv-compare-label{color:var(--color-text-secondary);flex:1;font-size:var(--font-size-badge);font-weight:700;letter-spacing:var(--letter-spacing-badge);padding-inline:var(--space-xs);text-align:center;text-transform:uppercase}
.pqv-compare-cell{display:flex;justify-content:center;min-width:0}
.pqv-compare-pill{border:var(--border-width-default) solid transparent;border-radius:var(--radius-sm);color:var(--color-text-primary);font-size:var(--font-size-body);font-weight:700;padding:var(--space-2xs) var(--space-sm)}
.pqv-compare-pill-win{background:var(--color-success-soft);border-color:var(--color-success);color:var(--color-success)}
.pqv-compare-pill-text{font-size:var(--font-size-caption);font-weight:600;padding-block:var(--space-2xs)}
.pqv-compare-narrative{display:grid;gap:var(--space-md);grid-template-columns:1fr 1fr}
.pqv-compare-narrative-col{min-width:0}
.pqv-compare-narrative-name{color:var(--color-text-muted);font-size:var(--font-size-badge);font-weight:700;letter-spacing:var(--letter-spacing-badge);margin-bottom:var(--space-2xs);text-transform:uppercase}
.pqv-compare-narrative-text{color:var(--color-text-secondary);font-size:var(--font-size-caption);line-height:var(--line-height-body);margin:0}
div[class*="st-key-pqv_compare_reset_"] button{color:var(--color-accent)!important}
"""
