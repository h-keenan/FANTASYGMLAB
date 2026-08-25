"""Unsigned Load my leagues must persist results after the first submit."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import app
from modules import marketing_landing
from modules.sleeper_leagues import LeagueLookupResult

ROOT = Path(__file__).resolve().parents[1]


class _Session:
    def __init__(self, initial: dict | None = None):
        object.__setattr__(self, "_data", dict(initial or {}))

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def pop(self, key, default=None):
        return self._data.pop(key, default)

    def __contains__(self, key):
        return key in self._data

    def keys(self):
        return self._data.keys()

    def __iter__(self):
        return iter(self._data)


class _Form:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _Spinner:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _run_launch(session: _Session, *, submit: bool, markdown: list[str], lookup) -> None:
    col = MagicMock()
    col.__enter__ = MagicMock(return_value=col)
    col.__exit__ = MagicMock(return_value=False)
    with ExitStack() as stack:
        stack.enter_context(patch.object(app.st, "session_state", session))
        stack.enter_context(
            patch.object(app.st, "markdown", side_effect=lambda body, **_k: markdown.append(str(body)))
        )
        stack.enter_context(patch.object(app.st, "form", return_value=_Form()))
        stack.enter_context(patch.object(app.st, "text_input", return_value="sleeper_user"))
        stack.enter_context(patch.object(app.st, "form_submit_button", return_value=submit))
        stack.enter_context(patch.object(app.st, "button", return_value=False))
        stack.enter_context(patch.object(app.st, "spinner", return_value=_Spinner()))
        stack.enter_context(patch.object(app.st, "caption"))
        stack.enter_context(patch.object(app.st, "columns", return_value=[col, col]))
        stack.enter_context(patch.object(app.st, "rerun"))
        stack.enter_context(
            patch("app.platform_import_ui.render_platform_import_panel", return_value={"handled": False})
        )
        stack.enter_context(patch("app.lookup_user_leagues", side_effect=lookup))
        stack.enter_context(patch("app.get_current_account", return_value={}))
        stack.enter_context(patch("app.workspace_notices.render_lookup_notice"))
        stack.enter_context(patch("app.ui_primitives.render_section_header"))
        stack.enter_context(patch("app.team_logo_html", return_value=""))
        app.render_home_launch_screen(
            username=str(session.get("username") or ""),
            selected_league_id="",
            df_players=None,
            compact=True,
            skip_account_entry=True,
        )


def test_first_submit_writes_leagues_and_shows_results_without_second_click():
    session = _Session(
        {
            marketing_landing.SIGNED_OUT_ENTRY_KEY: "import",
            "home_launch_username_input": "sleeper_user",
        }
    )
    calls: list[str] = []

    def lookup(username, season=None):
        calls.append("lookup")
        return LeagueLookupResult(
            [
                {"league_id": "lg-1", "name": "Dynasty Club", "season": "2026"},
                {"league_id": "lg-2", "name": "Keepers", "season": "2026"},
            ],
            "ok",
        )

    markdown: list[str] = []
    _run_launch(session, submit=True, markdown=markdown, lookup=lookup)

    assert calls == ["lookup"]
    assert len(session.get("leagues_for_user") or []) == 2
    joined = "\n".join(markdown)
    assert "Dynasty Club" in joined
    assert "Keepers" in joined
    trace = session.get(app.SIGNED_OUT_IMPORT_TRACE_KEY) or []
    assert trace[-1]["submit_count"] == 1
    assert trace[-1]["loader_called"] is True
    assert trace[-1]["loader_result_count"] == 2
    assert trace[-1]["leagues_written_count"] == 2
    assert trace[-1]["rerun_requested"] is False

    markdown.clear()
    _run_launch(session, submit=False, markdown=markdown, lookup=lookup)
    assert calls == ["lookup"]
    joined = "\n".join(markdown)
    assert "Dynasty Club" in joined
    follow = (session.get(app.SIGNED_OUT_IMPORT_TRACE_KEY) or [])[-1]
    assert follow["submit_count"] == 1
    assert follow["loader_called"] is False
    assert follow["render_branch"] == "results"
    assert follow["leagues_at_next_run"] == 2


def test_empty_sidebar_submit_does_not_wipe_launch_results():
    session = _Session(
        {
            "leagues_for_user": [{"league_id": "lg-1", "name": "Kept"}],
            "leagues_for_user_username": "sleeper_user",
            "username": "sleeper_user",
        }
    )
    with patch.object(app.st, "session_state", session):
        kept = app.load_leagues_for_username("", source="sidebar")
    assert kept == [{"league_id": "lg-1", "name": "Kept"}]
    assert session.get("leagues_for_user") == [{"league_id": "lg-1", "name": "Kept"}]


def test_sidebar_load_button_uses_distinct_key():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'key="sidebar_load_leagues_cta"' in source
    launch = source.split("def render_home_launch_screen", 1)[1].split(
        "\ndef render_onboarding_handoff", 1
    )[0]
    assert 'source="launch"' in launch
    assert "if auto_open:" in launch
    assert "launch_league_picker_cards" in launch
