"""Alerts / Activity route styles — square segmented controls, not APP_CSS."""

ALERTS_ACTIVITY_CSS = """
.dg-alerts-group{
    align-items:center;
    color:var(--color-text-muted);
    display:flex;
    font:var(--type-supporting-metadata);
    gap:var(--space-xs);
    letter-spacing:var(--letter-spacing-badge);
    margin:var(--space-lg) 0 var(--space-xs);
    text-transform:uppercase;
}
.dg-alerts-group__bar{
    background:currentColor;
    display:inline-block;
    height:0.8rem;
    width:3px;
}
.dg-alerts-group--injury{
    color:var(--color-danger);
}
.dg-alerts-group--transaction{
    color:var(--color-accent);
}
.dg-alerts-group--role{
    color:var(--color-success);
}
.dg-alerts-group--other{
    color:var(--color-text-muted);
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
    grid-template-columns:3.25rem minmax(0,1fr);
}
.dg-alerts-row--urgent.dg-alerts-row--player{
    grid-template-columns:3.25rem minmax(0,1fr);
}
.dg-alerts-portrait{
    --avatar-size:3.25rem;
    align-self:start;
    background:var(--color-surface-muted);
    border:var(--border-width-default) solid var(--color-border);
    box-sizing:border-box;
    flex:0 0 var(--avatar-size);
    height:var(--avatar-size);
    min-width:0;
    overflow:hidden;
    position:relative;
    width:var(--avatar-size);
}
.dg-alerts-row--urgent .dg-alerts-portrait{
    border-color:var(--color-warning);
}
.dg-alerts-row--urgent.dg-alerts-row--injury{
    background:color-mix(in srgb,var(--color-danger) 8%,transparent);
    border-color:var(--color-danger);
    border-left-color:var(--color-danger);
}
.dg-alerts-row--urgent.dg-alerts-row--injury .dg-alerts-portrait{
    border-color:var(--color-danger);
}
div[class*="st-key-alerts_item_"]{
    border-bottom:var(--border-width-default) solid var(--color-border);
}
div[class*="st-key-alerts_item_"] .dg-alerts-row{
    border-bottom:0;
}
div[class*="st-key-alerts_actions_"]{
    margin:var(--space-2xs) 0 var(--space-sm);
    max-width:100%;
    min-width:0;
    width:100%;
}
div[class*="st-key-alerts_actions_"] [data-testid="stHorizontalBlock"]{
    align-items:center !important;
    display:flex !important;
    flex-wrap:wrap !important;
    gap:var(--space-xs) var(--space-sm) !important;
    justify-content:flex-start !important;
    min-width:0;
    width:100%;
}
div[class*="st-key-alerts_actions_"] [data-testid="stColumn"]{
    flex:0 1 auto !important;
    min-width:0;
    padding:0 !important;
    width:auto !important;
}
div[class*="st-key-alerts_actions_"] [data-testid="stButton"]{
    display:block;
    margin:0;
    width:auto;
}
div[class*="st-key-alerts_actions_"] [data-testid="stButton"] > button{
    font:var(--type-supporting-metadata)!important;
    min-height:var(--touch-target-min);
    padding:0 var(--space-sm)!important;
    white-space:nowrap;
    width:auto!important;
}
.dg-alerts-row--read .dg-alerts-headline{
    color:var(--color-text-secondary);
}
.dg-alerts-row--teammate{
    opacity:0.96;
}
.dg-alerts-row--urgent .dg-alerts-glyph{
    border-color:var(--color-warning);
    color:var(--color-warning);
}
.dg-alerts-row--urgent.dg-alerts-row--injury .dg-alerts-glyph{
    border-color:var(--color-danger);
    color:var(--color-danger);
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
    font:var(--type-supporting-metadata);
    letter-spacing:var(--letter-spacing-badge);
    padding:0.15rem var(--space-xs);
}
.dg-alerts-badge--my{
    border-color:var(--color-accent);
    color:var(--color-accent);
}
.dg-alerts-badge--risk{
    border-color:var(--color-danger);
    color:var(--color-danger);
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
    font:var(--type-card-title);
    margin:0;
}
.dg-alerts-context{
    color:var(--color-text-secondary);
    font:var(--type-caption-emphasis);
    margin:var(--space-2xs) 0 0;
}
.dg-alerts-meta{
    color:var(--color-text-muted);
    display:flex;
    flex-wrap:wrap;
    font:var(--type-supporting-metadata);
    gap:var(--space-xs);
    margin:var(--space-2xs) 0 0;
}
.dg-alerts-source{
    color:var(--color-text-secondary);
    font:var(--type-supporting-metadata);
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
        grid-template-columns:2.75rem minmax(0,1fr);
    }
    .dg-alerts-row--urgent.dg-alerts-row--player{
        grid-template-columns:2.75rem minmax(0,1fr);
    }
    .dg-alerts-portrait{
        --avatar-size:2.75rem;
    }
    div[class*="st-key-alerts_actions_"] [data-testid="stHorizontalBlock"]{
        gap:var(--space-2xs) var(--space-xs) !important;
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
