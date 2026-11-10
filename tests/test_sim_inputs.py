"""RealSimInputs: builds a frozen snapshot from (faked) real sources, read-only."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from modules.sim.analysis import run_world
from modules.sim.inputs import RealSimInputs, normalize_slots
from modules.sim.types import SimInputsError, Strategy

POS_CYCLE = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "WR", "QB"]


def _make_db(path: Path, *, n: int = 200) -> None:
    con = sqlite3.connect(path)
    con.execute(
        "create table players (player_id text, name text, position text, team text, age real, "
        "value real, ppg real, prior_ppg real, injury_status text, active integer)"
    )
    rows = []
    for i in range(n):
        pos = POS_CYCLE[i % len(POS_CYCLE)]
        rows.append((str(1000 + i), f"Player {i}", pos, ["BUF", "MIA", "NE", "DAL"][i % 4], 22 + i % 12,
                     float(9000 - i * 40), 14.0 - i * 0.05, 12.0, "Out" if i == 3 else "", 1))
    rows.append(("D1", "Some Defense", "DEF", "BUF", 0, 5.0, 0, 0, "", 1))
    con.executemany("insert into players values (?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()


class FakeSleeper:
    def __init__(self, *, leg=6, teams=4):
        self.leg = leg
        self.teams = teams

    def get_league(self, league_id):
        return {
            "name": "Fake League", "season": "2026",
            "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "DEF", "BN", "BN", "IR"],
            "scoring_settings": {"rec": 1.0},
            "settings": {"leg": self.leg, "playoff_week_start": 15, "playoff_teams": 2, "trade_deadline": 10},
        }

    def get_rosters(self, league_id):
        out = []
        for r in range(1, self.teams + 1):
            players = [str(1000 + (r - 1) + self.teams * k) for k in range(8)] + ["D1", "MISSING"]
            out.append({"roster_id": r, "owner_id": f"u{r}", "players": players,
                        "settings": {"wins": 3, "losses": 2, "ties": 0, "fpts": 500, "fpts_decimal": 50,
                                     "fpts_against": 480, "fpts_against_decimal": 10}})
        return out

    def get_league_roster_profiles(self, league_id):
        return {str(r): {"team_name": f"Team {r}", "owner_name": f"Owner {r}", "username": f"user{r}"}
                for r in range(1, self.teams + 1)}

    def get_matchups_for_weeks(self, league_id, weeks):
        out = {}
        for w in weeks:
            if w == 7:
                out[w] = []  # a week Sleeper has not published: must be estimated
                continue
            out[w] = [{"roster_id": 1, "matchup_id": 1}, {"roster_id": 2, "matchup_id": 1},
                      {"roster_id": 3, "matchup_id": 2}, {"roster_id": 4, "matchup_id": 2}]
        return out


class FakeProjections:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def baseline_weekly_points(self, rows, *, scoring_settings=None):
        self.calls.append(scoring_settings)
        if self.fail:
            raise RuntimeError("cache unavailable")
        return {r["player_id"]: {"ppg": 15.0, "sd": 5.0} for r in rows if r["player_id"] != "1005"}


class FakePlayoff:
    @staticmethod
    def playoff_bracket_format(settings, playoff_teams, *, playoffs_started=False):
        return {"available": True, "reason": "", "reseed": False}


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "players.db"
    _make_db(path)
    return path


def _inputs(db, **kw):
    return RealSimInputs(
        str(db), sleeper_module=kw.get("sleeper", FakeSleeper()),
        projections_module=kw.get("projections", FakeProjections()), playoff_module=FakePlayoff(),
    )


def test_snapshot_from_real_shaped_sources(db):
    snap = _inputs(db).league_snapshot("L1", mode="remaining", username="USER2")
    assert snap.mode == "remaining"
    assert snap.settings.start_week == 6 and snap.settings.regular_season_end == 14
    assert snap.settings.trade_deadline_week == 10
    assert snap.settings.slots == ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX")
    assert snap.user_team.tid == "2" and snap.user_team.name == "Team 2"
    assert snap.user_team.wins == 3 and snap.user_team.pf == 500.5
    assert len(snap.schedule) == 14 - 6 + 1
    # DEF and unknown ids are not modeled
    assert all(set(t.roster) <= set(snap.players) for t in snap.teams)
    assert "D1" not in snap.players and "MISSING" not in snap.players
    assert snap.free_agents and not set(snap.free_agents) & {p for t in snap.teams for p in t.roster}
    assert "def_idp_slots_not_modeled" in snap.notes
    assert "schedule_estimated_weeks:7" in snap.notes
    assert snap.players["1003"].injury_weeks == 4  # "Out" in the table
    assert all(0 <= p.market <= 100 for p in snap.players.values())
    # projections: used when present, DB ppg fallback otherwise
    assert snap.players["1000"].mean == 15.0 and snap.players["1000"].sd == 5.0
    assert snap.players["1005"].mean > 0
    assert any(n.startswith("projection_fallback_players:") for n in snap.notes)


def test_snapshot_runs_end_to_end_and_round_trips(db):
    snap = _inputs(db).league_snapshot("L1", mode="remaining", username="user1")
    result = run_world(snap, Strategy(), 77)
    assert result["standings"] and result["grade"]["letter"]


def test_full_mode_zeroes_records_and_starts_week_one(db):
    snap = _inputs(db).league_snapshot("L1", mode="full", roster_id="3")
    assert snap.settings.start_week == 1 and snap.user_team.tid == "3"
    assert all(t.wins == 0 and t.pf == 0 for t in snap.teams)


def test_offseason_remaining_falls_back_to_full(db):
    snap = _inputs(db, sleeper=FakeSleeper(leg=0)).league_snapshot("L1", mode="remaining", roster_id="1")
    assert snap.mode == "full" and "offseason_full_season" in snap.notes


def test_completed_season_is_refused(db):
    with pytest.raises(SimInputsError) as exc:
        _inputs(db, sleeper=FakeSleeper(leg=16)).league_snapshot("L1", mode="remaining", roster_id="1")
    assert exc.value.code == "season_complete"


def test_team_not_found_and_bad_mode(db):
    with pytest.raises(SimInputsError) as exc:
        _inputs(db).league_snapshot("L1", username="nobody")
    assert exc.value.code == "team_not_found"
    with pytest.raises(SimInputsError) as exc:
        _inputs(db).league_snapshot("L1", mode="dynasty", roster_id="1")
    assert exc.value.code == "invalid_mode"


def test_projection_failure_degrades_to_table_fallback(db):
    snap = _inputs(db, projections=FakeProjections(fail=True)).league_snapshot("L1", roster_id="1")
    assert all(p.mean > 0 for p in snap.players.values())


def test_league_scoring_is_passed_to_projections(db):
    projections = FakeProjections()
    _inputs(db, projections=projections).league_snapshot("L1", roster_id="1")
    assert projections.calls == [{"rec": 1.0}]


def test_missing_players_db_is_reported(tmp_path):
    with pytest.raises(SimInputsError) as exc:
        RealSimInputs(
            str(tmp_path / "nope.db"), sleeper_module=FakeSleeper(), projections_module=FakeProjections(),
            playoff_module=FakePlayoff(),
        ).league_snapshot("L1", roster_id="1")
    assert exc.value.code == "players_unavailable"


def test_players_db_is_opened_read_only_and_never_modified(db):
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    mtime = db.stat().st_mtime_ns
    _inputs(db).league_snapshot("L1", roster_id="1")
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert db.stat().st_mtime_ns == mtime
    assert not list(db.parent.glob("players.db-*"))  # no journal/wal left behind


def test_normalize_slots():
    assert normalize_slots(["QB", "WRRB_FLEX", "REC_FLEX", "K", "DEF", "DL", "BN", "IR", "TAXI"]) == (
        ("QB", "FLEX", "REC_FLEX", "K"), True)
    assert normalize_slots([]) == (("QB", "RB", "RB", "WR", "WR", "TE", "FLEX"), False)


def test_real_playoff_module_has_the_signature_we_call():
    from modules import playoff_simulator

    fmt = playoff_simulator.playoff_bracket_format({"playoff_type": 0, "playoff_round_type": 0}, 6)
    assert fmt["available"] is True
