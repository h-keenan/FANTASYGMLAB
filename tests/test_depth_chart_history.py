from __future__ import annotations

import pandas as pd

from modules import depth_chart_history


def _players_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_first_ever_run_has_no_deltas_and_persists_a_snapshot(tmp_path):
    path = str(tmp_path / "snapshots.json")
    df = _players_df(
        [
            {"player_id": "p1", "depth_chart_order": 1, "depth_chart_position": "RB"},
            {"player_id": "p2", "depth_chart_order": 2, "depth_chart_position": "RB"},
            {"player_id": "p3", "depth_chart_order": 0, "depth_chart_position": ""},
        ]
    )

    out = depth_chart_history.record_depth_chart_snapshot(df, path=path, week_key="2026-W01")

    assert (out["depth_chart_order_delta"] == 0).all()
    snapshots = depth_chart_history.load_depth_chart_snapshots(path)
    assert snapshots["2026-W01"] == {"p1": 1, "p2": 2}
    # p3 (order 0 -- not on a depth chart at all) is never recorded.
    assert "p3" not in snapshots["2026-W01"]


def test_a_real_promotion_shows_a_positive_delta(tmp_path):
    path = str(tmp_path / "snapshots.json")
    week1 = _players_df([{"player_id": "backup", "depth_chart_order": 2, "depth_chart_position": "QB"}])
    depth_chart_history.record_depth_chart_snapshot(week1, path=path, week_key="2026-W01")

    # coridian_'s scenario: a backup moves from #2 to #1 on the depth chart.
    week2 = _players_df([{"player_id": "backup", "depth_chart_order": 1, "depth_chart_position": "QB"}])
    out = depth_chart_history.record_depth_chart_snapshot(week2, path=path, week_key="2026-W02")

    row = out[out["player_id"] == "backup"].iloc[0]
    assert row["depth_chart_order_delta"] == 1


def test_a_demotion_shows_a_negative_delta(tmp_path):
    path = str(tmp_path / "snapshots.json")
    week1 = _players_df([{"player_id": "starter", "depth_chart_order": 1, "depth_chart_position": "WR"}])
    depth_chart_history.record_depth_chart_snapshot(week1, path=path, week_key="2026-W01")

    week2 = _players_df([{"player_id": "starter", "depth_chart_order": 3, "depth_chart_position": "WR"}])
    out = depth_chart_history.record_depth_chart_snapshot(week2, path=path, week_key="2026-W02")

    row = out[out["player_id"] == "starter"].iloc[0]
    assert row["depth_chart_order_delta"] == -2


def test_a_player_entering_the_depth_chart_for_the_first_time_has_no_fake_delta(tmp_path):
    """No prior recorded order (order was 0, i.e. off the depth chart
    entirely, or genuinely new) means nothing real to diff against -- 0,
    not a fabricated jump."""
    path = str(tmp_path / "snapshots.json")
    week1 = _players_df([{"player_id": "p1", "depth_chart_order": 0, "depth_chart_position": ""}])
    depth_chart_history.record_depth_chart_snapshot(week1, path=path, week_key="2026-W01")

    week2 = _players_df([{"player_id": "p1", "depth_chart_order": 1, "depth_chart_position": "RB"}])
    out = depth_chart_history.record_depth_chart_snapshot(week2, path=path, week_key="2026-W02")

    assert out.iloc[0]["depth_chart_order_delta"] == 0


def test_only_the_most_recent_prior_week_is_used_for_comparison(tmp_path):
    path = str(tmp_path / "snapshots.json")
    depth_chart_history.record_depth_chart_snapshot(
        _players_df([{"player_id": "p1", "depth_chart_order": 3, "depth_chart_position": "RB"}]),
        path=path,
        week_key="2026-W01",
    )
    depth_chart_history.record_depth_chart_snapshot(
        _players_df([{"player_id": "p1", "depth_chart_order": 2, "depth_chart_position": "RB"}]),
        path=path,
        week_key="2026-W02",
    )
    out = depth_chart_history.record_depth_chart_snapshot(
        _players_df([{"player_id": "p1", "depth_chart_order": 1, "depth_chart_position": "RB"}]),
        path=path,
        week_key="2026-W03",
    )

    # Delta vs. the immediately preceding week (2 -> 1), not the oldest (3 -> 1).
    assert out.iloc[0]["depth_chart_order_delta"] == 1


def test_multiple_runs_in_the_same_week_only_keep_the_latest_value_for_that_week(tmp_path):
    path = str(tmp_path / "snapshots.json")
    depth_chart_history.record_depth_chart_snapshot(
        _players_df([{"player_id": "p1", "depth_chart_order": 2, "depth_chart_position": "RB"}]),
        path=path,
        week_key="2026-W01",
    )
    # Two refreshes within the same week (the real cron runs every 6h).
    depth_chart_history.record_depth_chart_snapshot(
        _players_df([{"player_id": "p1", "depth_chart_order": 2, "depth_chart_position": "RB"}]),
        path=path,
        week_key="2026-W02",
    )
    depth_chart_history.record_depth_chart_snapshot(
        _players_df([{"player_id": "p1", "depth_chart_order": 1, "depth_chart_position": "RB"}]),
        path=path,
        week_key="2026-W02",
    )

    snapshots = depth_chart_history.load_depth_chart_snapshots(path)
    assert snapshots["2026-W02"] == {"p1": 1}


def test_retains_only_the_most_recent_weeks(tmp_path):
    path = str(tmp_path / "snapshots.json")
    for week in range(1, 13):
        week_key = f"2026-W{week:02d}"
        depth_chart_history.record_depth_chart_snapshot(
            _players_df([{"player_id": "p1", "depth_chart_order": 1, "depth_chart_position": "RB"}]),
            path=path,
            week_key=week_key,
        )

    snapshots = depth_chart_history.load_depth_chart_snapshots(path)
    assert len(snapshots) == depth_chart_history.RETAINED_WEEKS
    assert "2026-W12" in snapshots
    assert "2026-W01" not in snapshots


def test_corrupt_snapshot_file_is_treated_as_empty_history(tmp_path):
    path = tmp_path / "snapshots.json"
    path.write_text("not valid json{{{")

    df = _players_df([{"player_id": "p1", "depth_chart_order": 1, "depth_chart_position": "RB"}])
    out = depth_chart_history.record_depth_chart_snapshot(df, path=str(path), week_key="2026-W01")

    assert out.iloc[0]["depth_chart_order_delta"] == 0


def test_empty_players_frame_returns_the_column_with_no_error(tmp_path):
    path = str(tmp_path / "snapshots.json")
    out = depth_chart_history.record_depth_chart_snapshot(pd.DataFrame(), path=path)
    assert "depth_chart_order_delta" in out.columns
    assert out.empty
