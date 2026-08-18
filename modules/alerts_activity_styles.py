"""Alerts / Activity route styles — square segmented controls, not APP_CSS."""

ALERTS_ACTIVITY_CSS = """
.dg-alerts-shell{
    max-width:52rem;
    min-width:0;
    width:100%;
}
.dg-alerts-masthead{
    border-bottom:var(--border-width-default) solid var(--color-border);
    margin:0 0 var(--space-md);
    padding:0 0 var(--space-sm);
}
.dg-alerts-kicker{
    color:var(--color-text-muted);
    font-size:var(--font-size-badge);
    letter-spacing:var(--letter-spacing-badge);
    margin:0 0 var(--space-2xs);
    text-transform:uppercase;
}
.dg-alerts-lede{
    color:var(--color-text-secondary);
    font:var(--font-body);
    margin:var(--space-xs) 0 0;
}
.dg-alerts-row{
    border-bottom:var(--border-width-default) solid var(--color-border);
    display:grid;
    gap:var(--space-sm);
    grid-template-columns:3.25rem minmax(0,1fr);
    padding:var(--space-sm) 0;
}
.dg-alerts-glyph{
    align-items:center;
    border:var(--border-width-default) solid var(--color-border);
    color:var(--color-text-primary);
    display:flex;
    font-size:var(--font-size-badge);
    font-weight:700;
    justify-content:center;
    letter-spacing:0.04em;
    min-height:2.5rem;
    padding:0 var(--space-2xs);
    text-transform:uppercase;
}
.dg-alerts-headline{
    color:var(--color-text-primary);
    font:var(--font-body-strong);
    margin:0;
}
.dg-alerts-context{
    color:var(--color-text-secondary);
    font:var(--font-caption);
    margin:var(--space-2xs) 0 0;
}
.dg-alerts-meta{
    color:var(--color-text-muted);
    display:flex;
    flex-wrap:wrap;
    gap:var(--space-xs);
    margin:var(--space-2xs) 0 0;
}
.dg-alerts-unread{
    background:var(--color-accent);
    display:inline-block;
    height:0.45rem;
    width:0.45rem;
}
.dg-alerts-empty{
    color:var(--color-text-secondary);
    font:var(--font-body);
    margin:var(--space-md) 0;
}
div[class*="st-key-alerts_filter_"] [data-testid="stButtonGroup"],
div[class*="st-key-alerts_filter_"] [data-baseweb="button-group"]{
    border-radius:0 !important;
    gap:0 !important;
}
div[class*="st-key-alerts_filter_"] [data-testid="stButtonGroup"] > div,
div[class*="st-key-alerts_filter_"] [data-baseweb="button-group"] > div{
    border-radius:0 !important;
    gap:0 !important;
}
div[class*="st-key-alerts_filter_"] [data-testid="stButtonGroup"] button,
div[class*="st-key-alerts_filter_"] [data-baseweb="button-group"] button{
    border-radius:0 !important;
    letter-spacing:0.02em;
    min-height:2.25rem;
}
div[class*="st-key-alerts_filter_"] [data-testid="stButtonGroup"] button[kind="primary"],
div[class*="st-key-alerts_filter_"] [data-testid="stButtonGroup"] button[aria-pressed="true"],
div[class*="st-key-alerts_filter_"] [data-baseweb="button-group"] button[aria-pressed="true"]{
    border-radius:0 !important;
}
"""
