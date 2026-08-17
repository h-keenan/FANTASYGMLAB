from modules.design_tokens import DESIGN_TOKEN_CSS
from modules.football_asset_styles import FOOTBALL_ASSET_CSS
from modules.league_intelligence_styles import LEAGUE_INTELLIGENCE_CSS
from modules.recommendation_trust_ux import RECOMMENDATION_TRUST_CSS
from modules.visual_hierarchy_styles import VISUAL_HIERARCHY_CSS
from modules.founder_beta_quick_fix_styles import FOUNDER_BETA_QUICK_FIX_CSS
from modules.ui_primitive_styles import UI_PRIMITIVE_CSS
from modules.component_family_styles import COMPONENT_FAMILY_CSS
from modules.dense_list_styles import DENSE_LIST_CSS
from modules.ui_modal_styles import UI_MODAL_CSS
from modules.application_shell_styles import APPLICATION_SHELL_CSS
from modules.interface_reimagining_styles import INTERFACE_REIMAGINING_CSS
from modules.mobile_workflow_styles import MOBILE_WORKFLOW_CSS
from modules.visual_identity_styles import COMMAND_CENTER_CSS
from modules.founder_beta_consistency_styles import FOUNDER_BETA_CONSISTENCY_CSS
from modules.brand_identity_styles import BRAND_IDENTITY_CSS
from modules.desktop_executive_layout_styles import DESKTOP_EXECUTIVE_LAYOUT_CSS
from modules.executive_workflow_compression_styles import EXECUTIVE_WORKFLOW_COMPRESSION_CSS
from modules.executive_design_unify_styles import EXECUTIVE_DESIGN_UNIFY_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.metric_graphic_styles import METRIC_GRAPHIC_CSS
from modules.css_ship import ship_css

# Midfile is ship-compacted at assembly time (comments preserved) for protobuf/
# APP_CSS headroom. Imported module constants stay verbatim for ownership tests.
_APP_CSS_MIDFILE = """
:root {
    --dg-accent: var(--color-accent);
    --dg-accent-strong: var(--color-accent-strong);
    --dg-success: var(--color-success);
    --dg-warning: var(--color-warning);
    --dg-danger: var(--color-danger);
    --dg-premium: var(--color-premium);
    --dg-elite: var(--color-action);
    --dg-surface-0: var(--color-bg);
    --dg-surface-1: var(--color-surface-primary);
    --dg-surface-2: var(--color-surface-secondary);
    --dg-surface-3: var(--color-surface-raised);
    --dg-border: var(--color-border);
    --dg-text: var(--color-text-primary);
    --dg-text-soft: var(--color-text-secondary);
    --dg-text-muted: var(--color-text-muted);
}
.stApp {
    background: var(--color-bg);
    color: var(--color-text-primary);
}
main,
main p,
main label,
main span,
main div,
main h1,
main h2,
main h3,
main h4 {
    color: #f8fafc;
}
.block-container {
    max-width: 1380px;
    padding: 0.8rem 2rem 2.2rem;
}
.dg-page-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.36rem;
    margin-top: 0.42rem;
}
.dg-glyph-chip,
.dg-tier-chip {
    align-items: center;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: var(--radius-pill);
    color: var(--dg-text-soft);
    display: inline-flex;
    font-size: 0.64rem;
    font-weight: 860;
    gap: 0.28rem;
    letter-spacing: 0.02em;
    line-height: 1;
    padding: 0.28rem 0.52rem;
    box-shadow:
        inset 0 1px 0 rgba(248, 250, 252, 0.05),
        0 8px 18px rgba(2, 6, 23, 0.18);
    white-space: nowrap;
}
.dg-glyph-chip-primary {
    background: color-mix(in srgb, var(--color-accent-strong) 12%, transparent);
    border-color: color-mix(in srgb, var(--color-accent-strong) 28%, transparent);
    color: var(--color-accent);
}
.dg-glyph-chip-success {
    background: rgba(20, 184, 166, 0.12);
    border-color: rgba(20, 184, 166, 0.26);
    color: #99f6e4;
}
.dg-glyph-chip-warning {
    background: rgba(245, 158, 11, 0.12);
    border-color: rgba(245, 158, 11, 0.26);
    color: #fde68a;
}
.dg-glyph-chip-premium {
    background: rgba(168, 85, 247, 0.12);
    border-color: rgba(168, 85, 247, 0.26);
    color: #e9d5ff;
}
.dg-card-primary,
.dg-card-secondary,
.dg-card-reference,
.dg-card-warning {
    backdrop-filter: blur(14px);
    border-radius: var(--radius-panel);
    overflow: hidden;
    position: relative;
}
.dg-card-primary {
    border-color: color-mix(in srgb, var(--color-accent-strong) 26%, transparent) !important;
    box-shadow:
        0 14px 28px rgba(2, 6, 23, 0.2),
        inset 0 1px 0 color-mix(in srgb, var(--color-accent-strong) 8%, transparent);
}
.dg-card-secondary {
    border-color: rgba(148, 163, 184, 0.14) !important;
    box-shadow:
        0 14px 28px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(248, 250, 252, 0.04);
}
.dg-card-reference {
    border-color: rgba(99, 102, 241, 0.18) !important;
    box-shadow:
        0 14px 28px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(99, 102, 241, 0.05);
}
.dg-card-warning {
    border-color: rgba(245, 158, 11, 0.26) !important;
    box-shadow:
        0 14px 28px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(245, 158, 11, 0.05);
}
.dg-card-primary::after,
.dg-card-secondary::after,
.dg-card-reference::after,
.dg-card-warning::after {
    content: "";
    height: 2px;
    left: 0;
    opacity: 0.9;
    position: absolute;
    right: 0;
    top: 0;
}
.dg-card-primary::after {
    background: linear-gradient(90deg, color-mix(in srgb, var(--color-accent-strong) 98%, transparent), rgba(45, 212, 191, 0.92));
}
.dg-card-secondary::after {
    background: linear-gradient(90deg, rgba(148, 163, 184, 0.78), rgba(226, 232, 240, 0.42));
}
.dg-card-reference::after {
    background: linear-gradient(90deg, rgba(129, 140, 248, 0.88), rgba(168, 85, 247, 0.78));
}
.dg-card-warning::after {
    background: linear-gradient(90deg, rgba(245, 158, 11, 0.98), rgba(239, 68, 68, 0.84));
}
.app-degraded-state {
    background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.035), transparent 34%),
        linear-gradient(180deg, rgba(15, 23, 42, 0.72), rgba(8, 13, 24, 0.78));
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: var(--radius-panel);
    color: var(--dg-text-soft);
    font-size: 0.82rem;
    line-height: 1.36;
    margin: 0.42rem 0;
    padding: 0.72rem 0.78rem;
}
.app-degraded-state {
    border-color: rgba(245, 158, 11, 0.24);
    color: #fde68a;
}
.dg-tier-chip {
    letter-spacing: 0.01em;
    padding: 0.3rem 0.56rem;
    position: relative;
    box-shadow:
        inset 0 1px 0 rgba(248, 250, 252, 0.08),
        0 10px 20px rgba(2, 6, 23, 0.2);
}
.dg-tier-elite {
    background: linear-gradient(180deg, rgba(250, 204, 21, 0.22), rgba(217, 119, 6, 0.16));
    border-color: rgba(250, 204, 21, 0.34);
    color: #fef08a;
}
.dg-tier-star {
    background: linear-gradient(180deg, rgba(168, 85, 247, 0.2), rgba(99, 102, 241, 0.14));
    border-color: rgba(168, 85, 247, 0.3);
    color: #e9d5ff;
}
.dg-tier-core-starter {
    background: color-mix(in srgb, var(--color-accent-strong) 12%, transparent);
    border-color: color-mix(in srgb, var(--color-accent-strong) 28%, transparent);
    color: var(--color-accent);
}
.dg-tier-starter {
    background: rgba(20, 184, 166, 0.12);
    border-color: rgba(20, 184, 166, 0.28);
    color: #99f6e4;
}
.dg-tier-contributor {
    background: rgba(245, 158, 11, 0.12);
    border-color: rgba(245, 158, 11, 0.26);
    color: #fde68a;
}
.dg-tier-depth {
    background: rgba(148, 163, 184, 0.12);
    border-color: rgba(148, 163, 184, 0.24);
    color: #cbd5e1;
}
.dg-tier-developmental {
    background: rgba(71, 85, 105, 0.28);
    border-color: rgba(100, 116, 139, 0.3);
    color: #cbd5e1;
}
.player-status-pill {
    align-items: center;
    backdrop-filter: blur(12px);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: var(--radius-pill);
    box-shadow:
        inset 0 1px 0 rgba(248, 250, 252, 0.06),
        0 8px 18px rgba(2, 6, 23, 0.18);
    color: #e2e8f0;
    display: inline-flex;
    font-size: 0.68rem;
    font-weight: 900;
    gap: 0.34rem;
    line-height: 1;
    max-width: 100%;
    padding: 0.34rem 0.58rem;
    white-space: nowrap;
}
.player-status-glyph {
    align-items: center;
    background: rgba(2, 6, 23, 0.26);
    border-radius: var(--radius-pill);
    color: #f8fafc;
    display: inline-flex;
    flex: 0 0 auto;
    font-size: 0.56rem;
    font-weight: 950;
    height: 1.16rem;
    justify-content: center;
    min-width: 1.16rem;
    padding: 0 0.18rem;
}
.player-status-pill-premium {
    background: linear-gradient(180deg, rgba(226, 232, 240, 0.2), rgba(148, 163, 184, 0.08));
    border-color: rgba(226, 232, 240, 0.34);
    color: #f8fafc;
}
.player-status-pill-elite {
    background: linear-gradient(180deg, rgba(250, 204, 21, 0.22), rgba(217, 119, 6, 0.1));
    border-color: rgba(250, 204, 21, 0.4);
    color: #fef3c7;
}
.player-status-pill-star {
    background: linear-gradient(180deg, rgba(168, 85, 247, 0.22), rgba(99, 102, 241, 0.1));
    border-color: rgba(196, 181, 253, 0.36);
    color: #f3e8ff;
}
.player-status-pill-core {
    background: linear-gradient(180deg, color-mix(in srgb, var(--color-accent-strong) 20%, transparent), color-mix(in srgb, var(--color-accent-strong) 8%, transparent));
    border-color: color-mix(in srgb, var(--color-accent) 34%, transparent);
    color: #dbeafe;
}
.player-status-pill-starter,
.player-status-pill-rise {
    background: linear-gradient(180deg, rgba(20, 184, 166, 0.18), rgba(15, 118, 110, 0.08));
    border-color: rgba(45, 212, 191, 0.32);
    color: #ccfbf1;
}
.player-status-pill-contributor {
    background: linear-gradient(180deg, rgba(245, 158, 11, 0.18), rgba(180, 83, 9, 0.08));
    border-color: rgba(251, 191, 36, 0.32);
    color: #fef3c7;
}
.player-status-pill-move {
    background: linear-gradient(180deg, rgba(249, 115, 22, 0.18), rgba(234, 88, 12, 0.08));
    border-color: rgba(251, 146, 60, 0.32);
    color: #fde68a;
}
.player-status-pill-hold {
    background: linear-gradient(180deg, rgba(71, 85, 105, 0.34), rgba(51, 65, 85, 0.2));
    border-color: rgba(148, 163, 184, 0.28);
    color: #e2e8f0;
}
.player-status-pill-risk {
    background: rgba(127, 29, 29, 0.16);
    border-color: rgba(248, 113, 113, 0.34);
    color: #fecaca;
}
.player-status-pill-drop {
    background: linear-gradient(180deg, rgba(239, 68, 68, 0.2), rgba(185, 28, 28, 0.08));
    border-color: rgba(248, 113, 113, 0.36);
    color: #fecaca;
}
.player-status-pill-neutral {
    background: rgba(30, 41, 59, 0.72);
    border-color: rgba(148, 163, 184, 0.2);
    color: #cbd5e1;
}
.player-support-chip {
    background: rgba(30, 41, 59, 0.78);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: var(--radius-pill);
    color: #cbd5e1;
    display: inline-flex;
    font-size: 0.62rem;
    font-weight: 800;
    line-height: 1;
    padding: 0.22rem 0.42rem;
    white-space: nowrap;
}
.player-support-chip-success {
    background: rgba(34, 197, 94, 0.12);
    border-color: rgba(74, 222, 128, 0.26);
    color: #bbf7d0;
}
.player-support-chip-warning {
    background: rgba(249, 115, 22, 0.12);
    border-color: rgba(251, 146, 60, 0.28);
    color: #fdba74;
}
.player-support-chip-premium {
    background: rgba(250, 204, 21, 0.12);
    border-color: rgba(250, 204, 21, 0.24);
    color: #fde68a;
}
.player-support-chip-hold {
    background: rgba(71, 85, 105, 0.28);
    border-color: rgba(148, 163, 184, 0.24);
    color: #e2e8f0;
}
.player-support-chip-risk {
    background: rgba(127, 29, 29, 0.2);
    border-color: rgba(248, 113, 113, 0.28);
    color: #fecaca;
}
.platform-sidebar-card {
    background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(9, 14, 26, 0.96));
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: var(--radius-panel);
    box-shadow: 0 18px 38px rgba(2, 6, 23, 0.28);
    margin: 0.25rem 0 1rem;
    padding: 0.95rem 1rem;
}
.platform-sidebar-top {
    align-items: center;
    display: flex;
    gap: 0.9rem;
}
.sidebar-logo-wrap {
    align-items: center;
    background: linear-gradient(160deg, var(--color-surface-raised), var(--color-surface-secondary));
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: var(--radius-panel);
    color: #f8fafc;
    display: flex;
    font-size: 0.94rem;
    font-weight: 900;
    height: 54px;
    justify-content: center;
    overflow: hidden;
    width: 54px;
}
.sidebar-logo-wrap img {
    height: 100%;
    object-fit: cover;
    width: 100%;
}
.platform-sidebar-eyebrow {
    color: var(--color-accent);
    font-size: 0.7rem;
    font-weight: 800;
    text-transform: uppercase;
}
.platform-sidebar-name {
    color: #f8fafc;
    font-size: 1rem;
    font-weight: 860;
    line-height: 1.12;
    margin-top: 0.18rem;
}
.platform-sidebar-meta {
    color: #94a3b8;
    font-size: 0.82rem;
    line-height: 1.35;
    margin-top: 0.18rem;
}
.desktop-sidebar-nav {
    display: block;
}
.mobile-gm-sheet-marker {
    display: none;
}
.mobile-gm-floating-trigger-marker {
    display: none;
}
.mobile-gm-sheet-kicker {
    color: var(--color-accent);
    font-size: 0.62rem;
    font-weight: 900;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.mobile-gm-sheet-title {
    color: #f8fafc;
    font-size: 0.92rem;
    font-weight: 900;
    line-height: 1.08;
    margin-top: 0.14rem;
}
.mobile-gm-sheet-note {
    color: #94a3b8;
    font-size: 0.74rem;
    line-height: 1.24;
    margin-top: 0.14rem;
}
.home-status-strip {
    display: grid;
    gap: 0.46rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin: 0.56rem 0 0.72rem;
}
.home-status-pill {
    background: rgba(8, 15, 28, 0.78);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    min-width: 0;
    padding: 0.56rem 0.62rem;
}
.home-status-pill-risk {
    border-color: rgba(245, 158, 11, 0.24);
}
.home-status-pill-need {
    border-color: rgba(239, 68, 68, 0.22);
}
.home-status-pill-draft {
    border-color: rgba(99, 102, 241, 0.22);
}
.home-status-label {
    color: #94a3b8;
    font-size: 0.62rem;
    font-weight: 820;
    text-transform: uppercase;
}
.home-status-value {
    color: #f8fafc;
    font-size: 0.84rem;
    font-weight: 860;
    line-height: 1.14;
    margin-top: 0.16rem;
}
.home-status-note {
    color: #cbd5e1;
    font-size: 0.72rem;
    line-height: 1.25;
    margin-top: 0.18rem;
}
.app-hero {
    background: linear-gradient(180deg, rgba(11, 18, 32, 0.92), rgba(9, 14, 26, 0.9));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    box-shadow: 0 14px 30px rgba(2, 6, 23, 0.18);
    color: #f8fafc;
    margin: 0 0 0.7rem;
    padding: 0.75rem 0.95rem;
}
.app-eyebrow {
    color: var(--color-accent-strong);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0;
    text-transform: uppercase;
}
.app-hero h1 {
    font-size: 1.3rem;
    line-height: 1.05;
    margin: 0.12rem 0 0.08rem;
}
.app-hero p {
    color: #cbd5e1;
    font-size: 0.86rem;
    line-height: 1.32;
    margin: 0;
}
/* Legal footer family owned by COMPONENT_FAMILY_CSS — do not reintroduce here. */

.team-identity-card {
    align-items: center;
    background: var(--color-surface-primary);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-panel);
    box-shadow: var(--shadow-none);
    display: flex;
    gap: var(--space-lg);
    margin: var(--space-xs) 0 var(--space-sm);
    overflow: hidden;
    padding: var(--space-md) var(--space-lg);
    position: relative;
}
/* removed dead midfile card accent (UNIFY/content:none cascade). */

.team-identity-copy {
    min-width: 0;
}
.team-identity-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.36rem;
    margin-top: 0.42rem;
}
.home-command-shell {
    margin: 0.08rem 0 0.72rem;
}
.home-command-kicker {
    color: var(--color-accent);
    font-size: 0.64rem;
    font-weight: 900;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.home-command-hero {
    align-items: center;
    background:
        radial-gradient(circle at top left, color-mix(in srgb, var(--color-accent-strong) 14%, transparent), transparent 34%),
        linear-gradient(180deg, rgba(11, 18, 32, 0.96), rgba(6, 10, 20, 0.98));
    border: 1px solid color-mix(in srgb, var(--color-accent-strong) 14%, transparent);
    border-radius: var(--radius-panel);
    box-shadow:
        0 18px 40px rgba(2, 6, 23, 0.22),
        inset 0 1px 0 rgba(248, 250, 252, 0.04);
    display: grid;
    gap: 0.78rem;
    grid-template-columns: auto minmax(0, 1fr);
    margin-top: 0.45rem;
    padding: 0.82rem 0.88rem;
}
.home-hero-logo {
    align-items: center;
    background: linear-gradient(180deg, rgba(30, 41, 59, 0.96), rgba(15, 23, 42, 0.94));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    color: #f8fafc;
    display: inline-flex;
    font-size: 1.02rem;
    font-weight: 900;
    height: 58px;
    justify-content: center;
    overflow: hidden;
    width: 58px;
}
.home-hero-logo img {
    display: block;
    height: 100%;
    object-fit: cover;
    width: 100%;
}
.home-command-team {
    color: #f8fafc;
    font-size: 1.08rem;
    font-weight: 900;
    line-height: 1.05;
}
.home-command-meta {
    color: #94a3b8;
    font-size: 0.78rem;
    line-height: 1.3;
    margin-top: 0.18rem;
}
.home-command-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.38rem;
    margin-top: 0.45rem;
}
.home-command-badge {
    background: rgba(8, 15, 28, 0.78);
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: var(--radius-pill);
    color: #cbd5e1;
    font-size: 0.68rem;
    font-weight: 780;
    padding: 0.22rem 0.5rem;
}
.home-command-badge-strategy {
    border-color: rgba(20, 184, 166, 0.3);
    color: #ccfbf1;
}
.home-command-badge-archetype {
    border-color: rgba(245, 158, 11, 0.3);
    color: #fde68a;
}
.home-hero-stats {
    display: grid;
    gap: 0.42rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    margin-top: 0.72rem;
}
.home-hero-stat {
    background: linear-gradient(180deg, rgba(8, 15, 28, 0.94), rgba(5, 10, 20, 0.98));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    min-width: 0;
    padding: 0.5rem 0.58rem;
}
.home-hero-stat-label {
    color: #94a3b8;
    font-size: 0.62rem;
    font-weight: 850;
    text-transform: uppercase;
}
.home-hero-stat-value {
    color: #f8fafc;
    font-size: 0.86rem;
    font-weight: 900;
    line-height: 1.14;
    margin-top: 0.12rem;
}
.home-action-center-label {
    color: #94a3b8;
    font-size: 0.68rem;
    font-weight: 820;
    line-height: 1.2;
    margin: 0.1rem 0 0.42rem;
    text-transform: uppercase;
}
.account-confirm-card {
    background: rgba(22, 163, 74, 0.1);
    border: 1px solid rgba(34, 197, 94, 0.28);
    border-radius: var(--radius-panel);
    margin: 0.64rem 0 0.82rem;
    padding: 0.8rem 0.9rem;
}
.account-confirm-title {
    color: #dcfce7;
    font-size: 0.98rem;
    font-weight: 850;
    margin-bottom: 0.22rem;
}
.account-confirm-copy {
    color: rgba(226, 232, 240, 0.86);
    font-size: 0.86rem;
    line-height: 1.42;
}
.account-confirm-status {
    color: rgba(187, 247, 208, 0.95);
    font-size: 0.78rem;
    line-height: 1.35;
    margin-top: 0.45rem;
    min-height: 1.35rem;
}
.launch-section-intro {
    background:
        radial-gradient(circle at top left, color-mix(in srgb, var(--color-accent-strong) 10%, transparent), transparent 34%),
        linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(8, 13, 24, 0.96));
    border: 1px solid rgba(148, 163, 184, 0.13);
    border-radius: var(--radius-panel);
    box-shadow:
        0 14px 28px rgba(2, 6, 23, 0.15),
        inset 0 1px 0 rgba(248, 250, 252, 0.04);
    margin: 0.8rem 0 0.55rem;
    padding: 0.82rem 0.9rem;
}
.launch-account-intro {
    border-color: color-mix(in srgb, var(--color-accent-strong) 18%, transparent);
}
.launch-import-intro {
    border-color: rgba(34, 197, 94, 0.18);
    margin-top: 1rem;
}
.launch-section-eyebrow {
    color: var(--color-accent);
    font-size: 0.66rem;
    font-weight: 900;
    letter-spacing: 0.08em;
    line-height: 1.1;
    text-transform: uppercase;
}
.launch-section-title {
    color: #f8fafc;
    font-size: 1rem;
    font-weight: 880;
    line-height: 1.18;
    margin-top: 0.22rem;
}
.launch-section-copy {
    color: #cbd5e1;
    font-size: 0.82rem;
    line-height: 1.36;
    margin-top: 0.24rem;
}
.launch-league-label {
    color: #94a3b8;
    font-size: 0.68rem;
    font-weight: 820;
    line-height: 1.2;
    margin: 0.08rem 0 0.42rem;
    text-transform: uppercase;
}
.launch-league-card {
    background:
        radial-gradient(circle at top left, color-mix(in srgb, var(--color-accent-strong) 10%, transparent), transparent 34%),
        linear-gradient(180deg, rgba(16, 25, 44, 0.94), rgba(8, 13, 24, 0.96));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    box-shadow:
        0 16px 32px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(248, 250, 252, 0.03);
    padding: 0.84rem 0.88rem;
    position: relative;
}
.launch-league-card::before {
    background: linear-gradient(180deg, color-mix(in srgb, var(--color-accent-strong) 96%, transparent), rgba(129, 140, 248, 0.84));
    border-radius: 0;
    content: "";
    left: 0;
    position: absolute;
    top: 14px;
    bottom: 14px;
    width: 4px;
}
.launch-league-card.selected {
    border-color: color-mix(in srgb, var(--color-accent-strong) 24%, transparent);
}
.launch-league-top {
    align-items: center;
    display: flex;
    gap: 0.78rem;
}
.launch-league-copy {
    min-width: 0;
}
.launch-league-name {
    color: #f8fafc;
    font-size: 0.98rem;
    font-weight: 880;
    line-height: 1.18;
}
.launch-league-team {
    color: #cbd5e1;
    font-size: 0.8rem;
    line-height: 1.26;
    margin-top: 0.14rem;
}
.launch-league-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.36rem;
    margin-top: 0.48rem;
}
.launch-league-chip {
    background: rgba(8, 15, 28, 0.78);
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: var(--radius-pill);
    color: #cbd5e1;
    font-size: 0.68rem;
    font-weight: 780;
    padding: 0.22rem 0.48rem;
}
.launch-league-chip-last {
    border-color: color-mix(in srgb, var(--color-accent-strong) 32%, transparent);
    color: var(--color-accent);
}
.home-command-grid {
    display: grid;
    gap: 0.6rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    margin: 0.68rem 0 0.85rem;
}
.home-command-card {
    background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.05), transparent 34%),
        linear-gradient(180deg, rgba(16, 25, 44, 0.94), rgba(8, 13, 24, 0.96));
    border: 1px solid rgba(148, 163, 184, 0.1);
    border-radius: var(--radius-panel);
    box-shadow:
        0 18px 34px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(248, 250, 252, 0.04);
    min-width: 0;
    overflow: hidden;
    padding: 0.76rem 0.8rem;
    position: relative;
}
.home-command-route-card {
    cursor: pointer;
}
.home-command-route-card:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--color-accent-strong) 72%, transparent);
    outline-offset: 2px;
}
.home-command-card-wide {
    grid-column: 1 / -1;
}
.home-command-card-label {
    color: #94a3b8;
    font-size: 0.66rem;
    font-weight: 860;
    text-transform: uppercase;
}
.home-command-card-cta {
    color: var(--color-accent);
    font-size: 0.68rem;
    font-weight: 800;
    margin-left: auto;
    white-space: nowrap;
}
.home-command-card-value {
    color: #f8fafc;
    font-size: 0.94rem;
    font-weight: 900;
    line-height: 1.14;
    margin-top: 0.18rem;
}
.home-command-card-note {
    color: #cbd5e1;
    font-size: 0.74rem;
    line-height: 1.28;
    margin-top: 0.2rem;
}
.home-command-card-trade {
    border-color: rgba(20, 184, 166, 0.26);
    box-shadow:
        0 14px 30px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(45, 212, 191, 0.06);
}
.home-command-card-waiver {
    border-color: color-mix(in srgb, var(--color-accent-strong) 26%, transparent);
    box-shadow:
        0 14px 30px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 color-mix(in srgb, var(--color-accent-strong) 6%, transparent);
}
.home-command-card-risk {
    border-color: rgba(245, 158, 11, 0.28);
    box-shadow:
        0 14px 30px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(245, 158, 11, 0.06);
}
.home-command-card-need {
    border-color: rgba(239, 68, 68, 0.24);
    box-shadow:
        0 14px 30px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(239, 68, 68, 0.05);
}
.home-command-card-draft {
    border-color: rgba(99, 102, 241, 0.24);
    box-shadow:
        0 14px 30px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(129, 140, 248, 0.05);
}
.player-detail-shell {
    margin: 0.1rem 0 1rem;
}
.player-detail-hero {
    align-items: center;
    background:
        radial-gradient(circle at top left, color-mix(in srgb, var(--color-accent-strong) 12%, transparent), transparent 34%),
        radial-gradient(circle at top right, rgba(168, 85, 247, 0.1), transparent 28%),
        linear-gradient(180deg, rgba(11, 18, 32, 0.98), rgba(6, 10, 20, 0.99));
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: var(--radius-panel);
    box-shadow:
        0 18px 42px rgba(2, 6, 23, 0.24),
        inset 0 1px 0 rgba(248, 250, 252, 0.04);
    display: grid;
    gap: 0.9rem;
    grid-template-columns: auto minmax(0, 1fr);
    margin-bottom: 0.8rem;
    padding: 0.95rem 1rem;
}
.player-detail-avatar {
    --avatar-size: 112px;
}
.player-detail-name {
    color: #f8fafc;
    font-size: 1.24rem;
    font-weight: 900;
    line-height: 1.04;
}
.player-detail-meta {
    color: #cbd5e1;
    font-size: 0.84rem;
    line-height: 1.34;
    margin-top: 0.18rem;
}
.player-detail-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.36rem;
    margin-top: 0.48rem;
}
.player-detail-score-row {
    display: grid;
    gap: 0.55rem;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    margin-top: 0.7rem;
}
.player-detail-score-pill {
    background: linear-gradient(180deg, rgba(8, 15, 28, 0.96), rgba(5, 10, 20, 0.98));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    min-width: 0;
    padding: 0.58rem 0.62rem;
}
.player-detail-score-label {
    color: #94a3b8;
    font-size: 0.66rem;
    font-weight: 820;
    text-transform: uppercase;
}
.player-detail-score-value {
    color: #f8fafc;
    font-size: 0.96rem;
    font-weight: 900;
    line-height: 1.08;
    margin-top: 0.18rem;
}
.player-detail-score-note {
    color: #cbd5e1;
    font-size: 0.74rem;
    line-height: 1.24;
    margin-top: 0.18rem;
}
.player-detail-empty {
    color: #94a3b8;
    font-size: 0.82rem;
    line-height: 1.32;
}
div[data-testid="stDialog"] div[role="dialog"] {
    max-width: min(760px, calc(100vw - 1rem)) !important;
    width: min(760px, calc(100vw - 1rem)) !important;
}
.player-quick-view-shell {
    margin: 0.1rem 0 0.3rem;
}
.player-quick-view-hero {
    align-items: center;
    background:
        radial-gradient(circle at top left, color-mix(in srgb, var(--color-accent-strong) 12%, transparent), transparent 34%),
        radial-gradient(circle at top right, rgba(168, 85, 247, 0.08), transparent 28%),
        linear-gradient(180deg, rgba(11, 18, 32, 0.98), rgba(6, 10, 20, 0.99));
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: var(--radius-panel);
    box-shadow:
        0 18px 40px rgba(2, 6, 23, 0.22),
        inset 0 1px 0 rgba(248, 250, 252, 0.04);
    display: grid;
    gap: 0.9rem;
    grid-template-columns: 92px minmax(0, 1fr);
    min-width: 0;
    overflow: hidden;
    padding: 0.9rem 0.95rem;
}
.player-quick-view-avatar {
    --avatar-size: 92px;
}
.player-quick-view-copy {
    min-width: 0;
}
.player-quick-view-source {
    color: var(--color-accent);
    font-size: 0.68rem;
    font-weight: 860;
    line-height: 1.2;
    text-transform: uppercase;
}
.player-quick-view-name {
    color: #f8fafc;
    font-size: 1.16rem;
    font-weight: 920;
    line-height: 1.04;
    margin-top: 0.16rem;
}
.player-quick-view-meta {
    color: #cbd5e1;
    font-size: 0.82rem;
    line-height: 1.32;
    margin-top: 0.18rem;
}
.player-quick-view-actions-label {
    color: #94a3b8;
    font-size: 0.7rem;
    font-weight: 820;
    line-height: 1.2;
    margin: 0.75rem 0 0.36rem;
    text-transform: uppercase;
}
div[data-testid="stDialog"] [data-testid="stVerticalBlock"] .player-quick-view-shell + div[data-testid="stElementContainer"] {
    min-width: 0;
}
.league-team-page {
    margin: 0.25rem 0 1rem;
}
.league-team-header {
    align-items: center;
    display: flex;
    gap: 1rem;
}
.league-team-copy {
    min-width: 0;
}
.team-owner-handle {
    color: #e2e8f0;
    font-size: 1rem;
    font-weight: 700;
    line-height: 1.2;
    margin-top: 0.2rem;
}
.team-owner-meta {
    color: #94a3b8;
    font-size: 0.86rem;
    margin-top: 0.25rem;
}
.team-card-tappable {
    cursor: pointer;
}
.team-card-tappable:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--color-accent-strong) 78%, transparent);
    outline-offset: 2px;
}
.team-card-tappable:hover {
    border-color: color-mix(in srgb, var(--color-accent-strong) 34%, transparent);
    transform: translateY(-1px);
}
.team-section-card {
    background: var(--color-surface-secondary);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-control);
    margin: 0.75rem 0;
    padding: 0.85rem 0.9rem;
}
.team-section-title {
    color: #f8fafc;
    font-size: 1rem;
    font-weight: 800;
    margin-bottom: 0.55rem;
}
.section-header {
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.88), rgba(11, 16, 32, 0.78));
    border: 1px solid rgba(148, 163, 184, 0.1);
    border-left: 3px solid var(--color-accent-strong);
    border-radius: var(--radius-control);
    box-shadow: 0 10px 22px rgba(2, 6, 23, 0.14);
    margin: 0.8rem 0 0.55rem;
    padding: 0.7rem 0.8rem;
}
.section-header-compact {
    margin-top: 0.55rem;
    padding: 0.62rem 0.75rem;
}
.section-kicker {
    color: var(--color-accent);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0;
    text-transform: uppercase;
}
.section-title {
    color: #f8fafc;
    font-size: 1.02rem;
    font-weight: 880;
    line-height: 1.15;
    margin-top: 0.18rem;
}
.section-note {
    color: #94a3b8;
    font-size: 0.8rem;
    line-height: 1.32;
    margin-top: 0.24rem;
}
.section-header,
.launch-section-intro,
.team-section-card {
    min-width: 0;
    overflow-wrap: anywhere;
}
.section-title,
.launch-section-title,
.team-section-title {
    letter-spacing: 0;
    overflow-wrap: anywhere;
}
.section-note,
.launch-section-copy,
.team-section-title {
    text-wrap: pretty;
}
.summary-tile-grid,
.analysis-grid,
.decision-panel-grid {
    display: grid;
    gap: 0.75rem;
    margin: 0.65rem 0 1rem;
}
.summary-tile-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
}
.summary-tile-grid-compact {
    gap: 0.6rem;
}
.analysis-grid,
.decision-panel-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
}
.summary-tile,
.analysis-card,
.decision-panel {
    background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.04), transparent 36%),
        linear-gradient(180deg, rgba(16, 25, 44, 0.94), rgba(8, 13, 24, 0.9));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    box-shadow:
        0 16px 34px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(248, 250, 252, 0.04);
    min-width: 0;
    overflow: hidden;
    padding: 0.78rem 0.84rem;
    position: relative;
    transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
}
.summary-tile-compact {
    padding: 0.68rem 0.74rem;
}
.summary-tile-tappable {
    cursor: pointer;
}
.summary-tile-tappable:hover,
.summary-tile-tappable:focus-visible {
    border-color: rgba(226, 232, 240, 0.26);
    box-shadow:
        0 18px 36px rgba(2, 6, 23, 0.22),
        inset 0 1px 0 rgba(248, 250, 252, 0.07);
    outline: none;
}
.summary-tile-affordance {
    color: rgba(226, 232, 240, 0.78);
    font-size: 0.66rem;
    font-weight: 860;
    letter-spacing: 0.03em;
    margin-top: 0.46rem;
    text-transform: uppercase;
}
/* card ::after strips owned/killed by EXECUTIVE_DESIGN_UNIFY_CSS */

/* removed dead midfile card accent (UNIFY/content:none cascade). */

/* removed dead midfile card accent (UNIFY/content:none cascade). */

/* removed dead midfile card accent (UNIFY/content:none cascade). */

.summary-tile-label,
.analysis-card-label,
.decision-panel-label {
    color: #94a3b8;
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
}
.summary-tile-value,
.analysis-card-title,
.decision-panel-title {
    color: #f8fafc;
    font-size: 1rem;
    font-weight: 860;
    line-height: 1.2;
    margin-top: 0.2rem;
}
.summary-tile-note {
    color: #cbd5e1;
    font-size: 0.85rem;
    line-height: 1.38;
    margin-top: 0.3rem;
}
.summary-detail-panel {
    background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.05), transparent 38%),
        linear-gradient(180deg, rgba(12, 17, 29, 0.96), rgba(6, 9, 16, 0.96));
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: var(--radius-pill);
    overflow: hidden;
}
.summary-detail-header {
    border-bottom: 1px solid rgba(148, 163, 184, 0.14);
    padding: 0.78rem 0.86rem;
}
.summary-detail-kicker {
    align-items: center;
    color: #94a3b8;
    display: flex;
    font-size: 0.68rem;
    font-weight: 860;
    gap: 0.36rem;
    text-transform: uppercase;
}
.summary-detail-title {
    color: #f8fafc;
    font-size: 1.04rem;
    font-weight: 920;
    line-height: 1.12;
    margin-top: 0.24rem;
}
.summary-detail-value {
    color: #e2e8f0;
    font-size: 0.9rem;
    font-weight: 780;
    margin-top: 0.2rem;
}
.summary-detail-rows {
    display: grid;
}
.summary-detail-row {
    border-bottom: 1px solid rgba(148, 163, 184, 0.11);
    display: grid;
    gap: 0.22rem;
    padding: 0.7rem 0.86rem;
}
.summary-detail-row:last-child {
    border-bottom: 0;
}
.summary-detail-row-label {
    color: #94a3b8;
    font-size: 0.68rem;
    font-weight: 860;
    text-transform: uppercase;
}
.summary-detail-row-value {
    color: #e2e8f0;
    font-size: 0.86rem;
    line-height: 1.36;
}
.summary-detail-list {
    border-top: 1px solid rgba(148, 163, 184, 0.14);
    display: grid;
}
.summary-detail-list-heading {
    color: #f8fafc;
    font-size: 0.72rem;
    font-weight: 900;
    letter-spacing: 0.03em;
    padding: 0.7rem 0.86rem 0.34rem;
    text-transform: uppercase;
}
.summary-detail-list-row {
    align-items: center;
    border-top: 1px solid rgba(148, 163, 184, 0.09);
    display: grid;
    gap: 0.62rem;
    grid-template-columns: minmax(0, 1fr) auto;
    padding: 0.62rem 0.86rem;
}
.summary-detail-list-row-current {
    background: linear-gradient(90deg, color-mix(in srgb, var(--color-accent-strong) 12%, transparent), rgba(15, 23, 42, 0.2));
    box-shadow: inset 3px 0 0 color-mix(in srgb, var(--color-accent-strong) 92%, transparent);
}
.summary-detail-list-main {
    min-width: 0;
}
.summary-detail-list-title {
    color: #f8fafc;
    display: block;
    font-size: 0.86rem;
    font-weight: 850;
    line-height: 1.18;
}
.summary-detail-list-note {
    color: #94a3b8;
    display: block;
    font-size: 0.72rem;
    line-height: 1.25;
    margin-top: 0.14rem;
}
.summary-detail-list-value {
    color: #e2e8f0;
    font-size: 0.82rem;
    font-weight: 900;
    white-space: nowrap;
}
.summary-tile-opportunity {
    border-color: rgba(20, 184, 166, 0.34);
}
.summary-tile-power {
    border-color: color-mix(in srgb, var(--color-accent-strong) 28%, transparent);
}
.summary-tile-franchise {
    border-color: rgba(168, 85, 247, 0.24);
}
.summary-tile-strategy {
    border-color: rgba(99, 102, 241, 0.24);
}
.summary-tile-weakness,
.summary-tile-risk {
    border-color: rgba(245, 158, 11, 0.26);
}
.analysis-card-strength {
    border-color: rgba(20, 184, 166, 0.34);
}
.decision-panel-strength {
    border-color: rgba(20, 184, 166, 0.34);
}
.analysis-card-weakness {
    border-color: rgba(239, 68, 68, 0.34);
}
.decision-panel-reference {
    border-color: rgba(148, 163, 184, 0.28);
}
.analysis-card-risk {
    border-color: rgba(245, 158, 11, 0.34);
}
/* removed dead midfile card accent (UNIFY/content:none cascade). */

.summary-tile-top,
.analysis-card-top,
.decision-panel-top,
.home-command-card-top {
    align-items: center;
    display: flex;
    gap: 0.42rem;
}
.summary-tile-dot,
.analysis-card-dot,
.decision-panel-dot,
.home-command-card-dot {
    border-radius: var(--radius-pill);
    display: inline-flex;
    flex: 0 0 8px;
    height: 8px;
    width: 8px;
}
.summary-tile-dot {
    background: linear-gradient(180deg, color-mix(in srgb, var(--color-accent-strong) 98%, transparent), rgba(45, 212, 191, 0.92));
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--color-accent-strong) 8%, transparent);
}
.analysis-card-dot {
    background: linear-gradient(180deg, rgba(245, 158, 11, 0.96), rgba(239, 68, 68, 0.88));
    box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.08);
}
.decision-panel-dot {
    background: linear-gradient(180deg, rgba(99, 102, 241, 0.96), color-mix(in srgb, var(--color-accent-strong) 88%, transparent));
    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.08);
}
.home-command-card-dot {
    background: linear-gradient(180deg, rgba(168, 85, 247, 0.98), color-mix(in srgb, var(--color-accent-strong) 92%, transparent));
    box-shadow: 0 0 0 4px rgba(168, 85, 247, 0.08);
}
.analysis-list {
    color: #cbd5e1;
    font-size: 0.88rem;
    line-height: 1.5;
    margin: 0.45rem 0 0;
    padding-left: 1rem;
}
.analysis-list li + li {
    margin-top: 0.28rem;
}
.decision-panel-body {
    display: grid;
    gap: 0.54rem;
    margin-top: 0.48rem;
}
.decision-panel-empty {
    color: #94a3b8;
    font-size: 0.8rem;
    line-height: 1.3;
    padding: 0.1rem 0 0.2rem;
}
.decision-panel-empty,
.player-detail-empty,
.summary-tile,
.analysis-card,
.decision-panel,
.draft-review-pick-card,
.launch-section-intro,
.launch-league-card,
.dg-alert-banner,
.dg-intel-card,
.news-card,
[data-testid="stMetric"] {
    min-width: 0;
}
.launch-league-chip,
.dg-glyph-chip,
.dg-tier-chip,
.player-support-chip,
.player-status-pill,
.news-badge,
.draft-review-chip,
.home-status-pill,
.account-status-chip {
    line-height: 1.12;
    max-width: 100%;
    overflow-wrap: anywhere;
    white-space: normal;
}
.draft-review-chip.mine,
.news-badge-priority {
    background: rgba(20, 184, 166, 0.13);
    border-color: rgba(20, 184, 166, 0.32);
    color: #99f6e4;
}
.draft-review-chip.unmatched,
.news-badge-warning,
.dg-alert-warning .dg-alert-kicker {
    color: #fde68a;
}
.decision-panel-grid-alert .player-status-pill {
    flex: 0 0 auto;
    max-width: 100%;
}
.team-score-grid {
    display: grid;
    gap: 0.65rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
}
.team-score-item {
    background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.04), transparent 40%),
        linear-gradient(180deg, rgba(14, 22, 40, 0.96), rgba(8, 13, 24, 0.92));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    box-shadow:
        0 12px 26px rgba(2, 6, 23, 0.16),
        inset 0 1px 0 rgba(248, 250, 252, 0.03);
    min-width: 0;
    padding: 0.72rem 0.78rem;
}
.team-score-name {
    color: #94a3b8;
    font-size: 0.76rem;
    font-weight: 800;
    text-transform: uppercase;
}
.team-score-value {
    color: #f8fafc;
    font-size: 1.08rem;
    font-weight: 850;
    margin-top: 0.24rem;
}
.dg-standings-division-label {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    margin: var(--space-sm) 0 var(--space-2xs);
    text-transform: uppercase;
}
.dg-standings-playoff-line {
    align-items: center;
    color: var(--color-text-muted);
    display: flex;
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-metadata);
    gap: var(--space-xs);
    letter-spacing: var(--letter-spacing-badge);
    margin: var(--space-2xs) 0;
    text-transform: uppercase;
}
.dg-standings-playoff-line::before,
.dg-standings-playoff-line::after {
    background: var(--color-border);
    content: "";
    flex: 1 1 auto;
    height: 1px;
}
.team-logo-wrap {
    align-items: center;
    background: linear-gradient(160deg, var(--color-surface-raised), var(--color-surface-secondary));
    border: 1px solid rgba(148, 163, 184, 0.35);
    border-radius: 50%;
    box-shadow:
        0 14px 30px rgba(2, 6, 23, 0.5),
        0 0 0 5px color-mix(in srgb, var(--color-accent-strong) 6%, transparent),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
    color: #f8fafc;
    display: flex;
    flex: 0 0 76px;
    font-size: 1.05rem;
    font-weight: 900;
    height: 76px;
    justify-content: center;
    overflow: hidden;
    width: 76px;
}
.team-logo-wrap img {
    height: 100%;
    object-fit: cover;
    width: 100%;
}
.team-kicker {
    color: var(--color-accent-strong);
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0;
    text-transform: uppercase;
}
.team-name {
    color: #f8fafc;
    font-size: 1.55rem;
    font-weight: 900;
    line-height: 1.1;
    margin-top: 0.15rem;
}
.team-subtitle {
    color: #94a3b8;
    font-size: 0.76rem;
    line-height: 1.32;
    margin-top: 0.16rem;
}
.advice-grid,
.prospect-grid {
    display: grid;
    gap: 0.75rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin: 0.65rem 0 1rem;
}
.advice-card,
.prospect-card {
    background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.04), transparent 38%),
        linear-gradient(180deg, rgba(16, 25, 44, 0.95), rgba(8, 13, 24, 0.92));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    box-shadow: 0 16px 34px rgba(2, 6, 23, 0.18);
    min-width: 0;
    overflow: hidden;
    padding: 0.85rem;
    position: relative;
}
.advice-card-primary {
    border-color: rgba(20, 184, 166, 0.42);
    box-shadow: inset 0 1px 0 rgba(20, 184, 166, 0.12);
}
.advice-card-priority {
    background: linear-gradient(180deg, rgba(20, 184, 166, 0.12), rgba(15, 23, 42, 0.98));
    border-color: rgba(20, 184, 166, 0.42);
}
.advice-card-need {
    border-color: rgba(245, 158, 11, 0.42);
}
.advice-card-health {
    border-color: rgba(239, 68, 68, 0.38);
}
.advice-card-opportunity {
    border-color: color-mix(in srgb, var(--color-accent-strong) 34%, transparent);
}
.advice-label,
.prospect-label {
    color: var(--color-accent-strong);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0;
    text-transform: uppercase;
}
.advice-title,
.prospect-name {
    color: #f8fafc;
    font-size: 1rem;
    font-weight: 850;
    line-height: 1.2;
    margin-top: 0.25rem;
}
.advice-body,
.prospect-note {
    color: #cbd5e1;
    font-size: 0.88rem;
    line-height: 1.38;
    margin-top: 0.38rem;
}
.prospect-meta {
    color: #94a3b8;
    font-size: 0.8rem;
    margin-top: 0.3rem;
}
.prospect-card-head {
    align-items: flex-start;
    display: flex;
    gap: 0.6rem;
    justify-content: space-between;
}
.prospect-card-title-group {
    min-width: 0;
}
.prospect-card-head .prospect-meta {
    flex: 0 0 auto;
    margin-top: 0;
    text-align: right;
}
div[class*="st-key-"][class*="_feedback_control"] {
    align-items: center;
    display: flex;
    justify-content: flex-end;
    margin: 0.18rem 0 0.42rem;
}
div[class*="st-key-"][class*="_feedback_control"] .feedback-control-marker {
    display: none;
}
div[class*="st-key-"][class*="_feedback_control"] [data-testid="stPopover"] > button {
    border-radius: var(--radius-pill);
    font-size: 0.68rem;
    min-height: 30px;
    padding: 0.22rem 0.56rem;
    width: auto;
}
div[class*="st-key-"][class*="_global_feedback_control"] {
    bottom: calc(0.85rem + env(safe-area-inset-bottom));
    position: fixed;
    right: calc(0.85rem + env(safe-area-inset-right));
    z-index: 999998;
}
div[class*="st-key-"][class*="_global_feedback_control"] .global-feedback-marker {
    display: none;
}
div[class*="st-key-"][class*="_global_feedback_control"] [data-testid="stPopover"] > button {
    background: rgba(12, 14, 18, 0.9);
    border: 1px solid rgba(226, 232, 240, 0.28);
    border-radius: var(--radius-pill);
    box-shadow: 0 14px 36px rgba(0, 0, 0, 0.38);
    color: #e5e7eb;
    font-size: 0.76rem;
    font-weight: 850;
    min-height: 38px;
    padding: 0.42rem 0.72rem;
    text-align: left;
}
.prospect-watch-groups {
    display: grid;
    gap: 0.7rem;
    margin: 0.55rem 0 0.9rem;
}
.prospect-position-group {
    min-width: 0;
}
.prospect-position-title {
    color: #cbd5e1;
    font-size: 0.72rem;
    font-weight: 850;
    letter-spacing: 0;
    text-transform: uppercase;
}
.prospect-position-group .prospect-grid {
    margin: 0.34rem 0 0;
}
.free-agent-summary-grid {
    display: grid;
    gap: 0.75rem;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    margin: 0.7rem 0 1rem;
}
.free-agent-summary-card {
    background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.04), transparent 38%),
        linear-gradient(180deg, rgba(16, 25, 44, 0.94), rgba(8, 13, 24, 0.9));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    box-shadow: 0 14px 30px rgba(2, 6, 23, 0.18);
    min-width: 0;
    overflow: hidden;
    padding: 0.82rem 0.86rem;
    position: relative;
}
.free-agent-summary-card.player-card-tappable {
    cursor: pointer;
}
.free-agent-summary-card.player-card-tappable:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--color-accent-strong) 72%, transparent);
    outline-offset: 2px;
}
.free-agent-summary-label {
    color: var(--color-accent-strong);
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
}
.free-agent-summary-name {
    color: #f8fafc;
    font-size: 0.98rem;
    font-weight: 850;
    line-height: 1.2;
    margin-top: 0.24rem;
}
.free-agent-summary-meta {
    color: #94a3b8;
    font-size: 0.82rem;
    line-height: 1.35;
    margin-top: 0.24rem;
}
.free-agent-list {
    display: grid;
    gap: 0.72rem;
    margin: 0.65rem 0 1rem;
}
.free-agent-card {
    --player-accent: rgba(148, 163, 184, 0.9);
    --player-accent-soft: rgba(148, 163, 184, 0.14);
    background:
        radial-gradient(circle at top left, var(--player-accent-soft), transparent 40%),
        linear-gradient(180deg, rgba(16, 25, 44, 0.94), rgba(8, 13, 24, 0.9));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    box-shadow: 0 14px 28px rgba(2, 6, 23, 0.16);
    min-width: 0;
    overflow: hidden;
    padding: 0.78rem 0.84rem 0.78rem 0.98rem;
    position: relative;
}
.free-agent-card.player-card-tappable {
    cursor: pointer;
}
.free-agent-card.player-card-tappable:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--color-accent-strong) 72%, transparent);
    outline-offset: 2px;
}
.free-agent-card::before {
    background: var(--player-accent);
    border-radius: 0;
    content: "";
    left: 0;
    position: absolute;
    top: 12px;
    bottom: 12px;
    width: 4px;
}
.free-agent-card::after {
    display: none;
}
.free-agent-card-tone-premium {
    --player-accent: linear-gradient(180deg, rgba(250, 204, 21, 0.96), rgba(217, 119, 6, 0.86));
    --player-accent-soft: rgba(250, 204, 21, 0.12);
}
.free-agent-card-tone-core {
    --player-accent: linear-gradient(180deg, color-mix(in srgb, var(--color-accent) 96%, transparent), color-mix(in srgb, var(--color-accent-strong) 84%, transparent));
    --player-accent-soft: color-mix(in srgb, var(--color-accent-strong) 12%, transparent);
}
.free-agent-card-tone-rise {
    --player-accent: linear-gradient(180deg, rgba(74, 222, 128, 0.96), rgba(16, 185, 129, 0.84));
    --player-accent-soft: rgba(34, 197, 94, 0.12);
}
.free-agent-card-tone-hold,
.free-agent-card-tone-neutral {
    --player-accent: linear-gradient(180deg, rgba(148, 163, 184, 0.9), rgba(71, 85, 105, 0.82));
    --player-accent-soft: rgba(100, 116, 139, 0.12);
}
.free-agent-card-tone-move {
    --player-accent: linear-gradient(180deg, rgba(251, 146, 60, 0.96), rgba(234, 88, 12, 0.84));
    --player-accent-soft: rgba(249, 115, 22, 0.12);
}
.free-agent-card-tone-drop,
.free-agent-card-tone-risk {
    --player-accent: linear-gradient(180deg, rgba(248, 113, 113, 0.96), rgba(220, 38, 38, 0.84));
    --player-accent-soft: rgba(239, 68, 68, 0.12);
}
.free-agent-main {
    align-items: flex-start;
    display: flex;
    gap: 0.85rem;
    min-width: 0;
}
.free-agent-avatar {
    --avatar-size: 76px;
    align-self: flex-start;
}
.free-agent-copy {
    min-width: 0;
    width: 100%;
}
.free-agent-top {
    align-items: flex-start;
    display: flex;
    gap: 0.7rem;
    justify-content: space-between;
}
.free-agent-name {
    color: #f8fafc;
    font-size: 1rem;
    font-weight: 850;
    line-height: 1.18;
    overflow-wrap: anywhere;
}
.free-agent-score-pill {
    background: color-mix(in srgb, var(--color-accent-strong) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-accent-strong) 28%, transparent);
    border-radius: var(--radius-pill);
    color: var(--color-accent);
    flex: 0 0 auto;
    font-size: 0.77rem;
    font-weight: 800;
    line-height: 1;
    padding: 0.38rem 0.58rem;
    white-space: nowrap;
}
.free-agent-card-tone-premium .free-agent-score-pill {
    background: rgba(250, 204, 21, 0.12);
    border-color: rgba(250, 204, 21, 0.26);
    color: #fde68a;
}
.free-agent-card-tone-core .free-agent-score-pill {
    background: color-mix(in srgb, var(--color-accent-strong) 12%, transparent);
    border-color: color-mix(in srgb, var(--color-accent) 26%, transparent);
    color: #dbeafe;
}
.free-agent-card-tone-rise .free-agent-score-pill {
    background: rgba(34, 197, 94, 0.12);
    border-color: rgba(74, 222, 128, 0.26);
    color: #bbf7d0;
}
.free-agent-card-tone-move .free-agent-score-pill {
    background: rgba(249, 115, 22, 0.12);
    border-color: rgba(251, 146, 60, 0.26);
    color: #fdba74;
}
.free-agent-card-tone-hold .free-agent-score-pill,
.free-agent-card-tone-neutral .free-agent-score-pill {
    background: rgba(51, 65, 85, 0.7);
    border-color: rgba(148, 163, 184, 0.2);
    color: #cbd5e1;
}
.free-agent-card-tone-drop .free-agent-score-pill,
.free-agent-card-tone-risk .free-agent-score-pill {
    background: rgba(127, 29, 29, 0.16);
    border-color: rgba(248, 113, 113, 0.28);
    color: #fecaca;
}
.free-agent-meta {
    color: #94a3b8;
    font-size: 0.84rem;
    line-height: 1.32;
    margin-top: 0.22rem;
}
.free-agent-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.36rem;
    margin-top: 0.45rem;
}
.free-agent-tag {
    background: rgba(148, 163, 184, 0.12);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: var(--radius-pill);
    color: #cbd5e1;
    font-size: 0.68rem;
    font-weight: 840;
    line-height: 1;
    padding: 0.26rem 0.48rem;
    box-shadow: inset 0 1px 0 rgba(248, 250, 252, 0.04);
    white-space: nowrap;
}
.free-agent-tag-emphasis {
    background: rgba(20, 184, 166, 0.14);
    border-color: rgba(20, 184, 166, 0.34);
    color: #99f6e4;
}
.free-agent-tag-muted {
    background: rgba(239, 68, 68, 0.12);
    border-color: rgba(239, 68, 68, 0.28);
    color: #fca5a5;
}
.free-agent-reason {
    color: #cbd5e1;
    font-size: 0.88rem;
    line-height: 1.42;
    margin-top: 0.5rem;
}
.scan-section-shell {
    margin: 0.75rem 0 1rem;
}
.scan-section-title {
    color: #f8fafc;
    font-size: 0.96rem;
    font-weight: 850;
    line-height: 1.2;
}
.scan-section-note {
    color: #94a3b8;
    font-size: 0.78rem;
    line-height: 1.35;
    margin-top: 0.18rem;
}
.scan-card-list,
.draft-team-grid {
    display: grid;
    gap: 0.72rem;
    grid-template-columns: 1fr;
    margin: 0.7rem 0 0.85rem;
}
.scan-card {
    --player-accent: linear-gradient(180deg, rgba(148, 163, 184, 0.88), rgba(71, 85, 105, 0.78));
    --player-accent-soft: rgba(148, 163, 184, 0.12);
    background:
        radial-gradient(circle at top left, var(--player-accent-soft), transparent 42%),
        linear-gradient(180deg, rgba(16, 25, 44, 0.95), rgba(8, 13, 24, 0.92));
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: var(--radius-panel);
    box-shadow:
        0 14px 30px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(248, 250, 252, 0.04);
    overflow: hidden;
    padding: 0.82rem 0.88rem 0.82rem 1rem;
    position: relative;
}
.scan-card.scan-card-tappable {
    cursor: pointer;
}
.scan-card.scan-card-tappable:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--color-accent-strong) 72%, transparent);
    outline-offset: 2px;
}
.compact-player-row {
    align-items: flex-start;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(8, 13, 25, 0.96));
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-left: 3px solid rgba(148, 163, 184, 0.7);
    border-radius: var(--radius-control);
    box-shadow: 0 12px 26px rgba(2, 6, 23, 0.28), inset 0 1px 0 rgba(248, 250, 252, 0.04);
    display: grid;
    gap: 0.58rem;
    grid-template-columns: 52px minmax(0, 1fr);
    height: auto;
    min-height: 0;
    overflow: hidden;
    padding: 0.56rem 0.62rem 0.58rem;
    position: relative;
}
.compact-player-row.scan-card-tappable {
    cursor: pointer;
}
.compact-player-row.scan-card-tappable:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--color-accent-strong) 72%, transparent);
    outline-offset: 2px;
}
.compact-player-row-tone-premium,
.compact-player-row-tone-elite,
.compact-player-row-tone-star,
.compact-player-row-tone-core,
.compact-player-row-tone-starter,
.compact-player-row-tone-rise {
    border-left-color: rgba(45, 212, 191, 0.8);
}
.compact-player-row-tone-move,
.compact-player-row-tone-contributor {
    border-left-color: rgba(251, 146, 60, 0.82);
}
.compact-player-row-tone-drop,
.compact-player-row-tone-risk {
    border-left-color: rgba(248, 113, 113, 0.86);
}
.compact-player-avatar {
    --avatar-size: 52px;
    align-items: center;
    align-self: flex-start;
    background: linear-gradient(160deg, var(--color-surface-raised), var(--color-surface-secondary));
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: var(--radius-control);
    display: flex;
    flex: 0 0 var(--avatar-size);
    height: var(--avatar-size);
    justify-content: center;
    overflow: hidden;
    position: relative;
    width: var(--avatar-size);
}
.compact-player-avatar::before {
    background: linear-gradient(180deg, rgba(8, 15, 28, 0.08), rgba(8, 15, 28, 0.22));
    border-radius: inherit;
    content: "";
    inset: 0;
    position: absolute;
    z-index: 0;
}
.compact-player-avatar span:not(.dg-player-headshot-fallback) {
    position: relative;
    text-shadow: 0 2px 8px rgba(2, 6, 23, 0.9);
    z-index: 2;
}
.compact-player-avatar img {
    height: 100%;
    inset: 0;
    max-width: 100%;
    object-fit: cover;
    object-position: center top;
    position: absolute;
    width: 100%;
    z-index: 1;
}
.compact-player-body {
    min-width: 0;
}
.compact-player-badges,
.compact-player-score-meta {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.32rem;
}
.compact-player-tags {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.24rem;
    min-width: 0;
}
.compact-player-name {
    color: #f8fafc;
    font-size: 0.96rem;
    font-weight: 800;
    letter-spacing: 0;
    line-height: 1.14;
    margin-top: 0.2rem;
}
.compact-player-score-meta {
    margin-top: 0.2rem;
}
.compact-player-value {
    background: rgba(15, 23, 42, 0.72);
    border: 1px solid color-mix(in srgb, var(--color-accent) 18%, transparent);
    border-radius: var(--radius-pill);
    color: var(--color-accent);
    font-size: 0.72rem;
    font-weight: 800;
    line-height: 1;
    padding: 0.26rem 0.46rem;
}
.player-value-injury-adjusted {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
}
.injury-adjustment-ring {
    width: 0.58rem;
    height: 0.58rem;
    border-radius: var(--radius-pill);
    display: inline-block;
    flex: 0 0 auto;
    border: 2px solid rgba(245, 158, 11, 0.82);
    box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.16);
}
.player-value-injury-minor .injury-adjustment-ring {
    width: 0.46rem;
    height: 0.46rem;
    border-color: rgba(251, 191, 36, 0.72);
    box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.12);
}
.player-value-injury-moderate .injury-adjustment-ring {
    background: rgba(248, 113, 113, 0.18);
    border-color: rgba(248, 113, 113, 0.95);
    box-shadow:
        0 0 0 2px rgba(248, 113, 113, 0.16),
        0 0 10px rgba(248, 113, 113, 0.18);
}
.player-value-injury-major .injury-adjustment-ring {
    background: rgba(239, 68, 68, 0.32);
    border-color: rgba(254, 202, 202, 0.98);
    box-shadow:
        0 0 0 2px rgba(239, 68, 68, 0.26),
        0 0 14px rgba(239, 68, 68, 0.28);
}
.compact-player-meta {
    color: #94a3b8;
    font-size: 0.74rem;
    font-weight: 700;
    line-height: 1.2;
}
.player-position-badge {
    align-items: center;
    background: rgba(226, 232, 240, 0.1);
    border: 1px solid rgba(226, 232, 240, 0.2);
    border-radius: var(--radius-pill);
    color: #f8fafc;
    display: inline-flex;
    flex: 0 0 auto;
    font-size: 0.68rem;
    font-weight: 920;
    letter-spacing: 0.02em;
    line-height: 1;
    min-height: 1.28rem;
    padding: 0.22rem 0.38rem;
}
.trade-asset-position-badge {
    font-size: 0.64rem;
    min-height: 1.18rem;
}
.compact-player-reason {
    color: #cbd5e1;
    font-size: 0.8rem;
    line-height: 1.32;
    margin-top: 0.42rem;
    overflow: visible;
}
.compact-player-reason strong {
    color: #f8fafc;
    font-weight: 850;
}
.scan-card-compact {
    border-radius: var(--radius-panel);
    padding: 0.6rem 0.68rem 0.62rem 0.78rem;
}
.scan-card-compact::before {
    top: 10px;
    bottom: 10px;
    width: 3px;
}
.scan-card-compact::after {
    height: 30px;
    width: 62%;
}
.scan-card::after {
    content: "";
    height: 40px;
    left: 0;
    opacity: 0.75;
    position: absolute;
    right: auto;
    top: 0;
    width: 54%;
    background: radial-gradient(circle at top left, var(--player-accent-soft), transparent 72%);
    z-index: 0;
}
.scan-card::before {
    background: var(--player-accent);
    border-radius: 0;
    content: "";
    left: 0;
    position: absolute;
    top: 12px;
    bottom: 12px;
    width: 4px;
    z-index: 1;
}
.scan-card-tone-premium,
.trade-asset-row-tone-premium {
    --player-accent: linear-gradient(180deg, rgba(226, 232, 240, 0.96), rgba(148, 163, 184, 0.84));
    --player-accent-soft: rgba(226, 232, 240, 0.1);
}
.scan-card-tone-elite,
.trade-asset-row-tone-elite {
    --player-accent: linear-gradient(180deg, rgba(250, 204, 21, 0.98), rgba(217, 119, 6, 0.88));
    --player-accent-soft: rgba(250, 204, 21, 0.12);
}
.scan-card-tone-star,
.trade-asset-row-tone-star {
    --player-accent: linear-gradient(180deg, rgba(196, 181, 253, 0.98), rgba(124, 58, 237, 0.86));
    --player-accent-soft: rgba(168, 85, 247, 0.12);
}
.scan-card-tone-core,
.trade-asset-row-tone-core {
    --player-accent: linear-gradient(180deg, color-mix(in srgb, var(--color-accent) 98%, transparent), color-mix(in srgb, var(--color-accent-strong) 86%, transparent));
    --player-accent-soft: color-mix(in srgb, var(--color-accent-strong) 12%, transparent);
}
.scan-card-tone-starter,
.trade-asset-row-tone-starter {
    --player-accent: linear-gradient(180deg, rgba(45, 212, 191, 0.98), rgba(13, 148, 136, 0.84));
    --player-accent-soft: rgba(20, 184, 166, 0.12);
}
.scan-card-tone-contributor,
.trade-asset-row-tone-contributor {
    --player-accent: linear-gradient(180deg, rgba(251, 191, 36, 0.92), rgba(180, 83, 9, 0.82));
    --player-accent-soft: rgba(245, 158, 11, 0.12);
}
.scan-card-tone-rise,
.trade-asset-row-tone-rise {
    --player-accent: linear-gradient(180deg, rgba(74, 222, 128, 0.98), rgba(16, 185, 129, 0.86));
    --player-accent-soft: rgba(34, 197, 94, 0.12);
}
.scan-card-tone-move,
.trade-asset-row-tone-move {
    --player-accent: linear-gradient(180deg, rgba(251, 146, 60, 0.98), rgba(234, 88, 12, 0.86));
    --player-accent-soft: rgba(249, 115, 22, 0.12);
}
.scan-card-tone-hold,
.trade-asset-row-tone-hold {
    --player-accent: linear-gradient(180deg, rgba(148, 163, 184, 0.92), rgba(71, 85, 105, 0.82));
    --player-accent-soft: rgba(100, 116, 139, 0.12);
}
.scan-card-tone-drop,
.trade-asset-row-tone-drop {
    --player-accent: linear-gradient(180deg, rgba(248, 113, 113, 0.98), rgba(220, 38, 38, 0.86));
    --player-accent-soft: rgba(239, 68, 68, 0.12);
}
.scan-card-tone-risk,
.trade-asset-row-tone-risk {
    --player-accent: linear-gradient(180deg, rgba(248, 113, 113, 0.92), rgba(185, 28, 28, 0.84));
    --player-accent-soft: rgba(239, 68, 68, 0.08);
}
.scan-card-tone-neutral,
.trade-asset-row-tone-neutral {
    --player-accent: linear-gradient(180deg, rgba(148, 163, 184, 0.84), rgba(71, 85, 105, 0.78));
    --player-accent-soft: rgba(148, 163, 184, 0.1);
}
.scan-card-main {
    align-items: flex-start;
    display: flex;
    gap: 0.8rem;
    position: relative;
    z-index: 2;
}
.scan-card-compact .scan-card-main {
    align-items: center;
    display: grid;
    gap: 0.74rem;
    grid-template-columns: 60px minmax(0, 1fr);
}
.scan-card-header-row,
.free-agent-status-row,
.trade-asset-status-row {
    align-items: center;
    display: flex;
    gap: 0.52rem;
    justify-content: space-between;
}
.scan-card-avatar {
    --avatar-size: 58px;
    align-items: center;
    align-self: flex-start;
    background: linear-gradient(160deg, var(--color-surface-raised), var(--color-surface-secondary));
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: var(--radius-control);
    display: flex;
    flex: 0 0 var(--avatar-size);
    height: var(--avatar-size);
    justify-content: center;
    overflow: hidden;
    position: relative;
    width: var(--avatar-size);
    z-index: 1;
}
.scan-card-compact .scan-card-avatar {
    --avatar-size: 60px;
    align-self: center;
    border-radius: var(--radius-panel);
    flex: 0 0 var(--avatar-size);
}
.scan-card-avatar::before {
    background: linear-gradient(180deg, rgba(8, 15, 28, 0.08), rgba(8, 15, 28, 0.22));
    border-radius: inherit;
    content: "";
    inset: 0;
    position: absolute;
    z-index: 0;
}
.scan-card-compact .scan-card-avatar::before {
    inset: 2px;
}
.scan-card-avatar span {
    position: relative;
    text-shadow: 0 2px 8px rgba(2, 6, 23, 0.9);
    z-index: 2;
}
.scan-card-avatar img {
    bottom: auto;
    filter: none;
    height: 100%;
    inset: 0;
    left: auto;
    max-width: 100%;
    object-fit: cover;
    object-position: center top;
    position: absolute;
    transform: none;
    width: 100%;
    z-index: 1;
}
.scan-card-compact .scan-card-avatar img {
    bottom: auto;
    filter: none;
    height: 100%;
    inset: 0;
    left: auto;
    max-width: 100%;
    object-fit: cover;
    object-position: center top;
    position: absolute;
    transform: none;
    width: 100%;
}
.scan-card-copy {
    min-width: 0;
    position: relative;
    width: 100%;
    z-index: 2;
}
.scan-card-compact .scan-card-copy {
    align-self: stretch;
    display: flex;
    flex-direction: column;
    gap: 0.28rem;
    justify-content: center;
    min-height: calc(var(--avatar-size) - 2px);
    padding-left: 0.08rem;
}
.scan-card-compact .scan-card-copy::before {
    background: linear-gradient(90deg, rgba(8, 15, 28, 0.28), rgba(8, 15, 28, 0.12) 58%, rgba(8, 15, 28, 0));
    border-radius: var(--radius-control);
    content: "";
    inset: -0.12rem -0.08rem -0.08rem -0.12rem;
    pointer-events: none;
    position: absolute;
    z-index: 0;
}
.scan-card-compact .scan-card-copy > * {
    position: relative;
    z-index: 1;
}
.scan-card-topline {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.34rem;
    min-width: 0;
}
.scan-card-compact .scan-card-topline {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.24rem;
}
.scan-card-topline .player-status-pill {
    flex: 0 0 auto;
    max-width: 100%;
}
.scan-card-topline .scan-card-tags {
    flex: 1 1 auto;
    min-width: 0;
}
.scan-card-compact .scan-card-topline .player-status-pill,
.scan-card-compact .scan-card-topline .scan-card-tags,
.scan-card-compact .scan-card-info,
.scan-card-compact .scan-card-score-meta {
    min-width: 0;
    width: 100%;
}
.scan-card-info {
    display: flex;
    flex-direction: column;
    gap: 0.14rem;
    min-width: 0;
}
.scan-card-score-meta {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.36rem;
    min-width: 0;
}
.scan-card-compact .scan-card-score-meta {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.14rem;
}
.scan-card-score-meta .scan-card-meta {
    flex: 1 1 88px;
    margin-top: 0;
    min-width: 0;
}
.scan-card-name-block,
.free-agent-name-block,
.trade-asset-name-block {
    min-width: 0;
    width: 100%;
}
.scan-card-name {
    color: #f8fafc;
    font-size: 1.02rem;
    font-weight: 900;
    line-height: 1.08;
    margin-top: 0.34rem;
    overflow-wrap: break-word;
    word-break: normal;
}
.scan-card-compact .scan-card-name {
    display: -webkit-box;
    font-size: 0.94rem;
    line-height: 1.06;
    margin-top: 0;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}
.scan-card-score {
    background: rgba(15, 23, 42, 0.86);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: var(--radius-pill);
    color: #e2e8f0;
    flex: 0 0 auto;
    font-size: 0.75rem;
    font-weight: 860;
    line-height: 1;
    padding: 0.36rem 0.56rem;
    white-space: nowrap;
}
.scan-card-compact .scan-card-score {
    font-size: 0.68rem;
    padding: 0.24rem 0.42rem;
}
.scan-card-tone-premium .scan-card-score {
    border-color: rgba(226, 232, 240, 0.28);
    color: #f8fafc;
}
.scan-card-tone-elite .scan-card-score {
    border-color: rgba(250, 204, 21, 0.28);
    color: #fef3c7;
}
.scan-card-tone-star .scan-card-score {
    border-color: rgba(196, 181, 253, 0.28);
    color: #f3e8ff;
}
.scan-card-tone-core .scan-card-score {
    border-color: color-mix(in srgb, var(--color-accent) 26%, transparent);
    color: #dbeafe;
}
.scan-card-tone-starter .scan-card-score,
.scan-card-tone-rise .scan-card-score {
    border-color: rgba(45, 212, 191, 0.24);
    color: #ccfbf1;
}
.scan-card-tone-contributor .scan-card-score {
    border-color: rgba(251, 191, 36, 0.24);
    color: #fef3c7;
}
.scan-card-tone-move .scan-card-score {
    border-color: rgba(251, 146, 60, 0.28);
    color: #fdba74;
}
.scan-card-tone-hold .scan-card-score,
.scan-card-tone-neutral .scan-card-score {
    border-color: rgba(148, 163, 184, 0.22);
    color: #cbd5e1;
}
.scan-card-tone-drop .scan-card-score,
.scan-card-tone-risk .scan-card-score {
    border-color: rgba(248, 113, 113, 0.28);
    color: #fecaca;
}
.scan-card-meta {
    color: #94a3b8;
    font-size: 0.81rem;
    line-height: 1.3;
    margin-top: 0.2rem;
}
.scan-card-compact .scan-card-meta {
    font-size: 0.74rem;
    line-height: 1.18;
    margin-top: 0;
}
.scan-card-compact-reason {
    color: #cbd5e1;
    display: -webkit-box;
    font-size: 0.68rem;
    line-height: 1.22;
    margin-top: 0.12rem;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}
.scan-card-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.34rem;
    margin-top: 0.42rem;
}
.scan-card-compact .scan-card-tags {
    gap: 0.26rem;
    margin-top: 0;
}
.scan-card-compact .scan-card-tags .player-support-chip:nth-child(n+3) {
    display: none;
}
.scan-card-note {
    color: #cbd5e1;
    font-size: 0.84rem;
    line-height: 1.38;
    margin-top: 0.44rem;
}
.scan-card-compact .player-status-pill {
    font-size: 0.62rem;
    gap: 0.22rem;
    padding: 0.22rem 0.38rem;
}
.scan-card-compact .player-status-glyph {
    font-size: 0.46rem;
    height: 0.92rem;
    min-width: 0.92rem;
    padding: 0 0.14rem;
}
.scan-card-compact .player-support-chip {
    font-size: 0.58rem;
    padding: 0.16rem 0.32rem;
}
.scan-card-mobile-details {
    display: none;
}
.scan-card-details {
    margin-top: 0.48rem;
}
.scan-card-details summary {
    list-style: none;
}
.scan-card-details summary::-webkit-details-marker {
    display: none;
}
.scan-card-details-toggle {
    align-items: center;
    color: #94a3b8;
    cursor: pointer;
    display: inline-flex;
    font-size: 0.74rem;
    font-weight: 820;
    gap: 0.34rem;
    letter-spacing: 0;
    line-height: 1;
}
.scan-card-details-toggle::before {
    color: #cbd5e1;
    content: "+";
    font-size: 0.88rem;
    font-weight: 900;
    line-height: 1;
}
.scan-card-details[open] .scan-card-details-toggle::before {
    content: "-";
}
.scan-card-details-body {
    margin-top: 0.42rem;
}
.scan-card-kpis {
    display: grid;
    gap: 0.48rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin-top: 0.56rem;
}
.scan-card-kpi {
    background: rgba(15, 23, 42, 0.66);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-control);
    min-width: 0;
    padding: 0.42rem 0.48rem;
}
.scan-card-kpi-label {
    color: #94a3b8;
    font-size: 0.63rem;
    font-weight: 800;
    line-height: 1.1;
    text-transform: uppercase;
}
.scan-card-kpi-value {
    color: #f8fafc;
    font-size: 0.82rem;
    font-weight: 820;
    line-height: 1.15;
    margin-top: 0.14rem;
}
.draft-review-round-grid {
    display: grid;
    gap: 0.55rem;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    margin: 0.55rem 0 0.2rem;
}
.draft-review-pick-card {
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(8, 13, 24, 0.96));
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: var(--radius-control);
    box-shadow: 0 12px 26px rgba(2, 6, 23, 0.16);
    display: grid;
    gap: 0.32rem;
    min-height: 0;
    padding: 0.7rem;
}
.draft-review-pick-top {
    align-items: center;
    display: flex;
    gap: 0.45rem;
    justify-content: space-between;
}
.draft-review-pick-slot {
    color: var(--dg-text-soft);
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0;
    text-transform: uppercase;
}
.draft-review-grade {
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: var(--radius-pill);
    color: #f8fafc;
    font-size: 0.78rem;
    font-weight: 900;
    line-height: 1;
    padding: 0.26rem 0.48rem;
}
.draft-review-grade.grade-strong {
    background: rgba(20, 184, 166, 0.18);
    border-color: rgba(20, 184, 166, 0.38);
}
.draft-review-grade.grade-solid {
    background: color-mix(in srgb, var(--color-accent-strong) 16%, transparent);
    border-color: color-mix(in srgb, var(--color-accent-strong) 34%, transparent);
}
.draft-review-grade.grade-watch {
    background: rgba(245, 158, 11, 0.16);
    border-color: rgba(245, 158, 11, 0.34);
}
.draft-review-grade.grade-risk {
    background: rgba(239, 68, 68, 0.16);
    border-color: rgba(239, 68, 68, 0.34);
}
.draft-review-grade.grade-muted {
    background: rgba(148, 163, 184, 0.12);
    border-color: rgba(148, 163, 184, 0.24);
}
.draft-review-player-name {
    color: var(--dg-text);
    font-size: 0.98rem;
    font-weight: 900;
    line-height: 1.15;
}
.draft-review-meta,
.draft-review-value,
.draft-review-reason {
    color: var(--dg-text-muted);
    font-size: 0.78rem;
    line-height: 1.35;
}
.draft-review-reason {
    color: var(--dg-text-soft);
}
.draft-review-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
}
.draft-review-chip {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: var(--radius-pill);
    color: var(--dg-text-soft);
    font-size: 0.68rem;
    font-weight: 800;
    padding: 0.18rem 0.42rem;
    text-transform: uppercase;
}
.draft-review-chip.mine {
    background: color-mix(in srgb, var(--color-accent-strong) 12%, transparent);
    border-color: color-mix(in srgb, var(--color-accent-strong) 28%, transparent);
}
.draft-review-chip.unmatched {
    background: rgba(245, 158, 11, 0.12);
    border-color: rgba(245, 158, 11, 0.28);
}
.draft-team-card {
    background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.05), transparent 34%),
        linear-gradient(180deg, rgba(16, 25, 44, 0.94), rgba(8, 13, 24, 0.92));
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: var(--radius-panel);
    box-shadow: 0 18px 36px rgba(2, 6, 23, 0.18);
    overflow: hidden;
    padding: 0.8rem 0.86rem;
    position: relative;
}
.draft-team-kicker {
    color: var(--color-accent-strong);
    font-size: 0.7rem;
    font-weight: 800;
    text-transform: uppercase;
}
.draft-team-name {
    color: #f8fafc;
    font-size: 0.98rem;
    font-weight: 860;
    line-height: 1.18;
    margin-top: 0.18rem;
}
.draft-team-meta {
    color: #94a3b8;
    font-size: 0.8rem;
    line-height: 1.32;
    margin-top: 0.24rem;
}
.draft-team-note {
    color: #cbd5e1;
    font-size: 0.84rem;
    line-height: 1.38;
    margin-top: 0.42rem;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(10, 16, 29, 0.98), rgba(6, 10, 20, 0.98));
    border-right: 1px solid rgba(148, 163, 184, 0.12);
    color: #f8fafc;
}
[data-testid="stSidebar"],
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4 {
    color: #f8fafc;
}
[data-testid="stSidebar"] .stButton button {
    width: 100%;
}
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stSelectbox label {
    font-weight: 700;
}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] select,
[data-testid="stSidebar"] [role="combobox"] {
    background: var(--color-bg);
    color: #f8fafc;
}
.stButton button {
    background: linear-gradient(180deg, rgba(22, 32, 53, 0.98), rgba(10, 16, 30, 0.98));
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: var(--radius-control);
    box-shadow:
        0 10px 22px rgba(2, 6, 23, 0.16),
        inset 0 1px 0 rgba(248, 250, 252, 0.04);
    font-weight: 650;
}
[data-testid="stMetric"] {
    background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.04), transparent 36%),
        linear-gradient(180deg, rgba(17, 24, 39, 0.98), rgba(11, 16, 32, 0.98));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    box-shadow:
        0 14px 30px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(248, 250, 252, 0.03);
    overflow: hidden;
    padding: 0.82rem 0.9rem;
    position: relative;
}
[data-testid="stMetric"]::after {
    background: linear-gradient(90deg, color-mix(in srgb, var(--color-accent-strong) 92%, transparent), rgba(45, 212, 191, 0.78));
    content: "";
    height: 2px;
    left: 0;
    position: absolute;
    right: 0;
    top: 0;
}
[data-testid="stMetricLabel"] p {
    color: #94a3b8;
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
}
[data-testid="stMetricValue"] {
    font-weight: 880;
}
[data-testid="stDataFrame"],
[data-testid="stPlotlyChart"] {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-control);
    overflow: hidden;
    width: 100%;
}
[data-testid="stPlotlyChart"] > div {
    width: 100% !important;
}
.trade-meta {
    color: #cbd5e1;
    font-size: 0.92rem;
    margin: 0.35rem 0 0.7rem;
}
.trade-idea-card {
    background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.05), transparent 34%),
        linear-gradient(180deg, rgba(14, 23, 40, 0.98), rgba(7, 12, 24, 0.96));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    box-shadow: 0 22px 50px rgba(2, 6, 23, 0.28);
    margin: 0.8rem 0 1rem;
    overflow: hidden;
    position: relative;
}
.trade-card-top {
    align-items: flex-start;
    background: linear-gradient(180deg, rgba(18, 27, 46, 0.98), rgba(10, 16, 30, 0.97));
    border-bottom: 1px solid rgba(148, 163, 184, 0.12);
    display: flex;
    gap: 0.8rem;
    justify-content: space-between;
    padding: 0.85rem 1rem;
}
.trade-card-kicker {
    color: var(--color-accent-strong);
    font-size: 0.73rem;
    font-weight: 800;
    letter-spacing: 0;
    text-transform: uppercase;
}
.trade-card-title {
    color: #f8fafc;
    font-size: 1.04rem;
    font-weight: 900;
    line-height: 1.22;
    margin-top: 0.18rem;
}
.trade-card-subtitle {
    color: #94a3b8;
    font-size: 0.8rem;
    margin-top: 0.22rem;
}
.trade-card-meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.36rem;
    margin-top: 0.34rem;
}
.trade-card-focus-row {
    display: grid;
    gap: 0.5rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin-top: 0.58rem;
}
.trade-card-focus-item {
    background: rgba(8, 15, 28, 0.62);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-control);
    min-width: 0;
    padding: 0.52rem 0.58rem;
}
.trade-card-focus-label {
    color: #94a3b8;
    font-size: 0.65rem;
    font-weight: 820;
    text-transform: uppercase;
}
.trade-card-focus-value {
    color: #f8fafc;
    font-size: 0.82rem;
    font-weight: 820;
    line-height: 1.2;
    margin-top: 0.2rem;
    word-break: break-word;
}
.trade-reason-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.45rem;
}
.trade-reason-tag {
    background: color-mix(in srgb, var(--color-accent-strong) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-accent-strong) 28%, transparent);
    border-radius: var(--radius-pill);
    color: var(--color-accent);
    font-size: 0.68rem;
    font-weight: 840;
    padding: 0.22rem 0.48rem;
    white-space: nowrap;
}
.trade-detail-summary {
    background: rgba(8, 15, 28, 0.62);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    margin: 0.68rem 1rem 0;
    padding: 0.62rem 0.7rem;
}
.trade-detail-title {
    color: #e2e8f0;
    font-size: 0.76rem;
    font-weight: 860;
    letter-spacing: 0;
    margin-bottom: 0.45rem;
}
.trade-idea-secondary {
    border-color: rgba(245, 158, 11, 0.16);
    box-shadow: 0 16px 36px rgba(2, 6, 23, 0.2);
}
.trade-idea-secondary .trade-card-top {
    background: linear-gradient(180deg, rgba(20, 22, 32, 0.96), rgba(11, 14, 24, 0.96));
}
.trade-secondary-banner {
    color: #fbbf24;
    font-size: 0.68rem;
    font-weight: 840;
    letter-spacing: 0;
    margin-top: 0.3rem;
    text-transform: uppercase;
}
.trade-delta-pill {
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: var(--radius-pill);
    color: #f8fafc;
    flex: 0 0 auto;
    font-size: 0.84rem;
    font-weight: 800;
    padding: 0.42rem 0.66rem;
    box-shadow:
        inset 0 1px 0 rgba(248, 250, 252, 0.05),
        0 10px 22px rgba(2, 6, 23, 0.18);
    white-space: nowrap;
}
.trade-delta-positive {
    background: rgba(20, 184, 166, 0.16);
    border-color: rgba(20, 184, 166, 0.45);
    color: #5eead4;
}
.trade-delta-negative {
    background: rgba(239, 68, 68, 0.16);
    border-color: rgba(239, 68, 68, 0.45);
    color: #fca5a5;
}
.trade-delta-neutral {
    background: rgba(148, 163, 184, 0.14);
    color: #cbd5e1;
}
.trade-matchup {
    align-items: stretch;
    display: grid;
    gap: 0.85rem;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    padding: 1rem;
}
.trade-side {
    min-width: 0;
}
.trade-side-header {
    align-items: center;
    color: #cbd5e1;
    display: flex;
    font-size: 0.78rem;
    font-weight: 800;
    justify-content: space-between;
    letter-spacing: 0;
    margin-bottom: 0.55rem;
    text-transform: uppercase;
}
.trade-side-value {
    color: #f8fafc;
    font-size: 0.95rem;
    text-transform: none;
}
.trade-assets {
    display: grid;
    gap: 0.55rem;
}
.trade-asset-row {
    --player-accent: linear-gradient(180deg, rgba(148, 163, 184, 0.84), rgba(71, 85, 105, 0.78));
    --player-accent-soft: rgba(148, 163, 184, 0.1);
    align-items: center;
    background:
        radial-gradient(circle at top left, var(--player-accent-soft), transparent 42%),
        linear-gradient(180deg, rgba(12, 18, 34, 0.98), rgba(7, 11, 22, 0.98));
    border: 1px solid rgba(148, 163, 184, 0.1);
    border-radius: var(--radius-panel);
    box-shadow:
        0 8px 18px rgba(2, 6, 23, 0.14),
        inset 0 1px 0 rgba(248, 250, 252, 0.03);
    display: flex;
    gap: 0.7rem;
    min-width: 0;
    overflow: hidden;
    padding: 0.68rem 0.72rem 0.68rem 0.88rem;
    position: relative;
}
.trade-asset-row-player.player-card-tappable {
    cursor: pointer;
}
.trade-asset-row-player.player-card-tappable:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--color-accent-strong) 72%, transparent);
    outline-offset: 2px;
}
.trade-asset-row::after {
    background: var(--player-accent);
    border-radius: var(--radius-pill);
    content: "";
    height: calc(100% - 16px);
    left: 8px;
    position: absolute;
    top: 8px;
    width: 2px;
}
.trade-asset-row-pick::after {
    background: linear-gradient(180deg, rgba(250, 204, 21, 0.96), rgba(245, 158, 11, 0.88));
}
.trade-asset-name {
    color: #f8fafc;
    font-size: 0.92rem;
    font-weight: 860;
    line-height: 1.14;
    margin-top: 0.3rem;
}
.trade-asset-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.32rem;
    margin-top: 0.38rem;
}
.trade-avatar,
.player-avatar,
.free-agent-avatar {
    --avatar-size: 116px;
    align-items: center;
    background: linear-gradient(160deg, var(--color-surface-raised), var(--color-surface-secondary));
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-none);
    box-shadow: var(--shadow-none);
    color: var(--color-text-primary);
    display: flex;
    flex: 0 0 var(--avatar-size);
    font-size: var(--font-size-body);
    font-weight: var(--font-weight-title);
    height: var(--avatar-size);
    justify-content: center;
    overflow: hidden;
    position: relative;
    width: var(--avatar-size);
}
.avatar-tone-premium {
    border-color: rgba(226, 232, 240, 0.44);
    box-shadow:
        0 8px 18px rgba(2, 6, 23, 0.44),
        0 0 0 2px rgba(226, 232, 240, 0.08),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.avatar-tone-elite {
    border-color: rgba(250, 204, 21, 0.5);
    box-shadow:
        0 8px 18px rgba(2, 6, 23, 0.44),
        0 0 0 2px rgba(250, 204, 21, 0.1),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.avatar-tone-star {
    border-color: rgba(196, 181, 253, 0.46);
    box-shadow:
        0 8px 18px rgba(2, 6, 23, 0.44),
        0 0 0 2px rgba(168, 85, 247, 0.08),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.avatar-tone-core {
    border-color: color-mix(in srgb, var(--color-accent-strong) 42%, transparent);
    box-shadow:
        0 8px 18px rgba(2, 6, 23, 0.44),
        0 0 0 2px color-mix(in srgb, var(--color-accent-strong) 8%, transparent),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.avatar-tone-starter,
.avatar-tone-rise {
    border-color: rgba(45, 212, 191, 0.42);
    box-shadow:
        0 8px 18px rgba(2, 6, 23, 0.44),
        0 0 0 2px rgba(20, 184, 166, 0.08),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.avatar-tone-contributor {
    border-color: rgba(251, 191, 36, 0.4);
    box-shadow:
        0 8px 18px rgba(2, 6, 23, 0.44),
        0 0 0 2px rgba(245, 158, 11, 0.08),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.avatar-tone-move {
    border-color: rgba(245, 158, 11, 0.44);
    box-shadow:
        0 8px 18px rgba(2, 6, 23, 0.44),
        0 0 0 2px rgba(245, 158, 11, 0.08),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.avatar-tone-hold {
    border-color: rgba(148, 163, 184, 0.34);
    box-shadow:
        0 8px 18px rgba(2, 6, 23, 0.42),
        0 0 0 2px rgba(148, 163, 184, 0.06),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.avatar-tone-drop,
.avatar-tone-risk {
    border-color: rgba(248, 113, 113, 0.46);
    box-shadow:
        0 8px 18px rgba(2, 6, 23, 0.44),
        0 0 0 2px rgba(248, 113, 113, 0.08),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.trade-avatar:not(.trade-avatar-pick)::before,
.player-avatar::before,
.free-agent-avatar::before {
    background: radial-gradient(circle at 50% 35%, rgba(248, 250, 252, 0.18), color-mix(in srgb, var(--color-accent-strong) 12%, transparent) 48%, rgba(2, 6, 23, 0.18) 72%);
    border-radius: 50%;
    content: "";
    inset: 4px;
    position: absolute;
    z-index: 0;
}
.trade-avatar span:not(.dg-player-headshot-fallback),
.player-avatar span:not(.dg-player-headshot-fallback),
.free-agent-avatar span:not(.dg-player-headshot-fallback) {
    position: relative;
    text-shadow: 0 2px 8px rgba(2, 6, 23, 0.9);
    z-index: 2;
}
.trade-avatar-pick {
    background: rgba(245, 158, 11, 0.18);
    border-color: rgba(245, 158, 11, 0.55);
    box-shadow:
        0 10px 24px rgba(2, 6, 23, 0.5),
        0 0 0 4px rgba(245, 158, 11, 0.08),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
    color: #fbbf24;
}
.player-avatar {
    margin-bottom: 0.18rem;
}
.trade-asset-copy {
    display: grid;
    gap: 0.18rem;
    min-width: 0;
    padding-left: 0.24rem;
}
.trade-asset-name {
    color: #f8fafc;
    font-size: 0.96rem;
    font-weight: 860;
    line-height: 1.18;
    overflow-wrap: anywhere;
}
.trade-asset-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.32rem;
    margin-top: 0.24rem;
}
.trade-asset-meta {
    color: #94a3b8;
    font-size: 0.82rem;
    line-height: 1.25;
    margin-top: 0.18rem;
}
.trade-asset-health-note {
    color: #fca5a5;
    font-size: 0.76rem;
    line-height: 1.28;
    margin-top: 0.18rem;
}
.trade-vs {
    align-items: center;
    align-self: center;
    background: linear-gradient(180deg, rgba(8, 15, 28, 0.98), rgba(4, 8, 18, 0.98));
    border: 1px solid color-mix(in srgb, var(--color-accent-strong) 16%, transparent);
    border-radius: var(--radius-pill);
    color: #cbd5e1;
    display: flex;
    font-size: 0.76rem;
    font-weight: 900;
    height: 38px;
    justify-content: center;
    box-shadow:
        inset 0 1px 0 rgba(248, 250, 252, 0.04),
        0 10px 22px rgba(2, 6, 23, 0.18);
    width: 38px;
}
.trade-value-meter {
    border-top: 1px solid var(--color-border);
    display: grid;
    gap: 0.5rem;
    padding: 0 1rem 0.95rem;
}
.trade-meter-row {
    align-items: center;
    display: grid;
    gap: 0.65rem;
    grid-template-columns: 5.5rem minmax(0, 1fr) 4.8rem;
}
.trade-meter-label,
.trade-meter-number {
    color: #cbd5e1;
    font-size: 0.82rem;
    font-weight: 750;
}
.trade-meter-number {
    text-align: right;
}
.trade-meter-track {
    background: linear-gradient(180deg, rgba(5, 10, 20, 0.98), rgba(2, 6, 12, 0.98));
    border: 1px solid rgba(148, 163, 184, 0.1);
    border-radius: var(--radius-pill);
    height: 0.58rem;
    overflow: hidden;
}
.trade-meter-fill {
    border-radius: var(--radius-pill);
    height: 100%;
    min-width: 3px;
}
.trade-meter-send {
    background: var(--color-accent-strong);
}
.trade-meter-receive {
    background: #14b8a6;
}
.trade-rationale {
    border-top: 1px solid rgba(148, 163, 184, 0.1);
    color: #cbd5e1;
    font-size: 0.86rem;
    line-height: 1.38;
    padding: 0.75rem 1rem 0.9rem;
}
.trade-rationale-compact {
    font-size: 0.78rem;
    line-height: 1.32;
    padding: 0.58rem 1rem 0.7rem;
}
.trade-fit-grid {
    border-top: 1px solid var(--color-border);
    display: grid;
    gap: 0.7rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding: 0.85rem 1rem 0.95rem;
}
.trade-fit-card {
    background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.04), transparent 40%),
        linear-gradient(180deg, rgba(16, 25, 44, 0.94), rgba(8, 13, 24, 0.9));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    box-shadow:
        0 14px 30px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(248, 250, 252, 0.04);
    min-width: 0;
    overflow: hidden;
    padding: 0.72rem 0.78rem;
    position: relative;
}
.trade-result-card {
    border-color: rgba(20, 184, 166, 0.36);
    box-shadow:
        0 20px 48px rgba(2, 6, 23, 0.32),
        0 0 0 1px rgba(20, 184, 166, 0.06);
}
.trade-result-card .trade-card-top {
    background: linear-gradient(180deg, rgba(20, 184, 166, 0.08), rgba(17, 24, 39, 0.98));
}
.trade-idea-positive::after,
.trade-result-card::after {
    background: linear-gradient(90deg, rgba(20, 184, 166, 0.98), color-mix(in srgb, var(--color-accent-strong) 88%, transparent));
}
.trade-idea-negative::after {
    background: linear-gradient(90deg, rgba(245, 158, 11, 0.98), rgba(239, 68, 68, 0.84));
}
.trade-idea-neutral::after {
    background: linear-gradient(90deg, rgba(148, 163, 184, 0.86), rgba(99, 102, 241, 0.72));
}
.trade-fit-card:first-child {
    border-color: color-mix(in srgb, var(--color-accent-strong) 26%, transparent);
}
.trade-fit-card:last-child {
    border-color: rgba(245, 158, 11, 0.24);
}
.trade-fit-label {
    color: #94a3b8;
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
}
.trade-fit-value {
    color: #f8fafc;
    font-size: 1rem;
    font-weight: 850;
    margin-top: 0.22rem;
}
.trade-fit-note {
    color: #cbd5e1;
    font-size: 0.82rem;
    line-height: 1.32;
    margin-top: 0.24rem;
}
.dg-intel-grid {
    display: grid;
    gap: 0.45rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin: 0.55rem 0 0.85rem;
    max-width: min(100%, 90rem);
}
.dg-intel-card {
    background: var(--color-surface-primary, #0f1114);
    border: 1px solid var(--dg-border, #2a2e36);
    border-radius: 2px;
    box-shadow: none;
    min-width: 0;
    padding: 0.7rem 0.75rem;
}
.dg-intel-card--supporting {
    opacity: 0.98;
}
.dg-intel-kicker {
    color: #94a3b8;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.dg-intel-team-row {
    align-items: center;
    display: flex;
    gap: 0.75rem;
    margin-top: 0.6rem;
}
.dg-intel-logo-wrap {
    align-items: center;
    background: linear-gradient(160deg, var(--color-surface-raised), var(--color-surface-secondary));
    border: 1px solid rgba(148, 163, 184, 0.35);
    border-radius: 50%;
    color: #f8fafc;
    display: flex;
    flex: 0 0 52px;
    font-size: 0.84rem;
    font-weight: 900;
    height: 52px;
    justify-content: center;
    overflow: hidden;
    width: 52px;
}
.dg-intel-logo-wrap img {
    height: 100%;
    object-fit: cover;
    width: 100%;
}
.dg-intel-team-copy {
    min-width: 0;
}
.dg-intel-title {
    color: #f8fafc;
    font-size: 1rem;
    font-weight: 850;
    line-height: 1.2;
}
.dg-intel-owner {
    color: #cbd5e1;
    font-size: 0.84rem;
    margin-top: 0.16rem;
}
.dg-intel-metric {
    color: #f8fafc;
    font-size: 1.15rem;
    font-weight: 900;
    line-height: 1.1;
    margin-top: 0.7rem;
}
.dg-intel-note {
    color: #94a3b8;
    font-size: 0.84rem;
    line-height: 1.35;
    margin-top: 0.35rem;
}
.news-card {
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(10, 16, 30, 0.88));
    border: 1px solid rgba(148, 163, 184, 0.1);
    border-radius: var(--radius-control);
    padding: 0.8rem 0.86rem;
}
.dg-alert-banner {
    background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.04), transparent 40%),
        linear-gradient(180deg, rgba(16, 25, 44, 0.96), rgba(8, 13, 24, 0.94));
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-panel);
    box-shadow:
        0 18px 38px rgba(2, 6, 23, 0.18),
        inset 0 1px 0 rgba(248, 250, 252, 0.04);
    margin: 0.2rem 0 0.7rem;
    overflow: hidden;
    padding: 0.8rem 0.88rem;
    position: relative;
}
.dg-alert-banner::after {
    content: "";
    height: 2px;
    left: 0;
    position: absolute;
    right: 0;
    top: 0;
}
.dg-alert-warning {
    border-color: rgba(245, 158, 11, 0.22);
}
.dg-alert-warning::after {
    background: linear-gradient(90deg, rgba(245, 158, 11, 0.98), rgba(239, 68, 68, 0.84));
}
.dg-alert-kicker {
    color: #f59e0b;
    font-size: 0.7rem;
    font-weight: 860;
    text-transform: uppercase;
}
.dg-alert-title {
    color: #f8fafc;
    font-size: 0.98rem;
    font-weight: 900;
    line-height: 1.14;
    margin-top: 0.18rem;
}
.dg-alert-body {
    color: #cbd5e1;
    font-size: 0.82rem;
    line-height: 1.34;
    margin-top: 0.22rem;
}
[data-testid="stAlert"] {
    background: var(--color-surface-muted);
    border: var(--border-width-default) solid var(--color-border);
    border-radius: var(--radius-panel);
    box-shadow: var(--shadow-none);
}
.news-card-top {
    align-items: flex-start;
    display: flex;
    gap: 0.75rem;
    justify-content: space-between;
}
.news-card-title {
    color: #f8fafc;
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.3;
    text-decoration: none;
}
.news-card-title:hover {
    color: var(--color-accent);
}
.news-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    justify-content: flex-end;
}
.news-badge {
    background: rgba(148, 163, 184, 0.12);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: var(--radius-pill);
    color: #cbd5e1;
    font-size: 0.74rem;
    font-weight: 700;
    padding: 0.2rem 0.5rem;
    white-space: nowrap;
}
.news-badge-priority {
    background: rgba(20, 184, 166, 0.16);
    border-color: rgba(20, 184, 166, 0.42);
    color: #99f6e4;
}
.news-badge-warning {
    background: rgba(245, 158, 11, 0.16);
    border-color: rgba(245, 158, 11, 0.38);
    color: #fcd34d;
}
.news-summary {
    color: #cbd5e1;
    font-size: 0.9rem;
    line-height: 1.42;
    margin-top: 0.55rem;
}

@media (max-width: 700px) {
    .draft-review-round-grid {
        grid-template-columns: 1fr;
    }
    .draft-review-pick-card {
        gap: 0.28rem;
        padding: 0.62rem;
    }
    .block-container {
        padding: 0.75rem 0.65rem 4.2rem;
    }
    .summary-tile,
    .analysis-card,
    .decision-panel,
    .draft-review-pick-card,
    .launch-section-intro,
    .launch-league-card,
    .dg-alert-banner,
    .dg-intel-card,
    .news-card,
    [data-testid="stMetric"] {
        border-radius: var(--radius-panel);
        min-height: 0;
        overflow-wrap: anywhere;
        padding: 0.68rem 0.72rem;
    }
    .section-title,
    .launch-section-title,
    .team-section-title {
        font-size: 0.94rem;
        line-height: 1.16;
    }
    .section-note,
    .launch-section-copy,
    .dg-alert-body,
    .news-summary {
        font-size: 0.78rem;
        line-height: 1.32;
    }
    .launch-league-chip,
    .dg-glyph-chip,
    .dg-tier-chip,
    .player-support-chip,
    .player-status-pill,
    .news-badge,
    .draft-review-chip,
    .home-status-pill,
    .account-status-chip {
        font-size: 0.64rem;
        line-height: 1.12;
        padding: 0.2rem 0.42rem;
        white-space: normal;
    }
    .app-degraded-state,
    .decision-panel-empty {
        border-radius: var(--radius-control);
        font-size: 0.76rem;
        line-height: 1.3;
        padding: 0.62rem 0.66rem;
    }
    .platform-sidebar-card {
        padding: 0.8rem 0.85rem;
    }
    .platform-sidebar-top {
        align-items: flex-start;
    }
    .app-hero {
        display: none;
    }
    [data-testid="stHorizontalBlock"] {
        gap: 0.65rem;
    }
    [data-testid="stMetric"] {
        padding: 0.7rem;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.65rem;
    }
    [data-testid="stTabs"] [role="tablist"] {
        gap: 0.15rem;
        overflow-x: auto;
        white-space: nowrap;
    }
    [data-testid="stTabs"] [role="tab"] {
        min-width: max-content;
        padding-left: 0.45rem;
        padding-right: 0.45rem;
    }
    [data-testid="stDataFrame"],
    [data-testid="stPlotlyChart"] {
        max-width: calc(100vw - 1.3rem);
        overflow-x: auto;
    }
    [data-testid="stPlotlyChart"] {
        min-height: 220px;
    }
    .trade-card-top {
        gap: 0.65rem;
        padding: 0.78rem 0.82rem;
    }
    .trade-card-focus-row {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .trade-detail-summary {
        margin: 0.5rem 0.68rem 0;
        padding: 0.5rem 0.54rem;
    }
    .trade-detail-title {
        font-size: 0.7rem;
        margin-bottom: 0.34rem;
    }
    .team-identity-card {
        align-items: flex-start;
        padding: 0.8rem;
    }
    .team-logo-wrap {
        flex-basis: 58px;
        height: 58px;
        width: 58px;
    }
    .team-name {
        font-size: 1.2rem;
    }
    .team-owner-handle {
        font-size: 0.92rem;
    }
    .team-score-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .summary-tile-grid,
    .analysis-grid,
    .decision-panel-grid {
        gap: 0.5rem;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin: 0.45rem 0 0.72rem;
    }
    .dg-intel-grid {
        grid-template-columns: 1fr;
    }
    .summary-tile,
    .analysis-card,
    .decision-panel {
        border-radius: var(--radius-panel);
        min-height: 0;
        padding: 0.62rem 0.66rem;
    }
    .summary-tile-value,
    .summary-tile-note,
    .analysis-card-title,
    .analysis-list {
        overflow-wrap: anywhere;
    }
    .summary-tile-compact {
        padding: 0.5rem 0.54rem;
    }
    .summary-tile-label,
    .analysis-card-label,
    .decision-panel-label {
        font-size: 0.64rem;
    }
    .summary-tile-value,
    .analysis-card-title,
    .decision-panel-title {
        font-size: 0.88rem;
        line-height: 1.12;
        margin-top: 0.16rem;
    }
    .summary-tile-note {
        font-size: 0.72rem;
        line-height: 1.24;
        margin-top: 0.2rem;
    }
    .analysis-list {
        font-size: 0.76rem;
        line-height: 1.34;
        margin-top: 0.32rem;
        padding-left: 0.84rem;
    }
    .analysis-list li + li {
        margin-top: 0.18rem;
    }
    .decision-panel-grid-alert {
        grid-template-columns: 1fr;
    }
    .decision-panel-grid-alert .player-status-pill {
        align-self: flex-start;
    }
    .dg-intel-grid {
        gap: 0.5rem;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin: 0.45rem 0 0.72rem;
    }
    .dg-intel-card {
        border-radius: var(--radius-control);
        padding: 0.62rem;
    }
    .dg-intel-kicker {
        font-size: 0.64rem;
    }
    .dg-intel-team-row {
        gap: 0.48rem;
        margin-top: 0.42rem;
    }
    .dg-intel-logo-wrap {
        flex: 0 0 40px;
        height: 40px;
        width: 40px;
    }
    .dg-intel-title {
        font-size: 0.84rem;
        line-height: 1.08;
    }
    .dg-intel-owner,
    .dg-intel-note {
        font-size: 0.7rem;
        line-height: 1.2;
    }
    .dg-intel-metric {
        font-size: 0.74rem;
        line-height: 1.18;
        margin-top: 0.28rem;
    }
    .advice-grid {
        gap: 0.5rem;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin: 0.45rem 0 0.72rem;
    }
    .advice-card {
        border-radius: var(--radius-panel);
        padding: 0.62rem 0.66rem;
    }
    .advice-label {
        font-size: 0.64rem;
    }
    .advice-title {
        font-size: 0.88rem;
        line-height: 1.12;
        margin-top: 0.16rem;
    }
    .advice-body {
        font-size: 0.72rem;
        line-height: 1.24;
        margin-top: 0.2rem;
    }
    .section-header {
        margin: 0.52rem 0 0.34rem;
        padding: 0.56rem 0.62rem;
    }
    .section-header-compact {
        margin-top: 0.38rem;
        padding: 0.5rem 0.58rem;
    }
    .section-kicker {
        font-size: 0.66rem;
    }
    .section-title {
        font-size: 0.9rem;
        margin-top: 0.12rem;
    }
    .section-note {
        font-size: 0.72rem;
        line-height: 1.22;
        margin-top: 0.16rem;
    }
    .scan-section-shell {
        margin: 0.46rem 0 0.62rem;
    }
    .free-agent-summary-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .free-agent-main {
        align-items: flex-start;
        flex-direction: row;
        gap: 0.44rem;
    }
    .free-agent-top {
        align-items: flex-start;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 0.36rem;
    }
    .free-agent-avatar {
        --avatar-size: 46px;
        flex: 0 0 46px;
    }
    .free-agent-score-pill {
        align-self: flex-start;
        font-size: 0.66rem;
        padding: 0.24rem 0.4rem;
    }
    .free-agent-card {
        padding: 0.38rem 0.44rem 0.42rem 0.54rem;
    }
    .free-agent-name {
        font-size: 0.88rem;
        line-height: 1.12;
    }
    .free-agent-meta {
        font-size: 0.7rem;
        line-height: 1.2;
        margin-top: 0.12rem;
    }
    .free-agent-tags {
        gap: 0.22rem;
        margin-top: 0.18rem;
    }
    .free-agent-reason {
        font-size: 0.74rem;
        line-height: 1.28;
        margin-top: 0.16rem;
    }
    .scan-card-list {
        gap: 0.55rem;
        grid-template-columns: repeat(auto-fit, minmax(min(172px, 100%), 1fr));
    }
    .scan-card-list.scan-card-list-compact {
        gap: 0.42rem;
        grid-template-columns: 1fr;
        margin: 0.46rem 0 0.7rem;
    }
    .scan-card-list.scan-card-list-compact:has(.scan-card-recommendation) {
        grid-template-columns: 1fr;
    }
    .scan-card {
        border-radius: var(--radius-panel);
        padding: 0.46rem 0.52rem 0.48rem 0.62rem;
    }
    .compact-player-row {
        border-radius: var(--radius-control);
        gap: 0.38rem;
        grid-template-columns: 44px minmax(0, 1fr);
        height: auto;
        min-height: 0;
        padding: 0.36rem 0.44rem 0.38rem;
    }
    .compact-player-avatar {
        --avatar-size: 44px;
    }
    .compact-player-badges {
        gap: 0.22rem;
    }
    .compact-player-tags .player-support-chip:nth-child(n+2) {
        display: none;
    }
    .compact-player-name {
        font-size: 0.84rem;
        line-height: 1.12;
        margin-top: 0.1rem;
    }
    .compact-player-score-meta {
        gap: 0.22rem;
        margin-top: 0.12rem;
    }
    .compact-player-value {
        font-size: 0.64rem;
        padding: 0.2rem 0.36rem;
    }
    .compact-player-meta {
        font-size: 0.66rem;
    }
    .compact-player-reason {
        font-size: 0.72rem;
        line-height: 1.28;
        margin-top: 0.22rem;
    }
    .scan-card::before {
        top: 9px;
        bottom: 9px;
        width: 3px;
    }
    .scan-card::after {
        height: 28px;
        width: 68%;
    }
    .scan-card-compact {
        border-radius: var(--radius-control);
        padding: 0.34rem 0.42rem 0.36rem 0.52rem;
    }
    .scan-card-compact::before {
        top: 7px;
        bottom: 7px;
        width: 3px;
    }
    .scan-card-compact::after {
        height: 16px;
        width: 62%;
    }
    .scan-card-main {
        align-items: flex-start;
        flex-direction: row;
        gap: 0.44rem;
    }
    .scan-card-compact .scan-card-main {
        align-items: flex-start;
        gap: 0.38rem;
        grid-template-columns: 48px minmax(0, 1fr);
    }
    .scan-card-avatar {
        --avatar-size: 46px;
        flex: 0 0 auto;
    }
    .scan-card-compact .scan-card-avatar {
        --avatar-size: 48px;
        align-self: flex-start;
        flex: 0 0 48px;
    }
    .scan-card-score,
    .free-agent-score-pill {
        align-self: flex-start;
    }
    .free-agent-status-row,
    .trade-asset-status-row {
        align-items: flex-start;
        flex-direction: column;
    }
    .scan-card-header-row {
        align-items: center;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 0.35rem;
    }
    .scan-card-compact .scan-card-header-row {
        align-items: flex-start;
        gap: 0.24rem;
        justify-content: flex-start;
    }
    .scan-card-compact .scan-card-header-row .scan-card-score {
        margin-left: auto;
    }
    .scan-card-name {
        font-size: 0.92rem;
        line-height: 1.12;
        margin-top: 0.08rem;
    }
    .scan-card-compact .scan-card-name {
        font-size: 0.82rem;
        line-height: 1.08;
        margin-top: 0;
    }
    .scan-card-score {
        font-size: 0.68rem;
        padding: 0.28rem 0.46rem;
    }
    .scan-card-compact .scan-card-score {
        font-size: 0.62rem;
        padding: 0.18rem 0.34rem;
    }
    .scan-card-meta {
        font-size: 0.72rem;
        line-height: 1.22;
        margin-top: 0.14rem;
    }
    .scan-card-compact .scan-card-meta {
        font-size: 0.62rem;
        line-height: 1.16;
        margin-top: 0;
    }
    .scan-card-compact-reason {
        display: none;
    }
    .scan-card-compact .scan-card-copy {
        gap: 0.1rem;
        justify-content: flex-start;
        min-height: 0;
        padding-left: 0;
    }
    .scan-card-compact.scan-card-recommendation .scan-card-compact-reason {
        display: block;
        font-size: 0.7rem;
        line-height: 1.24;
        margin-top: 0.08rem;
        overflow: visible;
        -webkit-line-clamp: unset;
    }
    .scan-card-compact.scan-card-recommendation .scan-card-main {
        align-items: start;
        gap: 0.34rem;
        grid-template-columns: 44px minmax(0, 1fr);
    }
    .scan-card-compact.scan-card-recommendation .scan-card-avatar {
        --avatar-size: 44px;
        align-self: start;
        flex-basis: 44px;
        margin-top: 0;
    }
    .scan-card-compact.scan-card-recommendation {
        padding: 0.3rem 0.38rem 0.32rem 0.46rem;
    }
    .scan-card-compact.scan-card-recommendation .scan-card-copy {
        gap: 0.12rem;
        justify-content: flex-start;
        min-height: 0;
        padding-left: 0;
    }
    .scan-card-compact.scan-card-recommendation .scan-card-topline {
        align-items: center;
        flex-direction: row;
        gap: 0.2rem;
    }
    .scan-card-compact.scan-card-recommendation .scan-card-info {
        gap: 0.06rem;
    }
    .scan-card-tags {
        gap: 0.28rem;
        margin-top: 0.28rem;
    }
    .scan-card-compact .scan-card-tags {
        gap: 0.18rem;
        margin-top: 0;
    }
    .scan-card-compact .scan-card-tags .player-support-chip:nth-child(n+2) {
        display: none;
    }
    .scan-card-tags .player-support-chip:nth-child(n+3) {
        display: none;
    }
    .scan-card-compact .player-status-pill {
        font-size: 0.58rem;
        gap: 0.16rem;
        padding: 0.18rem 0.32rem;
        max-width: 100%;
    }
    .scan-card-compact .player-status-glyph {
        font-size: 0.42rem;
        height: 0.8rem;
        min-width: 0.8rem;
        padding: 0 0.1rem;
    }
    .scan-card-compact .player-support-chip {
        font-size: 0.56rem;
        padding: 0.16rem 0.28rem;
    }
    .scan-card-topline {
        gap: 0.24rem;
    }
    .scan-card-score-meta {
        gap: 0.28rem;
    }
    .scan-card-desktop-extras {
        display: none;
    }
    .scan-card-mobile-details {
        display: block;
        margin-top: 0.3rem;
    }
    .scan-card-compact .scan-card-mobile-details {
        display: none;
        margin-top: 0;
    }
    .scan-card-details {
        margin-top: 0;
    }
    .scan-card-details-body .scan-card-kpis {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin-top: 0;
    }
    .scan-card-details-body .scan-card-note {
        font-size: 0.76rem;
        line-height: 1.28;
        margin-top: 0.34rem;
    }
    .dg-alert-banner {
        border-radius: var(--radius-panel);
        margin: 0.14rem 0 0.46rem;
        padding: 0.64rem 0.7rem;
    }
    .dg-alert-title {
        font-size: 0.86rem;
        line-height: 1.08;
        margin-top: 0.12rem;
    }
    .dg-alert-body {
        font-size: 0.74rem;
        line-height: 1.22;
        margin-top: 0.16rem;
    }
    .scan-card-compact .scan-card-desktop-extras {
        display: none;
    }
    .prospect-watch-groups {
        gap: 0.52rem;
        margin: 0.42rem 0 0.72rem;
    }
    .prospect-position-group .prospect-grid {
        gap: 0.42rem;
        grid-template-columns: 1fr;
        margin-top: 0.26rem;
    }
    .prospect-card {
        border-radius: var(--radius-control);
        display: block;
        padding: 0.58rem 0.64rem;
        width: 100%;
    }
    .prospect-card-head {
        align-items: flex-start;
        gap: 0.5rem;
    }
    .prospect-card-head .prospect-meta {
        font-size: 0.62rem;
        margin-top: 0;
        max-width: 42%;
    }
    .prospect-label,
    .prospect-position-title {
        font-size: 0.62rem;
    }
    .prospect-name {
        font-size: 0.86rem;
        line-height: 1.12;
        margin-top: 0.14rem;
    }
    .prospect-note {
        font-size: 0.72rem;
        line-height: 1.26;
        margin-top: 0.28rem;
    }
    .prospect-meta {
        font-size: 0.66rem;
        margin-top: 0.2rem;
    }
    .trade-card-top {
        flex-direction: column;
        gap: 0.42rem;
        padding: 0.62rem 0.68rem;
    }
    .trade-delta-pill {
        align-self: flex-start;
    }
    .trade-matchup {
        justify-items: stretch;
        grid-template-columns: 1fr;
        gap: 0.5rem;
        padding: 0.62rem 0.68rem;
    }
    .trade-side,
    .trade-assets,
    .trade-asset-row {
        box-sizing: border-box;
        margin-left: auto;
        margin-right: auto;
        width: 100%;
    }
    .trade-assets {
        gap: 0.38rem;
    }
    .trade-vs {
        height: auto;
        justify-self: center;
        padding: 0.35rem;
        width: 64px;
    }
    .trade-meter-row {
        gap: 0.45rem;
        grid-template-columns: 4.4rem minmax(0, 1fr) 4.1rem;
    }
    .trade-value-meter {
        gap: 0.38rem;
        padding: 0.55rem 0.68rem 0.62rem;
    }
    .trade-rationale-compact {
        font-size: 0.72rem;
        line-height: 1.26;
        padding: 0.5rem 0.68rem 0.6rem;
    }
    .trade-card-title {
        font-size: 1rem;
    }
    .trade-asset-row {
        align-items: flex-start;
        gap: 0.3rem;
        min-height: 0;
        padding: 0.28rem 0.34rem;
    }
    .trade-fit-grid {
        grid-template-columns: 1fr;
        padding: 0.62rem 0.68rem;
    }
    .trade-avatar,
    .player-avatar {
        --avatar-size: 46px;
    }
    .trade-asset-row .trade-avatar {
        --avatar-size: 42px;
        flex-basis: 42px;
        height: 42px;
        width: 42px;
    }
    .trade-asset-copy {
        gap: 0.08rem;
        padding-left: 0;
    }
    .trade-asset-name {
        font-size: 0.8rem;
        line-height: 1.08;
        margin-top: 0;
    }
    .trade-asset-meta {
        font-size: 0.64rem;
        line-height: 1.16;
        margin-top: 0.08rem;
    }
    .trade-asset-tags {
        gap: 0.16rem;
        margin-top: 0.1rem;
    }
    .trade-asset-tags .player-support-chip:nth-child(n+3) {
        display: none;
    }
    .trade-asset-health-note {
        font-size: 0.64rem;
        line-height: 1.18;
        margin-top: 0.08rem;
    }
    .news-card {
        padding: 0.8rem;
    }
    .news-card-top {
        flex-direction: column;
    }
    .news-badges {
        justify-content: flex-start;
    }
}

@media (max-width: 380px) {
    .summary-tile-grid,
    .analysis-grid,
    .decision-panel-grid,
    .dg-intel-grid,
    .advice-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 900px) {
    .block-container {
        padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 10.4rem);
    }
    .legal-footer-safe-space {
        height: calc(env(safe-area-inset-bottom, 0px) + 6.4rem);
    }
    .platform-sidebar-card,
    .sidebar-desktop-only {
        display: none !important;
    }
    .desktop-sidebar-nav {
        display: none !important;
    }
    div[data-testid="stPopoverContent"] {
        backdrop-filter: blur(18px);
        background: linear-gradient(180deg, rgba(8, 15, 28, 0.97), rgba(5, 9, 19, 0.99));
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: var(--radius-panel);
        box-shadow: 0 22px 52px rgba(2, 6, 23, 0.42);
        padding-top: 0.18rem;
    }
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button {
        border-radius: var(--radius-panel);
        font-size: 0.72rem;
        font-weight: 820;
        min-height: 52px;
        padding: 0.34rem 0.28rem;
        white-space: normal;
    }
    div[data-testid="stPopoverContent"] [data-testid="stSelectbox"] label {
        font-size: 0.76rem;
        font-weight: 760;
    }
    div[data-testid="stPopoverContent"] [data-baseweb="select"] {
        font-size: 0.82rem;
    }
    div[data-testid="stPopoverContent"] [data-testid="stCaptionContainer"] {
        margin-top: 0.35rem;
    }
    div[data-testid="stPopover"] > button:focus,
    div[data-testid="stPopover"] > button:focus-visible {
        box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent) 28%, transparent);
        outline: none;
    }
    div[data-testid="stPopoverContent"] .stColumn {
        min-width: 0;
    }
    div[data-testid="stPopoverContent"] {
        max-width: min(90vw, 304px);
    }
    div[data-testid="stPopover"] {
        margin: 0 !important;
    }
    [data-testid="stSidebar"] .platform-sidebar-card {
        margin-bottom: 0.65rem;
    }
    [data-testid="stPopoverContent"] [data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(180deg, color-mix(in srgb, var(--color-accent-strong) 22%, transparent), color-mix(in srgb, var(--color-accent-strong) 18%, transparent));
        border: 1px solid color-mix(in srgb, var(--color-accent-strong) 28%, transparent);
        color: #f8fafc;
    }
    [data-testid="stPopoverContent"] [data-testid="stButton"] > button[kind="secondary"] {
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(148, 163, 184, 0.12);
        color: #cbd5e1;
    }
    [data-testid="stPopoverContent"] [data-testid="stButton"] > button[kind="secondary"]:hover {
        background: rgba(30, 41, 59, 0.88);
        color: #f8fafc;
    }
    [data-testid="stPopoverContent"] [data-testid="stButton"] > button[kind="primary"]:hover {
        background: linear-gradient(180deg, color-mix(in srgb, var(--color-accent-strong) 28%, transparent), color-mix(in srgb, var(--color-accent-strong) 22%, transparent));
        color: #f8fafc;
    }
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) {
        background: linear-gradient(180deg, rgba(8, 15, 28, 0.98), rgba(5, 9, 19, 1));
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-left: 0;
        border-radius: 0;
        bottom: calc(env(safe-area-inset-bottom, 0px) + 4.25rem);
        box-shadow: 0 24px 56px rgba(2, 6, 23, 0.44);
        left: max(env(safe-area-inset-left, 0px), 0px);
        max-height: min(60vh, 450px);
        max-width: min(92vw, 420px);
        overflow-y: auto;
        padding: 0.76rem 0.8rem 0.82rem;
        position: fixed;
        right: auto;
        z-index: 1000;
    }
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button {
        border-radius: var(--radius-panel);
        font-size: 0.76rem;
        font-weight: 820;
        min-height: 48px;
        padding: 0.32rem 0.36rem;
        white-space: normal;
    }
    .home-command-hero {
        grid-template-columns: 52px minmax(0, 1fr);
        gap: 0.7rem;
        margin-top: 0.35rem;
        padding: 0.72rem 0.76rem;
    }
    .home-hero-logo {
        border-radius: var(--radius-panel);
        font-size: 0.94rem;
        height: 52px;
        width: 52px;
    }
    .home-command-team {
        font-size: 1rem;
    }
    .home-command-meta {
        font-size: 0.74rem;
    }
    .home-command-badges {
        gap: 0.28rem;
        margin-top: 0.38rem;
    }
    .home-command-badge {
        font-size: 0.64rem;
        padding: 0.18rem 0.42rem;
    }
    .home-hero-stats {
        gap: 0.38rem;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin-top: 0.6rem;
    }
    .home-hero-stat {
        border-radius: var(--radius-control);
        padding: 0.42rem 0.5rem;
    }
    .home-hero-stat-value {
        font-size: 0.8rem;
    }
    .home-command-grid {
        gap: 0.5rem;
        margin: 0.58rem 0 0.72rem;
        grid-template-columns: 1fr;
    }
    .home-command-card {
        border-radius: var(--radius-panel);
        padding: 0.54rem 0.58rem;
    }
    .home-command-player-card {
        padding: 0.38rem 0.42rem 0.4rem;
    }
    .home-command-player-card .home-command-card-top {
        margin-bottom: 0.18rem;
    }
    .home-command-player-card .scan-card-compact {
        padding: 0.3rem 0.36rem 0.32rem 0.46rem;
    }
    .home-command-player-card .scan-card-compact.scan-card-recommendation .scan-card-main {
        align-items: flex-start;
        gap: 0.34rem;
        grid-template-columns: 44px minmax(0, 1fr);
    }
    .home-command-player-card .scan-card-compact.scan-card-recommendation .scan-card-avatar {
        --avatar-size: 44px;
        flex-basis: 44px;
    }
    .home-command-player-card .scan-card-compact-reason {
        margin-top: 0.08rem;
    }
    .scan-card.scan-card-mobile-row,
    .home-command-player-card,
    .home-command-player-card .scan-card,
    .home-command-player-card .scan-card-compact,
    .scan-card-list.scan-card-list-compact .scan-card,
    .scan-card-list.scan-card-list-compact .scan-card-compact,
    .scan-card.scan-card-compact {
        aspect-ratio: auto !important;
        height: auto !important;
        min-height: 0 !important;
    }
    .scan-card.scan-card-mobile-row {
        display: block !important;
        padding: 0.3rem 0.38rem 0.34rem 0.48rem !important;
    }
    .home-command-player-card .scan-card-compact,
    .scan-card-list.scan-card-list-compact .scan-card-compact,
    .scan-card.scan-card-compact {
        padding: 0.26rem 0.34rem 0.3rem 0.42rem !important;
    }
    .scan-card.scan-card-mobile-row .scan-card-main,
    .home-command-player-card .scan-card-main,
    .home-command-player-card .scan-card-compact .scan-card-main,
    .scan-card-list.scan-card-list-compact .scan-card-main,
    .scan-card-list.scan-card-list-compact .scan-card-compact .scan-card-main,
    .scan-card.scan-card-compact .scan-card-main {
        align-items: flex-start !important;
        display: grid !important;
        gap: 0.3rem !important;
        grid-template-columns: 44px minmax(0, 1fr) !important;
        grid-template-rows: auto !important;
        height: auto !important;
        min-height: 0 !important;
    }
    .scan-card.scan-card-mobile-row .scan-card-avatar,
    .home-command-player-card .scan-card-avatar,
    .home-command-player-card .scan-card-compact .scan-card-avatar,
    .scan-card-list.scan-card-list-compact .scan-card-avatar,
    .scan-card-list.scan-card-list-compact .scan-card-compact .scan-card-avatar,
    .scan-card.scan-card-compact .scan-card-avatar {
        --avatar-size: 44px !important;
        align-self: flex-start !important;
        flex: 0 0 44px !important;
        height: 44px !important;
        margin-top: 0 !important;
        width: 44px !important;
    }
    .scan-card.scan-card-mobile-row .scan-card-copy,
    .home-command-player-card .scan-card-copy,
    .home-command-player-card .scan-card-compact .scan-card-copy,
    .scan-card-list.scan-card-list-compact .scan-card-copy,
    .scan-card-list.scan-card-list-compact .scan-card-compact .scan-card-copy,
    .scan-card.scan-card-compact .scan-card-copy {
        align-self: flex-start !important;
        display: flex !important;
        flex-direction: column !important;
        gap: 0.1rem !important;
        justify-content: flex-start !important;
        min-height: 0 !important;
        padding-left: 0 !important;
    }
    .scan-card.scan-card-mobile-row .scan-card-copy::before {
        display: none !important;
    }
    .scan-card.scan-card-mobile-row .scan-card-topline {
        align-items: center !important;
        flex-direction: row !important;
        gap: 0.2rem !important;
        margin: 0 0 0.08rem !important;
    }
    .scan-card.scan-card-mobile-row .scan-card-info {
        display: block !important;
        height: auto !important;
        min-height: 0 !important;
    }
    .scan-card.scan-card-mobile-row .scan-card-score-meta {
        align-items: center !important;
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 0.22rem !important;
        margin-top: 0.08rem !important;
    }
    .home-command-player-card .scan-card-compact-reason,
    .scan-card.scan-card-mobile-row .scan-card-compact-reason,
    .scan-card-list.scan-card-list-compact .scan-card-compact-reason,
    .scan-card.scan-card-compact .scan-card-compact-reason {
        display: block !important;
        margin-top: 0.22rem !important;
        max-height: none !important;
        overflow: visible !important;
        position: static !important;
        -webkit-line-clamp: unset !important;
    }
    .scan-card.scan-card-mobile-row .scan-card-desktop-extras,
    .scan-card.scan-card-mobile-row .scan-card-mobile-details {
        display: none !important;
    }
    .home-command-card-label {
        font-size: 0.64rem;
    }
    .home-command-card-value {
        font-size: 0.9rem;
    }
    .home-command-card-note {
        font-size: 0.74rem;
        margin-top: 0.2rem;
    }
    .launch-league-card {
        border-radius: var(--radius-panel);
        padding: 0.76rem 0.78rem;
    }
    .launch-league-top {
        gap: 0.66rem;
    }
    .launch-league-name {
        font-size: 0.92rem;
    }
    .launch-league-team {
        font-size: 0.76rem;
    }
    .home-status-strip {
        gap: 0.42rem;
        grid-template-columns: 1fr;
        margin: 0.5rem 0 0.66rem;
    }
    .home-status-pill {
        border-radius: var(--radius-control);
        padding: 0.52rem 0.58rem;
    }
    .home-status-value {
        font-size: 0.8rem;
    }
    .home-status-note {
        font-size: 0.7rem;
    }
    .player-detail-hero {
        gap: 0.72rem;
        grid-template-columns: 72px minmax(0, 1fr);
        padding: 0.78rem 0.8rem;
    }
    .player-detail-avatar {
        --avatar-size: 72px;
    }
    .player-detail-name {
        font-size: 1rem;
    }
    .player-detail-meta {
        font-size: 0.76rem;
    }
    .player-detail-score-row {
        gap: 0.45rem;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin-top: 0.56rem;
    }
    .player-detail-score-pill {
        border-radius: var(--radius-control);
        padding: 0.5rem 0.55rem;
    }
    .player-detail-score-value {
        font-size: 0.88rem;
    }
    .player-quick-view-hero {
        gap: 0.72rem;
        grid-template-columns: 76px minmax(0, 1fr);
        padding: 0.78rem 0.8rem;
    }
    .player-quick-view-avatar {
        --avatar-size: 76px;
    }
    .player-quick-view-name {
        font-size: 1rem;
    }
    .player-quick-view-meta {
        font-size: 0.76rem;
    }
    .dg-page-meta {
        gap: 0.3rem;
        margin-top: 0.34rem;
    }
    .dg-glyph-chip,
    .dg-tier-chip {
        font-size: 0.62rem;
        padding: 0.22rem 0.42rem;
    }
}

@media (max-width: 380px) {
    .scan-card-list.scan-card-list-compact {
        grid-template-columns: 1fr;
    }
}
.stApp,
[data-testid="stAppViewContainer"] {
    background:
        linear-gradient(180deg, #020409 0%, #070a11 46%, #03050a 100%) !important;
}
[data-testid="stHeader"] {
    display: none !important;
}
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stMetric"],
[data-testid="stAlert"],
div[data-testid="stExpander"],
.platform-sidebar-card,
.team-identity-card,
.team-section-card,
.home-command-hero,
.home-command-card,
.home-command-route-card,
.launch-section-intro,
.launch-league-card,
.summary-tile,
.analysis-card,
.advice-card,
.prospect-card,
.team-score-item,
.draft-team-card,
.draft-review-pick-card,
.trade-idea-card,
.trade-fit-card,
.trade-card-top,
.trade-card-focus-item,
.trade-detail-summary,
.free-agent-summary-card,
.free-agent-card,
.app-degraded-state {
    background:
        linear-gradient(180deg, rgba(14, 17, 25, 0.86), rgba(5, 7, 12, 0.94)) !important;
    border: 1px solid rgba(226, 232, 240, 0.09) !important;
    border-radius: var(--radius-control) !important;
    box-shadow:
        0 18px 44px rgba(0, 0, 0, 0.34),
        inset 0 1px 0 rgba(248, 250, 252, 0.03) !important;
}
.team-identity-card,
.home-command-hero,
.trade-idea-card,
.draft-review-pick-card,
.summary-tile,
.analysis-card,
.home-command-card,
.free-agent-summary-card,
.free-agent-card {
    clip-path: polygon(0 0, calc(100% - 9px) 0, 100% 9px, 100% 100%, 0 100%) !important;
}
/* removed dead midfile card accent (UNIFY/content:none cascade). */

.summary-tile-power,
.summary-tile-opportunity,
.summary-tile-franchise,
.summary-tile-strategy,
.home-command-card-trade,
.home-command-card-waiver,
.home-command-card-draft,
.home-command-card-risk,
.home-command-card-need,
.advice-card-primary,
.advice-card-priority,
.advice-card-need,
.advice-card-health,
.advice-card-opportunity,
.analysis-card-strength,
.analysis-card-weakness,
.analysis-card-risk,
.trade-idea-secondary {
    border-color: rgba(226, 232, 240, 0.1) !important;
    box-shadow:
        0 18px 44px rgba(0, 0, 0, 0.3),
        inset 0 1px 0 rgba(248, 250, 252, 0.025) !important;
}
/* removed dead midfile card accent (UNIFY/content:none cascade). */

.summary-tile-risk,
.summary-tile-weakness,
.home-command-card-risk,
.home-command-card-need,
.analysis-card-risk,
.analysis-card-weakness,
.advice-card-health,
.advice-card-need {
    border-color: rgba(245, 158, 11, 0.18) !important;
}
/* removed dead midfile card accent (UNIFY/content:none cascade). */

.home-command-shell,
.summary-tile-grid,
.team-score-grid,
.free-agent-summary-grid,
.draft-review-round-grid,
.trade-card-focus-row {
    justify-items: stretch !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
}
.home-command-kicker,
.team-section-title,
.summary-tile-label,
.analysis-card-label,
.trade-card-kicker,
.draft-review-pick-slot,
.free-agent-summary-label,
.team-owner-meta,
.summary-tile-note,
.analysis-card-title,
.analysis-card-label,
.trade-card-subtitle,
.free-agent-summary-meta {
    color: rgba(203, 213, 225, 0.72) !important;
}
.home-command-badge,
.launch-league-chip,
.trade-reason-tag,
.free-agent-score-pill,
.free-agent-tag,
.draft-review-chip,
.dg-glyph-chip,
.dg-tier-chip,
.player-support-chip,
.account-status-chip,
.player-status-pill {
    border-radius: var(--radius-pill) !important;
    box-shadow: none !important;
}
.trade-reason-tag,
.free-agent-score-pill,
.home-command-badge,
.launch-league-chip {
    background: rgba(16, 20, 30, 0.76) !important;
    border-color: rgba(226, 232, 240, 0.12) !important;
    color: rgba(226, 232, 240, 0.9) !important;
}
.scan-card,
.compact-player-row,
.trade-asset-row {
    background:
        linear-gradient(180deg, rgba(15, 19, 29, 0.88), rgba(5, 8, 14, 0.95)) !important;
    border-color: rgba(226, 232, 240, 0.11) !important;
    border-radius: var(--radius-control) !important;
    box-shadow:
        0 16px 34px rgba(0, 0, 0, 0.28),
        inset 3px 0 0 var(--player-accent, color-mix(in srgb, var(--color-accent-strong) 58%, transparent)) !important;
}
.scan-card::after,
.scan-card-compact::after,
.trade-asset-row::after,
.free-agent-card::after {
    opacity: 0.28 !important;
}
.scan-card::before,
.trade-asset-row::before,
.free-agent-card::before {
    border-radius: 0 !important;
    width: 3px !important;
}
[data-testid="stButton"] > button,
[data-testid="stDownloadButton"] > button,
[data-testid="stFormSubmitButton"] > button,
div[data-testid="stPopoverContent"] [data-testid="stButton"] > button {
    background:
        linear-gradient(180deg, rgba(18, 22, 32, 0.9), rgba(6, 9, 15, 0.96)) !important;
    border-color: rgba(226, 232, 240, 0.12) !important;
    border-radius: var(--radius-control) !important;
    box-shadow: none !important;
}
[data-testid="stButton"] > button[kind="primary"],
[data-testid="stFormSubmitButton"] > button[kind="primary"],
div[data-testid="stPopoverContent"] [data-testid="stButton"] > button[kind="primary"] {
    border-color: color-mix(in srgb, var(--color-accent-strong) 28%, transparent) !important;
    color: var(--color-accent) !important;
}
:root {
    --dg-accent: var(--color-accent);
    --dg-accent-strong: var(--color-accent-strong);
    --dg-success: var(--color-success);
    --dg-warning: var(--color-warning);
    --dg-danger: var(--color-danger);
    --dg-premium: var(--color-premium);
    --dg-elite: var(--color-action);
    --dg-shell-black: var(--color-bg);
    --dg-shell-graphite: var(--color-shell);
    --dg-shell-charcoal: var(--color-surface-primary);
    --dg-glass-panel: var(--color-surface-primary);
    --dg-glass-panel-strong: var(--color-surface-secondary);
    --dg-glass-border: var(--color-border);
    --dg-border: var(--color-border);
    --dg-border-strong: var(--color-border-strong);
    --dg-radius-card: var(--radius-panel);
    --dg-radius-panel: var(--radius-panel);
    --dg-radius-control: var(--radius-control);
    --dg-radius-chip: var(--radius-pill);
    --dg-shadow-panel: var(--shadow-card);
}
.stApp {
    background:
        linear-gradient(180deg, var(--dg-shell-black) 0%, var(--dg-shell-graphite) 48%, var(--color-bg) 100%) !important;
    color: var(--dg-text);
}
.block-container {
    padding-left: clamp(0.9rem, 2.4vw, 2rem);
    padding-right: clamp(0.9rem, 2.4vw, 2rem);
}
.home-hero-logo {
    background:
        linear-gradient(180deg, rgba(18, 24, 36, 0.9), rgba(5, 8, 14, 0.95));
    border-color: var(--dg-glass-border);
    border-radius: var(--dg-radius-card);
    box-shadow: var(--dg-shadow-panel);
}
.app-degraded-state,
.dg-card-primary,
.dg-card-secondary,
.dg-card-reference,
.dg-card-warning,
.platform-sidebar-card,
.launch-card,
.draft-review-pick-card,
.trade-card,
.trade-asset-row,
.free-agent-card,
.free-agent-summary-card,
.scan-card,
.compact-player-row {
    backdrop-filter: none;
    background: var(--color-surface-primary) !important;
    border-color: var(--color-border) !important;
    border-radius: var(--radius-panel) !important;
    box-shadow: var(--shadow-none) !important;
}
.dg-card-primary,
.dg-card-secondary,
.dg-card-reference,
.dg-card-warning,
.draft-review-pick-card,
.trade-card {
    clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 0 100%);
}
.dg-card-primary,
.home-command-card-primary {
    border-color: color-mix(in srgb, var(--color-accent-strong) 24%, transparent) !important;
}
.dg-card-warning,
.app-degraded-state {
    background:
        linear-gradient(180deg, rgba(28, 22, 12, 0.72), rgba(8, 10, 16, 0.92)) !important;
    border-color: rgba(245, 158, 11, 0.24) !important;
}
.dg-glyph-chip,
.dg-tier-chip,
.player-support-chip,
.draft-review-chip,
.account-status-chip,
.launch-league-chip,
.compact-player-value,
.player-status-pill,
.news-badge,
.news-badge-warning {
    border-radius: var(--dg-radius-chip) !important;
    box-shadow: none;
    letter-spacing: 0.01em;
    padding: 0.2rem 0.46rem;
}
.dg-glyph-chip-primary {
    background: color-mix(in srgb, var(--color-accent-strong) 10%, transparent);
    border-color: color-mix(in srgb, var(--color-accent-strong) 24%, transparent);
}
.dg-glyph-chip-success {
    background: rgba(34, 197, 94, 0.1);
    border-color: rgba(34, 197, 94, 0.24);
}
.dg-glyph-chip-warning {
    background: rgba(245, 158, 11, 0.1);
    border-color: rgba(245, 158, 11, 0.24);
}
[data-testid="stButton"] > button,
[data-testid="stDownloadButton"] > button,
[data-testid="stFormSubmitButton"] > button,
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"] {
    border-radius: var(--dg-radius-control) !important;
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
    background: rgba(5, 8, 14, 0.82) !important;
    border-color: rgba(226, 232, 240, 0.12) !important;
    border-radius: var(--dg-radius-control) !important;
}
/* Select/dropdown chrome owned by COMPONENT_FAMILY_CSS. */

@media (max-width: 900px) {
    input,
    input[type="text"],
    input[type="number"],
    input[type="password"],
    input[type="email"],
    input[type="search"],
    input[type="tel"],
    input[type="url"],
    textarea,
    select,
    [role="combobox"],
    [contenteditable="true"],
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stSelectbox"] [role="combobox"],
    [data-testid="stMultiSelect"] [role="combobox"],
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea,
    [data-baseweb="select"] input,
    [data-baseweb="select"] [role="combobox"],
    [data-baseweb="select"] > div {
        font-size: 16px !important;
        line-height: 1.35 !important;
    }

    button,
    a,
    summary,
    [role="button"],
    [data-testid="stButton"] > button,
    [data-testid="stDownloadButton"] > button,
    [data-testid="stFormSubmitButton"] > button,
    [data-testid="stRadio"] label,
    [data-testid="stCheckbox"] label,
    [data-testid="stPopover"] button,
    [data-testid="stDialog"] button,
    div[class*="st-key-mobile_gm_sheet_trigger_"] button,
    div[class*="st-key-global_feedback_"] button {
        touch-action: manipulation;
    }
}
div[data-testid="stExpander"] {
    border-color: rgba(226, 232, 240, 0.1) !important;
    border-radius: var(--dg-radius-panel) !important;
    overflow: hidden;
}
.scan-card,
.compact-player-row,
.trade-asset-row,
.free-agent-card,
.free-agent-summary-card {
    border-left: 3px solid var(--player-accent, color-mix(in srgb, var(--color-accent-strong) 62%, transparent)) !important;
}
.scan-card::before,
.trade-asset-row::before,
.free-agent-card::before {
    border-radius: 0 var(--dg-radius-chip) var(--dg-radius-chip) 0 !important;
}

@media (max-width: 900px) {
    .block-container {
        padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 10.8rem);
    }
    div[data-testid="stPopoverContent"],
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) {
        background: var(--dg-glass-panel-strong) !important;
        border-color: var(--dg-glass-border) !important;
        border-radius: 0 !important;
        box-shadow: 0 24px 58px rgba(0, 0, 0, 0.48) !important;
    }
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button {
        border-radius: var(--dg-radius-control) !important;
        min-height: 46px;
    }
}
[data-testid="stVerticalBlockBorderWrapper"],
.team-identity-card,
.team-section-card,
.home-command-hero,
.home-command-card,
.home-command-route-card,
.launch-section-intro,
.launch-league-card,
.summary-tile,
.analysis-card,
.advice-card,
.prospect-card,
.team-score-item,
.draft-team-card,
.draft-review-pick-card,
.trade-idea-card,
.trade-fit-card,
.trade-card-top,
.trade-card-focus-item,
.trade-detail-summary,
.free-agent-summary-card,
.free-agent-card,
.app-degraded-state {
    background:
        linear-gradient(180deg, rgba(13, 16, 24, 0.9), rgba(4, 6, 11, 0.96)) !important;
    border-color: rgba(226, 232, 240, 0.09) !important;
    border-radius: var(--radius-control) !important;
    box-shadow:
        0 18px 42px rgba(0, 0, 0, 0.34),
        inset 0 1px 0 rgba(248, 250, 252, 0.025) !important;
}
/* removed dead midfile card accent (UNIFY/content:none cascade). */

.summary-tile-risk,
.summary-tile-weakness,
.home-command-card-risk,
.home-command-card-need,
.analysis-card-risk,
.analysis-card-weakness,
.advice-card-health,
.advice-card-need,
.app-degraded-state {
    border-color: rgba(245, 158, 11, 0.2) !important;
}
.scan-card,
.compact-player-row,
.trade-asset-row {
    background:
        linear-gradient(180deg, rgba(15, 19, 29, 0.9), rgba(5, 8, 14, 0.96)) !important;
    border-color: rgba(226, 232, 240, 0.11) !important;
    border-radius: var(--radius-control) !important;
    box-shadow:
        0 16px 34px rgba(0, 0, 0, 0.28),
        inset 3px 0 0 var(--player-accent, color-mix(in srgb, var(--color-accent-strong) 58%, transparent)) !important;
}
.scan-card-avatar,
.compact-player-avatar,
.free-agent-avatar,
.team-logo-wrap {
    border-radius: var(--radius-control) !important;
}

@media (max-width: 900px) {
    div[data-testid="stPopoverContent"],
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) {
        background: rgba(5, 7, 12, 0.94) !important;
        border-color: rgba(226, 232, 240, 0.1) !important;
        border-radius: 0 !important;
    }
}
/* card accent kill owned by EXECUTIVE_DESIGN_UNIFY_CSS content:none */

/* removed dead midfile card accent (UNIFY/content:none cascade). */

.home-command-card,
.home-command-player-card,
.summary-tile,
.analysis-card,
.team-section-card,
.decision-panel,
.trade-idea-card,
.trade-fit-card,
.trade-detail-summary,
.free-agent-summary-card,
.draft-review-pick-card {
    background: linear-gradient(180deg, rgba(11, 14, 21, 0.88), rgba(4, 6, 11, 0.95)) !important;
    border-color: rgba(226, 232, 240, 0.08) !important;
    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.26) !important;
}
.home-command-card-trade,
.home-command-card-waiver,
.home-command-card-draft,
.summary-tile-power,
.summary-tile-opportunity,
.summary-tile-franchise,
.summary-tile-strategy,
.analysis-card-strength,
.advice-card-primary,
.advice-card-opportunity,
.trade-idea-positive {
    border-color: rgba(226, 232, 240, 0.09) !important;
}
.home-command-card-risk,
.home-command-card-need,
.summary-tile-risk,
.summary-tile-weakness,
.analysis-card-risk,
.analysis-card-weakness,
.advice-card-health,
.advice-card-need,
.dg-alert-warning {
    border-color: rgba(245, 158, 11, 0.22) !important;
}
.home-command-player-card .home-command-card-top,
.trade-card-top {
    background: rgba(5, 7, 12, 0.36) !important;
    border-bottom-color: rgba(226, 232, 240, 0.08) !important;
}
.roster-limit-strip {
    display: grid;
    gap: 0.42rem;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    margin: 0.56rem 0 0.68rem;
}
.roster-limit-stat {
    background: rgba(8, 11, 17, 0.62);
    border: 1px solid rgba(226, 232, 240, 0.08);
    border-radius: var(--radius-control);
    min-width: 0;
    padding: 0.48rem 0.52rem;
}
.roster-limit-stat span {
    color: rgba(148, 163, 184, 0.9);
    display: block;
    font-size: 0.61rem;
    font-weight: 820;
    line-height: 1.05;
    text-transform: uppercase;
}
.roster-limit-stat strong {
    color: #f8fafc;
    display: block;
    font-size: 0.9rem;
    font-weight: 900;
    line-height: 1.12;
    margin-top: 0.18rem;
    overflow-wrap: anywhere;
}
.roster-limit-stat small {
    color: rgba(203, 213, 225, 0.68);
    display: -webkit-box;
    font-size: 0.66rem;
    line-height: 1.2;
    margin-top: 0.18rem;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}
.roster-limit-stat-danger {
    border-color: rgba(239, 68, 68, 0.22);
}
.roster-limit-stat-warning {
    border-color: rgba(245, 158, 11, 0.2);
}
.decision-panel-grid-alert {
    gap: 0.46rem !important;
}
.decision-panel-grid-alert .decision-panel {
    padding: 0.58rem 0.62rem !important;
}
.decision-panel-grid-alert .decision-panel-title {
    font-size: 0.84rem !important;
}

@media (max-width: 900px) {
    .block-container {
        padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 12.4rem) !important;
    }
    .roster-limit-strip {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .roster-limit-stat {
        padding: 0.42rem 0.46rem;
    }
    .roster-limit-stat strong {
        font-size: 0.84rem;
    }
}

@media (max-width: 900px) {
    .block-container {
        max-width: none !important;
        padding-left: 0.72rem !important;
        padding-right: 0.72rem !important;
        padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 13.8rem) !important;
    }
    .home-command-shell,
    .league-team-page {
        justify-items: stretch !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
        text-align: left !important;
        width: 100% !important;
    }
    .home-command-hero,
    .team-identity-card,
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stMetric"],
    [data-testid="stAlert"],
    div[data-testid="stExpander"],
    .app-degraded-state,
    .platform-sidebar-card,
    .team-identity-card,
    .team-section-card,
    .home-command-hero,
    .home-command-card,
    .home-command-route-card,
    .home-command-player-card,
    .launch-section-intro,
    .launch-league-card,
    .summary-tile,
    .analysis-card,
    .advice-card,
    .prospect-card,
    .team-score-item,
    .decision-panel,
    .draft-team-card,
    .draft-review-pick-card,
    .trade-idea-card,
    .trade-fit-card,
    .trade-card-top,
    .trade-card-focus-item,
    .trade-detail-summary,
    .free-agent-summary-card,
    .free-agent-card {
        background: rgba(7, 9, 14, 0.9) !important;
        border-color: rgba(226, 232, 240, 0.075) !important;
        border-radius: 2px !important;
        box-shadow: none !important;
        clip-path: none !important;
    }
    .home-command-card,
    .summary-tile,
    .analysis-card,
    .decision-panel,
    .team-section-card,
    .trade-idea-card,
    .free-agent-summary-card,
    .draft-review-pick-card {
        margin-left: 0 !important;
        margin-right: 0 !important;
    }
/* card accent kill owned by EXECUTIVE_DESIGN_UNIFY_CSS content:none */

    .home-command-grid,
.summary-tile-grid,
.team-score-grid,
.decision-panel-grid,
.decision-panel-grid-alert,
.free-agent-summary-grid,
.draft-review-round-grid,
.trade-card-focus-row {
        gap: 0.44rem !important;
        justify-items: stretch !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }
    .home-command-player-card,
    .trade-idea-card,
    .free-agent-summary-card {
        padding: 0 !important;
    }
    .scan-card,
    .scan-card-compact,
    .compact-player-row,
    .trade-asset-row,
    .free-agent-card {
        border-radius: var(--radius-pill) !important;
        box-shadow: inset 3px 0 0 var(--player-accent, color-mix(in srgb, var(--color-accent-strong) 58%, transparent)) !important;
        clip-path: none !important;
    }
    .scan-card-avatar,
    .compact-player-avatar,
    .free-agent-avatar,
    .team-logo-wrap {
        border-radius: var(--radius-pill) !important;
    }
    .home-command-badge,
    .launch-league-chip,
    .trade-reason-tag,
    .free-agent-score-pill,
    .free-agent-tag,
    .draft-review-chip,
    .dg-glyph-chip,
    .dg-tier-chip,
    .player-support-chip,
    .account-status-chip,
    .player-status-pill {
        border-radius: var(--radius-pill) !important;
    }
    .roster-limit-strip {
        gap: 0.32rem !important;
        grid-template-columns: 1fr !important;
    }
    .roster-limit-stat {
        align-items: baseline;
        background: rgba(5, 7, 12, 0.62) !important;
        border-radius: 2px !important;
        display: grid;
        gap: 0.16rem 0.5rem;
        grid-template-columns: 5.6rem minmax(0, 1fr);
        padding: 0.36rem 0.44rem !important;
    }
    .roster-limit-stat span {
        grid-row: span 2;
    }
    .roster-limit-stat small {
        -webkit-line-clamp: 1;
    }
    .team-section-title,
    .trade-card-title {
        text-align: left !important;
    }
    div[data-testid="stPopoverContent"],
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) {
        background: rgba(4, 6, 11, 0.98) !important;
        border-color: rgba(226, 232, 240, 0.09) !important;
        border-left: 0 !important;
        border-radius: 0 !important;
        box-shadow: none !important;
    }
}

@media (max-width: 900px) {
    .dg-panel-list,
    .home-command-grid,
    .decision-panel-grid,
    .decision-panel-grid-alert,
    .free-agent-summary-grid,
    .free-agent-list,
    .draft-review-round-grid,
    .trade-card-focus-row {
        display: flex !important;
        flex-direction: column !important;
        gap: 2px !important;
    }
    .dg-panel-row,
    .home-command-card,
    .summary-tile,
    .analysis-card,
    .decision-panel,
    .free-agent-summary-card,
    .draft-review-pick-card,
    .trade-card-focus-item,
    .roster-limit-stat {
        border-radius: 0 !important;
        border-width: 0 0 1px 0 !important;
        box-shadow: none !important;
        clip-path: none !important;
    }
    .home-command-card,
    .decision-panel,
    .free-agent-summary-card,
    .draft-review-pick-card {
        padding: 0.54rem 0.56rem !important;
    }
    .home-command-player-card {
        background: rgba(5, 7, 12, 0.62) !important;
        border-width: 0 0 1px 0 !important;
        padding: 0 !important;
    }
    .home-command-player-card .home-command-card-top,
    .trade-card-top {
        min-height: 0 !important;
        padding: 0.46rem 0.56rem !important;
    }
    .home-command-player-card .compact-player-row,
    .home-command-player-card .scan-card,
    .free-agent-summary-card .compact-player-row,
    .decision-panel .compact-player-row {
        background: rgba(8, 10, 16, 0.72) !important;
        border-radius: 0 !important;
        margin: 0 !important;
    }
    .trade-idea-card {
        border-radius: 0 !important;
        margin: 0.52rem 0 !important;
    }
    .trade-asset-row,
    .scan-card,
    .scan-card-compact,
    .compact-player-row,
    .free-agent-card {
        border-radius: 2px !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }
    .draft-review-pick-card {
        display: grid !important;
        grid-template-columns: minmax(3.2rem, auto) minmax(0, 1fr);
        gap: 0.26rem 0.52rem !important;
        padding: 0.48rem 0.52rem !important;
    }
    .draft-review-pick-top {
        align-items: flex-start !important;
        display: contents !important;
    }
    .draft-review-pick-slot {
        grid-column: 1;
        grid-row: 1;
    }
    .draft-review-grade {
        grid-column: 1;
        grid-row: 2;
        justify-self: start;
    }
    .draft-review-player-name,
    .draft-review-meta,
    .draft-review-value,
    .draft-review-reason,
    .draft-review-chips {
        grid-column: 2;
    }
    [data-testid="stButton"] > button,
    [data-testid="stDownloadButton"] > button,
    [data-testid="stFormSubmitButton"] > button,
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button {
        border-radius: 0 !important;
        justify-content: flex-start !important;
        text-align: left !important;
    }
}
:root {
    --dg-theme-bg: var(--color-bg);
    --dg-theme-shell: var(--color-shell);
    --dg-theme-surface-primary: var(--color-surface-primary);
    --dg-theme-surface-secondary: var(--color-surface-secondary);
    --dg-theme-surface-raised: var(--color-surface-raised);
    --dg-theme-surface-muted: var(--color-surface-muted);
    --dg-theme-text: var(--color-text-primary);
    --dg-theme-text-muted: var(--color-text-muted);
    --dg-theme-divider: var(--color-border);
    --dg-theme-accent-cyan: var(--color-accent);
    --dg-theme-accent-silver: var(--color-text-secondary);
    --dg-theme-success: var(--color-success);
    --dg-theme-opportunity: var(--color-opportunity);
    --dg-theme-action: var(--color-action);
    --dg-theme-caution: var(--color-warning);
    --dg-theme-danger: var(--color-danger);
    --dg-theme-diagnostic: var(--color-diagnostic);
}
.dg-semantic-critical {
    --dg-semantic-color: var(--dg-theme-danger);
    --dg-semantic-soft: rgba(239, 68, 68, 0.16);
}
.dg-semantic-action {
    --dg-semantic-color: var(--dg-theme-action);
    --dg-semantic-soft: rgba(250, 204, 21, 0.14);
}
.dg-semantic-opportunity {
    --dg-semantic-color: var(--dg-theme-opportunity);
    --dg-semantic-soft: rgba(20, 184, 166, 0.14);
}
.dg-semantic-caution {
    --dg-semantic-color: var(--dg-theme-caution);
    --dg-semantic-soft: rgba(245, 158, 11, 0.14);
}
.dg-semantic-muted {
    --dg-semantic-color: rgba(229, 231, 235, 0.52);
    --dg-semantic-soft: rgba(229, 231, 235, 0.06);
}
.dg-semantic-grade-a {
    --dg-semantic-color: var(--dg-theme-success);
    --dg-semantic-soft: rgba(34, 197, 94, 0.15);
}
.dg-semantic-grade-b {
    --dg-semantic-color: var(--dg-theme-accent-silver);
    --dg-semantic-soft: rgba(229, 231, 235, 0.1);
}
.dg-semantic-grade-c {
    --dg-semantic-color: var(--dg-theme-caution);
    --dg-semantic-soft: rgba(245, 158, 11, 0.15);
}
.dg-semantic-grade-d {
    --dg-semantic-color: var(--dg-theme-danger);
    --dg-semantic-soft: rgba(239, 68, 68, 0.15);
}
.stApp,
[data-testid="stAppViewContainer"] {
    background:
        linear-gradient(180deg, var(--dg-theme-bg) 0%, var(--dg-theme-shell) 52%, #020304 100%) !important;
}
main,
[data-testid="stSidebar"] {
    background-color: transparent !important;
}
.dg-alert-warning,
.roster-limit-stat-danger,
.home-command-card-risk,
.summary-tile-risk,
.analysis-card-risk,
.decision-panel-risk,
.free-agent-card-tone-drop,
.free-agent-card-tone-risk {
    background:
        linear-gradient(90deg, rgba(245, 158, 11, 0.095), rgba(7, 8, 12, 0.9) 34%) !important;
    border-left: 3px solid rgba(245, 158, 11, 0.74) !important;
}
.roster-limit-stat-warning,
.home-command-card-need,
.summary-tile-weakness,
.analysis-card-weakness,
.advice-card-need,
.advice-card-health {
    background:
        linear-gradient(90deg, rgba(245, 158, 11, 0.14), rgba(7, 8, 12, 0.88) 38%) !important;
    border-left: 3px solid var(--dg-theme-caution) !important;
}
.home-command-card-trade,
.home-command-card-waiver,
.trade-idea-positive,
.free-agent-card-tone-core,
.free-agent-card-tone-rise,
.decision-panel-strength {
    background:
        linear-gradient(90deg, rgba(20, 184, 166, 0.13), rgba(7, 8, 12, 0.9) 38%) !important;
    border-left: 3px solid var(--dg-theme-opportunity) !important;
}
.home-command-card-draft,
.home-command-route-card,
.decision-panel-reference,
.app-degraded-state,
.draft-review-chip.unmatched {
    background:
        linear-gradient(90deg, rgba(139, 147, 255, 0.1), rgba(7, 8, 12, 0.88) 38%) !important;
    border-left: 3px solid var(--dg-theme-diagnostic) !important;
}
.home-command-card-cta,
.home-command-card-label,
.trade-card-kicker,
.free-agent-summary-label {
    color: var(--dg-theme-accent-silver) !important;
}
.home-command-card-trade .home-command-card-label,
.home-command-card-waiver .home-command-card-label,
.trade-idea-positive .trade-card-kicker,
.free-agent-card-tone-core .free-agent-score-pill,
.free-agent-card-tone-rise .free-agent-score-pill {
    color: #99f6e4 !important;
}
.home-command-card-risk .home-command-card-label,
.summary-tile-risk .summary-tile-label,
.analysis-card-risk .analysis-card-label,
.decision-panel-risk .decision-panel-label {
    color: #fecaca !important;
}
.home-command-card-need .home-command-card-label,
.summary-tile-weakness .summary-tile-label,
.analysis-card-weakness .analysis-card-label {
    color: #fed7aa !important;
}
.trade-idea-negative {
    background:
        linear-gradient(90deg, rgba(239, 68, 68, 0.075), rgba(7, 8, 12, 0.9) 38%) !important;
    border-left: 3px solid rgba(239, 68, 68, 0.58) !important;
}
.trade-idea-neutral {
    background:
        linear-gradient(90deg, rgba(229, 231, 235, 0.08), rgba(7, 8, 12, 0.9) 38%) !important;
    border-left: 3px solid rgba(229, 231, 235, 0.36) !important;
}
.trade-reason-tag,
.free-agent-tag,
.draft-review-chip {
    background: rgba(229, 231, 235, 0.07) !important;
    border-color: rgba(229, 231, 235, 0.14) !important;
    color: rgba(248, 250, 252, 0.86) !important;
}
.dg-glyph-chip-success {
    background: rgba(34, 197, 94, 0.12) !important;
    border-color: rgba(34, 197, 94, 0.28) !important;
    color: #bbf7d0 !important;
}
.draft-review-grade.grade-strong {
    background: rgba(34, 197, 94, 0.16) !important;
    border-color: rgba(34, 197, 94, 0.36) !important;
    color: #bbf7d0 !important;
}
.draft-review-grade.grade-solid {
    background: rgba(229, 231, 235, 0.12) !important;
    border-color: rgba(229, 231, 235, 0.28) !important;
    color: #f8fafc !important;
}
.draft-review-grade.grade-watch {
    background: rgba(245, 158, 11, 0.15) !important;
    border-color: rgba(245, 158, 11, 0.34) !important;
    color: #fde68a !important;
}
.draft-review-grade.grade-risk {
    background: rgba(239, 68, 68, 0.16) !important;
    border-color: rgba(239, 68, 68, 0.34) !important;
    color: #fecaca !important;
}
.draft-review-grade.grade-muted {
    background: rgba(139, 147, 255, 0.1) !important;
    border-color: rgba(139, 147, 255, 0.22) !important;
    color: #c7d2fe !important;
}

@media (max-width: 900px) {
    .dg-alert-warning,
    .roster-limit-stat-danger,
    .home-command-card-risk,
    .home-command-card-need,
    .home-command-card-trade,
    .home-command-card-waiver,
    .decision-panel-strength,
    .decision-panel-risk,
    .trade-idea-positive,
    .trade-idea-negative,
    .free-agent-card-tone-core,
    .free-agent-card-tone-rise,
    .free-agent-card-tone-drop,
    .free-agent-card-tone-risk {
        border-left-width: 3px !important;
    }
}
div[data-testid="stDialog"] div[role="dialog"] {
    background:
        linear-gradient(180deg, rgba(8, 9, 12, 0.98), rgba(2, 3, 5, 0.99)) !important;
    border: 1px solid rgba(229, 231, 235, 0.16) !important;
    border-radius: var(--radius-pill) !important;
    box-shadow:
        0 26px 72px rgba(0, 0, 0, 0.62),
        inset 0 1px 0 rgba(255, 255, 255, 0.035) !important;
    color: var(--dg-theme-text) !important;
    max-width: min(760px, calc(100vw - 0.75rem)) !important;
    overflow: hidden !important;
}
div[data-testid="stDialog"] div[role="dialog"] > div:first-child {
    border-bottom: 1px solid rgba(229, 231, 235, 0.1) !important;
}
div[data-testid="stDialog"] h2,
div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] h2 {
    color: #f8fafc !important;
    font-weight: 900 !important;
    letter-spacing: 0 !important;
}
.dg-quick-view-panel.player-quick-view-shell {
    background: var(--dg-theme-surface-primary) !important;
    border: 1px solid rgba(229, 231, 235, 0.12) !important;
    border-radius: 2px !important;
    box-shadow: none !important;
    margin: 0 !important;
    overflow: hidden !important;
}
.player-quick-view-header-band.player-quick-view-hero {
    align-items: stretch !important;
    background:
        linear-gradient(90deg, rgba(34, 211, 238, 0.06), rgba(12, 13, 16, 0.98) 18%, rgba(3, 4, 6, 0.99)) !important;
    border: 0 !important;
    border-bottom: 1px solid rgba(229, 231, 235, 0.13) !important;
    border-left: 3px solid rgba(148, 163, 184, 0.55) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    gap: 0.78rem !important;
    grid-template-columns: 88px minmax(0, 1fr) !important;
    padding: 0.78rem 0.82rem !important;
}
.player-quick-view-avatar {
    --avatar-size: 88px;
    border-radius: var(--radius-pill) !important;
    box-shadow: none !important;
}
.player-quick-view-copy {
    align-content: start;
    display: grid;
    min-width: 0;
}
.player-quick-view-source {
    color: rgba(226, 232, 240, 0.78) !important;
    font-size: 0.65rem !important;
    font-weight: 900 !important;
    letter-spacing: 0.04em !important;
    line-height: 1.1 !important;
    text-transform: uppercase;
}
.player-quick-view-name {
    color: #ffffff !important;
    font-size: 1.18rem !important;
    font-weight: 950 !important;
    letter-spacing: 0 !important;
    line-height: 1.02 !important;
    margin-top: 0.16rem !important;
    text-align: left !important;
}
.player-quick-view-meta {
    color: rgba(248, 250, 252, 0.74) !important;
    font-size: 0.75rem !important;
    line-height: 1.22 !important;
}
.player-quick-view-panel-body {
    background:
        linear-gradient(180deg, rgba(8, 9, 12, 0.96), rgba(2, 3, 5, 0.98)) !important;
    display: grid;
    gap: 0.55rem;
    padding: 0.72rem 0.82rem 0.82rem;
}
.player-quick-view-recommendation-card {
    background:
        linear-gradient(135deg, rgba(34, 211, 238, 0.15), rgba(9, 10, 13, 0.96) 42%, rgba(2, 3, 5, 0.98)) !important;
    border: 1px solid rgba(34, 211, 238, 0.22) !important;
    border-left: 4px solid var(--dg-theme-accent-cyan) !important;
    border-radius: 2px !important;
    margin: 0.5rem 0 0.38rem !important;
    padding: 0.56rem 0.68rem !important;
}
.player-quick-view-detail-list {
    border: 1px solid rgba(229, 231, 235, 0.1);
    border-radius: 2px;
    display: grid;
    overflow: hidden;
}
.player-quick-view-detail-row {
    align-items: start;
    background: rgba(8, 9, 12, 0.78);
    border-bottom: 1px solid rgba(229, 231, 235, 0.08);
    display: grid;
    gap: 0.58rem;
    grid-template-columns: minmax(5.6rem, 0.36fr) minmax(0, 1fr);
    min-width: 0;
    padding: 0.55rem 0.62rem;
}
.player-quick-view-detail-row:last-child {
    border-bottom: 0;
}
.player-quick-view-detail-label {
    color: rgba(248, 250, 252, 0.48);
    font-size: 0.64rem;
    font-weight: 900;
    letter-spacing: 0.04em;
    line-height: 1.15;
    text-transform: uppercase;
}
.player-quick-view-detail-copy {
    min-width: 0;
}
.player-quick-view-detail-value {
    color: #ffffff;
    font-size: 0.82rem;
    font-weight: 880;
    line-height: 1.16;
    overflow-wrap: anywhere;
}
.player-quick-view-detail-note {
    color: rgba(248, 250, 252, 0.62);
    font-size: 0.72rem;
    line-height: 1.28;
    margin-top: 0.14rem;
    overflow-wrap: anywhere;
}
.player-quick-view-context-section,
.player-quick-view-stat-section {
    background: rgba(229, 231, 235, 0.035);
    border: 1px solid rgba(229, 231, 235, 0.09);
    border-radius: 2px;
    margin: 0.42rem 0;
    overflow: hidden;
}
.player-quick-view-stat-heading {
    background: rgba(229, 231, 235, 0.05);
    border-bottom: 1px solid rgba(229, 231, 235, 0.08);
    border-left: 3px solid var(--dg-theme-accent-cyan);
    color: rgba(248, 250, 252, 0.72);
    font-size: 0.64rem;
    font-weight: 900;
    letter-spacing: 0.05em;
    line-height: 1.15;
    padding: 0.34rem 0.48rem;
    text-transform: uppercase;
}
.player-quick-view-stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(112px, 1fr));
}
.player-quick-view-stat-row {
    align-items: start;
    border-bottom: 1px solid rgba(229, 231, 235, 0.07);
    display: grid;
    gap: 0.12rem;
    grid-template-columns: 1fr;
    min-width: 0;
    padding: 0.34rem 0.44rem;
}
.player-quick-view-stat-row:nth-last-child(-n + 2) {
    border-bottom: 0;
}
.player-quick-view-stat-label {
    color: rgba(248, 250, 252, 0.5);
    font-size: 0.58rem;
    font-weight: 900;
    letter-spacing: 0.04em;
    line-height: 1.15;
    text-transform: uppercase;
}
.player-quick-view-stat-copy {
    min-width: 0;
}
.player-quick-view-stat-value {
    color: #ffffff;
    font-size: 0.9rem;
    font-weight: 940;
    line-height: 1.12;
    overflow-wrap: anywhere;
}
.player-quick-view-stat-note {
    color: rgba(248, 250, 252, 0.56);
    font-size: 0.64rem;
    line-height: 1.18;
    margin-top: 0.08rem;
    overflow-wrap: anywhere;
}
.player-quick-view-actions-label {
    border-left: 3px solid var(--dg-theme-accent-cyan);
    color: rgba(248, 250, 252, 0.72) !important;
    font-size: 0.68rem !important;
    font-weight: 900 !important;
    letter-spacing: 0.05em !important;
    margin: 0.7rem 0 0.34rem !important;
    padding-left: 0.5rem;
    text-transform: uppercase;
}
div[data-testid="stDialog"] .stButton > button {
    background: rgba(229, 231, 235, 0.08) !important;
    border: 1px solid rgba(229, 231, 235, 0.14) !important;
    border-left: 3px solid var(--dg-theme-accent-cyan) !important;
    border-radius: 2px !important;
    color: #f8fafc !important;
    font-weight: 850 !important;
}
div[data-testid="stDialog"] .stButton > button:hover {
    background: rgba(34, 211, 238, 0.12) !important;
    border-color: rgba(34, 211, 238, 0.28) !important;
}

@media (max-width: 900px) {
    div[data-testid="stDialog"] div[role="dialog"] {
        max-width: calc(100vw - 0.4rem) !important;
        width: calc(100vw - 0.4rem) !important;
    }
    .player-quick-view-header-band.player-quick-view-hero {
        grid-template-columns: 68px minmax(0, 1fr) !important;
        padding: 0.66rem 0.64rem !important;
    }
    .player-quick-view-avatar {
        --avatar-size: 68px;
    }
    .player-quick-view-name {
        font-size: 1rem !important;
    }
    .player-quick-view-panel-body {
        padding: 0.6rem 0.64rem 0.72rem;
    }
    .player-quick-view-detail-row {
        gap: 0.42rem;
        grid-template-columns: minmax(4.7rem, 0.34fr) minmax(0, 1fr);
        padding: 0.5rem 0.52rem;
    }
}
:root {
    --dg-smoke-dark: rgba(7, 8, 11, 0.72);
    --dg-smoke-mid: rgba(24, 25, 29, 0.54);
    --dg-smoke-ash: rgba(229, 231, 235, 0.075);
    --dg-smoke-border: rgba(229, 231, 235, 0.13);
    --dg-smoke-border-strong: rgba(248, 250, 252, 0.2);
    --dg-smoke-light-ready: rgba(238, 238, 235, 0.62);
    --dg-smoke-light-border-ready: rgba(32, 32, 34, 0.14);
}
.home-command-card,
.team-identity-card,
.summary-tile,
.analysis-card,
.decision-panel,
.trade-idea-card,
.trade-card,
.free-agent-card,
.free-agent-summary-card,
.draft-review-pick-card,
.roster-limit-strip,
.roster-limit-stat,
.platform-sidebar-card {
    backdrop-filter: blur(18px) saturate(112%) !important;
    background:
        linear-gradient(180deg, var(--dg-smoke-mid), var(--dg-smoke-dark)) !important;
    border-color: var(--dg-smoke-border) !important;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.035),
        0 18px 44px rgba(0, 0, 0, 0.24) !important;
}
.app-degraded-state {
    background:
        linear-gradient(180deg, rgba(229, 231, 235, 0.055), rgba(5, 6, 9, 0.68)) !important;
    border-color: rgba(229, 231, 235, 0.1) !important;
}
.player-avatar img,
.player-detail-avatar img,
.player-quick-view-avatar img,
.scan-card-avatar img,
.compact-player-avatar img,
.free-agent-avatar img,
.trade-asset-avatar img {
    display: block !important;
    height: 100% !important;
    inset: 0 !important;
    max-height: none !important;
    max-width: none !important;
    object-fit: cover !important;
    object-position: center center !important;
    position: absolute !important;
    width: 100% !important;
}
.player-avatar,
.player-detail-avatar,
.player-quick-view-avatar,
.scan-card-avatar,
.compact-player-avatar,
.free-agent-avatar,
.trade-asset-avatar {
    align-items: center !important;
    display: flex !important;
    justify-content: center !important;
    overflow: hidden !important;
}
.mobile-gm-destination-panel {
    background:
        linear-gradient(180deg, rgba(229, 231, 235, 0.07), rgba(4, 5, 8, 0.86)) !important;
    border: 1px solid var(--dg-smoke-border) !important;
    border-left: 3px solid var(--dg-theme-accent-cyan) !important;
    border-radius: 0 2px 2px 0 !important;
    box-shadow: none !important;
    margin: 0 0 0.35rem !important;
    padding: 0.54rem 0.58rem !important;
}
.mobile-gm-panel-header {
    display: grid;
    gap: 0.1rem;
}
.mobile-gm-current-page {
    color: rgba(248, 250, 252, 0.58);
    font-size: 0.68rem;
    font-weight: 760;
    line-height: 1.2;
}

@media (max-width: 900px) {
    div[data-testid="stPopoverContent"] {
        backdrop-filter: blur(20px) saturate(112%) !important;
        background:
            linear-gradient(180deg, rgba(16, 17, 21, 0.94), rgba(3, 4, 6, 0.96)) !important;
        border: 1px solid var(--dg-smoke-border) !important;
        border-left: 0 !important;
        border-radius: 0 2px 2px 0 !important;
        box-shadow: none !important;
        margin-left: 0 !important;
        max-width: min(82vw, 286px) !important;
        min-width: min(82vw, 286px) !important;
        padding: 0.45rem !important;
        transform: translateX(calc(-1 * env(safe-area-inset-left, 0px))) !important;
    }
    div[data-testid="stPopoverContent"] [data-testid="stButton"] {
        margin: 0 !important;
    }
    div[data-testid="stPopoverContent"] [data-testid="stVerticalBlock"],
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) {
        gap: 2px !important;
    }
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button {
        align-items: center !important;
        background: rgba(229, 231, 235, 0.045) !important;
        border: 0 !important;
        border-bottom: 1px solid rgba(229, 231, 235, 0.08) !important;
        border-left: 3px solid transparent !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        color: rgba(248, 250, 252, 0.68) !important;
        display: flex !important;
        font-size: 0.76rem !important;
        font-weight: 840 !important;
        justify-content: flex-start !important;
        letter-spacing: 0 !important;
        min-height: 34px !important;
        padding: 0.34rem 0.48rem !important;
        text-align: left !important;
        text-transform: none !important;
        white-space: normal !important;
    }
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button[kind="primary"],
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button[kind="primary"] {
        background:
            linear-gradient(90deg, rgba(34, 211, 238, 0.18), rgba(229, 231, 235, 0.06)) !important;
        border-left-color: var(--dg-theme-accent-cyan) !important;
        color: #ffffff !important;
    }
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button:hover,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button:hover {
        background: rgba(229, 231, 235, 0.085) !important;
        color: #ffffff !important;
    }
    .mobile-gm-sheet-kicker {
        color: var(--dg-theme-accent-cyan) !important;
        font-size: 0.6rem !important;
        letter-spacing: 0.08em !important;
    }
    .mobile-gm-sheet-title {
        color: #ffffff !important;
        font-size: 0.84rem !important;
        line-height: 1.05 !important;
        margin-top: 0 !important;
    }
    .mobile-gm-sheet-note {
        color: rgba(248, 250, 252, 0.52) !important;
        font-size: 0.68rem !important;
        line-height: 1.22 !important;
        margin: 0.24rem 0 0 !important;
    }
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) {
        backdrop-filter: blur(20px) saturate(112%) !important;
        background:
            linear-gradient(180deg, rgba(16, 17, 21, 0.94), rgba(3, 4, 6, 0.96)) !important;
        border: 1px solid var(--dg-smoke-border) !important;
        border-left: 0 !important;
        border-radius: 0 2px 2px 0 !important;
        box-shadow: none !important;
        left: max(env(safe-area-inset-left, 0px), 0px) !important;
        max-width: min(84vw, 310px) !important;
        padding: 0.48rem !important;
    }
}
:root {
    --dg-player-image-position: center 18%;
}
.player-avatar img,
.player-detail-avatar img,
.player-quick-view-avatar img,
.scan-card-avatar img,
.compact-player-avatar img,
.free-agent-avatar img,
.trade-asset-avatar img {
    object-fit: cover !important;
    object-position: var(--dg-player-image-position) !important;
}
.team-logo-wrap img,
.league-team-avatar img,
.team-card-avatar img {
    object-fit: cover !important;
    object-position: center center !important;
}
.player-avatar,
.player-detail-avatar,
.player-quick-view-avatar,
.scan-card-avatar,
.compact-player-avatar,
.free-agent-avatar,
.trade-asset-avatar,
.team-logo-wrap,
.league-team-avatar,
.team-card-avatar {
    place-items: center !important;
}

@media (max-width: 900px) {
    .home-command-kicker,
    .home-command-team,
    .home-command-meta,
    .team-section-title,
    .trade-card-title,
    .free-agent-summary-label,
    .draft-review-round-title,
    .player-detail-name,
    .player-detail-meta,
    .player-quick-view-name,
    .player-quick-view-meta,
    .player-quick-view-detail-label,
    .player-quick-view-detail-value,
    .player-quick-view-detail-note {
        text-align: left !important;
    }
    .home-command-shell,
    .home-command-hero,
    .home-command-card,
    .team-identity-card,
    .summary-tile,
    .analysis-card,
    .decision-panel,
    .trade-idea-card,
    .trade-card,
    .free-agent-card,
    .free-agent-summary-card,
    .draft-review-pick-card,
    .player-detail-shell,
    .dg-quick-view-panel.player-quick-view-shell {
        margin-left: 0 !important;
        margin-right: 0 !important;
        text-align: left !important;
    }
    .home-command-route-card,
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button {
        justify-content: flex-start !important;
        text-align: left !important;
    }
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button p,
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button span,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button p,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button span {
        display: block !important;
        text-align: left !important;
        width: 100% !important;
    }
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button::after,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button::after {
        color: rgba(248, 250, 252, 0.42);
        content: "›";
        font-size: 1rem;
        font-weight: 700;
        margin-left: auto;
        padding-left: 0.5rem;
    }
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button[kind="primary"]::after,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button[kind="primary"]::after {
        color: var(--dg-theme-accent-cyan);
        content: "▌";
        font-size: 0.85rem;
    }
    .player-quick-view-header-band.player-quick-view-hero,
    .player-detail-hero {
        align-items: start !important;
    }
    .player-detail-chip-row,
    .player-detail-score-row {
        justify-content: flex-start !important;
    }
    .player-quick-view-panel-body {
        gap: 0.44rem !important;
    }
    .player-quick-view-detail-row {
        align-items: start !important;
        min-height: 0 !important;
    }
    .home-command-card,
    .team-identity-card,
    .summary-tile,
    .analysis-card,
    .decision-panel,
    .trade-idea-card,
    .trade-card,
    .free-agent-card,
    .free-agent-summary-card,
    .draft-review-pick-card,
    .player-detail-shell,
    .dg-quick-view-panel.player-quick-view-shell {
        background:
            linear-gradient(180deg, rgba(229, 231, 235, 0.06), rgba(4, 5, 8, 0.78)) !important;
        border-color: rgba(229, 231, 235, 0.11) !important;
        border-radius: 2px !important;
    }
}
.dg-section-command,
.dg-section-alert,
.dg-section-primary-action,
.dg-section-opportunity-list,
.dg-section-metrics,
.dg-section-secondary,
.dg-ranked-row {
    border-radius: var(--radius-panel);
}

@media (max-width: 900px) {
    .section-header {
        background: transparent !important;
        border-left: 3px solid rgba(229, 231, 235, 0.18);
        margin: 1.08rem 0 0.34rem !important;
        padding: 0.1rem 0 0.1rem 0.58rem !important;
    }
    .section-header-compact {
        margin-top: 0.58rem !important;
    }
    .section-kicker {
        color: rgba(248, 250, 252, 0.46) !important;
        font-size: 0.6rem !important;
        font-weight: 900 !important;
        letter-spacing: 0.08em !important;
        line-height: 1.05 !important;
        text-transform: uppercase !important;
    }
    .section-title {
        color: #ffffff !important;
        font-size: 0.92rem !important;
        font-weight: 920 !important;
        line-height: 1.08 !important;
        margin-top: 0.08rem !important;
        text-align: left !important;
    }
    .section-note {
        color: rgba(248, 250, 252, 0.58) !important;
        font-size: 0.72rem !important;
        line-height: 1.28 !important;
        margin-top: 0.16rem !important;
        max-width: 48rem;
        text-align: left !important;
    }
    .home-command-shell,
    .home-command-hero,
    .team-identity-card {
        border-left: 4px solid rgba(248, 250, 252, 0.44) !important;
        margin-bottom: 0.92rem !important;
    }
    .home-command-hero {
        padding: 0.64rem 0.66rem !important;
    }
    .home-command-kicker,
    .team-kicker {
        color: rgba(248, 250, 252, 0.52) !important;
        font-size: 0.62rem !important;
        letter-spacing: 0.08em !important;
    }
    .home-command-grid,
    .decision-panel-grid,
    .decision-panel-grid-alert,
    .free-agent-summary-grid,
    .free-agent-list,
    .draft-review-round-grid,
    .trade-card-focus-row,
    .summary-tile-grid {
        gap: 3px !important;
        margin-top: 0.38rem !important;
        margin-bottom: 0.82rem !important;
    }
    .dg-section-alert,
    .home-command-card-risk,
    .roster-limit-strip,
    .roster-limit-stat-danger,
    .summary-tile-risk,
    .analysis-card-risk,
    .decision-panel-risk {
        background:
            linear-gradient(90deg, rgba(245, 158, 11, 0.12), rgba(5, 6, 9, 0.86) 40%) !important;
        border-left: 4px solid rgba(245, 158, 11, 0.78) !important;
        color: #fff7ed !important;
    }
    .dg-section-primary-action,
    .home-command-card-wide,
    .decision-panel-grid-alert .decision-panel:first-child {
        background:
            linear-gradient(90deg, rgba(34, 211, 238, 0.18), rgba(248, 250, 252, 0.07) 38%, rgba(5, 6, 9, 0.82)) !important;
        border-left: 5px solid var(--dg-theme-accent-cyan) !important;
    }
    .dg-section-opportunity-list,
    .home-command-card-trade,
    .home-command-card-waiver,
    .trade-idea-positive,
    .free-agent-card-tone-core,
    .free-agent-card-tone-rise,
    .free-agent-summary-card {
        background:
            linear-gradient(90deg, rgba(34, 197, 94, 0.12), rgba(5, 6, 9, 0.78) 36%) !important;
        border-left: 4px solid var(--dg-theme-opportunity) !important;
    }
    .dg-section-metrics,
    .summary-tile,
    .roster-limit-stat {
        background:
            linear-gradient(180deg, rgba(229, 231, 235, 0.045), rgba(4, 5, 8, 0.66)) !important;
        border-left: 2px solid rgba(229, 231, 235, 0.12) !important;
        padding: 0.42rem 0.5rem !important;
    }
    .summary-tile-grid,
    .roster-limit-strip {
        display: grid !important;
        gap: 2px !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }
    .roster-limit-strip {
        margin: 0.42rem 0 0.72rem !important;
    }
    .summary-tile-label,
    .roster-limit-stat span-label {
        color: rgba(248, 250, 252, 0.5) !important;
        font-size: 0.58rem !important;
        letter-spacing: 0.07em !important;
        line-height: 1.08 !important;
        text-transform: uppercase !important;
    }
    .summary-tile-value,
    .roster-limit-stat strong-value {
        color: #ffffff !important;
        font-size: 0.86rem !important;
        line-height: 1.08 !important;
        margin-top: 0.1rem !important;
    }
    .summary-tile-note,
    .roster-limit-stat small-note {
        color: rgba(248, 250, 252, 0.54) !important;
        font-size: 0.66rem !important;
        line-height: 1.2 !important;
        margin-top: 0.12rem !important;
    }
    .dg-section-secondary,
    .decision-panel-reference,
    .trade-idea-secondary,
    .draft-review-chip.unmatched {
        background:
            linear-gradient(180deg, rgba(229, 231, 235, 0.035), rgba(4, 5, 8, 0.56)) !important;
        border-left: 2px solid rgba(229, 231, 235, 0.1) !important;
        opacity: 0.94;
    }
    .app-degraded-state,
    .home-command-card-draft,
    .home-command-route-card,
    .decision-panel-reference,
    .draft-review-chip.unmatched {
        background:
            linear-gradient(90deg, rgba(139, 147, 255, 0.09), rgba(4, 5, 8, 0.7) 38%) !important;
        border-left-color: var(--dg-theme-diagnostic) !important;
    }
    .decision-panel {
        margin-bottom: 0 !important;
    }
    .decision-panel-top,
    .home-command-card-top,
    .free-agent-top,
    .trade-card-header,
    .draft-review-pick-top {
        align-items: flex-start !important;
        gap: 0.38rem !important;
    }
    .decision-panel-title,
    .home-command-card-value,
    .free-agent-name,
    .trade-card-title,
    .draft-review-player-name {
        font-size: 0.88rem !important;
        line-height: 1.12 !important;
    }
    .decision-panel-body,
    .scan-card-list,
    .free-agent-list {
        gap: 2px !important;
        margin-top: 0.36rem !important;
    }
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button {
        background:
            linear-gradient(90deg, rgba(229, 231, 235, 0.06), rgba(4, 5, 8, 0.74)) !important;
        border-bottom: 1px solid rgba(229, 231, 235, 0.08) !important;
        min-height: 32px !important;
    }
    .dg-ranked-row {
        background: var(--surface-1) !important;
        border-inline-start: var(--border-width-semantic) solid var(--border-standard) !important;
        border-radius: var(--radius-panel) !important;
        margin-bottom: var(--space-2xs) !important;
    }
    .dg-ranked-row--top {
        border-inline-start-color: var(--color-accent) !important;
    }
    .dg-ranked-row--current {
        border-inline-start-color: var(--color-accent) !important;
    }
    .dg-ranked-rank {
        background: var(--surface-raised) !important;
        border-radius: var(--radius-control) !important;
        min-height: 2rem;
    }
}
/* #231: legacy GM height:0 / width:auto removed — MOBILE_INTERACTION_OVERLAY_CSS owns the 44px orb.
 * Those rules leaked "Open GM menu" as clipped "O / PE" when height collapsed.
 */
.dg-preset-command,
.dg-preset-alert,
.dg-preset-primary-action,
.dg-preset-opportunity,
.dg-preset-player-list,
.dg-preset-metrics,
.dg-preset-secondary {
    border-radius: 2px;
}

@media (max-width: 900px) {
    .dg-preset-command,
    .home-command-shell,
    .home-command-hero,
    .team-identity-card {
        background:
            linear-gradient(90deg, rgba(248, 250, 252, 0.085), rgba(7, 8, 12, 0.86) 34%) !important;
        border-left: 4px solid rgba(248, 250, 252, 0.64) !important;
        padding-block: 0.64rem !important;
    }
    .dg-preset-command .section-title,
    .home-command-title,
    .team-name {
        letter-spacing: 0.01em !important;
    }
    .dg-preset-alert,
    .dg-alert-warning,
    .home-command-card-risk,
    .roster-limit-strip {
        background:
            linear-gradient(90deg, rgba(245, 158, 11, 0.13), rgba(6, 7, 10, 0.9) 30%) !important;
        border-left: 4px solid rgba(245, 158, 11, 0.86) !important;
    }
    .dg-preset-primary-action,
    .home-command-card-wide,
    .decision-panel-grid-alert .decision-panel:first-child {
        background:
            linear-gradient(90deg, rgba(34, 211, 238, 0.16), rgba(248, 250, 252, 0.075) 34%, rgba(5, 6, 9, 0.84)) !important;
        border-left: 5px solid rgba(103, 232, 249, 0.88) !important;
        padding-block: 0.62rem !important;
    }
    .dg-preset-opportunity,
    .home-command-card-trade,
    .home-command-card-waiver,
    .trade-idea-positive,
    .free-agent-card-tone-core,
    .free-agent-card-tone-rise {
        background:
            linear-gradient(90deg, rgba(20, 184, 166, 0.115), rgba(5, 6, 9, 0.83) 32%) !important;
        border-left: 3px solid rgba(45, 212, 191, 0.74) !important;
    }
    .dg-preset-player-list,
    .decision-panel,
    .free-agent-list,
    .scan-card-list,
    .draft-review-round-grid {
        background: rgba(229, 231, 235, 0.018) !important;
        border-left: 1px solid rgba(229, 231, 235, 0.08) !important;
        gap: 2px !important;
    }
    .decision-panel:not(:first-child),
    .free-agent-card-tone-hold,
    .free-agent-card-tone-neutral,
    .draft-review-pick-card {
        background:
            linear-gradient(180deg, rgba(229, 231, 235, 0.035), rgba(4, 5, 8, 0.58)) !important;
    }
    .dg-preset-metrics,
    .summary-tile,
    .roster-limit-stat {
        background: rgba(229, 231, 235, 0.038) !important;
        border-left: 2px solid rgba(229, 231, 235, 0.15) !important;
        padding: 0.36rem 0.44rem !important;
    }
    .summary-tile-grid {
        gap: 2px !important;
    }
    .summary-tile-grid-compact .summary-tile-power {
        background:
            linear-gradient(90deg, rgba(34, 211, 238, 0.11), rgba(229, 231, 235, 0.04) 34%, rgba(4, 5, 8, 0.72)) !important;
        border-left-color: rgba(103, 232, 249, 0.8) !important;
    }
    .dg-preset-secondary,
    .decision-panel-reference,
    .trade-idea-secondary,
    .app-degraded-state,
    .draft-review-chip.unmatched {
        background: rgba(229, 231, 235, 0.028) !important;
        border-left: 2px solid rgba(229, 231, 235, 0.1) !important;
        color: rgba(248, 250, 252, 0.7) !important;
        opacity: 0.92;
    }
    .home-command-card-risk .home-command-card-label,
    .dg-alert-kicker {
        color: #fbbf24 !important;
    }
    .home-command-card-trade .home-command-card-label,
    .home-command-card-waiver .home-command-card-label {
        color: #99f6e4 !important;
    }
}
.premium-badge {
    align-items: center;
    background: rgba(250, 204, 21, 0.12);
    border: 1px solid rgba(250, 204, 21, 0.3);
    border-radius: 2px;
    color: #fde68a;
    display: inline-flex;
    font-size: 0.62rem;
    font-weight: 900;
    letter-spacing: 0.08em;
    line-height: 1;
    padding: 0.22rem 0.38rem;
    text-transform: uppercase;
}
.premium-lock {
    background:
        linear-gradient(90deg, rgba(250, 204, 21, 0.08), rgba(5, 6, 9, 0.82) 34%) !important;
    border: 1px solid rgba(229, 231, 235, 0.1);
    border-left: 3px solid rgba(250, 204, 21, 0.62);
    border-radius: 2px;
    color: rgba(248, 250, 252, 0.82);
    margin: 0.52rem 0 0.72rem;
    padding: 0.62rem 0.68rem;
}
.premium-lock-top {
    align-items: center;
    display: flex;
    gap: 0.42rem;
    justify-content: space-between;
    margin-bottom: 0.36rem;
}
.premium-lock-cta {
    color: rgba(248, 250, 252, 0.58);
    font-size: 0.62rem;
    font-weight: 850;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.premium-lock-title {
    color: #ffffff;
    font-size: 0.88rem;
    font-weight: 900;
    line-height: 1.12;
}
.premium-lock-body {
    color: rgba(248, 250, 252, 0.64);
    font-size: 0.72rem;
    line-height: 1.28;
    margin-top: 0.18rem;
}
.premium-lock-included {
    color: rgba(248, 250, 252, 0.48);
    font-size: 0.62rem;
    font-weight: 750;
    letter-spacing: 0.04em;
    margin-top: 0.36rem;
    text-transform: uppercase;
}
.trade-hub-locked-preview {
    display: grid;
    gap: 0.28rem;
    margin: 0.2rem 0 0.45rem;
    max-width: 100%;
    overflow-x: hidden;
}
.trade-hub-locked-label {
    color: var(--color-text-muted, #a8adb7);
    font-size: 0.72rem;
    font-weight: 700;
    margin: 0;
}
.trade-hub-locked-row {
    display: grid;
    gap: 0.35rem;
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) 3.5rem;
    min-height: 0.7rem;
    opacity: 0.35;
}
.trade-hub-locked-row > span {
    background: var(--color-surface-raised, #1b1e23);
    border: 1px solid var(--color-border, #2a2e35);
    min-height: 0.55rem;
}
@media (max-width: 430px) {
    .trade-hub-locked-preview { margin-bottom: 0.3rem; }
    .premium-lock { margin: 0.35rem 0 0.5rem; padding: 0.5rem 0.55rem; }
}
.premium-page {
    display: grid;
    gap: 0.84rem;
    margin-top: 0.36rem;
}
.premium-page-header,
.premium-status-panel,
.premium-plan-slab,
.premium-billing-note {
    background:
        linear-gradient(135deg, rgba(248, 250, 252, 0.055), rgba(5, 6, 9, 0.82)),
        rgba(10, 12, 16, 0.72) !important;
    border: 1px solid rgba(229, 231, 235, 0.11);
    border-radius: 2px;
    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.28);
    padding: 0.78rem 0.82rem;
}
.premium-page-header {
    border-left: 3px solid rgba(34, 211, 238, 0.68);
}
.premium-page-kicker,
.premium-status-label,
.premium-plan-label,
.premium-billing-note-title {
    color: rgba(248, 250, 252, 0.55);
    font-size: 0.62rem;
    font-weight: 900;
    letter-spacing: 0.08em;
    line-height: 1;
    text-transform: uppercase;
}
.premium-page-title {
    color: #ffffff;
    font-size: 1.42rem;
    font-weight: 950;
    letter-spacing: 0;
    line-height: 1.02;
    margin-top: 0.34rem;
}
.premium-page-subtitle,
.premium-billing-note-body {
    color: rgba(248, 250, 252, 0.68);
    font-size: 0.78rem;
    line-height: 1.35;
    margin-top: 0.3rem;
}
.premium-status-panel {
    align-items: center;
    display: flex;
    justify-content: space-between;
}
.premium-status-value {
    border-radius: 2px;
    font-size: 0.72rem;
    font-weight: 900;
    letter-spacing: 0.06em;
    padding: 0.26rem 0.44rem;
    text-transform: uppercase;
}
.premium-status-free {
    background: rgba(148, 163, 184, 0.1);
    border: 1px solid rgba(148, 163, 184, 0.2);
    color: rgba(226, 232, 240, 0.78);
}
.premium-status-premium {
    background: rgba(34, 211, 238, 0.12);
    border: 1px solid rgba(34, 211, 238, 0.36);
    color: var(--color-accent);
}
.premium-plan-grid {
    display: grid;
    gap: 0.72rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
}
.premium-plan-premium {
    border-left: 3px solid rgba(34, 211, 238, 0.68);
}
.premium-plan-free {
    border-left: 3px solid rgba(148, 163, 184, 0.34);
}
.premium-plan-row {
    border-top: 1px solid rgba(229, 231, 235, 0.08);
    padding: 0.54rem 0 0.5rem;
}
.premium-plan-label + .premium-plan-row {
    margin-top: 0.44rem;
}
.premium-plan-row-title {
    color: rgba(248, 250, 252, 0.92);
    font-size: 0.82rem;
    font-weight: 900;
    line-height: 1.14;
}
.premium-plan-row-body {
    color: rgba(248, 250, 252, 0.62);
    font-size: 0.72rem;
    line-height: 1.28;
    margin-top: 0.16rem;
}
.premium-plan-row-premium .premium-plan-row-title {
    color: var(--color-accent);
}
.premium-billing-note {
    border-left: 3px solid rgba(168, 85, 247, 0.44);
}
.premium-dev-note code {
    background: rgba(248, 250, 252, 0.08);
    border: 1px solid rgba(248, 250, 252, 0.12);
    border-radius: 2px;
    color: #f8fafc;
    padding: 0.06rem 0.18rem;
}

@media (max-width: 760px) {
    .premium-plan-grid {
        grid-template-columns: 1fr;
    }
    .premium-page-header,
    .premium-status-panel,
    .premium-plan-slab,
    .premium-billing-note {
        padding: 0.68rem 0.72rem;
    }
}
.sr-only {
    height: 1px !important;
    margin: -1px !important;
    overflow: hidden !important;
    padding: 0 !important;
    position: absolute !important;
    width: 1px !important;
}
.dg-semantic-icon {
    align-items: center;
    background: transparent;
    border: 0;
    border-radius: 0;
    color: rgba(248, 250, 252, 0.72);
    display: inline-flex;
    flex: 0 0 auto;
    font-size: 0.68rem;
    font-weight: 900;
    height: auto;
    justify-content: center;
    line-height: 1;
    margin-right: 0.28rem;
    min-width: 0;
    padding: 0;
    text-transform: uppercase;
    vertical-align: 0.02rem;
}
.section-kicker .dg-semantic-icon,
.home-command-card-label .dg-semantic-icon,
.summary-tile-label .dg-semantic-icon,
.analysis-card-label .dg-semantic-icon,
.decision-panel-label .dg-semantic-icon,
.home-hero-stat-label .dg-semantic-icon,
.roster-limit-stat .dg-semantic-icon,
h3 .dg-semantic-icon {
    margin-right: 0.36rem;
}
.dg-alert-warning .dg-semantic-icon,
.home-command-card-risk .dg-semantic-icon,
.summary-tile-risk .dg-semantic-icon,
.decision-panel-risk .dg-semantic-icon,
.roster-limit-stat-danger .dg-semantic-icon {
    background: transparent;
    border-color: transparent;
    color: #fbbf24;
}
.home-command-card-need .dg-semantic-icon,
.summary-tile-weakness .dg-semantic-icon,
.analysis-card-weakness .dg-semantic-icon,
.roster-limit-stat-warning .dg-semantic-icon {
    background: transparent;
    border-color: transparent;
    color: #fed7aa;
}
.home-command-card-trade .dg-semantic-icon,
.home-command-card-waiver .dg-semantic-icon,
.trade-idea-positive .dg-semantic-icon,
.free-agent-card-tone-core .dg-semantic-icon,
.free-agent-card-tone-rise .dg-semantic-icon,
.summary-tile-opportunity .dg-semantic-icon,
.decision-panel-strength .dg-semantic-icon {
    background: transparent;
    border-color: transparent;
    color: #bbf7d0;
}
.home-command-card-draft .dg-semantic-icon,
.draft-review-pick-card .dg-semantic-icon,
.app-degraded-state .dg-semantic-icon,
.draft-review-chip.unmatched .dg-semantic-icon {
    background: transparent;
    border-color: transparent;
    color: #c7d2fe;
}

@media (max-width: 900px) {
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button {
        gap: 0.42rem !important;
    }
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button p,
    div[data-testid="stPopoverContent"] [data-testid="stButton"] > button span,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button p,
    div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker) [data-testid="stButton"] > button span {
        align-items: center !important;
        display: flex !important;
        gap: 0.42rem !important;
    }
    .dg-semantic-icon {
        height: auto;
        min-width: 0;
    }
    .roster-limit-strip {
        display: grid !important;
        gap: 0.3rem !important;
        grid-template-columns: 1fr !important;
    }
    .roster-limit-stat {
        align-items: start !important;
        border-radius: 2px !important;
        display: grid !important;
        gap: 0.16rem 0.56rem !important;
        grid-template-columns: minmax(4.6rem, 0.36fr) minmax(0, 1fr) !important;
        padding: 0.38rem 0.44rem !important;
    }
    .roster-limit-stat span {
        grid-column: 1 !important;
        line-height: 1.1 !important;
    }
    .roster-limit-stat strong {
        grid-column: 2 !important;
        margin-top: 0 !important;
    }
    .roster-limit-stat small {
        display: block !important;
        grid-column: 2 !important;
        line-height: 1.18 !important;
        margin-top: 0 !important;
        overflow: visible !important;
        -webkit-line-clamp: unset !important;
    }
}
/* Compact 2K player detail panels: modal-only stat table treatment. */
.player-detail-panel,
.player-detail-header,
.player-detail-identity,
.player-detail-row,
.player-detail-stat-table,
.player-detail-section {
    border-radius: 2px;
}
div[data-testid="stDialog"] div[role="dialog"] {
    padding: 0.44rem !important;
}
div[data-testid="stDialog"] .dg-quick-view-panel.player-quick-view-shell,
div[data-testid="stDialog"] .player-detail-shell {
    background:
        linear-gradient(180deg, rgba(16, 17, 21, 0.92), rgba(3, 4, 6, 0.96)) !important;
    border: 1px solid rgba(229, 231, 235, 0.13) !important;
    border-radius: 2px !important;
    box-shadow: none !important;
}
div[data-testid="stDialog"] .player-quick-view-header-band.player-quick-view-hero,
div[data-testid="stDialog"] .player-detail-hero {
    background:
        linear-gradient(90deg, rgba(34, 211, 238, 0.15), rgba(229, 231, 235, 0.055) 30%, rgba(3, 4, 6, 0.94)) !important;
    border-bottom: 1px solid rgba(229, 231, 235, 0.12) !important;
    border-left: 4px solid var(--dg-theme-accent-cyan) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    gap: 0.62rem !important;
    min-height: 0 !important;
    padding: 0.58rem 0.62rem !important;
}
div[data-testid="stDialog"] .player-detail-avatar,
div[data-testid="stDialog"] .player-quick-view-avatar {
    --avatar-size: 64px !important;
    align-self: start !important;
    border-radius: 2px !important;
    display: flex !important;
    flex: 0 0 var(--avatar-size) !important;
    height: var(--avatar-size) !important;
    justify-content: center !important;
    max-height: var(--avatar-size) !important;
    max-width: var(--avatar-size) !important;
    min-height: var(--avatar-size) !important;
    min-width: var(--avatar-size) !important;
    overflow: hidden !important;
    position: relative !important;
    width: var(--avatar-size) !important;
}
div[data-testid="stDialog"] .player-detail-avatar img,
div[data-testid="stDialog"] .player-quick-view-avatar img {
    height: 100% !important;
    inset: 0 !important;
    max-height: 100% !important;
    max-width: 100% !important;
    object-fit: cover !important;
    object-position: center var(--dg-headshot-focus, 18%) !important;
    position: absolute !important;
    width: 100% !important;
}
.league-switch-row {
    align-items: center;
    background: rgba(229, 231, 235, 0.045);
    border: 1px solid rgba(226, 232, 240, 0.12);
    border-left: 3px solid rgba(226, 232, 240, 0.18);
    border-radius: 2px;
    display: grid;
    gap: 0.5rem;
    grid-template-columns: minmax(0, 1fr) auto;
    margin: 0.34rem 0 0.22rem;
    padding: 0.44rem 0.5rem;
}
.league-switch-row-current {
    background: rgba(34, 211, 238, 0.08);
    border-color: rgba(34, 211, 238, 0.24);
    border-left-color: var(--dg-theme-accent-cyan);
}
.league-switch-row-copy {
    min-width: 0;
}
.league-switch-row-title {
    color: #f8fafc;
    font-size: 0.78rem;
    font-weight: 880;
    line-height: 1.12;
    overflow-wrap: anywhere;
}
.league-switch-row-meta {
    color: rgba(248, 250, 252, 0.58);
    font-size: 0.66rem;
    line-height: 1.18;
    margin-top: 0.12rem;
}
.league-switch-row-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem;
    justify-content: flex-end;
}
.league-switch-current-badge,
.league-switch-default-badge {
    border: 1px solid rgba(226, 232, 240, 0.16);
    border-radius: 2px;
    color: rgba(248, 250, 252, 0.78);
    font-size: 0.56rem;
    font-weight: 900;
    letter-spacing: 0.04em;
    line-height: 1;
    padding: 0.18rem 0.25rem;
    text-transform: uppercase;
}
.league-switch-current-badge {
    background: rgba(34, 211, 238, 0.14);
    border-color: rgba(34, 211, 238, 0.28);
    color: var(--color-accent);
}
.league-switch-default-badge {
    background: rgba(226, 232, 240, 0.08);
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker),
div[class*="st-key-mobile_gm_sheet_trigger_"] {
    bottom: max(16px, env(safe-area-inset-bottom)) !important;
    left: max(16px, env(safe-area-inset-left)) !important;
    right: auto !important;
    z-index: 1001000 !important;
}
div[class*="st-key-"][class*="_global_feedback_control"] {
    bottom: max(16px, env(safe-area-inset-bottom)) !important;
    left: auto !important;
    margin: 0 !important;
    max-width: max-content !important;
    min-width: 0 !important;
    overflow: visible !important;
    padding: 0 !important;
    pointer-events: none !important;
    position: fixed !important;
    right: max(16px, env(safe-area-inset-right)) !important;
    width: max-content !important;
    z-index: 1000990 !important;
}
div[class*="st-key-"][class*="_global_feedback_control"] div[data-testid="stPopover"] {
    pointer-events: auto !important;
    width: max-content !important;
}
div[class*="st-key-"][class*="_global_feedback_control"] [data-testid="stPopover"] > button {
    max-width: min(34vw, 118px) !important;
    min-width: 0 !important;
    padding: 0.38rem 0.58rem !important;
    pointer-events: auto !important;
    white-space: nowrap !important;
}
div[class*="st-key-"][class*="_global_feedback_control"] div[data-testid="stPopoverContent"] {
    max-width: min(82vw, 320px) !important;
}

@media (max-width: 900px) {
    div[class*="st-key-"][class*="_global_feedback_control"] {
        bottom: max(16px, env(safe-area-inset-bottom)) !important;
        right: max(16px, env(safe-area-inset-right)) !important;
    }
    div[class*="st-key-"][class*="_global_feedback_control"] [data-testid="stPopover"] > button {
        max-width: 104px !important;
        min-height: 34px !important;
    }
}

@media (max-width: 900px) {
    div[class*="st-key-"][class*="_global_feedback_control"] [data-testid="stPopover"] > button {
        font-size: 0 !important;
        height: 30px !important;
        max-width: 54px !important;
        min-height: 30px !important;
        padding: 0 0.32rem !important;
        width: 54px !important;
    }
    div[class*="st-key-"][class*="_global_feedback_control"] [data-testid="stPopover"] > button::before {
        content: "Report";
        font-size: 0.62rem !important;
        font-weight: 800 !important;
        letter-spacing: 0.02em !important;
        line-height: 1 !important;
    }
    body:has(div[data-testid="stDialog"]) div[class*="st-key-"][class*="_global_feedback_control"] {
        display: none !important;
    }
}
/* Final avatar polish: logos center normally; player headshots keep a consistent face crop. */
.sidebar-logo-wrap img,
.team-logo-wrap img,
.home-hero-logo img,
.dg-ranked-logo img,
.league-team-avatar img,
.team-card-avatar img {
    display: block !important;
    height: 100% !important;
    max-height: 100% !important;
    max-width: 100% !important;
    object-fit: cover !important;
    object-position: center center !important;
    width: 100% !important;
}
.home-hero-logo-command {
    align-items: center;
    color: rgba(248, 250, 252, 0.9);
    display: flex;
    font-weight: 900;
    justify-content: center;
    letter-spacing: 0.03em;
}

@media (max-width: 900px) {
    .home-command-shell {
        margin-bottom: 0.54rem !important;
    }
    .home-command-hero {
        gap: 0.42rem !important;
        grid-template-columns: 1fr !important;
        min-height: 0 !important;
        padding: 0.5rem 0.56rem !important;
    }
    .home-hero-logo-command {
        display: none !important;
    }
    .home-command-team {
        font-size: 0.88rem !important;
        line-height: 1.08 !important;
    }
    .home-command-meta {
        font-size: 0.68rem !important;
        line-height: 1.24 !important;
        margin-top: 0.18rem !important;
    }
    .home-command-badges {
        gap: 0.24rem !important;
        margin-top: 0.32rem !important;
    }
    .home-hero-stats {
        gap: 0.32rem !important;
        margin-top: 0.36rem !important;
    }
    .home-hero-stat {
        min-height: 0 !important;
        padding: 0.34rem 0.38rem !important;
    }
}
.free-agent-avatar {
    --avatar-size: 56px !important;
    align-self: flex-start !important;
    border-radius: var(--radius-pill) !important;
    flex: 0 0 var(--avatar-size) !important;
    height: var(--avatar-size) !important;
    overflow: hidden !important;
    width: var(--avatar-size) !important;
}
.free-agent-avatar::before {
    border-radius: var(--radius-pill) !important;
    inset: 0 !important;
}
.free-agent-avatar img {
    bottom: auto !important;
    display: block !important;
    height: 100% !important;
    left: auto !important;
    max-height: 100% !important;
    max-width: 100% !important;
    object-fit: cover !important;
    object-position: center var(--dg-headshot-focus, 18%) !important;
    position: absolute !important;
    right: auto !important;
    top: 0 !important;
    transform: scale(var(--dg-headshot-scale, 1.16)) !important;
    transform-origin: center var(--dg-headshot-focus, 18%) !important;
    width: 100% !important;
}

@media (max-width: 900px) {
    .free-agent-avatar {
        --avatar-size: 48px !important;
    }
}
div[data-testid="stDialog"] .player-quick-view-name,
div[data-testid="stDialog"] .player-detail-name {
    font-size: 1rem !important;
    line-height: 1.02 !important;
    margin-top: 0.06rem !important;
}
div[data-testid="stDialog"] .player-quick-view-meta,
div[data-testid="stDialog"] .player-detail-meta {
    font-size: 0.7rem !important;
    line-height: 1.18 !important;
}
div[data-testid="stDialog"] .player-detail-chip-row {
    gap: 0.24rem !important;
    margin-top: 0.32rem !important;
}
div[data-testid="stDialog"] .player-detail-chip-row .dg-glyph-chip,
div[data-testid="stDialog"] .player-detail-score-pill {
    border-radius: 2px !important;
    font-size: 0.62rem !important;
    min-height: 0 !important;
    padding: 0.22rem 0.34rem !important;
}
    div[data-testid="stDialog"] .player-quick-view-panel-body {
        gap: 0.36rem !important;
        padding: 0.46rem 0.52rem 0.56rem !important;
    }
div[data-testid="stDialog"] .summary-tile-affordance {
    display: none !important;
}
div[data-testid="stDialog"] .player-quick-view-season-context {
    color: var(--color-text-secondary) !important;
    font-size: var(--font-size-caption) !important;
    font-weight: var(--font-weight-metadata) !important;
    line-height: var(--line-height-caption) !important;
    margin: var(--space-sm) 0 var(--space-xs) !important;
}
div[data-testid="stDialog"] .player-quick-view-detail-list,
div[data-testid="stDialog"] .player-quick-view-context-section,
div[data-testid="stDialog"] .player-quick-view-stat-section,
div[data-testid="stDialog"] .summary-tile-grid,
div[data-testid="stDialog"] .player-detail-score-row {
    border: 1px solid rgba(229, 231, 235, 0.09) !important;
    border-radius: 2px !important;
    display: grid !important;
    gap: 0 !important;
    grid-template-columns: 1fr !important;
    margin: 0.26rem 0 !important;
    overflow: hidden !important;
}
div[data-testid="stDialog"] .player-quick-view-detail-row,
div[data-testid="stDialog"] .player-quick-view-stat-row,
div[data-testid="stDialog"] .summary-tile,
div[data-testid="stDialog"] .player-detail-score-pill {
    align-items: start !important;
    background: rgba(229, 231, 235, 0.035) !important;
    border: 0 !important;
    border-bottom: 1px solid rgba(229, 231, 235, 0.075) !important;
    border-left: 0 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    display: grid !important;
    gap: 0.38rem !important;
    grid-template-columns: minmax(5.25rem, 0.36fr) minmax(0, 1fr) !important;
    margin: 0 !important;
    min-height: 0 !important;
    padding: 0.34rem 0.44rem !important;
}
div[data-testid="stDialog"] .player-quick-view-detail-row:last-child,
div[data-testid="stDialog"] .player-quick-view-stat-row:last-child,
div[data-testid="stDialog"] .summary-tile:last-child,
div[data-testid="stDialog"] .player-detail-score-pill:last-child {
    border-bottom: 0 !important;
}
div[data-testid="stDialog"] .player-quick-view-stat-heading {
    background: rgba(229, 231, 235, 0.045) !important;
    border-bottom: 1px solid rgba(229, 231, 235, 0.075) !important;
    border-left: 3px solid rgba(34, 211, 238, 0.58) !important;
    color: rgba(248, 250, 252, 0.7) !important;
    font-size: 0.58rem !important;
    font-weight: 900 !important;
    letter-spacing: 0.06em !important;
    line-height: 1.12 !important;
    padding: 0.28rem 0.44rem !important;
    text-transform: uppercase !important;
}
div[data-testid="stDialog"] .summary-tile-top,
div[data-testid="stDialog"] .player-detail-score-label {
    align-self: start !important;
    grid-column: 1 !important;
    margin: 0 !important;
}
div[data-testid="stDialog"] .summary-tile-label,
div[data-testid="stDialog"] .player-detail-score-label,
div[data-testid="stDialog"] .player-quick-view-detail-label,
div[data-testid="stDialog"] .player-quick-view-stat-label {
    color: rgba(248, 250, 252, 0.5) !important;
    font-size: 0.58rem !important;
    font-weight: 900 !important;
    letter-spacing: 0.06em !important;
    line-height: 1.12 !important;
    overflow-wrap: normal !important;
    text-transform: uppercase !important;
    white-space: normal !important;
    word-break: keep-all !important;
}
div[data-testid="stDialog"] .summary-tile-value,
div[data-testid="stDialog"] .player-detail-score-value,
div[data-testid="stDialog"] .player-quick-view-detail-value,
div[data-testid="stDialog"] .player-quick-view-stat-value {
    color: #ffffff !important;
    font-size: 0.78rem !important;
    font-weight: 880 !important;
    grid-column: 2 !important;
    line-height: 1.12 !important;
    margin: 0 !important;
}
div[data-testid="stDialog"] .summary-tile-note,
div[data-testid="stDialog"] .player-detail-score-note,
div[data-testid="stDialog"] .player-quick-view-detail-note,
div[data-testid="stDialog"] .player-quick-view-stat-note {
    color: rgba(248, 250, 252, 0.58) !important;
    font-size: 0.68rem !important;
    grid-column: 2 !important;
    line-height: 1.22 !important;
    margin-top: 0.08rem !important;
}
div[data-testid="stDialog"] .player-quick-view-recommendation-card {
    margin: 0.36rem 0 0.26rem !important;
    padding: 0.46rem 0.56rem !important;
}
div[data-testid="stDialog"] .player-quick-view-stat-grid {
    grid-template-columns: repeat(auto-fit, minmax(94px, 1fr)) !important;
}
div[data-testid="stDialog"] .player-quick-view-stat-row {
    gap: 0.1rem !important;
    grid-template-columns: 1fr !important;
    padding: 0.28rem 0.38rem !important;
}
div[data-testid="stDialog"] .player-quick-view-stat-label,
div[data-testid="stDialog"] .player-quick-view-stat-value,
div[data-testid="stDialog"] .player-quick-view-stat-note {
    grid-column: 1 !important;
}
div[data-testid="stDialog"] .player-quick-view-stat-value {
    font-size: 0.86rem !important;
    font-weight: 940 !important;
}
div[data-testid="stDialog"] .player-quick-view-stat-note {
    display: none !important;
}
div[data-testid="stDialog"] .section-header {
    margin: 0.58rem 0 0.2rem !important;
    padding-left: 0.44rem !important;
}
div[data-testid="stDialog"] .section-title {
    font-size: 0.78rem !important;
}
div[data-testid="stDialog"] .section-note {
    display: none !important;
}
div[data-testid="stDialog"] .player-quick-view-actions-label {
    margin-top: 0.48rem !important;
}

@media (max-width: 900px) {
    div[data-testid="stDialog"] div[role="dialog"] {
        padding: 0.28rem !important;
    }
    div[data-testid="stDialog"] .player-quick-view-header-band.player-quick-view-hero,
    div[data-testid="stDialog"] .player-detail-hero {
        grid-template-columns: 58px minmax(0, 1fr) !important;
        padding: 0.5rem 0.5rem !important;
    }
    div[data-testid="stDialog"] .player-detail-avatar,
    div[data-testid="stDialog"] .player-quick-view-avatar {
        --avatar-size: 58px !important;
    }
    div[data-testid="stDialog"] .player-detail-avatar,
    div[data-testid="stDialog"] .player-detail-avatar.player-quick-view-avatar,
    div[data-testid="stDialog"] .player-quick-view-avatar,
    div[data-testid="stDialog"] .player-quick-view-header-band .player-detail-avatar {
        aspect-ratio: 1 / 1 !important;
        flex: 0 0 58px !important;
        height: 58px !important;
        max-height: 58px !important;
        max-width: 58px !important;
        min-height: 58px !important;
        min-width: 58px !important;
        width: 58px !important;
    }
    div[data-testid="stDialog"] .player-detail-avatar img,
    div[data-testid="stDialog"] .player-detail-avatar.player-quick-view-avatar img,
    div[data-testid="stDialog"] .player-quick-view-avatar img,
    div[data-testid="stDialog"] .player-quick-view-header-band .player-detail-avatar img {
        aspect-ratio: 1 / 1 !important;
        display: block !important;
        height: 58px !important;
        max-height: 58px !important;
        max-width: 58px !important;
        min-height: 0 !important;
        min-width: 0 !important;
        object-fit: cover !important;
        object-position: center var(--dg-headshot-focus, 18%) !important;
        width: 58px !important;
    }
    div[data-testid="stDialog"] .player-quick-view-detail-row,
    div[data-testid="stDialog"] .player-quick-view-stat-row,
    div[data-testid="stDialog"] .summary-tile,
    div[data-testid="stDialog"] .player-detail-score-pill {
        grid-template-columns: 1fr !important;
        padding: 0.32rem 0.4rem !important;
    }
    div[data-testid="stDialog"] .summary-tile-top,
    div[data-testid="stDialog"] .summary-tile-value,
    div[data-testid="stDialog"] .summary-tile-note,
    div[data-testid="stDialog"] .player-detail-score-label,
    div[data-testid="stDialog"] .player-detail-score-value,
    div[data-testid="stDialog"] .player-detail-score-note,
    div[data-testid="stDialog"] .player-quick-view-detail-label,
    div[data-testid="stDialog"] .player-quick-view-detail-value,
    div[data-testid="stDialog"] .player-quick-view-detail-note,
    div[data-testid="stDialog"] .player-quick-view-stat-label,
    div[data-testid="stDialog"] .player-quick-view-stat-value,
    div[data-testid="stDialog"] .player-quick-view-stat-note {
        grid-column: 1 !important;
    }
    div[data-testid="stDialog"] .summary-tile-label,
    div[data-testid="stDialog"] .player-detail-score-label,
    div[data-testid="stDialog"] .player-quick-view-detail-label,
    div[data-testid="stDialog"] .player-quick-view-stat-label {
        line-height: 1.18 !important;
        max-width: 100% !important;
    }
    div[data-testid="stDialog"] .player-quick-view-stat-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }
}
:root {
    /* Founder beta responsive shell: final, authoritative control geometry. */
--dg-mobile-control-bottom: max(14px, env(safe-area-inset-bottom, 0px));
    --dg-mobile-control-side: max(14px, env(safe-area-inset-left, 0px));
    --dg-mobile-shell-clearance: calc(76px + env(safe-area-inset-bottom, 0px));
}
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stMainMenu"],
[data-testid="stAppDeployButton"],
[data-testid="stElementToolbar"],
[data-testid="collapsedControl"] {
    display: none !important;
}
div[class*="st-key-"][class*="_global_feedback_control"] {
    bottom: var(--dg-mobile-control-bottom) !important;
    left: auto !important;
    right: max(14px, env(safe-area-inset-right, 0px)) !important;
}
/* GM sheet chrome owned by MOBILE_INTERACTION_OVERLAY_CSS. */

@media (max-width: 900px) {
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {
        max-width: 100vw !important;
        overflow-x: clip !important;
    }

    [data-testid="stMainBlockContainer"] {
        padding-bottom: var(--dg-mobile-shell-clearance) !important;
    }

    div[data-testid="stHorizontalBlock"] {
        max-width: 100% !important;
    }

    div[data-testid="stDataFrame"],
    div[data-testid="stTable"],
    div[data-testid="stPlotlyChart"] {
        max-width: 100% !important;
        overflow-x: auto !important;
    }

    button,
    [role="button"] {
        touch-action: manipulation;
    }

    body:has(div[data-testid="stDialog"]) div[class*="st-key-mobile_gm_sheet_trigger_"],
    body:has(div[data-testid="stDialog"]) div[class*="st-key-"][class*="_global_feedback_control"] {
        visibility: hidden !important;
        pointer-events: none !important;
    }
}
/* Shared player headshots. Final,
player-only,
and authoritative. */
.dg-player-headshot {
    --dg-headshot-scale: 1.16;
    --dg-headshot-focus: 18%;
    align-items: center !important;
    display: flex !important;
    justify-content: center !important;
    overflow: hidden !important;
    position: relative !important;
}
.dg-player-headshot--compact {
    --dg-headshot-scale: 1.12;
    --dg-headshot-focus: 20%;
}
.dg-player-headshot--standard {
    --dg-headshot-scale: 1.16;
    --dg-headshot-focus: 18%;
}
.dg-player-headshot--profile {
    --dg-headshot-scale: 1.1;
    --dg-headshot-focus: 16%;
}
.dg-player-headshot .dg-player-headshot-image,
.dg-player-headshot > img {
    bottom: auto !important;
    display: block !important;
    filter: none !important;
    height: 100% !important;
    inset: 0 !important;
    left: 0 !important;
    margin: 0 !important;
    max-height: 100% !important;
    max-width: 100% !important;
    object-fit: cover !important;
    object-position: center var(--dg-headshot-focus) !important;
    position: absolute !important;
    right: auto !important;
    top: 0 !important;
    transform: scale(var(--dg-headshot-scale)) !important;
    transform-origin: center var(--dg-headshot-focus) !important;
    width: 100% !important;
    z-index: 1 !important;
}
.dg-player-headshot-fallback {
    align-items: center !important;
    display: flex !important;
    height: 100% !important;
    inset: 0 !important;
    justify-content: center !important;
    pointer-events: none !important;
    position: absolute !important;
    text-align: center !important;
    transform: none !important;
    width: 100% !important;
    z-index: 0 !important;
}
/* Hide initials whenever a photo element is present. onerror removes a broken img. */
.dg-player-headshot:has(img.dg-player-headshot-image) .dg-player-headshot-fallback,
.dg-player-headshot:has(.dg-player-headshot-image.is-loaded) .dg-player-headshot-fallback {
    opacity: 0 !important;
    visibility: hidden !important;
}
/* Trade Hub mobile hierarchy: presentation only. */
.trade-card-top-compact {
    align-items: flex-start;
    border-bottom: var(--border-width-default) solid var(--color-border);
    display: block;
    min-height: 0;
    padding: var(--space-lg);
}
.trade-card-top-compact .trade-card-kicker {
    color: var(--color-information);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    line-height: var(--line-height-badge);
    text-transform: uppercase;
}
.trade-card-top-compact .trade-card-title {
    color: var(--color-text-primary);
    font-size: var(--font-size-section-title);
    font-weight: var(--font-weight-title);
    line-height: var(--line-height-title);
    margin-top: var(--space-sm);
}
.trade-card-summary {
    color: var(--color-text-secondary);
    font: var(--font-body);
    margin-top: var(--space-md);
    overflow-wrap: anywhere;
}
.trade-card-opportunity {
    background: var(--color-information-soft);
    border-left: var(--border-width-semantic) solid var(--color-information);
    border-radius: var(--radius-md);
    margin-top: var(--space-md);
    padding: var(--space-sm) var(--space-md);
}
.trade-card-opportunity-label {
    color: var(--color-information);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.trade-card-opportunity p {
    color: var(--color-text-secondary);
    font: var(--font-body);
    margin: var(--space-xs) 0 0;
    overflow-wrap: anywhere;
}
.trade-card-partner {
    color: var(--color-text-muted);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    margin-top: var(--space-md);
}
.trade-card-partner strong {
    color: var(--color-text-secondary);
}
.trade-card-top-compact .trade-card-meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-sm);
    margin-top: var(--space-md);
}
.trade-matchup-compact {
    align-items: stretch;
    display: grid;
    gap: 0;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    padding: var(--space-sm) var(--space-md);
}
.trade-matchup-compact .trade-side {
    background: transparent !important;
    border: 0 !important;
    border-radius: 0 !important;
    min-width: 0;
    padding: var(--space-md) var(--space-xs);
}
.trade-matchup-compact .trade-side-header {
    align-items: baseline;
    color: var(--color-text-muted);
    display: flex;
    font-size: var(--font-size-caption);
    justify-content: space-between;
    margin-bottom: var(--space-sm);
}
.trade-matchup-compact .trade-side-value {
    font-size: var(--font-size-body);
    font-weight: var(--font-weight-title);
}
.trade-matchup-compact .trade-assets {
    gap: 0;
}
.trade-matchup-compact .trade-asset-row {
    background: var(--color-surface-muted) !important;
    border: 0 !important;
    border-bottom: var(--border-width-default) solid var(--color-border) !important;
    border-radius: 0 !important;
    gap: var(--space-md);
    min-height: var(--touch-target-min);
    padding: var(--space-sm);
}
.trade-matchup-compact .trade-asset-row:first-child {
    border-radius: var(--radius-md) var(--radius-md) 0 0 !important;
}
.trade-matchup-compact .trade-asset-row:last-child {
    border-bottom: 0 !important;
    border-radius: 0 0 var(--radius-md) var(--radius-md) !important;
}
.trade-matchup-compact .trade-asset-row:only-child {
    border-radius: var(--radius-md) !important;
}
.trade-matchup-compact .trade-avatar {
    flex: 0 0 var(--space-3xl);
    height: var(--space-3xl);
    width: var(--space-3xl);
}
.trade-matchup-compact .trade-asset-name {
    font-size: var(--font-size-body);
    line-height: var(--line-height-card);
    overflow-wrap: anywhere;
}
.trade-matchup-compact .trade-asset-meta {
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    margin-top: var(--space-xs);
    white-space: normal;
}
.trade-matchup-compact .trade-asset-status-row,
.trade-matchup-compact .trade-asset-tags {
    gap: var(--space-xs);
}
.trade-matchup-compact .trade-vs {
    align-items: center;
    color: var(--color-information);
    display: flex;
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    justify-content: center;
    padding: 0 var(--space-sm);
}
.trade-card-net-strip {
    align-items: center;
    background: var(--color-surface-muted);
    border-top: var(--border-width-default) solid var(--color-border);
    color: var(--color-text-muted);
    display: flex;
    font-size: var(--font-size-caption);
    justify-content: space-between;
    padding: var(--space-md) var(--space-lg);
}
.trade-card-net-strip strong {
    font-size: var(--font-size-body);
    font-weight: var(--font-weight-title);
}
.trade-value-send {
    color: var(--color-danger);
}
.trade-value-receive {
    color: var(--color-success);
}
.trade-delta-positive {
    color: var(--color-success) !important;
}
.trade-delta-negative {
    color: var(--color-danger) !important;
}
.trade-delta-neutral {
    color: var(--color-text-secondary) !important;
}
div[class*="st-key-trade_why_"] {
    margin: var(--space-xs) 0 var(--space-sm);
}
div[class*="st-key-trade_why_"][class*="_control"] [data-testid="stButton"] {
    margin: 0;
}
div[class*="st-key-trade_why_"][class*="_control"] [data-testid="stButton"] button {
    align-items: center;
    color: var(--color-text-secondary);
    font-size: var(--font-size-caption);
    font-weight: var(--font-weight-button);
    min-height: var(--touch-target-min);
    padding: 0 var(--space-sm);
}
div[class*="st-key-trade_why_"][class*="_control"] [data-testid="stButton"] button:focus-visible {
    border-radius: var(--radius-md);
    box-shadow: var(--focus-ring);
    outline: none;
}
.trade-reason-panel {
    background: var(--color-information-soft);
    border-left: var(--border-width-semantic) solid var(--color-information);
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
    margin: var(--space-xs) 0 var(--space-sm);
    overflow: hidden;
    padding: var(--space-xs) var(--space-md);
    width: 100%;
}
.trade-reason-row {
    border-bottom: var(--border-width-default) solid var(--color-border);
    display: grid;
    gap: var(--space-xs);
    grid-template-columns: minmax(7.8rem, 0.42fr) minmax(0, 1fr);
    padding: var(--space-md) 0;
}
.trade-reason-row:last-child {
    border-bottom: 0;
}
.trade-reason-row > span {
    color: var(--color-information);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.trade-reason-row p {
    color: var(--color-text-secondary);
    font-size: var(--font-size-caption);
    line-height: var(--line-height-body);
    margin: 0;
    min-width: 0;
    overflow: visible;
    overflow-wrap: anywhere;
    text-overflow: clip;
    white-space: normal;
}
.trade-idea-end-marker {
    border-bottom: var(--border-width-default) solid var(--color-border);
    height: 1px;
    margin: var(--space-md) 0 var(--space-lg);
}
div[class*="st-key-trade_hub_"] [data-testid="stExpander"] {
    border-color: var(--color-border);
    margin-bottom: var(--space-xs);
}

@keyframes trade-card-enter {
    from {
        opacity: 0;
        transform: translateY(var(--space-xs));
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@media (max-width: 700px) {
    .trade-matchup-compact {
        display: block;
        padding: var(--space-sm) var(--space-md);
    }
    .trade-matchup-compact .trade-vs {
        gap: var(--space-sm);
        min-height: var(--space-xl);
        padding: 0;
    }
    .trade-matchup-compact .trade-vs::before,
    .trade-matchup-compact .trade-vs::after {
        background: var(--color-border);
        content: "";
        flex: 1;
        height: 1px;
    }
    .trade-matchup-compact .trade-side {
        padding: var(--space-sm) 0;
    }
    .trade-reason-row {
        gap: var(--space-xs);
        grid-template-columns: 1fr;
    }
    .trade-idea-end-marker {
        margin-bottom: var(--space-lg);
    }
}
.trade-summary-card {
    border-color: var(--color-border) !important;
    margin: var(--space-md) 0 var(--space-xs) !important;
    max-width: 100%;
    overflow: hidden;
    padding: var(--space-md) var(--space-lg) var(--space-sm);
}
.trade-summary-header {
    align-items: end;
    display: flex;
    gap: var(--space-md);
    justify-content: space-between;
    min-width: 0;
}
.trade-summary-heading {
    display: grid;
    gap: var(--space-xs);
    min-width: 0;
}
.trade-summary-category,
.trade-summary-kicker,
.trade-summary-side > span {
    color: var(--color-text-muted);
    font-size: var(--font-size-badge);
    font-weight: var(--font-weight-title);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.trade-summary-title {
    color: var(--color-text-primary);
    font-size: var(--font-size-card-title);
    font-weight: var(--font-weight-title);
    line-height: var(--line-height-title);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.trade-summary-partner {
    color: var(--color-text-secondary);
    flex: 0 0 auto;
    font-size: var(--font-size-caption);
}
.trade-summary-package {
    border-block: var(--border-width-default) solid var(--color-border);
    display: grid;
    gap: var(--space-sm);
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    margin-top: var(--space-sm);
    padding: var(--space-sm) 0;
}
.trade-summary-side {
    min-width: 0;
}
.trade-summary-side > div {
    color: var(--color-text-primary);
    font-size: var(--font-size-body);
    line-height: var(--line-height-card);
    overflow-wrap: break-word;
}
.trade-summary-separator {
    color: var(--color-text-muted);
}
.trade-summary-value {
    align-items: center;
    color: var(--color-text-muted);
    display: flex;
    font-size: var(--font-size-caption);
    justify-content: space-between;
    padding-top: var(--space-sm);
}
.trade-summary-signals {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    margin-top: var(--space-sm);
}
.trade-summary-rationale {
    color: var(--color-text-secondary);
    display: -webkit-box;
    font-size: var(--font-size-caption);
    line-height: var(--line-height-body);
    margin: var(--space-sm) 0 0;
    overflow: hidden;
    overflow-wrap: break-word;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}
div[class*="st-key-trade_summary_"][class*="_open"] {
    margin: 0 0 var(--space-sm);
}
div[class*="st-key-trade_summary_"][class*="_open"] button {
    min-height: var(--touch-target-min);
}

@media (max-width: 700px) {
    .trade-summary-card {
        margin-top: var(--space-sm) !important;
        min-height: 0;
        padding: var(--space-sm) var(--space-md) var(--space-xs);
    }
    .trade-summary-header {
        align-items: start;
        display: block;
    }
    .trade-summary-partner {
        margin-top: var(--space-xs);
    }
    .trade-summary-package {
        display: block;
    }
    .trade-summary-side + .trade-summary-side {
        margin-top: var(--space-xs);
    }
    .trade-summary-signals .dg-ui-badge:nth-child(n + 4) {
        display: none;
    }
}
""".strip()

APP_CSS = (
    "<style>\n"
    + DESIGN_TOKEN_CSS
    + "\n"
    + UI_PRIMITIVE_CSS
    + "\n"
    + COMPONENT_FAMILY_CSS
    + "\n"
    + DENSE_LIST_CSS
    + "\n"
    + UI_MODAL_CSS
    + "\n"
    + ship_css(_APP_CSS_MIDFILE)
    + "\n"
    + APPLICATION_SHELL_CSS
    + "\n"
    + FOOTBALL_ASSET_CSS
    + LEAGUE_INTELLIGENCE_CSS
    + RECOMMENDATION_TRUST_CSS
    + COMMAND_CENTER_CSS
    + INTERFACE_REIMAGINING_CSS
    + MOBILE_WORKFLOW_CSS
    + FOUNDER_BETA_CONSISTENCY_CSS
    + FOUNDER_BETA_QUICK_FIX_CSS
    + BRAND_IDENTITY_CSS
    + VISUAL_HIERARCHY_CSS
    + DESKTOP_EXECUTIVE_LAYOUT_CSS
    + EXECUTIVE_WORKFLOW_COMPRESSION_CSS
    + EXECUTIVE_DESIGN_UNIFY_CSS
    + METRIC_GRAPHIC_CSS
    + MOBILE_INTERACTION_OVERLAY_CSS
    + "\n</style>\n"
)
