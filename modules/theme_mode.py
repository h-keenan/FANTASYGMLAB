"""Day/Night/System theme resolution for the web app.

Mirrors mobile's already-shipped ThemeModeContext
(mobile/src/context/ThemeModeContext.tsx): an explicit Day/Night choice, or
"System" which resolves against the browser's OS-level color-scheme
preference. Persisted through the *same* user_settings JSONB "settings" blob
and the same ``theme_mode`` key mobile's own /v1/preferences endpoint already
reads/writes (see services/mobile_api_service.py's THEME_MODE_VALUES /
_device_preferences_from_settings), so an account's explicit choice is stored
in one place an eventual cross-platform sync could read from later — wiring
that sync is out of scope here.

Streamlit is server-rendered: on a brand-new "System" session there is no way
to know the browser's OS preference before any client JS has run. This module
accepts the same one-rerun-to-settle trade-off every other client-signal
bridge in this app already does (see modules/auth_storage_handshake.py's own
docstring) — the probe component mounts, reports the real
prefers-color-scheme reading back to Python, and the *next* rerun renders
with the correct palette. Until then a fresh "System" session renders dark
(matches mobile's own documented DEFAULT_MODE).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, MutableMapping

import streamlit as st

from modules import account_store
from modules import auth_supabase
from modules import user_preferences

THEME_MODE_VALUES = {"light", "dark", "auto"}
DEFAULT_MODE = "dark"
SETTINGS_KEY = "theme_mode"

# session_state keys
LOCAL_OVERRIDE_KEY = "_theme_mode_local_override"
SYSTEM_PREFERS_DARK_KEY = "_theme_system_prefers_dark"
# The Day/Night/System radio's own Streamlit widget key (account_ui.py). A
# widget's session_state entry is populated by the framework *before* the
# script body runs on the rerun that widget interaction triggers — reading it
# here, ahead of CSS injection earlier in app.py's script, is what lets the
# new choice apply on the very same rerun the user made it, with no explicit
# st.rerun() call. This app enforces a hard cap on explicit `st.rerun()` call
# sites (see scripts/measure_interaction_rerun_architecture.py /
# tests/test_ui_constitution_v1.py and its siblings) — reading the widget's
# already-current value instead of forcing a rerun keeps this feature inside
# that budget.
RADIO_WIDGET_KEY = "account_theme_mode_radio"


def stored_mode(user_settings: Mapping[str, object] | None) -> str:
    """The account's persisted choice, or the documented default."""

    raw = user_preferences.preference_values(user_settings).get(SETTINGS_KEY)
    return raw if raw in THEME_MODE_VALUES else DEFAULT_MODE


def current_mode(session_state: Mapping[str, Any]) -> str:
    """The mode in effect for this render.

    Preference order: this rerun's live radio-widget value (freshest signal,
    see RADIO_WIDGET_KEY), then an unsaved local pick recorded by set_mode
    outside the widget flow, then the persisted account setting.
    """

    from_widget = session_state.get(RADIO_WIDGET_KEY)
    if from_widget in THEME_MODE_VALUES:
        return from_widget
    override = session_state.get(LOCAL_OVERRIDE_KEY)
    if override in THEME_MODE_VALUES:
        return override
    return stored_mode(session_state.get("account_user_settings"))


def resolve_is_dark(session_state: Mapping[str, Any]) -> bool:
    """Resolve "auto" against the last client probe reading; else the explicit choice."""

    mode = current_mode(session_state)
    if mode == "light":
        return False
    if mode == "dark":
        return True
    probed = session_state.get(SYSTEM_PREFERS_DARK_KEY)
    return True if probed is None else bool(probed)


def with_theme_mode(user_settings: Mapping[str, object] | None, *, mode: str) -> dict:
    """Merge the theme preference without replacing unrelated settings."""

    if mode not in THEME_MODE_VALUES:
        mode = DEFAULT_MODE
    merged = user_preferences.preference_values(user_settings)
    merged[SETTINGS_KEY] = mode
    return {"settings": merged}


def persist_authenticated_theme_mode(
    *,
    config: dict,
    session_state: MutableMapping[str, Any],
    mode: str,
) -> str:
    """Persist the theme choice for the signed-in account. Empty string on success."""

    user_id = auth_supabase.current_user_id(session_state)
    access_token = auth_supabase.current_access_token(session_state)
    if not user_id or not access_token:
        return "Authentication is required."
    updated = with_theme_mode(session_state.get("account_user_settings"), mode=mode)
    payload = account_store.build_user_settings_payload(
        user_id=user_id,
        settings=updated["settings"],
    )
    saved, error = account_store.upsert_user_settings(config, access_token, payload)
    if saved:
        session_state["account_user_settings"] = payload
        return ""
    return error


def set_mode(*, config: dict, session_state: MutableMapping[str, Any], mode: str) -> str:
    """Apply a new Day/Night/System choice instantly, syncing to the account if signed in.

    Same instant-local/best-effort-remote shape as mobile's setMode: the local
    override takes effect on this same rerun regardless of network outcome.
    """

    if mode not in THEME_MODE_VALUES:
        mode = DEFAULT_MODE
    session_state[LOCAL_OVERRIDE_KEY] = mode
    if auth_supabase.current_user_id(session_state) and auth_supabase.current_access_token(session_state):
        return persist_authenticated_theme_mode(config=config, session_state=session_state, mode=mode)
    return ""


_SYSTEM_PROBE_JS = """
    export default function(component) {
      const { setTriggerValue } = component
      const hostWindow = window.parent || window
      const media = hostWindow.matchMedia
        ? hostWindow.matchMedia('(prefers-color-scheme: dark)')
        : null
      if (!media) return
      const emit = () => {
        setTriggerValue("system_theme", { is_dark: !!media.matches, ts: Date.now() })
      }
      emit()
      if (typeof media.addEventListener === "function") {
        media.addEventListener("change", emit)
      } else if (typeof media.addListener === "function") {
        media.addListener(emit)
      }
    }
"""

THEME_SYSTEM_PROBE_COMPONENT = st.components.v2.component(
    "theme_system_probe",
    html="<span aria-hidden='true' style='display:none'></span>",
    js=_SYSTEM_PROBE_JS,
    isolate_styles=False,
)


def sync_system_preference(session_state: MutableMapping[str, Any], *, key: str = "theme_system_probe") -> None:
    """Mount the OS color-scheme probe and cache its latest reading.

    Cheap (zero visible content), safe to call on every rerun regardless of
    the active mode — "System" is the only mode that reads the cached value,
    but keeping the probe mounted unconditionally means switching *into*
    System mode never has to wait for a fresh mount.
    """

    try:
        result = THEME_SYSTEM_PROBE_COMPONENT(
            key=key,
            data={},
            width=1,
            height=1,
            on_system_theme_change=lambda *_a, **_k: None,
        )
    except ValueError as exc:
        # Local AppTest / unregistered component — keep the documented default.
        if "is not registered" not in str(exc):
            raise
        return
    payload: Any = getattr(result, "system_theme", None)
    if isinstance(payload, dict) and "is_dark" in payload:
        session_state[SYSTEM_PREFERS_DARK_KEY] = bool(payload["is_dark"])
