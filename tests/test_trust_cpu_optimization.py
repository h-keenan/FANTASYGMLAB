from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from modules import trust_engine
from modules.player_eligibility import (
    annotate_player_eligibility,
    eligibility_diagnostics,
    filter_current_fantasy_players,
)
from scripts.profile_trust_enforcement import (
    _diagnostic_and_schema_equivalence,
    _load_real_frame,
    _safe_profile_location,
)


NOW = datetime(2026, 7, 30, tzinfo=timezone.utc)


def _reference_validate_player(record, *, now=None):
    stable = trust_engine._stable_payload(record)
    payload = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return trust_engine._cached_validation(
        "player",
        trust_engine.canonical_object_key("player", record),
        payload,
        trust_engine._now_bucket(now),
    )


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


def _differential(frame: pd.DataFrame, *, now: datetime = NOW):
    trust_engine.clear_validation_cache()
    with patch(
        "modules.trust_enforcement.validate_player",
        side_effect=_reference_validate_player,
    ):
        reference = annotate_player_eligibility(frame, now=now)
    reference_diagnostics = eligibility_diagnostics(reference)

    trust_engine.clear_validation_cache()
    optimized = annotate_player_eligibility(frame, now=now)
    pd.testing.assert_frame_equal(
        reference,
        optimized,
        check_dtype=True,
        check_exact=True,
    )
    assert eligibility_diagnostics(optimized) == reference_diagnostics
    return reference, optimized


def test_validation_reuses_one_stable_serialization_for_key_and_payload():
    original_dumps = trust_engine.json.dumps
    with patch.object(trust_engine.json, "dumps", wraps=original_dumps) as dumps:
        trust_engine.clear_validation_cache()
        trust_engine.validate_player(_row(), now=NOW)

    assert dumps.call_count == 1


def test_real_public_player_dataset_is_exactly_equivalent():
    frame, output_columns = _load_real_frame("data/players.db")

    result = _diagnostic_and_schema_equivalence(frame, output_columns)

    assert len(frame) == 988
    assert all(
        result[key]
        for key in (
            "frame_exact",
            "column_order_exact",
            "row_order_exact",
            "dtypes_exact",
            "null_masks_exact",
            "fingerprints_exact",
            "diagnostics_exact",
            "schema_restoration_exact",
        )
    )


@pytest.mark.parametrize(
    "record",
    [
        _row(),
        _row(player_id="injured", injury_status="Out"),
        _row(player_id="recent", metadata_updated_at="2026-07-29T00:00:00+00:00"),
        _row(player_id="stale", metadata_updated_at="2022-01-01T00:00:00+00:00"),
        _row(player_id="rookie", years_exp=np.int64(0), age=np.float64(21.0)),
        _row(player_id="retired", active=False, status="retired", team=""),
        _row(player_id="fa", team="", depth_chart_position="", depth_chart_order=0),
        _row(player_id="no-news", news_updated=None, news_updated_at=None),
        _row(player_id="malformed", verified_signals={"team": ["CHI", "GB"]}),
        _row(player_id="", full_name="Missing Identity"),
        _row(
            player_id="nulls",
            age=None,
            bye_week=None,
            news_updated=pd.NA,
            metadata_updated_at=None,
            fantasycalc_value=np.nan,
        ),
    ],
)
def test_controlled_player_categories_remain_exact(record):
    _differential(pd.DataFrame([record]))


def test_duplicate_names_and_identities_preserve_order_reasons_and_diagnostics():
    frame = pd.DataFrame(
        [
            _row(player_id="duplicate", full_name="Same Name"),
            _row(player_id="duplicate", full_name="Same Name"),
            _row(player_id="unique", full_name="Same Name"),
        ]
    )

    reference, optimized = _differential(frame)

    assert reference.index.equals(optimized.index)
    assert reference["trust_block_reason"].tolist() == [
        "duplicate_player_identity",
        "duplicate_player_identity",
        "",
    ]


@pytest.mark.parametrize(
    "now,updated",
    [
        (
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            "2025-12-31T23:59:59+00:00",
        ),
        (
            datetime(2027, 1, 1, tzinfo=timezone.utc),
            "2026-01-01T00:00:00+00:00",
        ),
        (
            datetime(2026, 7, 30, tzinfo=timezone.utc),
            "2024-07-30T00:00:00+00:00",
        ),
    ],
)
def test_date_and_year_boundaries_remain_exact(now, updated):
    _differential(
        pd.DataFrame(
            [
                _row(
                    metadata_updated_at=updated,
                    news_updated_at=updated,
                    stats_season=now.year - 1,
                    latest_stats_season=now.year - 1,
                )
            ]
        ),
        now=now,
    )


def test_fingerprints_and_cache_keys_are_byte_identical_for_stable_payloads():
    records = [
        _row(),
        dict(reversed(tuple(_row(player_id="unicode-\u00e9").items()))),
        _row(
            player_id="mixed",
            verified_signals={"team": {"CHI", "GB"}},
            bye_week=np.int64(7),
        ),
    ]
    for record in records:
        stable = trust_engine._stable_payload(record)
        payload = json.dumps(stable, sort_keys=True, separators=(",", ":"))
        assert trust_engine._canonical_object_key_from_payload(
            "player",
            payload,
        ) == trust_engine.canonical_object_key("player", record)


def test_repeated_invocations_do_not_reuse_changed_player_decisions():
    first = pd.DataFrame([_row(status="active", active=True)])
    changed = pd.DataFrame([_row(status="retired", active=False)])

    first_result = annotate_player_eligibility(first, now=NOW)
    changed_result = annotate_player_eligibility(changed, now=NOW)

    assert (
        first_result.iloc[0]["trust_validation_fingerprint"]
        != changed_result.iloc[0]["trust_validation_fingerprint"]
    )
    assert first_result.iloc[0]["is_current_fantasy_eligible"]
    assert not changed_result.iloc[0]["is_current_fantasy_eligible"]


def test_diagnostics_disabled_and_recording_failure_preserve_filtered_output():
    frame = pd.DataFrame([_row(), _row(player_id="", full_name="Blocked")])
    expected = filter_current_fantasy_players(frame, now=NOW)

    with patch("modules.performance.debug_enabled", return_value=True), patch(
        "modules.performance.record_trust_diagnostics",
        side_effect=RuntimeError("controlled diagnostic failure"),
    ):
        actual = filter_current_fantasy_players(frame, now=NOW)

    pd.testing.assert_frame_equal(expected, actual, check_exact=True)


def test_malformed_scalar_exception_behavior_is_unchanged():
    class BrokenScalar:
        def __str__(self):
            raise RuntimeError("controlled malformed scalar")

    record = _row(player_id=BrokenScalar())
    trust_engine.clear_validation_cache()
    with pytest.raises(RuntimeError, match="controlled malformed scalar"):
        _reference_validate_player(record, now=NOW)
    trust_engine.clear_validation_cache()
    with pytest.raises(RuntimeError, match="controlled malformed scalar"):
        trust_engine.validate_player(record, now=NOW)


def test_no_new_persistent_trust_state_or_app_wiring():
    source = Path("modules/trust_engine.py").read_text(encoding="utf-8")

    assert "st.session_state" not in source
    assert "cache_data" not in source
    assert "cache_resource" not in source
    assert "_canonical_object_key_from_payload(kind, payload)" in source
    assert Path("app.py").read_text(encoding="utf-8")


def test_profiler_locations_do_not_expose_host_path_segments():
    external = _safe_profile_location(
        r"C:\Users\controlled-user\venv\Lib\site-packages\pandas\core.py",
        42,
    )
    repository = _safe_profile_location(
        str(Path.cwd() / "modules" / "trust_engine.py"),
        17,
    )

    assert external == "core.py:42"
    assert "controlled-user" not in external
    assert repository == "./modules/trust_engine.py:17"
