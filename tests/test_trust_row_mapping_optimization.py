from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from modules import trust_engine
from modules.player_eligibility import (
    annotate_player_eligibility,
    eligibility_diagnostics,
)
from modules.trust_enforcement import enforce_player_record
from scripts.profile_trust_enforcement import _load_real_frame
from scripts.profile_trust_row_mapping import (
    _safe_location,
    reference_annotate,
)


NOW = datetime(2026, 7, 30, tzinfo=timezone.utc)


def _row(**overrides):
    row = {
        "player_id": "100",
        "full_name": "Controlled Player",
        "position": "QB",
        "fantasy_positions": ["QB"],
        "sport": "nfl",
        "active": True,
        "status": "active",
        "team": "CHI",
        "age": 25.0,
        "bye_week": 7,
        "years_exp": 2,
        "depth_chart_position": "QB",
        "depth_chart_order": 1,
        "stats_season": 2025,
        "latest_stats_season": 2025,
        "fantasycalc_value": 1000.0,
        "news_updated": NOW.timestamp(),
        "news_updated_at": NOW.isoformat(),
        "metadata_updated_at": NOW.isoformat(),
        "injury_status": "",
        "verified_signals": {},
    }
    row.update(overrides)
    return row


def _assert_exact(frame: pd.DataFrame):
    trust_engine.clear_validation_cache()
    expected = reference_annotate(frame, now=NOW)
    expected_diagnostics = eligibility_diagnostics(expected)
    trust_engine.clear_validation_cache()
    actual = annotate_player_eligibility(frame, now=NOW)

    pd.testing.assert_frame_equal(expected, actual, check_exact=True, check_dtype=True)
    assert expected_diagnostics == eligibility_diagnostics(actual)
    assert expected["trust_validation_fingerprint"].equals(
        actual["trust_validation_fingerprint"]
    )
    return expected, actual


def test_real_988_player_frame_is_field_for_field_equivalent():
    frame, output_columns = _load_real_frame("data/players.db")

    expected, actual = _assert_exact(frame)

    assert len(frame) == 988
    assert tuple(expected.columns) == tuple(actual.columns)
    assert tuple(output_columns) == tuple(
        column for column in output_columns if column in actual.columns
    )
    assert expected.isna().equals(actual.isna())


def test_nullable_extension_and_timestamp_scalars_remain_exact():
    frame = pd.DataFrame(
        {
            "player_id": pd.Series(["101", "102", pd.NA], dtype="string"),
            "full_name": pd.Series(["One", "Two", "Missing"], dtype="string"),
            "position": pd.Series(["QB", "RB", "WR"], dtype="string"),
            "fantasy_positions": [["QB"], ["RB"], ["WR"]],
            "sport": pd.Series(["nfl", "nfl", "nfl"], dtype="string"),
            "active": pd.Series([True, pd.NA, False], dtype="boolean"),
            "status": pd.Series(["active", "", "retired"], dtype="string"),
            "team": pd.Series(["CHI", pd.NA, ""], dtype="string"),
            "age": pd.Series([25, pd.NA, 31], dtype="Int64"),
            "bye_week": pd.Series([7, pd.NA, 10], dtype="Int64"),
            "years_exp": pd.Series([2, 0, pd.NA], dtype="Int64"),
            "depth_chart_position": ["QB", "", ""],
            "depth_chart_order": pd.Series([1, pd.NA, 0], dtype="Int64"),
            "stats_season": pd.Series([2025, pd.NA, 2023], dtype="Int64"),
            "latest_stats_season": pd.Series([2025, pd.NA, 2023], dtype="Int64"),
            "fantasycalc_value": pd.Series([1000.0, np.nan, 0.0], dtype="Float64"),
            "news_updated": [NOW.timestamp(), np.nan, None],
            "news_updated_at": [
                pd.Timestamp("2026-07-30T00:00:00Z"),
                pd.Timestamp("2026-07-29T00:00:00Z"),
                pd.Timestamp("2024-01-01", tz="UTC"),
            ],
            "metadata_updated_at": [
                pd.Timestamp("2026-07-30T00:00:00Z"),
                pd.Timestamp("2026-07-29T00:00:00Z"),
                pd.Timestamp("2024-01-01", tz="UTC"),
            ],
            "injury_status": ["", pd.NA, "Out"],
            "verified_signals": [{}, {"team": ["CHI"]}, {}],
        }
    )

    _assert_exact(frame)


@pytest.mark.parametrize(
    "record",
    [
        _row(player_id=np.int64(101), age=np.float64(24.0)),
        _row(player_id="00101", bye_week="07", age="25"),
        _row(player_id="", full_name="Missing Identity"),
        _row(player_id="rookie", years_exp=0),
        _row(player_id="inactive", active=False, status="retired"),
        _row(player_id="free-agent", team=""),
        _row(player_id="injured", injury_status="Out"),
        _row(player_id="no-news", news_updated=None, news_updated_at=None),
        _row(player_id="null", age=None, bye_week=np.nan, metadata_updated_at=None),
        _row(
            player_id="nested",
            verified_signals={"team": ["CHI"], "source": {"valid": True}},
        ),
    ],
)
def test_python_numpy_null_and_nested_records_remain_exact(record):
    _assert_exact(pd.DataFrame([record]))


def test_one_series_and_one_enforcement_mapping_are_constructed_per_player():
    frame = pd.DataFrame([_row(player_id=str(index)) for index in range(4)])
    original_iterrows = pd.DataFrame.iterrows
    original_to_dict = pd.Series.to_dict
    yielded = 0
    mappings = 0

    def observed_iterrows(self):
        nonlocal yielded
        for item in original_iterrows(self):
            yielded += 1
            yield item

    def observed_to_dict(self, *args, **kwargs):
        nonlocal mappings
        mappings += 1
        return original_to_dict(self, *args, **kwargs)

    with patch.object(pd.DataFrame, "iterrows", observed_iterrows), patch.object(
        pd.Series,
        "to_dict",
        observed_to_dict,
    ):
        annotate_player_eligibility(frame, now=NOW)

    assert yielded == len(frame)
    assert mappings == len(frame)


def test_shared_mapping_is_not_mutated_by_trust_consumers():
    row = _row(verified_signals={"team": ["CHI"]})
    before = {
        **row,
        "verified_signals": {"team": list(row["verified_signals"]["team"])},
    }

    enforce_player_record(
        row,
        eligible=True,
        canonical_player_ids=frozenset({"100"}),
    )

    assert row == before


def test_repeated_invocations_do_not_retain_or_reuse_row_mappings():
    frame = pd.DataFrame([_row()])
    seen = []

    def observed(record, *args, **kwargs):
        seen.append(record)
        return enforce_player_record(record, *args, **kwargs)

    with patch("modules.player_eligibility.enforce_player_record", side_effect=observed):
        first = annotate_player_eligibility(frame, now=NOW)
        changed = annotate_player_eligibility(
            frame.assign(status="retired", active=False),
            now=NOW,
        )

    assert seen[0] is not seen[1]
    assert first.iloc[0]["trust_validation_fingerprint"] != changed.iloc[0][
        "trust_validation_fingerprint"
    ]


def test_malformed_scalar_exception_behavior_is_identical():
    class BrokenScalar:
        def __str__(self):
            raise RuntimeError("controlled malformed scalar")

    frame = pd.DataFrame([_row(player_id=BrokenScalar())])
    with pytest.raises(RuntimeError, match="controlled malformed scalar"):
        reference_annotate(frame, now=NOW)
    with pytest.raises(RuntimeError, match="controlled malformed scalar"):
        annotate_player_eligibility(frame, now=NOW)


def test_nat_exception_behavior_is_identical():
    frame = pd.DataFrame([_row(metadata_updated_at=pd.NaT)])

    with pytest.raises(ValueError, match="NaTType does not support astimezone"):
        reference_annotate(frame, now=NOW)
    with pytest.raises(ValueError, match="NaTType does not support astimezone"):
        annotate_player_eligibility(frame, now=NOW)


def test_timezone_naive_timestamp_exception_behavior_is_identical():
    frame = pd.DataFrame(
        [_row(metadata_updated_at=pd.Timestamp("2026-07-30T00:00:00"))]
    )

    with pytest.raises(TypeError, match="tz-naive Timestamp"):
        reference_annotate(frame, now=NOW)
    with pytest.raises(TypeError, match="tz-naive Timestamp"):
        annotate_player_eligibility(frame, now=NOW)


def test_diagnostics_disabled_and_recording_failure_remain_outside_row_lifetime():
    frame = pd.DataFrame([_row(), _row(player_id="", full_name="Blocked")])
    expected = annotate_player_eligibility(frame, now=NOW)

    with patch(
        "modules.performance.record_trust_diagnostics",
        side_effect=RuntimeError("controlled failure"),
    ):
        actual = annotate_player_eligibility(frame, now=NOW)

    pd.testing.assert_frame_equal(expected, actual, check_exact=True)


def test_no_persistent_row_cache_or_app_change():
    source = Path("modules/player_eligibility.py").read_text(encoding="utf-8")

    assert "st.session_state" not in source
    assert "cache_data" not in source
    assert "cache_resource" not in source
    assert "rows = [row for _, row in annotated.iterrows()]" in source
    assert Path("app.py").read_text(encoding="utf-8")


def test_benchmark_locations_are_sanitized():
    location = _safe_location(
        r"C:\Users\controlled-user\venv\Lib\site-packages\pandas\core.py",
        42,
    )

    assert location == "core.py:42"
    assert "controlled-user" not in location
