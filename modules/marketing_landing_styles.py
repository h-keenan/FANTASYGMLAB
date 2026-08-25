"""Styles for the public Founder Beta marketing landing (injected only on launch)."""

MARKETING_LANDING_CSS = """
body:has(.fgl-landing) .app-hero{display:none!important}
.fgl-landing{box-sizing:border-box;color:var(--color-text-primary,#e5e7eb);display:flex;flex-direction:column;gap:var(--space-md,.75rem);margin:0 auto 1.25rem;max-width:min(72rem,calc(100vw - 2rem));min-width:0;width:100%}
.fgl-landing__hero-grid{align-items:stretch;display:grid;gap:var(--space-lg,1.25rem);grid-template-columns:1fr}
.fgl-landing__hero{background:var(--color-surface,#0b0d10);border:var(--border-width-default,1px) solid var(--color-border,rgba(148,163,184,.16));box-sizing:border-box;display:grid;gap:.75rem;max-width:100%;min-width:0;padding:1.15rem 1.2rem 1.25rem}
.fgl-landing__brand-row{align-items:center;display:flex;flex-wrap:wrap;gap:.55rem}
.fgl-landing__product{color:var(--color-text-primary,#f8fafc);font-size:clamp(1.35rem,2.4vw,1.85rem);font-weight:900;line-height:1.1}
.fgl-landing__value{color:var(--color-text-primary,#f8fafc);font-size:clamp(1.05rem,4.2vw,1.65rem);font-weight:800;hyphens:none;line-height:1.22;margin:0;max-width:36rem;overflow-wrap:break-word;word-break:normal}
.fgl-landing__support{color:var(--color-text-secondary,rgba(203,213,225,.92));font-size:1rem;line-height:1.45;margin:0;max-width:34rem}
.fgl-landing__trust{color:var(--color-text-muted,rgba(148,163,184,.95));font-size:.82rem;line-height:1.4;margin:.15rem 0 0;max-width:34rem}
.fgl-landing__guest-note{color:var(--color-text-muted,rgba(148,163,184,.95));font-size:.8rem;line-height:1.4;margin:.35rem 0 0;max-width:34rem}
.fgl-landing__preview{display:grid;gap:.35rem;list-style:none;margin:.55rem 0 0;max-width:34rem;padding:0}
.fgl-landing__preview-item{border-block-start:1px solid var(--color-border,rgba(148,163,184,.12));display:grid;gap:.1rem;padding-top:.4rem}
.fgl-landing__preview-item:first-child{border-block-start:0;padding-top:0}
.fgl-landing__preview-item strong{color:var(--color-text-primary,#f8fafc);font-size:.82rem;font-weight:750}
.fgl-landing__preview-item span{color:var(--color-text-secondary,rgba(203,213,225,.9));font-size:.78rem;line-height:1.35}
.fgl-landing__composition{background:var(--color-surface-muted,rgba(15,23,42,.55));border:var(--border-width-default,1px) solid var(--color-border,rgba(148,163,184,.16));border-inline-start:var(--border-width-semantic,3px) solid var(--color-accent-strong,#22d3ee);box-sizing:border-box;display:grid;gap:.65rem;min-width:0;padding:1rem 1.05rem}
.fgl-landing__composition-kicker{color:var(--color-text-muted,rgba(148,163,184,.95));font-size:.68rem;font-weight:750;letter-spacing:.08em;text-transform:uppercase}
.fgl-landing__composition-item{border-block-start:1px solid var(--color-border,rgba(148,163,184,.12));padding-top:.55rem}
.fgl-landing__composition-item:first-of-type{border-block-start:0;padding-top:0}
.fgl-landing__composition-item h3{color:var(--color-text-primary,#f8fafc);font-size:.95rem;font-weight:750;margin:0 0 .2rem}
.fgl-landing__composition-item p{color:var(--color-text-secondary,rgba(203,213,225,.9));font-size:.84rem;line-height:1.4;margin:0}
body:has(.fgl-landing) [class*="st-key-landing_primary_cta"] button{font-weight:750!important}
body:has(.fgl-landing) [class*="st-key-landing_secondary_cta"] button{font-weight:650!important}
body:has(.fgl-landing) [class*="st-key-landing_guest_cta"]{margin-top:.15rem}
body:has(.fgl-landing) [class*="st-key-landing_guest_cta"] button{background:transparent!important;border:1px solid var(--color-border,rgba(148,163,184,.28))!important;box-shadow:none!important;color:var(--color-text-secondary,rgba(203,213,225,.95))!important;font-weight:600!important}
body:has(.fgl-landing) [class*="st-key-landing_pricing_cta"] button{font-size:.86rem!important}
body:has(.fgl-landing) div[class*="st-key-"][class*="_global_feedback_control"]{display:none!important}
.fgl-landing__section{border-block-start:1px solid var(--color-border,rgba(148,163,184,.14));display:grid;gap:.4rem;padding:.85rem 0 .1rem}
.fgl-landing__section--deferred{margin-top:.15rem}
.fgl-landing__section h2{color:var(--color-text-primary,#f8fafc);font-size:clamp(1.05rem,2vw,1.25rem);font-weight:800;margin:0}
.fgl-landing__section h3{color:var(--color-text-primary,#f8fafc);font-size:.9rem;font-weight:750;margin:0 0 .15rem}
.fgl-landing__section p,.fgl-landing__section li{color:var(--color-text-secondary,rgba(203,213,225,.9));font-size:.88rem;line-height:1.4}
.fgl-landing__section ul{margin:0;padding-inline-start:1rem}
.fgl-landing__kicker{color:var(--color-text-muted,rgba(148,163,184,.95));font-size:.68rem;font-weight:750;letter-spacing:.08em;text-transform:uppercase}
.fgl-landing__split{display:grid;gap:.55rem;grid-template-columns:1fr}
.fgl-landing__plan{border:1px solid var(--color-border,rgba(148,163,184,.14));padding:.65rem .7rem}
.fgl-landing__plan--premium{border-color:rgba(250,204,21,.35)}
.fgl-landing__note,.fgl-landing__billing{color:var(--color-text-muted,rgba(168,173,183,.95));font-size:.78rem;margin:.25rem 0 0}
.fgl-landing__proof{display:grid;gap:.5rem;max-width:100%;min-width:0;padding:.15rem 0 .2rem}
.fgl-landing__proof h2{color:var(--color-text-primary,#f8fafc);font-size:clamp(1.05rem,2vw,1.25rem);font-weight:800;margin:0}
.fgl-landing__proof-grid{box-sizing:border-box;display:grid;gap:.5rem;grid-template-columns:1fr;max-width:100%;min-width:0}
.fgl-landing__proof-card{border:1px solid var(--color-border,rgba(148,163,184,.16));box-sizing:border-box;max-width:100%;min-width:0;padding:.65rem .7rem}
.fgl-landing__proof-card h3{color:var(--color-text-primary,#f8fafc);font-size:.9rem;font-weight:750;margin:0 0 .15rem}
.fgl-landing__proof-card p{color:var(--color-text-secondary,rgba(203,213,225,.9));font-size:.84rem;line-height:1.4;margin:0;overflow-wrap:anywhere}
body:has(.fgl-landing) .account-confirm-card{margin:.4rem 0 .5rem;padding:.75rem .8rem}
body:has(.fgl-landing) .launch-section-intro{margin:.4rem 0 .3rem;padding:.2rem 0;box-shadow:none;border:none;background:transparent}
body:has(.fgl-landing) .launch-import-intro{margin-top:.35rem;padding:.55rem 0 .2rem;border-block-start:1px solid var(--color-border,rgba(148,163,184,.16))}
body:has(.fgl-landing) .launch-account-intro{margin-top:.45rem;padding-top:.4rem;border-block-start:1px solid var(--color-border,rgba(148,163,184,.12))}
body:has(.fgl-landing) .launch-section-title{font-size:1.05rem;margin-top:.12rem}
body:has(.fgl-landing) .launch-section-copy{font-size:.88rem;margin-top:.12rem}
body:has(.fgl-landing) [data-testid="stVerticalBlockBorderWrapper"]{gap:.45rem}
@media (max-width:430px){.fgl-landing{max-width:calc(100vw - 1.25rem);margin-inline:auto}.fgl-landing__hero{padding:.85rem}.fgl-landing__value{font-size:clamp(1.02rem,5.2vw,1.28rem);overflow-wrap:break-word;word-break:normal;hyphens:none}}
@media (min-width:900px){.fgl-landing__hero-grid{grid-template-columns:minmax(0,1.15fr) minmax(16rem,.85fr);align-items:start}.fgl-landing__hero{padding:1.4rem 1.5rem}.fgl-landing__split,.fgl-landing__proof-grid{grid-template-columns:1fr 1fr}}
@media (min-width:1280px){.fgl-landing{max-width:74rem}}
"""
