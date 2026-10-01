"""Welcome/signup audit Fix 4 (web): a guest importing a league must pass
the same age gate an account-creator does.

Before this fix, modules.age_gate.render_age_confirmation was only ever
called from the two account-CREATION forms (modules.account_ui's
launch_account_signup, modules.guest_conversion's guest_dialog_signup) — a
guest who never creates an account could import a Sleeper league without
ever passing an age check. This covers both the standalone age_gate contract
and the new wiring in app.py's guest import entry point.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from modules import age_gate


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_calculate_age_handles_birthday_not_yet_reached_this_year():
    today = date(2026, 1, 1)
    assert age_gate.calculate_age(date(2013, 6, 1), today) == 12
    assert age_gate.calculate_age(date(2013, 1, 1), today) == 13


def test_render_age_confirmation_blocks_under_minimum_age(monkeypatch):
    state: dict = {}
    inputs = iter(["01", "01", "2020"])  # ~6 years old relative to "today"

    class _FakeColumn:
        def text_input(self, *a, **k):
            return next(inputs)

    monkeypatch.setattr(age_gate.st, "session_state", state)
    monkeypatch.setattr(age_gate.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(age_gate.st, "columns", lambda n: [_FakeColumn() for _ in range(n)])
    monkeypatch.setattr(age_gate.st, "button", lambda *a, **k: True)
    errors: list[str] = []
    monkeypatch.setattr(age_gate.st, "error", lambda msg: errors.append(msg))

    result = age_gate.render_age_confirmation("test_guard")

    assert result is False
    assert state.get("_test_guard_age_gate_blocked") is True
    assert errors and "13" in errors[0]


def test_render_age_confirmation_passes_and_caches_for_session(monkeypatch):
    state: dict = {}
    today = date.today()
    birth_year = today.year - 20
    inputs = iter([f"{today.month:02d}", f"{today.day:02d}", str(birth_year)])

    class _FakeColumn:
        def text_input(self, *a, **k):
            return next(inputs)

    monkeypatch.setattr(age_gate.st, "session_state", state)
    monkeypatch.setattr(age_gate.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(age_gate.st, "columns", lambda n: [_FakeColumn() for _ in range(n)])
    monkeypatch.setattr(age_gate.st, "button", lambda *a, **k: True)

    result = age_gate.render_age_confirmation("test_guard2")
    assert result is True
    assert state.get("_test_guard2_age_gate_passed") is True

    # Second call this session short-circuits straight to True without
    # re-touching any of the input widgets.
    def _boom(n):
        raise AssertionError("should not re-prompt")

    monkeypatch.setattr(age_gate.st, "columns", _boom)
    assert age_gate.render_age_confirmation("test_guard2") is True


def test_guest_import_entry_point_is_gated_behind_age_gate_in_app():
    launch_fn = APP.split("def _render_launch_import_and_leagues() -> None:", 1)[1].split(
        "\n    def ", 1
    )[0]
    assert "guest_conversion.is_guest(st.session_state)" in launch_fn
    assert "age_gate.render_age_confirmation(\"launch_guest_import\")" in launch_fn
    gate_index = launch_fn.index("age_gate.render_age_confirmation(")
    import_index = launch_fn.index("platform_import_ui.render_platform_import_panel(")
    assert gate_index < import_index


def test_only_two_pre_existing_account_creation_call_sites_plus_the_new_guest_gate():
    account_ui = (ROOT / "modules" / "account_ui.py").read_text(encoding="utf-8")
    guest_conversion = (ROOT / "modules" / "guest_conversion.py").read_text(encoding="utf-8")
    assert account_ui.count("age_gate.render_age_confirmation(") == 1
    assert guest_conversion.count("age_gate.render_age_confirmation(") == 1
    assert APP.count("age_gate.render_age_confirmation(") == 1
