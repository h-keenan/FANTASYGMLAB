"""Canonical surplus vs need presentation for one roster snapshot."""

from __future__ import annotations

from typing import Iterable, Sequence


_SKILL = ("QB", "RB", "WR", "TE")


def _norm_positions(values: Iterable[object] | None) -> list[str]:
    seen: list[str] = []
    for raw in values or ():
        pos = str(raw or "").strip().upper()
        if pos in _SKILL and pos not in seen:
            seen.append(pos)
    return seen


def _ordered_unique(values: Sequence[object] | None) -> list[str]:
    seen: list[str] = []
    for raw in values or ():
        pos = str(raw or "").strip().upper()
        if pos and pos not in seen:
            seen.append(pos)
    return seen


def canonicalize_surplus_and_thin(
    surplus: Sequence[object] | None,
    thin: Sequence[object] | None,
    *,
    needed: Sequence[object] | None = None,
) -> tuple[list[str], list[str]]:
    """A position cannot be a clear SURPLUS and THIN in the same summary.

    Need wins skill-position overlap (coverage shortage). Otherwise the
    position stays surplus and is dropped from thin. Non-skill rooms such as
    K remain unchanged. No invented starter-vs-depth copy.
    """

    surplus_list = _ordered_unique(surplus)
    thin_list = _ordered_unique(thin)
    needed_set = set(_norm_positions(needed))
    overlap = (set(surplus_list) & set(thin_list)) & set(_SKILL)
    for pos in overlap:
        if pos in needed_set:
            surplus_list = [item for item in surplus_list if item != pos]
        else:
            thin_list = [item for item in thin_list if item != pos]
    return surplus_list, thin_list


def surplus_thin_summary_clause(
    surplus: Sequence[object] | None,
    thin: Sequence[object] | None,
    *,
    needed: Sequence[object] | None = None,
) -> str:
    surplus_list, thin_list = canonicalize_surplus_and_thin(
        surplus, thin, needed=needed
    )
    surplus_text = ", ".join(surplus_list) or "None"
    thin_text = ", ".join(thin_list) or "None"
    return f"Surplus: {surplus_text} | Thin: {thin_text}"
