"""Team-level role coupling (player-model-3): one fill-in per vacated starter, never two backups with
starter-level volume. Pure resolver tests, then the engine: determinism, resume == replay, injuries
mid-season, AI lineups, and old saves untouched."""

from __future__ import annotations

import copy
from dataclasses import replace

from modules.sim import game_scoring, player_model, player_model_v2
from modules.sim import team_roles as tr
from modules.sim.game_engine import ScoringSession, advance, finish_draft
from modules.sim.game_eval import Evaluator
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_store import GameStore
from modules.sim.game_types import GameSettings
from modules.sim.store import InMemoryBackend
from tests.test_sim_game_engine import BYES, ROWS

V2_ID = "player_model-player-model-2"
V3_ID = "player_model-player-model-3"


def M(pid, pos, mean, order=tr.NO_ORDER, market=0.0, out=False):
    return tr.Member(pid=pid, pos=pos, team="PHI", mean=mean, market=market, order=order, starts_out=out)


def avail(*down):
    return lambda pid: pid not in down


# ------------------------------------------------------------------ resolver


def test_constants_match_the_calibrated_model_and_the_real_backup_qb_prior():
    ab = player_model.INSEASON.absorb
    assert tuple(tr.ABSORB[p] for p in ("QB", "RB", "WR", "TE")) == ab[:4]
    assert tr.FIRST_BACKUP_SHARE == 1.0 / (1.0 + 0.25)
    from modules import player_projections
    assert tr.BACKUP_QB_SHARE == player_projections.BACKUP_QB_PLAY_SHARE


def test_starter_out_two_backups_exactly_one_fills_in():
    qbs = tr.depth_order([M("hurts", "QB", 16.6, 1), M("milton", "QB", 13.2, 2), M("mckee", "QB", 10.7, 3)])
    roles = tr.resolve_group(qbs, avail("hurts"))
    assert roles["hurts"].kind == "out"
    assert roles["milton"].kind == "fill_in" and roles["milton"].covering == "hurts"
    assert roles["mckee"].kind == "backup" and roles["mckee"].mult == tr.BACKUP_QB_SHARE
    fills = [r for r in roles.values() if r.kind == "fill_in"]
    assert len(fills) == 1
    # QB fill-in: 0.2 x own mean + 0.6 x the starter's mean; about his own if-he-starts number, not more
    assert abs(roles["milton"].mult * 13.2 - (0.2 * 13.2 + 0.6 * 16.6)) < 0.05
    # the group's total expected volume is about one starter, not two
    total = sum(r.mult * m for r, m in zip((roles["milton"], roles["mckee"]), (13.2, 10.7)))
    assert total < 16.6


def test_starter_returns_restores_roles_and_backups_go_back_to_baseline():
    qbs = tr.depth_order([M("a", "QB", 17.0, 1), M("b", "QB", 12.0, 2), M("c", "QB", 9.0, 3)])
    assert tr.resolve_group(qbs, avail())["a"] == tr.Role("starter")
    roles = tr.resolve_group(qbs, avail())
    assert roles["b"].kind == "backup" and roles["c"].kind == "backup"
    # the next fill-in when the first backup is hurt too
    both = tr.resolve_group(qbs, avail("a", "b"))
    assert both["c"].kind == "fill_in" and both["b"].kind == "out"


def test_multi_slot_groups_get_one_partial_inheritor_per_vacated_starter():
    rbs = tr.depth_order([M(f"rb{i}", "RB", m, i) for i, m in enumerate((15.0, 11.0, 6.0, 4.0, 2.0), 1)])
    roles = tr.resolve_group(rbs, avail("rb1"))
    assert [p for p, r in roles.items() if r.kind == "fill_in"] == ["rb3"]
    assert roles["rb2"].kind == "starter" and roles["rb4"].kind == "bench" and roles["rb4"].mult == 1.0
    uplift = roles["rb3"].mult * 6.0 - 6.0
    assert abs(uplift - tr.ABSORB["RB"] * tr.FIRST_BACKUP_SHARE * 15.0) < 0.05  # partial, not the starter's mean
    two = tr.resolve_group(rbs, avail("rb1", "rb2"))
    assert sorted(p for p, r in two.items() if r.kind == "fill_in") == ["rb3", "rb4"]
    wrs = tr.depth_order([M(f"wr{i}", "WR", 12.0 - i, i) for i in range(1, 7)])
    wr = tr.resolve_group(wrs, avail("wr2"))
    assert [p for p, r in wr.items() if r.kind == "fill_in"] == ["wr4"] and wr["wr5"].mult == 1.0


def test_kickers_and_defenses_are_exempt():
    ks = tr.depth_order([tr.Member("k1", "K", "PHI", 8.0), tr.Member("k2", "K", "PHI", 7.0)])
    assert all(r.kind == "exempt" and r.mult == 1.0 for r in tr.resolve_group(ks, avail("k1")).values())
    book = tr.RoleBook({"d": type("P", (), {"pos": "DEF", "nfl_team": "PHI", "mean": 7.0})()})
    assert book.key("d") is None


def test_depth_order_prefers_chart_then_projection_and_keeps_an_injured_star_on_top():
    healthy = tr.depth_order([M("x", "QB", 10.0, 2), M("y", "QB", 14.0, 1), M("z", "QB", 12.0)])
    assert [m.pid for m in healthy] == ["y", "x", "z"]
    # live chart drops the injured star below his fill-in; he is still the starter when back
    star = tr.depth_order([M("fill", "QB", 13.0, 1), M("hurts", "QB", 16.0, 2, market=90.0, out=True)])
    assert star[0].pid == "hurts"
    # an injured nobody does not jump the queue
    nobody = tr.depth_order([M("fill", "QB", 13.0, 1, market=40.0), M("sub", "QB", 9.0, 2, market=1.0, out=True)])
    assert nobody[0].pid == "fill"


def test_resolver_is_deterministic_and_order_independent():
    ms = [M("a", "QB", 17.0, 1), M("b", "QB", 12.0, 2), M("c", "QB", 9.0, 3)]
    r1 = tr.resolve_group(tr.depth_order(ms), avail("a"))
    r2 = tr.resolve_group(tr.depth_order(list(reversed(ms))), avail("a"))
    assert r1 == r2


# -------------------------------------------------------------------- engine


def rows_with_phi(hurts_out=4):
    """ATL gets the scenario: a star QB hurt for ``hurts_out`` weeks and two backups, both with starter-level means."""

    rows = copy.deepcopy(ROWS)
    atl = [r for r in rows if r["nfl_team"] == "ATL" and r["pos"] == "QB"]
    assert len(atl) == 3
    spec = [("hurts", 17.0, 90.0, hurts_out, 2 if hurts_out else 1), ("milton", 14.6, 60.0, 0, 1 if hurts_out else 2), ("mckee", 13.5, 55.0, 0, 3)]
    for r, (name, mean, market, weeks, order) in zip(atl, spec):
        r.update(name=name, mean=mean, market=market, injury_weeks=weeks, extra={"depth_chart_order": float(order)})
    return rows, {n: r["pid"] for n, r in zip(("hurts", "milton", "mckee"), atl)}


def make(model_id, rows=None, seed=11):
    rows = rows or ROWS
    settings = replace(GameSettings.parse({"user_slot": 4}), reserve_v=0, ir_slots=0)
    return build_snapshot(rows, BYES, settings, seed, scoring_model=model_id)


def drafted(snap, seed=11):
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, seed)
    auto_for_user(ctx, em, seed)
    finish_draft(em, snap, state, seed)
    return state, em


def test_pool_means_are_not_changed_so_draft_value_and_adp_stay_consistent():
    rows, ids = rows_with_phi()
    a, b = make(V2_ID, rows), make(V3_ID, rows)
    assert {p: (x.mean, x.value, x.adp) for p, x in a.players.items()} == {p: (x.mean, x.value, x.adp) for p, x in b.players.items()}


def test_evaluator_shows_one_fill_in_projection_and_marks_roles():
    rows, ids = rows_with_phi()
    snap = make(V3_ID, rows)
    state = GameState(snap)
    state.week = 1
    ev = Evaluator(snap, state)
    assert ev.roles_on
    milton, mckee, hurts = (ev.role_info(ids[n], 1) for n in ("milton", "mckee", "hurts"))
    assert milton["kind"] == "fill_in" and milton["label"] == "Starting while hurts is out"
    assert mckee["kind"] == "backup" and mckee["label"] == "Backup" and mckee["if_starts"] == 13.5
    assert hurts["kind"] == "starter" and hurts["week"] >= 5  # shown for the first game he plays
    assert ev.next_proj(ids["hurts"], 1) == 17.0
    assert ev.proj(ids["hurts"], 1) == 0.0  # still out for lineup purposes
    # next-game projections: only the fill-in carries starter-level volume
    assert ev.next_proj(ids["milton"], 1) > 12.0 and ev.next_proj(ids["mckee"], 1) < 4.0
    # weeks 1-4 fill-in, then back to baseline when the starter returns
    assert ev.role_mult(ids["milton"], 4) > 0.85 and ev.role_mult(ids["milton"], 6) == tr.BACKUP_QB_SHARE
    # the rest-of-season number (valuations, AI) blends the two, so a 4-week fill-in is not a starter
    assert ev.ros_mean(ids["milton"]) < 0.7 * 14.6
    old = Evaluator(make(V2_ID, rows), state)
    assert not old.roles_on and old.role_info(ids["mckee"], 1) is None and old.ros_mean(ids["mckee"]) == 13.5


def play(model_id, rows=None, weeks=17, seed=11, spy=None):
    snap = make(model_id, rows, seed)
    state, em = drafted(snap, seed)
    store = GameStore(InMemoryBackend())
    row = store.create_game("u", snapshot=snap, seed=seed)
    store.append_events("u", row["id"], em.events)
    while state.status != "complete" and state.week <= weeks:
        em = Emitter(state, snap)
        advance(em, snap, state, seed)
        store.append_events("u", row["id"], em.events)
        store.save_checkpoint("u", row["id"], state, state.week)
    return store, row["id"], snap, state


def test_every_week_each_team_group_has_at_most_one_fill_in_per_vacated_starter(monkeypatch):
    calls = []
    orig = ScoringSession.week

    def spy(self, pid, week, role_mult=None):
        calls.append((pid, week, role_mult))
        return orig(self, pid, week, role_mult)

    monkeypatch.setattr(ScoringSession, "week", spy)
    rows, ids = rows_with_phi()
    store, gid, snap, state = play(V3_ID, rows)
    by_week = {}
    for pid, week, m in calls:
        by_week.setdefault(week, {})[pid] = m
    for week in range(1, 5):  # the star is out
        m, k = by_week[week][ids["milton"]], by_week[week][ids["mckee"]]
        assert m > 0.85 and k == tr.BACKUP_QB_SHARE and ids["hurts"] not in by_week[week]
    for week in range(5, 18):  # he is back (unless re-injured): roles restore
        if ids["hurts"] in by_week.get(week, {}):
            assert by_week[week][ids["milton"]] == tr.BACKUP_QB_SHARE
    # across the whole league: never more than one QB per team with a multiplier above the backup share,
    # and never more fill-ins than starters out in that group
    for week, mults in by_week.items():
        per_team = {}
        for pid, m in mults.items():
            p = snap.players[pid]
            if p.pos == "QB" and m is not None and m > tr.BACKUP_QB_SHARE + 1e-9:
                per_team.setdefault(p.nfl_team, []).append(pid)
        assert all(len(v) <= 1 for v in per_team.values()), (week, per_team)
    # K and DEF never get a multiplier other than 1
    assert all(m == 1.0 for pid, w, m in calls if snap.players[pid].pos in ("K", "DEF"))


def test_total_team_qb_points_stay_near_one_starter_not_two():
    rows, ids = rows_with_phi(hurts_out=4)
    # weeks 1-4: milton plays, mckee is a bench QB; average over seeds so a single draw does not decide it
    both_old = both_new = 0.0
    n = 0
    for seed in (3, 4, 5, 6):
        for model_id in (V2_ID, V3_ID):
            store, gid, snap, state = play(model_id, rows, weeks=5, seed=seed)
            pts = lambda name: [x or 0.0 for x in state.points.get(ids[name], [])[:4]]
            total = sum(pts("milton")) + sum(pts("mckee"))
            if model_id == V2_ID:
                both_old += total
            else:
                both_new += total
        n += 1
    assert both_old / n > 40 and both_new / n < 0.8 * both_old / n  # old: two starters; new: about one


def test_resume_equals_replay_for_new_games_and_is_deterministic():
    rows, _ = rows_with_phi()
    s1, g1, snap1, st1 = play(V3_ID, rows, weeks=6)
    s2, g2, snap2, st2 = play(V3_ID, rows, weeks=6)
    assert st1.digest() == st2.digest()
    assert s1.load_state("u", g1, snap1, use_checkpoint=True).digest() == s1.load_state("u", g1, snap1, use_checkpoint=False).digest() == st1.digest()


def test_old_model_saves_are_unchanged_and_never_see_roles(monkeypatch):
    from tests.test_sim_game_model_versions import GOLDEN_V2_DIGESTS, _play
    seen = []
    orig = ScoringSession.week
    monkeypatch.setattr(ScoringSession, "week", lambda self, pid, week, role_mult=None: (seen.append(role_mult), orig(self, pid, week, role_mult))[1])
    *_, snap, state, digests = _play(V2_ID)
    assert digests == GOLDEN_V2_DIGESTS
    assert seen and all(m is None for m in seen)
    assert not game_scoring.team_roles_enabled(V2_ID) and game_scoring.team_roles_enabled(V3_ID)
    assert not game_scoring.team_roles_enabled(game_scoring.FALLBACK_ID)


def test_frozen_v2_module_is_the_old_model_and_v3_only_adds_roles():
    assert player_model_v2.MODEL_VERSION == "player-model-2" and not getattr(player_model_v2, "TEAM_ROLES", False)
    assert player_model.MODEL_VERSION == "player-model-3" and player_model.TEAM_ROLES
    p = {"player_id": "x", "pos": "WR", "age": 25.0, "team": "KC", "projection_mean_ppg": 12.0, "is_rookie": False}
    a = player_model_v2.draw_season_profile(p, player_model_v2.profile_rng(3, "x"))
    b = player_model.draw_season_profile(p, player_model.profile_rng(3, "x"))
    assert a.season_mean_ppg == b.season_mean_ppg and a.injury_events == b.injury_events  # same season story
    assert player_model.with_role_multiplier(b, 3, 1.0) is b


def test_role_multiplier_scales_only_that_week_and_adds_no_randomness():
    p = {"player_id": "x", "pos": "RB", "age": 25.0, "team": "KC", "projection_mean_ppg": 8.0, "is_rookie": False}
    prof = player_model.draw_season_profile(p, player_model.profile_rng(5, "x"))
    wk = next(w for w in range(1, 18) if prof.games_available_mask[w - 1] and not any(e.week == w for e in prof.injury_events))
    base = player_model.draw_week_points(p, prof, wk, player_model.week_rng(5, "x", wk), {})
    up = player_model.draw_week_points(p, player_model.with_role_multiplier(prof, wk, 1.5), wk, player_model.week_rng(5, "x", wk), {})
    assert abs(up.expected_points - 1.5 * base.expected_points) < 0.01
    other = next(w for w in range(1, 18) if w != wk and prof.games_available_mask[w - 1])
    a = player_model.draw_week_points(p, prof, other, player_model.week_rng(5, "x", other), {})
    b = player_model.draw_week_points(p, player_model.with_role_multiplier(prof, wk, 1.5), other, player_model.week_rng(5, "x", other), {})
    assert a == b


def test_injury_mid_season_re_resolves_roles_for_following_weeks():
    rows, ids = rows_with_phi(hurts_out=0)  # everyone healthy at the start
    snap = make(V3_ID, rows)
    assert snap.bye_of(ids["hurts"]) >= 5
    state = GameState(snap)
    state.week = 2  # weeks 2-4 have no ATL bye
    ev = Evaluator(snap, state)
    assert ev.role_info(ids["milton"], 2)["kind"] == "backup"
    state.out[ids["hurts"]] = 2  # an injury event applied by the engine: out weeks 2-3
    ev = Evaluator(snap, state)
    assert ev.role_info(ids["milton"], 2)["kind"] == "fill_in"
    assert ev.role_mult(ids["mckee"], 2) == tr.BACKUP_QB_SHARE and ev.role_mult(ids["milton"], 4) == tr.BACKUP_QB_SHARE
    state.out[ids["milton"]] = 2  # the fill-in is hurt too: the next man up takes over, still just one
    ev = Evaluator(snap, state)
    assert ev.role_info(ids["mckee"], 2)["kind"] == "fill_in" and ev.role_mult(ids["milton"], 4) == tr.BACKUP_QB_SHARE


def test_ai_lineups_and_waivers_value_one_backup_not_both():
    rows, ids = rows_with_phi()
    snap = make(V3_ID, rows)
    state = GameState(snap)
    state.week = 1
    ev = Evaluator(snap, state)
    # worth to an AI manager: the fill-in is worth more than the benched QB, and neither is valued as the star
    from modules.sim.game_eval import USER_PARAMS
    assert ev.worth(USER_PARAMS, ids["milton"]) > ev.worth(USER_PARAMS, ids["mckee"])
    assert ev.ros_mean(ids["mckee"]) < 0.5 * snap.players[ids["mckee"]].mean
    # a roster holding both starts the fill-in in its one QB slot (the bench QB has a bench-level mean)
    roster = [ids["milton"], ids["mckee"]]
    qb_entries = ev.entries(roster, 1)
    assert qb_entries[0][0] > 3 * qb_entries[1][0]
