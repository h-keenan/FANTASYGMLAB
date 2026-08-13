#!/usr/bin/env python3
"""T0–T8 browser bootstrap probe for production/local Streamlit Dashboard.

Primary truth is Chromium + websocket ForwardMsg sizes, not AppTest.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

USERNAME = "amatl7"
LEAGUE_BUTTON = "Open Austin and Co."


def _decode_forward(payload: bytes) -> dict[str, Any]:
    from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

    msg = ForwardMsg()
    raw = payload
    for candidate in (payload, payload[1:], payload[4:], payload[8:]):
        try:
            msg.ParseFromString(candidate)
            if msg.WhichOneof("type"):
                raw = candidate
                break
        except Exception:
            msg = ForwardMsg()
    kind = msg.WhichOneof("type") or "unparsed"
    info: dict[str, Any] = {
        "type": kind,
        "bytes": len(payload),
        "parsed_bytes": len(raw),
    }
    if kind == "delta":
        delta = msg.delta
        dkind = delta.WhichOneof("type")
        info["delta"] = dkind
        if dkind == "new_element":
            el = delta.new_element
            ekind = el.WhichOneof("type")
            info["element"] = ekind
            if ekind == "html":
                body = el.html.body
                info["html_bytes"] = len(body.encode("utf-8"))
                info["has_style"] = "<style" in body.casefold()
                if "dg-build-identity" in body:
                    info["label"] = "build_identity"
                elif len(body) > 20_000:
                    info["label"] = "large_html"
            elif ekind == "markdown":
                body = el.markdown.body
                info["md_bytes"] = len(body.encode("utf-8"))
            elif ekind == "imgs":
                info["img_count"] = len(el.imgs.imgs)
            elif ekind == "component_instance":
                info["component"] = el.component_instance.component_name
                info["component_bytes"] = len(el.component_instance.json)
        elif dkind == "add_block":
            info["block"] = delta.add_block.WhichOneof("type") or "block"
    elif kind == "new_session":
        info["label"] = "new_session"
    elif kind == "script_finished":
        info["label"] = "script_finished"
    return info


def _resource_rows(page) -> list[dict[str, Any]]:
    return page.evaluate(
        """() => performance.getEntriesByType('resource').map((e) => ({
            name: e.name.split('?')[0].slice(-120),
            initiator: e.initiatorType,
            start: Math.round(e.startTime),
            duration: Math.round(e.duration),
            size: e.transferSize || 0,
            encoded: e.encodedBodySize || 0,
            cached: e.transferSize === 0 && e.decodedBodySize > 0,
            protocol: e.nextHopProtocol,
        }))"""
    )


def _dom_stats(page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const all = document.querySelectorAll('*');
          const hidden = [...all].filter((el) => {
            const cs = getComputedStyle(el);
            return cs.display === 'none' || cs.visibility === 'hidden' || el.hidden;
          }).length;
          return {
            nodes: all.length,
            hidden,
            styles: document.querySelectorAll('style').length,
            imgs: document.querySelectorAll('img').length,
            useful: !!document.querySelector('[data-fgl-dashboard-useful="1"]'),
            gpCache: document.querySelector('[data-fgl-dashboard-useful="1"]')?.getAttribute('data-fgl-gp-cache'),
            hydrateMs: document.querySelector('[data-fgl-dashboard-useful="1"]')?.getAttribute('data-fgl-hydrate-to-useful-ms'),
            dashMs: document.querySelector('[data-fgl-dashboard-useful="1"]')?.getAttribute('data-fgl-dashboard-ms'),
            hydrate: !!document.querySelector('[data-fgl-dashboard-hydrating="1"], .dashboard-hydrate-placeholder'),
            shell: !!document.querySelector('[data-fgl-shell-ready="1"]'),
            complete: !!document.querySelector('[data-fgl-dashboard-complete="1"]'),
          };
        }"""
    )


def _paints(page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const nav = performance.getEntriesByType('navigation')[0];
          const paints = Object.fromEntries(
            performance.getEntriesByType('paint').map((e) => [e.name, Math.round(e.startTime)])
          );
          return {
            fp: paints['first-paint'] || null,
            fcp: paints['first-contentful-paint'] || null,
            dcl: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
            responseStart: nav ? Math.round(nav.responseStart) : null,
            responseEnd: nav ? Math.round(nav.responseEnd) : null,
            transferSize: nav ? nav.transferSize : null,
          };
        }"""
    )


class WsTrace:
    def __init__(self, t0: float) -> None:
        self.t0 = t0
        self.open_at: float | None = None
        self.first_msg_at: float | None = None
        self.frames: list[dict[str, Any]] = []
        self.inbound_bytes = 0
        self.outbound_bytes = 0
        self.runs = 0
        self.by_element: Counter[str] = Counter()
        self.html_style_bytes = 0
        self.top_html: list[tuple[int, str]] = []

    def attach(self, page) -> None:
        def on_ws(ws) -> None:
            if self.open_at is None:
                self.open_at = time.perf_counter()

            def incoming(data) -> None:
                now = time.perf_counter()
                if self.first_msg_at is None:
                    self.first_msg_at = now
                raw = data if isinstance(data, bytes) else str(data).encode("utf-8", "replace")
                self.inbound_bytes += len(raw)
                info = _decode_forward(raw) if isinstance(data, bytes) else {
                    "type": "text",
                    "bytes": len(raw),
                }
                info["t_ms"] = round((now - self.t0) * 1000)
                if info.get("type") == "script_finished":
                    self.runs += 1
                    info["run"] = self.runs
                if info.get("element"):
                    self.by_element[str(info["element"])] += 1
                if info.get("has_style"):
                    self.html_style_bytes += int(info.get("html_bytes") or info["bytes"])
                size = int(info.get("html_bytes") or info.get("md_bytes") or info["bytes"])
                label = str(info.get("label") or info.get("element") or info.get("type"))
                self.top_html.append((size, label))
                self.frames.append(info)

            def outgoing(data) -> None:
                raw = data if isinstance(data, bytes) else str(data).encode("utf-8", "replace")
                self.outbound_bytes += len(raw)

            ws.on("framereceived", incoming)
            ws.on("framesent", outgoing)

        page.on("websocket", on_ws)

    def snapshot_range(self, *, start_ms: float, end_ms: float | None) -> dict[str, Any]:
        frames = [
            f
            for f in self.frames
            if f.get("t_ms", 0) >= start_ms
            and (end_ms is None or f.get("t_ms", 0) <= end_ms)
        ]
        inbound = sum(int(f.get("bytes") or 0) for f in frames)
        by_el: Counter[str] = Counter()
        style_bytes = 0
        top: list[tuple[int, str]] = []
        for info in frames:
            if info.get("element"):
                by_el[str(info["element"])] += 1
            if info.get("has_style"):
                style_bytes += int(info.get("html_bytes") or info["bytes"])
            size = int(info.get("html_bytes") or info.get("md_bytes") or info["bytes"])
            label = str(info.get("label") or info.get("element") or info.get("type"))
            top.append((size, label))
        top = sorted(top, reverse=True)[:10]
        return {
            "start_ms": start_ms,
            "end_ms": end_ms,
            "messages": len(frames),
            "inbound_bytes": inbound,
            "script_finished": sum(1 for f in frames if f.get("type") == "script_finished"),
            "script_finished_ms": [f.get("t_ms") for f in frames if f.get("type") == "script_finished"],
            "style_html_bytes": style_bytes,
            "style_events": sum(1 for f in frames if f.get("has_style")),
            "elements": dict(by_el),
            "top10": [{"bytes": b, "label": lab} for b, lab in top],
        }

    def snapshot(self, until_ms: float | None = None) -> dict[str, Any]:
        frames = self.frames
        if until_ms is not None:
            frames = [f for f in frames if f.get("t_ms", 0) <= until_ms]
        inbound = sum(int(f.get("bytes") or 0) for f in frames)
        first_delta = next((f for f in frames if f.get("type") == "delta"), None)
        first_html = next(
            (f for f in frames if f.get("element") in {"html", "markdown"}),
            None,
        )
        top = sorted(self.top_html, reverse=True)[:10]
        return {
            "open_ms": None if self.open_at is None else round((self.open_at - self.t0) * 1000),
            "first_msg_ms": None
            if self.first_msg_at is None
            else round((self.first_msg_at - self.t0) * 1000),
            "first_delta_ms": None if first_delta is None else first_delta.get("t_ms"),
            "first_html_ms": None if first_html is None else first_html.get("t_ms"),
            "first_delta_bytes": None if first_delta is None else first_delta.get("bytes"),
            "messages": len(frames),
            "inbound_bytes": inbound,
            "outbound_bytes": self.outbound_bytes,
            "script_finished": sum(1 for f in frames if f.get("type") == "script_finished"),
            "script_finished_ms": [f.get("t_ms") for f in frames if f.get("type") == "script_finished"],
            "style_html_bytes": self.html_style_bytes,
            "style_events": sum(1 for f in frames if f.get("has_style")),
            "elements": dict(self.by_element),
            "top10": [{"bytes": b, "label": lab} for b, lab in top],
        }


def _wait_markers(page, ws: WsTrace, t0: float, t_open: float) -> dict[str, Any]:
    marks = {
        "T5_shell": None,
        "T6_hydrate": None,
        "T7_useful": None,
        "T8_stable": None,
        "game_plan_text": None,
    }
    deadline = time.perf_counter() + 90
    while time.perf_counter() < deadline:
        html = page.content()
        now = time.perf_counter()
        if marks["T5_shell"] is None and (
            'data-fgl-shell-ready="1"' in html or "Austin and Co." in html
        ):
            # After league open, shell is the executive header rather than landing hero.
            if "Dashboard" in html or 'data-fgl-shell-ready="1"' in html:
                marks["T5_shell"] = now
        if marks["T6_hydrate"] is None and (
            "Updating Dashboard" in html or "data-fgl-dashboard-hydrating" in html
        ):
            marks["T6_hydrate"] = now
        if marks["game_plan_text"] is None and "Today's Game Plan" in html:
            marks["game_plan_text"] = now
        if marks["T7_useful"] is None and (
            'data-fgl-dashboard-useful="1"' in html
            or ("Today's Game Plan" in html and "Updating Dashboard" not in html)
        ):
            marks["T7_useful"] = now
        if marks["T7_useful"] is not None:
            page.wait_for_timeout(350)
            marks["T8_stable"] = time.perf_counter()
            break
        page.wait_for_timeout(80)
    def ms(ts):
        return None if ts is None else round((ts - t0) * 1000)
    def from_open(ts):
        return None if ts is None else round((ts - t_open) * 1000)
    return {
        "from_nav": {k: ms(v) for k, v in marks.items()},
        "from_open_league": {k: from_open(v) for k, v in marks.items()},
        "dom_useful": _dom_stats(page),
        "ws_useful": ws.snapshot(until_ms=ms(marks["T7_useful"])),
        "ws_stable": ws.snapshot(),
        "ws_after_open": ws.snapshot_range(
            start_ms=round((t_open - t0) * 1000),
            end_ms=ms(marks["T7_useful"]),
        ),
        "paints": _paints(page),
    }


def _goto_import_and_open(page, ws: WsTrace, t0: float) -> dict[str, Any]:
    t_load = None
    t_open = time.perf_counter()
    page.wait_for_selector('[data-testid="stApp"]', timeout=60_000)
    page.wait_for_timeout(800)
    user = page.get_by_label("Sleeper username")
    if not user.count():
        user = page.locator("input").first
    user.first.fill(USERNAME)
    load = page.get_by_role("button", name="Load my leagues")
    t_load = time.perf_counter()
    load.first.click()
    page.get_by_role("button", name=LEAGUE_BUTTON).first.wait_for(timeout=60_000)
    t_list = time.perf_counter()
    page.get_by_role("button", name=LEAGUE_BUTTON).first.click()
    t_open = time.perf_counter()
    result = _wait_markers(page, ws, t0, t_open)
    result["load_click_ms"] = round((t_load - t0) * 1000)
    result["league_list_ms"] = round((t_list - t0) * 1000)
    result["open_league_ms"] = round((t_open - t0) * 1000)
    return result


def run_case(playwright, *, base: str, width: int, label: str, reuse_browser=None) -> dict[str, Any]:
    import urllib.request

    health_ms = None
    try:
        started = time.perf_counter()
        with urllib.request.urlopen(base.rstrip("/") + "/_stcore/health", timeout=15) as resp:
            resp.read()
            health_ms = round((time.perf_counter() - started) * 1000)
    except Exception as exc:  # noqa: BLE001
        health_ms = f"fail:{exc}"

    browser = reuse_browser or playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": width, "height": 844 if width <= 430 else 900},
        device_scale_factor=2 if width <= 430 else 1,
    )
    page = context.new_page()
    page.set_default_timeout(120_000)
    t0 = time.perf_counter()
    ws = WsTrace(t0)
    ws.attach(page)
    page.goto(base, wait_until="domcontentloaded", timeout=60_000)
    t1 = time.perf_counter()
    page.wait_for_selector('[data-testid="stApp"]', timeout=60_000)
    timeline = {
        "T0": 0,
        "T1_html": round((t1 - t0) * 1000),
        "T2_ws": ws.snapshot()["open_ms"],
        "T3_first_msg": ws.snapshot()["first_msg_ms"],
        "T4_first_delta": ws.snapshot()["first_delta_ms"],
    }
    imported = _goto_import_and_open(page, ws, t0)
    shot_dir = ROOT / "artifacts" / "bootstrap-first-useful"
    shot_dir.mkdir(parents=True, exist_ok=True)
    shot = shot_dir / f"{label}-{width}.png"
    page.screenshot(path=str(shot), full_page=True)
    resources = _resource_rows(page)
    report = {
        "label": label,
        "width": width,
        "health_ms": health_ms,
        "timeline_nav": timeline,
        "imported": imported,
        "screenshot": str(shot),
        "resources_top": sorted(resources, key=lambda r: r.get("duration") or 0, reverse=True)[:15],
        "resource_bytes": sum(int(r.get("size") or 0) for r in resources),
        "fonts": [r for r in resources if "font" in (r.get("name") or "").casefold() or r.get("initiator") == "css"],
        "images": [r for r in resources if r.get("initiator") == "img"][:20],
        "dom_final": _dom_stats(page),
    }
    # Same-session route return if Game Plan is up.
    route = {"ok": False}
    try:
            trade = page.get_by_role("button", name="OPEN TRADE HUB")
            if trade.count():
                t_route = time.perf_counter()
                trade.first.click()
                page.wait_for_timeout(500)
                nav = page.locator('[data-testid="stBaseButton-headerNoPadding"], button').filter(has_text="Dashboard")
                clicked = False
                for locator in (
                    page.get_by_role("button", name="Dashboard", exact=True),
                    page.get_by_text("Dashboard", exact=True),
                ):
                    if locator.count():
                        try:
                            locator.first.click(force=True, timeout=5_000)
                            clicked = True
                            break
                        except Exception:
                            continue
                useful = None
                deadline = time.perf_counter() + 12
                while clicked and time.perf_counter() < deadline:
                    html = page.content()
                    if 'data-fgl-dashboard-useful="1"' in html or "Today's Game Plan" in html:
                        useful = time.perf_counter()
                        break
                    page.wait_for_timeout(80)
                route = {
                    "ok": useful is not None,
                    "return_ms": None if useful is None else round((useful - t_route) * 1000),
                    "clicked": clicked,
                }
            page.screenshot(path=str(shot_dir / f"{label}-{width}-route-return.png"), full_page=False)
    except Exception as exc:  # noqa: BLE001
        route = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    report["route_return"] = route
    context.close()
    if reuse_browser is None:
        browser.close()
        return report, None
    return report, browser


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="https://app.fantasygmlab.com")
    parser.add_argument("--width", type=int, default=390)
    parser.add_argument("--label", default="prod-warm-new-session")
    parser.add_argument(
        "--output",
        default=str(ROOT / "artifacts" / "bootstrap-first-useful" / "report.json"),
    )
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        report, _ = run_case(
            playwright,
            base=args.base,
            width=args.width,
            label=args.label,
        )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
