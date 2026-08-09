"""Shell chrome schema contracts after cold-path decoupling (#215 / hotfix).

Two distinct states:

A. IDENTITY SHELL
   Guaranteed from league/auth context, not from a valued display frame:
   - league identity, roster identity (``my_roster_id`` / roster profile)
   - account/entitlement, navigation
   Does NOT require ``roster_id`` on any DataFrame, valued ranks, or enrichment.

B. VALUED / ENRICHED SHELL
   Optional rows from ``league_detail_ranks`` / team-direction summary that include
   ``roster_id`` plus ranks, posture, draft context, etc.

Global loading only requires A. Valued enrichment must never KeyError when the
display frame is empty, partial, or missing ``roster_id``.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

ROSTER_ID_COLUMN = "roster_id"

# Provenance tokens for shell chrome memo signatures (identity vs valued).
IDENTITY_SHELL_PROVENANCE = "identity"
VALUED_SHELL_PROVENANCE = "valued"
PENDING_VALUED_SHELL_PROVENANCE = "valued_pending"


def has_roster_id_column(frame: pd.DataFrame | None) -> bool:
    """True when ``frame`` exposes a ``roster_id`` column (may still have zero rows)."""

    if frame is None:
        return False
    columns = getattr(frame, "columns", None)
    if columns is None:
        return False
    return ROSTER_ID_COLUMN in columns


def is_valued_shell_display(frame: pd.DataFrame | None) -> bool:
    """Valued-shell schema: roster_id present. Empty/RangeIndex-only → False."""

    return has_roster_id_column(frame)


def select_shell_team_row(
    frame: pd.DataFrame | None,
    roster_id: object,
) -> dict[str, Any]:
    """Resolve optional valued enrichment for ``roster_id``.

    Never synthesizes a fake ``roster_id`` column. Returns ``{}`` when:
    - frame is None / missing ``roster_id``
    - zero rows / no matching roster
    Callers must already know roster identity from profile/membership context.
    """

    if roster_id is None or roster_id == "":
        return {}
    if not has_roster_id_column(frame):
        return {}
    assert frame is not None
    if len(frame.index) == 0:
        return {}
    try:
        matched = frame[frame[ROSTER_ID_COLUMN].astype(str) == str(roster_id)]
    except (TypeError, ValueError, KeyError):
        return {}
    if matched.empty:
        return {}
    row = matched.iloc[0]
    return row.to_dict() if hasattr(row, "to_dict") else dict(row)


def team_row_from_shell_context(
    shell_context: Mapping[str, Any] | None,
    roster_id: object,
) -> dict[str, Any]:
    """Pull optional valued row from ``league_detail_ranks`` (shell_display owner).

    After #215, ``league_detail_ranks`` may be empty, RangeIndex-only, or a
    partial frame without ``roster_id``. This is the single guarded lookup used
    by ``_build_shell_chrome_bundle`` via ``get_or_build_shell_chrome``.
    """

    context = shell_context if isinstance(shell_context, Mapping) else {}
    shell_display = context.get("league_detail_ranks", pd.DataFrame())
    if shell_display is None:
        shell_display = pd.DataFrame()
    return select_shell_team_row(shell_display, roster_id)


def legacy_shell_display_row_lookup(
    shell_display: pd.DataFrame,
    roster_id: object,
) -> dict[str, Any]:
    """Pre-hotfix lookup — raises KeyError when ``roster_id`` column is absent.

    Kept for regression tests that prove the production crash shape.
    """

    shell_row = shell_display[
        shell_display[ROSTER_ID_COLUMN].astype(str) == str(roster_id)
    ]
    return shell_row.iloc[0].to_dict() if not shell_row.empty else {}


def strategy_summary_usable(frame: pd.DataFrame | None) -> bool:
    """Team-direction summary is usable for metrics only with roster_id schema."""

    if not has_roster_id_column(frame):
        return False
    assert frame is not None
    return len(frame.index) > 0


def identity_shell_bundle(
    *,
    strategy: str = "retool",
    strategy_label: str = "",
    auto_strategy: str | None = None,
    strategy_override: str = "Auto",
    profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Minimal chrome bundle — no valued team row."""

    resolved_strategy = str(strategy or "retool")
    return {
        "active_team_strategy": resolved_strategy,
        "active_team_strategy_label": strategy_label or resolved_strategy,
        "auto_team_strategy": str(auto_strategy or resolved_strategy),
        "team_strategy_override": str(strategy_override or "Auto"),
        "shell_team_profile": dict(profile or {}),
        "shell_team_row": {},
        "shell_chrome_schema": IDENTITY_SHELL_PROVENANCE,
    }


def valued_shell_bundle(
    *,
    strategy: str,
    strategy_label: str,
    auto_strategy: str,
    strategy_override: str,
    profile: Mapping[str, Any] | None,
    team_row: Mapping[str, Any] | None,
    enrichment_pending: bool = False,
) -> dict[str, Any]:
    """Chrome bundle after optional valued-row enrichment."""

    provenance = (
        PENDING_VALUED_SHELL_PROVENANCE
        if enrichment_pending or not team_row
        else VALUED_SHELL_PROVENANCE
    )
    return {
        "active_team_strategy": str(strategy or "retool"),
        "active_team_strategy_label": str(strategy_label or strategy or "retool"),
        "auto_team_strategy": str(auto_strategy or strategy or "retool"),
        "team_strategy_override": str(strategy_override or "Auto"),
        "shell_team_profile": dict(profile or {}),
        "shell_team_row": dict(team_row or {}),
        "shell_chrome_schema": provenance,
    }
