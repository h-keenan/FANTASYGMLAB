import pandas as pd
import pytest

from scripts.benchmark_public_player_cache import comparable


@pytest.mark.parametrize("storage", ["python", "pyarrow"])
def test_missing_normalization_preserves_value_equivalence(storage):
    left = pd.DataFrame({"injury_level": pd.Series(
        ["healthy", pd.NA, "minor", None], dtype=object
    )})
    right = pd.DataFrame({"injury_level": pd.Series(
        ["healthy", float("nan"), "minor", pd.NA],
        dtype=pd.StringDtype(storage=storage),
    )})
    fields = ["injury_level"]
    pd.testing.assert_frame_equal(comparable(left, fields), comparable(right, fields))
    right.loc[2, "injury_level"] = "healthy"
    with pytest.raises(AssertionError):
        pd.testing.assert_frame_equal(comparable(left, fields), comparable(right, fields))


def test_normalization_preserves_present_values_and_order():
    values = [7, True, 2.5, ["RB", "WR"], ("QB",), "healthy"]
    frame = pd.DataFrame({"values": pd.Series(values, dtype=object), "other": range(6)})
    result = comparable(frame, ["other", "values"])
    assert list(result.columns) == ["other", "values"]
    for original, normalized in zip(values, result["values"]):
        assert type(normalized) is type(original)
        assert normalized == original
