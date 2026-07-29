from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_production_reruns_do_not_unconditionally_reload_dependency_modules():
    app = source("app.py")
    guarded = app.split('if app_config.config_bool("DYNASTYGM_DEV_RELOAD_MODULES"):', 1)
    assert len(guarded) == 2
    before_guard, after_guard = guarded
    assert "importlib.reload(" not in before_guard
    assert after_guard.count("importlib.reload(") == 16
    assert "DYNASTYGM_DEBUG_PERF" in source("modules/performance.py")


def test_league_switch_uses_only_selected_card_loading_feedback():
    app = source("app.py")
    switcher = app.split("def render_header_league_switcher", 1)[1].split(
        "def render_top_league_identity_header", 1
    )[0]
    component = app.split("LEAGUE_SWITCH_CARD_COMPONENT", 1)[1].split(
        "CHART_COLORS", 1
    )[0]
    assert "league-switch-card-loading" in component
    assert "Switching league..." in component
    assert "st.spinner" not in switcher
    assert "_switch_to_saved_league(selected_row" in switcher


def test_mobile_accessibility_floor_focus_and_keyboard_safety():
    styles = source("modules/ux_polish_styles.py")
    assert "--dg-ux-small-type: 0.75rem" in styles
    assert "--dg-ux-control-height: 44px" in styles
    assert "--dg-ux-focus-ring" in styles
    assert "font-size: 16px !important" in styles
    assert "[role=\"button\"]:focus-visible" in styles
    assert "launch_choose_account" in styles
    assert "user-scalable=no" not in styles
    assert "maximum-scale=1" not in styles


def test_floating_controls_yield_to_every_blocking_mobile_surface():
    styles = source("modules/ux_polish_styles.py")
    assert "body:has(.mobile-gm-sheet-marker)" in styles
    assert "body:has(.league-actions-sheet-marker)" in styles
    assert 'body:has(div[data-testid="stDialog"])' in styles
    assert "pointer-events: none !important" in styles
    assert "visibility: hidden !important" in styles
    assert "safe-area-inset-bottom" in source("modules/app_styles.py")


def test_reduced_motion_is_application_wide_without_disabling_zoom():
    styles = source("modules/ux_polish_styles.py")
    reduced = styles.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    assert "*::before" in reduced
    assert "animation-duration: 0.01ms !important" in reduced
    assert "transition-duration: 0.01ms !important" in reduced
    assert "scroll-behavior: auto !important" in reduced


def test_shared_player_presentation_remains_authoritative():
    base_styles = source("modules/app_styles.py")
    cards = source("modules/player_cards.py")
    assert "Shared player headshots" in base_styles
    assert "dg-player-headshot--compact" in base_styles
    assert "dg-player-headshot--standard" in base_styles
    assert "dg-player-headshot--profile" in base_styles
    assert "object-fit: contain !important" in base_styles
    assert "object-position: center bottom !important" in base_styles
    assert "def injury_status_badge" in cards
    assert "injury-adjustment-badge" in cards


def test_polish_roadmap_covers_every_requested_destination_and_severity():
    roadmap = source("docs/founder-beta-polish-roadmap.md")
    for destination in (
        "Dashboard",
        "My Team",
        "League Overview",
        "Rankings",
        "Trade Hub",
        "Waivers",
        "Startup Draft Center",
        "Live Draft",
        "Premium",
        "Workspace",
        "Settings / Account",
        "Feedback",
        "Login / Signup",
        "League picker",
    ):
        assert destination in roadmap
    for severity in ("## Critical", "## High", "## Medium backlog", "## Low backlog"):
        assert severity in roadmap


def test_live_draft_polling_and_trade_diagnostics_are_not_weakened():
    live_ui = source("modules/live_draft_ui.py")
    performance = source("modules/performance.py")
    trade_ideas = source("modules/trade_ideas.py")
    assert live_ui.count("@st.fragment") == 1
    assert "trade_generation_flame" in performance
    assert "TRADE_PIPELINE_STAGES" in trade_ideas
