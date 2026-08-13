"""FantasyGM Lab brand identity system contracts."""

from __future__ import annotations

from pathlib import Path

from modules import brand_identity


ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"
DOC = ROOT / "docs" / "fantasygm-lab-brand-identity.md"


def test_brand_doc_locks_permanent_mark():
    text = DOC.read_text(encoding="utf-8")
    assert "FGL Arc Monogram" in text
    assert "command-plate" in text  # archived / legacy reference
    assert "Trajectory motif usage" in text
    assert "Product-semantic separation" in text
    assert brand_identity.BRAND_MARK_NAME == "FGL Arc Monogram"
    assert brand_identity.BRAND_MARK_GEOMETRY == "fgl-arc-monogram"
    assert brand_identity.BRAND_MARK_LEGACY_GEOMETRY == "command-plate"


def test_asset_inventory_exists():
    required = (
        "fantasygm-lab-mark.svg",
        "fantasygm-lab-mark-light.svg",
        "fantasygm-lab-mark-dark.svg",
        "fantasygm-lab-mark-mono-light.svg",
        "fantasygm-lab-mark-compact.svg",
        "fantasygm-lab-primary.svg",
        "fantasygm-lab-primary-light.svg",
        "fantasygm-lab-primary-dark.svg",
        "fantasygm-lab-founder-beta.svg",
        "fantasygm-lab-mark.png",
        "share-card-mark.png",
        "favicon.png",
        "favicon.ico",
        "og-founder-beta.png",
        "icons/icon-512.png",
        "icons/icon-256.png",
        "icons/icon-192.png",
        "icons/icon-180.png",
        "icons/icon-128.png",
        "icons/favicon-64.png",
        "icons/favicon-32.png",
        "icons/favicon-16.png",
        "archive/b-signal-grid.svg",
        "archive/c-ledger-bars.svg",
        "archive/a-command-plate-source.svg",
        "archive/command-plate/README.md",
        "archive/README.md",
    )
    for relative in required:
        path = BRAND / relative
        assert path.exists(), relative
        assert path.stat().st_size > 40, relative
    assert not (BRAND / "candidates").exists()


def test_brand_api_paths_and_helpers():
    assert brand_identity.PRODUCT_NAME == "FantasyGM Lab"
    assert brand_identity.PRODUCT_DOMAIN == "fantasygmlab.com"
    assert brand_identity.asset_path("brand_compact").name == "fantasygm-lab-mark.svg"
    assert brand_identity.asset_path("mark_compact").name == "fantasygm-lab-mark-compact.svg"
    assert brand_identity.asset_path("share_card_mark").exists()
    assert brand_identity.asset_path("og_image").exists()
    assert brand_identity.asset_path("favicon").exists()
    assert brand_identity.asset_path("icon_512").exists()
    html = brand_identity.mark_img_html(size_px=28)
    assert "dg-brand-plate" in html
    assert "dg-brand-plate__fgl" in html
    assert "FGL" in html
    assert "FantasyGM Lab" in html or "aria-label='FantasyGM Lab'" in html
    assert brand_identity.asset_path("brand_compact").read_text(encoding="utf-8").startswith("<svg")
    assert "FGL" in brand_identity.asset_path("brand_compact").read_text(encoding="utf-8")
    assert "FantasyGM Lab" in brand_identity.founder_beta_badge_html(compact=False)
    assert "Founder Beta" in brand_identity.founder_beta_badge_html(compact=True)
    assert brand_identity.GM_ORB_LABEL == "GM"
    assert "Open GM menu" in brand_identity.GM_ORB_ARIA_LABEL
    # Trajectory colors are brand constants, not product decision logic
    assert brand_identity.BRAND_TRAJECTORY_ANALYZE == brand_identity.BRAND_ACCENT
    assert "valuation" not in Path(brand_identity.__file__).read_text(encoding="utf-8").casefold()


def test_shell_and_startup_use_mark_assets():
    shell = (ROOT / "modules" / "application_shell.py").read_text(encoding="utf-8")
    startup = (ROOT / "modules" / "startup_coordinator.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    brand = (ROOT / "modules" / "brand_identity.py").read_text(encoding="utf-8")
    assert "mark_img_html" in shell
    assert "mark_img_html" in startup
    assert "page_icon_path()" in app
    assert "DynastyGM" not in shell
    assert "Candidate A" not in brand
    assert "MARK_CANDIDATES" not in brand
    assert "fgl-arc-monogram" in brand


def test_share_cards_consume_brand_mark_bytes():
    from modules import share_card_renderer
    from modules import share_recommendation_cards as share

    mark = brand_identity.share_card_mark_png_bytes()
    assert mark.startswith(b"\x89PNG")
    lockup = brand_identity.share_card_lockup_png_bytes()
    assert lockup.startswith(b"\x89PNG")
    assert len(lockup) >= len(mark)
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


def test_favicon_sizes_exist_and_are_square():
    from PIL import Image

    for name, expected in (("favicon-16.png", 16), ("favicon-32.png", 32), ("favicon.png", 64)):
        path = BRAND / name
        with Image.open(path) as img:
            assert img.size == (expected, expected)


def test_compact_mark_differs_from_large_svg():
    large = (BRAND / "fantasygm-lab-mark.svg").read_text(encoding="utf-8")
    compact = (BRAND / "fantasygm-lab-mark-compact.svg").read_text(encoding="utf-8")
    assert large != compact
    assert "FGL" in compact
    # Compact omits arrowhead polygons used in the large cut
    assert compact.count("<path d=\"M") >= 3 or compact.count("stroke=") >= 3
