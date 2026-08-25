"""Styles for the public Founder Beta marketing landing (injected only on launch)."""

MARKETING_LANDING_CSS = """
body:has(.fgl-landing) .app-hero{display:none!important}
body:has(.fgl-landing) [data-testid="stSidebar"]{display:none!important}
body:has([data-fgl-welcome-flow="welcome"]) [class*="st-key-landing_primary_cta"] button,
body:has([data-fgl-welcome-flow="welcome"]) [class*="st-key-landing_secondary_cta"] button{
  letter-spacing:normal!important;text-transform:none!important;font-weight:700!important
}
body:has(.fgl-landing) div[class*="st-key-"][class*="_global_feedback_control"]{display:none!important}
body:has(.fgl-landing) [data-testid="stMainBlockContainer"]{
  box-sizing:border-box;margin-inline:auto;max-width:min(72rem,calc(100vw - 1.5rem));padding-inline:.2rem;width:100%
}
body:has(.fgl-landing) .legal-footer-links,
body:has(.fgl-landing) .dg-build-identity{
  box-sizing:border-box;margin-inline:auto;max-width:min(72rem,calc(100vw - 1.5rem));width:100%
}
.fgl-landing{box-sizing:border-box;color:var(--color-text-primary,#e5e7eb);display:flex;flex-direction:column;gap:.65rem;margin:0 auto .35rem;max-width:100%;min-width:0;width:100%}
.fgl-landing__hero{background:transparent;border:0;box-sizing:border-box;display:grid;gap:.55rem;max-width:100%;min-width:0;padding:.35rem 0 .15rem}
.fgl-landing__hero--compact{gap:.25rem;padding:.15rem 0}
.fgl-landing__brand-row{align-items:center;display:flex;flex-wrap:wrap;gap:.5rem}
.fgl-landing__product{color:var(--color-text-primary,#f8fafc);font-size:1.15rem;font-weight:800;line-height:1.15}
.fgl-landing__hero-grid{display:grid;gap:.55rem;grid-template-columns:1fr}
.fgl-landing__value{color:var(--color-text-primary,#f8fafc);font-size:clamp(1.2rem,4.6vw,1.55rem);font-weight:800;hyphens:none;line-height:1.2;margin:0;max-width:36rem;overflow-wrap:break-word;word-break:normal}
.fgl-landing__support{color:var(--color-text-secondary,rgba(203,213,225,.92));font-size:.95rem;line-height:1.4;margin:0;max-width:34rem}
.fgl-landing__trust{color:var(--color-text-muted,rgba(148,163,184,.95));font-size:.8rem;line-height:1.35;margin:.15rem 0 .2rem;max-width:34rem}
.fgl-landing__proof-panel{border:1px solid var(--color-border,rgba(148,163,184,.16));border-radius:.55rem;box-sizing:border-box;display:grid;gap:.55rem;min-width:0;padding:.75rem .8rem}
.fgl-landing__proof-panel .fgl-landing__kicker{margin:0}
.fgl-landing__preview{display:grid;gap:.55rem;list-style:none;margin:0;max-width:none;padding:0}
.fgl-landing__preview-item{display:grid;gap:.12rem}
.fgl-landing__preview-item strong{color:var(--color-text-primary,#f8fafc);font-size:.92rem;font-weight:750}
.fgl-landing__preview-item span{color:var(--color-text-secondary,rgba(203,213,225,.9));font-size:.84rem;line-height:1.4;overflow-wrap:anywhere}
.fgl-landing__section{border-block-start:1px solid var(--color-border,rgba(148,163,184,.14));display:grid;gap:.4rem;padding:.7rem 0 .1rem}
.fgl-landing__section h2{color:var(--color-text-primary,#f8fafc);font-size:1.05rem;font-weight:800;margin:0}
.fgl-landing__section h3{color:var(--color-text-primary,#f8fafc);font-size:.9rem;font-weight:750;margin:0 0 .15rem}
.fgl-landing__section p,.fgl-landing__section li{color:var(--color-text-secondary,rgba(203,213,225,.9));font-size:.86rem;line-height:1.4}
.fgl-landing__kicker{color:var(--color-text-muted,rgba(148,163,184,.95));font-size:.68rem;font-weight:750;letter-spacing:.04em;text-transform:uppercase}
.fgl-landing__split{display:grid;gap:.55rem;grid-template-columns:1fr}
.fgl-landing__plan{border:1px solid var(--color-border,rgba(148,163,184,.14));padding:.65rem .7rem}
.fgl-landing__note,.fgl-landing__billing{color:var(--color-text-muted,rgba(168,173,183,.95));font-size:.78rem;margin:.25rem 0 0}
.fgl-landing--deferred{margin-top:.35rem}
body:has(.fgl-landing) .account-confirm-card{margin:.4rem 0 .5rem;padding:.75rem .8rem}
body:has(.fgl-landing) .launch-section-intro,
body:has(.fgl-landing) .launch-account-intro{margin:.15rem 0 .25rem;padding:0;box-shadow:none;border:none;background:transparent}
body:has(.fgl-landing) .launch-import-intro{margin-top:.1rem}
body:has(.fgl-landing) .launch-section-title{font-size:1.15rem;margin-top:.1rem}
body:has(.fgl-landing) .launch-section-copy{font-size:.9rem;margin-top:.1rem}
body:has(.fgl-landing) [data-testid="stVerticalBlockBorderWrapper"]{gap:.4rem}
body:has(.fgl-landing) [class*="st-key-landing_back_cta"] button{font-weight:600!important}
body:has([data-fgl-welcome-flow="welcome"]) [class*="st-key-landing_primary_cta"],
body:has([data-fgl-welcome-flow="welcome"]) [class*="st-key-landing_secondary_cta"]{max-width:100%}
body:has([data-fgl-welcome-flow="welcome"]) [class*="st-key-landing_pricing_cta"]{margin-top:.15rem;max-width:18rem}
@media (max-width:430px){
.fgl-landing__value{font-size:clamp(1.12rem,5vw,1.32rem);overflow-wrap:break-word;word-break:normal;hyphens:none}
body:has(.fgl-landing) [data-testid="stMainBlockContainer"]{max-width:calc(100vw - 1.25rem)}
}
@media (min-width:900px){
.fgl-landing__value{font-size:clamp(1.45rem,2.1vw,2rem);max-width:none}
.fgl-landing__support{font-size:1.02rem;max-width:36rem}
.fgl-landing__split{grid-template-columns:1fr 1fr}
body:has([data-fgl-welcome-flow="welcome"]) [class*="st-key-landing_primary_cta"],
body:has([data-fgl-welcome-flow="welcome"]) [class*="st-key-landing_secondary_cta"]{max-width:22rem}
body:has([data-fgl-welcome-flow="welcome"]) [class*="st-key-landing_secondary_cta"] button{font-weight:600!important}
}
"""
