"""Contracts for P0 Dashboard renderer bisect (#245)."""

from __future__ import annotations

from pathlib import Path

from modules import p0_dashboard_bisect as bisect


ROOT = Path(__file__).resolve().parents[1]


def test_minimal_flag_defaults_off(monkeypatch):
    monkeypatch.delenv(bisect.MINIMAL_ENV, raising=False)
    assert bisect.minimal_dashboard_enabled() is False
    monkeypatch.setenv(bisect.MINIMAL_ENV, "1")
    assert bisect.minimal_dashboard_enabled() is True


def test_enable_through_gate_order(monkeypatch):
    monkeypatch.setenv(bisect.ENABLE_THROUGH_ENV, "what_changed")
    assert bisect.block_allowed("intro") is True
    assert bisect.block_allowed("game_plan") is True
    assert bisect.block_allowed("what_changed") is True
    assert bisect.block_allowed("summary") is False
    assert bisect.block_allowed("deep_analysis") is False


def test_app_keeps_a_through_e_canaries():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    for token in (
        "FGL_P0_A_AFTER_AUTH",
        "FGL_P0_B_BEFORE_ROUTE",
        "FGL_P0_C_DASHBOARD_ENTER",
        "FGL_P0_D_FIRST_ELEMENT_RETURNED",
        "FGL_P0_E_DASHBOARD_RETURNED",
        "FGL_P0_D0_RENDERER_ENTERED",
        "FGL_P0_D1_BEFORE_GAME_PLAN",
        "FGL_P0_D9_BEFORE_RETURN",
        "FGL_P0_DASHBOARD_MINIMAL",
    ):
        assert token in app or token in (
            ROOT / "modules" / "p0_dashboard_bisect.py"
        ).read_text(encoding="utf-8")


def test_workflow_emits_d2_through_d8():
    source = (ROOT / "modules" / "dashboard_workflow.py").read_text(encoding="utf-8")
    for token in (
        "FGL_P0_D2_AFTER_GAME_PLAN",
        "FGL_P0_D3_BEFORE_WHAT_CHANGED",
        "FGL_P0_D4_AFTER_WHAT_CHANGED",
        "FGL_P0_D5_BEFORE_SUMMARY_TILES",
        "FGL_P0_D6_AFTER_SUMMARY_TILES",
        "FGL_P0_D7_BEFORE_DEEP_ANALYSIS",
        "FGL_P0_D8_AFTER_DEEP_ANALYSIS",
    ):
        assert token in source


def test_workflow_exception_path_no_longer_silent():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "st.exception(dashboard_exc)" in app
    assert "FGL_P0_DASHBOARD_EXCEPTION_" in app
