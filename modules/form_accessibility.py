"""Canonical Streamlit form-control accessibility helpers.

Streamlit 1.61 emits ``autocomplete=""`` when the parameter is omitted on
non-password ``st.text_input`` widgets, which Chrome reports as an invalid
autocomplete token. Password inputs default to ``new-password``, which is
wrong for sign-in.

Owned consumer-facing text inputs must pass a non-empty valid token.
Do not emit ``autocomplete=""``.
"""

from __future__ import annotations

from typing import Any

import streamlit as st


EMAIL = "email"
CURRENT_PASSWORD = "current-password"
NEW_PASSWORD = "new-password"
USERNAME = "username"
OFF = "off"

VALID_TOKENS = frozenset(
    {
        EMAIL,
        CURRENT_PASSWORD,
        NEW_PASSWORD,
        USERNAME,
        OFF,
        "on",
        "name",
        "organization",
        "tel",
        "url",
    }
)


def require_autocomplete(value: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise ValueError("autocomplete must be a non-empty valid token")
    if token not in VALID_TOKENS:
        raise ValueError(f"unsupported autocomplete token: {token}")
    return token


def text_input(label: str, *, autocomplete: str, **kwargs: Any) -> Any:
    """``st.text_input`` that never emits an empty autocomplete attribute."""

    return st.text_input(
        label,
        autocomplete=require_autocomplete(autocomplete),
        **kwargs,
    )
