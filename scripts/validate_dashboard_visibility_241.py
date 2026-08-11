#!/usr/bin/env python3
"""Browser-level Dashboard visibility proof for #241 (parent-DOM probe).

Requires DYNASTYGM_STARTUP=1 on the Streamlit process so the probe + canary run.
Validates top-level DOM markers, Game Plan text, overlay absence, ≥5s stability,
and optional browser→Python ack attributes.
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
        "game_plan_visible": False,
        "canary_visible": False,
        "browser_visible_attr": False,
        "non_zero_dimensions": False,
        "stable_ms": 0.0,
        "remount_suspect": False,
        "console_acks": 0,
        "console_inspects": 0,
        "probe_document": "",
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
            if "DYNASTYGM_STARTUP" not in text:
                return
            try:
                payload = json.loads(text.split("DYNASTYGM_STARTUP", 1)[1].strip())
            except Exception:
                console_rows.append({"raw": text[:200]})
                return
            console_rows.append(payload)

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
        game_plan_text = page.get_by_text("Today's Game Plan", exact=False).count() > 0
        canary = page.get_by_text("DASHBOARD_CANARY_", exact=False).count() > 0 or page.get_by_text("FGL_P0_", exact=False).count() > 0
        result["useful_present"] = useful
        result["complete_present"] = complete
        result["root_present"] = root
        result["overlay_absent"] = shell == 0
        result["game_plan_visible"] = game_plan_text
        result["canary_visible"] = canary

        dims = page.evaluate(
            """() => {
              const nodes = Array.from(document.querySelectorAll('h1,h2,h3,h4,div,span,p,section'));
              let el = null;
              for (const n of nodes) {
                if (!(n.textContent || '').includes("Today's Game Plan")) continue;
                const r = n.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) { el = n; break; }
              }
              if (!el) {
                el = document.querySelector('.block-container')
                  || document.querySelector('[data-testid="stMain"]');
              }
              if (!el) return {width: 0, height: 0};
              const r = el.getBoundingClientRect();
              return {width: Math.round(r.width), height: Math.round(r.height)};
            }"""
        )
        result["root_rect"] = dims
        result["non_zero_dimensions"] = bool(
            dims and dims.get("width", 0) > 0 and dims.get("height", 0) > 0
        )

        # Observe stability ≥5s (acceptance for #241).
        started = time.perf_counter()
        disappeared = False
        while (time.perf_counter() - started) < 5.0:
            if page.locator('[data-fgl-dashboard-useful="1"]').count() == 0:
                disappeared = True
                break
            if page.locator(".dg-startup-shell").count() > 0:
                disappeared = True
                break
            if page.get_by_text("Today's Game Plan", exact=False).count() == 0:
                disappeared = True
                break
            page.wait_for_timeout(200)
        result["stable_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
        result["remount_suspect"] = disappeared
        result["browser_visible_attr"] = page.evaluate(
            "() => document.documentElement.getAttribute('data-fgl-browser-dashboard-visible') === '1'"
        )
        acks = [r for r in console_rows if r.get("kind") == "browser_dashboard_visible"]
        inspects = [r for r in console_rows if r.get("kind") == "browser_dashboard_inspect"]
        result["console_acks"] = len(acks)
        result["console_inspects"] = len(inspects)
        if acks:
            result["probe_document"] = str(acks[-1].get("probe_document") or "")
        elif inspects:
            result["probe_document"] = str(inspects[-1].get("probe_document") or "")
        result["ok"] = bool(
            useful
            and complete
            and root
            and game_plan_text
            and result["overlay_absent"]
            and result["non_zero_dimensions"]
            and not disappeared
            and result["stable_ms"] >= 5000
            and not canary
        )
        context.close()
        browser.close()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument("--output", default="artifacts/dashboard-visibility-241")
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
        "schema": "dynastygm-dashboard-visibility-241-v1",
        "ok": not failed,
        "rows": rows,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
