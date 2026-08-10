from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_saved_league_cards_are_directly_tappable_without_switch_button():
    app = source("app.py")
    section = app.split("def render_header_league_switcher", 1)[1].split(
        "def render_top_league_identity_header", 1
    )[0]
    assert "LEAGUE_SWITCH_CARD_COMPONENT" in section
    assert '"Switch"' not in section
    assert "Switching to " in app
    assert "Loading league..." in app
    assert "Switching league..." not in app
    assert '"current": is_current' in section
    assert '"is_default": bool(row.get("is_default"))' in section


def test_league_actions_sheet_uses_required_sections_and_internal_scroll():
    app = source("app.py")
    styles = source("modules/ux_polish_styles.py")
    for label in (
        "Current League",
        "Switch League",
        "Refresh Current League",
        "Manage Leagues",
        "Premium",
    ):
        assert label in app
    assert "max-height: min(72dvh, 620px)" in styles
    assert "overflow-y: auto" in styles


def test_injury_value_indicators_are_explicit_badges():
    cards = source("modules/player_cards.py")
    assert "def injury_status_badge" in cards
    for label in ("IR", "OUT", "Q", "INJ"):
        assert f'return "{label}"' in cards
    generated = cards.split("def injury_adjusted_value_html", 1)[1].split(
        "def canonical_player_status", 1
    )[0]
    assert "injury-adjustment-badge" in generated
    assert "injury-adjustment-ring injury-adjustment-badge" in generated


def test_recommendation_copy_is_condensed_only_in_rendering_modules():
    workspace = source("modules/workspace_ui.py")
    live_ui = source("modules/live_draft_ui.py")
    assert "def concise_recommendation_text" in workspace
    assert "title='{escape(full_note, quote=True)}'" in workspace
    assert "def _concise_reason" in live_ui
    assert "rec.get('reason')" in live_ui


def test_roster_pressure_replaces_duplicate_over_limit_tiles():
    my_team = source("modules/my_team_ui.py")
    assert "Roster Pressure" in my_team
    assert 'if my_roster_limit.get("over_limit")' in my_team
    assert '"label": "Roster Limit Status"' not in my_team
    assert '"label": "Immediate Recommendation"' not in my_team


def test_floating_controls_remain_safe_area_aware_and_modal_safe():
    styles = source("modules/ux_polish_styles.py")
    base_styles = source("modules/app_styles.py")
    overlay = source("modules/mobile_interaction_overlay_styles.py")
    combined = styles + base_styles + overlay
    assert "safe-area-inset-bottom" in combined
    assert "min-width: var(--touch-target-min) !important" in overlay
    assert "border-radius: 50% !important" in overlay
    assert "body:has(div[data-testid=\"stDialog\"])" in styles
    assert "padding-bottom: var(--dg-mobile-shell-clearance)" in combined


def test_mobile_polish_does_not_disable_zoom():
    combined = source("app.py") + source("modules/ux_polish_styles.py")
    assert "user-scalable=no" not in combined
    assert "maximum-scale=1" not in combined
