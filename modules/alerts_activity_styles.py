"""Alerts / Activity route styles — square segmented controls, not APP_CSS."""

ALERTS_ACTIVITY_CSS = """
.dg-alerts-shell{
    max-width:52rem;
    min-width:0;
    width:100%;
}
.dg-alerts-masthead{
    align-items:baseline;
    display:flex;
    gap:var(--space-sm);
    margin:0 0 var(--space-xs);
    padding:0;
}
.dg-alerts-kicker{
    color:var(--color-text-primary);
    font:var(--font-label);
    letter-spacing:var(--letter-spacing-label);
    margin:0;
    text-transform:uppercase;
}
.dg-alerts-lede{
    color:var(--color-text-muted);
    font:var(--font-caption);
    margin:0;
}
.dg-alerts-row{
    border-bottom:var(--border-width-default) solid var(--color-border);
    display:grid;
    gap:var(--space-sm);
    grid-template-columns:3.25rem minmax(0,1fr);
    padding:var(--space-sm) 0;
}
.dg-alerts-row--urgent{
    background:color-mix(in srgb,var(--color-warning) 8%,transparent);
    border:var(--border-width-default) solid var(--color-warning);
    border-left:0.3rem solid var(--color-warning);
    margin:var(--space-xs) 0;
    padding:var(--space-sm);
}
.dg-alerts-row--player{
    grid-template-columns:3.5rem minmax(0,1fr);
}
.dg-alerts-row--urgent.dg-alerts-row--player{
    grid-template-columns:4rem minmax(0,1fr);
}
.dg-alerts-player-visual,
.dg-alerts-portrait{
    background:var(--color-surface-muted);
    border:var(--border-width-default) solid var(--color-border);
    box-sizing:border-box;
    height:3.5rem;
    min-width:0;
    overflow:hidden;
    position:relative;
    width:3.5rem;
}
.dg-alerts-row--urgent .dg-alerts-player-visual,
.dg-alerts-row--urgent .dg-alerts-portrait{
    border-color:var(--color-warning);
    height:4rem;
    width:4rem;
}
.dg-alerts-portrait img,
.dg-alerts-portrait .dg-player-headshot-image{
    height:100%;
    inset:0;
    object-fit:cover;
    object-position:var(--dg-headshot-focus-x,44%) var(--dg-headshot-focus,18%);
    position:absolute;
    transform:scale(1.16);
    transform-origin:var(--dg-headshot-focus-x,44%) var(--dg-headshot-focus,18%);
    width:100%;
}
.dg-alerts-portrait .dg-player-headshot-fallback{
    align-items:center;
    color:var(--color-text-secondary);
    display:flex;
    font:var(--font-label);
    inset:0;
    justify-content:center;
    position:absolute;
}
div[class*="st-key-alerts_item_"]{
    border-bottom:var(--border-width-default) solid var(--color-border);
}
div[class*="st-key-alerts_item_"] .dg-alerts-row{
    border-bottom:0;
}
div[class*="st-key-alerts_item_"] [data-testid="stButton"]{
    margin:calc(-1 * var(--space-xs)) 0 var(--space-sm) calc(3.5rem + var(--space-sm));
}
.dg-alerts-row--urgent .dg-alerts-glyph{
    border-color:var(--color-warning);
    color:var(--color-warning);
}
.dg-alerts-row--news:not(.dg-alerts-row--urgent){
    opacity:0.88;
}
.dg-alerts-badges{
    display:flex;
    flex-wrap:wrap;
    gap:var(--space-2xs);
    margin:var(--space-xs) 0 0;
}
.dg-alerts-badge{
    border:var(--border-width-default) solid var(--color-border);
    color:var(--color-text-secondary);
    font:var(--font-label);
    letter-spacing:var(--letter-spacing-label);
    padding:0.15rem var(--space-xs);
}
.dg-alerts-badge--my{
    border-color:var(--color-accent);
    color:var(--color-accent);
}
.dg-alerts-badge--risk{
    border-color:var(--color-warning);
    color:var(--color-warning);
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
    display:flex !important;
    flex-wrap:nowrap !important;
    gap:0 !important;
    max-width:100%;
    overflow-x:auto;
    overflow-y:hidden;
    -webkit-overflow-scrolling:touch;
}
div[class*="st-key-alerts_filter_"] [data-testid="stButtonGroup"] > div,
div[class*="st-key-alerts_filter_"] [data-baseweb="button-group"] > div{
    border-radius:0 !important;
    display:flex !important;
    flex:0 0 auto;
    flex-wrap:nowrap !important;
    gap:0 !important;
}
div[class*="st-key-alerts_filter_"] [data-testid="stButtonGroup"] button,
div[class*="st-key-alerts_filter_"] [data-baseweb="button-group"] button{
    border-radius:0 !important;
    flex:0 0 auto;
    letter-spacing:0.02em;
    min-height:2.25rem;
    white-space:nowrap;
}
div[class*="st-key-alerts_filter_"] [data-testid="stButtonGroup"] button[kind="primary"],
div[class*="st-key-alerts_filter_"] [data-testid="stButtonGroup"] button[aria-pressed="true"],
div[class*="st-key-alerts_filter_"] [data-baseweb="button-group"] button[aria-pressed="true"]{
    border-radius:0 !important;
}
@media (max-width:430px){
    .dg-alerts-row{
        grid-template-columns:2.75rem minmax(0,1fr);
    }
    .dg-alerts-row--player{
        grid-template-columns:3.25rem minmax(0,1fr);
    }
    .dg-alerts-row--urgent.dg-alerts-row--player{
        grid-template-columns:3.5rem minmax(0,1fr);
    }
    .dg-alerts-player-visual,
    .dg-alerts-portrait{
        height:3.25rem;
        width:3.25rem;
    }
    .dg-alerts-row--urgent .dg-alerts-player-visual,
    .dg-alerts-row--urgent .dg-alerts-portrait{
        height:3.5rem;
        width:3.5rem;
    }
    div[class*="st-key-alerts_item_"] [data-testid="stButton"]{
        margin-left:calc(3.25rem + var(--space-sm));
    }
    .dg-alerts-row--urgent{
        padding:var(--space-sm) var(--space-xs);
    }
    .dg-alerts-badge{
        white-space:normal;
    }
    .dg-alerts-headline,
    .dg-alerts-context{
        min-width:0;
        word-break:normal;
        overflow-wrap:anywhere;
    }
}
"""
