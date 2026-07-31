"""Capture and fail closed on deterministic mobile UI defects."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

SURFACES = {
    "dashboard": ("Next Moves", "League Pulse"),
    "league": ("League Snapshot", "Power Rankings"),
    "trade": ("Trade Board", "Estimated value difference"),
    "my-team": ("Roster Priorities", "Position Groups"),
}
WIDTHS = (320, 390, 430)
ERROR_TEXT = ("StreamlitDuplicateElementKey", "DuplicateElementKey", "Traceback", "Uncaught exception")


def _frame_with_selector(page, selector: str, *, timeout: float = 30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for frame in page.frames[1:]:
            try:
                if frame.locator(selector).count():
                    return frame
            except Exception:
                continue
        page.wait_for_timeout(100)
    raise AssertionError(f"component selector did not appear: {selector}")


def _capture_trade_flow(page, output: Path, width: int) -> dict:
    """Exercise the summary → trade → dossier → trade path in one dialog."""

    summary_frame = _frame_with_selector(page, ".trade-summary-card")
    summary_frame.locator(".trade-summary-card").click()
    page.locator('[data-testid="stDialog"]').wait_for(state="visible", timeout=30_000)
    detail_frame = _frame_with_selector(page, "[data-trade-detail-key]")
    expanded_name = f"trade-detail-expanded-{width}x844.png"
    page.screenshot(path=str(output / expanded_name), full_page=True)

    detail_frame.locator('[data-player-id="6794"]').click()
    page.locator('[data-trade-dossier-player="6794"]').wait_for(state="attached", timeout=30_000)
    dossier_name = f"trade-player-dossier-{width}x844.png"
    page.screenshot(path=str(output / dossier_name), full_page=True)

    page.get_by_role("button", name="Back to trade").click()
    page.locator('[data-trade-dossier-player="6794"]').wait_for(state="detached", timeout=30_000)
    _frame_with_selector(page, "[data-trade-detail-key]")
    returned_name = f"trade-detail-returned-{width}x844.png"
    page.screenshot(path=str(output / returned_name), full_page=True)
    return {
        "expanded": expanded_name,
        "dossier": dossier_name,
        "returned": returned_name,
    }


def _assert_layout(page, surface: str, width: int, expected: tuple[str, ...]) -> dict:
    page.wait_for_selector("[data-ui-surface]", state="attached", timeout=30_000)
    body_text = page.locator("body").inner_text()
    failures = [f"error text: {text}" for text in ERROR_TEXT if text in body_text]
    declared_sections = page.locator("[data-ui-surface]").get_attribute("data-ui-sections") or ""
    declared_sections = {section.strip() for section in declared_sections.split(",") if section.strip()}
    for section in expected:
        if section not in declared_sections:
            failures.append(f"missing section: {section}")
    metrics = page.evaluate(
        """() => {
          const root = document.documentElement;
          const heading = document.querySelector('h1, .dg-workspace-page-title');
          const primary = [...document.querySelectorAll(
            '.dg-workspace-page, .dg-workspace-context, .home-command-card, .team-rank-card, .trade-summary-card, .football-player-asset'
          )].filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
          const badTargets = [...document.querySelectorAll('button, [role="button"], a')]
            .filter(el => el.getAttribute('aria-label') !== 'Link to heading')
            .filter(el => !el.closest('[data-testid="stHeaderActionElements"]'))
            .filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (r.width < 28 || r.height < 28); })
            .map(el => ({text: (el.innerText || el.getAttribute('aria-label') || '').slice(0, 80), width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height}));
          const hr = heading?.getBoundingClientRect();
          return {
            viewport: root.clientWidth,
            scrollWidth: root.scrollWidth,
            heading: hr ? {left: hr.left, right: hr.right, width: hr.width, height: hr.height, scrollWidth: heading.scrollWidth, scrollHeight: heading.scrollHeight, clientWidth: heading.clientWidth, clientHeight: heading.clientHeight} : null,
            narrow: primary.map(el => ({className: el.className, width: el.getBoundingClientRect().width})).filter(item => item.width < Math.min(120, root.clientWidth * 0.35)),
            badTargets,
            exceptions: document.querySelectorAll('[data-testid="stException"], .stException').length,
          };
        }"""
    )
    if metrics["scrollWidth"] > metrics["viewport"] + 1:
        failures.append(f"horizontal overflow: {metrics['scrollWidth']} > {metrics['viewport']}")
    heading = metrics["heading"]
    if not heading:
        failures.append("missing primary heading")
    else:
        if heading["left"] < -1 or heading["right"] > width + 1:
            failures.append("primary heading is outside viewport")
        if heading["scrollWidth"] > heading["clientWidth"] + 1 or heading["scrollHeight"] > heading["clientHeight"] + 1:
            failures.append("primary heading is clipped")
    if metrics["narrow"]:
        failures.append(f"near-zero-width primary content: {metrics['narrow']}")
    if metrics["badTargets"]:
        failures.append(f"unusable tap targets: {metrics['badTargets']}")
    if metrics["exceptions"]:
        failures.append(f"Streamlit exception elements: {metrics['exceptions']}")
    for frame in page.frames[1:]:
        try:
            frame_metrics = frame.evaluate("() => ({clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth, text: document.body?.innerText || ''})")
        except Exception as exc:
            failures.append(f"component frame unavailable: {exc}")
            continue
        if frame_metrics["scrollWidth"] > frame_metrics["clientWidth"] + 1:
            failures.append(f"component horizontal overflow: {frame_metrics['scrollWidth']} > {frame_metrics['clientWidth']}")
        for text in ERROR_TEXT:
            if text in frame_metrics["text"]:
                failures.append(f"component error text: {text}")
    if failures:
        raise AssertionError(f"{surface}@{width}: " + "; ".join(failures))
    return metrics


def main() -> int:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument("--output", default="artifacts/ui-mobile")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    report = {"widths": list(WIDTHS), "surfaces": {}}
    report_path = output / "validation-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for surface, expected in SURFACES.items():
                report["surfaces"][surface] = {}
                for width in WIDTHS:
                    page = browser.new_page(viewport={"width": width, "height": 844}, device_scale_factor=1)
                    try:
                        page.goto(f"{args.base_url}/?surface={surface}", wait_until="networkidle", timeout=60_000)
                        filename = f"{surface}-{width}x844.png"
                        try:
                            metrics = _assert_layout(page, surface, width, expected)
                        except Exception as exc:
                            page.screenshot(path=str(output / filename), full_page=True)
                            report["surfaces"][surface][str(width)] = {"screenshot": filename, "error": str(exc)}
                            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                            raise
                        else:
                            page.screenshot(path=str(output / filename), full_page=True)
                            report["surfaces"][surface][str(width)] = {"screenshot": filename, "metrics": metrics}
                            if surface == "trade":
                                report["surfaces"][surface][str(width)]["interaction"] = _capture_trade_flow(
                                    page,
                                    output,
                                    width,
                                )
                    finally:
                        page.close()
        finally:
            browser.close()
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
