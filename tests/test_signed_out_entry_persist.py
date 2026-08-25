"""Signed-out entry must survive Streamlit reruns on non-dict session_state."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from modules import marketing_landing


class _StreamlitSession:
    """Production st.session_state is not a dict."""

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


def _click(label: str):
    def _button(text, **_kwargs):
        return str(text) == label

    return _button


def _render(session: _StreamlitSession, *, label: str = ""):
    col = MagicMock()
    col.__enter__ = MagicMock(return_value=col)
    col.__exit__ = MagicMock(return_value=False)
    with patch.object(marketing_landing.st, "session_state", session), patch.object(
        marketing_landing.st, "markdown"
    ), patch.object(
        marketing_landing.st,
        "button",
        side_effect=_click(label) if label else MagicMock(return_value=False),
    ), patch.object(marketing_landing.st, "rerun"), patch.object(
        marketing_landing, "_track"
    ), patch.object(marketing_landing.st, "columns", return_value=[col, col]), patch(
        "modules.stripe_billing.load_stripe_config",
        return_value=MagicMock(configured=False),
    ):
        return marketing_landing.render_marketing_landing()


def _script_rerun_read(session: _StreamlitSession) -> str:
    """Match app.py: drop run-scoped flags, then resolve signed-out entry."""

    session.pop("_early_launch_account_rendered", None)
    session.pop("_welcome_hero_signin_rendered", None)
    session.pop("_signed_out_workflow_mounted", None)
    marketing_landing.mark_signed_out_run_start(session)
    flow = marketing_landing.welcome_flow_state(session)
    _render(session)
    return flow


def test_session_helper_is_not_a_dict():
    session = _StreamlitSession()
    assert not isinstance(session, dict)
    assert isinstance({}, dict)


def test_welcome_import_survives_two_reruns_on_non_dict_session():
    session = _StreamlitSession()
    first = _script_rerun_read(session)
    assert first == "welcome"
    assert session.get(marketing_landing.SIGNED_OUT_ENTRY_KEY) == "welcome"

    actions = _render(session, label=marketing_landing.APP_PRIMARY_CTA_LABEL)
    assert actions["primary"] is True
    assert session.get(marketing_landing.SIGNED_OUT_ENTRY_KEY) == "import"

    rerun_1 = _script_rerun_read(session)
    rerun_2 = _script_rerun_read(session)
    assert rerun_1 == "import"
    assert rerun_2 == "import"
    assert session.get(marketing_landing.SIGNED_OUT_ENTRY_KEY) == "import"
    assert marketing_landing.welcome_flow_state(session) == "import"


def test_welcome_sign_in_survives_two_reruns_on_non_dict_session():
    session = _StreamlitSession()
    first = _script_rerun_read(session)
    assert first == "welcome"

    actions = _render(session, label=marketing_landing.SECONDARY_CTA_LABEL)
    assert actions["secondary"] is True
    assert session.get(marketing_landing.SIGNED_OUT_ENTRY_KEY) == "sign_in"

    rerun_1 = _script_rerun_read(session)
    rerun_2 = _script_rerun_read(session)
    assert rerun_1 == "sign_in"
    assert rerun_2 == "sign_in"
    assert session.get(marketing_landing.SIGNED_OUT_ENTRY_KEY) == "sign_in"
    assert marketing_landing.welcome_flow_state(session) == "sign_in"


def test_valid_entry_is_not_rewritten_to_welcome_on_empty_league():
    session = _StreamlitSession(
        {
            marketing_landing.SIGNED_OUT_ENTRY_KEY: "import",
            "landing_focus": "get_started",
        }
    )
    assert marketing_landing.welcome_flow_state(session) == "import"
    assert marketing_landing.welcome_flow_state(session) == "import"
    assert session.get(marketing_landing.SIGNED_OUT_ENTRY_KEY) == "import"


def test_migrate_welcome_only_when_key_absent():
    empty = _StreamlitSession()
    assert marketing_landing.welcome_flow_state(empty) == "welcome"
    assert empty.get(marketing_landing.SIGNED_OUT_ENTRY_KEY) == "welcome"

    leftover = _StreamlitSession({"landing_focus": "sign_in"})
    assert marketing_landing.welcome_flow_state(leftover) == "sign_in"
    assert leftover.get(marketing_landing.SIGNED_OUT_ENTRY_KEY) == "sign_in"


def test_set_signed_out_entry_writes_non_dict_session():
    session = _StreamlitSession()
    assert marketing_landing.set_signed_out_entry(session, "import") == "import"
    assert session.get(marketing_landing.SIGNED_OUT_ENTRY_KEY) == "import"
    marketing_landing.reset_welcome_flow(session)
    assert marketing_landing.welcome_flow_state(session) == "welcome"
