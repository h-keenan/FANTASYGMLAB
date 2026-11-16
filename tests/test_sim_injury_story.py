"""injury_v 1 (every Sim injury has a type) and the player story timeline derived from the event log.

Owner asks: "What is this guy's story? Why did he go from QB2 to not getting playing time?" and "Sim injuries show only 'Out 4 wks'"."""

from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from modules.sim import game_dynasty as dyn
from modules.sim import game_scoring, injuries
from modules.sim import game_story as story
from modules.sim.game_draft import DraftContext, auto_for_user
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_eval import Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameSettings
from modules.sim.game_view import player_detail, player_row
from modules.sim.synthetic import build_synthetic_pool

ROWS, BYES = build_synthetic_pool(7)
MODEL = game_scoring.default_model().model_id


def _game(seed=31, **flags):
    d = GameSettings.parse({"mode": "dynasty", "teams": 8, "user_slot": 3, "start_year": 2026, "seasons": 3, "rookie_rounds": 3}).to_dict()
    d.pop("injury_v", None)
    d.update(flags)
    snap = build_snapshot(ROWS, BYES, GameSettings.from_dict(d), seed, scoring_model=MODEL)
    state = GameState(snap)
    em = Emitter(state, snap)
    auto_for_user(DraftContext(snap, state), em, seed)
    finish_draft(em, snap, state, seed)
    return snap, state, em, seed


def _play(snap, state, em, seed, weeks=None):
    n = 0
    while state.status in ("in_season", "playoffs") and (weeks is None or n < weeks):
        advance(em, snap, state, seed)
        n += 1


# ------------------------------------------------------------------------------------------------ the sampler


def _sample(pos, weeks, n=4000):
    rng = np.random.default_rng(5)
    return Counter(injuries.draw_injury_type(pos, weeks, float(u)) for u in rng.random(n))


def test_long_injuries_are_severe_types_and_short_ones_are_tweaks():
    assert [injuries.band_for(w) for w in (1, 2, 3, 5, 6, 8, 9, 17)] == ["minor", "minor", "moderate", "moderate", "major", "major", "severe", "severe"]
    severe = _sample("RB", 12)
    assert severe.most_common(1)[0][0] == "Torn ACL" and severe["Torn ACL"] / sum(severe.values()) > 0.2
    minor = _sample("RB", 1)
    assert "Torn ACL" not in minor and "Torn Achilles" not in minor
    assert {"Hamstring", "Ankle", "Concussion"} <= set(minor)


def test_position_shifts_the_odds():
    qb, wr, k = _sample("QB", 1), _sample("WR", 1), _sample("K", 1)
    share = lambda c, *names: sum(c[n] for n in names) / sum(c.values())
    assert share(qb, "Shoulder", "Hand") > 2 * share(wr, "Shoulder", "Hand")
    assert share(wr, "Hamstring") > 2 * share(qb, "Hamstring")
    assert share(k, "Quad", "Hip", "Groin") > 0.35 and k["Concussion"] < k["Quad"] / 10


def test_the_draw_is_a_pure_function_and_covers_the_unit_interval():
    assert injuries.draw_injury_type("QB", 4, 0.3) == injuries.draw_injury_type("QB", 4, 0.3)
    for u in (0.0, 0.5, 0.999999999, 1.0):
        assert injuries.draw_injury_type("TE", 10, u) in dict(injuries.TYPES["severe"])
    assert injuries.out_label("Hamstring", 4) == "Hamstring · out 4 wks" and injuries.out_label(None, 1) == "Out 1 wk"


# ------------------------------------------------------------------------------------------------ the flag


def test_new_games_carry_the_flag_and_old_ones_do_not():
    d = GameSettings.parse({"mode": "dynasty"}).to_dict()
    assert d["injury_v"] == 1
    old = GameSettings.from_dict({k: v for k, v in d.items() if k != "injury_v"})
    assert old.injury_v == 0 and "injury_v" not in old.to_dict()


def _injury_events(em):
    return [e for e in em.events if e["type"] == "injury"]


def test_an_injury_event_names_every_new_injury_only_when_on():
    snap, state, em, seed = _game(injury_v=1)
    _play(snap, state, em, seed)
    evs = _injury_events(em)
    assert evs
    for e in evs:
        kinds = e["payload"]["kinds"]
        assert {pid for pid, _ in e["payload"]["items"]} == set(kinds)
        for pid, weeks in e["payload"]["items"]:
            assert kinds[pid] in dict(injuries.weighted_types(snap.players[pid].pos, weeks))
    snap0, state0, em0, _ = _game(injury_v=0)
    _play(snap0, state0, em0, seed)
    assert all("kinds" not in e["payload"] for e in _injury_events(em0)) and state0.out_kind == {}


def test_naming_an_injury_moves_nothing_else():
    a = _game(injury_v=1)
    b = _game(injury_v=0)
    for snap, state, em, seed in (a, b):
        _play(snap, state, em, seed)
    assert a[1].points == b[1].points and a[1].history[-1]["games"] == b[1].history[-1]["games"]
    assert [e["payload"]["items"] for e in _injury_events(a[2])] == [e["payload"]["items"] for e in _injury_events(b[2])]


def test_the_type_shows_on_the_row_and_clears_when_he_is_back():
    snap, state, em, seed = _game(injury_v=1)
    state_ids = {}
    for _ in range(snap.settings.regular_weeks):
        advance(em, snap, state, seed)
        ev = Evaluator(snap, state)
        owners = state.owner_map()
        for pid, left in state.out.items():
            if pid in state.out_kind:
                row = player_row(snap, state, ev, pid, owners)
                assert row["injury"] == state.out_kind[pid] and row["injury_label"] == f"{row['injury']} · out {left} wk{'' if left == 1 else 's'}"
                state_ids[pid] = row["injury"]
        assert set(state.out_kind) <= set(state.out)
        if state.status != "in_season":
            break
    assert state_ids
    healthy = next(p for p in snap.players if p not in state.out)
    assert "injury" not in player_row(snap, state, Evaluator(snap, state), healthy, state.owner_map())


def test_a_save_without_the_flag_has_no_type_anywhere():
    snap, state, em, seed = _game(injury_v=0)
    _play(snap, state, em, seed, weeks=6)
    ev, owners = Evaluator(snap, state), state.owner_map()
    for pid in state.out:
        assert "injury" not in player_row(snap, state, ev, pid, owners)
    assert state.out_kind == {}


# ------------------------------------------------------------------------------------------------ the story


def _ev(type_, payload, week=0):
    return {"type": type_, "week": week, "payload": payload}


def _pids(snap, pos, n):
    return [p for p in snap.pids if snap.players[p].pos == pos][:n]


def test_the_story_reads_depth_moves_injuries_and_trades_in_plain_language():
    snap, state, em, seed = _game(injury_v=1, incumbent_v=1)
    root = snap.root
    me, other = _pids(snap, "QB", 2)
    team = snap.players[me].nfl_team
    events = [
        _ev("depth_chart", {"season_no": 1, "year": 2026, "phase": "offseason", "changes": [
            {"nfl_team": team, "pos": "QB", "slot": 1, "pid": other, "replaced_pid": me, "reason": "rookie_won_job", "gap": 1.5, "needed": 1.2, "incumbent_season": "down"}]}),
        _ev("injury", {"items": [[me, 4]], "kinds": {me: "Hamstring"}}, week=3),
        _ev("trade", {"team_a": snap.user_team.tid, "team_b": snap.tids[0], "give": [me], "get": [other]}, week=5),
        _ev("depth_chart", {"season_no": 1, "year": 2026, "phase": "in_season", "changes": [
            {"nfl_team": team, "pos": "QB", "slot": 1, "pid": me, "replaced_pid": other, "reason": "returned_from_injury"}]}, week=8),
    ]
    view = story.player_view(root, events, me)
    lines = [(e["kind"], e["text"], e["tone"]) for e in view["story"]]
    short = story.short_name(snap.players[other].name)
    assert ("depth", f"Lost the {team} QB1 starting job to {short} (rookie won the job)", "bad") in lines
    assert any(k == "injury" and t.startswith("Hamstring in Week 3: out 4 weeks") for k, t, _ in lines)
    assert any(k == "traded" and "Traded from" in t for k, t, _ in lines)
    assert any(k == "depth" and t.startswith(f"Back from injury: retook the {team} QB1 job from {short}") for k, t, _ in lines)
    # the timeline is ordered by season, then week; the season line closes the season
    order = [(e["season"], e["week"]) for e in view["story"]]
    assert order == sorted(order)
    assert view["story"][-1]["kind"] == "season" or view["story"][-1]["week"] <= 99
    # the other player's side of the same event
    other_lines = [e["text"] for e in story.player_view(root, events, other)["story"] if e["kind"] == "depth"]
    assert f"Took the {team} QB1 job from {story.short_name(snap.players[me].name)} (rookie won the job)" in other_lines


def test_a_backup_who_never_plays_is_explained_by_who_is_ahead():
    snap, state, em, seed = _game(injury_v=1)
    _play(snap, state, em, seed)
    root = snap.root
    book = Evaluator(snap, state).book
    key = next(k for k, ms in book.groups.items() if k[1] == "QB" and len(ms) >= 3)
    third = book.groups[key][2].pid
    seasons = [e for e in story.player_view(root, em.events, third)["story"] if e["kind"] == "season"]
    assert seasons and seasons[0]["role"] == "QB3"
    line = seasons[0]["text"]
    if seasons[0]["games"] == 0:
        assert "did not play" in line and "behind " in line
    else:
        assert "pts" in line


def test_a_season_line_has_role_points_and_a_big_season_tag():
    snap, state, em, seed = _game(injury_v=1)
    _play(snap, state, em, seed)
    top = max((p for p in snap.players if snap.players[p].pos == "QB"), key=lambda p: sum(g for g in state.points.get(p, []) if g is not None))
    (line,) = [e for e in story.player_view(snap.root, em.events, top)["story"] if e["kind"] == "season"]
    assert line["games"] > 0 and line["points"] > 0 and f"{line['points']} pts" in line["text"] and line["pos_rank"] == 1
    assert "big season: QB1" in line["text"] and line["tone"] == "good" and line["role"].startswith("QB")


def test_the_injury_record_counts_games_missed_per_season_and_career():
    snap, _, _, _ = _game(injury_v=1)
    me = _pids(snap, "RB", 1)[0]
    events = [
        _ev("injury", {"items": [[me, 3]], "kinds": {me: "Ankle"}}, week=2),
        _ev("injury", {"items": [[me, 20]], "kinds": {me: "Torn ACL"}}, week=10),  # capped by the regular season
        _ev("week_scored", {"kind": "regular", "games": [], "points": {}, "alive_next": [], "eliminated": {}}, week=10),
    ]
    rec = story.player_view(snap.root, events, me)["injuries"]
    regular = snap.settings.regular_weeks
    (s,) = rec["seasons"]
    assert s["season"] == 2026 and [x["injury"] for x in s["stints"]] == ["Ankle", "Torn ACL"]
    assert s["stints"][0] == {"start_week": 3, "end_week": 5, "games_missed": 3, "injury": "Ankle"}
    assert s["stints"][1]["games_missed"] == regular - 10 and s["games_missed"] == 3 + regular - 10
    assert rec["career_games_missed"] == s["games_missed"] and rec["ok"]
    cur = rec["current"]
    assert cur["unavailable"] and cur["line"] == f"Torn ACL · out {19} wks"  # one week has been played since


def test_no_injuries_is_a_clean_record():
    snap, _, _, _ = _game(injury_v=1)
    rec = story.player_view(snap.root, [], next(iter(snap.players)))["injuries"]
    assert rec["current"] is None and rec["seasons"] == [] and rec["career_games_missed"] == 0 and rec["since_season"] is None


def test_the_sim_depth_chart_is_the_teams_own_order_with_injuries_marked():
    snap, state, em, seed = _game(injury_v=1)
    ev = Evaluator(snap, state)
    key = next(k for k, ms in ev.book.groups.items() if k[1] == "WR" and len(ms) >= 3)
    pid = ev.book.groups[key][1].pid
    chart = story.depth_chart_view(snap, state, ev, pid)
    assert chart["ok"] and chart["team"] == key[0] and chart["slot"] == "WR" and chart["self_order"] == 2
    assert [e["order"] for e in chart["entries"]] == list(range(1, len(chart["entries"]) + 1)) and chart["total"] == len(chart["entries"])
    assert [e["is_self"] for e in chart["entries"]].count(True) == 1
    state.out[chart["entries"][0]["player_id"]] = 4
    state.out_kind[chart["entries"][0]["player_id"]] = "Hamstring"
    again = story.depth_chart_view(snap, state, ev, pid)
    assert again["entries"][0]["injury_status"] == "Hamstring · out 4 wks" and again["entries"][0]["status"] == "out"
    kicker = next(p for p in snap.players if snap.players[p].pos == "K")
    assert story.depth_chart_view(snap, state, ev, kicker) is None
    assert player_detail(snap, state, pid)["depth_chart"]["self_order"] == 2
    assert "depth_chart" not in player_detail(snap, state, kicker)


def test_the_notification_names_the_injury():
    from modules.sim import game_notifications as notes

    snap, state, em, seed = _game(injury_v=1)
    user = snap.user_team.tid
    _play(snap, state, em, seed, weeks=10)
    mine = {e["payload"]["kinds"][pid] for e in _injury_events(em) for pid, _ in e["payload"]["items"] if state.where(user, pid) is not None}
    heads = [i["headline"] for i in notes.derive(snap, state, em.events, 0, limit=200)["items"] if i["kind"] == "injury"]
    assert mine and heads and {h.split(":")[0] for h in heads} <= mine
