import json
from pathlib import Path
import shutil
from unittest.mock import patch

import pandas as pd

from modules import public_player_snapshot
from modules import rankings


def _hydrated_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": pd.Series(["101", "202"], dtype="object"),
            "name": pd.Series(["Fixture One", "Fixture Two"], dtype="object"),
            "position": pd.Series(["QB", "WR"], dtype="object"),
            "injury_level": pd.Series(["healthy", "moderate"], dtype="object"),
            "is_current_fantasy_eligible": pd.Series([True, False], dtype="bool"),
            "value_score": pd.Series([9000, 8000], dtype="int64"),
            "trust_enforcement": pd.Series(["pass", "blocked"], dtype="object"),
        }
    )


def _fingerprint(size: int = 10):
    return (("sqlite", True, size, 1), ("season_stats", True, 20, 2))


def test_snapshot_builder_keeps_only_deterministic_public_hydration():
    snapshot = public_player_snapshot.build_public_player_snapshot(
        _hydrated_frame(),
        hydration_columns=(
            "name",
            "position",
            "injury_level",
            "is_current_fantasy_eligible",
        ),
    )

    assert snapshot.columns.tolist() == [
        "player_id",
        "name",
        "position",
        "injury_level",
        "is_current_fantasy_eligible",
    ]
    assert "value_score" not in snapshot
    assert "trust_enforcement" not in snapshot


def test_snapshot_builder_rejects_valuation_ranking_and_trust_columns():
    for forbidden in ("value_score", "search_rank", "trust_enforcement"):
        try:
            public_player_snapshot.build_public_player_snapshot(
                _hydrated_frame(),
                hydration_columns=("name", forbidden),
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"{forbidden} was accepted")


def test_snapshot_round_trip_preserves_fields_order_dtypes_and_missing_values(tmp_path):
    source = _hydrated_frame().copy()
    source.loc[1, "name"] = None
    snapshot = public_player_snapshot.build_public_player_snapshot(
        source,
        hydration_columns=(
            "name",
            "position",
            "injury_level",
            "is_current_fantasy_eligible",
        ),
    )
    db_path = tmp_path / "players.db"

    public_player_snapshot.save_public_player_snapshot(
        db_path,
        snapshot,
        source_fingerprint=_fingerprint(),
        output_columns=source.columns,
    )
    loaded = public_player_snapshot.load_public_player_snapshot(
        db_path,
        source_fingerprint=_fingerprint(),
    )

    assert loaded is not None
    assert loaded.output_columns == tuple(source.columns)
    pd.testing.assert_frame_equal(loaded.frame, snapshot, check_dtype=True)


def test_schema_version_mismatch_invalidates_snapshot(tmp_path):
    db_path = tmp_path / "players.db"
    snapshot = public_player_snapshot.build_public_player_snapshot(
        _hydrated_frame(),
        hydration_columns=("name", "position", "injury_level"),
    )
    public_player_snapshot.save_public_player_snapshot(
        db_path,
        snapshot,
        source_fingerprint=_fingerprint(),
        output_columns=_hydrated_frame().columns,
    )
    _, metadata_path = public_player_snapshot.snapshot_paths(db_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["schema_version"] += 1
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    assert (
        public_player_snapshot.load_public_player_snapshot(
            db_path,
            source_fingerprint=_fingerprint(),
        )
        is None
    )
    assert not any(path.exists() for path in public_player_snapshot.snapshot_paths(db_path))


def test_source_fingerprint_mismatch_invalidates_snapshot(tmp_path):
    db_path = tmp_path / "players.db"
    snapshot = public_player_snapshot.build_public_player_snapshot(
        _hydrated_frame(),
        hydration_columns=("name", "position", "injury_level"),
    )
    public_player_snapshot.save_public_player_snapshot(
        db_path,
        snapshot,
        source_fingerprint=_fingerprint(),
        output_columns=_hydrated_frame().columns,
    )

    assert (
        public_player_snapshot.load_public_player_snapshot(
            db_path,
            source_fingerprint=_fingerprint(size=11),
        )
        is None
    )
    assert not any(path.exists() for path in public_player_snapshot.snapshot_paths(db_path))


def test_deserialize_failure_invalidates_and_returns_none(tmp_path):
    db_path = tmp_path / "players.db"
    snapshot = public_player_snapshot.build_public_player_snapshot(
        _hydrated_frame(),
        hydration_columns=("name", "position", "injury_level"),
    )
    public_player_snapshot.save_public_player_snapshot(
        db_path,
        snapshot,
        source_fingerprint=_fingerprint(),
        output_columns=_hydrated_frame().columns,
    )
    data_path, _ = public_player_snapshot.snapshot_paths(db_path)
    data_path.write_bytes(b"not-a-pickle")

    assert (
        public_player_snapshot.load_public_player_snapshot(
            db_path,
            source_fingerprint=_fingerprint(),
        )
        is None
    )
    assert not any(path.exists() for path in public_player_snapshot.snapshot_paths(db_path))


def test_snapshot_load_returns_mutation_isolated_frames(tmp_path):
    db_path = tmp_path / "players.db"
    snapshot = public_player_snapshot.build_public_player_snapshot(
        _hydrated_frame(),
        hydration_columns=("name", "position", "injury_level"),
    )
    public_player_snapshot.save_public_player_snapshot(
        db_path,
        snapshot,
        source_fingerprint=_fingerprint(),
        output_columns=_hydrated_frame().columns,
    )
    first = public_player_snapshot.load_public_player_snapshot(
        db_path,
        source_fingerprint=_fingerprint(),
    )
    assert first is not None
    first.frame.loc[0, "name"] = "Mutated"
    second = public_player_snapshot.load_public_player_snapshot(
        db_path,
        source_fingerprint=_fingerprint(),
    )

    assert second is not None
    assert second.frame.loc[0, "name"] == "Fixture One"


def test_real_public_player_snapshot_is_field_for_field_equivalent(tmp_path):
    db_path = tmp_path / "players.db"
    shutil.copyfile(Path("data/players.db"), db_path)
    public_player_snapshot.invalidate_public_player_snapshot(db_path)

    expected = rankings._load_players_without_snapshot(str(db_path))
    fingerprint = rankings.public_player_source_fingerprint(str(db_path))
    rankings._save_players_snapshot(str(db_path), expected, fingerprint)
    actual = rankings._load_players_from_snapshot(str(db_path), fingerprint)

    assert actual is not None
    assert actual.columns.tolist() == expected.columns.tolist()
    assert actual["player_id"].tolist() == expected["player_id"].tolist()
    assert actual["injury_level"].tolist() == expected["injury_level"].tolist()
    assert actual["is_current_fantasy_eligible"].tolist() == expected[
        "is_current_fantasy_eligible"
    ].tolist()
    assert len(actual) == len(expected)
    pd.testing.assert_frame_equal(
        actual,
        expected,
        check_dtype=True,
        check_like=False,
    )


def test_missing_or_failed_snapshot_uses_existing_hydration_fallback():
    source = _hydrated_frame()
    with patch(
        "modules.rankings._load_players_from_snapshot",
        return_value=None,
    ), patch(
        "modules.rankings._load_players_without_snapshot",
        return_value=source,
    ) as fallback, patch(
        "modules.rankings._save_players_snapshot",
    ) as save:
        loaded = rankings._load_players_uncached("missing-fixture.db")

    fallback.assert_called_once_with("missing-fixture.db")
    save.assert_called_once()
    # Hydration now appends the canonical valuation-provenance contract even
    # when the source snapshot itself does not carry those derived columns.
    from modules.valuation_authority import annotate_valuation_authority

    pd.testing.assert_frame_equal(
        loaded,
        annotate_valuation_authority(source),
        check_dtype=True,
    )
