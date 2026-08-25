"""Production-equivalent CSS/DOM ownership proof for GM Orb and PQV hero."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from modules.app_styles import APP_CSS
from modules.player_images import get_player_headshot_url, headshot_content_type
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.semantic_glyphs import DESTINATION_CONCEPT, gm_orb_row_css, glyph_mask_data_uri
from scripts.css_dom_ownership_fixture import (
    REPRESENTATIVE_PLAYERS,
    headshot_facts,
    ownership_document,
    sleeper_fixture_bytes,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "css-dom-ownership"


def _alpha_bbox(payload: bytes) -> dict[str, float | int | str]:
    image = Image.open(__import__("io").BytesIO(payload)).convert("RGBA")
    width, height = image.size
    pixels = image.load()
    min_x, min_y, max_x, max_y = width, height, -1, -1
    opaque = 0
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] > 16:
                opaque += 1
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    return {
        "mode": image.mode,
        "format": str(image.format or "PNG"),
        "natural_width": width,
        "natural_height": height,
        "opaque_pct": round(100 * opaque / (width * height), 2),
        "left_margin": min_x,
        "right_margin": width - max_x - 1,
        "top_margin": min_y,
        "bottom_margin": height - max_y - 1,
        "bbox_w": max_x - min_x + 1,
        "bbox_h": max_y - min_y + 1,
    }


def test_real_sleeper_artwork_is_wide_png_not_synthetic_square_jpeg():
    facts = []
    for sleeper_id, name, _pos, _team, _ini in REPRESENTATIVE_PLAYERS:
        payload = sleeper_fixture_bytes(sleeper_id)
        assert headshot_content_type(payload) == "image/png"
        assert payload.startswith(b"\x89PNG")
        bbox = _alpha_bbox(payload)
        row = {"name": name, "cdn": get_player_headshot_url(sleeper_id), **headshot_facts(sleeper_id), **bbox}
        facts.append(row)
        assert bbox["natural_width"] >= 300
        assert bbox["natural_height"] >= 240
        assert bbox["natural_width"] != 240 or bbox["natural_height"] != 240
        assert bbox["bottom_margin"] == 0
        assert bbox["left_margin"] > 0
        assert bbox["opaque_pct"] < 55
    tracy = next(item for item in facts if item["sleeper_id"] == "11655")
    assert tracy["natural_width"] == 350
    assert tracy["natural_height"] == 254
    assert tracy["cdn"] == "https://sleepercdn.com/content/nfl/players/11655.jpg"


def test_dialog_css_no_longer_locks_pqv_hero_to_58px():
    assert "div[data-testid=\"stDialog\"] .player-detail-avatar:not(.player-quick-view-avatar)" in APP_CSS
    assert "div[data-testid=\"stDialog\"] .player-detail-avatar.player-quick-view-avatar img" not in APP_CSS
    assert "div[data-testid=\"stDialog\"] .player-quick-view-header-band .player-detail-avatar img" not in APP_CSS
    mobile = APP_CSS.split("@media (max-width: 900px)", 2)[-1]
    assert ".player-detail-avatar:not(.player-quick-view-avatar)" in mobile
    assert ".player-quick-view-avatar img" not in APP_CSS.split(".player-avatar img", 1)[-1][:800]
    pqv = PLAYER_QUICK_VIEW_CSS.replace(" ", "")
    assert "--pqv-portrait-size:clamp(3.5rem,16vw,4.5rem)" in pqv
    assert "transform:scale(var(--dg-headshot-scale,1.65))!important" in pqv
    assert "[data-player-id" not in PLAYER_QUICK_VIEW_CSS
    assert "11655" not in PLAYER_QUICK_VIEW_CSS
    assert "tyrone" not in PLAYER_QUICK_VIEW_CSS.casefold()


def test_orb_overlay_architecture_is_gone():
    css = gm_orb_row_css()
    assert "button::before" in css
    assert "dg-gm-route-glyph" not in css
    assert "position:absolute" not in css
    assert "padding-inline-start:calc(var(--dg-orb-glyph-inset)" not in css
    for key in ("dashboard", "my_team", "trade_hub", "rankings", "players"):
        assert f"st-key-mobile_sheet_nav_{key}" in css
        assert glyph_mask_data_uri(DESTINATION_CONCEPT[key]) in css
    overlay = (ROOT / "modules" / "mobile_interaction_overlay_styles.py").read_text(encoding="utf-8")
    assert "padding-inline-start: calc(var(--dg-orb-glyph-inset) + var(--dg-orb-glyph-slot)" not in overlay
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "route_row_glyph_html(page.key)" not in app


def _measure(page) -> dict:
    return page.evaluate(
        """() => {
          const frame = document.querySelector('.pqv-hero-portrait');
          const inner = frame && frame.querySelector('.player-quick-view-avatar, .dg-player-headshot');
          const img = frame && frame.querySelector('img, .dg-player-headshot-image');
          const fallback = frame && frame.querySelector('.dg-player-headshot-fallback');
          const styles = [...document.querySelectorAll('style')].map(n => n.textContent || '');
          const pqvInjected = styles.some(t => t.includes('--pqv-portrait-size'));
          const appInjected = styles.some(t => t.includes('.dg-player-headshot--profile'));
          const pqvIndex = styles.findIndex(t => t.includes('--pqv-portrait-size'));
          const appIndex = styles.findIndex(t => t.includes('.dg-player-headshot--profile'));
          const fr = frame ? frame.getBoundingClientRect() : null;
          const ir = inner ? inner.getBoundingClientRect() : null;
          const imgCs = img ? getComputedStyle(img) : null;
          const innerCs = inner ? getComputedStyle(inner) : null;
          const frameCs = frame ? getComputedStyle(frame) : null;
          const button = document.querySelector('div[class*="st-key-mobile_sheet_nav_dashboard"] button');
          const label = button && (button.querySelector('p') || button);
          const before = button ? getComputedStyle(button, '::before') : null;
          const after = button ? getComputedStyle(button, '::after') : null;
          const br = button ? button.getBoundingClientRect() : null;
          const lr = label ? label.getBoundingClientRect() : null;
          const padL = button ? parseFloat(getComputedStyle(button).paddingLeft) || 0 : 0;
          const beforeW = before ? parseFloat(before.width) || 0 : 0;
          const beforeGap = before ? parseFloat(before.marginRight) || 0 : 0;
          const glyphRight = br ? br.left + padL + beforeW : 0;
          const trade = document.querySelector('.trade-summary-assets .dg-compact-asset--standard .dg-compact-asset-avatar, .trade-summary-assets .dg-compact-asset--standard .dg-player-headshot');
          const tr = trade ? trade.getBoundingClientRect() : null;
          const dash = document.querySelector('[data-dashboard-portraits="1"] .dg-compact-asset--standard .dg-player-headshot');
          const dashImg = dash && dash.querySelector('img, .dg-player-headshot-image');
          const scan = document.querySelector('[data-dashboard-portraits="1"] .scan-card-avatar');
          const scanImg = scan && scan.querySelector('img, .dg-player-headshot-image');
          const rowAv = document.querySelector('[data-dashboard-portraits="1"] .compact-player-avatar');
          const rowImg = rowAv && rowAv.querySelector('img, .dg-player-headshot-image');
          const dashCs = dashImg ? getComputedStyle(dashImg) : null;
          const scanCs = scanImg ? getComputedStyle(scanImg) : null;
          const rowCs = rowImg ? getComputedStyle(rowImg) : null;
          const dr = dash ? dash.getBoundingClientRect() : null;
          const portrait = (node, cs, box) => node && cs && box && {
            tree: node.parentElement ? node.parentElement.className : '',
            visibleTag: node.tagName,
            visibleClass: node.className,
            w: +box.width.toFixed(1),
            h: +box.height.toFixed(1),
            width: cs.width,
            height: cs.height,
            transform: cs.transform,
            objectPosition: cs.objectPosition,
            objectFit: cs.objectFit,
          };
          return {
            pqvInjected,
            appInjected,
            pqvAfterApp: pqvIndex > appIndex && pqvIndex >= 0,
            overlayGlyph: !!document.querySelector('.dg-gm-route-glyph'),
            tree: frame ? frame.innerHTML.slice(0, 800) : '',
            visibleTag: img && img.tagName,
            visibleClass: img && img.className,
            fallbackHidden: fallback ? getComputedStyle(fallback).visibility : null,
            frame: fr && {w: +fr.width.toFixed(1), h: +fr.height.toFixed(1)},
            inner: ir && {w: +ir.width.toFixed(1), h: +ir.height.toFixed(1), top: +(ir.top - fr.top).toFixed(1)},
            imgNatural: img && {w: img.naturalWidth, h: img.naturalHeight},
            imgComputed: imgCs && {
              width: imgCs.width,
              height: imgCs.height,
              transform: imgCs.transform,
              objectPosition: imgCs.objectPosition,
              objectFit: imgCs.objectFit,
              overflow: imgCs.overflow,
              position: imgCs.position,
              inset: [imgCs.top, imgCs.right, imgCs.bottom, imgCs.left].join('/'),
            },
            innerComputed: innerCs && {width: innerCs.width, height: innerCs.height},
            frameScale: frameCs && frameCs.getPropertyValue('--dg-headshot-scale').trim(),
            orb: button && {
              display: getComputedStyle(button).display,
              justify: getComputedStyle(button).justifyContent,
              beforeContent: before.content,
              beforeWidth: before.width,
              beforeMask: before.webkitMaskImage || before.maskImage,
              afterContent: after.content,
              labelLeft: lr && +lr.left.toFixed(1),
              glyphRight: +glyphRight.toFixed(1),
              gap: lr ? +(lr.left - glyphRight).toFixed(1) : null,
              flex: getComputedStyle(button).display,
            },
            trade: tr && {w: +tr.width.toFixed(1), h: +tr.height.toFixed(1)},
            dashboard: portrait(dashImg, dashCs, dr),
            scanCard: portrait(scanImg, scanCs, scan ? scan.getBoundingClientRect() : null),
            compactRow: portrait(rowImg, rowCs, rowAv ? rowAv.getBoundingClientRect() : null),
          };
        }"""
    )


def _run_browser(engine: str, width: int, player_id: str = "11655") -> dict:
    from playwright.sync_api import sync_playwright

    html = ownership_document(player_id=player_id)
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        launcher = getattr(playwright, engine)
        try:
            browser = launcher.launch(headless=True)
        except Exception as exc:  # pragma: no cover - engine availability
            return {"engine": engine, "error": str(exc)}
        page = browser.new_page(viewport={"width": width, "height": 844})
        page.set_content(html, wait_until="load")
        page.wait_for_function(
            "() => { const img = document.querySelector('.pqv-hero-portrait img'); const dash = document.querySelector('[data-dashboard-portraits=\"1\"] img'); return img && img.naturalWidth > 0 && dash && dash.naturalWidth > 0; }",
            timeout=15_000,
        )
        measured = _measure(page)
        shot_root = OUT / f"{engine}-{width}-{player_id}"
        page.locator(".pqv-hero-portrait").screenshot(path=str(OUT / f"{engine}-{width}-{player_id}-pqv.png"))
        page.locator('div[class*="st-key-mobile_sheet_nav_dashboard"] button').screenshot(
            path=str(OUT / f"{engine}-{width}-orb-dashboard.png")
        )
        if width == 390 and player_id == "11655":
            page.screenshot(path=str(OUT / f"{engine}-{width}-full.png"), full_page=False)
        browser.close()
        measured["engine"] = engine
        measured["width"] = width
        measured["shot"] = str(shot_root)
        return measured


def test_production_equivalent_computed_styles_chromium_390():
    measured = _run_browser("chromium", 390, "11655")
    assert measured.get("error") is None, measured
    assert measured["pqvInjected"] is True
    assert measured["appInjected"] is True
    assert measured["pqvAfterApp"] is True
    assert measured["overlayGlyph"] is False
    assert measured["visibleTag"] == "IMG"
    assert "dg-player-headshot-image" in (measured["visibleClass"] or "")
    assert measured["imgNatural"]["w"] == 350
    assert measured["imgNatural"]["h"] == 254
    frame_w = measured["frame"]["w"]
    frame_h = measured["frame"]["h"]
    assert abs(frame_w - frame_h) < 1.5
    assert frame_w > 70
    inner_w = measured["inner"]["w"]
    assert abs(inner_w - frame_w) < 2, measured["inner"]
    assert abs(measured["inner"]["top"]) < 2
    img_w = float(str(measured["imgComputed"]["width"]).replace("px", ""))
    assert abs(img_w - frame_w) < 2, measured["imgComputed"]
    assert "58px" not in measured["imgComputed"]["width"]
    assert "1.65" in measured["imgComputed"]["transform"]
    assert "22%" in measured["imgComputed"]["objectPosition"]
    assert measured["imgComputed"]["objectFit"] == "cover"
    orb = measured["orb"]
    assert orb["display"] == "flex"
    assert orb["justify"] == "flex-start"
    assert orb["beforeContent"] in {'""', "''"} or orb["beforeContent"] == '""'
    assert "data:image/svg+xml" in (orb["beforeMask"] or "")
    assert orb["gap"] is not None and 4 <= orb["gap"] <= 24
    assert "CURRENT" in orb["afterContent"]
    assert abs(measured["trade"]["w"] - 52) <= 2
    assert abs(measured["trade"]["h"] - 52) <= 2
    dash = measured["dashboard"]
    assert dash, measured
    assert dash["visibleTag"] == "IMG"
    assert "dg-player-headshot-image" in (dash["visibleClass"] or "")
    assert abs(dash["w"] - 52) <= 3, dash
    assert abs(dash["h"] - 52) <= 3, dash
    assert "1.16" in dash["transform"] or "matrix" in dash["transform"]
    assert "18%" in dash["objectPosition"]
    assert dash["objectFit"] == "cover"
    assert "none" not in (dash["transform"] or "").casefold() or "matrix" in dash["transform"]
    scan = measured["scanCard"]
    assert scan and scan["objectFit"] == "cover"
    assert "18%" in scan["objectPosition"]
    row = measured["compactRow"]
    assert row and "dg-player-headshot-image" in (row["visibleClass"] or "")
    assert "18%" in row["objectPosition"]


def test_real_player_computed_styles_cover_several_headshots():
    for sleeper_id, _name, _pos, _team, _ini in REPRESENTATIVE_PLAYERS:
        measured = _run_browser("chromium", 390, sleeper_id)
        assert measured.get("error") is None, measured
        assert measured["imgNatural"]["w"] >= 300
        img_w = float(str(measured["imgComputed"]["width"]).replace("px", ""))
        assert img_w > 70
        assert "1.65" in measured["imgComputed"]["transform"]


def test_webkit_390_if_available():
    measured = _run_browser("webkit", 390, "11655")
    if measured.get("error") and "Executable doesn't exist" in str(measured.get("error")):
        return
    assert measured.get("error") is None, measured
    assert "1.65" in measured["imgComputed"]["transform"]
    assert measured["overlayGlyph"] is False
    assert "data:image/svg+xml" in (measured["orb"]["beforeMask"] or "")
    img_w = float(str(measured["imgComputed"]["width"]).replace("px", ""))
    assert img_w > 70
    assert abs(measured["inner"]["w"] - measured["frame"]["w"]) < 2
    dash = measured.get("dashboard") or {}
    assert dash.get("objectFit") == "cover"
    assert "18%" in (dash.get("objectPosition") or "")
    assert abs(dash.get("w", 0) - 52) <= 4


def test_chromium_1440_keeps_filled_hero_and_standard_trade_portrait():
    measured = _run_browser("chromium", 1440, "11655")
    assert measured.get("error") is None, measured
    assert "1.65" in measured["imgComputed"]["transform"]
    assert abs(measured["inner"]["w"] - measured["frame"]["w"]) < 2
    assert abs(measured["trade"]["w"] - 52) <= 2
    dash = measured.get("dashboard") or {}
    assert abs(dash.get("w", 0) - 52) <= 4
    assert "18%" in (dash.get("objectPosition") or "")
