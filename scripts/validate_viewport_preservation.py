"""Browser viewport / focus contract for in-place Streamlit actions."""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from playwright.sync_api import Page

MEASURE_JS = """() => {
  const doc = document;
  const main = doc.querySelector('[data-testid="stMain"]');
  const se = doc.scrollingElement || doc.documentElement;
  const ae = doc.activeElement;
  const label = (el) => {
    if (!el || el === doc.body || el === doc.documentElement) return "BODY";
    const t = (el.innerText || el.getAttribute("aria-label") || el.tagName || "")
      .trim().replace(/\\s+/g, " ").slice(0, 80);
    return `${el.tagName}:${t}`.slice(0, 140);
  };
  const maxMain = main ? Math.max(0, main.scrollHeight - main.clientHeight) : 0;
  return {
    hash: location.hash,
    windowScrollY: window.scrollY || 0,
    seScrollTop: se ? se.scrollTop : 0,
    mainScrollTop: main ? main.scrollTop : 0,
    mainScrollHeight: main ? main.scrollHeight : 0,
    mainClientHeight: main ? main.clientHeight : 0,
    mainMax: maxMain,
    atMainBottom: maxMain > 40 && main && main.scrollTop >= maxMain - 8,
    atMainTop: main ? main.scrollTop <= 2 : (window.scrollY || 0) <= 2,
    active: label(ae),
  };
}"""


def measure(page: Page) -> dict[str, Any]:
    return page.evaluate(MEASURE_JS)


def wait_for_restore_kick(page: Page, old_seq: int, *, timeout_ms: int = 90_000) -> None:
    """Wait for the same rerun-completion signal click_in_place() uses.

    A GM Orb open/close click triggers a full Streamlit rerun like any other
    button — on a loaded CI runner that rerun (plus the app's own scroll
    restore ladder, up to 1200ms after the kick — see
    modules.viewport_preservation's restore() setTimeout schedule) can take
    longer than any fixed guess. Waiting for this signal to actually fire,
    rather than assuming it has after N milliseconds, is what
    click_in_place() already does for every other in-place action here.
    """
    page.wait_for_function(
        "old => Number(window.__dgViewportRestoreKickSeq || 0) > old",
        arg=old_seq,
        timeout=timeout_ms,
    )


def wait_for_scroll_stable(page: Page, *, timeout_ms: int = 1200, poll_ms: int = 100) -> dict[str, Any]:
    """Poll mainScrollTop until it stops moving, instead of a fixed sleep.

    A flat `wait_for_timeout` assumes the open/close animation always
    settles within that window; under CI runner load it sometimes hasn't,
    producing a spurious scroll-delta failure. Requiring two consecutive
    identical reads (not just one) guards against catching the scroll
    mid-animation at a moment it happens to pause; the timeout is still a
    hard ceiling so a genuinely stuck animation doesn't hang the check.
    """
    last = measure(page)
    stable_reads = 0
    elapsed = 0
    while elapsed < timeout_ms:
        page.wait_for_timeout(poll_ms)
        elapsed += poll_ms
        current = measure(page)
        if current["mainScrollTop"] == last["mainScrollTop"]:
            stable_reads += 1
            if stable_reads >= 2:
                return current
        else:
            stable_reads = 0
        last = current
    return last


def wait_app(page: Page) -> None:
    page.wait_for_selector('[data-testid="stApp"]', timeout=90_000)
    page.wait_for_selector('[data-testid="stMain"]', timeout=90_000)
    page.wait_for_function("document.fonts && document.fonts.status === 'loaded'", timeout=90_000)
    page.wait_for_function("Number(window.__dgViewportRestoreKickSeq || 0) >= 1", timeout=90_000)


def button_locator(page: Page, name: str):
    loc = page.get_by_role("button", name=re.compile(rf"^{re.escape(name)}$", re.I))
    if loc.count() == 0:
        loc = page.get_by_role("button", name=re.compile(name, re.I))
    return loc.first


def scroll_action_into_view(page: Page, name: str, *, target_y: int = 200) -> dict[str, Any]:
    return page.evaluate(
        """([name, targetY]) => {
          const main = document.querySelector('[data-testid="stMain"]');
          const btn = Array.from(document.querySelectorAll("button")).find((b) => {
            const text = (b.innerText || b.getAttribute("aria-label") || "")
              .replace(/\\s+/g, " ").trim();
            return text.toLowerCase() === String(name).toLowerCase()
              || text.toLowerCase().indexOf(String(name).toLowerCase()) >= 0;
          });
          if (!main || !btn) throw new Error(`viewport target missing: ${name}`);
          const br = btn.getBoundingClientRect();
          const mr = main.getBoundingClientRect();
          main.scrollTop += (br.top - mr.top - targetY);
          // A real user repositioning the page for their next click does it
          // with a scroll/wheel gesture, which the app's own
          // cancelForUserScroll listener uses to drop any stale in-place
          // anchor left over from a prior click (unless that anchor is a
          // lockScroll one, e.g. the GM orb's fixed trigger). Setting
          // scrollTop directly here — as this harness does to position the
          // next target without simulating pixel-perfect mouse/wheel events —
          // bypasses that listener, so a still-"fresh" (<5s old) anchor from
          // the previous in-place action can survive and have its own
          // delayed restore() corrections fire later using now-stale
          // geometry, fighting this repositioning. Mirror the real-gesture
          // behavior here so the harness doesn't leave state a genuine user
          // action would have cleared.
          const anchor = window.__dgInPlaceAnchor;
          if (anchor && !anchor.lockScroll) window.__dgInPlaceAnchor = null;
          const box = btn.getBoundingClientRect();
          return {
            ok: true,
            scrollTop: main.scrollTop,
            box: { top: box.top, bottom: box.bottom, height: box.height },
          };
        }""",
        [name, target_y],
    )


def action_box(page: Page, name: str) -> dict[str, Any] | None:
    return page.evaluate(
        """(name) => {
          const btn = Array.from(document.querySelectorAll("button")).find((b) => {
            const text = (b.innerText || b.getAttribute("aria-label") || "")
              .replace(/\\s+/g, " ").trim();
            return text.toLowerCase() === String(name).toLowerCase()
              || text.toLowerCase().indexOf(String(name).toLowerCase()) >= 0;
          });
          if (!btn) return null;
          const box = btn.getBoundingClientRect();
          const vh = window.innerHeight || 0;
          return {
            top: box.top,
            bottom: box.bottom,
            height: box.height,
            onscreen: box.bottom > 8 && box.top < (vh - 8),
          };
        }""",
        name,
    )


def assert_in_place_contract(
    before: dict[str, Any],
    after: dict[str, Any],
    box_after: dict[str, Any] | None,
    *,
    action: str,
    allow_top: bool = False,
) -> None:
    if after.get("hash"):
        raise AssertionError(f"{action}: unexpected hash {after['hash']}")
    if after.get("atMainBottom"):
        raise AssertionError(f"{action}: viewport jumped to document bottom")
    if after.get("atMainTop") and not before.get("atMainTop") and not allow_top:
        raise AssertionError(f"{action}: viewport jumped to document top")
    if box_after is None:
        return
    if not box_after.get("onscreen"):
        raise AssertionError(f"{action}: originating control left the viewport; before={before}; after={after}; box_after={box_after}")


def click_in_place(page: Page, name: str) -> dict[str, Any]:
    button_locator(page, name).wait_for(state="visible", timeout=90_000)
    page.wait_for_function("window.__dgViewportPreserveBound === true", timeout=90_000)
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    scrolled = scroll_action_into_view(page, name)
    before = measure(page)
    before["box"] = action_box(page, name)
    before["scrollSetup"] = scrolled
    old_seq = page.evaluate("window.__dgViewportRestoreKickSeq || 0")
    before["kickSeq"] = old_seq
    button_locator(page, name).click(timeout=15_000)
    try:
        page.wait_for_function(
            "old => Number(window.__dgViewportRestoreKickSeq || 0) > old",
            arg=old_seq,
            timeout=90_000,
        )
    except Exception as exc:
        diag = page.evaluate("""() => ({
          kickSeq: window.__dgViewportRestoreKickSeq || 0,
          helperBound: window.__dgViewportPreserveBound === true,
          target: Boolean(Array.from(document.querySelectorAll('button')).find(b =>
            (b.innerText || b.getAttribute('aria-label') || '').toLowerCase().includes('resend confirmation email'))),
          main: (() => { const m = document.querySelector('[data-testid="stMain"]'); return m ? {scrollTop:m.scrollTop, scrollHeight:m.scrollHeight, clientHeight:m.clientHeight} : null })()
        })""")
        raise AssertionError(f"{name}: late restore kick did not increment; old_seq={old_seq}; diag={diag}") from exc
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    after = measure(page)
    after["box"] = action_box(page, name)
    assert_in_place_contract(before, after, after.get("box"), action=name)
    return {"before": before, "after": after}


def focus_feedback_and_measure(page: Page) -> dict[str, Any]:
    """Safari-class: after a disabled control, focus can land on footer Feedback."""

    before = measure(page)
    page.evaluate(
        """() => {
          const btn = Array.from(document.querySelectorAll("button")).find((b) => {
            const text = (b.innerText || b.getAttribute("aria-label") || "").toLowerCase();
            return text.indexOf("feedback") >= 0;
          });
          if (btn && typeof btn.focus === "function") btn.focus();
        }"""
    )
    page.wait_for_timeout(250)
    after = measure(page)
    return {"before": before, "after": after}


def run_viewport_matrix(page: Page, *, base_url: str) -> dict[str, Any]:
    report: dict[str, Any] = {"cases": {}}
    page.goto(
        f"{base_url}/?surface=guest-landing&fixture_auth=pending_definite",
        wait_until="domcontentloaded",
        timeout=90_000,
    )
    wait_app(page)
    report["cases"]["resend_confirmation"] = click_in_place(page, "Resend confirmation email")
    steal = focus_feedback_and_measure(page)
    report["cases"]["resend_focus_feedback"] = steal
    if steal["after"].get("atMainBottom"):
        raise AssertionError("focusing Feedback after resend jumped to the bottom")
    resend_box = action_box(page, "Resend confirmation email")
    if resend_box and not resend_box.get("onscreen"):
        raise AssertionError("resend control left the viewport after Feedback focus")

    page.goto(f"{base_url}/?surface=dashboard", wait_until="domcontentloaded", timeout=90_000)
    wait_app(page)
    report["cases"]["dashboard_refresh"] = click_in_place(page, "Refresh")
    waiver = page.get_by_role("button", name=re.compile(r"Open Waivers", re.I))
    if waiver.count():
        report["cases"]["dashboard_waiver"] = click_in_place(page, "Open Waivers")
    orb_before = measure(page)
    orb = page.get_by_role("button", name=re.compile(r"Open GM menu", re.I))
    if orb.count():
        scroll_action_into_view(page, "Open GM menu", target_y=400)
        orb_before = measure(page)
        old_seq = page.evaluate("window.__dgViewportRestoreKickSeq || 0")
        orb.first.click()
        wait_for_restore_kick(page, old_seq)
        orb_after = wait_for_scroll_stable(page, timeout_ms=1500)
        delta = abs(orb_after["mainScrollTop"] - orb_before["mainScrollTop"])
        if delta > 48:
            raise AssertionError(f"GM Orb open changed page scroll by {delta}px")
        if orb_after.get("atMainBottom"):
            raise AssertionError("GM Orb open jumped to the bottom")
        close = page.get_by_role("button", name=re.compile(r"^Close$", re.I))
        if close.count():
            close_old_seq = page.evaluate("window.__dgViewportRestoreKickSeq || 0")
            close.first.click()
            wait_for_restore_kick(page, close_old_seq)
            orb_closed = wait_for_scroll_stable(page, timeout_ms=1500)
            if orb_closed.get("atMainBottom"):
                raise AssertionError("GM Orb close jumped to the bottom")
        report["cases"]["gm_orb"] = {"before": orb_before, "after": orb_after, "scrollDelta": delta}

    page.goto(f"{base_url}/?surface=viewport-preserve", wait_until="domcontentloaded", timeout=90_000)
    wait_app(page)
    report["cases"]["strategy_toggle"] = click_in_place(page, "Strategy & analysis")
    report["cases"]["pqv_more_details"] = click_in_place(page, "STATS")
    report["cases"]["viewport_refresh"] = click_in_place(page, "Refresh")

    page.goto(f"{base_url}/?surface=player-dossier", wait_until="domcontentloaded", timeout=90_000)
    wait_app(page)
    report["cases"]["dossier_more_details"] = click_in_place(page, "STATS")

    page.goto(f"{base_url}/?surface=my-team", wait_until="domcontentloaded", timeout=90_000)
    wait_app(page)
    report["cases"]["my_team_load"] = measure(page)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument("--width", type=int, default=390)
    parser.add_argument("--height", type=int, default=844)
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": args.width, "height": args.height},
            is_mobile=args.width <= 430,
            has_touch=args.width <= 430,
        )
        try:
            report = run_viewport_matrix(page, base_url=args.base_url.rstrip("/"))
        finally:
            browser.close()
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
