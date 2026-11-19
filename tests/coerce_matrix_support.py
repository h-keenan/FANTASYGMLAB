"""Shared input matrix + registry for the float-coercer characterization test (see test_coerce_characterization.py)."""

from __future__ import annotations

import decimal
import importlib
import math
import warnings

import numpy as np
import pandas as pd


class _Raises:
    def __float__(self):
        raise RuntimeError("boom")


class _Fine:
    def __float__(self):
        return 4.25


class _EqRaises:
    def __eq__(self, other):
        raise RuntimeError("eq")

    __hash__ = None  # type: ignore[assignment]

    def __float__(self):
        return 1.0


MATRIX: list[tuple[str, object]] = [
    ("None", None),
    ("empty", ""),
    ("space", " "),
    ("str_3.5", "3.5"),
    ("str_padded", "  4 "),
    ("str_abc", "abc"),
    ("str_nan", "nan"),
    ("str_inf", "inf"),
    ("str_1e3", "1e3"),
    ("nan", float("nan")),
    ("inf", float("inf")),
    ("-inf", float("-inf")),
    ("True", True),
    ("False", False),
    ("Decimal", decimal.Decimal("2.5")),
    ("Decimal_nan", decimal.Decimal("NaN")),
    ("np_float", np.float64(1.5)),
    ("np_nan", np.float64("nan")),
    ("np_int", np.int64(3)),
    ("int", 7),
    ("int_huge", 10**400),
    ("neg", -2.5),
    ("zero", 0),
    ("neg_zero", -0.0),
    ("bytes", b"5"),
    ("complex", complex(1, 0)),
    ("list", []),
    ("list1", [1]),
    ("dict", {}),
    ("object", object()),
    ("tuple", (1, 2)),
    ("float_raises", _Raises()),
    ("float_fine", _Fine()),
    ("eq_raises", _EqRaises()),
    ("pd_NA", pd.NA),
    ("pd_NaT", pd.NaT),
    ("np_arr1", np.array([2.0])),
    ("np_arr2", np.array([1.0, 2.0])),
]

# (module, old helper name, new name bound in the module after the refactor)
REGISTRY: list[tuple[str, str, str]] = [
    ("auth_storage_handshake", "_safe_float", "float_or_none_blank"),
    ("multi_team_trade_finder", "_num", "float_nan_to_default"),
    ("wrapped_real", "_num", "float_or_default"),
    ("roster_value_model", "_num", "float_finite_or_default"),
    ("team_sheet", "_num", "float_nan_to_none"),
    ("league_recaps", "_float", "float_or_default"),
    ("trade_ideas", "_safe_float", "float_or_default_any"),
    ("draft_assistant", "_safe_float", "float_nan_to_default"),
    ("playoff_context", "_num", "float_nan_to_default"),
    ("external_league_common", "safe_float", "float_or_default"),
    ("trade_cautions", "_num", "float_or_default"),
    ("rookie_adp", "_num", "float_nan_to_none"),
    ("league_value_settings", "_safe_float", "float_or_default_any"),
    ("live_draft", "safe_float", "float_nan_to_default_blank"),
    ("team_eval", "_safe_float", "float_or_default_any"),
    ("opponent_profile", "_num", "float_nan_to_none"),
    ("weekly_roundup", "_num", "float_finite_or_default"),
    ("trade_lineup_model", "_num", "float_finite_or_none+float_finite_or_default"),
    ("espn_leagues", "_safe_float", "float_or_default"),
    ("team_profile", "_num", "float_nan_to_default"),
    ("external_interesting_trades", "_num", "float_finite_or_default"),
    ("trade_outcome_results", "_safe_float", "float_nan_to_none"),
    ("team_streaks", "_safe_float", "float_or_default"),
    ("league_maturity", "_safe_float", "float_nan_to_default"),
    ("wrapped_real_data", "_num", "float_or_none"),
    ("live_big_plays", "_num", "number_or_default"),
    ("league_integrity", "_num", "float_nan_to_none_blank"),
    ("trade_posture", "_num", "float_or_default"),
    ("transaction_grades", "_float", "float_nan_to_none_blank"),
]

DEFAULT_PROBE = -1.0


def _norm(result: object) -> str:
    if isinstance(result, float):
        if math.isnan(result):
            return "float:nan"
        return f"float:{result!r}"
    return f"{type(result).__name__}:{result!r}"


def call(fn, value, *args) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return _norm(fn(value, *args))
        except Exception as exc:  # noqa: BLE001 - the matrix records the exception type
            return f"EXC:{type(exc).__name__}"


def accepts_default(fn) -> bool:
    import inspect

    params = list(inspect.signature(fn).parameters.values())
    return len(params) >= 2


def run_matrix(fn, probe_default: bool = True) -> dict[str, str]:
    out: dict[str, str] = {}
    for label, value in MATRIX:
        out[label] = call(fn, value)
        if probe_default and accepts_default(fn):
            out[label + "|default"] = call(fn, value, DEFAULT_PROBE)
    return out


def resolve(mod, new: str):
    """``a+b``: the old helper had ``default=None``; one-arg call sites now use ``a``, explicit-default ones ``b``."""
    if "+" not in new:
        return getattr(mod, new)
    one, two = (getattr(mod, n) for n in new.split("+"))

    def both(value, *args):
        return two(value, *args) if args else one(value)

    both.__signature__ = __import__("inspect").signature(lambda value, default=None: None)  # type: ignore[attr-defined]
    return both


def load(module: str):
    return importlib.import_module(f"modules.{module}")
