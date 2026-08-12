"""Styles for the public Founder Beta marketing landing (injected only on launch)."""

MARKETING_LANDING_CSS = """
body:has(.fgl-landing) .app-hero{display:none!important}
.fgl-landing{color:#e5e7eb;display:flex;flex-direction:column;gap:.9rem;margin:0 0 .85rem;max-width:72rem}
.fgl-landing__hero{background:linear-gradient(180deg,#0b0d10,#050607);border:1px solid rgba(148,163,184,.16);border-inline-start:3px solid #22d3ee;display:grid;gap:.65rem;overflow:hidden;padding:.85rem;position:relative}
.fgl-landing__hero::before,.fgl-landing__hero::after{border:solid transparent;border-radius:0 100% 0 0;border-top-width:2px;border-right-width:2px;content:"";height:58%;pointer-events:none;position:absolute;right:-2%;top:8%;width:42%}
.fgl-landing__hero::before{border-right-color:rgba(34,211,238,.35);border-top-color:rgba(34,211,238,.35)}
.fgl-landing__hero::after{border-right-color:rgba(250,204,21,.22);border-top-color:rgba(250,204,21,.22);height:48%;top:14%;width:34%}
.fgl-landing__brand-row,.fgl-landing__value,.fgl-landing__support{position:relative;z-index:1}
.fgl-landing__brand-row{align-items:center;display:flex;flex-wrap:wrap;gap:.6rem}
.fgl-landing__product{color:#f8fafc;font-size:clamp(1.2rem,2.8vw,1.65rem);font-weight:950;line-height:1.05}
.fgl-landing__value{color:#f8fafc;font-size:clamp(1.02rem,2.3vw,1.35rem);font-weight:800;line-height:1.2;margin:0;max-width:38rem}
.fgl-landing__support{color:rgba(203,213,225,.9);font-size:.86rem;line-height:1.35;margin:0;max-width:40rem}
.fgl-landing__trust{color:rgba(148,163,184,.95);font-size:.72rem;letter-spacing:.02em;line-height:1.3;margin:.15rem 0 0;max-width:40rem}
.fgl-landing__section{border-block-start:1px solid rgba(148,163,184,.14);display:grid;gap:.4rem;padding:.7rem 0 .1rem}
.fgl-landing__section h2{color:#f8fafc;font-size:clamp(.95rem,2vw,1.15rem);font-weight:850;margin:0}
.fgl-landing__section h3{color:#f8fafc;font-size:.86rem;font-weight:800;margin:0 0 .2rem}
.fgl-landing__section p,.fgl-landing__section li{color:rgba(203,213,225,.9);font-size:.82rem;line-height:1.35}
.fgl-landing__section ul{margin:0;padding-inline-start:.95rem}
.fgl-landing__kicker{color:rgba(34,211,238,.92);font-size:.62rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase}
.fgl-landing__split{display:grid;gap:.55rem;grid-template-columns:1fr}
.fgl-landing__plan{border:1px solid rgba(148,163,184,.14);padding:.55rem .65rem}
.fgl-landing__plan--premium{border-color:rgba(250,204,21,.35)}
.fgl-landing__note,.fgl-landing__billing{color:rgba(168,173,183,.95);font-size:.74rem;margin:.35rem 0 0}
.fgl-landing__focus-note{border:1px solid rgba(34,211,238,.28);color:#e2e8f0;font-size:.76rem;margin:.2rem 0 .6rem;padding:.4rem .55rem}
.fgl-landing__shot-caption{color:rgba(203,213,225,.92);font-size:.78rem;margin:.55rem 0 .2rem}
@media (min-width:768px){.fgl-landing__split{grid-template-columns:1fr 1fr}.fgl-landing__hero{padding:1.05rem 1.15rem}}
"""
