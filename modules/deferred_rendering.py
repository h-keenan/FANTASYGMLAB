"""Deterministic session gates for secondary Streamlit work.

Streamlit executes the contents of collapsed expanders. These helpers add an
explicit interaction boundary so secondary content is not built until the
user requests it. Only namespaced UI readiness is stored here.
"""

from __future__ import annotations

import re
from collections.abc import MutableMapping


_STATE_PREFIX = "deferred_section_ready__"


def deferred_state_key(section_id: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(section_id).casefold()).strip("_")
    if not normalized:
        raise ValueError("section_id must contain at least one letter or number")
    return f"{_STATE_PREFIX}{normalized}"


def is_deferred_section_ready(
    state: MutableMapping[str, object],
    section_id: str,
) -> bool:
    return bool(state.get(deferred_state_key(section_id), False))


def mark_deferred_section_ready(
    state: MutableMapping[str, object],
    section_id: str,
) -> None:
    state[deferred_state_key(section_id)] = True


def reset_deferred_section(
    state: MutableMapping[str, object],
    section_id: str,
) -> None:
    state.pop(deferred_state_key(section_id), None)

