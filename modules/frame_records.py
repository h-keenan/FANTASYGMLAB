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


def _fast_dtype(dtype: Any) -> bool:
    return str(dtype) in _FAST_NUMPY_DTYPES or str(dtype) == "str"


def frame_records(frame: pd.DataFrame | None) -> list[dict[Any, Any]]:
    if frame is None:
        return []
    if frame.empty or not frame.columns.is_unique or not all(_fast_dtype(d) for d in frame.dtypes):
        return frame.to_dict("records")
    columns = list(frame.columns)
    object_positions = [i for i, dtype in enumerate(frame.dtypes) if str(dtype) == "object"]
    rows = frame.to_numpy(dtype=object).tolist()
    if object_positions:
        for row in rows:
            for i in object_positions:
                row[i] = maybe_box_native(row[i])
    return [dict(zip(columns, row)) for row in rows]
