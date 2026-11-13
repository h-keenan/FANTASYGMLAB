"""The GM game running on the calibrated player model: injuries have one source of truth
(the model's season profile), whole-season scoring is sane, and resume == replay."""

from __future__ import annotations

import collections
import re
from pathlib import Path

import numpy as np
import pytest

from modules.sim import game_scoring, player_model
from modules.sim.game_eval import Evaluator
from modules.sim.game_engine import session_for
from tests import test_sim_isolation as iso
from tests.test_sim_game_engine import _persisted, season

SEED = 11


@pytest.fixture(scope="module")
def played():
    iso._audit_state.update(active=True, writes=[])
    result = season(SEED)
    iso._audit_state["active"] = False
    return result, list(iso._audit_state["writes"])


def test_the_real_player_model_is_the_default():
    assert game_scoring.default_model().model_id == f"player_model-{player_model.MODEL_VERSION}"


# ------------------------------------------------------------------ adapter mapping


class _Prof:
    def __init__(self, mask, reasons):
        self.games_available_mask = tuple(mask)
        self.unavailable_reason = tuple(reasons)


def test_calendar_weeks_out_counts_a_bye_inside_the_window():
    mask = [True] * 17
    reason = [""] * 17
    for w, r in ((5, "injury"), (6, "bye"), (7, "injury")):  # hurt in week 4: out 5, bye 6, out 7
        mask[w - 1] = False
        reason[w - 1] = r
    prof = _Prof(mask, reason)
    assert game_scoring.calendar_weeks_out(prof, 4) == 3
    # a bye right after the injury and nothing else: not an injury absence
    mask2, reason2 = [True] * 17, [""] * 17
    mask2[4], reason2[4] = False, "bye"
    assert game_scoring.calendar_weeks_out(_Prof(mask2, reason2), 4) == 0
    assert game_scoring.calendar_weeks_out(_Prof(mask, reason), 12) == 0


def test_adapter_maps_every_model_field_explicitly():
    class Result:
        points, stats, active, injury_incurred = 12.5, {"rec": 4, "rec_yd": 61.0}, True, True

    class Module:
        MODEL_VERSION = "x"

        @staticmethod
        def draw_season_profile(player, rng):
            m, r = [True] * 17, [""] * 17
            m[4] = m[5] = False
            r[4] = r[5] = "injury"
            return _Prof(m, r)

        @staticmethod
        def draw_week_points(player, profile, week, rng, scoring):
            return Result

    model = game_scoring.PlayerModelAdapter(Module)
    prof = model.profile({}, None)
    res = model.week({}, prof, 4, None, {})
    assert (res.points, dict(res.stats), res.active, res.newly_injured, res.out_weeks) == (
        12.5, {"rec": 4.0, "rec_yd": 61.0}, True, True, 2)


# ------------------------------------------------------------------ whole game


def test_a_full_game_has_sane_league_wide_scoring(played):
    (snap, state, em, _), _writes = played
    assert state.status == "complete"
    kinds = collections.Counter(h["kind"] for h in state.history)
    assert kinds["regular"] == 14 and kinds["playoff"] >= 2
    scores = [p for h in state.history if h["kind"] == "regular" for g in h["games"] for p in (g["home_pts"], g["away_pts"])]
    assert 90 < np.mean(scores) < 135, np.mean(scores)           # 12-team PPR lineup
    assert 18 < np.std(scores) < 40
    assert min(scores) > 25 and max(scores) < 260
    wins = sorted(s["w"] for s in state.stand.values())
    assert wins[-1] - wins[0] >= 4 and wins[-1] <= 13            # a real spread, nobody perfect
    per_week = collections.Counter()
    for e in em.events:
        if e["type"] == "injury":
            per_week[e["week"]] += len(e["payload"]["items"])
    assert all(per_week[w] > 0 for w in range(1, 15))
    assert all(per_week[w] < 0.15 * len(snap.players) for w in per_week)


def test_ai_lineups_are_essentially_never_empty(played):
    """A vacant starting slot triggers an emergency waiver claim. The residue is real
    scarcity: every free kicker on a bye, or two starters hurt in the same week (a team
    makes one claim per week)."""

    (snap, state, em, _), _writes = played
    user = snap.user_team.tid
    rows = [e for e in em.events if e["type"] == "lineup_set" and e["payload"]["team"] != user]
    empties = [sum(1 for _s, pid in e["payload"]["slots"] if not pid) for e in rows]
    assert len(rows) >= 11 * 14
    assert sum(1 for n in empties if n) <= 0.04 * len(rows), sum(1 for n in empties if n)
    assert max(empties) <= 2


def test_injuries_come_from_the_model_and_every_view_agrees(played):
    """For every player and week: he scored iff the model's profile had him available
    (or it was the game he got hurt in), and the game's 'out N weeks' equals the model's."""

    (snap, state, em, _), _writes = played
    session = session_for(snap, SEED)
    hurt = {}
    for e in em.events:
        if e["type"] == "injury":
            for pid, weeks in e["payload"]["items"]:
                hurt[(pid, e["week"])] = weeks
                profile = session.profile(pid)
                assert any(ev.week == e["week"] for ev in profile.injury_events)
                assert weeks == game_scoring.calendar_weeks_out(profile, e["week"])
    assert hurt
    mismatches = []
    for pid, hist in state.points.items():
        if snap.players[pid].injury_weeks:
            continue  # started the season hurt: not the model's story
        mask = session.profile(pid).games_available_mask
        for week, pts in enumerate(hist, 1):
            if week <= len(mask) and (pts is not None) != bool(mask[week - 1]):
                mismatches.append((pid, week, pts, mask[week - 1]))
    assert not mismatches, mismatches[:5]


def test_resume_equals_replay_and_a_second_run_is_identical(played):
    (_, state, _, _), _writes = played
    store, gid, snap, final, _ = _persisted(SEED)
    assert store.load_state("u", gid, snap, use_checkpoint=True).digest() == store.load_state("u", gid, snap, use_checkpoint=False).digest() == final.digest()
    assert final.digest() == state.digest()


def test_a_full_game_writes_nothing_under_data(played):
    _, writes = played
    assert iso._writes_under_data(writes) == []


# ------------------------------------------------------------------ no hindsight leak


def test_user_facing_projections_never_use_the_hidden_season_outcome(played):
    (snap, state, em, _), _writes = played
    forbidden = re.compile(r"expected_points|season_multiplier|season_mean_ppg|\barchetype\b|injury_events|role_changes")
    for path in sorted(Path(game_scoring.__file__).parent.glob("game_*.py")):
        code = "\n".join(l for l in path.read_text().splitlines() if not l.lstrip().startswith("#"))
        assert not forbidden.search(code), (path.name, forbidden.search(code).group(0))
    # before any week is played, the projection a player sees is exactly the public preseason number
    fresh_snap = snap
    ev = Evaluator(fresh_snap, type(state)(fresh_snap))
    assert all(ev.base_mean(pid) == fresh_snap.players[pid].mean for pid in fresh_snap.pids)
    # with team roles the shown rest-of-season number is that public mean times a role factor from the public
    # depth chart and injury list only (no hidden profile); K and defenses are exempt
    assert all(ev.ros_mean(pid) == fresh_snap.players[pid].mean for pid in fresh_snap.pids if fresh_snap.players[pid].pos in ("K", "DEF"))
