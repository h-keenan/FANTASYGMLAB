"""Canonical customer notices for core-journey gates and failures.

Uses ``ui_primitives.empty_state_panel`` so Streamlit-native alerts do not leak
into branded workspace pages. Callers own buttons and routing.
"""

from __future__ import annotations

from modules import product_copy
from modules import ui_primitives
from modules.sleeper_leagues import league_lookup_customer_message


def render_lookup_notice(status: str) -> bool:
    message = league_lookup_customer_message(status) if status != "ok" else ""
    if not message:
        return False
    kind = "no-data" if status in {"empty_username", "no_leagues", "user_not_found"} else "error"
    ui_primitives.render_empty_state_panel(
        product_copy.LOOKUP_ERROR_TITLE,
        message,
        kind=kind,
        recovery_guidance=product_copy.LOOKUP_RECOVERY,
    )
    return True


def render_roster_mismatch_notice() -> None:
    ui_primitives.render_empty_state_panel(
        product_copy.ROSTER_MISMATCH_TITLE,
        product_copy.ROSTER_MISMATCH_BODY,
        kind="error",
        recovery_guidance=product_copy.ROSTER_MISMATCH_RECOVERY,
    )


def render_startup_blocked_notice(explanation: str) -> None:
    ui_primitives.render_empty_state_panel(
        product_copy.STARTUP_BLOCKED_TITLE,
        explanation,
        kind="unavailable",
        recovery_guidance=product_copy.STARTUP_BLOCKED_RECOVERY,
    )


def render_workspace_note(title: str, explanation: str, *, kind: str = "no-data") -> None:
    ui_primitives.render_empty_state_panel(
        title,
        explanation,
        kind=kind,
    )
