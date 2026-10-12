"""Viewport / focus preservation contract for in-place reruns."""

from __future__ import annotations

import ast
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from modules.app_styles import APP_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.viewport_preservation import VIEWPORT_PRESERVE_JS, VIEWPORT_RESTORE_KICK_JS
from scripts.measure_interaction_rerun_architecture import count_explicit_reruns


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
HARNESS = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")


def test_viewport_helper_is_event_driven_and_not_scrollintoview():
    assert "scrollIntoView" not in VIEWPORT_PRESERVE_JS
    assert "MutationObserver" not in VIEWPORT_PRESERVE_JS
    assert "setInterval" not in VIEWPORT_PRESERVE_JS
    assert "requestAnimationFrame" in VIEWPORT_PRESERVE_JS
    assert "pointerdown" in VIEWPORT_PRESERVE_JS
    assert "focusin" in VIEWPORT_PRESERVE_JS
    assert "__dgInPlaceAnchor" in VIEWPORT_PRESERVE_JS
    assert 'addEventListener("touchmove", cancelForUserScroll' in VIEWPORT_PRESERVE_JS
    assert 'addEventListener("wheel", cancelForUserScroll' in VIEWPORT_PRESERVE_JS
    assert "__dgUserScrollIntentAt" in VIEWPORT_PRESERVE_JS
    assert "scrollIntoView" not in APP


def test_label_fallback_requires_unique_replacement_identity():
    """The bounded label fallback handles key churn without arbitrary matches."""
    assert "actionLabel = (node)" in VIEWPORT_PRESERVE_JS
    assert "matches.length === 1 ? matches[0] : null" in VIEWPORT_PRESERVE_JS
    assert "A duplicate label has no safe identity" in VIEWPORT_PRESERVE_JS
    assert "last.key && last.label" not in VIEWPORT_PRESERVE_JS
    assert VIEWPORT_PRESERVE_JS.count("const actionLabel =") == 1
    assert VIEWPORT_PRESERVE_JS.index("const actionLabel =") < VIEWPORT_PRESERVE_JS.index("const restore =")


def test_app_and_harness_mount_shared_helper():
    assert "viewport_preservation.render_viewport_preservation()" in APP
    assert "viewport_preservation.render_viewport_preservation()" in HARNESS
    assert 'st.components.v2.component(\n    "viewport_preserve"' not in APP
    assert APP.count("_render_navigation_scroll_reset(current_page, league_id=") == 1
    assert "render_viewport_restore_kick()" in APP
    assert "render_viewport_restore_kick()" in HARNESS


def test_late_kick_only_calls_existing_restore_after_two_frames():
    assert "__dgRestoreInPlaceAnchor" in VIEWPORT_PRESERVE_JS
    assert "requestAnimationFrame" in VIEWPORT_RESTORE_KICK_JS
    assert "__dgRestoreInPlaceAnchor()" in VIEWPORT_RESTORE_KICK_JS
    assert "__dgViewportRestoreKickSeq" in VIEWPORT_RESTORE_KICK_JS
    assert "addEventListener" not in VIEWPORT_RESTORE_KICK_JS
    assert "setInterval" not in VIEWPORT_RESTORE_KICK_JS
    assert "MutationObserver" not in VIEWPORT_RESTORE_KICK_JS


def test_intentional_nav_detection_covers_real_navigation_call_sites():
    """Every plain st.button that commits a real cross-page route must be
    recognized by isIntentionalNav(), or the in-place scroll-anchor system
    fights navigation_state.py's scroll-reset-to-top and the page visibly
    jumps on every real navigation (#937-class bug). Nothing in the app ever
    sets data-fgl-intentional-nav and none of these are <a href> links, so
    detection relies on each button's own Streamlit "st-key-<key>" class.
    This pins the key patterns in VIEWPORT_PRESERVE_JS against the literal
    `key=` strings at each real call site so a future rename trips here
    instead of silently reintroducing the jump.
    """
    assert "isIntentionalNavKey" in VIEWPORT_PRESERVE_JS
    assert "INTENTIONAL_NAV_KEY_PREFIXES" in VIEWPORT_PRESERVE_JS
    assert "INTENTIONAL_NAV_KEY_SUFFIXES" in VIEWPORT_PRESERVE_JS
    assert "INTENTIONAL_NAV_KEY_EXACT" in VIEWPORT_PRESERVE_JS
    assert "isIntentionalNavKey(keyFrom(el))" in VIEWPORT_PRESERVE_JS

    workspace_ui_src = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")
    gm_targets_ui_src = (ROOT / "modules" / "gm_targets_ui.py").read_text(encoding="utf-8")
    live_draft_ui_src = (ROOT / "modules" / "live_draft_ui.py").read_text(encoding="utf-8")
    dashboard_orientation_src = (
        ROOT / "modules" / "dashboard_orientation.py"
    ).read_text(encoding="utf-8")
    dashboard_workflow_src = (
        ROOT / "modules" / "dashboard_workflow.py"
    ).read_text(encoding="utf-8")
    founder_ops_ui_src = (ROOT / "modules" / "founder_ops_ui.py").read_text(encoding="utf-8")
    founder_labs_ui_src = (ROOT / "modules" / "founder_labs_ui.py").read_text(encoding="utf-8")
    notification_center_src = (
        ROOT / "modules" / "notification_center.py"
    ).read_text(encoding="utf-8")

    # (source holding the real call site, the literal key= there, the
    # matching prefix pattern that must appear in VIEWPORT_PRESERVE_JS)
    prefix_cases = [
        (workspace_ui_src, 'key=f"home_quick_action_{row_idx}_{route_key}"', "home_quick_action_"),
        (APP, 'key=f"player_quick_view_trade_hub_{player_id}"', "player_quick_view_trade_hub_"),
        (APP, 'key=f"premium_lock_route_{key_base}"', "premium_lock_route_"),
        (APP, 'key=f"mobile_sheet_nav_{page.key}"', "mobile_sheet_nav_"),
        (gm_targets_ui_src, 'key=f"gm_targets_handoff_{dest_key}_{card.player_id}"', "gm_targets_handoff_"),
        (live_draft_ui_src, 'key=f"live_rank_trade_{player_id}"', "live_rank_trade_"),
        # #95x-class regression: added by later PRs without a matching key
        # pattern, reintroducing the #937/#939 jump.
        (founder_labs_ui_src, 'key=f"founder_labs_open_{row.key}"', "founder_labs_open_"),
        (APP, 'key=f"workflow_return_{current_page}_{context.origin_page}"', "workflow_return_"),
        (
            notification_center_src,
            'key=f"urgent_delivery_open_{_text(record.get(\'id\'))}"',
            "urgent_delivery_open_",
        ),
        (APP, 'key_prefix=f"executive_notifications_{current_page or \'home\'}"', "executive_notifications_"),
    ]
    for source, literal_key, pattern in prefix_cases:
        assert literal_key in source, f"navigation call site moved or renamed: {literal_key!r}"
        assert f'"{pattern}"' in VIEWPORT_PRESERVE_JS, f"missing intentional-nav key pattern: {pattern!r}"

    suffix_cases = [
        (APP, 'key=f"{key_prefix}_{route_key}_handoff"', "_handoff"),
        (APP, 'key=f"{key_prefix}_open_trade_hub"', "_open_trade_hub"),
        (APP, 'key=f"{key_prefix}_open_trade_analyzer"', "_open_trade_analyzer"),
        (dashboard_orientation_src, 'key=f"{scope_key}_my_team"', "_my_team"),
        # #95x-class regression: added by later PRs without a matching key
        # pattern, reintroducing the #937/#939 jump.
        (APP, 'key=f"{key_prefix}_open_premium"', "_open_premium"),
        (APP, 'key=f"{key_prefix}_open_team_stance"', "_open_team_stance"),
        (APP, 'key=f"{key_prefix}_open_founder_labs"', "_open_founder_labs"),
        (APP, 'key=f"{key_prefix}_open_founder_ops"', "_open_founder_ops"),
        (notification_center_src, 'key=f"{action_key_prefix}_see_all"', "_see_all"),
    ]
    for source, literal_key, pattern in suffix_cases:
        assert literal_key in source, f"navigation call site moved or renamed: {literal_key!r}"
        assert f'"{pattern}"' in VIEWPORT_PRESERVE_JS, f"missing intentional-nav key pattern: {pattern!r}"

    assert 'key="gm_targets_empty_open_players"' in gm_targets_ui_src
    assert '"gm_targets_empty_open_players"' in VIEWPORT_PRESERVE_JS

    # Dashboard "module" tiles (render_home_command_tiles) route-navigate
    # via a plain HTML data-route card sharing ONE Streamlit widget key with
    # sibling in-place cards in the same tap-delegation root
    # (interaction_contract.TAP_DELEGATION_JS) — key-based matching alone
    # can never tell those cards apart, so isIntentionalNav() must check the
    # data-route attribute directly instead of (or in addition to) the key
    # allowlist. Pin both the DOM check and the real call site that sets
    # data-route only on the navigating card.
    assert 'el.closest("[data-route]")' in VIEWPORT_PRESERVE_JS
    interaction_contract_src = (
        ROOT / "modules" / "interaction_contract.py"
    ).read_text(encoding="utf-8")
    assert "data-route" in workspace_ui_src
    assert ".home-command-route-card[data-route]" in interaction_contract_src

    # Exact-match call sites added by later PRs (dead "Read recap" button
    # wired live, the player-detail Back button, header League management,
    # and the founder pages) that never got a matching key pattern — the
    # #95x-class regression this fix is comprehensively closing.
    exact_cases = [
        (dashboard_workflow_src, 'key="dashboard_league_recap_teaser"'),
        (APP, 'key="player_detail_back_btn"'),
        (APP, 'key="top_header_change_league"'),
        (APP, 'key="top_header_import_league"'),
        (APP, 'key="top_header_manage_import_empty"'),
        (founder_ops_ui_src, 'key="founder_ops_home"'),
        (founder_labs_ui_src, 'key="founder_labs_to_ops"'),
        (founder_labs_ui_src, 'key="founder_labs_home"'),
    ]
    for source, literal_key in exact_cases:
        assert literal_key in source, f"navigation call site moved or renamed: {literal_key!r}"
        exact_key = literal_key.split('"')[1]
        assert f'"{exact_key}"' in VIEWPORT_PRESERVE_JS, f"missing intentional-nav exact key: {exact_key!r}"


def test_navigation_tracker_reads_stmain_scroller():
    assert "querySelector('[data-testid=\"stMain\"]')" in APP
    assert "main.scrollTop" in APP or "mainScroller" in APP
    assert "__dgNavScrollAt" in APP


def test_no_stmain_bottom_inset_and_app_css_budget():
    media = MOBILE_INTERACTION_OVERLAY_CSS.split("@media (max-width: 900px)", 1)[1]
    main_block = media.split('[data-testid="stMain"]', 1)[1][:900]
    assert "bottom: 0 !important" in main_block
    assert not any(
        line.strip().startswith("bottom: var(--dg-mobile-shell-clearance)")
        for line in main_block.splitlines()
    )
    assert len(APP_CSS) < 393_000


def test_explicit_rerun_count_unchanged():
    assert count_explicit_reruns() <= 63


def test_helper_module_has_no_rerun_or_provider():
    source = (ROOT / "modules" / "viewport_preservation.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr != "rerun"
    assert "requests." not in source
    assert "supabase" not in source.casefold()


def test_debug_pending_confirmation_is_gated(monkeypatch):
    from modules import account_ui
    from modules import auth_supabase

    monkeypatch.delenv("DYNASTYGM_DEBUG_UI", raising=False)
    state: dict = {}
    monkeypatch.setattr(account_ui.st, "session_state", state, raising=False)
    account_ui._ensure_debug_pending_confirmation()
    assert not auth_supabase.is_pending_email_confirmation(state)

    monkeypatch.setenv("DYNASTYGM_DEBUG_UI", "1")
    class _Params(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

    monkeypatch.setattr(account_ui.st, "query_params", _Params(fixture_auth="pending_definite"))
    monkeypatch.setattr(account_ui.st, "session_state", state)
    account_ui._ensure_debug_pending_confirmation()
    assert auth_supabase.is_pending_email_confirmation(state)


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _wait_health(url: str, *, timeout: float = 60.0) -> None:
    import urllib.request

    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "/_stcore/health", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(0.4)
    raise AssertionError(f"Streamlit health failed for {url}: {last_error}")


@pytest.fixture(scope="module")
def harness_url():
    pytest.importorskip("playwright")
    port = _free_port()
    env = os.environ.copy()
    env["BROWSER"] = "none"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "scripts" / "ui_validation_harness.py"),
            "--server.headless",
            "true",
            "--server.address",
            "127.0.0.1",
            "--server.port",
            str(port),
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        _wait_health(url)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.parametrize("width,height", [(390, 844), (1440, 900)])
def test_browser_in_place_actions_keep_region(harness_url, width, height):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    from scripts.validate_viewport_preservation import run_viewport_matrix

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        kwargs = {
            "viewport": {"width": width, "height": height},
            "is_mobile": width <= 430,
            "has_touch": width <= 430,
        }
        if width <= 430:
            kwargs["user_agent"] = (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            )
        page = browser.new_page(**kwargs)
        errors = []
        page.on("pageerror", lambda error: errors.append(f"{page.url}: {error}"))
        page.on("console", lambda message: errors.append(f"{page.url}: {message.text}") if message.type == "error" else None)
        try:
            report = run_viewport_matrix(page, base_url=harness_url)
            assert not errors, errors
        finally:
            browser.close()
    assert "resend_confirmation" in report["cases"]
    before = report["cases"]["resend_confirmation"]["before"]
    after = report["cases"]["resend_confirmation"]["after"]
    assert not after["atMainBottom"]
    if not before["atMainTop"]:
        assert not after["atMainTop"]
    assert "dashboard_refresh" in report["cases"]
    assert "strategy_toggle" in report["cases"]
    assert "pqv_more_details" in report["cases"]


@pytest.mark.parametrize("auth", ["guest", "pending_definite"])
def test_guest_landing_completes_once_without_js_errors(harness_url, auth):
    from playwright.sync_api import sync_playwright
    from scripts.validate_viewport_preservation import wait_app, click_in_place

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        try:
            page.goto(f"{harness_url}/?surface=guest-landing&fixture_auth={auth}")
            wait_app(page)
            assert page.locator('[data-testid="stException"]').count() == 0
            assert page.locator('.st-key-landing_pricing_cta').count() == 1
            assert page.evaluate("window.__dgViewportPreserveBound === true")
            if auth == "pending_definite":
                result = click_in_place(page, "Resend confirmation email")
                assert page.evaluate("window.__dgViewportRestoreKickSeq") > result["before"]["kickSeq"]
                page.evaluate("window.__dgRestoreInPlaceAnchor()")
            assert not errors, errors
        finally:
            browser.close()


def test_real_dom_click_recognizes_fixed_navigation_keys(harness_url):
    """Real-browser regression check for the #95x-class jump.

    test_intentional_nav_detection_covers_real_navigation_call_sites (above)
    pins the literal key= strings against the JS source as plain Python
    strings — it would not catch a bug in keyFrom()'s DOM class-walk or
    isIntentionalNavKey()'s matching itself. This drives a real Chromium
    pointerdown at a real rendered button carrying each literal key= from
    one of the previously-missing real navigation call sites (one EXACT
    key, one PREFIXES-matched key, one SUFFIXES-matched key — see the
    dg_nav_detection_fixture block in scripts/ui_validation_harness.py's
    _viewport_preserve()) and reads back the real shipped isIntentionalNav()
    verdict the browser actually computed, off window.__dgInPlaceAnchor.nav.
    """
    from playwright.sync_api import sync_playwright
    from scripts.validate_viewport_preservation import check_intentional_nav_key, wait_app

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            page.goto(f"{harness_url}/?surface=viewport-preserve")
            wait_app(page)
            for key in (
                "dashboard_league_recap_teaser",  # INTENTIONAL_NAV_KEY_EXACT
                "founder_labs_open_nav_fixture",  # INTENTIONAL_NAV_KEY_PREFIXES
                "nav_fixture_open_premium",  # INTENTIONAL_NAV_KEY_SUFFIXES
            ):
                anchor = check_intentional_nav_key(page, key)
                assert anchor.get("nav") is True, f"{key}: expected isIntentionalNav() to recognize this key, got {anchor!r}"
                assert anchor.get("key") == f"st-key-{key}", f"{key}: keyFrom() resolved the wrong class: {anchor!r}"
            # Negative control: an un-namespaced key must NOT be treated as
            # navigation, or this check would be vacuously true for anything.
            anchor = check_intentional_nav_key(page, "viewport_refresh_inplace")
            assert anchor.get("nav") is False, f"control key wrongly recognized as nav: {anchor!r}"
        finally:
            browser.close()


def test_real_dom_mobile_tap_recognizes_module_route_cards(harness_url):
    """Real-browser regression check for dashboard "module" tiles on mobile.

    coridian_'s repeated report ("modules need to be tappable ... tapping
    still jumps me around like I'm scrolling") is a different gap than the
    #95x key-allowlist regression test_real_dom_click_recognizes_fixed_navigation_keys
    covers above: render_home_command_tiles (modules/workspace_ui.py) draws
    route-navigating cards and in-place Player Quick View cards as plain
    HTML inside ONE shared st.components.v2 tap-delegation root
    (interaction_contract.TAP_DELEGATION_JS), so every card shares a single
    Streamlit widget key — isIntentionalNavKey()'s key matching can never
    tell them apart. isIntentionalNav() instead checks the data-route
    attribute that Python only puts on the navigating card
    (_open_home_command_route / commit_destination_navigation). This drives
    a real mobile-viewport, touch-style pointerdown (not just a desktop
    mouse pointerdown) at both card shapes from the dg_nav_detection_fixture
    block in scripts/ui_validation_harness.py's _viewport_preserve(), and
    reads back the real shipped isIntentionalNav() verdict off
    window.__dgInPlaceAnchor.nav — not a re-implementation of that logic.
    """
    from playwright.sync_api import sync_playwright
    from scripts.validate_viewport_preservation import check_intentional_nav_selector, wait_app

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
        )
        try:
            page.goto(f"{harness_url}/?surface=viewport-preserve")
            wait_app(page)
            anchor = check_intentional_nav_selector(
                page, "[data-route='viewport_fixture_route']", touch=True
            )
            assert anchor.get("nav") is True, (
                f"module route card: expected isIntentionalNav() to recognize "
                f"data-route on a real mobile touch tap, got {anchor!r}"
            )
            # Negative control: the sibling in-place module card (same shared
            # component key, no data-route) must NOT be treated as
            # navigation, or this check would be vacuously true for any card
            # in the tap-delegation root.
            anchor = check_intentional_nav_selector(
                page, ".home-command-player-card", touch=True
            )
            assert anchor.get("nav") is False, (
                f"in-place module card wrongly recognized as nav: {anchor!r}"
            )
        finally:
            browser.close()


def test_real_dom_fragment_scoped_action_keeps_tapped_control_anchored(harness_url):
    """Real-browser regression check for the third recurrence of coridian_'s
    "modules jump around when tapping" report.

    #955's data-route fix (covered above) was correct but addressed a
    different gap than this one. Between #955 and the third report, PR #972
    added @st.fragment to modules/team_stance_ui.py and
    modules/founder_analytics_ui.py (and app.py already had an older
    @st.fragment-scoped Trade Hub "Show more" feed-reveal, from #198) — a
    fragment-scoped rerun never re-executes anything outside the fragment,
    so it never re-mounts render_viewport_preservation()/
    render_viewport_restore_kick(), which live in app.py's main() outside
    every fragment. Those two mounts are what re-schedule the proactive
    rAF/setTimeout restore ladder on every FULL rerun; without a re-mount,
    an in-place action that reveals new content ABOVE the tapped control
    (this fixture's shape, and Trade Hub's "Show more" shape) had nothing
    deterministic left to correct the resulting scroll offset — the
    focusin/scroll listeners only fire on an actual focus or scroll change,
    not a pure layout reflow. The fix schedules that same ladder from
    record() itself (the pointerdown instant), which needs no full-rerun
    remount and so covers fragment reruns the same as full ones.

    A real tap here needs a long enough settle after page load before
    interacting: the component's OWN initial-mount ladder (scheduled at
    page load, independent of this bug) can still have a pending setTimeout
    around 1200ms out, and tapping before that expires lets a leftover
    startup timer coincidentally "rescue" the anchor — passing even on the
    unfixed code and masking the exact regression this test exists to
    catch. Waiting comfortably past that window (2.5s) before the first
    interaction reflects a real user tapping well after the page has
    settled, not an accidental rescue from page-load timing.

    This clicks the real "Fragment reveal toggle" button inside a real,
    module-level @st.fragment (scripts/ui_validation_harness.py's
    _fragment_reveal_fixture, mounted inside the viewport-preserve surface
    — decorated at import time, exactly like the two production call sites)
    and asserts its on-screen position holds across the fragment rerun that
    reveals an st.info block above it — not a re-implementation of the
    restore logic, the real shipped JS the browser runs.
    """
    from playwright.sync_api import sync_playwright
    from scripts.validate_viewport_preservation import wait_app

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
        )
        try:
            page.goto(f"{harness_url}/?surface=viewport-preserve")
            wait_app(page)
            locator = page.get_by_role("button", name="Fragment reveal toggle")
            locator.scroll_into_view_if_needed()
            # Let any residual startup-mount ladder fully expire (see
            # docstring) before recording the baseline position.
            page.wait_for_timeout(2500)
            before = locator.bounding_box()
            assert before is not None
            locator.click()
            # Give the record()-anchored restore ladder its full window
            # (rAF double + setTimeouts up to 1200ms) plus margin. This
            # interaction never bumps __dgViewportRestoreKickSeq (that
            # counter only increments on a FULL rerun's remount — the
            # exact gap under test), so we cannot wait on that signal here.
            page.wait_for_timeout(2000)
            after = locator.bounding_box()
            assert after is not None
            assert abs(after["y"] - before["y"]) < 4, (
                "fragment-scoped reveal shifted the tapped control on "
                f"screen (jump bug): before={before!r} after={after!r}"
            )
        finally:
            browser.close()


def test_real_dom_page_shell_container_is_not_mistaken_for_a_widget_key(harness_url):
    """Real-browser regression check for the fourth recurrence of coridian_'s
    "tapping randomly jumps where you are on the page, scrolling wise".

    The first three recurrences each had a genuinely different cause (an
    isIntentionalNav() key-allowlist gap, a shared tap-delegation zone
    needing data-route instead of key-matching, and @st.fragment reruns
    never re-scheduling the restore ladder from mount — see the tests
    above). This one is different again: modules/page_shell.py's
    page_body() (Phase 2 web-shell rollout, #998-#1000) wraps an ENTIRE
    adopting page's top-level sections in one keyed container so it can own
    a single flex gap. A control with no key of its own inside that
    container — the real shape of my_team_ui.py's "Key backups" st.expander
    and waivers_ui.py's "Detailed Table View" st.expander, reproduced here
    by scripts/ui_validation_harness.py's page_body() fixture block — used
    to have NO ancestor "st-key-" class at all, so keyFrom() correctly
    returned "" for it and restore() fell back to the (correct,
    pre-existing) "snap to near top/bottom" heuristic. Once page_body()
    wraps the page, that same upward walk now finds page_body's own
    page-wide key instead — and restore()'s
    ``doc.querySelector("." + last.key)`` fallback then resolves to the
    ENTIRE page's content block (not the tapped control), so the delta
    between that block's top and the offset recorded for the actual control
    is huge and effectively random. This pointerdowns the real unkeyed
    st.expander summary inside the real page_body() container and reads
    back the real shipped keyFrom() verdict off
    window.__dgInPlaceAnchor.key — not a re-implementation of that logic.
    """
    from playwright.sync_api import sync_playwright
    from scripts.validate_viewport_preservation import wait_app

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            page.goto(f"{harness_url}/?surface=viewport-preserve")
            wait_app(page)
            # The page_body() container itself really does carry a
            # "st-key-" class — this is the regression's precondition, not
            # a sanity check on something else.
            assert (
                page.locator(".st-key-viewport_preserve_page_shell_fixture").count()
                == 1
            )
            summary = page.locator(
                "summary:has-text('Key backups fixture')"
            ).first
            summary.scroll_into_view_if_needed()
            page.wait_for_function("window.__dgViewportPreserveBound === true", timeout=90_000)
            summary.dispatch_event("pointerdown")
            anchor = page.evaluate("window.__dgInPlaceAnchor")
            assert anchor is not None
            assert anchor.get("key") == "", (
                "keyFrom() resolved the page_body() shell's own page-wide "
                f"key instead of recognizing it as a non-identity shell: {anchor!r}"
            )
        finally:
            browser.close()
