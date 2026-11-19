"""The one place that turns "something that should be a number" into a float.

Before this module, ~30 modules each defined a private ``_num`` / ``_safe_float`` / ``safe_float`` / ``_float`` with
subtly different rules for NaN, infinity, ``None``/``""`` and which exceptions to swallow (audit item 7). Each variant
below documents ONE exact semantic and every former helper maps to the variant that matches it. Pick by the table:

                              on failure   NaN          +/-inf       exceptions caught
  float_or_default            default      passed       passed       TypeError, ValueError
  float_or_default_any        default      passed       passed       Exception
  float_nan_to_default        default      -> default   passed       TypeError, ValueError
  float_finite_or_default     default      -> default   -> default   TypeError, ValueError
  float_or_none               None         passed       passed       TypeError, ValueError
  float_nan_to_none           None         -> None      passed       TypeError, ValueError
  float_finite_or_none        None         -> None      -> None      TypeError, ValueError
  float_or_none_blank         None         passed       passed       TypeError, ValueError, "" check inside try
  float_nan_to_default_blank  default      -> default   passed       TypeError, ValueError, "" check inside try
  float_nan_to_none_blank     None         -> None      passed       TypeError, ValueError, "" check outside try
  number_or_default           default      -> default   passed       none (isinstance int/float only)
  float_if_number             None         passed       passed       none (isinstance int/float only)

``bool`` is an ``int`` so ``True`` coerces to ``1.0`` everywhere. Exceptions outside the listed ones (for example
``OverflowError`` from ``float(10**400)``, or an error raised inside a custom ``__float__``) propagate.
The ``*_blank`` variants also treat ``""`` as missing; they differ only in WHERE the ``== ""`` test runs (inside the try,
so ``pd.NA`` / multi-element arrays give the failure result, or outside it, so they raise), because the former helpers
differed there and callers' behaviour on such inputs is frozen by tests/test_coerce_characterization.py.
"""

from __future__ import annotations

import math
from typing import Any

__all__ = [
    "float_or_default",
    "float_or_default_any",
    "float_nan_to_default",
    "float_finite_or_default",
    "float_or_none",
    "float_or_none_blank",
    "float_nan_to_default_blank",
    "float_nan_to_none_blank",
    "float_finite_or_none",
    "float_nan_to_none",
    "number_or_default",
    "float_if_number",
]


def float_or_default(value: Any, default: Any = 0.0) -> Any:
    """``float(value)``, or ``default`` on TypeError/ValueError. NaN and inf pass through."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def float_or_default_any(value: Any, default: Any = 0.0) -> Any:
    """Like ``float_or_default`` but swallows every ``Exception`` (even a failing ``__float__``)."""
    try:
        return float(value)
    except Exception:
        return default


def float_nan_to_default(value: Any, default: Any = 0.0) -> Any:
    """``float(value)``; ``default`` on TypeError/ValueError or when the result is NaN. inf passes through."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if out == out else default


def float_finite_or_default(value: Any, default: Any = 0.0) -> Any:
    """``float(value)``; ``default`` on TypeError/ValueError or when the result is NaN or +/-inf."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def float_or_none(value: Any) -> float | None:
    """``float(value)``, or None on None/TypeError/ValueError. NaN and inf pass through."""
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def float_nan_to_none(value: Any) -> float | None:
    """``float(value)``, or None on None/TypeError/ValueError or when the result is NaN. inf passes through."""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def number_or_default(value: Any, default: float = 0.0) -> float:
    """``float(value)`` only when ``value`` is already an int/float (bool included) and not NaN, else ``default``."""
    return float(value) if isinstance(value, (int, float)) and value == value else default


def float_if_number(value: Any) -> float | None:
    """``float(value)`` only when ``value`` is already an int/float (bool included), else None. NaN passes through."""
    return float(value) if isinstance(value, (int, float)) else None


def float_finite_or_none(value: Any) -> float | None:
    """``float(value)``; None on TypeError/ValueError or when the result is NaN or +/-inf."""
    return float_finite_or_default(value, None)


def float_or_none_blank(value: Any) -> float | None:
    """Like ``float_or_none`` but ``""`` is also missing. The ``== ""`` test runs inside the try, so a value whose
    ``__eq__`` raises TypeError/ValueError (``pd.NA``, a multi-element array) yields None; any other error propagates."""
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def float_nan_to_default_blank(value: Any, default: Any = 0.0) -> Any:
    """Like ``float_nan_to_default`` but ``None``/``""`` short-circuit to ``default`` with the ``== ""`` test inside the
    try (same error behaviour as ``float_or_none_blank``)."""
    try:
        if value is None or value == "":
            return default
        out = float(value)
        return out if out == out else default
    except (TypeError, ValueError):
        return default


def float_nan_to_none_blank(value: Any) -> float | None:
    """Like ``float_nan_to_none`` but ``""`` is also missing. The ``in (None, "")`` test runs OUTSIDE the try, so a
    value whose ``==`` raises (``pd.NA``, a multi-element array) raises to the caller, as the old helpers did."""
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None
