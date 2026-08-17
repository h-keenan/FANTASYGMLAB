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
        "Explore",
    ),
    "league": (
        "Standings",
        "Power Rankings",
        "Franchise Value",
        "Draft Capital",
        "How to read these boards",
        "League Insights",
        "History",
    ),
    "trade": ("Value change", "Review package"),
    "my-team": ("Roster Posture", "How these roster grades work", "Roster Core", "Position Groups", "Draft Capital"),
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
        "Dynasty value",
        "Why we value him this way",
        "Current fantasy evidence",
        "Recent News",
        "More details",
    ),
    "header-geometry": (
        "Header Geometry",
        "Switch League",
        "Alerts",
        "You",
    ),
    "guest-landing": (
        "Import your league",
        "Load my leagues",
        "Save your leagues",
    ),
    "trade-analyzer": (
        "You receive",
        "You send",
        "Analyze Trade",
        "Build the trade",
    ),
    "methodology": (
        "How FantasyGM Lab Evaluates Players",
        "What FantasyGM Lab does not claim",
        "Value is league-specific",
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


def _ensure_trade_supporting(page, dialog) -> None:
    """Package copy is immediate; supporting metrics load on demand."""

    dialog.get_by_text("Synthetic target rationale.", exact=True).first.wait_for(
        state="visible", timeout=30_000
    )
    load_metrics = dialog.get_by_role("button", name=re.compile(r"Load supporting metrics", re.I))
    evidence = dialog.get_by_text("Supporting evidence", exact=True)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and load_metrics.count() == 0 and evidence.count() == 0:
        page.wait_for_timeout(100)
    if load_metrics.count():
        load_metrics.first.click()
    evidence.wait_for(state="visible", timeout=30_000)


def _capture_trade_flow(page, output: Path, width: int) -> dict:
    """Exercise the summary → trade → dossier → trade path in one dialog."""

    summary_frame = _frame_with_selector(page, ".trade-summary-card")
    summary_frame.locator(".trade-summary-card").click()
    page.locator('[data-testid="stDialog"]').wait_for(state="visible", timeout=30_000)
    detail_frame = _frame_with_selector(page, "[data-trade-detail-key]")
    dialog = page.locator('[data-testid="stDialog"]')
    _ensure_trade_supporting(page, dialog)
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
    dialog = page.locator('[data-testid="stDialog"]')
    _ensure_trade_supporting(page, dialog)
    page.wait_for_timeout(750)
    returned_name = f"trade-detail-returned-{width}x844.png"
    page.screenshot(path=str(output / returned_name), full_page=True)
    return {
        "expanded": expanded_name,
        "dossier": dossier_name,
        "returned": returned_name,
        "dialogContract": dialog_contract,
    }


def _open_team_snapshot_expander(page) -> None:
    """Reveal Team Snapshot tiles collapsed after the executive action layer."""

    visible_tiles = page.locator(".summary-tile-tappable").locator("visible=true")
    if visible_tiles.count() == 0:
        expander = page.locator('[data-testid="stExpander"]').filter(has_text="Team Snapshot")
        expander.first.wait_for(state="attached", timeout=30_000)
        header = expander.get_by_role("button").first
        if header.count() == 0:
            header = expander.locator("summary").first
        header.click()
    visible_tiles.first.wait_for(state="visible", timeout=30_000)


def _capture_metric_flow(page, output: Path, width: int) -> dict:
    _open_team_snapshot_expander(page)
    frame = _frame_with_selector(page, ".summary-tile-tappable")
    captures = {}
    for index, slug in ((1, "average-age"), (2, "starter-strength")):
        tile = frame.locator(".summary-tile-tappable").nth(index)
        tile.scroll_into_view_if_needed()
        tile.click()
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
        _open_team_snapshot_expander(page)
        frame = _frame_with_selector(page, ".summary-tile-tappable")
    return captures


def _capture_waiver_flow(page, output: Path, width: int) -> dict:
    frame = _frame_with_selector(page, ".free-agent-card")
    filename = f"waiver-priority-expanded-{width}x844.png"
    frame.locator(".free-agent-card").first.click()
    page.locator('[data-testid="stDialog"]').wait_for(state="visible", timeout=30_000)
    page.get_by_text(re.compile(r"Dynasty value", re.I)).wait_for(state="visible", timeout=30_000)
    dialog_contract = _dialog_contract(page)
    page.wait_for_timeout(750)
    page.screenshot(path=str(output / filename), full_page=True)
    return {"expandedPriority": filename, "dialogContract": dialog_contract}


def _capture_player_dossier_flow(page, output: Path, width: int) -> dict:
    page.get_by_role("button", name="More details").click()
    page.get_by_role("button", name="Hide details").wait_for(
        state="visible", timeout=30_000
    )
    page.get_by_text("Complete Season Stats", exact=True).locator("visible=true").first.wait_for(
        state="visible", timeout=30_000
    )
    page.get_by_text("2023", exact=True).first.wait_for(state="visible", timeout=30_000)
    expanded_name = f"player-dossier-history-expanded-{width}x844.png"
    page.screenshot(path=str(output / expanded_name), full_page=True)
    complete_name = f"player-dossier-complete-stats-{width}x844.png"
    page.screenshot(path=str(output / complete_name), full_page=True)
    page.get_by_text("Executive Summary", exact=True).wait_for(state="visible", timeout=30_000)
    advanced_name = f"player-dossier-advanced-{width}x844.png"
    page.screenshot(path=str(output / advanced_name), full_page=True)
    page.get_by_role("button", name="Hide details").click()
    page.get_by_role("button", name="More details").wait_for(
        state="visible", timeout=30_000
    )
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
    orb = page.get_by_role("button", name=re.compile(r"Open GM menu|^(GM|Menu)$", re.I))
    orb_box = orb.bounding_box()
    orb_styles = orb.evaluate(
        """el => {
          const c = getComputedStyle(el);
          return {
            radius: c.borderRadius,
            color: c.color,
            fontSize: c.fontSize,
            textIndent: c.textIndent,
            overflow: c.overflow,
            bgImage: c.backgroundImage.slice(0, 48),
            width: c.width,
            height: c.height,
          };
        }"""
    )
    if not orb_box or min(orb_box["width"], orb_box["height"]) + 0.01 < 44:
        raise AssertionError(f"undersized GM control: {orb_box}")
    # Product contract (#231/#235): circular icon control with hidden label.
    radius = str(orb_styles.get("radius") or "")
    if radius != "50%":
        raise AssertionError(f"GM control must be circular (50%), got border-radius={radius}")
    # Visible label must not leak as O / PE / OPEN.
    if str(orb_styles.get("color") or "") not in {
        "rgba(0, 0, 0, 0)",
        "transparent",
        "rgba(0,0,0,0)",
    }:
        raise AssertionError(f"GM label color not hidden: {orb_styles.get('color')}")
    if str(orb_styles.get("fontSize") or "") not in {"0px", "0"}:
        raise AssertionError(f"GM label font-size not clipped: {orb_styles.get('fontSize')}")
    if "url(" not in str(orb_styles.get("bgImage") or ""):
        raise AssertionError(f"GM mark background missing: {orb_styles.get('bgImage')}")
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
        if min(button["width"], button["height"]) > 0
        and min(button["width"], button["height"]) + 0.01 < 44
    ]
    if small_targets:
        failures.append(f"undersized GM targets: {small_targets}")
    if current_style["label"].casefold() != "dashboard" or current_style["borderLeft"] != "3px" or current_style["radius"] != "0px":
        failures.append(f"current route is not structurally highlighted: {current_style}")
    if failures:
        raise AssertionError("; ".join(failures))
    filename = f"navigation-expanded-{width}x844.png"
    page.screenshot(path=str(output / filename), full_page=True)
    return {"expanded": filename, "orb": {"box": orb_box, "radius": orb_styles.get("radius"), "styles": orb_styles}, "menu": metrics, "current": current_style}


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
    # Production/harness command trigger is "League" (not "Switch League").
    league_trigger = page.get_by_role("button", name=re.compile(r"^Switch League"))
    if league_trigger.count() == 0:
        league_trigger = page.get_by_role("button", name=re.compile(r"^League$"))
    league_trigger.first.click()
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
    page.get_by_role("button", name=re.compile(r"Open GM menu|^(GM|Menu)$", re.I)).click()
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


def _orb_action_collisions(page) -> dict:
    """Return GM Orb vs in-flow actionable control intersections."""

    return page.evaluate(
        """() => {
          const box = (el) => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            if (r.width <= 1 || r.height <= 1) return null;
            return {
              top: r.top, left: r.left, right: r.right, bottom: r.bottom,
              width: r.width, height: r.height,
              text: ((el.innerText || el.getAttribute('aria-label') || '')
                .trim().split('\\n')[0] || '').slice(0, 80),
            };
          };
          const overlaps = (a, b) => a && b && !(
            a.right <= b.left + 1 || a.left >= b.right - 1
            || a.bottom <= b.top + 1 || a.top >= b.bottom - 1
          );
          const area = (a, b) => {
            const x = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
            const y = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
            return x * y;
          };
          const marker = document.querySelector('.mobile-gm-floating-trigger-marker');
          if (!marker) return {orb: null, hits: []};
          const orbRoot = marker.closest('[class*="st-key-mobile_gm_sheet_trigger_"]')
            || marker.closest('[data-testid="stVerticalBlock"]')
            || marker.parentElement;
          const orb = box(orbRoot) || box(orbRoot && orbRoot.querySelector('button'));
          if (!orb) return {orb: null, hits: []};
          const main = document.querySelector('[data-testid="stMain"]');
          const mainBox = main ? box(main) : null;
          const intersect = (a, b) => {
            if (!a || !b) return null;
            const top = Math.max(a.top, b.top);
            const left = Math.max(a.left, b.left);
            const right = Math.min(a.right, b.right);
            const bottom = Math.min(a.bottom, b.bottom);
            if (right <= left + 1 || bottom <= top + 1) return null;
            return {top, left, right, bottom};
          };
          const hits = [];
          document.querySelectorAll(
            'button, a, [role="button"], summary, [data-testid="stExpander"] details, nav a, nav button'
          ).forEach((el) => {
            if (orbRoot && orbRoot.contains(el)) return;
            const visible = intersect(box(el), mainBox);
            if (!visible || !overlaps(orb, visible)) return;
            if (area(orb, visible) < 4) return;
            hits.push({...visible, overlapArea: area(orb, visible), tag: el.tagName, text: (box(el)||{}).text});
          });
          return {orb, hits, mainBox};
        }"""
    )


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
          )].filter(el => {
            const r = el.getBoundingClientRect();
            if (!(r.width > 0 && r.height > 0)) return false;
            // Secondary command tiles may share a multi-column row under tablet
            // widths; they are not "primary content" for the near-zero check (#235).
            if (el.classList.contains('home-command-card-secondary')) return false;
            return true;
          });
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
            heading: hr ? {left: hr.left, right: hr.right, width: hr.width, height: hr.height, scrollWidth: heading.scrollWidth, scrollHeight: heading.scrollHeight, clientWidth: heading.clientWidth, clientHeight: heading.clientHeight, overflowX: getComputedStyle(heading).overflowX, overflowY: getComputedStyle(heading).overflowY} : null,
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
              const actions = document.querySelector('[class*="st-key-executive_command_actions"]')?.getBoundingClientRect();
              return {
                actionsWidth: actions?.width ?? null,
                cells: buttons.map(el => {
                const r = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                const chevron = el.querySelector('svg') || el.querySelector('[aria-hidden="true"]');
                const chevronBox = chevron?.getBoundingClientRect();
                const chevronVisible = !!(chevronBox && chevronBox.width > 0 && chevronBox.height > 0
                  && chevronBox.left >= r.left - 1
                  && chevronBox.right <= r.right + 1
                  && chevronBox.top >= r.top - 1
                  && chevronBox.bottom <= r.bottom + 1);
                return {
                  label: (el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 48),
                  width: r.width,
                  height: r.height,
                  top: r.top,
                  lineHeight: style.lineHeight,
                  paddingTop: style.paddingTop,
                  paddingBottom: style.paddingBottom,
                  transform: style.transform,
                  chevronCenter: chevronBox ? (chevronBox.top + chevronBox.height / 2) : null,
                  chevronVisible,
                  separatorCenter: r.top + r.height / 2,
                  borderLeft: style.borderInlineStartWidth || style.borderLeftWidth,
                  hasPopover: !!el.closest('[data-testid="stPopover"]'),
                };
              }),
              };
            })(),
          };
        }"""
    )
    command_metrics = metrics.get("commandCells") or {}
    if isinstance(command_metrics, list):
        command_cells = command_metrics
        actions_width = None
    else:
        command_cells = command_metrics.get("cells") or []
        actions_width = command_metrics.get("actionsWidth")
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
        clipped = [
            cell.get("label") or "command"
            for cell in command_cells[:3]
            if cell.get("hasPopover") and cell.get("chevronVisible") is False
        ]
        if clipped:
            failures.append(f"command-cell chevron clipped: {clipped}")
        if actions_width is not None and width >= 761 and actions_width + 1 < min(448.0, width * 0.35):
            failures.append(
                f"command rail too narrow for shared desktop width: {actions_width:.1f}px at {width}"
            )
        separators = [cell.get("separatorCenter") for cell in command_cells[:3] if cell.get("separatorCenter") is not None]
        if len(separators) >= 2 and max(separators) - min(separators) > 1.5:
            failures.append(f"separator center drift: {separators}")
        # First cell has no leading button border — rail/row rule owns that edge.
        border_widths = [str(cell.get("borderLeft")) for cell in command_cells[:3]]
        if border_widths and border_widths[0] not in {"0px", "0"}:
            failures.append(f"first command cell should not carry a leading separator: {border_widths[0]}")
        peer_borders = set(border_widths[1:])
        if len(peer_borders) != 1:
            failures.append(f"uneven peer command-cell separators: {peer_borders}")
        elif "0px" in peer_borders or "0" in peer_borders:
            failures.append(f"peer command cells missing separators: {peer_borders}")
    elif surface in {"dashboard", "header-geometry"}:
        failures.append(f"expected three command cells, found {len(command_cells)}")
    if surface == "header-geometry":
        shell_text = str(metrics.get("shellText") or "")
        if "Extremely Serious Dynasty" not in shell_text and "Serious Dynasty" not in shell_text:
            # Long league may ellipsis in the identity row; require at least a long-name stem.
            if "Dynasty Football League" not in shell_text and "Extremely" not in shell_text:
                failures.append("long league fixture missing from identity shell")
        labels = " | ".join(str(cell.get("label") or "") for cell in command_cells[:3])
        if "ALERTS (12)" not in labels.upper() and "ALERTS(12)" not in labels.upper().replace(" ", ""):
            failures.append(f"Alerts (12) fixture missing from command cells: {labels}")
        widths = [float(cell.get("width") or 0) for cell in command_cells[:3]]
        if len(widths) == 3 and widths[0] + 1 < max(widths[1], widths[2]):
            failures.append(f"League column narrower than peers under content-aware weights: {widths}")
    if metrics["scrollWidth"] > metrics["viewport"] + 1:
        failures.append(f"horizontal overflow: {metrics['scrollWidth']} > {metrics['viewport']}")
    heading = metrics["heading"]
    if not heading:
        failures.append("missing primary heading")
    else:
        if heading["left"] < -1 or heading["right"] > width + 1:
            failures.append("primary heading is outside viewport")
        overflow_x = str(heading.get("overflowX") or "")
        overflow_y = str(heading.get("overflowY") or "")
        clipped_x = overflow_x in {"hidden", "clip"} and heading["scrollWidth"] > heading["clientWidth"] + 1
        clipped_y = overflow_y in {"hidden", "clip"} and heading["scrollHeight"] > heading["clientHeight"] + 1
        if clipped_x or clipped_y:
            failures.append("primary heading is clipped")
    if metrics["narrow"]:
        failures.append(f"near-zero-width primary content: {metrics['narrow']}")
    if metrics["badTargets"]:
        failures.append(f"unusable tap targets: {metrics['badTargets']}")
    if metrics["exceptions"]:
        failures.append(f"Streamlit exception elements: {metrics['exceptions']}")
    if metrics["visibleChrome"]:
        failures.append(f"visible Streamlit chrome: {metrics['visibleChrome']}")
    if surface == "guest-landing":
        if metrics["shellCount"] != 0:
            failures.append(
                f"guest landing must have zero live executive shells: {metrics['shellCount']}"
            )
        if metrics.get("switcherCount", 0) not in (0, None) and int(metrics.get("switcherCount") or 0) != 0:
            failures.append(
                f"guest landing must not mount league switcher: {metrics.get('switcherCount')}"
            )
        command_cells = (metrics.get("commandCells") or {}).get("cells") or []
        command_labels = " | ".join(str(cell.get("label") or "") for cell in command_cells)
        if any(label in command_labels.upper() for label in ("SELECT", "ALERTS", "YOU", "LEAGUE")):
            failures.append(f"guest landing mounted live command cells: {command_labels}")
    else:
        top_limit = 26 if width >= 1024 else 24
        if metrics["workspaceTop"] is None or metrics["workspaceTop"] > top_limit:
            failures.append(f"unreclaimed top chrome space: {metrics['workspaceTop']}")
        if metrics["shellCount"] != 1:
            failures.append(f"expected one executive shell: {metrics['shellCount']}")
        if metrics["switcherCount"] != 1:
            failures.append(f"expected one integrated league switcher: {metrics['switcherCount']}")
        if any(label in metrics["shellText"] for label in ("Power Rank", "Franchise Rank", "Strategy", "Archetype")):
            failures.append(f"franchise metrics leaked into executive shell: {metrics['shellText']}")
        shell_height_limit = 190 if surface == "header-geometry" else 140
        if width <= 430 and (
            metrics["shellHeight"] is None or metrics["shellHeight"] > shell_height_limit
        ):
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
        avatar = summary_frame.locator(".dg-compact-asset-avatar, .dg-compact-pick-plate").first
        avatar_box = avatar.bounding_box() if avatar.count() else None
        if not card_box or not avatar_box:
            failures.append("trade summary metrics unavailable")
        else:
            title_clipped = summary_frame.locator(".trade-summary-title").evaluate(
                "el => el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1"
            )
            package = summary_frame.locator(".trade-summary-card").first.evaluate(
                """el => {
                  const side = el.querySelector('.trade-summary-side');
                  if (!side) return null;
                  const label = side.querySelector('.trade-summary-side-label');
                  const assets = side.querySelector('.trade-summary-assets');
                  const pack = el.querySelector('.trade-summary-package');
                  const box = (node) => {
                    if (!node) return null;
                    const r = node.getBoundingClientRect();
                    return {left: r.left, right: r.right, top: r.top, width: r.width, height: r.height};
                  };
                  const style = label ? getComputedStyle(label) : null;
                  return {
                    label: box(label),
                    assets: box(assets),
                    package: box(pack),
                    labelDisplay: style ? style.display : '',
                  };
                }"""
            )
            trade_summary = {
                "height": card_box["height"],
                "width": card_box["width"],
                "avatarHeight": avatar_box["height"],
                "avatarWidth": avatar_box["width"],
                "titleClipped": title_clipped,
                "package": package,
            }
            metrics["tradeSummary"] = trade_summary
            if trade_summary["height"] > 420:
                failures.append(f"trade summary too tall: {trade_summary['height']:.1f}px")
            avatar_edge = min(trade_summary["avatarHeight"], trade_summary["avatarWidth"])
            if avatar_edge < 32 or avatar_edge > 48:
                failures.append(
                    f"trade summary identity box off compact contract: {avatar_edge:.1f}px"
                )
            if trade_summary["titleClipped"]:
                failures.append("trade summary title is clipped")
            if package:
                if package.get("labelDisplay") == "none":
                    failures.append("trade summary side labels hidden")
                label_box = package.get("label") or {}
                assets_box = package.get("assets") or {}
                if label_box and assets_box:
                    gap = (assets_box.get("left") or 0) - (label_box.get("right") or 0)
                    if gap > 48:
                        failures.append(f"trade summary label drifted from assets: {gap:.0f}px")
                    if abs((label_box.get("top") or 0) - (assets_box.get("top") or 0)) > 24:
                        failures.append("trade summary label not vertically paired with assets")
                pack_box = package.get("package") or {}
                if width >= 1024 and pack_box.get("width", 0) > 720:
                    failures.append(
                        f"trade summary package stretched too wide: {pack_box.get('width')}"
                    )
        try:
            trade_text = page.inner_text("body")
        except Exception:
            trade_text = str(metrics.get("shellText") or "")
        if trade_text.count("What is Auto?") > 1:
            failures.append("duplicate What is Auto disclosure")
        if "Search return paths from one of your players" in trade_text:
            failures.append("redundant Trade Hub secondary search expander")
        if trade_text.count("Search Around a Player") > 2:
            failures.append("duplicate Search Around a Player entry")
    if surface == "trade-analyzer":
        try:
            analyzer_text = page.inner_text("body")
        except Exception:
            analyzer_text = body_text
        folded = analyzer_text.casefold()
        if "+ Add asset" in analyzer_text:
            failures.append("legacy Add asset toggle still present")
        if "you receive" not in folded or "you send" not in folded:
            failures.append("send/receive grammar missing")
        if "analyze trade" not in folded:
            failures.append("Analyze Trade CTA missing")
        if "build the trade" not in folded:
            failures.append("Build the trade stage missing")
        if "no assets selected" in folded:
            failures.append("legacy empty-package copy still present")
    if surface == "methodology":
        try:
            methodology_text = page.inner_text("body")
        except Exception:
            methodology_text = body_text
        if methodology_text.count("How FantasyGM Lab Evaluates Players") < 1:
            failures.append("methodology title missing")
        if "Load my leagues" in methodology_text or "Import your league" in methodology_text:
            failures.append("marketing/import hero stacked above methodology")
        if methodology_text.count("How FantasyGM Lab Evaluates Players") > 2:
            failures.append("duplicate methodology titles")
    if surface == "dashboard":
        body_text = str(metrics.get("shellText") or "")
        # Prefer full page text from heading metrics path when available.
        try:
            body_text = page.inner_text("body")
        except Exception:
            pass
        if body_text.count("Today's Game Plan") > 1:
            failures.append("duplicate Today's Game Plan headers")
        if "Your Next Move" in body_text:
            failures.append("Your Next Move should not appear when Game Plan owns current actions")
        if "Valuation:" not in body_text:
            failures.append("missing Strategy context on Dashboard")
        if "Lens ·" in body_text:
            failures.append("legacy Lens pill must not appear on Dashboard")
        trade_visual = page.locator("[data-gp-trade-visual]").first
        if trade_visual.count():
            package = trade_visual.evaluate(
                """el => {
                  const r = el.getBoundingClientRect();
                  const give = el.querySelector('.dg-gp-trade-side--give');
                  const get = el.querySelector('.dg-gp-trade-side--get');
                  const mid = el.querySelector('.dg-gp-trade-for');
                  const box = (node) => {
                    if (!node) return null;
                    const b = node.getBoundingClientRect();
                    return {left: b.left, right: b.right, width: b.width, top: b.top};
                  };
                  return {
                    width: r.width,
                    text: el.innerText || '',
                    raw: el.textContent || '',
                    give: box(give),
                    get: box(get),
                    for: box(mid),
                  };
                }"""
            )
            metrics["gamePlanTradeVisual"] = package
            source = f"{package.get('raw', '')} {package.get('text', '')}"
            if "You give" not in source and "YOU GIVE" not in source:
                failures.append("Game Plan trade visual missing give/get labels")
            if "You get" not in source and "YOU GET" not in source:
                failures.append("Game Plan trade visual missing give/get labels")
            if width >= 1024 and package.get("width", 0) > 680:
                failures.append(
                    f"Game Plan trade visual stretched too wide: {package.get('width')}"
                )
            give = package.get("give") or {}
            got = package.get("get") or {}
            mid = package.get("for") or {}
            same_row = (
                give
                and got
                and abs((give.get("top") or 0) - (got.get("top") or 0)) < 16
            )
            if same_row and mid and give.get("right", 0) > (mid.get("left") or 0) + 8:
                failures.append("Game Plan give/FOR/get columns overlap")
            if width >= 1024 and same_row:
                gap = (got.get("left") or 0) - (give.get("right") or 0)
                if gap > 280:
                    failures.append(f"Game Plan give/get drifted apart: {gap:.0f}px")
        if width <= 430:
            geometry = page.evaluate(
                """() => {
                  const root = document.documentElement;
                  const viewport = root.clientWidth;
                  const strategy = [...document.querySelectorAll('button')].find(el => {
                    const r = el.getBoundingClientRect();
                    return (el.innerText || '').includes('Valuation:') && r.width > 1 && r.height > 1;
                  });
                  const refresh = [...document.querySelectorAll('button')].find(el => {
                    const r = el.getBoundingClientRect();
                    const label = (el.innerText || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    return label === 'refresh' && r.width > 1 && r.height > 1;
                  });
                  const meta = document.querySelector('.dg-dashboard-page-meta');
                  const box = (el) => {
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height};
                  };
                  return {
                    viewport,
                    scrollWidth: root.scrollWidth,
                    strategy: box(strategy),
                    strategyText: strategy ? (strategy.innerText || '') : '',
                    strategyClipped: strategy ? (strategy.scrollWidth > strategy.clientWidth + 1) : null,
                    refresh: box(refresh),
                    meta: box(meta),
                  };
                }"""
            )
            metrics["dashboardGeometry"] = geometry
            if geometry.get("scrollWidth", 0) > geometry.get("viewport", 0) + 1:
                failures.append(
                    f"dashboard horizontal overflow: {geometry['scrollWidth']} > {geometry['viewport']}"
                )
            strategy = geometry.get("strategy") or {}
            if not strategy:
                failures.append("Strategy context control missing")
            else:
                if strategy.get("right", 0) > geometry.get("viewport", 0) + 1:
                    failures.append("Strategy control overflows viewport")
                if geometry.get("strategyClipped"):
                    failures.append("Strategy label is clipped")
                strategy_text = str(geometry.get("strategyText") or "")
                if "Valuation:" not in strategy_text or "Balanced" not in strategy_text:
                    failures.append("Strategy label incomplete")
            meta = geometry.get("meta") or {}
            if strategy and meta:
                overlap = not (
                    strategy.get("bottom", 0) <= meta.get("top", 0) + 1
                    or meta.get("bottom", 0) <= strategy.get("top", 0) + 1
                )
                if overlap:
                    failures.append("Strategy collides with league context")
            refresh = geometry.get("refresh") or {}
            if refresh and refresh.get("right", 0) > geometry.get("viewport", 0) + 1:
                failures.append("Refresh overflows viewport")
            if refresh and refresh.get("left", 0) < -1:
                failures.append("Refresh clipped on the left")
            header_flow = page.evaluate(
                """() => {
                  const box = (el) => {
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height};
                  };
                  const overlaps = (a, b) => {
                    if (!a || !b) return false;
                    return !(a.bottom <= b.top + 1 || b.bottom <= a.top + 1);
                  };
                  const lede = document.querySelector('.dg-game-plan-lede, [class*="_lede"] [data-testid="stCaptionContainer"]');
                  const utility = document.querySelector('.dg-game-plan-utility, [class*="_utility"] [data-testid="stCaptionContainer"]');
                  const refreshBtn = [...document.querySelectorAll('button')].find(el => {
                    const r = el.getBoundingClientRect();
                    const label = (el.innerText || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    return label === 'refresh' && r.width > 1 && r.height > 1;
                  });
                  const ledeBox = box(lede);
                  const utilityBox = box(utility);
                  const refreshBox = box(refreshBtn);
                  return {
                    lede: ledeBox,
                    utility: utilityBox,
                    refresh: refreshBox,
                    ledeFont: lede ? getComputedStyle(lede).fontSize : '',
                    utilityFont: utility ? getComputedStyle(utility).fontSize : '',
                    ledeUtilityOverlap: overlaps(ledeBox, utilityBox),
                    utilityRefreshOverlap: overlaps(utilityBox, refreshBox),
                    ledeRefreshOverlap: overlaps(ledeBox, refreshBox),
                  };
                }"""
            )
            metrics["gamePlanHeaderFlow"] = header_flow
            if header_flow.get("ledeUtilityOverlap"):
                failures.append("Game Plan subtitle overlaps updated timestamp")
            if header_flow.get("utilityRefreshOverlap"):
                failures.append("Updated timestamp overlaps Refresh")
            if header_flow.get("ledeRefreshOverlap"):
                failures.append("Game Plan subtitle overlaps Refresh")
            if header_flow.get("lede") and header_flow.get("refresh"):
                if (header_flow["lede"].get("bottom") or 0) > (
                    header_flow["refresh"].get("top") or 0
                ) + 1:
                    failures.append("Game Plan subtitle is not above Refresh in document flow")
        if body_text.find("Today's Game Plan") >= 0:
            has_refresh = "refresh" in body_text.casefold()
            if not has_refresh:
                try:
                    has_refresh = page.get_by_role("button", name="Refresh").count() > 0
                except Exception:
                    has_refresh = False
            if not has_refresh:
                failures.append("Refresh action missing from Game Plan")
        what_changed_at = body_text.find("What Changed")
        game_plan_at = body_text.find("Today's Game Plan")
        if (
            what_changed_at >= 0
            and game_plan_at >= 0
            and what_changed_at < game_plan_at
        ):
            failures.append("What Changed must appear after Today's Game Plan")
    if width <= 900:
        orb_hits = _orb_action_collisions(page)
        metrics["gmOrbCollisions"] = orb_hits
        if orb_hits.get("orb") and orb_hits.get("hits"):
            sample = orb_hits["hits"][0]
            failures.append(
                "GM Orb covers actionable control "
                f"{sample.get('text')!r} overlap={sample.get('overlapArea')}"
            )
        if surface in {"dashboard", "navigation", "design-system"}:
            orb = orb_hits.get("orb") or {}
            if not orb or float(orb.get("width") or 0) < 40 or float(orb.get("height") or 0) < 40:
                failures.append("GM Orb missing or collapsed on mobile")
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
