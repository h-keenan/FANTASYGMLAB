#!/usr/bin/env python3
"""Browser-level Dashboard visibility proof for #240.

Validates that Dashboard markers exist in the DOM, the startup overlay is absent,
and the page remains stable across a short observation window (no remount loop).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def _run(base_url: str, *, width: int, height: int, throttle: str | None) -> dict:
    from playwright.sync_api import sync_playwright

    console_rows: list[dict] = []
    result = {
        "ok": False,
        "width": width,
        "height": height,
        "throttle": throttle or "",
        "useful_present": False,
        "complete_present": False,
        "root_present": False,
        "overlay_absent": False,
        "browser_visible_attr": False,
        "stable_ms": 0.0,
        "remount_suspect": False,
        "error": "",
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        if throttle == "slow-4g":
            client = page.context.new_cdp_session(page)
            client.send(
                "Network.emulateNetworkConditions",
                {
                    "offline": False,
                    "downloadThroughput": (1.6 * 1024 * 1024) / 8,
                    "uploadThroughput": (750 * 1024) / 8,
                    "latency": 150,
                },
            )

        def _on_console(msg) -> None:
            text = msg.text or ""
            if "DYNASTYGM_STARTUP" in text and "browser_dashboard_visible" in text:
                try:
                    payload = json.loads(text.split("DYNASTYGM_STARTUP", 1)[1].strip())
                    console_rows.append(payload)
                except Exception:
                    console_rows.append({"raw": text[:200]})

        page.on("console", _on_console)
        page.goto(
            f"{base_url.rstrip('/')}/?surface=dashboard",
            wait_until="networkidle",
            timeout=60_000,
        )
        page.wait_for_selector("[data-ui-surface='dashboard']", state="attached", timeout=30_000)
        page.wait_for_selector('[data-fgl-dashboard-useful="1"]', state="attached", timeout=30_000)

        useful = page.locator('[data-fgl-dashboard-useful="1"]').count() > 0
        complete = page.locator('[data-fgl-dashboard-complete="1"]').count() > 0
        root = page.locator('[data-fgl-dashboard-root="1"]').count() > 0
        shell = page.locator(".dg-startup-shell").count()
        result["useful_present"] = useful
        result["complete_present"] = complete
        result["root_present"] = root
        result["overlay_absent"] = shell == 0

        # Observe stability: markers must remain for >= 1.5s without disappearing.
        started = time.perf_counter()
        disappeared = False
        while (time.perf_counter() - started) < 1.5:
            if page.locator('[data-fgl-dashboard-useful="1"]').count() == 0:
                disappeared = True
                break
            if page.locator(".dg-startup-shell").count() > 0:
                disappeared = True
                break
            page.wait_for_timeout(100)
        result["stable_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
        result["remount_suspect"] = disappeared
        result["browser_visible_attr"] = (
            page.locator('[data-fgl-browser-dashboard-visible="1"]').count() > 0
            or page.evaluate(
                "() => document.documentElement.getAttribute('data-fgl-browser-dashboard-visible') === '1'"
            )
        )
        result["console_acks"] = len(console_rows)
        result["ok"] = bool(
            useful
            and complete
            and root
            and result["overlay_absent"]
            and not disappeared
        )
        context.close()
        browser.close()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument("--output", default="artifacts/dashboard-visibility-240")
    args = parser.parse_args(argv)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    matrix = [
        {"width": 1280, "height": 800, "throttle": None, "label": "desktop"},
        {"width": 390, "height": 844, "throttle": None, "label": "mobile-390"},
        {"width": 390, "height": 844, "throttle": "slow-4g", "label": "mobile-slow4g"},
    ]
    rows = []
    failed = False
    for spec in matrix:
        try:
            row = _run(
                args.base_url,
                width=int(spec["width"]),
                height=int(spec["height"]),
                throttle=spec["throttle"],
            )
            row["label"] = spec["label"]
        except Exception as exc:
            row = {
                "ok": False,
                "label": spec["label"],
                "error": f"{type(exc).__name__}: {exc}",
            }
            failed = True
        rows.append(row)
        if not row.get("ok"):
            failed = True

    report = {
        "schema": "dynastygm-dashboard-visibility-240-v1",
        "ok": not failed,
        "rows": rows,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
