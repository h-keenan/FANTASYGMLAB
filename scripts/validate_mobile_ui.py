"""Capture and fail closed on deterministic mobile UI defects."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

SURFACES = {
    "dashboard": (
        "Immediate Action",
        "Your Next Move",
        "Team Snapshot",
        "League Intelligence",
        "Deep Analysis",
    ),
    "league": ("Power Rankings", "About these metrics"),
    "trade": ("Trade Board", "Estimated value difference"),
    "my-team": ("Roster Priorities", "Position Groups"),
    "waivers": ("Waiver Priorities", "Available Targets"),
    "navigation": ("All Destinations", "Core", "Support"),
    "live-draft": (
        "Who should I draft next?",
        "Available Player Rankings",
        "Live Team Rankings",
        "Draft Board",
    ),
}
WIDTHS = (320, 390, 430, 1440)
ERROR_TEXT = ("StreamlitDuplicateElementKey", "DuplicateElementKey", "Traceback", "Uncaught exception")


def _frame_with_selector(page, selector: str, *, timeout: float = 30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if page.locator(selector).count():
                return page
        except Exception:
            pass
        # Streamlit can retain detached/hidden component frames briefly after a
        # dialog rerun. The newest frame is the active presentation surface.
        for frame in reversed(page.frames[1:]):
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
    page.get_by_text("Synthetic confidence rationale.", exact=True).wait_for(
        state="visible", timeout=30_000
    )
    dialog_contract = _dialog_contract(page)
    page.wait_for_timeout(750)
    expanded_name = f"trade-detail-expanded-{width}x844.png"
    page.screenshot(path=str(output / expanded_name), full_page=True)

    detail_frame.locator('[data-player-id="6794"]').click()
    page.locator('[data-trade-dossier-player="6794"]').wait_for(state="attached", timeout=30_000)
    page.wait_for_timeout(750)
    dossier_name = f"trade-player-dossier-{width}x844.png"
    page.screenshot(path=str(output / dossier_name), full_page=True)

    page.get_by_role("button", name="Back to trade").click()
    page.locator('[data-trade-dossier-player="6794"]').wait_for(state="detached", timeout=30_000)
    _frame_with_selector(page, "[data-trade-detail-key]")
    page.get_by_text("Synthetic confidence rationale.", exact=True).wait_for(
        state="visible", timeout=30_000
    )
    page.wait_for_timeout(750)
    returned_name = f"trade-detail-returned-{width}x844.png"
    page.screenshot(path=str(output / returned_name), full_page=True)
    return {
        "expanded": expanded_name,
        "dossier": dossier_name,
        "returned": returned_name,
        "dialogContract": dialog_contract,
    }


def _capture_metric_flow(page, output: Path, width: int) -> dict:
    frame = _frame_with_selector(page, ".summary-tile-tappable")
    captures = {}
    for index, slug in ((1, "average-age"), (2, "starter-strength")):
        frame.locator(".summary-tile-tappable").nth(index).click()
        dialog = page.locator('[data-testid="stDialog"]')
        dialog.wait_for(state="visible", timeout=30_000)
        page.get_by_text("League Leaderboard", exact=True).wait_for(state="visible", timeout=30_000)
        captures[f"{slug}Contract"] = _dialog_contract(page)
        page.wait_for_timeout(750)
        filename = f"metric-{slug}-{width}x844.png"
        page.screenshot(path=str(output / filename), full_page=True)
        captures[slug] = filename
        close = dialog.locator('button[aria-label="Close"]')
        if close.count():
            close.click()
        else:
            page.keyboard.press("Escape")
        dialog.wait_for(state="hidden", timeout=30_000)
        page.reload(wait_until="networkidle", timeout=60_000)
        frame = _frame_with_selector(page, ".summary-tile-tappable")
    return captures


def _capture_waiver_flow(page, output: Path, width: int) -> dict:
    frame = _frame_with_selector(page, ".free-agent-card")
    filename = f"waiver-priority-expanded-{width}x844.png"
    frame.locator(".free-agent-card").first.click()
    page.locator('[data-testid="stDialog"]').wait_for(state="visible", timeout=30_000)
    page.get_by_text("Snapshot", exact=True).wait_for(state="visible", timeout=30_000)
    dialog_contract = _dialog_contract(page)
    page.wait_for_timeout(750)
    page.screenshot(path=str(output / filename), full_page=True)
    return {"expandedPriority": filename, "dialogContract": dialog_contract}


def _dialog_contract(page) -> dict:
    dialog_selector = '[role="dialog"]'
    dialog_frame = _frame_with_selector(page, dialog_selector)
    dialog = dialog_frame.locator(dialog_selector)
    modal_root = dialog_frame.locator('[data-testid="stDialog"]')
    close = dialog.locator('button[aria-label="Close"]')
    metrics = dialog.evaluate(
        """el => {
          const c = getComputedStyle(el); const r = el.getBoundingClientRect();
          const children = [...el.children].map(child => ({
            radius: getComputedStyle(child).borderRadius,
            background: getComputedStyle(child).backgroundColor
          }));
          return {radius: c.borderRadius, width: r.width, height: r.height, overflow: c.overflow, children};
        }"""
    )
    close_box = close.bounding_box()
    metrics["closeTarget"] = close_box
    metrics["wrapperRadii"] = modal_root.evaluate(
        "el => [...el.children].map(child => getComputedStyle(child).borderRadius)"
    )
    if metrics["radius"] != "0px":
        raise AssertionError(f"noncanonical modal radius: {metrics['radius']}")
    rounded_children = [child for child in metrics["children"] if child["radius"] != "0px"]
    if rounded_children:
        raise AssertionError(f"rounded modal header or body: {rounded_children}")
    rounded_wrappers = [radius for radius in metrics["wrapperRadii"] if radius != "0px"]
    if rounded_wrappers:
        raise AssertionError(f"rounded modal wrapper: {rounded_wrappers}")
    if not close_box or min(close_box["width"], close_box["height"]) + 0.01 < 44:
        raise AssertionError(f"undersized modal close target: {close_box}")
    return metrics


def _capture_navigation_flow(page, output: Path, width: int) -> dict:
    orb = page.get_by_role("button", name="GM", exact=True)
    orb_box = orb.bounding_box()
    orb_radius = orb.evaluate("el => getComputedStyle(el).borderRadius")
    orb_wrapper_radius = orb.locator("xpath=..").evaluate("el => getComputedStyle(el).borderRadius")
    if not orb_box or min(orb_box["width"], orb_box["height"]) < 44:
        raise AssertionError(f"undersized GM control: {orb_box}")
    if orb_radius != "0px":
        raise AssertionError(f"rounded GM control: {orb_radius}")
    if orb_wrapper_radius != "0px":
        raise AssertionError(f"rounded GM wrapper: {orb_wrapper_radius}")
    orb.click()
    page.get_by_text("All Destinations", exact=True).wait_for(state="visible", timeout=30_000)
    shell = page.locator(
        'div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker)'
    )
    metrics = shell.evaluate(
        """el => {
          const c = getComputedStyle(el); const r = el.getBoundingClientRect();
          const buttons = [...el.querySelectorAll('button')].map(button => {
            const b = button.getBoundingClientRect(); return {label: button.innerText, width: b.width, height: b.height};
          });
          return {
            radius: c.borderRadius, backgroundColor: c.backgroundColor,
            backgroundImage: c.backgroundImage, overflowY: c.overflowY,
            left: r.left, right: r.right, top: r.top, bottom: r.bottom,
            width: r.width, height: r.height, buttons
          };
        }"""
    )
    current = shell.locator('button[kind="primary"]')
    current_style = current.evaluate(
        "el => ({label: el.innerText, borderLeft: getComputedStyle(el).borderLeftWidth, radius: getComputedStyle(el).borderRadius})"
    )
    failures = []
    if metrics["radius"] != "0px":
        failures.append(f"large rounded GM shell: {metrics['radius']}")
    if metrics["backgroundImage"] != "none":
        failures.append(f"legacy GM gradient: {metrics['backgroundImage']}")
    if metrics["overflowY"] not in {"auto", "scroll"}:
        failures.append(f"GM menu lacks internal scrolling: {metrics['overflowY']}")
    if metrics["left"] < -1 or metrics["right"] > width + 1 or metrics["top"] < -1 or metrics["bottom"] > 845:
        failures.append(f"GM menu outside viewport: {metrics}")
    small_targets = [button for button in metrics["buttons"] if min(button["width"], button["height"]) < 44]
    if small_targets:
        failures.append(f"undersized GM targets: {small_targets}")
    if current_style["label"].casefold() != "dashboard" or current_style["borderLeft"] != "3px" or current_style["radius"] != "0px":
        failures.append(f"current route is not structurally highlighted: {current_style}")
    if failures:
        raise AssertionError("; ".join(failures))
    filename = f"navigation-expanded-{width}x844.png"
    page.screenshot(path=str(output / filename), full_page=True)
    return {"expanded": filename, "orb": {"box": orb_box, "radius": orb_radius}, "menu": metrics, "current": current_style}


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
          const chromeSelectors = [
            '[data-testid="stHeader"]', '[data-testid="stToolbar"]',
            '[data-testid="stMainMenu"]', '[data-testid="stAppDeployButton"]',
            '[data-testid="stStatusWidget"]',
            '[data-testid="stDecoration"]', '[data-testid="stElementToolbar"]'
          ];
          const visibleChrome = chromeSelectors.flatMap(selector =>
            [...document.querySelectorAll(selector)]
              .filter(el => { const r = el.getBoundingClientRect(); const c = getComputedStyle(el); return c.display !== 'none' && c.visibility !== 'hidden' && r.width > 0 && r.height > 0; })
              .map(el => ({selector, width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height}))
          );
          const workspace = document.querySelector('.dg-application-workspace')?.getBoundingClientRect();
          return {
            viewport: root.clientWidth,
            scrollWidth: root.scrollWidth,
            heading: hr ? {left: hr.left, right: hr.right, width: hr.width, height: hr.height, scrollWidth: heading.scrollWidth, scrollHeight: heading.scrollHeight, clientWidth: heading.clientWidth, clientHeight: heading.clientHeight} : null,
            narrow: primary.map(el => ({className: el.className, width: el.getBoundingClientRect().width})).filter(item => item.width < Math.min(120, root.clientWidth * 0.35)),
            badTargets,
            exceptions: document.querySelectorAll('[data-testid="stException"], .stException').length,
            visibleChrome,
            workspaceTop: workspace?.top ?? null,
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
    if metrics["visibleChrome"]:
        failures.append(f"visible Streamlit chrome: {metrics['visibleChrome']}")
    if metrics["workspaceTop"] is None or metrics["workspaceTop"] > 24:
        failures.append(f"unreclaimed top chrome space: {metrics['workspaceTop']}")
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
    if surface == "trade":
        summary_frame = _frame_with_selector(page, ".trade-summary-card", timeout=2.0)
        card_box = summary_frame.locator(".trade-summary-card").bounding_box()
        avatar_box = summary_frame.locator(".trade-summary-avatar").first.bounding_box()
        if not card_box or not avatar_box:
            failures.append("trade summary metrics unavailable")
        else:
            title_clipped = summary_frame.locator(".trade-summary-title").evaluate(
                "el => el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1"
            )
            trade_summary = {
                "height": card_box["height"],
                "width": card_box["width"],
                "avatarHeight": avatar_box["height"],
                "avatarWidth": avatar_box["width"],
                "titleClipped": title_clipped,
            }
            metrics["tradeSummary"] = trade_summary
            if trade_summary["height"] > 360:
                failures.append(f"trade summary too tall: {trade_summary['height']:.1f}px")
            if min(trade_summary["avatarHeight"], trade_summary["avatarWidth"]) < 44:
                failures.append("trade summary avatar below 44px visual target")
            if trade_summary["titleClipped"]:
                failures.append("trade summary title is clipped")
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
                            if surface == "dashboard":
                                report["surfaces"][surface][str(width)]["comparisons"] = _capture_metric_flow(page, output, width)
                            if surface == "trade":
                                report["surfaces"][surface][str(width)]["interaction"] = _capture_trade_flow(
                                    page,
                                    output,
                                    width,
                                )
                            if surface == "waivers":
                                report["surfaces"][surface][str(width)]["interaction"] = _capture_waiver_flow(page, output, width)
                            if surface == "navigation":
                                report["surfaces"][surface][str(width)]["interaction"] = _capture_navigation_flow(page, output, width)
                    finally:
                        page.close()
        finally:
            browser.close()
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
