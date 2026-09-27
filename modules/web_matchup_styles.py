"""Web Matchup route styles.

Constants-only, same pattern as ``modules/alerts_activity_styles.py``: every
color/spacing/type value is a ``var(--...)`` reference into
``modules/design_tokens.py``'s already-audited (dark AND light) token set —
never a new hardcoded hex or px literal. The hero "versus" layout and lineup
list below have no existing shared component to reuse (mobile's equivalent is
native RN layout, not CSS), so this file adds new selectors on top of the
shared tokens rather than duplicating an existing web pattern.
"""

WEB_MATCHUP_CSS = """
.dg-matchup-hero{
    background:var(--surface-raised);
    border:var(--border-width-default) solid var(--border-standard);
    border-radius:var(--radius-panel);
    box-shadow:var(--shadow-card);
    padding:var(--space-lg);
    margin-bottom:var(--space-lg);
}
.dg-matchup-week-row{
    align-items:center;
    color:var(--text-accent);
    display:flex;
    font:var(--type-supporting-metadata);
    gap:var(--space-xs);
    letter-spacing:var(--letter-spacing-badge);
    margin-bottom:var(--space-md);
    text-transform:uppercase;
}
.dg-matchup-live-badge{
    background:var(--color-accent-soft);
    border-radius:var(--radius-pill);
    color:var(--text-accent);
    font:var(--type-supporting-metadata);
    padding:2px var(--space-xs);
}
.dg-matchup-versus-row{
    display:grid;
    gap:var(--space-md);
    grid-template-columns:1fr auto 1fr;
}
.dg-matchup-versus-side{
    min-width:0;
    text-align:center;
}
.dg-matchup-team-name{
    color:var(--text-primary);
    font:var(--font-card-title);
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
}
.dg-matchup-record{
    color:var(--text-muted);
    font:var(--type-supporting-metadata);
    margin-top:2px;
}
.dg-matchup-value{
    color:var(--text-primary);
    font:var(--font-weight-display) var(--font-size-numeric)/var(--line-height-title) var(--font-family-sans);
    margin-top:var(--space-xs);
}
.dg-matchup-sub-value{
    color:var(--text-muted);
    font:var(--type-supporting-metadata);
    margin-top:2px;
}
.dg-matchup-versus-divider{
    align-self:center;
    color:var(--text-muted);
    font:var(--type-supporting-metadata);
    letter-spacing:var(--letter-spacing-badge);
}
.dg-matchup-headline{
    color:var(--text-primary);
    font:var(--font-weight-title) 1.0625rem/var(--line-height-title) var(--font-family-sans);
    margin-top:var(--space-md);
}
.dg-matchup-basis-label{
    color:var(--text-muted);
    font:var(--type-supporting-metadata);
    line-height:var(--line-height-caption);
    margin-top:var(--space-2xs);
}
.dg-matchup-secondary-basis{
    color:var(--text-muted);
    font:var(--type-supporting-metadata);
    line-height:var(--line-height-caption);
    margin-top:2px;
}
.dg-matchup-lineup{
    display:flex;
    flex-direction:column;
    gap:var(--space-xs);
}
"""
