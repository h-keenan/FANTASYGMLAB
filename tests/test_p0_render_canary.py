"""Focused checks for P0 render canary diagnostic helpers."""

from __future__ import annotations

import os

from modules import p0_render_canary


def test_safe_render_defaults_on(monkeypatch):
    monkeypatch.delenv(p0_render_canary.SAFE_RENDER_ENV, raising=False)
    assert p0_render_canary.safe_render_enabled() is True


def test_safe_render_can_disable(monkeypatch):
    monkeypatch.setenv(p0_render_canary.SAFE_RENDER_ENV, "0")
    assert p0_render_canary.safe_render_enabled() is False


def test_safe_render_css_targets_shell_and_main_containers():
    css = p0_render_canary.SAFE_RENDER_CSS
    assert ".dg-startup-shell" in css
    assert "display: none !important" in css
    assert '[data-testid="stAppViewContainer"]' in css
    assert '[data-testid="stMain"]' in css
    assert ".block-container" in css
    assert "visibility: visible !important" in css


def test_canary_labels_are_unique_and_documented():
    labels = [
        "FGL_P0_A_AFTER_AUTH",
        "FGL_P0_B_BEFORE_ROUTE",
        "FGL_P0_C_DASHBOARD_ENTER",
        "FGL_P0_D_FIRST_ELEMENT_RETURNED",
        "FGL_P0_E_DASHBOARD_RETURNED",
        "FGL_P0_CANARY_AFTER_AUTH",
        "FGL_P0_TEST_BUTTON",
        "FGL_P0_DASHBOARD_NATIVE_ELEMENT",
    ]
    assert len(labels) == len(set(labels))
    app_src = open("app.py", encoding="utf-8").read()
    for label in labels:
        assert label in app_src, label
