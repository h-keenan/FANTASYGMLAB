"""League settings and start modes of the GM game: size, scoring, TE premium,
superflex, K/DEF toggles, bench, redraft/dynasty modes, and starting from a
real league's rosters (read-only, through the sim's input door)."""

from __future__ import annotations

import csv
import dataclasses

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from modules.sim import api as sim_api
from modules.sim import game_actions as act
from modules.sim import game_scoring
from modules.sim.game_ai import TradeDesk, validate_offer
from modules.sim.game_draft import DraftContext, auto_for_user, flex_shortage, run_ai_picks, starter_shortage
from modules.sim.game_engine import advance, finish_draft, start_from_league
from modules.sim.game_eval import Evaluator
from modules.sim.game_mode import LEGACY_POLICY, policy_for
from modules.sim.game_result import build_result, replay_game
from modules.sim.game_setup import build_league_snapshot, build_snapshot, finalize_pool, league_settings
from modules.sim.game_state import Emitter, GameState, fold
from modules.sim.game_types import (
    GameSettings,
    GameSnapshot,
    ImportedTeam,
    LeagueImport,
    derive_layout,
)
from modules.sim.inputs import DEF_PREFIX, PlayerPool, RealSimInputs, import_slots
from modules.sim.store import InMemoryBackend
from modules.sim.synthetic import build_synthetic_pool
from modules.sim.types import SimInputsError

ROWS, BYES = build_synthetic_pool(7)
MODEL = game_scoring.default_model().model_id


def snapshot(seed=11, **settings):
    return build_snapshot(ROWS, BYES, GameSettings.parse({"user_slot": 4, **settings}), seed, scoring_model=MODEL)


def play_draft(snap, seed=11):
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, seed)
    auto_for_user(ctx, em, seed)
    finish_draft(em, snap, state, seed)
    return state, em


# ------------------------------------------------------------------ settings


def test_quick_start_defaults_are_twelve_teams_half_ppr_standard_lineup():
    s = GameSettings.parse({})
    assert (s.teams, s.scoring, s.te_premium, s.superflex, s.include_k, s.include_def) == (12, "half", 0.0, False, True, False)
    assert s.slots == ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K")
    assert (s.bench, s.roster_limit, s.rounds, s.mode) == (8, 16, 14, "redraft")
    assert s.scoring_settings["rec"] == 0.5 and "bonus_rec_te" not in s.scoring_settings


@pytest.mark.parametrize("superflex,k,d,bench,slots,limit,rounds", [
    (False, True, False, 8, 8, 16, 14),
    (True, True, False, 8, 9, 17, 15),
    (True, False, True, 6, 9, 15, 13),
    (False, False, False, 4, 7, 11, 9),
    (True, True, True, 10, 10, 20, 18),
])
def test_layout_is_derived_from_the_toggles(superflex, k, d, bench, slots, limit, rounds):
    got = derive_layout(superflex=superflex, include_k=k, include_def=d, bench=bench)
    assert (len(got[0]), got[1], got[2]) == (slots, limit, rounds)
    assert ("SUPER_FLEX" in got[0], "K" in got[0], "DEF" in got[0]) == (superflex, k, d)
    parsed = GameSettings.parse({"superflex": superflex, "include_k": k, "include_def": d, "bench": bench})
    assert (parsed.slots, parsed.roster_limit, parsed.rounds) == got


@pytest.mark.parametrize("bad", [
    {"teams": 9}, {"teams": 16}, {"teams": True}, {"scoring": "nope"}, {"te_premium": 0.25}, {"te_premium": True},
    {"superflex": "yes"}, {"include_def": 1}, {"include_k": None}, {"bench": 3}, {"bench": 11}, {"bench": 8.5},
    {"mode": "keeper"}, {"mode": "dynasty"}, {"difficulty": "brutal"}, {"user_slot": 13}, {"auto_lineup": "x"},
])
def test_invalid_settings_are_rejected(bad):
    with pytest.raises(ValueError):
        GameSettings.parse(bad)


def test_te_premium_flows_into_the_scoring_the_pool_is_projected_in():
    assert GameSettings.parse({"te_premium": 0.5}).scoring_settings["bonus_rec_te"] == 0.5
    assert GameSettings.parse({"scoring": "std", "te_premium": 1.0}).scoring_settings["rec"] == 0.0


def test_settings_round_trip_and_old_saves_load_with_inferred_new_fields():
    s = GameSettings.parse({"teams": 14, "scoring": "std", "te_premium": 0.5, "superflex": True,
                            "include_def": True, "bench": 6, "difficulty": "hard"})
    assert GameSettings.from_dict(s.to_dict()) == s
    old = {"teams": 12, "scoring": "ppr", "difficulty": "normal", "user_slot": 3, "auto_lineup": False,
           "slots": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K"], "rounds": 14, "roster_limit": 16,
           "regular_weeks": 14, "playoff_teams": 6, "playoff_weeks": 3, "trade_deadline_week": 10}
    legacy = GameSettings.from_dict(old)
    assert (legacy.mode, legacy.superflex, legacy.include_k, legacy.include_def, legacy.bench) == ("redraft", False, True, False, 8)
    assert legacy.rules == 1 and legacy.policy is LEGACY_POLICY and legacy.scoring_settings["rec"] == 1.0


def test_modes_are_extensible_and_dynasty_is_declared_but_not_playable():
    assert policy_for("redraft").season_valuation and policy_for("redraft").available
    assert not policy_for("dynasty").available and not policy_for("dynasty").season_valuation
    assert not policy_for("redraft", rules=1).season_valuation


# ---------------------------------------------------------------------- pool


def test_pool_only_has_the_positions_the_league_plays():
    base = finalize_pool(ROWS, GameSettings.parse({}))
    assert {p.pos for p in base.values()} == {"QB", "RB", "WR", "TE", "K"}
    no_k = finalize_pool(ROWS, GameSettings.parse({"include_k": False}))
    assert {p.pos for p in no_k.values()} == {"QB", "RB", "WR", "TE"}
    with_def = finalize_pool(ROWS, GameSettings.parse({"include_def": True}))
    assert sum(p.pos == "DEF" for p in with_def.values()) == 32


def test_superflex_makes_quarterbacks_more_valuable_in_the_draft_value():
    one = finalize_pool(ROWS, GameSettings.parse({}))
    sf = finalize_pool(ROWS, GameSettings.parse({"superflex": True}))
    qb = lambda pool: sorted((p.value for p in pool.values() if p.pos == "QB"), reverse=True)[:12]  # noqa: E731
    assert sum(qb(sf)) > sum(qb(one))
    best_adp = lambda pool: min(p.adp for p in pool.values() if p.pos == "QB")  # noqa: E731
    assert best_adp(sf) <= best_adp(one)


def test_a_def_league_without_defenses_in_the_pool_is_unavailable_not_invented():
    rows = [r for r in ROWS if r["pos"] != "DEF"]
    with pytest.raises(SimInputsError) as err:
        build_snapshot(rows, BYES, GameSettings.parse({"include_def": True}), 3)
    assert err.value.code == "def_unavailable"


# -------------------------------------------------------------- draft + play


def test_flex_shortage_counts_superflex_and_each_flex_kind():
    slots = ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "K")
    nothing = {"QB": 0, "RB": 0, "WR": 0, "TE": 0}
    assert flex_shortage(slots, nothing)[0] == 2
    assert flex_shortage(slots, {"QB": 2, "RB": 2, "WR": 2, "TE": 1})[0] == 1  # a second QB fills the superflex
    assert flex_shortage(slots, {"QB": 2, "RB": 3, "WR": 2, "TE": 1})[0] == 0
    assert flex_shortage(("QB", "FLEX"), {"QB": 5})[0] == 1  # extra QBs never fill a plain flex
    assert starter_shortage(slots, {"QB": 1})["FLEX"] == 2.0 and starter_shortage(slots, {})["K"] == 1.0


@pytest.mark.parametrize("opts", [
    {"teams": 14, "superflex": True, "include_def": True, "bench": 6, "scoring": "std", "te_premium": 1.0},
    {"teams": 8, "include_k": False, "bench": 10, "scoring": "ppr"},
    {"teams": 10, "superflex": True, "include_k": False, "include_def": True},
])
def test_the_engine_honors_every_setting_from_draft_through_the_playoffs(opts):
    seed = 5
    snap = snapshot(seed, **opts)
    s = snap.settings
    assert len(snap.teams) == s.teams
    state, em = play_draft(snap, seed)
    for tid, roster in state.rosters.items():
        assert len(roster) == s.rounds
        positions = [snap.players[p].pos for p in roster]
        assert positions.count("K") == (1 if s.include_k else 0)
        assert positions.count("DEF") == (1 if s.include_def else 0)
        assert sum(pos == "QB" for pos in positions) >= 1
        rows = state.lineups[tid]
        assert [r[0] for r in rows] == list(s.slots) and all(r[1] for r in rows)
    if s.superflex:  # superflex leagues carry more quarterbacks than the same league without it
        plain = snapshot(seed, **{**opts, "superflex": False})
        plain_state, _ = play_draft(plain, seed)
        qbs = lambda sn, st: sum(sn.players[p].pos == "QB" for r in st.rosters.values() for p in r)  # noqa: E731
        assert qbs(snap, state) / s.teams > qbs(plain, plain_state) / plain.settings.teams
    while state.status != "complete":
        advance(em, snap, state, seed)
    assert state.champion in snap.tids
    assert len(state.history) == s.regular_weeks + s.playoff_weeks
    assert all(len(r) <= s.roster_limit for r in state.rosters.values())
    # resume == replay with the new settings in play
    assert fold(snap, em.events).digest() == state.digest()


def test_kickers_and_defenses_cannot_be_traded():
    snap = snapshot(3, include_def=True)
    state, _ = play_draft(snap, 3)
    user = snap.user_team.tid
    partner = next(t for t in snap.tids if t != user)
    mine = [p for p in state.rosters[user] if snap.players[p].pos == "DEF"][0]
    theirs = [p for p in state.rosters[partner] if snap.players[p].pos not in ("K", "DEF")][0]
    with pytest.raises(ValueError, match="cannot be traded"):
        validate_offer(snap, state, partner, [mine], [theirs])
    their_def = [p for p in state.rosters[partner] if snap.players[p].pos == "DEF"][0]
    mine2 = [p for p in state.rosters[user] if snap.players[p].pos not in ("K", "DEF")][0]
    with pytest.raises(ValueError, match="cannot be traded"):
        validate_offer(snap, state, partner, [mine2], [their_def])


def test_redraft_values_players_by_this_seasons_value_and_ignores_age():
    snap = snapshot(3)
    state, _ = play_draft(snap, 3)
    ev = Evaluator(snap, state)
    assert ev.policy.season_valuation
    team = next(t for t in snap.teams if not t.is_user)
    from modules.sim.game_eval import team_params
    params = team_params(snap, team.tid)
    pid = max(snap.players, key=lambda p: snap.players[p].value)
    young = dataclasses.replace(snap.players[pid], age=22.0)
    old = dataclasses.replace(snap.players[pid], age=34.0)
    snap.players  # frozen mapping reference check
    a = Evaluator(dataclasses.replace(snap, players={**snap.players, pid: young}), state)
    b = Evaluator(dataclasses.replace(snap, players={**snap.players, pid: old}), state)
    assert a.worth(params, pid) == pytest.approx(b.worth(params, pid))


def test_legacy_saves_keep_the_market_and_age_valuation():
    snap = snapshot(3)
    legacy = dataclasses.replace(snap, settings=dataclasses.replace(snap.settings, rules=1))
    state = GameState(legacy)
    ev = Evaluator(legacy, state)
    assert not ev.policy.season_valuation
    from modules.sim.game_eval import team_params
    team = next(t for t in legacy.teams if not t.is_user)
    params = team_params(legacy, team.tid)
    pid = next(iter(legacy.players))
    young = dataclasses.replace(legacy.players[pid], age=22.0)
    old = dataclasses.replace(legacy.players[pid], age=36.0)
    wy = Evaluator(dataclasses.replace(legacy, players={**legacy.players, pid: young}), state).worth(params, pid)
    wo = Evaluator(dataclasses.replace(legacy, players={**legacy.players, pid: old}), state).worth(params, pid)
    assert wy > wo


# ------------------------------------------------------------- league import


def imported_league(teams=12, user=3, *, slots=("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "K", "DEF"),
                    bench=6, scoring=None, rows=ROWS):
    by_pos: dict[str, list[str]] = {}
    for r in sorted(rows, key=lambda r: -r["market"]):
        by_pos.setdefault(r["pos"], []).append(r["pid"])
    need = {"QB": 2, "RB": 5, "WR": 5, "TE": 2, "K": 1, "DEF": 1}
    rosters: dict[int, list[str]] = {i: [] for i in range(teams)}
    for pos, count in need.items():
        pool = by_pos[pos]
        for i in range(teams):
            rosters[i].extend(pool[i * count:(i + 1) * count])
    return LeagueImport(
        league_id="L1", league_name="My League", season="2026",
        teams=tuple(ImportedTeam(tid=str(100 + i), name=f"Team {i}", owner=f"Owner {i}", is_user=i == user,
                                 roster=tuple(rosters[i])) for i in range(teams)),
        slots=slots, bench=bench, scoring_settings=scoring or {"rec": 1.0, "pass_td": 4.0, "bonus_rec_te": 0.5},
        playoff_teams=6, notes=("n1",),
    )


def league_snapshot(seed=7, **kw):
    imp = imported_league(**kw)
    settings = league_settings(imp, difficulty="normal", auto_lineup=False)
    return imp, build_league_snapshot(ROWS, BYES, imp, settings, seed, scoring_model=MODEL)


def test_league_settings_mirror_the_real_league():
    imp, snap = league_snapshot()
    s = snap.settings
    assert (s.teams, s.start, s.regular_weeks, s.superflex, s.include_k, s.include_def) == (12, "league", 14, True, True, True)
    assert s.slots == imp.slots and s.te_premium == 0.5 and s.scoring == "ppr"
    assert s.scoring_settings == {"rec": 1.0, "pass_td": 4.0, "bonus_rec_te": 0.5}
    assert s.roster_limit >= max(len(t.roster) for t in imp.teams) and s.bench == s.roster_limit - len(s.slots)
    assert snap.user_team.tid == "103" and snap.user_team.name == "Team 3"
    assert GameSnapshot.from_dict(snap.to_dict()).to_dict() == snap.to_dict()


def test_a_league_game_starts_in_week_one_with_the_real_rosters_and_plays_a_full_season():
    imp, snap = league_snapshot()
    state = GameState(snap)
    em = Emitter(state, snap)
    start_from_league(em, snap, state, 7)
    assert state.status == "in_season" and state.week == 1 and not state.picks
    for t in imp.teams:
        assert sorted(state.rosters[t.tid]) == sorted(t.roster)
        assert [r[0] for r in state.lineups[t.tid]] == list(snap.settings.slots)
    assert state.boundary_seq == state.seq
    while state.status != "complete":
        advance(em, snap, state, 7)
    assert len(state.history) == 14 + snap.settings.playoff_weeks and state.champion
    assert fold(snap, em.events).digest() == state.digest()
    # replay from the user's commands reproduces the same season
    assert replay_game(snap, 7, em.events, strict=True).digest() == state.digest()
    result = build_result(snap, 7, em.events, state, explain=False)
    assert result["champion"]["team_id"] == state.champion and result["draft"]["grade"]


def test_league_players_the_pool_cannot_project_are_dropped_and_counted():
    imp = imported_league()
    ghost = dataclasses.replace(imp.teams[0], roster=imp.teams[0].roster + ("not-a-player",))
    imp = dataclasses.replace(imp, teams=(ghost,) + imp.teams[1:])
    settings = league_settings(imp, difficulty="normal", auto_lineup=False)
    snap = build_league_snapshot(ROWS, BYES, imp, settings, 7)
    assert "not-a-player" not in snap.start_rosters[ghost.tid]
    assert "roster_players_not_projected:1" in snap.notes and "n1" in snap.notes


def test_rostered_players_survive_the_pool_cap():
    imp = imported_league(teams=4, user=0)
    deep = max((r for r in ROWS if r["pos"] == "QB"), key=lambda r: -int(r["pid"][1:]))  # a deep-bench QB
    t0 = dataclasses.replace(imp.teams[0], roster=imp.teams[0].roster + (deep["pid"],))
    imp = dataclasses.replace(imp, teams=(t0,) + imp.teams[1:])
    settings = league_settings(imp, difficulty="normal", auto_lineup=False)
    snap = build_league_snapshot(ROWS, BYES, imp, settings, 7)
    assert deep["pid"] in snap.players and deep["pid"] in snap.start_rosters[t0.tid]


# ----------------------------------------------------------- the input door


class FakeSleeper:
    def __init__(self, rosters=None, positions=None, league=None):
        self.calls = []
        self._rosters = rosters if rosters is not None else [
            {"roster_id": i, "players": [f"p{i}a", f"p{i}b", "SF", "LA"], "taxi": [f"p{i}b"]} for i in range(1, 13)
        ]
        self._positions = positions or ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "WRRB_FLEX", "SUPER_FLEX", "K", "DEF",
                                         "DL", "BN", "BN", "BN", "IR"]
        self._league = league

    def get_league(self, league_id):
        self.calls.append("league")
        if self._league is not None:
            return self._league
        return {"name": "L", "season": "2026", "roster_positions": self._positions,
                "scoring_settings": {"rec": 0.5, "pass_td": 4, "bonus_rec_te": 0.5},
                "settings": {"playoff_teams": 4}}

    def get_rosters(self, league_id):
        return self._rosters

    def get_league_roster_profiles(self, league_id):
        return {str(r["roster_id"]): {"team_name": f"T{r['roster_id']}", "owner_name": f"O{r['roster_id']}",
                                      "username": f"user{r['roster_id']}"} for r in self._rosters}


def real_inputs(sleeper, **kw):
    return RealSimInputs("data/none.db", games_csv_path=kw.pop("csv", "data/none.csv"), sleeper_module=sleeper,
                         projections_module=object(), playoff_module=object())


def test_import_slots_maps_flex_kinds_bench_and_ignores_idp_ir_taxi():
    slots, bench, ignored = import_slots(["QB", "RB", "WRRB_FLEX", "SUPER_FLEX", "REC_FLEX", "K", "DEF", "DL", "BN", "BN", "IR", "TAXI"])
    assert slots == ("QB", "RB", "FLEX", "SUPER_FLEX", "REC_FLEX", "K", "DEF") and bench == 2 and ignored is True
    assert import_slots(["BN"]) == ((), 1, False)


def test_league_import_reads_settings_and_rosters_without_writing():
    sleeper = FakeSleeper()
    imp = real_inputs(sleeper).league_import("L1", username="USER3")
    assert [t.is_user for t in imp.teams].index(True) == 2 and len(imp.teams) == 12
    assert imp.slots == ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "SUPER_FLEX", "K", "DEF") and imp.bench == 3
    assert "idp_slots_not_modeled" in imp.notes and imp.playoff_teams == 4 and imp.scoring_settings["bonus_rec_te"] == 0.5
    first = imp.teams[0].roster
    assert first == tuple(sorted(("p1a", DEF_PREFIX + "SF", DEF_PREFIX + "LAR")))  # taxi dropped, DEF ids mapped
    assert sleeper.calls == ["league"]  # reads only


@pytest.mark.parametrize("kwargs,code", [
    ({"rosters": [{"roster_id": i, "players": []} for i in range(1, 12)]}, "league_size_unsupported"),
    ({"positions": ["BN", "DL"]}, "league_lineup_unsupported"),
    ({"league": {"name": "L", "roster_positions": ["QB"], "scoring_settings": {}}}, "league_scoring_unavailable"),
    ({"league": {}}, "league_unavailable"),
])
def test_league_import_refuses_what_it_cannot_model(kwargs, code):
    with pytest.raises(SimInputsError) as err:
        real_inputs(FakeSleeper(**kwargs)).league_import("L1", username="user1")
    assert err.value.code == code


def test_league_import_needs_to_know_which_team_is_yours():
    with pytest.raises(SimInputsError) as err:
        real_inputs(FakeSleeper()).league_import("L1", username="nobody")
    assert err.value.code == "team_not_found"
    imp = real_inputs(FakeSleeper()).league_import("L1", username="", roster_id="5")
    assert next(t for t in imp.teams if t.is_user).tid == "5"


def test_defense_rows_come_from_points_allowed_and_are_absent_without_a_schedule(tmp_path):
    teams = ["ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS".split()][0]
    path = tmp_path / "games.csv"
    with path.open("w", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=["season", "game_type", "week", "away_team", "away_score", "home_team", "home_score"])
        w.writeheader()
        for week in range(1, 9):
            for i in range(0, 32, 2):
                home, away = teams[i], teams[i + 1]
                # ARI allows 3 a game, ATL allows 40: a clear best and worst defense; the rest allow 20
                w.writerow({"season": 2026, "game_type": "REG", "week": week, "away_team": away,
                            "away_score": 3 if i == 0 else 20, "home_team": home, "home_score": 40 if i == 0 else 20})
        w.writerow({"season": 2026, "game_type": "REG", "week": 9, "away_team": "ARI", "away_score": "", "home_team": "ATL", "home_score": ""})
    inputs = RealSimInputs("x", games_csv_path=str(path), sleeper_module=object(), projections_module=object(), playoff_module=object())
    rows = {r["nfl_team"]: r for r in inputs._defense_rows()}
    assert len(rows) == 32 and all(r["pos"] == "DEF" and 3.0 <= r["mean"] <= 12.0 for r in rows.values())
    assert rows["ARI"]["mean"] > rows["ATL"]["mean"] and rows["ARI"]["pid"] == "DEF-ARI"
    empty = RealSimInputs("x", games_csv_path=str(tmp_path / "missing.csv"), sleeper_module=object(),
                          projections_module=object(), playoff_module=object())
    assert empty._defense_rows() == []


# ----------------------------------------------------------------------- API


class Inputs:
    def __init__(self, imported=None, error=None):
        self.pool_calls: list[dict] = []
        self.imported = imported
        self.error = error
        self.import_args = None

    def league_snapshot(self, *a, **k):  # pragma: no cover
        raise AssertionError

    def player_pool(self, scoring):
        self.pool_calls.append(dict(scoring))
        return PlayerPool(ROWS, BYES)

    def league_import(self, league_id, *, username="", roster_id=""):
        self.import_args = (league_id, username, roster_id)
        if self.error:
            raise SimInputsError(self.error)
        return self.imported


def make_app(inputs):
    backend = InMemoryBackend()

    def require_user(authorization: str | None = Header(default=None)):
        if not authorization:
            raise HTTPException(status_code=401, detail="no")
        return {"id": authorization, "_access_token": "tok"}

    app = FastAPI()
    sim_api.mount(app, sim_api.SimApiDeps(
        require_user=require_user, is_pro=lambda u: True, sleeper_username=lambda u: "turbo",
        backend_for=lambda u: backend, inputs=inputs), environ={"SIM_ENABLED": "1"})
    return TestClient(app), backend


H = {"Authorization": "pro"}


def test_options_expose_quick_start_defaults_advanced_options_and_start_modes():
    from modules.sim import game_api
    game_api.clear_pool_cache()
    client, _ = make_app(Inputs(imported_league()))
    data = client.get("/v1/sim/games/options", headers=H).json()
    o = data["options"]
    assert (o["teams"]["default"], o["scoring"]["default"], o["te_premium"]["values"]) == (12, "half", [0.0, 0.5, 1.0])
    assert o["teams"]["values"] == [8, 10, 12, 14] and o["mode"]["values"] == ["redraft"]
    assert (o["bench"]["min"], o["bench"]["max"], o["bench"]["default"]) == (4, 10, 8)
    assert o["superflex"]["default"] is False and o["include_k"]["default"] is True and o["include_def"]["default"] is False
    assert data["layout"] == {"base_slots": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"], "draft_spare_spots": 2}
    modes = {m["id"]: m for m in data["start_modes"]}
    assert modes["fresh"]["available"] and modes["league"]["available"]
    assert modes["season_start"] == {"id": "season_start", "available": False, "reason": "no_roster_history"}
    assert {p["id"] for p in data["personas"]} >= {"contender", "rebuilder"}


def test_create_with_advanced_options_saves_them_and_projects_in_that_scoring():
    from modules.sim import game_api
    game_api.clear_pool_cache()
    inputs = Inputs()
    client, _ = make_app(inputs)
    res = client.post("/v1/sim/games", json={"teams": 14, "scoring": "std", "te_premium": 0.5, "superflex": True,
                                             "include_def": True, "bench": 6, "user_slot": 2}, headers=H).json()
    s = res["game"]["settings"]
    assert (s["teams"], s["scoring"], s["te_premium"], s["superflex"], s["include_def"], s["bench"]) == (14, "std", 0.5, True, True, 6)
    assert s["slots"][-3:] == ["SUPER_FLEX", "K", "DEF"] and s["rounds"] == 14 and s["roster_limit"] == 16
    assert res["draft"]["total_picks"] == 14 * 14
    assert inputs.pool_calls[-1]["rec"] == 0.0 and inputs.pool_calls[-1]["bonus_rec_te"] == 0.5
    reloaded = client.get(f"/v1/sim/games/{res['game']['id']}", headers=H).json()["game"]["settings"]
    assert reloaded == s
    bad = client.post("/v1/sim/games", json={"teams": 9}, headers=H)
    assert bad.status_code == 422
    assert client.post("/v1/sim/games", json={"mode": "dynasty"}, headers=H).status_code == 422


def test_pool_cache_is_keyed_by_the_full_scoring_not_just_the_preset():
    from modules.sim import game_api
    game_api.clear_pool_cache()
    inputs = Inputs()
    client, _ = make_app(inputs)
    for body in ({"scoring": "half"}, {"scoring": "half"}, {"scoring": "half", "te_premium": 0.5}):
        client.delete(f"/v1/sim/games/{client.post('/v1/sim/games', json=body, headers=H).json()['game']['id']}", headers=H)
    assert [c.get("bonus_rec_te") for c in inputs.pool_calls] == [None, 0.5]


def test_start_from_one_of_my_leagues_through_the_api():
    from modules.sim import game_api
    game_api.clear_pool_cache()
    imp = imported_league()
    inputs = Inputs(imp)
    client, backend = make_app(inputs)
    res = client.post("/v1/sim/games", json={"start": "league", "league_id": "L1", "difficulty": "hard",
                                             "team_name": "Renamed", "teams": 8}, headers=H).json()
    assert res["reason"] == "" and "draft" not in res
    g = res["game"]
    assert g["status"] == "in_season" and g["week"] == 1 and g["phase"] == "regular_season"
    assert g["settings"]["teams"] == 12 and g["settings"]["start"] == "league" and g["settings"]["difficulty"] == "hard"
    assert g["you"]["name"] == "Renamed" and g["you"]["team_id"] == "103"
    assert inputs.import_args == ("L1", "turbo", "")
    assert inputs.pool_calls[-1]["bonus_rec_te"] == 0.5
    gid = g["id"]
    team = client.get(f"/v1/sim/games/{gid}/teams/103", headers=H).json()
    assert sorted(p["id"] for p in team["players"]) == sorted(imp.teams[3].roster)
    adv = client.post(f"/v1/sim/games/{gid}/advance", json={"week": 1}, headers=H).json()
    assert adv["recap"]["week"] == 1 and adv["game"]["week"] == 2
    again = client.get(f"/v1/sim/games/{gid}", headers=H).json()["game"]
    assert again["week"] == 2 and again["settings"]["start"] == "league"
    assert set(backend.tables) <= {"sim_games", "sim_events", "sim_week_checkpoints"}


@pytest.mark.parametrize("error", ["team_not_found", "league_unavailable", "league_size_unsupported"])
def test_league_start_passes_through_input_errors_as_reasons_and_creates_nothing(error):
    from modules.sim import game_api
    game_api.clear_pool_cache()
    client, backend = make_app(Inputs(error=error))
    res = client.post("/v1/sim/games", json={"start": "league", "league_id": "L1"}, headers=H).json()
    assert res["reason"] == error and "game" not in res
    assert not backend.tables.get("sim_games")


def test_league_start_validates_input_and_is_unavailable_without_the_door():
    from modules.sim import game_api
    game_api.clear_pool_cache()

    class PoolOnly:
        def player_pool(self, scoring):
            return PlayerPool(ROWS, BYES)

    client, _ = make_app(Inputs(imported_league()))
    assert client.post("/v1/sim/games", json={"start": "league"}, headers=H).status_code == 422
    assert client.post("/v1/sim/games", json={"start": "season_start"}, headers=H).status_code == 422
    client2, _ = make_app(PoolOnly())
    assert client2.get("/v1/sim/games/options", headers=H).json()["start_modes"][1]["available"] is False
    assert client2.post("/v1/sim/games", json={"start": "league", "league_id": "L"}, headers=H).json()["reason"] == "league_unavailable"
