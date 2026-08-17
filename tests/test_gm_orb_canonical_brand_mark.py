"""GM floating control uses the canonical compact FGL Arc Monogram."""

from __future__ import annotations

from pathlib import Path

from modules import brand_identity
from modules.app_styles import APP_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_gm_orb_uses_compact_mark_asset_api():
    assert brand_identity.GM_ORB_MARK_ASSET_KEY == "mark_compact"
    path = brand_identity.asset_path("mark_compact")
    assert path.name == "fantasygm-lab-mark-compact.svg"
    assert path.exists()
    assert brand_identity.gm_orb_mark_asset_bytes() == path.stat().st_size
    assert brand_identity.gm_orb_mark_asset_bytes() < 2_048
    uri = brand_identity.gm_orb_mark_data_uri()
    assert uri.startswith("data:image/svg+xml,")
    assert "FGL" in path.read_text(encoding="utf-8")
    assert "#0F1114" in path.read_text(encoding="utf-8")


def test_gm_orb_trigger_html_scopes_mark_without_global_css_base64():
    html = brand_identity.gm_orb_floating_trigger_html()
    assert "mobile-gm-floating-trigger-marker" in html
    assert "background-size:contain" in html
    assert "background-origin:content-box" in html
    assert "data:image/svg+xml," in html
    assert "fantasygm-lab-mark-compact.svg" not in APP_CSS
    assert brand_identity.gm_orb_mark_data_uri() not in APP_CSS
    assert "button::before" in APP_CSS


def test_gm_orb_button_uses_accessible_name_not_visible_gm_text():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    shell = app.split("def render_mobile_navigation_shell", 1)[1].split(
        "def safe_pick_value", 1
    )[0]
    assert "gm_orb_floating_trigger_html()" in shell
    assert "GM_ORB_ARIA_LABEL" in shell
    assert brand_identity.GM_ORB_ARIA_LABEL == "Open GM menu"
    assert "brand_identity.GM_ORB_LABEL," not in shell


def test_gm_orb_css_hides_text_and_keeps_touch_target():
    assert "color: transparent !important" in APP_CSS
    assert "min-width: var(--touch-target-min) !important" in APP_CSS
    assert ".mobile-gm-orb-hint" in APP_CSS
    brand_css = (ROOT / "modules" / "brand_identity_styles.py").read_text(encoding="utf-8")
    assert "GM Orb chrome is owned by MOBILE_INTERACTION_OVERLAY_CSS" in brand_css
    assert "st-key-mobile_gm_sheet_trigger_" not in brand_css
    from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS

    needle = (
        '.mobile-gm-floating-trigger-marker) [data-testid="stButton"]'
    )
    start = MOBILE_INTERACTION_OVERLAY_CSS.index(needle)
    end = MOBILE_INTERACTION_OVERLAY_CSS.index("mobile-gm-sheet-marker", start)
    gm_block = MOBILE_INTERACTION_OVERLAY_CSS[start:end]
    assert "writing-mode" not in gm_block
    assert "border-radius: 50%" in gm_block
    assert "font-size: 0" in gm_block
    assert "text-transform: uppercase" not in gm_block
    # #244: orb geometry must not use unscoped descendant :has().
    assert (
        'stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker)'
        not in MOBILE_INTERACTION_OVERLAY_CSS
    )
    assert (
        'stVerticalBlock"]:has(> div[data-testid="stElementContainer"] '
        ".mobile-gm-floating-trigger-marker)"
        in MOBILE_INTERACTION_OVERLAY_CSS
    )

def test_gm_orb_contract_doc_exists():
    doc = (ROOT / "docs" / "gm-orb-canonical-brand-mark.md").read_text(encoding="utf-8")
    assert "mark_compact" in doc
    assert "Open GM menu" in doc
    assert "background-size: contain" in doc
