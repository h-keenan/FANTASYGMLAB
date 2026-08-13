"""Final shared visual-identity layer for the DynastyGM command center.

This stylesheet intentionally follows all legacy page CSS so shared contracts
win without changing page renderers or business behavior.
"""

COMMAND_CENTER_CSS = """
/* DynastyGM Visual Identity Phase 1: monochrome, rectilinear command center. */
:root {
    color-scheme: dark;
}

.stApp {
    background: var(--color-bg) !important;
    color: var(--color-text-primary);
}

main,
[data-testid="stMain"],
[data-testid="stAppViewContainer"] {
    background: transparent !important;
}

/* Native controls: engineered geometry, restrained interaction feedback.
   Executive League/Alerts/You popovers are owned solely by
   EXECUTIVE_COMMAND_HEADER_CSS — do not set popover geometry here. */
.stButton > button,
.stDownloadButton > button,
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"],
[data-baseweb="input"] > div,
[data-baseweb="textarea"] > div,
input,
textarea,
select {
    border-color: var(--color-border-strong) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-none) !important;
}
/* Select/dropdown chrome owned by COMPONENT_FAMILY_CSS — do not restyle here. */

.stButton > button,
.stDownloadButton > button,
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"] {
    font-size: var(--font-size-caption) !important;
    font-weight: var(--font-weight-button) !important;
    letter-spacing: var(--letter-spacing-badge);
    min-height: var(--control-min-height);
    text-transform: uppercase;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
    background: var(--color-surface-raised) !important;
    border-color: var(--color-text-secondary) !important;
    transform: none !important;
}

/* One panel contract across migrated and legacy production surfaces. */
.dg-ui-card,
.dg-ui-empty-state,
.trade-idea-card,
.waiver-recommendation-card,
.scan-card,
.compact-player-row,
.summary-tile,
.team-card,
.league-team-card,
.draft-team-card,
.premium-card,
.settings-card,
.player-detail-panel,
.player-detail-section,
.player-quick-view-recommendation-card,
.player-quick-view-detail-row,
.player-quick-view-stat-row,
[data-testid="stAlert"],
div[data-testid="stExpander"]{
    background: var(--color-surface-primary) !important;
    border: var(--border-width-default) solid var(--color-border) !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-none) !important;
}

.dg-ui-card--elevated,
div[data-testid="stDialog"] div[role="dialog"]{
    box-shadow: var(--shadow-card) !important;
}

.dg-ui-card--premium{
    border-left-color: var(--color-premium) !important;
}

.dg-ui-card--experimental{
    border-left-color: var(--color-experimental) !important;
}

/* Canonical player-card geometry across all current consumers. */
.scan-card,
.compact-player-row,
.dg-ui-player-card{
    border-left: var(--border-width-semantic) solid var(--color-border-strong) !important;
    min-width: 0;
    overflow: hidden;
}

.scan-card.scan-card-tappable:hover,
.compact-player-row.scan-card-tappable:hover,
.dg-ui-player-card:hover{
    background: var(--color-surface-raised) !important;
    border-color: var(--color-border-strong) !important;
    transform: none !important;
}

.scan-card-avatar,
.compact-player-avatar,
.player-detail-avatar,
.player-quick-view-avatar{
    background: var(--color-surface-secondary) !important;
    border-color: var(--color-border-strong) !important;
    border-radius: var(--radius-none) !important;
}

.scan-card-name,
.compact-player-name{
    color: var(--color-text-primary) !important;
    font-weight: var(--font-weight-title) !important;
}

.scan-card-meta,
.compact-player-meta,
.scan-card-kpi-label{
    color: var(--color-text-muted) !important;
}

/* Prestige is the only default player-card accent language. */
.player-prestige,
.player-status-pill,
.dg-ui-badge {
    background: var(--color-surface-muted) !important;
    border: var(--border-width-default) solid currentColor !important;
    border-radius: var(--radius-none) !important;
    box-shadow: var(--shadow-none) !important;
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.player-prestige-elite { color: var(--color-prestige-elite) !important; }
.player-prestige-starter { color: var(--color-prestige-starter) !important; }
.player-prestige-contributor { color: var(--color-prestige-contributor) !important; }
.player-prestige-development { color: var(--color-prestige-development) !important; }
.player-prestige-depth { color: var(--color-prestige-depth) !important; }
.player-prestige-replacement { color: var(--color-prestige-replacement) !important; }

.player-position-badge,
.scan-card-position,
.compact-player-position,
.player-support-chip,
.trade-player-chip,
.waiver-player-chip {
    background: var(--color-surface-muted) !important;
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-radius: var(--radius-none) !important;
    color: var(--color-text-secondary) !important;
}

/* Section hierarchy and dashboard density. */
.dg-ui-eyebrow,
.section-kicker,
.card-kicker,
.metric-label{
    color: var(--color-text-muted) !important;
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

.dg-ui-section-header,
.section-header {
    border-bottom: var(--border-width-default) solid var(--color-border);
    padding-bottom: var(--space-sm);
}

.dg-ui-section-title,
.section-title{
    letter-spacing: -0.01em;
}

/* Analytics tables. */
[data-testid="stDataFrame"],
[data-testid="stTable"],
.stDataFrame,
table {
    border-radius: var(--radius-none) !important;
    font-variant-numeric: tabular-nums;
}

table {
    border-collapse: collapse;
}

table th {
    background: var(--color-surface-secondary) !important;
    color: var(--color-text-secondary) !important;
    font-size: var(--font-size-badge);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}

table td,
table th {
    border-color: var(--color-border) !important;
}

table tbody tr:nth-child(even) {
    background: var(--color-surface-muted);
}

/* Existing modal framework, restyled rather than replaced. */
div[data-testid="stDialog"] div[role="dialog"] {
    background: var(--color-shell) !important;
    border: var(--border-width-default) solid var(--color-border-strong) !important;
    border-radius: var(--radius-none) !important;
}

.dg-modal-header,
.player-detail-header,
.player-quick-view-header-band {
    background: var(--color-surface-secondary) !important;
    border-radius: var(--radius-none) !important;
    border-bottom-color: var(--color-border-strong) !important;
}

/* Semantic accents remain available only for meaning. */
.dg-ui-badge--success { color: var(--color-success) !important; }
.dg-ui-badge--opportunity { color: var(--color-opportunity) !important; }
.dg-ui-badge--caution { color: var(--color-warning) !important; }
.dg-ui-badge--danger { color: var(--color-danger) !important; }
.dg-ui-badge--premium { color: var(--color-premium) !important; }
.dg-ui-badge--experimental { color: var(--color-experimental) !important; }

@media (max-width: 760px) {
    .dg-ui-card,
.dg-ui-empty-state{
        padding: var(--space-md) !important;
    }

    .scan-card,
.compact-player-row{
        min-height: var(--touch-target-min);
    }

    .stButton > button,
    .stDownloadButton > button {
        min-height: var(--touch-target-min) !important;
    }
}

@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
    }
}
"""
