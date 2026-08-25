"""Regression contracts for header + legal-link geometry owners."""

from __future__ import annotations

import re
from pathlib import Path

from modules.app_styles import APP_CSS
from modules.application_shell_styles import APPLICATION_SHELL_CSS
from modules.component_family_styles import COMPONENT_FAMILY_CSS
from modules.executive_command_header_styles import EXECUTIVE_COMMAND_HEADER_CSS


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
HARNESS = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
MIDFILE = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
SHELL_HTML = (ROOT / "modules" / "application_shell.py").read_text(encoding="utf-8")
BRAND = (ROOT / "modules" / "brand_identity_styles.py").read_text(encoding="utf-8")


def test_command_cells_share_fill_height_and_padding_contract():
    css = EXECUTIVE_COMMAND_HEADER_CSS
    trigger = css.split("/* Notification Center")[0]
    assert "height: 100% !important" in trigger
    assert "min-height: var(--touch-target-min) !important" in trigger
    assert "padding-block: 0 !important" in trigger
    assert "padding-inline: var(--space-sm) !important" in trigger
    assert trigger.count("padding-inline: var(--space-sm) !important") >= 1
    # Shared trigger rule — no League/Alerts/You padding forks.
    assert "st-key-executive_command_cell_league" not in trigger or "padding" not in (
        trigger.split("st-key-executive_command_cell_league")[1][:80]
        if "st-key-executive_command_cell_league" in trigger
        else ""
    )
    assert "translateY(" not in trigger
    assert "top: auto !important" in trigger


def test_streamlit_column_gap_and_alignment_do_not_skew_commands():
    topbar = APP[
        APP.index("def render_platform_topbar(") : APP.index("def _query_param_page(")
    ]
    assert "gap=None" in topbar
    assert 'vertical_alignment="bottom"' in topbar
    assert 'vertical_alignment="stretch"' not in topbar
    assert 'gap="small"' not in topbar
    assert "gap=None" in HARNESS
    assert 'vertical_alignment="bottom"' in HARNESS
    assert 'vertical_alignment="stretch"' not in HARNESS


def test_identity_shell_owns_block_centerline_geometry():
    assert "dg-executive-shell__meta" in SHELL_HTML
    assert "grid-template-columns: minmax(0, auto) minmax(0, 1fr)" in APPLICATION_SHELL_CSS
    assert "grid-row: 1 / 3" not in APPLICATION_SHELL_CSS
    assert ".dg-executive-shell__meta" in APPLICATION_SHELL_CSS
    assert "height: 100%" in APPLICATION_SHELL_CSS
    # Brand module must not re-own the brand square display model.
    assert ".dg-executive-shell__brand{align-items:center;display:inline-flex" not in BRAND.replace(
        " ", ""
    ).replace("\n", "")


def test_legal_footer_has_one_canonical_family_owner():
    family = COMPONENT_FAMILY_CSS
    assert ".legal-footer-link{" in family.replace(" ", "") or ".legal-footer-link{" in family
    assert "padding-block:var(--space-xs)!important" in family.replace(" ", "")
    assert "padding-inline:var(--space-sm)!important" in family.replace(" ", "")
    assert "display:inline-flex!important" in family.replace(" ", "")
    assert "justify-content:center" in family.replace(" ", "")
    # Subordinate hover — not CTA fill.
    assert "legal-footer-link:hover{background:transparent!important" in family.replace(" ", "")
    assert "transform:none!important" in family.replace(" ", "")
    # Midfile duplicate removed.
    assert re.search(r"^\.legal-footer-link\s*\{", MIDFILE, re.M) is None
    assert re.search(r"^\.legal-footer-links\s*\{", MIDFILE, re.M) is None
    assert re.search(r"^\.legal-footer-link-active\s*\{", MIDFILE, re.M) is None
    # Mobile CTA left-align must not capture legal links.
    assert ".legal-footer-links .legal-footer-link," not in MIDFILE
    assert "\n    .legal-footer-link,\n" not in MIDFILE


def test_legal_family_is_early_component_owner_not_late_override():
    assert COMPONENT_FAMILY_CSS in APP_CSS
    assert APP_CSS.index(COMPONENT_FAMILY_CSS) < APP_CSS.index("Legal footer family owned by COMPONENT_FAMILY_CSS")
    # No late APP_CSS append inventing a second legal owner.
    after_family = APP_CSS.split(COMPONENT_FAMILY_CSS, 1)[1]
    late_legal_rules = re.findall(
        r"\.legal-footer-link\s*\{[^}]+\}", after_family
    )
    assert late_legal_rules == []


def test_header_command_css_forbids_per_control_translate_offsets():
    trigger = EXECUTIVE_COMMAND_HEADER_CSS.split("/* Notification Center")[0]
    for needle in ("translateY(", "translateX(", "margin-top:", "margin-bottom:", "top: 0", "top:0"):
        assert needle not in trigger


STREAMLIT_COLUMN_VERTICAL_ALIGNMENTS = frozenset({"top", "center", "bottom", "distribute"})


def test_st_columns_never_use_unsupported_vertical_alignment():
    """StreamlitInvalidVerticalAlignmentError if a value outside the API set is passed."""

    pattern = re.compile(
        r"vertical_alignment\s*=\s*(['\"])(?P<value>[^'\"]+)\1",
        re.M,
    )
    offenders: list[str] = []
    scan_roots = (ROOT / "app.py", ROOT / "modules", ROOT / "scripts")
    files: list[Path] = []
    files.append(ROOT / "app.py")
    files.extend((ROOT / "modules").rglob("*.py"))
    files.extend((ROOT / "scripts").rglob("*.py"))
    for path in files:
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            value = match.group("value")
            if value not in STREAMLIT_COLUMN_VERTICAL_ALIGNMENTS:
                offenders.append(f"{path.relative_to(ROOT)}:{value}")
    assert offenders == []
