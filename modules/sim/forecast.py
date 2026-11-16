"""One-tap rest-of-season forecast for the user's real league.

Pure (stdlib + numpy + modules.sim): takes a frozen ``LeagueSnapshot`` and the
league's shared playoff-odds row.

There is exactly ONE playoff-odds number in the product
(docs/decisions/one-playoff-odds.md): the Roster-Power Monte Carlo
(``modules.playoff_simulator``), handed in as ``shared_odds``. The forecast
never computes its own odds, record or finish; it echoes the shared row so
Season Outlook can never disagree with GM Plan, Dashboard or Trade Odds.

What this engine adds is the *swing factors*: relative questions the shared
model cannot answer ("what if I win week 9?", "what if I work the wire?"),
answered by replaying the remaining schedule with the user's auto-set lineup
on fixed seeds:
- a key game: playoff odds conditional on winning vs losing it, read off the
  baseline samples;
- working the wire / trading: the same seeds replayed with the user's auto-GM
  switched on, compared paired against the baseline run.
Only the DIFFERENCE is reported, and only when it clears its own sampling
noise (``NOISE_Z`` standard errors); anything smaller is labeled "small" and
carries no number.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any

import numpy as np

from modules.sim.engine import SeasonOutcome, simulate_season
from modules.sim.types import LeagueSnapshot, Strategy

BASE_SAMPLES = 80
SCENARIO_SAMPLES = 30
# Cost scales with weeks left, so long horizons (an offseason full-season
# forecast, an early-season league) get fewer replays: a budget of simulated
# weeks, clamped so the odds stay stable (playoff odds within about +-7 points at the 48-sample floor, tighter above it).
BASE_WEEK_BUDGET = 560
SCENARIO_WEEK_BUDGET = 210
MIN_BASE_SAMPLES = 48
MIN_SCENARIO_SAMPLES = 20


def sample_plan(weeks: int) -> tuple[int, int]:
    """(baseline replays, replays per what-if scenario) for a horizon of ``weeks`` games."""

    weeks = max(1, weeks)
    base = max(MIN_BASE_SAMPLES, min(BASE_SAMPLES, BASE_WEEK_BUDGET // weeks))
    scenario = max(MIN_SCENARIO_SAMPLES, min(SCENARIO_SAMPLES, SCENARIO_WEEK_BUDGET // weeks))
    return base, scenario
MAX_FACTORS = 3
GAME_LOOKAHEAD = 4
MIN_BRANCH = 8  # samples needed on each side of a game before its swing is trusted
MIN_GAME_SWING = 0.05
# A swing is "real" only when it is at least this many standard errors of its
# own estimate (about a 95% bound); a smaller one is reported as "small", with
# no number, because the replays cannot tell it from zero.
NOISE_Z = 2.0

BASELINE = Strategy(trade_aggressiveness=0.0, waiver_aggressiveness=0.0, lineup_auto_set=True)
WIRE = replace(BASELINE, waiver_aggressiveness=1.0)
TRADES = replace(BASELINE, trade_aggressiveness=0.75)


def _score(outcome: SeasonOutcome) -> dict[str, Any]:
    user = outcome.user
    return {
        "playoffs": bool(user["made_playoffs"]),
        "title": user["playoff_result"] == "champion",
    }


def paired_standard_error(base: list[int], scenario: list[int]) -> float:
    """Standard error of the mean paired difference ``scenario - base``.

    The same seeds drive both runs, so each replay's difference is one
    observation; this is the noise on the reported change in odds, which is
    much tighter than two independent estimates when the runs are correlated.
    """

    n = min(len(base), len(scenario))
    if n < 2:
        return 1.0
    diffs = np.array([scenario[i] - base[i] for i in range(n)], dtype=float)
    return float(np.std(diffs, ddof=1) / np.sqrt(n))


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    return sum(1 for r in rows if r[key]) / len(rows) if rows else 0.0


def _user_results_by_week(outcome: SeasonOutcome, tid: str) -> dict[int, tuple[str, bool] | None]:
    """week -> (opponent tid, user won) for each regular-season game the user plays."""

    out: dict[int, tuple[str, bool] | None] = {}
    for week in outcome.weekly:
        for game in week["games"]:
            if tid not in (game["home"], game["away"]):
                continue
            home = game["home"] == tid
            mine, theirs = (game["home_pts"], game["away_pts"]) if home else (game["away_pts"], game["home_pts"])
            opp = game["away"] if home else game["home"]
            out[week["week"]] = None if mine == theirs else (opp, mine > theirs)
    return out


def _game_factors(
    snapshot: LeagueSnapshot, outcomes: list[SeasonOutcome], scores: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    tid = snapshot.user_team.tid
    names = {t.tid: t.name for t in snapshot.teams}
    per_sample = [_user_results_by_week(o, tid) for o in outcomes]
    weeks = sorted({w for r in per_sample for w in r})[:GAME_LOOKAHEAD]
    factors: list[dict[str, Any]] = []
    for week in weeks:
        wins, losses = [], []
        opponent = ""
        for result, score in zip(per_sample, scores):
            cell = result.get(week)
            if cell is None:
                continue
            opponent = cell[0]
            (wins if cell[1] else losses).append(score)
        if len(wins) < MIN_BRANCH or len(losses) < MIN_BRANCH:
            continue
        p_win, p_loss = _rate(wins, "playoffs"), _rate(losses, "playoffs")
        t_win, t_loss = _rate(wins, "title"), _rate(losses, "title")
        swing = p_win - p_loss
        if swing < MIN_GAME_SWING:
            continue
        # Win and loss branches are different replays (unpaired): SE of a difference of two rates.
        se = float(np.sqrt(p_win * (1 - p_win) / len(wins) + p_loss * (1 - p_loss) / len(losses)))
        small = swing < NOISE_Z * se
        who = names.get(opponent, "your opponent")
        factors.append({
            "kind": "game", "week": week,
            "title": f"Week {week} vs {who}",
            "detail": (
                "Winning this one helps your playoff odds a little, but the effect is within the simulation's noise."
                if small
                else f"Winning this one is worth about {round(swing * 100)} points of playoff odds compared with losing it."
            ),
            "playoff_delta": None if small else round(swing, 3),
            "title_delta": None if small else round(t_win - t_loss, 3),
            "small": small, "noise": round(se, 3),
            "players": [],
        })
    return factors


def _label(asset: dict[str, Any] | None) -> str:
    if not asset:
        return "a player"
    name = asset.get("name") or asset.get("label") or "a pick"
    return f"{name} ({asset['pos']})" if asset.get("pos") else str(name)


def _labels(assets: list[dict[str, Any]]) -> str:
    return " + ".join(_label(a) for a in assets) or "nothing"


def _move_factor(
    kind: str, base: list[dict[str, Any]], scenario: list[SeasonOutcome], tid: str
) -> dict[str, Any] | None:
    scen = [_score(o) for o in scenario]
    n = len(scen)
    base = base[:n]
    p_gain = _rate(scen, "playoffs") - _rate(base, "playoffs")
    t_gain = _rate(scen, "title") - _rate(base, "title")
    p_se = paired_standard_error([int(r["playoffs"]) for r in base], [int(r["playoffs"]) for r in scen])
    t_se = paired_standard_error([int(r["title"]) for r in base], [int(r["title"]) for r in scen])
    p_real = p_gain > 0 and p_gain >= NOISE_Z * p_se
    t_real = t_gain > 0 and t_gain >= NOISE_Z * t_se
    if p_gain <= 0 and t_gain <= 0:
        return None
    small = not (p_real or t_real)
    events = [e for o in scenario for e in o.events if e.get("involves_user") and e["type"] == kind]
    if not events:
        return None
    if kind == "waiver":
        # Most frequently chosen pickup, ties broken by how much the engine liked it.
        tally: Counter[str] = Counter(e["add"]["player_id"] for e in events)
        top_pid = max(tally, key=lambda p: (tally[p], sum(e["gain"] for e in events if e["add"]["player_id"] == p)))
        sample = next(e for e in events if e["add"]["player_id"] == top_pid)
        players = [_label(sample["add"])]
        title = f"Work the waiver wire: {players[0]}"
        detail = "Pickups like this can help when your lineup has a weak spot, but the effect is too small to measure reliably."
        if not small:
            detail = "Pickups like this lift your playoff odds when your lineup has a weak spot."
    else:
        def key(e: dict[str, Any]) -> str:
            gives, gets = (e["gives"], e["gets"]) if e["team"] == tid else (e["gets"], e["gives"])
            return "|".join(sorted(a.get("player_id") or a.get("label", "") for a in gives)) + ">" + "|".join(
                sorted(a.get("player_id") or a.get("label", "") for a in gets)
            )

        tally = Counter(key(e) for e in events)
        top = max(tally, key=lambda k: tally[k])
        sample = next(e for e in events if key(e) == top)
        gives, gets = (sample["gives"], sample["gets"]) if sample["team"] == tid else (sample["gets"], sample["gives"])
        players = [_labels(gets)]
        title = f"Make a trade: get {_labels(gets)}"
        detail = f"One way it shows up: send {_labels(gives)}."
        if any(a.get("kind") == "pick" for a in gives + gets):
            detail += " Draft picks carry no on-field value this season, so their future worth is not counted."
    return {
        "kind": "waiver" if kind == "waiver" else "trade", "week": None, "title": title,
        "detail": detail,
        "playoff_delta": None if small else round(p_gain, 3),
        "title_delta": None if small else round(t_gain, 3),
        "small": small, "noise": round(p_se, 3),
        "players": players,
    }


def _shared_record(user: Any, shared: dict[str, Any]) -> dict[str, Any]:
    """Projected record from the shared model's medians (never a second estimate)."""

    wins = int(shared.get("median_final_wins") or 0)
    losses = int(shared.get("median_final_losses") or 0)
    return {"wins": wins, "losses": losses, "projected": f"{wins}-{losses}", "games": wins + losses + user.ties}


def build_forecast(
    snapshot: LeagueSnapshot,
    shared_odds: dict[str, Any],
    *,
    samples: int | None = None,
    scenario_samples: int | None = None,
) -> dict[str, Any]:
    """``shared_odds`` is the user's row of the league's shared playoff-odds result
    (``modules.playoff_simulator``: playoff_probability / title_probability in percent,
    median_final_wins / median_final_losses / median_seed, clinched / eliminated)."""

    user = snapshot.user_team
    horizon = max(1, min(len(snapshot.schedule), snapshot.settings.regular_season_end - snapshot.settings.start_week + 1))
    planned_base, planned_scenario = sample_plan(horizon)
    samples = planned_base if samples is None else samples
    scenario_samples = planned_scenario if scenario_samples is None else scenario_samples
    outcomes = [simulate_season(snapshot, BASELINE, seed) for seed in range(1, samples + 1)]
    scores = [_score(o) for o in outcomes]
    games = int(outcomes[0].user["games"]) if outcomes else 0

    factors = _game_factors(snapshot, outcomes, scores)
    m = min(scenario_samples, samples)
    for kind, strategy in (("waiver", WIRE), ("trade", TRADES)):
        scenario = [simulate_season(snapshot, strategy, seed) for seed in range(1, m + 1)]
        factor = _move_factor(kind, scores, scenario, user.tid)
        if factor:
            factors.append(factor)
    # Real swings first (largest first), then the "small" ones.
    factors.sort(key=lambda f: (f["small"], -(abs(f["playoff_delta"] or 0.0) + 0.5 * abs(f["title_delta"] or 0.0))))

    title = shared_odds.get("title_probability")
    return {
        "samples": samples,
        "start_week": snapshot.settings.start_week,
        "regular_season_end": snapshot.settings.regular_season_end,
        "weeks_remaining": games,
        "team": {"team_id": user.tid, "name": user.name},
        "current": {"wins": user.wins, "losses": user.losses, "ties": user.ties},
        "odds": {
            "playoffs": round(float(shared_odds.get("playoff_probability") or 0.0) / 100.0, 3),
            "title": round(float(title) / 100.0, 3) if title is not None else None,
            "playoff_spots": snapshot.settings.playoff_teams,
            "clinched": bool(shared_odds.get("clinched")),
            "eliminated": bool(shared_odds.get("eliminated")),
        },
        "record": _shared_record(user, shared_odds),
        "finish": {"median": int(shared_odds.get("median_seed") or 0), "teams": len(snapshot.teams)},
        "swing_factors": factors[:MAX_FACTORS],
    }
