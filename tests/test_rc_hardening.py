from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import Mock

from modules import accounts, profile, startup_coordinator


def test_startup_origin_persists_across_mid_startup_reruns(monkeypatch):
    state: dict = {}
    monkeypatch.setattr(startup_coordinator.st, "empty", lambda: Mock())
    monkeypatch.setattr(startup_coordinator.runtime_trace, "count", lambda *_: None)
    monkeypatch.setattr(startup_coordinator.runtime_trace, "mark", lambda *_: None)

    first = startup_coordinator.StartupCoordinator.begin(state)
    origin = state[startup_coordinator.STARTUP_TIMING_STARTED_KEY]
    first.advance(startup_coordinator.StartupPhase.AUTH_RESTORING)

    second = startup_coordinator.StartupCoordinator.begin(state)

    assert second.active is True
    assert state[startup_coordinator.STARTUP_TIMING_STARTED_KEY] == origin


def test_startup_complete_clears_timing_origin(monkeypatch):
    state: dict = {}
    placeholder = Mock()
    monkeypatch.setattr(startup_coordinator.st, "empty", lambda: placeholder)
    monkeypatch.setattr(startup_coordinator.runtime_trace, "count", lambda *_: None)
    monkeypatch.setattr(startup_coordinator.runtime_trace, "mark", lambda *_: None)

    coordinator = startup_coordinator.StartupCoordinator.begin(state)
    assert startup_coordinator.STARTUP_TIMING_STARTED_KEY in state
    coordinator.complete()

    assert startup_coordinator.STARTUP_TIMING_STARTED_KEY not in state
    assert state[startup_coordinator.STARTUP_COMPLETE_KEY] is True


def test_dashboard_rendered_milestone_uses_startup_origin_not_stale_clock(monkeypatch):
    state: dict = {}
    monkeypatch.setattr(startup_coordinator.st, "empty", lambda: Mock())
    monkeypatch.setattr(startup_coordinator.runtime_trace, "count", lambda *_: None)
    monkeypatch.setattr(startup_coordinator.runtime_trace, "mark", lambda *_: None)

    startup_coordinator.StartupCoordinator.begin(state)
    origin = state[startup_coordinator.STARTUP_TIMING_STARTED_KEY]
    # Simulate a long-lived stale clock that previously leaked into post-complete logs.
    state[startup_coordinator.STARTUP_TIMING_STARTED_KEY] = origin - 1550.0
    # Restore the true origin for an active startup session.
    state[startup_coordinator.STARTUP_TIMING_STARTED_KEY] = origin
    elapsed = startup_coordinator.log_startup_milestone(
        state,
        "dashboard_rendered",
        started_at=origin,
    )
    assert elapsed < 5_000


def test_loading_copy_matches_real_workspace_milestones():
    markup = startup_coordinator.startup_shell_html(
        startup_coordinator.StartupPhase.PAGE_READY
    )
    assert "Opening your workspace..." in markup
    assert "Finishing setup..." not in markup
    route = startup_coordinator.startup_shell_html(
        startup_coordinator.StartupPhase.ROUTE_RESTORING
    )
    assert "Preparing your workspace..." in route


def test_upsert_account_skips_unchanged_disk_write(tmp_path, monkeypatch):
    path = tmp_path / "accounts.json"
    monkeypatch.setattr(accounts, "ACCOUNTS_PATH", str(path))
    monkeypatch.setattr(accounts, "os", accounts.os)
    accounts.upsert_account("1", "league-a", "manager")
    mtime = path.stat().st_mtime_ns
    time.sleep(0.01)
    accounts.upsert_account("1", "league-a", "manager")
    assert path.stat().st_mtime_ns == mtime


def test_save_profile_key_skips_unchanged_disk_write(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    monkeypatch.setattr(profile, "PROFILE_PATH", str(path))
    payload = {
        "roles": {"1": "Core"},
        "trade_block": [],
        "untouchables": ["Ace"],
        "strategy_override": "Auto",
        "valuation_archetype_id": profile.DEFAULT_VALUATION_ARCHETYPE_ID,
    }
    profile.save_profile_key("manager", "league-a", payload)
    mtime = path.stat().st_mtime_ns
    time.sleep(0.01)
    profile.save_profile_key("manager", "league-a", payload)
    assert path.stat().st_mtime_ns == mtime


def test_app_gates_dashboard_rendered_to_active_startup():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "dashboard_rendered" in source
    assert "STARTUP_COMPLETE_KEY" in source.split("dashboard_rendered", 1)[0][-400:]


def test_experimental_destinations_use_bracket_label():
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'suffix = f" {brand_identity.EXPERIMENTAL_LABEL}"' in source
    assert '(brand_identity.EXPERIMENTAL_LABEL, "warning")' in source
    assert '("[EXPERIMENTAL]", "warning")' in source
