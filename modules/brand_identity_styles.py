"""FantasyGM Lab Founder Beta brand and identity presentation layer.

Appended last so branding wins over legacy chrome without redesigning layouts.
"""

BRAND_IDENTITY_CSS = """
/* GM Orb chrome is owned by MOBILE_INTERACTION_OVERLAY_CSS */

.dg-brand-mark{align-items:center;box-sizing:border-box;display:inline-flex;justify-content:center;line-height:0;overflow:hidden}
.dg-brand-plate{background:var(--color-surface-primary,#0f1114);border-radius:18%;box-sizing:border-box;display:inline-block;flex:0 0 auto;overflow:hidden;position:relative;vertical-align:middle}
.dg-brand-plate--light{background:var(--color-text-primary, #f8fafc)}
.dg-brand-plate__img{display:block;height:100%;object-fit:contain;width:100%}
.dg-brand-mark--sm{height:1.75rem;min-width:1.75rem;width:1.75rem}
.dg-brand-mark--md{height:2.75rem;min-width:2.75rem;width:2.75rem}
.dg-brand-mark--lg{height:4rem;min-width:4rem;width:4rem}
/* Brand square geometry is owned by APPLICATION_SHELL_CSS. */
.dg-executive-shell__mark{height:28px;width:28px}
.dg-startup-mark{align-items:center;display:inline-flex;justify-content:center;line-height:0}
.dg-startup-mark-img{height:40px;width:40px}
.home-hero-logo-img{display:inline-block}

.dg-founder-badge {
    align-items: center;
    background: color-mix(in srgb, var(--color-shell, #090a0c) 72%, transparent);
    border: var(--border-width-default, 1px) solid color-mix(in srgb, var(--color-border, #2a2e35) 70%, transparent);
    border-inline-start: 2px solid color-mix(in srgb, var(--color-brand-accent, #22d3ee) 72%, transparent);
    box-sizing: border-box;
    color: var(--color-text-secondary, #e5e7eb);
    display: inline-flex;
    gap: 0.55rem;
    max-width: 100%;
    padding: 0.28rem 0.55rem 0.28rem 0.28rem;
}

.dg-founder-badge__mark,
.dg-founder-badge__mark-img {
    align-items: center;
    display: inline-flex;
    flex: 0 0 auto;
    height: 1.45rem;
    justify-content: center;
    min-width: 1.45rem;
    overflow: hidden;
    width: 1.45rem;
}

.dg-founder-badge__mark {
    background: var(--color-text-primary, #f8fafc);
    color: var(--color-brand-mark-ink, #0b1220);
    font-size: 0.58rem;
    font-weight: 900;
    letter-spacing: 0.06em;
}

.dg-founder-badge__copy {
    display: grid;
    gap: 0.05rem;
    min-width: 0;
    text-align: left;
}

.dg-founder-badge__copy strong {
    color: var(--color-text-primary, #f8fafc);
    font-size: 0.68rem;
    font-weight: 850;
    letter-spacing: 0.01em;
    line-height: 1.1;
}

.dg-founder-badge__copy em {
    color: rgba(148, 163, 184, 0.92);
    font-size: 0.56rem;
    font-style: normal;
    font-weight: 750;
    letter-spacing: 0.08em;
    line-height: 1;
    text-transform: uppercase;
}

.dg-founder-badge--compact {
    gap: 0.4rem;
    padding: 0.18rem 0.42rem 0.18rem 0.18rem;
}

.dg-founder-badge--compact .dg-founder-badge__mark,
.dg-founder-badge--compact .dg-founder-badge__mark-img {
    font-size: 0.5rem;
    height: 1.2rem;
    min-width: 1.2rem;
    width: 1.2rem;
}

.dg-founder-badge--compact .dg-founder-badge__copy strong {
    font-size: 0.6rem;
}

.dg-founder-badge--compact .dg-founder-badge__copy em {
    font-size: 0.5rem;
}

.app-hero {
    align-items: flex-start;
    background:
        linear-gradient(180deg, rgba(11, 18, 32, 0.96), rgba(8, 12, 20, 0.94));
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: 2px;
    box-shadow: none;
    display: grid;
    gap: 0.42rem;
    margin: 0 0 0.7rem;
    padding: 0.72rem 0.9rem;
}

.app-hero-top {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    justify-content: space-between;
}

.app-eyebrow {
    color: rgba(148, 163, 184, 0.88);
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.app-hero h1 {
    font-size: clamp(1.25rem, 2.4vw, 1.55rem);
    font-weight: 950;
    letter-spacing: -0.02em;
    line-height: 1.05;
    margin: 0;
}

.app-hero p {
    color: rgba(203, 213, 225, 0.88);
    font-size: 0.82rem;
    line-height: 1.35;
    margin: 0;
    max-width: 42rem;
}

.mobile-gm-experimental-note {
    color: rgba(203, 213, 225, 0.78);
    font-size: 0.68rem;
    line-height: 1.35;
    margin: 0.15rem 0 0.35rem;
}

/* GM sheet kicker/caption chrome owned by MOBILE_INTERACTION_OVERLAY_CSS. */

div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stCaptionContainer"] p {
    margin: 0;
}

div[class*="st-key-mobile_sheet_nav_"][class*="weekly_report"] [data-testid="stButton"] > button,
div[class*="st-key-mobile_sheet_nav_"][class*="trade_analyzer"] [data-testid="stButton"] > button,
div[class*="st-key-mobile_sheet_nav_"][class*="archetypes"] [data-testid="stButton"] > button,
div[class*="st-key-mobile_sheet_nav_"][class*="manager_tendencies"] [data-testid="stButton"] > button,
div[class*="st-key-mobile_sheet_nav_"][class*="live_draft"] [data-testid="stButton"] > button,
div[class*="st-key-mobile_sheet_nav_"][class*="players"] [data-testid="stButton"] > button,
div[class*="st-key-mobile_sheet_nav_"][class*="player_detail"] [data-testid="stButton"] > button,
div[class*="st-key-mobile_sheet_nav_"][class*="teams"] [data-testid="stButton"] > button,
div[class*="st-key-mobile_sheet_nav_"][class*="news"] [data-testid="stButton"] > button {
    border-inline-start-color: rgba(245, 158, 11, 0.55) !important;
}

.dg-premium-chip,.dg-experimental-chip{align-items:center;display:inline-flex;font-size:.58rem;font-weight:850;letter-spacing:.08em;line-height:1;padding:.28rem .42rem;text-transform:uppercase}
.dg-premium-chip{background:var(--color-action-soft, rgba(250,204,21,.14));border:1px solid rgba(250,204,21,.4);color:var(--color-premium, #facc15)}
.dg-experimental-chip{background:var(--color-diagnostic-soft, rgba(139,147,255,.12));border:1px solid rgba(139,147,255,.38);color:var(--color-experimental, #8b93ff)}

.trade-summary-footer {
    align-items: center;
    border-top: 1px solid var(--color-border, rgba(148, 163, 184, 0.16));
    display: flex;
    gap: 0.45rem;
    justify-content: space-between;
    padding-top: 0.45rem;
}

.trade-summary-footer .trade-summary-affordance {
    border-top: 0;
    margin: 0;
    padding-top: 0;
}

.trade-summary-brand,
.trade-detail-brand,
.dg-decision-brand {
    align-items: center;
    color: var(--color-text-muted, #94a3b8);
    display: inline-flex;
    gap: 0.28rem;
    min-width: 0;
}

.trade-detail-brand,
.dg-decision-brand {
    border-bottom: 1px solid var(--color-border, rgba(148, 163, 184, 0.16));
    justify-content: flex-start;
    margin: 0 0 var(--space-sm, 0.5rem);
    padding: 0 0 var(--space-sm, 0.45rem);
    width: 100%;
}

.trade-summary-brand__mark,
.trade-detail-brand__mark,
.trade-summary-brand__mark-img,
.trade-detail-brand__mark-img,
.dg-decision-brand__mark-img,
.dg-compact-mark-img {
    display: inline-block;
    height: 1.75rem;
    object-fit: contain;
    width: 1.75rem;
}

.trade-summary-brand__mark,
.trade-detail-brand__mark {
    background: transparent;
}

.trade-summary-brand__name,
.trade-detail-brand__name {
    font-size: 0.56rem;
    font-weight: 750;
    letter-spacing: 0.02em;
    white-space: nowrap;
}

.trade-summary-brand__badge,
.trade-detail-brand__badge {
    font-size: 0.48rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    opacity: 0.72;
    text-transform: uppercase;
    white-space: nowrap;
}

div[class*="st-key-"][class*="_global_feedback_control"] [data-testid="stPopover"] > button {
    background: rgba(8, 12, 20, 0.92) !important;
    border: 1px solid rgba(148, 163, 184, 0.34) !important;
    border-inline-start: 2px solid color-mix(in srgb, var(--color-accent-strong) 70%, transparent) !important;
    border-radius: 2px !important;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.32) !important;
    color: var(--color-text-secondary, #e5e7eb) !important;
    font-weight: 850 !important;
}

div[class*="st-key-"][class*="_global_feedback_control"] [data-testid="stPopover"] > button:hover {
    border-color: color-mix(in srgb, var(--color-accent-strong) 55%, transparent) !important;
    color: var(--color-text-primary, #f8fafc) !important;
}

.dg-feedback-brand {
    align-items: center;
    display: flex;
    gap: 0.45rem;
    margin: 0 0 0.45rem;
}

.dg-feedback-brand__title {
    color: var(--color-text-primary, #f8fafc);
    font-size: 0.78rem;
    font-weight: 850;
    line-height: 1.2;
}

.dg-feedback-brand__note {
    color: rgba(148, 163, 184, 0.92);
    font-size: 0.68rem;
    line-height: 1.3;
}

.premium-page {
    gap: 1rem;
    margin-inline: auto;
    max-width: 56rem;
}

.premium-page-header {
    padding: 1rem 1.05rem;
}

.premium-page-kicker {
    color: color-mix(in srgb, var(--color-accent-strong) 88%, transparent);
}

.premium-page-title {
    font-size: clamp(1.45rem, 2.6vw, 1.85rem);
    letter-spacing: -0.03em;
}

.premium-page-subtitle {
    max-width: 40rem;
}

.premium-plan-premium {
    background:
        linear-gradient(160deg, color-mix(in srgb, var(--color-accent-strong) 8%, transparent), rgba(8, 12, 20, 0.55)),
        rgba(10, 12, 16, 0.78) !important;
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-accent-strong) 12%, transparent);
}

.premium-plan-row-title {
    font-size: 0.86rem;
}

.premium-plan-row-body {
    font-size: 0.76rem;
}

.premium-billing-note {
    border-left: 2px solid rgba(148, 163, 184, 0.28);
}

.premium-dev-note {
    display: none;
}

@media (min-width: 1024px) {
    .home-command-shell,
    .trade-summary-card,
    .decision-panel,
    .analysis-card,
    .free-agent-card,
    .premium-page,
    .methodology-page {
        max-width: 100%;
    }

    .premium-plan-grid {
        gap: 0.9rem;
    }

    .home-command-shell{
        margin-inline: auto;
        width: 100%;
    }
}

@media (max-width: 430px) {
    .app-hero {
        padding: 0.65rem 0.75rem;
    }

    .trade-summary-brand__badge {
        display: none;
    }
}
"""
