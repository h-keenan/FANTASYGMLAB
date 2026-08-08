"""Contracts for executive header responsive geometry (#185 family)."""

from __future__ import annotations

from pathlib import Path

from modules import notification_center
from modules.application_shell_styles import APPLICATION_SHELL_CSS
from modules.executive_command_header_styles import (
    COMMAND_COLUMN_WEIGHTS,
    EXECUTIVE_COMMAND_HEADER_CSS,
)


ROOT = Path(__file__).resolve().parents[1]


def test_command_column_weights_favor_league_without_extreme_skew():
    assert COMMAND_COLUMN_WEIGHTS == (1.35, 1.05, 0.9)
    assert round(sum(COMMAND_COLUMN_WEIGHTS), 2) == 3.3


def test_alerts_command_label_caps_at_99_plus():
    assert notification_center.alerts_command_label(0) == "Alerts"
    assert notification_center.alerts_command_label(1) == "Alerts (1)"
    assert notification_center.alerts_command_label(12) == "Alerts (12)"
    assert notification_center.alerts_command_label(99) == "Alerts (99)"
    assert notification_center.alerts_command_label(100) == "Alerts (99+)"
    assert notification_center.alerts_command_label(999) == "Alerts (99+)"


def test_chevron_column_and_flexible_rail_owned_by_command_header_module():
    css = EXECUTIVE_COMMAND_HEADER_CSS
    assert "grid-template-columns: minmax(0, 1fr) 0.75rem !important;" in css
    assert "minmax(min(100%, 28rem), 1fr)" in css
    assert "width: 22.5rem;" not in css
    assert "translateY(" not in css.split("/* Notification Center")[0]
    assert "border-inline-start: 0 !important;" in css


def test_founder_badge_has_max_width_so_it_cannot_starve_commands():
    assert "max-width: 9.75rem;" in APPLICATION_SHELL_CSS
    assert ".dg-executive-shell__title-row .dg-founder-badge" in APPLICATION_SHELL_CSS


def test_harness_and_production_share_command_column_weights():
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "COMMAND_COLUMN_WEIGHTS" in harness
    assert "COMMAND_COLUMN_WEIGHTS" in app
    assert "header-geometry" in harness
    assert "HEADER_LEAGUE_FIXTURES" in harness


def test_geometry_contract_doc_exists():
    doc = (ROOT / "docs" / "executive-header-responsive-geometry.md").read_text(
        encoding="utf-8"
    )
    for heading in (
        "Root cause",
        "Responsive contract",
        "Breakpoint behavior",
        "Command sizing",
        "Chevron",
        "CSS ownership",
        "Performance",
        "Remaining limitations",
    ):
        assert heading in doc
    assert "da23e67dea9b2fffa488157631893868d9b8cf33" in doc
