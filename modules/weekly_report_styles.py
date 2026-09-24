"""Token-backed styles for the Weekly League Report surface.

Owns only the Power/Franchise rank-movement badges rendered inline in
modules.weekly_report_ui's summary tiles (via the tile "graphic" slot) — the
shared summary-tile/analysis-card chrome itself lives in workspace_ui/
app_styles and is intentionally left untouched. Scoped to the ``wr-move``
prefix so nothing here can affect any other surface.
"""

WEEKLY_REPORT_CSS = """
/* Weekly Report — rank movement direction badges only */
.wr-move-badge{display:inline-flex;align-items:center;gap:4px;margin-top:var(--space-xs);font-weight:var(--font-weight-metadata);font-size:var(--font-size-caption);letter-spacing:0.01em}
.wr-move-badge__arrow{font-size:0.7em;line-height:1}
.wr-move-badge--up{color:var(--color-success)}
.wr-move-badge--down{color:var(--color-danger)}
.wr-move-badge--flat{color:var(--color-text-muted)}
""".strip()
