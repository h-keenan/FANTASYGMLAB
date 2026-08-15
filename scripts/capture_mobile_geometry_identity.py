"""Capture POST-319 mobile geometry + identity artifacts."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "artifacts" / "mobile-geometry-identity"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_http(url: str, *, timeout: float = 90.0) -> None:
    import urllib.request

    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if int(getattr(response, "status", 200) or 200) < 500:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.4)
    raise RuntimeError(f"harness did not start: {last_error}")


def _write_share_cards() -> dict:
    from PIL import Image

    from modules import share_card_renderer
    from modules import share_recommendation_cards as share

    share.clear_share_cache_for_tests()
    portraits = {
        player_id: share.fetch_portrait_bytes(player_id)
        for player_id in ("11655", "12492", "9225", "12527", "12489")
    }
    tracy_bryant = share.build_trade_share_card(
        {
            "tag": "GET YOUNGER + PICK",
            "trade_gain": 237,
            "my_score": 3503,
            "their_score": 3740,
            "trade_confidence_label": "Low",
            "reasoning_summary": "Canonical share copy for geometry capture.",
            "send_assets": [
                {
                    "asset_type": "player",
                    "name": "Tyrone Tracy",
                    "player_id": "11655",
                    "position": "RB",
                    "team": "NYG",
                }
            ],
            "receive_assets": [
                {
                    "asset_type": "player",
                    "name": "Pat Bryant",
                    "player_id": "12492",
                    "position": "WR",
                    "team": "DEN",
                },
                {"asset_type": "pick", "label": "2027 Round 3", "position": "PICK"},
            ],
        },
        source_surface="trade_hub",
    )
    other = share.build_trade_share_card(
        {
            "tag": "PACKAGE",
            "trade_gain": 180,
            "my_score": 3400,
            "their_score": 3580,
            "trade_confidence_label": "Low",
            "reasoning_summary": "Second portrait-shape share card.",
            "send_assets": [
                {
                    "asset_type": "player",
                    "name": "Tank Bigsby",
                    "player_id": "9225",
                    "position": "RB",
                    "team": "PHI",
                }
            ],
            "receive_assets": [
                {
                    "asset_type": "player",
                    "name": "Ashton Jeanty",
                    "player_id": "12527",
                    "position": "RB",
                    "team": "LV",
                }
            ],
        },
        source_surface="trade_hub",
    )
    started = time.perf_counter()
    png = share_card_renderer.render_share_card_png(tracy_bryant, portraits=portraits)
    other_png = share_card_renderer.render_share_card_png(other, portraits=portraits)
    render_ms = (time.perf_counter() - started) * 1000
    phone = share_card_renderer.phone_display_png(png, 390)
    (OUT / "share-tracy-bryant-2027r3-full.png").write_bytes(png)
    (OUT / "share-tracy-bryant-2027r3-390.png").write_bytes(phone)
    (OUT / "share-bigsby-jeanty-full.png").write_bytes(other_png)
    (OUT / "share-bigsby-jeanty-390.png").write_bytes(
        share_card_renderer.phone_display_png(other_png, 390)
    )
    preview = Image.open(BytesIO(phone)).convert("RGB")
    frame = Image.new("RGB", (390, preview.size[1] + 72), (8, 9, 11))
    frame.paste(preview, (0, 48))
    buf = BytesIO()
    frame.save(buf, format="PNG")
    (OUT / "share-preview-390.png").write_bytes(buf.getvalue())
    return {
        "share_render_ms": round(render_ms, 1),
        "full_size": list(Image.open(BytesIO(png)).size),
        "phone_390_size": list(Image.open(BytesIO(phone)).size),
        "portraits_fetched": {key: bool(value) for key, value in portraits.items()},
    }


def main() -> int:
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    share_report = _write_share_cards()
    port = _free_port()
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "scripts" / "ui_validation_harness.py"),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--server.address",
            "127.0.0.1",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    timings = {"share_render_ms": share_report["share_render_ms"]}
    try:
        _wait_http(base)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            shots = (
                ("dashboard", 320, "Dashboard-320.png", ""),
                ("dashboard", 360, "Dashboard-360.png", ""),
                ("dashboard", 375, "Dashboard-375.png", ""),
                ("dashboard", 390, "Dashboard-390.png", ""),
                ("dashboard", 430, "Dashboard-430.png", ""),
                ("dashboard", 768, "Dashboard-768.png", ""),
                ("dashboard", 1440, "Dashboard-1440.png", ""),
                ("trade", 390, "Trade-Hub-390.png", ""),
                ("dashboard", 320, "Franchise-320.png", "franchise"),
                ("dashboard", 390, "Franchise-390.png", "franchise"),
                ("dashboard", 430, "Franchise-430.png", "franchise"),
            )
            for surface, width, filename, modal in shots:
                page = browser.new_page(viewport={"width": width, "height": 900})
                query = f"surface={surface}"
                if modal:
                    query += "&open_modal=franchise"
                started = time.perf_counter()
                page.goto(f"{base}/?{query}", wait_until="domcontentloaded", timeout=90_000)
                page.wait_for_timeout(1800)
                key = f"{surface}_{width}_{modal or 'page'}"
                timings[key] = round((time.perf_counter() - started) * 1000, 1)
                page.screenshot(path=str(OUT / filename), full_page=True)
                if surface == "trade" and width == 390:
                    try:
                        page.get_by_text("Review package", exact=False).first.click(timeout=8_000)
                        page.wait_for_timeout(900)
                        page.screenshot(path=str(OUT / "Trade-detail-390.png"), full_page=True)
                    except Exception:
                        page.screenshot(path=str(OUT / "Trade-detail-390.png"), full_page=True)
                page.close()
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()
    report = {"timings": timings, "share": share_report}
    (OUT / "capture-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
