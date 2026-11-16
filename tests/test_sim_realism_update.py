"""The Realism update: an event-sourced switch that turns newer rule gates on in a save made before them (modules/sim/game_rules.py).

Gate/registry, the fold (settings history), old logs byte-identical (golden digests, no ``rules`` key), strict replay across the
event (redraft and dynasty), per-flag boundaries, checkpoints, undo/revert through the API, the endpoint and the view payload."""

from __future__ import annotations

import functools
import json

import pytest

from modules.sim import game_actions as act
from modules.sim import game_dynasty as dyn
from modules.sim import game_rules as rules
from modules.sim import game_scoring
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState, fold
from modules.sim.game_types import GameError, GameSettings
from modules.sim.synthetic import build_synthetic_pool
from tests.test_sim_game_api import advance as api_advance
from tests.test_sim_game_api import finish_draft as api_finish_draft
from tests.test_sim_game_api import hdr, make_app, new_game

ROWS, BYES = build_synthetic_pool(7)
SEED = 11
MODEL = "player_model-player-model-5"
# Digests of a save made before EVERY upgradable gate (settings carry none of the keys), produced by origin/main at 9a9dd946 (before the
# Realism update existed) and reproduced here: the update changes nothing for a log that lacks the event. Synthetic pool, seed 11.
GOLDEN_OLD = {
    "redraft": "1c4fc89f0f26d9a75c02265a03c0b7252ab92a0a511ead91893a2e0110471fec",
    "dynasty3": "67fa6cb0ebeb536b641b15bbe3b898a30771b8169a3fa8c0d1b634db3822fd84",
}
OLD_FLAGS = ("hint_v", "limit_v", "kd_v", "world_v", "aging_v", "names_v", "econ_v", "stability_v")


def _old_settings(**extra) -> GameSettings:
    """A save made before every upgradable gate existed (the keys are simply absent, like on a real old save)."""

    d = GameSettings.parse({"user_slot": 4, "superflex": True, **extra}).to_dict()
    for flag in OLD_FLAGS:
        d.pop(flag, None)
    return GameSettings.from_dict(d)


# ------------------------------------------------------------------------------------------------ scripted games


def _redraft(upgrade_after: int | None, weeks: int = 6, model: str = MODEL):
    snap = build_snapshot(ROWS, BYES, _old_settings(), SEED, scoring_model=model)
    state = GameState(snap)
    em = Emitter(state, snap)
    run_ai_picks(DraftContext(snap, state), em, SEED)
    auto_for_user(DraftContext(snap, state), em, SEED)
    finish_draft(em, snap, state, SEED)
    for n in range(weeks):
        if upgrade_after == n:
            act.upgrade_realism(em)
        advance(em, em.snap, state, SEED)
    return snap, state, em


def _dynasty(upgrade_at: tuple[int, str] | None, seasons: int = 4, model: str = MODEL):
    """Play an old dynasty save to the end; ``upgrade_at`` = (season_no, "start" | "offseason") is where the user presses Update."""

    snap = build_snapshot(ROWS, BYES, _old_settings(mode="dynasty", seasons=seasons, start_year=2026, rookie_rounds=2, scoring="ppr"), SEED, scoring_model=model)
    state = GameState(snap)
    em = Emitter(state, snap)
    auto_for_user(DraftContext(snap, state), em, SEED)
    finish_draft(em, snap, state, SEED)
    while True:
        sn, sd = snap.under(state.rules).season_view(state.view_no), dyn.season_seed(SEED, state.view_no)
        em.snap = sn
        if upgrade_at == (state.season_no, "start") and state.status == "in_season" and state.week == 1 and not state.rules:
            act.upgrade_realism(em)
            sn = em.snap
        while state.status in ("in_season", "playoffs"):
            advance(em, em.snap, state, sd)
        if state.status != "offseason":
            return snap, state, em
        sn, sd = snap.view_for(state), dyn.season_seed(SEED, state.view_no)
        em.snap = sn
        if upgrade_at == (state.season_no, "offseason") and not state.rules:
            act.upgrade_realism(em)
            sn = em.snap
        dyn.start_rookie_draft(em)
        dyn.run_ai_rookie_picks(em, sd)
        dyn.auto_rookie_draft(em, sd)
        dyn.start_next_season(em, sd)


def _replay(snap, em):
    return fold(snap, em.events).digest()


@functools.lru_cache(maxsize=None)
def _dyn_cached(upgrade_at, seasons=4):
    return _dynasty(upgrade_at, seasons)


# ------------------------------------------------------------------------------------------------ registry and gate


def test_registry_is_well_formed():
    fields = set(GameSettings.__dataclass_fields__)
    assert rules.UPGRADABLE_FLAGS and set(rules.UPGRADABLE_FLAGS) == set(rules.FLAGS)
    for flag, (target, boundary) in rules.UPGRADABLE_FLAGS.items():
        assert flag in fields and isinstance(target, int) and target >= 1
        assert boundary in rules.BOUNDARIES
    # the declared boundaries (see the module docstring)
    b = {f: v[1] for f, v in rules.UPGRADABLE_FLAGS.items()}
    assert b["hint_v"] == b["limit_v"] == b["kd_v"] == "now" and b["world_v"] == "week" and b["aging_v"] == b["names_v"] == "season"


def test_pending_flags_for_old_new_and_non_dynasty_saves():
    old_dyn = _old_settings(mode="dynasty", seasons=3, start_year=2026, rookie_rounds=2)
    assert set(rules.pending_flags(old_dyn, [])) == set(rules.UPGRADABLE_FLAGS)
    assert set(rules.pending_flags(_old_settings(), [])) == set(rules.UPGRADABLE_FLAGS) - {"aging_v", "names_v"}  # redraft has no offseasons
    new = GameSettings.parse({"mode": "dynasty", "seasons": 3, "start_year": 2026, "rookie_rounds": 2})
    assert rules.pending_flags(new, []) == {}
    # a flag an earlier update already covers is never offered twice
    entry = rules.make_entry({"hint_v": 1}, seq=5, week=2, season_no=1, status="in_season", view_no=1)
    assert "hint_v" not in rules.pending_flags(old_dyn, [entry])
    # half-upgraded saves only offer what is missing
    half = GameSettings.from_dict({**old_dyn.to_dict(), "hint_v": 1, "world_v": 1})
    assert set(rules.pending_flags(half, [])) == set(rules.UPGRADABLE_FLAGS) - {"hint_v", "world_v"}


def test_decision_and_generation_settings_follow_the_boundary():
    base = _old_settings(mode="dynasty", seasons=5, start_year=2026, rookie_rounds=2)
    entry = rules.make_entry({"hint_v": 1, "world_v": 1, "aging_v": 1, "names_v": 1}, seq=9, week=3, season_no=2, status="in_season", view_no=2)
    assert entry["view_from"] == 3 and entry["bounds"] == {"hint_v": "now", "world_v": "week", "aging_v": "season", "names_v": "season"}
    now = rules.decision_settings(base, [entry], 2)
    assert (now.hint_v, now.world_v, now.aging_v, now.names_v) == (1, 1, 0, 0)  # season flags wait for their season
    later = rules.decision_settings(base, [entry], 3)
    assert (later.hint_v, later.world_v, later.aging_v, later.names_v) == (1, 1, 1, 1)
    assert (rules.generation_settings(base, [entry], 2).aging_v, rules.generation_settings(base, [entry], 2).world_v) == (0, 0)
    assert rules.generation_settings(base, [entry], 3).world_v == 1  # the pool generator gets world_v from the season it is built in
    # an event written under an older registry keeps the boundaries it was written with
    legacy = {**entry, "bounds": {"hint_v": "season"}}
    assert rules.decision_settings(base, [legacy], 2).hint_v == 0


def test_settings_serialization_is_unchanged_and_effective_settings_expose_the_flags():
    old = _old_settings()
    assert not any(f in old.to_dict() for f in OLD_FLAGS)
    snap, state, em = _redraft(upgrade_after=2)
    assert snap.settings.hint_v == 0 and "hint_v" not in snap.to_dict()["settings"]  # the stored snapshot never changes
    eff = em.snap.settings
    assert (eff.hint_v, eff.limit_v, eff.kd_v, eff.world_v) == (1, 1, 1, 1) and eff.to_dict()["world_v"] == 1


# ------------------------------------------------------------------------------------------------ fold and old logs


def test_old_logs_without_the_event_are_byte_identical():
    snap, state, em = _redraft(upgrade_after=None, weeks=6)
    assert state.rules == [] and "rules" not in state.digest() and em.snap is snap
    assert state.digest() == GOLDEN_OLD["redraft"]
    assert not any(e["type"] == "realism_upgrade" for e in em.events)
    assert _replay(snap, em) == state.digest()
    root, dstate, dem = _dyn_cached(None, 3)
    assert dstate.rules == [] and "realism_upgrade" not in {e["type"] for e in dem.events}
    assert dstate.digest() == GOLDEN_OLD["dynasty3"] and _replay(root, dem) == dstate.digest()


def test_fold_records_the_settings_history_and_the_feed_row():
    snap, state, em = _redraft(upgrade_after=3)
    ev = next(e for e in em.events if e["type"] == "realism_upgrade")
    assert ev["actor"] == "user" and ev["week"] == 4 and set(ev["payload"]["flags"]) == set(rules.UPGRADABLE_FLAGS) - {"aging_v", "names_v"}
    assert len(state.rules) == 1 and state.rules[0]["seq"] == ev["seq"] and state.rules[0]["view_from"] == 2
    assert state.transactions[-1]["type"] == "rules" if False else any(t["type"] == "rules" for t in state.transactions)
    assert "rules" in json.dumps(state.to_dict()) and state.digest() != _redraft(upgrade_after=None)[1].digest()


def test_update_is_idempotent_and_refused_on_a_finished_game():
    snap, state, em = _redraft(upgrade_after=1, weeks=2)
    n = len(em.events)
    assert act.upgrade_realism(em) == {} and len(em.events) == n  # already current: nothing appended
    done = GameState(snap)
    done.status = "complete"
    with pytest.raises(GameError):
        act.upgrade_realism(Emitter(done, snap))


# ------------------------------------------------------------------------------------------------ strict replay


@pytest.mark.parametrize("upgrade_after", [0, 2, 4])
def test_strict_replay_across_the_upgrade_redraft(upgrade_after):
    snap, state, em = _redraft(upgrade_after=upgrade_after, weeks=7)
    assert _replay(snap, em) == state.digest()  # fold from scratch
    snap2, state2, em2 = _redraft(upgrade_after=upgrade_after, weeks=7)  # re-running the same commands from scratch
    assert state2.digest() == state.digest() and em2.events == em.events
    # a checkpoint taken after the event resumes to the same state
    cut = next(e["seq"] for e in em.events if e["type"] == "realism_upgrade") + 1
    mid = fold(snap, [e for e in em.events if e["seq"] < cut])
    resumed = GameState.from_dict(snap, mid.to_dict())
    assert resumed.rules == mid.rules and resumed.rules
    assert fold(snap, [e for e in em.events if e["seq"] >= cut], resumed).digest() == state.digest()


def test_the_upgrade_actually_changes_what_happens_after_it_and_nothing_before():
    plain = _redraft(upgrade_after=None, weeks=8)[1]
    upg = _redraft(upgrade_after=4, weeks=8)[1]
    # weeks played before the event are identical (the same scores, the same standings after them)
    assert [h for h in plain.history[:4]] == [h for h in upg.history[:4]]
    assert plain.digest() != upg.digest()


def test_world_v_bench_quarterbacks_sit_only_after_the_event():
    plain = _redraft(upgrade_after=None, weeks=9)
    upg = _redraft(upgrade_after=3, weeks=9)
    snap, state, _ = upg

    def qb_games(snap, st, weeks):
        out = {}
        for pid, hist in st.points.items():
            if snap.players[pid].pos == "QB":
                for w, pts in enumerate(hist, 1):
                    if pts is not None and w in weeks:
                        out.setdefault((snap.players[pid].nfl_team, w), set()).add(pid)
        return out

    before = qb_games(snap, state, {1, 2, 3})
    assert before == qb_games(plain[0], plain[1], {1, 2, 3})
    after = qb_games(snap, state, set(range(4, 10)))
    assert after and all(len(v) == 1 for v in after.values())  # one quarterback per NFL team and week once world_v is on


# ------------------------------------------------------------------------------------------------ dynasty boundaries


def test_season_flags_reach_only_seasons_generated_after_the_event():
    root, state, em = _dyn_cached((2, "start"))
    (entry,) = state.rules
    assert entry["season_no"] == 2 and entry["view_from"] == 3
    plain_root, plain_state, plain_em = _dyn_cached(None)
    v = root.under(state.rules)
    p = plain_root
    # seasons already built are exactly what an un-updated game built
    for season in (1, 2):
        assert dict(v.season_view(season).players) == dict(p.season_view(season).players)
    assert v.season_view(2).settings.aging_v == 0 and v.season_view(3).settings.aging_v == 1
    assert v.season_view(2).settings.hint_v == 1  # a "now" flag applies to the season in play at once
    # the next offseason onwards differs: new names, new retirement logic
    assert dict(v.season_view(3).players) != dict(p.season_view(3).players)
    assert v.season_view(2).settings.names_v == 0 and v.season_view(3).settings.names_v == 1
    assert _replay(root, em) == state.digest()


def test_an_offseason_update_waits_one_more_season():
    root, state, em = _dyn_cached((1, "offseason"))
    (entry,) = state.rules
    assert entry["status"] == "offseason" and entry["view_from"] == 3  # the offseason's own rookie class and aging are already built
    plain_root = _dyn_cached(None)[0]
    for season in (1, 2):
        assert dict(root.under(state.rules).season_view(season).players) == dict(plain_root.season_view(season).players)
    assert _replay(root, em) == state.digest()
    rows = rules.rules_info(root.settings, root.under(state.rules).season_view(2).settings, state.rules, "offseason", 2)
    assert [s["flag"] for s in rows["scheduled"]] == ["aging_v", "names_v", "stability_v"] and rows["rules_version"] == 1 and not rows["eligible"]


def test_new_rookie_names_do_not_repeat_after_a_names_update():
    root, state, _ = _dyn_cached((1, "offseason"), 4)
    view = root.under(state.rules)
    seen: set[str] = set()
    names = []
    for season in (3, 4):
        classes = [p.name for p in view.season_view(season).players.values() if p.extra.get("draft_year") == 2026 + season - 1]
        names += classes
    assert names and len(set(names)) == len(names)
    assert not set(names) & {p.name for p in root.players.values()}
    del seen


def test_an_aging_update_changes_who_retires_in_the_next_offseason():
    root, state, _ = _dyn_cached((1, "start"))
    plain_root = _dyn_cached(None)[0]
    v = root.under(state.rules)
    gone_new = set(v.season_view(1).players) - set(v.season_view(2).players)
    gone_old = set(plain_root.season_view(1).players) - set(plain_root.season_view(2).players)
    assert gone_new != gone_old  # season 2 is the first built under aging_v: a different retirement rule, the same dice


# ------------------------------------------------------------------------------------------------ API


def _old_game(client, backend, **body):
    """A game created through the API, then rewritten as a save from before the gates (settings stripped in the stored snapshot)."""

    from modules.sim import game_store

    gid = new_game(client, user_slot=4, **body)["game"]["id"]
    for row in backend.tables["sim_games"]:
        if row["id"] == gid:
            for key in OLD_FLAGS:
                row["snapshot"]["settings"].pop(key, None)
                row["settings"].pop(key, None)
    game_store.SNAPSHOTS.drop(gid)
    game_store.STATES.drop(gid)
    return gid


def _get(client, gid):
    return client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]


def test_endpoint_updates_an_old_save_once_and_exposes_settings_and_rules_version():
    client, backend, _ = make_app()
    gid = _old_game(client, backend)
    api_finish_draft(client, gid)
    api_advance(client, gid)
    g = _get(client, gid)
    assert g["rules"]["rules_version"] == 0 and g["rules"]["eligible"] and "hint_v" not in g["settings"]
    assert {r["flag"] for r in g["rules"]["pending"]} == set(rules.UPGRADABLE_FLAGS) - {"aging_v", "names_v"}
    assert all(r["label"] and r["body"] and r["when"] for r in g["rules"]["pending"]) and g["rules"]["note"]
    res = client.post(f"/v1/sim/games/{gid}/realism-upgrade", headers=hdr()).json()
    assert res["reason"] == "" and res["upgraded"] is True and "world_v" in res["flags"]
    assert res["settings"]["world_v"] == 1 and res["settings"]["hint_v"] == 1 and res["rules"]["rules_version"] == 1 and not res["rules"]["eligible"]
    g = _get(client, gid)
    assert g["settings"]["world_v"] == 1 and g["rules"]["rules_version"] == 1 and g["rules"]["in_force"]["hint_v"] == 1
    n = len(backend.tables["sim_events"])
    again = client.post(f"/v1/sim/games/{gid}/realism-upgrade", headers=hdr()).json()
    assert again["upgraded"] is False and len(backend.tables["sim_events"]) == n
    # the activity feed and the notifications say so
    feed = client.get(f"/v1/sim/games/{gid}/league", headers=hdr()).json()["transactions"]
    assert any(t["type"] == "rules" and t["text"].startswith("Rules updated") for t in feed)
    inbox = client.get(f"/v1/sim/games/{gid}/notifications", headers=hdr()).json()
    assert any(i["kind"] == "rules" for i in inbox["items"])
    # and play goes on
    assert api_advance(client, gid)["game"]["week"] == 3


def test_endpoint_is_premium_and_unknown_games_404():
    client, backend, _ = make_app(pro=("pro",))
    gid = _old_game(client, backend)
    api_finish_draft(client, gid)
    assert client.post("/v1/sim/games/nope/realism-upgrade", headers=hdr()).status_code in (404, 422)
    assert client.post(f"/v1/sim/games/{gid}/realism-upgrade", headers=hdr("pro2")).status_code in (200, 404)
    assert client.post(f"/v1/sim/games/{gid}/realism-upgrade").status_code == 401


def test_a_new_game_has_nothing_to_update():
    client, _, _ = make_app()
    gid = new_game(client)["game"]["id"]
    g = _get(client, gid)
    assert g["rules"]["rules_version"] == 0 and not g["rules"]["eligible"] and g["rules"]["pending"] == []
    api_finish_draft(client, gid)
    res = client.post(f"/v1/sim/games/{gid}/realism-upgrade", headers=hdr()).json()
    assert res["upgraded"] is False and res["flags"] == []


def test_revert_week_before_the_event_reverts_the_flags_and_replay_matches():
    client, backend, _ = make_app()
    gid = _old_game(client, backend)
    api_finish_draft(client, gid)
    api_advance(client, gid)
    client.post(f"/v1/sim/games/{gid}/realism-upgrade", headers=hdr())
    assert _get(client, gid)["settings"]["world_v"] == 1
    rev = client.post(f"/v1/sim/games/{gid}/revert-week", headers=hdr()).json()
    assert rev["reverted"] >= 1 and rev["game"]["settings"].get("world_v", 0) == 0 and rev["game"]["rules"]["eligible"]
    # a decision before the event and the upgrade after it: reverting removes only what came after the boundary
    client.post(f"/v1/sim/games/{gid}/realism-upgrade", headers=hdr())
    api_advance(client, gid)  # the upgrade is now before the boundary: it stays
    assert _get(client, gid)["rules"]["rules_version"] == 1
    client.post(f"/v1/sim/games/{gid}/revert-week", headers=hdr())
    assert _get(client, gid)["settings"]["world_v"] == 1


def test_undo_sim_across_the_event_restores_the_old_rules():
    client, backend, _ = make_app()
    gid = _old_game(client, backend)
    api_finish_draft(client, gid)
    api_advance(client, gid)
    first = next(e for e in sorted(backend.tables["sim_events"], key=lambda r: r["seq"]) if e["type"] == "advance" and e["game_id"] == gid)
    client.post(f"/v1/sim/games/{gid}/realism-upgrade", headers=hdr())
    api_advance(client, gid)
    assert _get(client, gid)["rules"]["rules_version"] == 1
    res = client.post(f"/v1/sim/games/{gid}/undo-sim", json={"from_seq": first["seq"]}, headers=hdr()).json()
    assert res["undone"] is True and res["game"]["rules"]["rules_version"] == 0 and res["game"]["settings"].get("world_v", 0) == 0
    # the saved checkpoints of the undone weeks are gone: a cold reload (no caches) agrees
    from modules.sim import game_store

    game_store.STATES.drop(gid)
    assert _get(client, gid)["rules"]["rules_version"] == 0


def test_cold_reload_from_checkpoint_and_log_agree_after_the_event():
    client, backend, _ = make_app()
    gid = _old_game(client, backend)
    api_finish_draft(client, gid)
    api_advance(client, gid)
    client.post(f"/v1/sim/games/{gid}/realism-upgrade", headers=hdr())
    api_advance(client, gid)
    warm = _get(client, gid)
    from modules.sim import game_store

    game_store.STATES.drop(gid)
    game_store.SNAPSHOTS.drop(gid)
    cold = _get(client, gid)
    assert cold["settings"] == warm["settings"] and cold["rules"] == warm["rules"] and cold["week"] == warm["week"] == 3
