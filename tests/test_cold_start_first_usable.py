"""Cold-start critical path and hang-protection contracts (PR #138)."""

from __future__ import annotations

from pathlib import Path

from modules import auth_supabase
from modules import startup_critical_path


ROOT = Path(__file__).resolve().parents[1]


def test_auth_pending_hang_protection_times_out():
    state: dict = {}
    assert startup_critical_path.should_stop_for_auth_pending(state) is True
    assert startup_critical_path.should_stop_for_auth_pending(state) is False
    assert state.get(startup_critical_path.AUTH_RESTORE_TIMED_OUT_KEY) is True
    assert "Session restore" in state.get(startup_critical_path.STARTUP_DEGRADED_NOTICE_KEY, "")


def test_cold_start_report_exists():
    doc = (ROOT / "docs" / "cold-start-first-usable-screen.md").read_text(encoding="utf-8")
    for section in (
        "Root causes",
        "First usable screen",
        "Critical vs deferred",
        "Launch verdict",
        "190f9533838a793f504de661a365e32de7ecccd2",
    ):
        assert section in doc
    assert "| Target | Status |" in doc
