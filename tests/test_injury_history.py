from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from modules import injury_history as ih


def _p(status="Active", inj=None, part=None, practice=None, team="KC", pos="WR"):
    return {"status": status, "injury_status": inj, "injury_body_part": part,
            "practice_participation": practice, "practice_description": None, "team": team, "position": pos}


def _dump(extra: dict) -> dict:
    d = {f"filler{i}": _p() for i in range(ih.MIN_PLAYERS_IN_DUMP)}
    d.update(extra)
    return d


def test_is_tracked_requires_team_and_skill_position():
    assert ih.is_tracked(_p())
    assert not ih.is_tracked(_p(team=None))
    assert not ih.is_tracked(_p(pos="LB"))
    assert not ih.is_tracked("junk")


def test_healthy_definition():
    assert ih.player_state(_p()).healthy
    assert not ih.player_state(_p(inj="Questionable")).healthy
    assert not ih.player_state(_p(status="Inactive")).healthy


def test_detect_changes_baseline_change_recovery_and_silence():
    players = {"1": _p(inj="Questionable", part="Knee"), "2": _p(), "3": _p(inj="Out")}
    prev = {"3": ("Active", "Out", "", "")}
    ev = ih.detect_changes(prev, players, captured_at="t", season=2026, week=9)
    assert [e["player_id"] for e in ev] == ["1"]  # 2 healthy+unknown silent, 3 unchanged
    assert ev[0]["body_part"] == "Knee" and ev[0]["week"] == 9

    # status change
    players["1"] = _p(inj="Out", part="Knee")
    ev = ih.detect_changes({"1": ("Active", "Questionable", "Knee", "")}, {"1": players["1"]}, captured_at="t", season=2026, week=9)
    assert len(ev) == 1 and ev[0]["injury_status"] == "Out"

    # recovery recorded as an event with empty injury fields
    ev = ih.detect_changes({"1": ("Active", "Out", "Knee", "")}, {"1": _p()}, captured_at="t", season=2026, week=10)
    assert len(ev) == 1 and ev[0]["injury_status"] == "" and ev[0]["status"] == "Active"

    # practice status change alone is an event
    ev = ih.detect_changes({"1": ("Active", "Questionable", "Knee", "")}, {"1": _p(inj="Questionable", part="Knee", practice="Limited")}, captured_at="t", season=2026, week=10)
    assert len(ev) == 1


def test_no_change_means_no_events():
    players = {"1": _p(inj="Out", part="Knee")}
    prev = ih.last_state_keys([{"player_id": "1", "status": "Active", "injury_status": "Out", "body_part": "Knee", "practice": ""}])
    assert ih.detect_changes(prev, players, captured_at="t", season=2026, week=1) == []


def test_due_snapshot_key_slots_catchup_and_dedupe():
    # Tue 2026-11-10 15:00 UTC: tue slot (14:00) passed
    now = datetime(2026, 11, 10, 15, tzinfo=timezone.utc)
    assert ih.due_snapshot_key(now, []) == "2026-11-10-tue"
    assert ih.due_snapshot_key(now, ["2026-11-10-tue"]) is None
    # before the slot -> nothing (Mon night)
    assert ih.due_snapshot_key(datetime(2026, 11, 10, 13, tzinfo=timezone.utc), []) is None
    # long after the slot: beyond catch-up window, not recorded
    assert ih.due_snapshot_key(datetime(2026, 11, 11, 23, tzinfo=timezone.utc), []) is None
    # Friday slot 21:00
    assert ih.due_snapshot_key(datetime(2026, 11, 13, 22, tzinfo=timezone.utc), []) == "2026-11-13-fri"


def test_in_snapshot_season():
    assert ih.in_snapshot_season(datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert not ih.in_snapshot_season(datetime(2026, 6, 1, tzinfo=timezone.utc))


def test_capture_writes_events_then_is_idempotent_and_snapshots_once(tmp_path: Path):
    now = datetime(2026, 11, 10, 15, tzinfo=timezone.utc)
    players = _dump({"1": _p(inj="Questionable", part="Knee"), "2": _p(inj="Out")})
    s1 = ih.capture(players, tmp_path, now=now, season=2026, week=10, environ={})
    assert s1["events"] == 2 and s1["snapshot_key"] == "2026-11-10-tue" and s1["snapshot_rows"] == 2
    s2 = ih.capture(players, tmp_path, now=now, season=2026, week=10, environ={})
    assert s2["events"] == 0 and s2["snapshot_key"] is None
    assert len(ih.read_rows(ih.events_path(tmp_path, 2026))) == 2
    assert len(ih.read_rows(ih.snapshots_path(tmp_path, 2026))) == 2
    idx = ih.read_rows(ih.index_path(tmp_path))
    assert len(idx) == 1 and idx[0]["tracked_players"] == str(ih.MIN_PLAYERS_IN_DUMP + 2)

    players["2"] = _p()  # recovery
    s3 = ih.capture(players, tmp_path, now=datetime(2026, 11, 10, 16, tzinfo=timezone.utc), season=2026, week=10, environ={})
    assert s3["events"] == 1


def test_capture_carries_state_across_season_files(tmp_path: Path):
    now = datetime(2026, 11, 10, 9, tzinfo=timezone.utc)
    ih.capture(_dump({"1": _p(inj="IR")}), tmp_path, now=now, season=2025, week=None, environ={})
    s = ih.capture(_dump({"1": _p(inj="IR")}), tmp_path, now=now, season=2026, week=None, environ={})
    assert s["events"] == 0  # same state as last recorded in the prior season file


def test_capture_dry_run_disable_and_guards(tmp_path: Path):
    now = datetime(2026, 11, 10, 15, tzinfo=timezone.utc)
    players = _dump({"1": _p(inj="Out")})
    s = ih.capture(players, tmp_path, now=now, season=2026, week=1, dry_run=True, environ={})
    assert s["events"] == 1 and not (tmp_path / ih.HISTORY_DIR).exists()
    s = ih.capture(players, tmp_path, now=now, season=2026, week=1, environ={ih.DISABLE_ENV: "1"})
    assert s["skipped"] == "disabled" and not (tmp_path / ih.HISTORY_DIR).exists()
    s = ih.capture({"1": _p(inj="Out")}, tmp_path, now=now, season=2026, week=1, environ={})
    assert "too small" in s["skipped"] and not (tmp_path / ih.HISTORY_DIR).exists()


def test_capture_sanity_limit_blocks_mass_flip(tmp_path: Path):
    now = datetime(2026, 11, 10, 9, tzinfo=timezone.utc)
    ih.capture(_dump({"1": _p(inj="Out")}), tmp_path, now=now, season=2026, week=1, environ={})
    many = {str(1000 + i): _p(inj="Out") for i in range(ih.MAX_EVENTS_PER_RUN + 10)}
    s = ih.capture(_dump(many), tmp_path, now=now, season=2026, week=1, environ={})
    assert "sanity limit" in s["skipped"]


def test_csv_roundtrip_header_only_once(tmp_path: Path):
    path = tmp_path / "x.csv"
    ih.append_rows(path, [{"player_id": "1", "injury_status": "Out, ankle"}], ih.EVENT_COLUMNS)
    ih.append_rows(path, [{"player_id": "2"}], ih.EVENT_COLUMNS)
    rows = ih.read_rows(path)
    assert [r["player_id"] for r in rows] == ["1", "2"] and rows[0]["injury_status"] == "Out, ankle"
    assert path.read_text().count("captured_at") == 1
