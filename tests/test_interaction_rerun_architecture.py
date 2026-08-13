"""Regression coverage for interaction-rerun architecture (#198)."""

from __future__ import annotations

from pathlib import Path

from modules import workspace_ui


ROOT = Path(__file__).resolve().parents[1]


def test_client_disclosure_is_browser_local_and_escaped():
    html = workspace_ui.client_disclosure_html(
        "How to read these boards",
        workspace_ui.concept_band_html(
            [
                {
                    "label": "<Standings>",
                    "title": "Actual results",
                    "body": "Wins & losses.",
                    "tone": "strategy",
                }
            ]
        ),
    )
    assert "<details" in html
    assert "<summary>How to read these boards</summary>" in html
    assert "&lt;Standings&gt;" in html
    assert "<Standings>" not in html
    assert "summary-tile-grid" in html
    assert "summary-tile dg-ui-card" in html
    assert "concept-band" not in html
    assert "concept-chip" not in html


def test_how_to_read_boards_is_client_local_not_streamlit_expander():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    rankings = source[source.index('if league_section == "Rankings":') :]
    assert "client_disclosure_html" in rankings
    assert '"How to read these boards"' in rankings
    assert 'expander("How to read these boards"' not in rankings


def test_pqv_more_news_is_client_local_details():
    source = (ROOT / "modules" / "player_quick_view.py").read_text(encoding="utf-8")
    assert "player-dossier-more-news" in source
    assert 'st.expander(f"More news' not in source


def test_redundant_pqv_open_reruns_removed():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    draft = (ROOT / "modules" / "draft_center_ui.py").read_text(encoding="utf-8")
    assert (
        'source_note="Startup Draft Center available-player board.",\n            )\n'
        "            st.rerun()"
    ) not in app
    assert (
        'source_note="Draft Assistant recommendation bucket.",\n            )\n'
        "            st.rerun()"
    ) not in draft
    assert (
        'source_note="Available player ranking board.",\n            )\n'
        "            st.rerun()"
    ) not in draft


def test_gm_targets_and_share_avoid_explicit_rerun():
    gm = (ROOT / "modules" / "gm_targets_ui.py").read_text(encoding="utf-8")
    share = (ROOT / "modules" / "share_recommendation_ui.py").read_text(encoding="utf-8")
    assert "st.rerun()" not in gm
    assert "on_click=_toggle_pqv_target" in gm
    assert "st.rerun()" not in share


def test_trade_show_more_is_fragment_scoped_without_board_rebuild():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("def _trade_hub_visible_feed()")
    assert "@st.fragment" in source[max(0, start - 40) : start]
    body = source[start : source.index("_trade_hub_visible_feed()", start + 10)]
    assert "increment_session_counter" in body
    assert "build_trade_ideas(" not in body
    assert "st.rerun()" not in body


def test_interaction_rerun_harness_runs():
    import importlib.util

    path = ROOT / "scripts" / "measure_interaction_rerun_architecture.py"
    spec = importlib.util.spec_from_file_location("measure_interaction_rerun_architecture", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.run(samples=3)
    # +confirmation / hierarchy / recommendation refresh / team-comparison tap.
    assert report["explicit_st_rerun_count"] <= 56
    assert "How to read these boards" in report["client_disclosures"]
    assert report["trade_show_more_contract"]["fragment_scoped"] is True
    assert report["trade_show_more_contract"]["no_build_trade_ideas"] is True
