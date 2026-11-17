"""Freshness / completeness report and its hookup to the ops watchdog."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from modules import data_freshness, sleeper

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ops_health_check  # noqa: E402


def _touch(path: Path, age_hours: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    when = time.time() - age_hours * 3600
    os.utime(path, (when, when))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    for spec in data_freshness.DATASETS:
        name = "nflverse_advanced_stats_2026.json" if spec.name == "advanced_stats_nflverse" else spec.path
        _touch(tmp_path / name, 1)
    monkeypatch.setattr(sleeper, "season_stats_completeness", lambda season=None: {"season": 2026, "status": "complete", "expected_through": 10, "missing_weeks": [], "suspect_weeks": [], "age_seconds": 3600.0})
    monkeypatch.setattr(data_freshness, "_in_season", lambda: True)
    return tmp_path


def _by_name(report):
    return {row["name"]: row for row in report["datasets"]}


def test_all_fresh_is_clean(data_dir):
    report = data_freshness.build_report(data_dir=str(data_dir))
    assert report["failing"] == []


def test_a_stopped_sync_fails_in_season_and_only_warns_off_season(data_dir, monkeypatch):
    _touch(data_dir / "fantasycalc_values.csv", 24 * 4)
    assert "values_fantasycalc" in data_freshness.build_report(data_dir=str(data_dir))["failing"]
    monkeypatch.setattr(data_freshness, "_in_season", lambda: False)
    report = data_freshness.build_report(data_dir=str(data_dir))
    assert "values_fantasycalc" not in report["failing"]


def test_missing_file_fails_in_season(data_dir):
    os.remove(data_dir / "depth_chart_snapshots.json")
    assert "depth_charts" in data_freshness.build_report(data_dir=str(data_dir))["failing"]


def test_incomplete_weekly_stats_fail_with_the_missing_weeks(data_dir, monkeypatch):
    monkeypatch.setattr(sleeper, "season_stats_completeness", lambda season=None: {"season": 2026, "status": "incomplete", "expected_through": 10, "missing_weeks": [5, 6], "suspect_weeks": [], "age_seconds": 60.0})
    row = _by_name(data_freshness.build_report(data_dir=str(data_dir)))["weekly_stats"]
    assert row["status"] == "fail" and "[5, 6]" in row["detail"]


def test_truncated_week_payload_is_suspect(data_dir, monkeypatch):
    monkeypatch.setattr(sleeper, "season_stats_completeness", lambda season=None: {"season": 2026, "status": "complete", "expected_through": 10, "missing_weeks": [], "suspect_weeks": [7], "age_seconds": 60.0})
    assert "weekly_stats" in data_freshness.build_report(data_dir=str(data_dir))["failing"]


def test_a_crashing_completeness_check_is_itself_a_failure(data_dir, monkeypatch):
    def boom(season=None):
        raise RuntimeError("x")

    monkeypatch.setattr(sleeper, "season_stats_completeness", boom)
    assert "weekly_stats" in data_freshness.build_report(data_dir=str(data_dir))["failing"]


def test_manifest_flags_a_truncated_completed_week(tmp_path, monkeypatch):
    monkeypatch.setattr(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", str(tmp_path / "sleeper_player_stats_{season}.json"))
    monkeypatch.setattr(sleeper, "expected_stats_weeks", lambda season: 4)
    path = sleeper.PLAYER_STATS_CACHE_TEMPLATE.format(season=2026)
    (tmp_path / "sleeper_player_stats_2026.json").write_text("{}")
    full = {f"p{i}": {"gp": 1} for i in range(200)}
    payloads = [(1, full), (2, full), (3, {"p1": {"gp": 1}}), (4, {})]
    sleeper._write_stats_manifest(path, 2026, range(1, 5), [1, 2, 3, 4], sleeper._week_played_counts(payloads))
    report = sleeper.season_stats_completeness(2026)
    assert report["status"] == "complete" and report["suspect_weeks"] == [3]  # week 4 is in progress: not judged


def test_ops_check_turns_failing_datasets_into_failing_checks():
    body = '{"ok": true, "datasets": [{"name": "weekly_stats", "status": "fail", "detail": "missing weeks [5]"}, {"name": "depth_charts", "status": "warn", "detail": "old"}, {"name": "values_fantasycalc", "status": "ok", "detail": "1h"}]}'
    results = ops_health_check.run_freshness_checks(get=lambda url, headers=None: (200, body, 0.1))
    states = {r["name"]: r["status"] for r in results}
    assert states == {"data_weekly_stats": "fail", "data_depth_charts": "ok", "data_values_fantasycalc": "ok"}
    assert ops_health_check.run_freshness_checks(get=lambda url, headers=None: (500, "", 0.1))[0]["status"] == "fail"
