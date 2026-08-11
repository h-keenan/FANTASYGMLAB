"""Soft-deadline notice must not linger on the ready Dashboard (#246)."""

from __future__ import annotations

from pathlib import Path

from modules import startup_critical_path


ROOT = Path(__file__).resolve().parents[1]


def test_app_clears_degraded_notice_on_loading_dismiss():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "STARTUP_DEGRADED_NOTICE_KEY" in app
    # Ready path must clear the notice; must not caption it after chrome is ready.
    assert "consume_degraded_notice" not in app or "st.caption(degraded_notice)" not in app
    assert app.count("STARTUP_DEGRADED_NOTICE_KEY") >= 2


def test_soft_deadline_sets_notice_once():
    state: dict = {}
    started = 0.0
    # Force elapsed past deadline by seeding timing key in the past via monkeypatch-like
    # direct call with a fake started_at far in the past.
    import time

    old = time.perf_counter()
    assert startup_critical_path.mark_soft_deadline_if_exceeded(
        state, started_at=old - 120.0
    )
    notice = startup_critical_path.consume_degraded_notice(state)
    assert "taking longer than usual" in notice.casefold()
    assert startup_critical_path.consume_degraded_notice(state) == ""
