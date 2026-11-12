"""Row dicts from a DataFrame, equivalent to ``frame.to_dict("records")``.

``DataFrame.to_dict("records")`` goes column by column (``iloc[:, k]`` plus a
Series iterator per column); on the wide player frames (about 140 columns)
that is milliseconds for a handful of rows, and the trade search asks for it
once per candidate package. One ``to_numpy(dtype=object)`` and a single
``tolist()`` give the same native Python values in microseconds for the dtypes
the player frames use. Object cells are boxed with pandas' own
``maybe_box_native`` exactly as ``to_dict`` does; any other dtype (datetimes,
nullable, categorical, 32-bit numerics, ...) or duplicate column labels keep
the pandas path.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from pandas.core.dtypes.cast import maybe_box_native

_FAST_NUMPY_DTYPES = frozenset({"float64", "int64", "bool", "object"})


def _classify_dtype(dtype: Any) -> str:
    name = str(dtype)
    if name == "object":
        return "object"
    return "fast" if (name in _FAST_NUMPY_DTYPES or name == "str") else "slow"


# dtype -> "object" | "fast" | "slow". ``str(dtype)`` is surprisingly costly
# (about 4 us) and a 140-column frame pays it per column per call; dtypes are
# hashable and few, so classify each distinct dtype once.
_DTYPE_KIND: dict[Any, str] = {}


def _fast_dtype(dtype: Any) -> bool:
    return _dtype_kind(dtype) != "slow"


def _dtype_kind(dtype: Any) -> str:
    try:
        return _DTYPE_KIND[dtype]
    except KeyError:
        kind = _classify_dtype(dtype)
        try:
            _DTYPE_KIND[dtype] = kind
        except TypeError:  # unhashable extension dtype: classify every time
            pass
        return kind
    except TypeError:
        return _classify_dtype(dtype)


def frame_records(frame: pd.DataFrame | None) -> list[dict[Any, Any]]:
    if frame is None:
        return []
    if frame.empty or not frame.columns.is_unique:
        return frame.to_dict("records")
    kinds = [_dtype_kind(d) for d in frame.dtypes.tolist()]
    if "slow" in kinds:
        return frame.to_dict("records")
    columns = list(frame.columns)
    object_positions = [i for i, kind in enumerate(kinds) if kind == "object"]
    rows = frame.to_numpy(dtype=object).tolist()
    if object_positions:
        for row in rows:
            for i in object_positions:
                row[i] = maybe_box_native(row[i])
    return [dict(zip(columns, row)) for row in rows]
