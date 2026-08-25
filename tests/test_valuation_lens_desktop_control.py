"""Desktop evaluation-lens control shares canonical session ``league_type``."""

from pathlib import Path

from modules import valuation_archetype_ui


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
UI = (ROOT / "modules" / "valuation_archetype_ui.py").read_text(encoding="utf-8")


def test_canonical_lens_owner_is_session_league_type():
    assert valuation_archetype_ui.CANONICAL_LENS_SESSION_KEY == "league_type"
    assert valuation_archetype_ui.SUPPORTED_VALUATION_LENSES == (
        "Dynasty",
        "Rebuild",
        "Non-Dynasty",
    )
    for lens in valuation_archetype_ui.SUPPORTED_VALUATION_LENSES:
        assert lens in APP
    assert 'key=CANONICAL_LENS_SESSION_KEY' in UI or 'key="league_type"' in UI
    assert 'key="league_type"' not in APP.split("with st.sidebar:", 1)[1].split(
        "account_actions = account_ui.render_account_panel(", 1
    )[0]


def test_dashboard_page_context_is_the_only_lens_widget():
    assert 'st.selectbox(' in UI
    assert 'CANONICAL_LENS_SESSION_KEY' in UI
    assert 'key="dashboard_page_context"' in UI
    assert "render_evaluation_lens_control(" in UI
    assert "Evaluate using" in APP
    sidebar = APP.split("with st.sidebar:", 1)[1].split(
        "account_actions = account_ui.render_account_panel(", 1
    )[0]
    assert 'st.selectbox(' in sidebar
    assert "Valuation lens" not in sidebar
    assert "League scoring overrides" in sidebar


def test_explicit_lens_is_not_overwritten_on_same_league_rerun():
    auto_block = APP.split(
        'if st.session_state.get("league_settings_auto_lens_id") != selected_league_id:',
        1,
    )[1].split("legacy_lens = st.session_state.get", 1)[0]
    assert 'st.session_state["league_type"] = auto_lens' in auto_block
    coerce = APP.split(
        'league_type = _safe_text(st.session_state.get("league_type"), auto_lens)',
        1,
    )[1].split("if startup.active:", 1)[0]
    assert 'st.session_state["league_type"] = league_type' in coerce
    assert "auto_lens" in coerce
    # Presentation / archetype enrichment must not write the canonical lens.
    home = APP.split("def render_home_dashboard(", 1)[1].split(
        "def render_platform_topbar(", 1
    )[0]
    assert '["league_type"] =' not in home
    assert "valued_shell_chrome_enrichment" not in home


def test_lens_maps_to_canonical_score_fields():
    from app import VALUATION_LENS_TO_SCORE_FIELD, valuation_score_field

    assert VALUATION_LENS_TO_SCORE_FIELD == {
        "Dynasty": "dynasty_score",
        "Rebuild": "rebuild_score",
        "Non-Dynasty": "value_score",
    }
    for lens, field in VALUATION_LENS_TO_SCORE_FIELD.items():
        assert valuation_score_field(lens) == field


def test_current_valuation_lens_rejects_unknown_values():
    assert valuation_archetype_ui.current_valuation_lens({"league_type": "Rebuild"}) == "Rebuild"
    assert valuation_archetype_ui.current_valuation_lens({"league_type": "Win Now"}) == "Dynasty"
    assert valuation_archetype_ui.current_valuation_lens({}) == "Dynasty"
