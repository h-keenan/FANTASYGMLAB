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
    {"mode": "keeper"}, {"mode": "dynasty", "seasons": 9}, {"difficulty": "brutal"}, {"user_slot": 13}, {"auto_lineup": "x"},
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


def test_modes_are_extensible_and_dynasty_is_playable():
    assert policy_for("redraft").season_valuation and policy_for("redraft").available
    assert policy_for("dynasty").available and policy_for("dynasty").dynasty and not policy_for("dynasty").season_valuation
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


def test_kickers_and_defenses_cannot_be_traded_on_an_old_save():
    snap = snapshot(3, include_def=True)
    snap = dataclasses.replace(snap, settings=dataclasses.replace(snap.settings, kd_v=0))  # a save from before kd_v
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

    def league_teams(self, league_id, *, username=""):
        from modules.sim.game_types import LeagueTeamChoice, LeagueTeams
        self.teams_args = (league_id, username)
        if self.error:
            raise SimInputsError(self.error)
        teams = tuple(LeagueTeamChoice(
            roster_id=t.tid, team_name=t.name, owner_name=t.owner, wins=1, losses=0, ties=0,
            points_for=100.0, rank=i + 1, is_you=t.is_user) for i, t in enumerate(self.imported.teams))
        you = next((t.roster_id for t in teams if t.is_you), "")
        return LeagueTeams(league_id=league_id, league_name="My League", season="2026", teams=teams, you_roster_id=you)


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
    assert o["teams"]["values"] == [8, 10, 12, 14] and o["mode"]["values"] == ["redraft", "dynasty"]
    assert (o["bench"]["min"], o["bench"]["max"], o["bench"]["default"]) == (4, 10, 8)
    assert o["superflex"]["default"] is False and o["include_k"]["default"] is True and o["include_def"]["default"] is False
    assert data["layout"] == {"base_slots": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"], "draft_spare_spots": 2}
    assert o["flex_type"] == {"values": ["flex", "rb_wr"], "default": "flex", "slots": {"flex": "FLEX", "rb_wr": "WRRB_FLEX"}}
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
    assert client.post("/v1/sim/games", json={"mode": "dynasty", "seasons": 9}, headers=H).status_code == 422


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


def test_a_defense_and_superflex_game_on_the_real_pool_completes():
    """Structural check on whatever data/players.db + data/nfl_games.csv hold
    (read only, projections stubbed): 32 estimated defenses, a superflex lineup,
    a full draft and a season to a champion."""

    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    db, games = root / "data" / "players.db", root / "data" / "nfl_games.csv"
    if not db.exists() or not games.exists():
        pytest.skip("no players.db / nfl_games.csv in this checkout")

    class Projections:
        def baseline_weekly_points(self, rows, *, scoring_settings=None):
            return {}

    settings = GameSettings.parse({"user_slot": 6, "superflex": True, "include_def": True, "te_premium": 0.5, "teams": 14})
    pool = RealSimInputs(str(db), games_csv_path=str(games), projections_module=Projections(), sleeper_module=object(),
                         playoff_module=object()).player_pool(settings.scoring_settings)
    assert "def_estimated_from_points_allowed" in pool.notes
    snap = build_snapshot(pool.rows, pool.bye_weeks, settings, 3, scoring_model=MODEL)
    state, em = play_draft(snap, 3)
    assert all(len(r) == settings.rounds for r in state.rosters.values())
    while state.status != "complete":
        advance(em, snap, state, 3)
    assert state.champion in snap.tids


# ------------------------------------------------ team pickers (no typed names)

TRICKY_NAMES = ["Team O'Brien", "The Big  Show", "Ballers \U0001F3C8\U0001F525", "\u00c9quipe Fant\u00f4me", "A&B \"Crew\" <3"]


class PickerSleeper(FakeSleeper):
    """Sleeper data whose team names are hostile to string matching, and whose
    account link does not match any roster's username (display name / co-owner)."""

    def __init__(self, names=None, owner_ids=None, co_owners=None, user_id="u-me", usernames=None):
        names = names or TRICKY_NAMES
        rosters = [{"roster_id": i + 1, "owner_id": (owner_ids or {}).get(i + 1, f"u{i + 1}"),
                    "co_owners": (co_owners or {}).get(i + 1, []), "players": [f"p{i}"],
                    "settings": {"wins": 5 - i % 5, "losses": i % 5, "ties": 0, "fpts": 900 - 10 * i, "fpts_decimal": 50}}
                   for i in range(12)]
        super().__init__(rosters=rosters)
        self._names = names
        self._user_id = user_id
        self._usernames = usernames or {}

    def get_user_id(self, username):
        return self._user_id if username.casefold() == "meuser" else None

    def get_league_roster_profiles(self, league_id):
        return {str(r["roster_id"]): {
            "team_name": self._names[(r["roster_id"] - 1) % len(self._names)] + ("" if r["roster_id"] <= len(self._names) else f" {r['roster_id']}"),
            "owner_name": f"Owner {r['roster_id']}", "username": self._usernames.get(r["roster_id"], f"other{r['roster_id']}"),
        } for r in self._rosters}


def test_league_teams_lists_names_with_spaces_emoji_and_quotes_and_preselects_by_user_id():
    sleeper = PickerSleeper(owner_ids={4: "u-me"})
    res = real_inputs(sleeper).league_teams("L1", username="MeUser")  # no roster has username "meuser"
    assert res.you_roster_id == "4" and [t.is_you for t in res.teams].count(True) == 1
    assert [t.team_name for t in res.teams[:5]] == TRICKY_NAMES
    assert [t.rank for t in res.teams if t.roster_id == "1"] == [1] and res.teams[0].points_for == 900.5
    assert sleeper.calls == ["league"]  # read-only


def test_league_teams_preselects_by_username_casefolded_or_co_owner_and_never_guesses():
    assert real_inputs(PickerSleeper(usernames={7: "MeUser"})).league_teams("L1", username="meuser").you_roster_id == "7"
    assert real_inputs(PickerSleeper(usernames={7: "meuser"})).league_teams("L1", username="@MeUser ").you_roster_id == "7"
    assert real_inputs(PickerSleeper(co_owners={9: ["u-me"]})).league_teams("L1", username="meuser").you_roster_id == "9"
    nobody = real_inputs(PickerSleeper()).league_teams("L1", username="stranger")
    assert nobody.you_roster_id == "" and not any(t.is_you for t in nobody.teams)
    assert real_inputs(PickerSleeper()).league_teams("L1", username="").you_roster_id == ""


def test_league_teams_refuses_other_platforms_and_unreadable_leagues():
    with pytest.raises(SimInputsError) as err:
        real_inputs(PickerSleeper()).league_teams("espn:5:2026", username="x")
    assert err.value.code == "league_platform_unsupported"
    with pytest.raises(SimInputsError) as err:
        real_inputs(FakeSleeper(league={})).league_teams("L1", username="x")
    assert err.value.code == "league_unavailable"


def test_league_import_picks_the_team_by_roster_id_whatever_its_name_looks_like():
    sleeper = PickerSleeper()
    for rid, name in enumerate(TRICKY_NAMES, start=1):
        imp = real_inputs(sleeper).league_import("L1", username="", roster_id=str(rid))
        mine = next(t for t in imp.teams if t.is_user)
        assert mine.tid == str(rid) and mine.name == name
    with pytest.raises(SimInputsError) as err:
        real_inputs(sleeper).league_import("L1", username="", roster_id="99")
    assert err.value.code == "team_not_found"
    imp = real_inputs(PickerSleeper(owner_ids={4: "u-me"})).league_import("L1", username="MeUser")
    assert next(t for t in imp.teams if t.is_user).tid == "4"


def test_league_teams_endpoint_and_creating_by_roster_id():
    from modules.sim import game_api
    game_api.clear_pool_cache()
    inputs = Inputs(imported_league())
    client, _ = make_app(inputs)
    res = client.get("/v1/sim/games/league-teams?league_id=L1", headers=H).json()
    assert res["reason"] == "" and res["you_roster_id"] == "103" and len(res["teams"]) == 12
    assert [t["roster_id"] for t in res["teams"] if t["is_you"]] == ["103"]
    assert inputs.teams_args == ("L1", "turbo")
    assert client.get("/v1/sim/games/league-teams", headers=H).status_code == 422
    assert client.get("/v1/sim/games/league-teams?league_id=L1").status_code == 401
    created = client.post("/v1/sim/games", json={"start": "league", "league_id": "L1", "roster_id": "105"}, headers=H).json()
    assert inputs.import_args == ("L1", "turbo", "105") and created["reason"] == ""
    broken = Inputs(imported_league(), error="league_platform_unsupported")
    client2, _ = make_app(broken)
    assert client2.get("/v1/sim/games/league-teams?league_id=espn:1:2026", headers=H).json()["reason"] == "league_platform_unsupported"


def test_options_list_preset_team_names():
    from modules.sim import game_api
    game_api.clear_pool_cache()
    client, _ = make_app(Inputs(imported_league()))
    names = client.get("/v1/sim/games/options", headers=H).json()["options"]["team_names"]
    assert names["max_length"] == 40 and len(names["values"]) >= 24 and len(set(names["values"])) == len(names["values"])
    assert all(0 < len(n) <= 40 for n in names["values"])
    banned = ("Cowboys", "Packers", "Chiefs", "Eagles", "Patriots", "49ers", "Steelers", "Giants", "Jets", "Bears")
    assert not any(b.lower() in n.lower() for n in names["values"] for b in banned)


@pytest.mark.parametrize("name", TRICKY_NAMES)
def test_fresh_league_keeps_a_chosen_name_exactly_and_ai_teams_never_reuse_it(name):
    from modules.sim import game_api
    game_api.clear_pool_cache()
    client, _ = make_app(Inputs(imported_league()))
    res = client.post("/v1/sim/games", json={"team_name": name}, headers=H).json()
    clean = " ".join(name.split())
    assert res["game"]["you"]["name"] == clean
    teams = res["draft"]["teams"]
    assert sum(1 for t in teams if t["name"] == clean) == 1


def test_random_team_name_is_a_preset_and_unique_among_teams():
    from modules.sim import game_api
    from modules.sim.game_setup import TEAM_NAMES
    game_api.clear_pool_cache()
    client, _ = make_app(Inputs(imported_league()))
    for _ in range(4):
        res = client.post("/v1/sim/games", json={"random_team_name": True}, headers=H).json()
        me = res["game"]["you"]["name"]
        assert me in TEAM_NAMES
        assert [t["name"] for t in res["draft"]["teams"]].count(me) == 1
        client.delete(f"/v1/sim/games/{res['game']['id']}", headers=H)


def test_ai_names_skip_a_preset_the_player_picked_even_with_different_case_or_spacing():
    from modules.sim.game_setup import TEAM_NAMES, build_snapshot
    from modules.sim.game_types import GameSettings
    settings = GameSettings.parse({"teams": 14, "user_slot": 1})
    for seed in range(8):
        for chosen in (TEAM_NAMES[0], "  " + TEAM_NAMES[3].upper().replace(" ", "  ")):
            snap = build_snapshot(ROWS, BYES, settings, seed, user_team_name=chosen)
            keys = [" ".join(t.name.split()).casefold() for t in snap.teams]
            assert len(set(keys)) == len(keys)


def test_too_long_team_name_is_rejected():
    from modules.sim import game_api
    game_api.clear_pool_cache()
    client, _ = make_app(Inputs(imported_league()))
    assert client.post("/v1/sim/games", json={"team_name": "x" * 41}, headers=H).status_code == 422


# ------------------------------------------------------------------ flex eligibility (RB/WR/TE default, RB/WR alternative)

# The model id a save records is "player_model-<generation>"; a bare "player-model-5" is not an id, resolves to the CURRENT default
# and silently plays on whatever model is newest (that was the whole drift from 1c4fc89f to 228f0621: model 6 became the default).
OLD_SAVE_MODEL = "player_model-player-model-5"
OLD_SAVE_DIGEST = "1c4fc89f0f26d9a75c02265a03c0b7252ab92a0a511ead91893a2e0110471fec"  # captured on main before flex_type / kd_v / limit_v / names_v / model 6


def _played_digest(snap):
    state, em = play_draft(snap)
    for _ in range(6):
        advance(em, snap, state, 11)
    return state.digest()


def _golden_snapshot():
    return build_snapshot(ROWS, BYES, GameSettings.parse({"user_slot": 4, "superflex": True}), 11, scoring_model=OLD_SAVE_MODEL)


def _as_old_save(snap):
    """The same game as a save from before flex_type / kd_v: its settings carry neither key."""
    raw = {k: v for k, v in snap.settings.to_dict().items() if k not in ("flex_type", "kd_v", "limit_v", "names_v", "hint_v")}
    return dataclasses.replace(snap, settings=GameSettings.from_dict(raw))


def test_default_flex_is_unchanged_and_never_serialized():
    s = GameSettings.parse({})
    assert s.flex_type == "flex" and "FLEX" in s.slots and "WRRB_FLEX" not in s.slots
    assert "flex_type" not in s.to_dict()
    assert GameSettings.from_dict(s.to_dict()) == s


def test_old_save_replays_identically_to_a_game_with_the_new_flags():
    old = _as_old_save(_golden_snapshot())
    assert "flex_type" not in old.settings.to_dict() and "kd_v" not in old.settings.to_dict()
    assert old.settings.non_tradable == ("K", "DEF")
    assert old.settings.limit_v == 0 and old.settings.names_v == 0 and old.settings.kd_v == 0 and old.scoring_model == OLD_SAVE_MODEL
    # Explicit old settings on the old model reproduce the digest captured before any of the new flags or model 6 existed.
    assert _played_digest(old) == OLD_SAVE_DIGEST
    # A new game (flex_type default, kd_v 1) on the same model plays identically to the save without the keys: the flags change
    # nothing until used. (Not an absolute pin: any engine change on main legitimately moves a digest; verified equal to
    # origin/main's own digest for this save when this PR was cut.)
    # (hint_v 1 changes the user's auto-pick helper, so the comparison game keeps hint_v 0: see test_sim_hint_v.py for the rest.)
    assert _played_digest(old) == _played_digest(dataclasses.replace(_golden_snapshot(), settings=dataclasses.replace(_golden_snapshot().settings, hint_v=0)))


def test_rb_wr_flex_option_changes_only_the_flex_slot_and_round_trips():
    s = GameSettings.parse({"flex_type": "rb_wr"})
    assert s.slots == ("QB", "RB", "RB", "WR", "WR", "TE", "WRRB_FLEX", "K")
    assert (s.roster_limit, s.rounds) == (16, 14)
    assert s.to_dict()["flex_type"] == "rb_wr"
    assert GameSettings.from_dict(s.to_dict()) == s
    with pytest.raises(ValueError):
        GameSettings.parse({"flex_type": "te_only"})


def test_rb_wr_flex_never_starts_a_tight_end_and_lineup_rules_enforce_it():
    from modules.sim.game_types import slot_positions
    from modules.sim.lineup import SlotPlan, pick_lineup

    assert slot_positions("WRRB_FLEX") == frozenset({"RB", "WR"})
    plan = SlotPlan(("QB", "TE", "WRRB_FLEX"))
    entries = [(20.0, "q", "QB"), (9.0, "t1", "TE"), (15.0, "t2", "TE"), (4.0, "r1", "RB")]
    assignment, _ = pick_lineup(plan, entries)
    assert dict(assignment)["WRRB_FLEX"] == "r1"  # the better TE is not eligible
    std, _ = pick_lineup(SlotPlan(("QB", "TE", "FLEX")), entries)
    assert dict(std)["FLEX"] == "t1"  # the standard flex may take a TE (lineup TE is the 15, flex the 9)


def test_rb_wr_flex_league_plays_a_full_game_and_replays():
    snap = snapshot(seed=11, flex_type="rb_wr")
    state, em = play_draft(snap)
    for _ in range(4):
        advance(em, snap, state, 11)
    assert replay_game(snap, 11, em.events, strict=True).digest() == state.digest()
    for tid, row in state.lineups.items():
        slot_pos = {s: snap.players[p].pos for s, p in row if p}
        assert slot_pos.get("WRRB_FLEX") in (None, "RB", "WR")


# ------------------------------------------------------------------ kickers and defenses in trades (kd_v)


def _kd_world():
    snap = snapshot(seed=11)
    state, em = play_draft(snap)
    advance(em, snap, state, 11)
    return snap, state, em


def test_kd_v_is_set_on_new_games_serialized_and_absent_on_old_saves():
    s = GameSettings.parse({})
    assert s.kd_v == 1 and s.non_tradable == () and s.to_dict()["kd_v"] == 1
    old = GameSettings.from_dict({k: v for k, v in s.to_dict().items() if k != "kd_v"})
    assert old.kd_v == 0 and old.non_tradable == ("K", "DEF") and "kd_v" not in old.to_dict()


def test_old_save_without_kd_v_still_refuses_a_kicker_trade():
    from modules.sim.game_ai import validate_offer
    snap, state, em = _kd_world()
    old_snap = dataclasses.replace(snap, settings=dataclasses.replace(snap.settings, kd_v=0))
    user = snap.user_team.tid
    partner = next(t for t in snap.tids if t != user)
    k = next(p for p in state.rosters[user] if snap.players[p].pos == "K")
    their_k = next(p for p in state.rosters[partner] if snap.players[p].pos == "K")
    with pytest.raises(ValueError, match="cannot be traded"):
        validate_offer(old_snap, state, partner, [k], [their_k])
    validate_offer(snap, state, partner, [k], [their_k])  # a new game allows the swap


def test_kicker_swap_is_accepted_and_executes_but_a_second_kicker_is_refused():
    from modules.sim.game_ai import TradeDesk, validate_offer
    from modules.sim.game_types import GameError
    snap, state, em = _kd_world()
    user = snap.user_team.tid
    partner = next(t for t in snap.tids if t != user)
    k = next(p for p in state.rosters[user] if snap.players[p].pos == "K")
    their_k = next(p for p in state.rosters[partner] if snap.players[p].pos == "K")
    with pytest.raises(GameError) as err:  # asking for a kicker without giving yours leaves you with two
        validate_offer(snap, state, partner, [next(p for p in state.rosters[user] if snap.players[p].pos == "WR")], [their_k])
    assert err.value.code == "singleton_limit"
    desk = TradeDesk(Evaluator(snap, state), 11)
    # A kicker-for-kicker swap with a sweetener the AI likes: find one it accepts, then send it.
    sweeteners = [[]] + [[p] for p in state.rosters[user] if snap.players[p].pos in ("RB", "WR", "TE", "QB")]
    chosen = next((give for give in ([k] + extra for extra in sweeteners) if desk.verdict(partner, give, [their_k]).decision == "accept"), None)
    assert chosen is not None
    trade = act.send_trade(em, desk, partner, chosen, [their_k])[1]
    assert trade is not None
    assert k in state.rosters[partner] and their_k in state.rosters[user]
    assert replay_game(snap, 11, em.events, strict=True).digest() == state.digest()
