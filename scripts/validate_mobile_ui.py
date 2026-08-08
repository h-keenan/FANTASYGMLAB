"""Capture and fail closed on deterministic mobile UI defects."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

SURFACES = {
    "dashboard": (
        "Today's Game Plan",
        "What Changed",
        "Immediate Action",
        "Your Next Move",
        "Team Snapshot",
        "League Intelligence",
        "Deep Analysis",
    ),
    "league": ("Standings", "Power Rankings", "About these metrics"),
    "trade": ("Value change", "Review package"),
    "my-team": ("Roster Priorities", "Position Groups"),
    "waivers": ("Waiver Priorities", "Available Targets"),
    "navigation": ("Where to go", "Core", "Support"),
    "live-draft": (
        "Who should I draft next?",
        "Available Player Rankings",
        "Live Team Rankings",
        "Draft Board",
    ),
    "player-dossier": (
        "Identity",
        "Recommendation",
        "Current Value",
        "Current Season",
        "Career Resume",
        "Career Timeline",
        "View complete season stats",
        "Recent News",
        "Advanced Details",
    ),
}
WIDTHS = (320, 390, 430, 768, 1024, 1280, 1440, 1600, 1920)
ALERTS_CAPTURE_WIDTHS = (320, 390, 430, 768, 1024, 1280, 1440, 1600, 1920)
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
    page.get_by_text("Current Value", exact=True).wait_for(state="visible", timeout=30_000)
    dialog_contract = _dialog_contract(page)
    page.wait_for_timeout(750)
    page.screenshot(path=str(output / filename), full_page=True)
    return {"expandedPriority": filename, "dialogContract": dialog_contract}


def _capture_player_dossier_flow(page, output: Path, width: int) -> dict:
    page.get_by_role("button", name="View full career resume").click()
    page.get_by_role("button", name="Collapse career history").wait_for(
        state="visible", timeout=30_000
    )
    page.get_by_text("2023", exact=True).first.wait_for(state="visible", timeout=30_000)
    expanded_name = f"player-dossier-history-expanded-{width}x844.png"
    page.screenshot(path=str(output / expanded_name), full_page=True)
    page.get_by_role("button", name="Collapse career history").click()
    page.get_by_role("button", name="View full career resume").wait_for(
        state="visible", timeout=30_000
    )
    page.get_by_text("View complete season stats", exact=True).locator("visible=true").first.click()
    page.wait_for_timeout(400)
    stats_heading = page.get_by_text("Complete Season Stats", exact=True)
    try:
        stats_heading.locator("visible=true").first.wait_for(state="visible", timeout=8_000)
    except Exception:
        # Streamlit expander clicks are occasionally no-ops on the first attempt.
        page.get_by_text("View complete season stats", exact=True).locator("visible=true").first.click()
        page.wait_for_timeout(600)
        stats_heading.locator("visible=true").first.wait_for(state="visible", timeout=25_000)
    complete_name = f"player-dossier-complete-stats-{width}x844.png"
    page.screenshot(path=str(output / complete_name), full_page=True)
    # Streamlit can briefly retain a detached expander label after collapse.
    page.get_by_text("Advanced Details", exact=True).locator("visible=true").first.click()
    page.get_by_text("Executive Summary", exact=True).wait_for(state="visible", timeout=30_000)
    advanced_name = f"player-dossier-advanced-{width}x844.png"
    page.screenshot(path=str(output / advanced_name), full_page=True)
    return {
        "expandedHistory": expanded_name,
        "completeSeasonStats": complete_name,
        "advancedDetails": advanced_name,
    }


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
    orb = page.get_by_role("button", name=re.compile(r"^(GM|Menu)$", re.I))
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
    page.get_by_text("Where to go", exact=True).wait_for(state="visible", timeout=30_000)
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
    small_targets = [
        button
        for button in metrics["buttons"]
        if min(button["width"], button["height"]) + 0.01 < 44
    ]
    if small_targets:
        failures.append(f"undersized GM targets: {small_targets}")
    if current_style["label"].casefold() != "dashboard" or current_style["borderLeft"] != "3px" or current_style["radius"] != "0px":
        failures.append(f"current route is not structurally highlighted: {current_style}")
    if failures:
        raise AssertionError("; ".join(failures))
    filename = f"navigation-expanded-{width}x844.png"
    page.screenshot(path=str(output / filename), full_page=True)
    return {"expanded": filename, "orb": {"box": orb_box, "radius": orb_radius}, "menu": metrics, "current": current_style}


def _goto_dashboard_fixture(page, origin: str, *, inbox_open: bool = False) -> None:
    query = "surface=dashboard&notify=populated"
    if inbox_open:
        query += "&inbox=open"
    page.goto(
        f"{origin}/?{query}",
        wait_until="networkidle",
        timeout=60_000,
    )
    page.wait_for_selector("[data-ui-surface='dashboard']", state="attached", timeout=30_000)


def _inbox_panel(page):
    """Prefer live popover panel; fall back to harness force-open panel."""

    popover = page.locator(
        '[data-testid="stPopoverBody"]:has(.dg-notification-panel), '
        '[data-testid="stPopoverContent"]:has(.dg-notification-panel)'
    )
    if popover.count():
        return popover.first
    harness = page.locator(
        '[class*="inbox_harness_open"]:has(.dg-notification-panel), '
        '.dg-notification-harness-open ~ .dg-notification-panel, '
        '[data-inbox-open="1"]'
    )
    if harness.count():
        panel = page.locator(".dg-notification-panel").first
        return panel
    return page.locator(".dg-notification-panel").first


def _open_alerts_inbox(page, origin: str) -> None:
    """Open Alerts dropdown via popover tap; fall back to harness ?inbox=open."""

    _goto_dashboard_fixture(page, origin)
    trigger = page.locator(
        '[class*="st-key-executive_command_cell_alerts_"] [data-testid="stPopover"] button'
    )
    if trigger.count() == 0:
        trigger = page.locator(
            '[class*="st-key-executive_command_cell_alerts_"] [data-testid="stButton"] button'
        )
    if trigger.count():
        box = trigger.first.bounding_box()
        if box and min(box["width"], box["height"]) + 0.01 >= 44:
            trigger.first.click()
            page.wait_for_load_state("networkidle", timeout=60_000)
    try:
        page.locator(".dg-notification-panel").first.wait_for(state="attached", timeout=8_000)
    except Exception:
        _goto_dashboard_fixture(page, origin, inbox_open=True)
        page.locator(".dg-notification-panel").first.wait_for(state="attached", timeout=30_000)
    # Must not open as a centered modal dialog for Alerts.
    dialog_inbox = page.locator('[data-testid="stDialog"]:has(.dg-notification-panel)')
    if dialog_inbox.count():
        raise AssertionError("Alerts inbox rendered as st.dialog modal; expected anchored dropdown")


def _dialog_button(page, pattern: str):
    return page.locator('[role="dialog"]').first.get_by_role(
        "button", name=re.compile(pattern, re.I)
    ).first


def _assert_tap_target(page, locator, label: str, *, origin: str | None = None) -> dict:
    target = locator.first
    target.scroll_into_view_if_needed(timeout=30_000)
    target.wait_for(state="visible", timeout=30_000)
    box = target.bounding_box()
    if not box or min(box["width"], box["height"]) + 0.01 < 44:
        raise AssertionError(f"undersized tap target for {label}: {box}")
    href = target.get_attribute("href")
    if href and href.startswith("?") and origin:
        page.goto(f"{origin.rstrip('/')}/{href}", wait_until="networkidle", timeout=60_000)
    else:
        target.click()
        page.wait_for_load_state("networkidle", timeout=60_000)
    return {"label": label, "box": box}


def _capture_alerts_dropdown(page, output: Path, width: int, *, base_url: str) -> dict:
    """Capture Alerts dropdown geometry across phone/tablet/desktop widths."""

    origin = base_url.rstrip("/")
    _open_alerts_inbox(page, origin)
    panel = _inbox_panel(page)
    panel.wait_for(state="visible", timeout=30_000)
    page.screenshot(path=str(output / f"alerts-inbox-open-{width}x844.png"), full_page=False)
    box = panel.bounding_box() or {}
    # Scope chrome asserts to the open surface — never count closed portals.
    title_count = panel.locator(".dg-notification-panel__title").count()
    kicker_count = panel.locator(".dg-notification-panel__kicker").count()
    first_item = panel.locator(".dg-notification-item").first
    first_visible = first_item.count() > 0 and first_item.is_visible()
    failures: list[str] = []
    if title_count != 1:
        failures.append(f"expected one Alerts title, found {title_count}")
    title_text = ""
    if title_count:
        title_text = (panel.locator(".dg-notification-panel__title").first.inner_text() or "").strip()
    if title_text and title_text.casefold() != "alerts":
        failures.append(f"Alerts panel title mismatch: {title_text!r}")
    if kicker_count:
        failures.append("FOUNDER BETA kicker must not appear in Alerts dropdown")
    if panel.get_by_role("button", name=re.compile(r"Close inbox", re.I)).count():
        failures.append("redundant Close Inbox button present")
    if panel.get_by_text("Inbox", exact=True).count():
        failures.append("legacy Inbox label still visible in Alerts panel")
    # No giant centered dialog backdrop for Alerts on any capture width.
    if page.locator('[data-testid="stDialog"]:has(.dg-notification-panel)').count():
        failures.append("Alerts opened as st.dialog modal backdrop")
    if box:
        if box["x"] < -1 or box["y"] < -1:
            failures.append(f"dropdown overflows viewport origin: {box}")
        if box["x"] + box["width"] > width + 2:
            failures.append(f"dropdown overflows viewport width {width}: {box}")
        if width >= 768 and (box["width"] < 360 or box["width"] > 520):
            failures.append(f"desktop dropdown width out of ~380–480px band: {box['width']}")
    if not first_visible:
        failures.append("first notification not visible without extra scroll/copy")
    # Actual interactive CTA must be present and sized (click path, not href-only).
    cta = panel.get_by_role("link", name=re.compile(r"Open Trade Hub", re.I))
    if cta.count() == 0:
        cta = panel.get_by_role("button", name=re.compile(r"Open Trade Hub", re.I))
    if cta.count() == 0:
        failures.append("Open Trade Hub CTA missing from open Alerts dropdown")
    else:
        cta_box = cta.first.bounding_box()
        if not cta_box or min(cta_box["width"], cta_box["height"]) + 0.01 < 44:
            failures.append(f"Open Trade Hub CTA undersized: {cta_box}")
    if failures:
        raise AssertionError(f"alerts@{width}: " + "; ".join(failures))
    return {
        "panelBox": box,
        "titleCount": title_count,
        "firstItemVisible": first_visible,
        "modalDialog": False,
    }


def _capture_command_bar_interactions(page, output: Path, width: int, *, base_url: str) -> dict:
    """Click-path validation for Alerts, League, You, and GM on phone widths."""

    if width > 430:
        return {}

    results: dict[str, object] = {}
    origin = base_url.rstrip("/")

    results["alertsGeometry"] = _capture_alerts_dropdown(
        page, output, width, base_url=base_url
    )
    results["tradeHub"] = _assert_tap_target(
        page,
        page.get_by_role("link", name=re.compile(r"Open Trade Hub", re.I)),
        "Open Trade Hub",
        origin=origin,
    )
    page.wait_for_selector(
        "[data-fixture-notification-destination='trade_hub']",
        state="attached",
        timeout=30_000,
    )

    _open_alerts_inbox(page, origin)
    results["waivers"] = _assert_tap_target(
        page,
        page.get_by_role("link", name=re.compile(r"Open Waivers", re.I)),
        "Open Waivers",
        origin=origin,
    )
    page.wait_for_selector(
        "[data-fixture-notification-destination='waivers']",
        state="attached",
        timeout=30_000,
    )

    _open_alerts_inbox(page, origin)
    results["playerQuickView"] = _assert_tap_target(
        page,
        page.get_by_role("link", name=re.compile(r"Open Player", re.I)),
        "Open Player",
        origin=origin,
    )
    page.wait_for_selector(
        "[data-fixture-notification-destination='player_quick_view']",
        state="attached",
        timeout=30_000,
    )

    # League Overview deep link must also be an actual control inside Alerts.
    _open_alerts_inbox(page, origin)
    panel = _inbox_panel(page)
    panel.wait_for(state="visible", timeout=30_000)
    league_cta = panel.get_by_role("link", name=re.compile(r"Open League Overview", re.I))
    if league_cta.count() == 0:
        league_cta = panel.get_by_role("button", name=re.compile(r"Open League Overview", re.I))
    if league_cta.count() == 0:
        raise AssertionError("Open League Overview CTA missing from Alerts dropdown")
    results["leagueOverview"] = _assert_tap_target(
        page,
        league_cta,
        "Open League Overview",
        origin=origin,
    )
    page.wait_for_selector(
        "[data-fixture-notification-destination='league_overview'], "
        "[data-fixture-notification-destination='rankings']",
        state="attached",
        timeout=30_000,
    )

    _goto_dashboard_fixture(page, origin)
    page.get_by_role("button", name=re.compile(r"^Switch League")).first.click()
    page.wait_for_load_state("networkidle", timeout=60_000)
    page.screenshot(path=str(output / f"switch-league-open-{width}x844.png"), full_page=False)
    results["leagueSwitch"] = _assert_tap_target(
        page,
        page.get_by_role("button", name="Fixture Alt League", exact=True),
        "Fixture Alt League",
    )
    page.wait_for_selector(
        "[data-fixture-league-choice='Fixture Alt League']",
        state="attached",
        timeout=30_000,
    )

    _goto_dashboard_fixture(page, origin)
    page.get_by_role("button", name=re.compile(r"^You(\s|\(|$)")).first.click()
    page.wait_for_load_state("networkidle", timeout=60_000)
    page.screenshot(path=str(output / f"you-menu-open-{width}x844.png"), full_page=False)
    feedback = page.get_by_text("Send feedback", exact=True)
    if feedback.count():
        feedback.first.click()
    results["youMenu"] = {"label": "You", "feedbackExpanded": feedback.count() > 0}

    page.goto(f"{origin}/?surface=navigation", wait_until="networkidle", timeout=60_000)
    page.screenshot(path=str(output / f"dashboard-gm-closed-{width}x844.png"), full_page=False)
    page.get_by_role("button", name=re.compile(r"^(GM|Menu)$", re.I)).click()
    page.get_by_text("Where to go", exact=True).wait_for(state="visible", timeout=30_000)
    page.screenshot(path=str(output / f"gm-menu-open-{width}x844.png"), full_page=False)
    shell = page.locator(
        'div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-sheet-marker)'
    )
    trade_hub = shell.locator("button", has_text=re.compile(r"^Trade Hub$"))
    results["gmDestination"] = _assert_tap_target(page, trade_hub, "Trade Hub")
    page.wait_for_selector(
        "[data-fixture-gm-destination='trade_hub']",
        state="attached",
        timeout=30_000,
    )
    return results


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
          const heading = document.querySelector('h1, .dg-executive-shell__title');
          const primary = [...document.querySelectorAll(
            '.dg-executive-shell, .home-command-card, .summary-tile, .trade-summary-card, .football-player-asset'
          )].filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
          const badTargets = [...document.querySelectorAll('button, [role="button"], a')]
            .filter(el => el.getAttribute('aria-label') !== 'Link to heading')
            .filter(el => el.getAttribute('aria-label') !== 'Dismiss')
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
          const workspace = document.querySelector('.dg-executive-shell')?.getBoundingClientRect();
          const shellWrapper = document.querySelector('[class*="st-key-executive_workspace_shell"]')?.getBoundingClientRect();
          const shellText = document.querySelector('.dg-executive-shell')?.innerText || '';
          return {
            viewport: root.clientWidth,
            scrollWidth: root.scrollWidth,
            heading: hr ? {left: hr.left, right: hr.right, width: hr.width, height: hr.height, scrollWidth: heading.scrollWidth, scrollHeight: heading.scrollHeight, clientWidth: heading.clientWidth, clientHeight: heading.clientHeight} : null,
            narrow: primary.map(el => ({className: el.className, width: el.getBoundingClientRect().width})).filter(item => item.width < Math.min(120, root.clientWidth * 0.35)),
            badTargets,
            exceptions: document.querySelectorAll('[data-testid="stException"], .stException').length,
            visibleChrome,
            workspaceTop: workspace?.top ?? null,
            shellHeight: shellWrapper?.height ?? null,
            shellCount: document.querySelectorAll('.dg-executive-shell').length,
            switcherCount: document.querySelectorAll('[class*="st-key-executive_workspace_shell"] [class*="st-key-top_league_actions"] [data-testid="stPopover"] button').length,
            shellText,
            commandCells: (() => {
              const buttons = [...document.querySelectorAll(
                '[class*="st-key-executive_command_actions"] div[class*="st-key-executive_command_cell_"] button'
              )].filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
              });
              return buttons.map(el => {
                const r = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                const chevron = el.querySelector('svg') || el.querySelector('[aria-hidden="true"]');
                const chevronBox = chevron?.getBoundingClientRect();
                return {
                  height: r.height,
                  top: r.top,
                  lineHeight: style.lineHeight,
                  paddingTop: style.paddingTop,
                  paddingBottom: style.paddingBottom,
                  transform: style.transform,
                  chevronCenter: chevronBox ? (chevronBox.top + chevronBox.height / 2) : null,
                  separatorCenter: r.top + r.height / 2,
                  borderLeft: style.borderInlineStartWidth || style.borderLeftWidth,
                  hasPopover: !!el.closest('[data-testid="stPopover"]'),
                };
              });
            })(),
          };
        }"""
    )
    command_cells = metrics.get("commandCells") or []
    if len(command_cells) >= 3:
        heights = {round(cell["height"], 1) for cell in command_cells[:3]}
        if len(heights) != 1:
            failures.append(f"unequal command-cell heights: {heights}")
        tops = [round(cell["top"], 1) for cell in command_cells[:3]]
        if max(tops) - min(tops) > 1.5:
            failures.append(f"command-cell baseline drift: {tops}")
        line_heights = {cell["lineHeight"] for cell in command_cells[:3]}
        if len(line_heights) != 1:
            failures.append(f"unequal command-cell line-heights: {line_heights}")
        if any(cell.get("transform") not in {"none", "matrix(1, 0, 0, 1, 0, 0)"} for cell in command_cells[:3]):
            failures.append(f"forbidden command-cell transforms: {[c.get('transform') for c in command_cells[:3]]}")
        chevrons = [cell.get("chevronCenter") for cell in command_cells[:3] if cell.get("chevronCenter") is not None]
        popover_cells = [cell for cell in command_cells[:3] if cell.get("hasPopover")]
        if len(popover_cells) >= 2:
            popover_chevrons = [
                cell.get("chevronCenter")
                for cell in popover_cells
                if cell.get("chevronCenter") is not None
            ]
            if len(popover_chevrons) < len(popover_cells):
                failures.append(f"missing command-cell chevrons: {popover_chevrons}")
            elif max(popover_chevrons) - min(popover_chevrons) > 1.5:
                failures.append(f"chevron center drift: {popover_chevrons}")
        elif len(chevrons) < 2:
            failures.append(f"missing command-cell chevrons: {chevrons}")
        elif max(chevrons) - min(chevrons) > 1.5:
            failures.append(f"chevron center drift: {chevrons}")
        separators = [cell.get("separatorCenter") for cell in command_cells[:3] if cell.get("separatorCenter") is not None]
        if len(separators) >= 2 and max(separators) - min(separators) > 1.5:
            failures.append(f"separator center drift: {separators}")
        border_widths = {str(cell.get("borderLeft")) for cell in command_cells[:3]}
        if len(border_widths) != 1:
            failures.append(f"uneven command-cell separators: {border_widths}")
    elif surface == "dashboard":
        failures.append(f"expected three command cells, found {len(command_cells)}")
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
    if metrics["shellCount"] != 1:
        failures.append(f"expected one executive shell: {metrics['shellCount']}")
    if metrics["switcherCount"] != 1:
        failures.append(f"expected one integrated league switcher: {metrics['switcherCount']}")
    if any(label in metrics["shellText"] for label in ("Power Rank", "Franchise Rank", "Strategy", "Archetype")):
        failures.append(f"franchise metrics leaked into executive shell: {metrics['shellText']}")
    if width <= 430 and (metrics["shellHeight"] is None or metrics["shellHeight"] > 140):
        failures.append(f"mobile executive shell too tall: {metrics['shellHeight']}")
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
    if surface == "dashboard":
        body_text = str(metrics.get("shellText") or "")
        # Prefer full page text from heading metrics path when available.
        try:
            body_text = page.inner_text("body")
        except Exception:
            pass
        immediate_at = body_text.find("Immediate Action")
        next_move_at = body_text.find("Your Next Move")
        if immediate_at >= 0 and next_move_at >= 0 and immediate_at > next_move_at:
            failures.append("Immediate Action must appear above Your Next Move")
        if body_text.count("Today's Game Plan") > 1:
            failures.append("duplicate Today's Game Plan headers")
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
                                if width in (320, 390, 430):
                                    report["surfaces"][surface][str(width)]["commandBarInteractions"] = (
                                        _capture_command_bar_interactions(
                                            page,
                                            output,
                                            width,
                                            base_url=args.base_url,
                                        )
                                    )
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
                            if surface == "player-dossier":
                                report["surfaces"][surface][str(width)]["interaction"] = _capture_player_dossier_flow(page, output, width)
                    finally:
                        page.close()
            report["alertsDropdown"] = {}
            for width in ALERTS_CAPTURE_WIDTHS:
                # Phone widths already exercise click-paths; still re-capture
                # geometry so every required width has a dedicated Alerts shot.
                page = browser.new_page(viewport={"width": width, "height": 844}, device_scale_factor=1)
                try:
                    report["alertsDropdown"][str(width)] = _capture_alerts_dropdown(
                        page,
                        output,
                        width,
                        base_url=args.base_url,
                    )
                except Exception as exc:
                    page.screenshot(
                        path=str(output / f"alerts-inbox-open-{width}x844.png"),
                        full_page=True,
                    )
                    report["alertsDropdown"][str(width)] = {"error": str(exc)}
                    report_path.write_text(
                        json.dumps(report, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    raise
                finally:
                    page.close()
        finally:
            browser.close()
    report["widths"] = list(WIDTHS)
    report["alertsCaptureWidths"] = list(ALERTS_CAPTURE_WIDTHS)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
