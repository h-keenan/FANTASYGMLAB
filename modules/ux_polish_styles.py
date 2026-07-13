FOUNDER_BETA_UX_CSS = """
<style>
:root {
    --dg-ux-radius: 14px;
    --dg-ux-card-pad: clamp(0.68rem, 2.2vw, 0.9rem);
    --dg-ux-section-gap: clamp(0.72rem, 2.6vw, 1.05rem);
    --dg-ux-control-height: 44px;
}

.league-switch-card-grid {
    display: grid;
    gap: 0.48rem;
    margin: 0.42rem 0 0.7rem;
}

.league-switch-card {
    appearance: none;
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(8, 13, 24, 0.96));
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: var(--dg-ux-radius);
    color: #f8fafc;
    cursor: pointer;
    display: grid;
    gap: 0.2rem;
    min-height: 66px;
    padding: 0.72rem 0.78rem;
    text-align: left;
    touch-action: manipulation;
    width: 100%;
}

.league-switch-card:hover,
.league-switch-card:focus-visible {
    border-color: rgba(103, 232, 249, 0.48);
    outline: none;
}

.league-switch-card-current {
    background: linear-gradient(90deg, rgba(34, 211, 238, 0.14), rgba(15, 23, 42, 0.96));
    border-color: rgba(34, 211, 238, 0.34);
}

.league-switch-card-loading {
    cursor: wait;
    opacity: 0.72;
}

.league-switch-card-title {
    font-size: 0.84rem;
    font-weight: 880;
    line-height: 1.18;
    overflow-wrap: anywhere;
}

.league-switch-card-meta {
    color: rgba(226, 232, 240, 0.66);
    font-size: 0.68rem;
    line-height: 1.25;
}

.league-switch-card-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.28rem;
    margin-top: 0.18rem;
}

.league-switch-card-badge,
.injury-adjustment-badge {
    align-items: center;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 999px;
    display: inline-flex;
    font-size: 0.56rem;
    font-weight: 900;
    letter-spacing: 0.04em;
    line-height: 1;
    min-height: 20px;
    padding: 0.2rem 0.38rem;
    text-transform: uppercase;
}

.league-switch-card-badge-current {
    background: rgba(34, 211, 238, 0.14);
    border-color: rgba(34, 211, 238, 0.32);
    color: #cffafe;
}

.league-switch-card-badge-default {
    background: rgba(226, 232, 240, 0.08);
    color: #e2e8f0;
}

.injury-adjustment-badge {
    background: rgba(249, 115, 22, 0.14);
    border-color: rgba(249, 115, 22, 0.34);
    color: #fed7aa;
    margin-left: 0.3rem;
    vertical-align: middle;
}

.home-command-card-dot,
.summary-tile-dot {
    display: none !important;
}

body:has(.league-actions-sheet-marker) div[data-testid="stPopoverContent"] {
    max-height: min(72dvh, 620px) !important;
    max-width: min(calc(100vw - 24px), 410px) !important;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    padding: 0.72rem !important;
    width: min(calc(100vw - 24px), 410px) !important;
}

.league-actions-sheet-marker {
    height: 0;
    overflow: hidden;
}

.league-actions-section {
    border-top: 1px solid rgba(148, 163, 184, 0.14);
    margin-top: 0.72rem;
    padding-top: 0.72rem;
}

.league-actions-section:first-of-type {
    border-top: 0;
    margin-top: 0;
    padding-top: 0;
}

@media (max-width: 900px) {
    [data-testid="stMainBlockContainer"] {
        padding-left: clamp(0.72rem, 3.2vw, 1rem) !important;
        padding-right: clamp(0.72rem, 3.2vw, 1rem) !important;
    }

    [data-testid="stVerticalBlock"] {
        gap: var(--dg-ux-section-gap);
    }

    .analysis-card,
    .decision-panel,
    .home-command-card,
    .summary-tile,
    .trade-card,
    .free-agent-card,
    .live-rank-row,
    .live-draft-rec-card,
    .draft-review-pick-card {
        border-radius: var(--dg-ux-radius) !important;
        max-width: 100% !important;
        overflow-wrap: anywhere;
    }

    .analysis-card,
    .decision-panel,
    .home-command-card,
    .summary-tile,
    .trade-card,
    .free-agent-card {
        padding: var(--dg-ux-card-pad) !important;
    }

    [data-testid="stButton"] > button,
    [data-testid="stPopover"] > button,
    [data-testid="stFormSubmitButton"] > button {
        min-height: var(--dg-ux-control-height) !important;
    }

    img {
        max-width: 100%;
    }

    .home-command-card-note,
    .summary-tile-note,
    .live-draft-rec-reason,
    .live-rank-reason {
        line-height: 1.34 !important;
    }

    body:has(div[data-testid="stDialog"]) div[class*="st-key-mobile_gm_sheet_trigger_"],
    body:has(div[data-testid="stDialog"]) div[class*="_global_feedback_control"] {
        display: none !important;
    }
}
</style>
"""
