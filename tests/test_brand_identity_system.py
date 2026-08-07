"""FantasyGM Lab brand identity system contracts."""

from __future__ import annotations

from pathlib import Path

from modules import brand_identity


ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"
DOC = ROOT / "docs" / "fantasygm-lab-brand-identity.md"


def test_brand_doc_and_selected_candidate():
    text = DOC.read_text(encoding="utf-8")
    assert "Command Plate" in text
    assert "candidates" in text.casefold()
    assert brand_identity.SELECTED_MARK_CANDIDATE == "a-command-plate"
    assert len(brand_identity.MARK_CANDIDATES) == 3


def test_asset_inventory_exists():
    required = (
        "fantasygm-lab-mark.svg",
        "fantasygm-lab-mark-light.svg",
        "fantasygm-lab-primary.svg",
        "fantasygm-lab-primary-light.svg",
        "fantasygm-lab-founder-beta.svg",
        "fantasygm-lab-mark.png",
        "share-card-mark.png",
        "favicon.png",
        "favicon.ico",
        "og-founder-beta.png",
        "candidates/a-command-plate.svg",
        "candidates/b-signal-grid.svg",
        "candidates/c-ledger-bars.svg",
    )
    for relative in required:
        path = BRAND / relative
        assert path.exists(), relative
        assert path.stat().st_size > 40, relative


def test_brand_api_paths_and_helpers():
    assert brand_identity.PRODUCT_NAME == "FantasyGM Lab"
    assert brand_identity.PRODUCT_DOMAIN == "fantasygmlab.com"
    assert brand_identity.asset_path("brand_compact").name == "fantasygm-lab-mark.svg"
    assert brand_identity.asset_path("share_card_mark").exists()
    html = brand_identity.mark_img_html(size_px=28)
    assert "dg-brand-plate" in html
    assert "FantasyGM Lab" in html or "aria-label='FantasyGM Lab'" in html
    assert brand_identity.asset_path("brand_compact").read_text(encoding="utf-8").startswith("<svg")
    assert "FantasyGM Lab" in brand_identity.founder_beta_badge_html(compact=False)
    assert "Founder Beta" in brand_identity.founder_beta_badge_html(compact=True)
    assert brand_identity.GM_ORB_LABEL == "GM"
    assert "Open GM menu" in brand_identity.GM_ORB_ARIA_LABEL


def test_shell_and_startup_use_mark_assets():
    shell = (ROOT / "modules" / "application_shell.py").read_text(encoding="utf-8")
    startup = (ROOT / "modules" / "startup_coordinator.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "mark_img_html" in shell
    assert "mark_img_html" in startup
    assert "page_icon_path()" in app
    # No scattered DynastyGM customer brand string in shell.
    assert "DynastyGM" not in shell


def test_share_cards_consume_brand_mark_bytes():
    from modules import share_card_renderer
    from modules import share_recommendation_cards as share

    mark = brand_identity.share_card_mark_png_bytes()
    assert mark.startswith(b"\x89PNG")
    card = share.build_trade_share_card(
        {
            "trade_gain": 10,
            "trade_confidence_label": "High",
            "reasoning_summary": "Canonical reason only.",
            "send_assets": [{"name": "A", "player_id": "1"}],
            "receive_assets": [{"name": "B", "player_id": "2"}],
        }
    )
    png = share_card_renderer.render_share_card_png(card, portraits={})
    assert png.startswith(b"\x89PNG")


def test_no_football_logic_in_brand_modules():
    brand = (ROOT / "modules" / "brand_identity.py").read_text(encoding="utf-8")
    assert "Presentation only" in brand
    assert "valuation" not in brand.casefold()
    assert "recommendation score" not in brand.casefold()


def test_customer_facing_name_is_fantasygm_lab():
    assert "Fantasy GM" not in brand_identity.PRODUCT_NAME
    assert brand_identity.PRODUCT_NAME == "FantasyGM Lab"
