from __future__ import annotations

from pathlib import Path

from modules import startup_coordinator


class _Placeholder:
    def __init__(self) -> None:
        self.markdown_calls: list[tuple[str, bool]] = []
        self.empty_calls = 0

    def markdown(self, value: str, *, unsafe_allow_html: bool = False) -> None:
        self.markdown_calls.append((value, unsafe_allow_html))

    def empty(self) -> None:
        self.empty_calls += 1


def test_startup_coordinator_persists_phase_across_required_reruns(monkeypatch):
    state: dict = {}
    placeholders: list[_Placeholder] = []

    def _empty() -> _Placeholder:
        placeholder = _Placeholder()
        placeholders.append(placeholder)
        return placeholder

    monkeypatch.setattr(startup_coordinator.st, "empty", _empty)
    counts: list[str] = []
    monkeypatch.setattr(startup_coordinator.runtime_trace, "count", counts.append)

    first = startup_coordinator.StartupCoordinator.begin(state)
    first.advance(startup_coordinator.StartupPhase.AUTH_RESTORING)
    first.advance(startup_coordinator.StartupPhase.PUBLIC_DATA_LOADING)

    second = startup_coordinator.StartupCoordinator.begin(state)

    assert first.active is True
    assert second.phase is startup_coordinator.StartupPhase.AUTH_RESTORING
    assert len(placeholders) == 2
    assert counts == ["startup_shell_mounts", "startup_shell_mounts"]


def test_startup_coordinator_completes_once_and_stays_inactive(monkeypatch):
    state: dict = {}
    placeholder = _Placeholder()
    monkeypatch.setattr(startup_coordinator.st, "empty", lambda: placeholder)
    counts: list[str] = []
    monkeypatch.setattr(startup_coordinator.runtime_trace, "count", counts.append)

    coordinator = startup_coordinator.StartupCoordinator.begin(state)
    coordinator.advance(startup_coordinator.StartupPhase.PAGE_READY)
    calls_before_complete = len(placeholder.markdown_calls)
    coordinator.complete()
    later_rerun = startup_coordinator.StartupCoordinator.begin(state)

    assert placeholder.empty_calls == 1
    assert len(placeholder.markdown_calls) == calls_before_complete
    assert startup_coordinator.COORDINATOR_KEY not in state
    assert state[startup_coordinator.STARTUP_COMPLETE_KEY] is True
    assert later_rerun.active is False
    assert counts == ["startup_shell_mounts", "application_mounts"]


def test_reset_restarts_shell_for_login_logout_or_explicit_restart(monkeypatch):
    state = {
        startup_coordinator.STARTUP_COMPLETE_KEY: True,
        startup_coordinator.COORDINATOR_KEY: {
            "phase": int(startup_coordinator.StartupPhase.PAGE_READY)
        },
    }
    placeholder = _Placeholder()
    monkeypatch.setattr(startup_coordinator.st, "empty", lambda: placeholder)
    monkeypatch.setattr(startup_coordinator.runtime_trace, "count", lambda *_: None)

    startup_coordinator.reset_startup_coordinator(state)
    restarted = startup_coordinator.StartupCoordinator.begin(state)

    assert restarted.active is True
    assert restarted.phase is startup_coordinator.StartupPhase.PUBLIC_DATA_LOADING
    assert placeholder.markdown_calls


def test_malformed_session_phase_falls_back_safely(monkeypatch):
    state = {startup_coordinator.COORDINATOR_KEY: "malformed"}
    placeholder = _Placeholder()
    monkeypatch.setattr(startup_coordinator.st, "empty", lambda: placeholder)
    monkeypatch.setattr(startup_coordinator.runtime_trace, "count", lambda *_: None)

    coordinator = startup_coordinator.StartupCoordinator.begin(state)

    assert coordinator.phase is startup_coordinator.StartupPhase.PUBLIC_DATA_LOADING


def test_startup_shell_is_full_viewport_centered_responsive_and_accessible():
    markup = startup_coordinator.startup_shell_html(
        startup_coordinator.StartupPhase.AUTH_RESTORING
    )

    assert "position: fixed" in markup
    assert "inset: 0" in markup
    assert "min-height: 100dvh" in markup
    assert "box-sizing: border-box" in markup
    assert "align-items: center" in markup
    assert "justify-content: center" in markup
    assert "@media (max-width: 600px)" in markup
    assert "env(safe-area-inset-top" in markup
    assert "role='status'" in markup
    assert "aria-live='polite'" in markup
    assert "role='progressbar'" in markup
    assert "FantasyGM Lab" in markup
    assert "Founder Beta" in markup
    assert "dg-startup-milestone" in markup
    assert "--dg-startup-progress:" in markup
    # Progress width is phase-driven; only a decorative sheen may animate.
    assert "aria-valuenow=" in markup
    assert "dg-startup-sheen" in markup
    assert "indeterminate" not in markup.casefold()


def test_app_wires_coordinator_without_native_startup_spinner():
    source = Path("app.py").read_text(encoding="utf-8")

    begin = source.index("StartupCoordinator.begin(st.session_state)")
    styles = source.index("inject_global_styles(APP_CSS)", begin)
    page_ready = source.index(
        "startup.advance(startup_coordinator.StartupPhase.PAGE_READY)"
    )
    complete = source.index('runtime_trace.mark("first_usable_paint")', page_ready)
    complete_call = source.index("startup.complete()", page_ready)
    page_dispatch = source.index('if current_page == "dashboard":', page_ready)

    assert begin < styles < page_ready < complete < complete_call < page_dispatch
    assert 'st.spinner("Loading player data...")' not in source
    assert source.count('runtime_trace.mark("first_usable_paint")') == 1
    assert "startup_critical_path.should_stop_for_auth_pending" in source
    assert "live_draft_discovery" in source


def test_required_auth_and_saved_league_reruns_are_preserved():
    source = Path("app.py").read_text(encoding="utf-8")

    auth_restore = source.index('if auth_restore.get("restored"):')
    auth_rerun = source.index("st.rerun()", auth_restore)
    league_restore = source.index("if _maybe_auto_resume_supabase_league():")
    league_rerun = source.index("st.rerun()", league_restore)

    assert auth_restore < auth_rerun < league_restore < league_rerun
