"""CSS / protobuf headroom recovery contracts."""

from __future__ import annotations

import re
from pathlib import Path

from modules.app_styles import APP_CSS, _APP_CSS_MIDFILE
from modules.component_family_styles import COMPONENT_FAMILY_CSS
from modules.css_ship import ship_css
from modules.dense_list_styles import DENSE_LIST_CSS
from modules.design_tokens import DESIGN_TOKEN_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS


ROOT = Path(__file__).resolve().parents[1]

SCOPED = (
    'stVerticalBlock"]:has(> div[data-testid="stElementContainer"] '
    ".mobile-gm-floating-trigger-marker)"
)
UNSCOPED = 'stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker)'

RETIRED_FAMILIES = (
    ".dg-application-workspace",
    ".dg-ops-rail",
    ".dg-workspace-page-title",
    ".trade-score-card",
    ".trade-why-grid",
    ".trade-explain-card",
    ".app-glass-panel",
    ".dg-glass-panel",
    ".app-chip",
    ".app-empty-state",
    ".app-card",
    ".app-section",
)


def test_app_css_budget_recovered():
    assert len(APP_CSS) < 390_000
    assert len(APP_CSS) < 418_220


def test_canonical_css_ordering_preserved():
    assert APP_CSS.index(DESIGN_TOKEN_CSS) < APP_CSS.index(COMPONENT_FAMILY_CSS)
    assert APP_CSS.index(COMPONENT_FAMILY_CSS) < APP_CSS.index(DENSE_LIST_CSS)
    assert APP_CSS.index(DENSE_LIST_CSS) < APP_CSS.index(ship_css(_APP_CSS_MIDFILE))
    assert APP_CSS.index(ship_css(_APP_CSS_MIDFILE)) < APP_CSS.index(
        MOBILE_INTERACTION_OVERLAY_CSS
    )
    source = (ROOT / "modules" / "app_styles.py").read_text(encoding="utf-8")
    assert source.rindex("MOBILE_INTERACTION_OVERLAY_CSS") > source.index(
        "EXECUTIVE_DESIGN_UNIFY_CSS"
    )


def test_midfile_is_ship_compacted():
    shipped = ship_css(_APP_CSS_MIDFILE)
    assert shipped in APP_CSS
    assert len(shipped) < len(_APP_CSS_MIDFILE)


def test_retired_dead_families_stay_gone():
    for selector in RETIRED_FAMILIES:
        assert selector not in APP_CSS


def test_live_degraded_and_dense_contracts_remain():
    assert ".app-degraded-state" in APP_CSS
    assert "dg-dense-row" in APP_CSS or "dg-ranked-row" in APP_CSS
    assert DENSE_LIST_CSS in APP_CSS


def test_has_selectors_forbid_unscoped_root_collapse():
    assert SCOPED in APP_CSS
    assert SCOPED in MOBILE_INTERACTION_OVERLAY_CSS
    assert UNSCOPED not in APP_CSS
    assert UNSCOPED not in MOBILE_INTERACTION_OVERLAY_CSS
    # No stVerticalBlock :has( without direct-child marker scoping.
    unscoped = re.findall(
        r'div\[data-testid="stVerticalBlock"\]:has\((?!>)',
        APP_CSS,
    )
    assert unscoped == []


def test_token_aliases_still_owned_by_design_tokens():
    assert "--radius-panel" in DESIGN_TOKEN_CSS
    assert "--dg-radius-card: var(--radius-panel)" in APP_CSS
    assert COMPONENT_FAMILY_CSS in APP_CSS


def test_audit_doc_exists():
    assert (ROOT / "docs" / "css-protobuf-headroom-recovery.md").exists()
