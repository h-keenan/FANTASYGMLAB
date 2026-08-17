"""Viewport / focus preservation contract for in-place reruns."""

from __future__ import annotations

import ast
import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

from modules.app_styles import APP_CSS
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS
from modules.viewport_preservation import VIEWPORT_PRESERVE_JS
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
    assert "scrollIntoView" not in APP


def test_app_and_harness_mount_shared_helper():
    assert "viewport_preservation.render_viewport_preservation()" in APP
    assert "viewport_preservation.render_viewport_preservation()" in HARNESS
    assert 'st.components.v2.component(\n    "viewport_preserve"' not in APP
    assert APP.count("_render_navigation_scroll_reset(current_page, league_id=") == 1


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
    assert len(APP_CSS) < 390_000


def test_explicit_rerun_count_unchanged():
    assert count_explicit_reruns() <= 58


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
            "python3",
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
        try:
            report = run_viewport_matrix(page, base_url=harness_url)
        finally:
            browser.close()
    assert "resend_confirmation" in report["cases"]
    before = report["cases"]["resend_confirmation"]["before"]
    after = report["cases"]["resend_confirmation"]["after"]
    assert not after["atMainBottom"]
    assert after["mainScrollTop"] > 20 or before["atMainTop"] is False
    assert "dashboard_refresh" in report["cases"]
    assert "strategy_toggle" in report["cases"]
    assert "pqv_more_details" in report["cases"]
