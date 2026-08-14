"""Capture post-#315 avatar + share-panel screenshots (Playwright)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.app_styles import APP_CSS
from modules.player_images import get_player_image_url
from modules.player_profile_ui import avatar_html
from modules.trade_detail_styles import TRADE_DETAIL_CSS

OUT = ROOT / "artifacts" / "post-315-ui"


def _page(body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"{APP_CSS}<style>{TRADE_DETAIL_CSS}</style>"
        "<style>body{margin:0;background:#08090b;padding:16px;font-family:system-ui,sans-serif}"
        ".row{align-items:center;display:flex;gap:12px;margin:0 0 16px;color:#eceef2}</style>"
        f"</head><body>{body}</body></html>"
    )


def main() -> int:
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    success = avatar_html(get_player_image_url("4046"), "CL", "compact-player-avatar")
    failed = avatar_html("", "UP", "compact-player-avatar")
    html = _page(
        "<div class='row' id='success'>"
        f"{success}<div><strong>CeeDee Lamb</strong><div>WR · DAL</div></div></div>"
        "<div class='row' id='fallback'>"
        f"{failed}<div><strong>Unknown Player</strong><div>no photo</div></div></div>"
        "<div class='fgl-share-panel' id='share'>"
        "<p class='fgl-share-kicker'>Share Trade Idea</p>"
        "<div class='fgl-share-preview'><div style='background:#15181d;aspect-ratio:9/10;width:100%'></div></div>"
        "</div>"
    )
    path = OUT / "capture.html"
    path.write_text(html, encoding="utf-8")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(path.as_uri(), wait_until="networkidle")
        page.wait_for_timeout(800)
        page.locator("#success").screenshot(path=str(OUT / "roster-photo-success.png"))
        page.locator("#fallback").screenshot(path=str(OUT / "roster-photo-fallback.png"))
        page.set_viewport_size({"width": 1280, "height": 800})
        page.locator("#share").screenshot(path=str(OUT / "share-panel-desktop.png"))
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator("#share").screenshot(path=str(OUT / "share-panel-390.png"))
        browser.close()
    print(f"wrote {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
