from pathlib import Path

from streamlit.testing.v1 import AppTest

from modules import football_assets
from modules.player_tier_identity import resolve_player_tier_identity


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "waivers_visual_harness.py"


def _app() -> AppTest:
    return AppTest.from_file(str(HARNESS), default_timeout=60).run()


def test_waivers_visual_harness_is_synthetic_and_production_isolated():
    source = HARNESS.read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "waivers_visual_harness" not in app_source
    assert "Synthetic fixture only" in source
    assert "access_token" not in source
    assert "password" not in source.casefold()
    assert "auth_session" not in source


def test_waivers_visual_harness_uses_production_card_renderer():
    source = HARNESS.read_text(encoding="utf-8")
    assert "app.render_free_agent_cards(" in source
    assert "Emanuel Wilson" in source


def test_waivers_visual_harness_runs_without_exception():
    # The real card markup renders through a custom tap-grid Streamlit
    # component (modules.player_cards.render_tappable_player_html ->
    # PLAYER_SCAN_TAP_COMPONENT), not st.markdown, so AppTest can't
    # introspect its inner HTML the way application.markdown does for plain
    # markdown elements — this only proves the production wiring (real
    # render_free_agent_cards, real callables threaded in from app.py) runs
    # clean end-to-end against the synthetic fixture. The actual ring/pill
    # markup is verified directly below, against the same
    # football_assets.player_card_html primitive waivers_ui.py calls.
    application = _app()
    assert not application.exception


def test_waiver_card_html_shows_ring_and_pill_primitives():
    # Mirrors exactly what modules.waivers_ui.render_free_agent_cards passes
    # into football_assets.player_card_html for a priority-add card: the
    # same extra_classes (free-agent-card), tier_frame="ring" default, and a
    # colored position pill via position_badge_html — the two primitives
    # modules.waivers_presentation_styles' scoped CSS override targets.
    html = football_assets.player_card_html(
        football_assets.FootballPlayerAsset(
            player_id="9221",
            display_name="Emanuel Wilson",
            position="RB",
            team="GB",
            prestige_label="Contributor",
            prestige_level="contributor",
            value_label="Dynasty Score",
            value="78",
        ),
        avatar_html="<img src='x.png' alt=''>",
        extra_classes=("free-agent-card", "dg-ui-card"),
        position_html=football_assets.position_badge_html("RB"),
        identity=resolve_player_tier_identity({"player_tier": "contributor"}),
    )
    assert "free-agent-card" in html
    # Avatar ring: the Dashboard-matching circular vivid-green ring markup
    # (modules.waivers_presentation_styles' scoped override of
    # football_assets.player_card_html's shared dg-tier-frame--ring).
    assert "dg-tier-frame--ring" in html
    # Colored position pill: football_assets.position_badge_html's existing
    # shared primitive (same function the Dashboard cards use).
    assert "dg-football-position--rb" in html
    # Bold player name markup (compact-player-name — font-weight: 800 via
    # modules.app_styles).
    assert "compact-player-name" in html
