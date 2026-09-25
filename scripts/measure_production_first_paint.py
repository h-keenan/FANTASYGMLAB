"""Measure real production first-paint waterfalls for FantasyGM Lab.

Separates infrastructure wake from Streamlit bootstrap from app markers.

Examples:
  python scripts/measure_production_first_paint.py
  python scripts/measure_production_first_paint.py --app-url https://www.fantasygmlab.com
  python scripts/measure_production_first_paint.py --static-url file:///.../static/landing/index.html
  python scripts/measure_production_first_paint.py --cold-probe --trials 3

Markers (app):
  [data-fgl-shell-ready]
  [data-fgl-dashboard-useful]
  [data-fgl-dashboard-complete]

Markers (static):
  [data-fgl-static-landing]
  [data-fgl-shell-ready]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_APP_URL = "https://app.fantasygmlab.com"
DEFAULT_HEALTH_URL = "https://app.fantasygmlab.com/_stcore/health"
DEFAULT_STATIC_PATH = ROOT / "static" / "landing" / "index.html"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_probe(url: str, *, timeout: float = 60.0) -> dict[str, Any]:
    started = time.perf_counter()
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "FantasyGMLab-FirstPaintHarness/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            elapsed_ms = (time.perf_counter() - started) * 1000
            return {
                "ok": True,
                "status": int(response.status),
                "elapsed_ms": round(elapsed_ms, 1),
                "bytes": len(body),
                "content_type": response.headers.get("Content-Type", ""),
                "x_render_routing": response.headers.get("x-render-routing", ""),
            }
    except Exception as exc:  # noqa: BLE001 — harness must capture all probe failures
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": round(elapsed_ms, 1),
        }


def _distribution(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered:
        return {}
    index = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return {
        "min": round(ordered[0], 1),
        "mean": round(statistics.fmean(ordered), 1),
        "median": round(statistics.median(ordered), 1),
        "directional_p95": round(ordered[index], 1),
        "max": round(ordered[-1], 1),
    }


def measure_http_series(url: str, *, trials: int, label: str) -> dict[str, Any]:
    samples = [_http_probe(url) for _ in range(trials)]
    ok_ms = [float(s["elapsed_ms"]) for s in samples if s.get("ok")]
    return {
        "label": label,
        "url": url,
        "trials": trials,
        "ok_count": len(ok_ms),
        "distribution_ms": _distribution(ok_ms),
        "samples": samples,
    }


def measure_browser_page(
    url: str,
    *,
    marker: str,
    timeout_ms: int,
    mobile: bool,
    throttle: str | None,
) -> dict[str, Any]:
    """Playwright Chromium timings. Optional dependency."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return {
            "ok": False,
            "error": f"playwright_unavailable: {exc}",
            "hint": "pip install playwright && playwright install chromium",
        }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context_kwargs: dict[str, Any] = {}
            if mobile:
                context_kwargs.update(
                    {
                        "viewport": {"width": 390, "height": 844},
                        "device_scale_factor": 2,
                        "is_mobile": True,
                        "has_touch": True,
                        "user_agent": (
                            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                            "Mobile/15E148 Safari/604.1 FantasyGMLab-FirstPaintHarness"
                        ),
                    }
                )
            else:
                context_kwargs["viewport"] = {"width": 1440, "height": 900}
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            if throttle == "mobile-3g":
                cdp = context.new_cdp_session(page)
                cdp.send(
                    "Network.emulateNetworkConditions",
                    {
                        "offline": False,
                        "downloadThroughput": (1.6 * 1024 * 1024) / 8,
                        "uploadThroughput": (750 * 1024) / 8,
                        "latency": 150,
                    },
                )

            nav_started = time.perf_counter()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            dcl_ms = (time.perf_counter() - nav_started) * 1000
            marker_error = None
            try:
                page.wait_for_selector(marker, timeout=timeout_ms)
                marker_ms = (time.perf_counter() - nav_started) * 1000
                marker_found = True
            except Exception as exc:  # noqa: BLE001
                marker_ms = (time.perf_counter() - nav_started) * 1000
                marker_found = False
                marker_error = f"{type(exc).__name__}: {exc}"

            paint = page.evaluate(
                """() => {
                  const nav = performance.getEntriesByType('navigation')[0];
                  const paints = Object.fromEntries(
                    performance.getEntriesByType('paint').map(e => [e.name, e.startTime])
                  );
                  return {
                    responseStart: nav ? nav.responseStart : null,
                    domContentLoaded: nav ? nav.domContentLoadedEventEnd : null,
                    loadEventEnd: nav ? nav.loadEventEnd : null,
                    firstPaint: paints['first-paint'] || null,
                    firstContentfulPaint: paints['first-contentful-paint'] || null,
                  };
                }"""
            )
            browser.close()
            return {
                "ok": marker_found,
                "url": url,
                "marker": marker,
                "mobile": mobile,
                "throttle": throttle,
                "wall_to_domcontentloaded_ms": round(dcl_ms, 1),
                "wall_to_marker_ms": round(marker_ms, 1),
                "marker_error": marker_error,
                "performance_timing": paint,
                "measured_at": _now_iso(),
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "hint": "playwright install chromium",
            "url": url,
            "marker": marker,
        }


def cold_wake_probe(health_url: str, *, settle_s: float = 2.0) -> dict[str, Any]:
    """Compare first health probe vs immediate repeat (wake delta)."""
    first = _http_probe(health_url, timeout=120.0)
    time.sleep(settle_s)
    second = _http_probe(health_url, timeout=30.0)
    wake_ms = None
    if first.get("ok") and second.get("ok"):
        wake_ms = round(float(first["elapsed_ms"]) - float(second["elapsed_ms"]), 1)
    return {
        "health_url": health_url,
        "first": first,
        "second": second,
        "estimated_wake_contribution_ms": wake_ms,
        "interpretation": (
            "If first ≫ second (e.g. 10–15s vs 0.1–0.5s), Render cold wake dominates."
            if wake_ms is not None
            else "Could not estimate wake contribution."
        ),
        "measured_at": _now_iso(),
    }


def static_transfer_budget(landing_dir: Path) -> dict[str, Any]:
    first_fold = [
        landing_dir / "index.html",
        landing_dir / "landing.css",
        landing_dir / "assets" / "fantasygmlab-symbol-compact.png",
        landing_dir / "assets" / "favicon.png",
    ]
    lazy = list((landing_dir / "assets" / "web").glob("*.jpg"))
    first_bytes = sum(p.stat().st_size for p in first_fold if p.exists())
    lazy_bytes = sum(p.stat().st_size for p in lazy if p.exists())
    return {
        "first_fold_bytes": first_bytes,
        "first_fold_kb": round(first_bytes / 1024, 1),
        "lazy_image_bytes": lazy_bytes,
        "budget_html_css_js_target_kb": 150,
        "within_budget": first_bytes < 150 * 1024,
        "files": {
            str(p.relative_to(landing_dir)): p.stat().st_size
            for p in first_fold
            if p.exists()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-url", default=DEFAULT_APP_URL)
    parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL)
    parser.add_argument(
        "--static-url",
        default="",
        help="Static landing URL or file:// path. Defaults to local index.html.",
    )
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--cold-probe", action="store_true")
    parser.add_argument("--browser", action="store_true", help="Require Playwright.")
    parser.add_argument("--mobile", action="store_true")
    parser.add_argument(
        "--throttle",
        choices=["none", "mobile-3g"],
        default="none",
    )
    parser.add_argument("--timeout-ms", type=int, default=90000)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    static_url = args.static_url or DEFAULT_STATIC_PATH.resolve().as_uri()
    report: dict[str, Any] = {
        "measured_at": _now_iso(),
        "app_url": args.app_url,
        "health_url": args.health_url,
        "static_url": static_url,
        "http": {
            "health": measure_http_series(
                args.health_url, trials=args.trials, label="health"
            ),
            "app_html": measure_http_series(
                args.app_url, trials=args.trials, label="app_html"
            ),
        },
        "static_budget": static_transfer_budget(ROOT / "static" / "landing"),
        "timing_model": {
            "T0": "DNS/TLS/connect",
            "T1": "Render routing",
            "T2": "Render process available",
            "T3": "Streamlit HTML/bootstrap delivered",
            "T4": "WebSocket/session established",
            "T5": "Python script begins",
            "T6": "imports complete",
            "T7": "shell available (data-fgl-shell-ready)",
            "T8": "auth restore complete",
            "T9": "canonical league context available",
            "T10": "Dashboard first useful (data-fgl-dashboard-useful)",
            "T11": "Dashboard stable (data-fgl-dashboard-complete)",
        },
    }

    if args.cold_probe:
        report["cold_wake"] = cold_wake_probe(args.health_url)

    browser_error = None
    if args.browser:
        report["browser"] = {
            "static": measure_browser_page(
                static_url,
                marker='[data-fgl-shell-ready="1"]',
                timeout_ms=args.timeout_ms,
                mobile=args.mobile,
                throttle=None if args.throttle == "none" else args.throttle,
            ),
            "app_shell": measure_browser_page(
                args.app_url,
                marker='[data-fgl-shell-ready="1"]',
                timeout_ms=args.timeout_ms,
                mobile=args.mobile,
                throttle=None if args.throttle == "none" else args.throttle,
            ),
        }
        if not report["browser"]["static"].get("ok") and "playwright" in str(
            report["browser"]["static"].get("error", "")
        ):
            browser_error = report["browser"]["static"]["error"]
    else:
        # Best-effort browser when Playwright is installed.
        static_try = measure_browser_page(
            static_url,
            marker='[data-fgl-shell-ready="1"]',
            timeout_ms=min(args.timeout_ms, 30000),
            mobile=args.mobile,
            throttle=None,
        )
        report["browser"] = {"static_optional": static_try}
        if static_try.get("error", "").startswith("playwright_unavailable"):
            browser_error = static_try["error"]

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    if browser_error and args.browser:
        print(browser_error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
