import json
import os
import time

import pandas as pd

from modules import player_value_history as pvh


def _frame(player_id, dynasty_score, **components):
    row = {"player_id": player_id, "dynasty_score": dynasty_score}
    row.update(components)
    return pd.DataFrame([row])


def test_capture_snapshot_pulls_score_and_known_components():
    frame = _frame(
        "1", 500, market_score=400.0, age_curve_score=300.0, role_score=100.0,
        scarcity_score=50.0, opportunity_score=200.0, production_score=150.0,
    )
    snapshot = pvh.capture_snapshot(frame)
    assert snapshot == {
        "1": {
            "score": 500.0, "market_score": 400.0, "age_curve_score": 300.0,
            "role_score": 100.0, "scarcity_score": 50.0, "opportunity_score": 200.0,
            "production_score": 150.0,
        }
    }


def test_capture_snapshot_handles_empty_and_missing_player_id():
    assert pvh.capture_snapshot(pd.DataFrame()) == {}
    assert pvh.capture_snapshot(pd.DataFrame([{"dynasty_score": 1}])) == {}


def test_diff_snapshots_omits_unchanged_and_new_players():
    previous = {"1": {"score": 500.0}, "2": {"score": 300.0}}
    current = {"1": {"score": 500.0}, "2": {"score": 300.0}, "3": {"score": 999.0}}
    assert pvh.diff_snapshots(previous, current) == []


def test_diff_snapshots_identifies_dominant_market_driver_and_direction():
    previous = {"1": {"score": 500.0, "market_score": 400.0, "age_curve_score": 300.0,
                      "role_score": 100.0, "scarcity_score": 50.0, "opportunity_score": 200.0,
                      "production_score": 150.0}}
    current = {"1": {"score": 680.0, "market_score": 700.0, "age_curve_score": 300.0,
                     "role_score": 100.0, "scarcity_score": 50.0, "opportunity_score": 200.0,
                     "production_score": 150.0}}
    changes = pvh.diff_snapshots(previous, current)
    assert len(changes) == 1
    change = changes[0]
    assert change["player_id"] == "1"
    assert change["previous_score"] == 500
    assert change["current_score"] == 680
    assert change["delta"] == 180
    assert change["driver_factor"] == "market_score"
    assert change["driver_label"] == "Market value"
    assert "Market value increased" in change["reason"]
    assert "180 points" in change["reason"]
    assert "up" in change["reason"]


def test_diff_snapshots_identifies_decreasing_role_driver():
    previous = {"1": {"score": 500.0, "market_score": 400.0, "age_curve_score": 300.0,
                      "role_score": 3800.0, "scarcity_score": 50.0, "opportunity_score": 200.0,
                      "production_score": 150.0}}
    current = {"1": {"score": 470.0, "market_score": 400.0, "age_curve_score": 300.0,
                     "role_score": 1800.0, "scarcity_score": 50.0, "opportunity_score": 200.0,
                     "production_score": 150.0}}
    changes = pvh.diff_snapshots(previous, current)
    assert len(changes) == 1
    change = changes[0]
    assert change["delta"] == -30
    assert change["driver_factor"] == "role_score"
    assert "Depth-chart role decreased" in change["reason"]
    assert "down" in change["reason"]


def test_diff_snapshots_attributes_unexplained_delta_to_other_without_corroboration():
    # Overall score moved but every tracked additive component is unchanged
    # AND there is no risk/injury signal (risk_multiplier, injury_risk_score,
    # non_injury_risk_multiplier) in either snapshot to corroborate an actual
    # injury/availability change. Labeling this "Injury or availability risk"
    # would assert a specific causal claim the data doesn't support, so it
    # must fall back to the honest, generic "Other factors" label instead.
    previous = {"1": {"score": 500.0, "market_score": 400.0, "age_curve_score": 300.0,
                      "role_score": 100.0, "scarcity_score": 50.0, "opportunity_score": 200.0,
                      "production_score": 150.0}}
    current = {"1": {"score": 350.0, "market_score": 400.0, "age_curve_score": 300.0,
                     "role_score": 100.0, "scarcity_score": 50.0, "opportunity_score": 200.0,
                     "production_score": 150.0}}
    changes = pvh.diff_snapshots(previous, current)
    assert changes[0]["driver_factor"] == "other"
    assert changes[0]["driver_label"] == "Other factors"
    assert "Other factors" in changes[0]["reason"]
    assert "risk" not in changes[0]["reason"].lower()
    assert "injury" not in changes[0]["reason"].lower()


def test_diff_snapshots_attributes_unexplained_delta_to_risk_when_corroborated():
    # Same unexplained-residual shape as above, but this time the snapshot
    # also carries rankings.py's real risk/injury fields, and
    # risk_multiplier actually moved between the two snapshots -- a genuine
    # injury/availability-driven swing. Only now is "Injury or availability
    # risk" an accurate, corroborated label.
    previous = {"1": {"score": 500.0, "market_score": 400.0, "age_curve_score": 300.0,
                      "role_score": 100.0, "scarcity_score": 50.0, "opportunity_score": 200.0,
                      "production_score": 150.0, "risk_multiplier": 1.0,
                      "non_injury_risk_multiplier": 1.0, "injury_risk_score": 0.0}}
    current = {"1": {"score": 350.0, "market_score": 400.0, "age_curve_score": 300.0,
                     "role_score": 100.0, "scarcity_score": 50.0, "opportunity_score": 200.0,
                     "production_score": 150.0, "risk_multiplier": 0.72,
                     "non_injury_risk_multiplier": 1.0, "injury_risk_score": 1.0}}
    changes = pvh.diff_snapshots(previous, current)
    assert changes[0]["driver_factor"] == "risk"
    assert "Injury or availability risk" in changes[0]["reason"]


def test_capture_snapshot_pulls_corroboration_columns_when_present():
    frame = _frame(
        "1", 500, market_score=400.0, risk_multiplier=0.72,
        non_injury_risk_multiplier=1.0, injury_risk_score=1.0,
    )
    snapshot = pvh.capture_snapshot(frame)
    assert snapshot["1"]["risk_multiplier"] == 0.72
    assert snapshot["1"]["non_injury_risk_multiplier"] == 1.0
    assert snapshot["1"]["injury_risk_score"] == 1.0


def test_diff_snapshots_sorts_by_absolute_delta_descending_then_player_id():
    previous = {"1": {"score": 100.0}, "2": {"score": 100.0}, "3": {"score": 100.0}}
    current = {"1": {"score": 105.0}, "2": {"score": 50.0}, "3": {"score": 95.0}}
    changes = pvh.diff_snapshots(previous, current)
    assert [c["player_id"] for c in changes] == ["2", "1", "3"]


def test_value_changes_since_last_refresh_full_cycle(tmp_path):
    db_path = tmp_path / "players.db"
    db_path.write_bytes(b"v1")

    frame_a = _frame("1", 500, market_score=400.0)
    first = pvh.value_changes_since_last_refresh(str(db_path), frame_a)
    assert first == []
    assert pvh.history_path(str(db_path)).is_file()

    # Re-reading without any underlying source change must not erase the
    # baseline or diff a snapshot against itself.
    second = pvh.value_changes_since_last_refresh(str(db_path), frame_a)
    assert second == []
    state = json.loads(pvh.history_path(str(db_path)).read_text())
    assert state["snapshot"]["1"]["score"] == 500.0

    # A real refresh: source bytes/mtime change, and the player's score moves.
    db_path.write_bytes(b"v2-longer")
    os.utime(db_path, (time.time() + 5, time.time() + 5))
    frame_b = _frame("1", 650, market_score=600.0)
    third = pvh.value_changes_since_last_refresh(str(db_path), frame_b)
    assert len(third) == 1
    assert third[0]["delta"] == 150
    # Each change carries when the underlying snapshot was actually taken,
    # distinct from "now"/whenever this function happened to be called.
    assert isinstance(third[0]["snapshot_refreshed_at"], str) and third[0]["snapshot_refreshed_at"]

    # Calling again with the same (post-refresh) source returns the same
    # cached diff rather than finding nothing because snapshot == snapshot.
    fourth = pvh.value_changes_since_last_refresh(str(db_path), frame_b)
    assert fourth == third
    # The cached re-read must report the SAME snapshot_refreshed_at as the
    # original refresh -- it reflects when the snapshot was captured, not
    # whenever this second call happened.
    assert fourth[0]["snapshot_refreshed_at"] == third[0]["snapshot_refreshed_at"]


def test_value_changes_since_last_refresh_is_fail_neutral_on_bad_frame(tmp_path):
    db_path = tmp_path / "players.db"
    db_path.write_bytes(b"v1")
    assert pvh.value_changes_since_last_refresh(str(db_path), pd.DataFrame()) == []
    assert pvh.value_changes_since_last_refresh(str(db_path), None) == []


def test_history_path_derives_sidecar_name_next_to_db():
    assert str(pvh.history_path("data/players.db")) == "data/players.value-history.json"
