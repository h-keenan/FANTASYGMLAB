"""Route-scoped CSS for the relaunch paywall-trigger gates.

Not part of APP_CSS (modules/app_styles.py is already near the byte-budget
ceiling — see tests/test_app_css_architecture.py). Injected only on the
routes that actually render a locked-feature preview, via
``modules.html_rendering.inject_global_styles``, the same lazy-injection
pattern as modules.alerts_activity_styles / modules.premium_page's
PREMIUM_HIGHLIGHT_CSS.

Pairs with ``modules.premium.premium_blur_preview_html`` to satisfy the
relaunch product rule: a locked feature must stay visible (a dimmed,
literally-blurred shape of what's hidden) rather than disappear outright —
never a bare "Premium" wall with nothing behind it.
"""

PAYWALL_GATE_CSS = """
.paywall-blur-preview{
    display:grid;
    gap:0.3rem;
    margin:0.2rem 0 0.5rem;
    max-width:100%;
    overflow-x:hidden;
    position:relative;
}
.paywall-blur-label{
    color:var(--color-text-muted,#a8adb7);
    font-size:0.72rem;
    font-weight:700;
    margin:0;
}
.paywall-blur-row{
    background:var(--color-surface-raised,#3d4248);
    border:1px solid var(--color-border,#2a2e35);
    border-radius:4px;
    filter:blur(2px);
    min-height:1.1rem;
    opacity:0.62;
}
@media (max-width: 430px){
    .paywall-blur-preview{ margin-bottom:0.3rem; }
}
"""
