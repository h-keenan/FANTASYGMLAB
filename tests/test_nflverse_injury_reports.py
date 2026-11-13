from __future__ import annotations

import gzip
import pytest

from modules import nflverse_injury_reports as nir

HEADER = "season,season_type,game_type,team,week,gsis_id,position,full_name,first_name,last_name,report_primary_injury,report_secondary_injury,report_status,practice_primary_injury,practice_secondary_injury,practice_status\n"


def _csv(n=3, season=2025):
    rows = [f"{season},REG,REG,KC,{w},00-000000{w},WR,Name {w},A,B,Knee,,Out,Knee,,Did Not Participate In Practice\n" for w in range(1, n + 1)]
    rows.append(f"{season - 1},REG,REG,KC,1,00-0000099,WR,Old,A,B,,,,,,\n")  # other season dropped
    return HEADER + "".join(rows)


def test_parse_filters_season_sorts_and_maps_sleeper_ids():
    rows = nir.parse_reports(_csv(3), 2025, sleeper_id_for_gsis=lambda g, *a: "S" + g[-1] if g.endswith("1") else None)
    assert [r["week"] for r in rows] == ["1", "2", "3"]
    assert rows[0]["sleeper_id"] == "S1" and rows[1]["sleeper_id"] == ""
    assert rows[0]["practice_status"].startswith("Did Not")


def test_parse_rejects_missing_columns():
    with pytest.raises(nir.InjuryReportError):
        nir.parse_reports("season,week\n2025,1\n", 2025)


def test_serialize_is_deterministic_gzip():
    rows = nir.parse_reports(_csv(3), 2025)
    a, b = nir.serialize(rows), nir.serialize(rows)
    assert a == b
    assert gzip.decompress(a).decode().startswith("season,season_type")


def test_seasons_to_sync_backfills_missing_then_current(tmp_path):
    assert nir.seasons_to_sync(tmp_path, 2024) == [2021, 2022, 2023, 2024]
    nir.report_path(tmp_path, 2022).parent.mkdir(parents=True)
    nir.report_path(tmp_path, 2022).write_bytes(b"x")
    assert nir.seasons_to_sync(tmp_path, 2024) == [2021, 2023, 2024]


def test_sync_season_writes_once_then_noop(tmp_path):
    fetch = lambda s: _csv(3, s)
    r1 = nir.sync_season(tmp_path, 2026, current_season=2026, fetch=fetch)
    assert r1["changed"] and r1["rows"] == 3
    r2 = nir.sync_season(tmp_path, 2026, current_season=2026, fetch=fetch)
    assert not r2["changed"]


def test_sync_season_dry_run_writes_nothing(tmp_path):
    r = nir.sync_season(tmp_path, 2026, current_season=2026, fetch=lambda s: _csv(3, s), dry_run=True)
    assert r["changed"] and not nir.report_path(tmp_path, 2026).exists()


def test_unpublished_current_is_quiet_but_past_is_an_error(tmp_path):
    def missing(s):
        raise nir.NotPublished("404")

    assert nir.sync_season(tmp_path, 2026, current_season=2026, fetch=missing)["status"] == "not_published_yet"
    with pytest.raises(nir.NotPublished):
        nir.sync_season(tmp_path, 2022, current_season=2026, fetch=missing)


def test_completed_season_too_small_and_shrink_guard(tmp_path):
    with pytest.raises(nir.InjuryReportError):
        nir.sync_season(tmp_path, 2022, current_season=2026, fetch=lambda s: _csv(3, s))
    nir.sync_season(tmp_path, 2026, current_season=2026, fetch=lambda s: _csv(10, s))
    with pytest.raises(nir.InjuryReportError):
        nir.sync_season(tmp_path, 2026, current_season=2026, fetch=lambda s: _csv(2, s))
