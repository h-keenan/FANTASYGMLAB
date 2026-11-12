"""One-tap rest-of-season forecast for the user's real league.

Pure (stdlib + numpy + modules.sim): takes a frozen ``LeagueSnapshot`` and
replays the remaining schedule many times with the user on their current
roster and an auto-set lineup (no trades, no waiver moves), so the odds answer
"as of today, on current rosters, rest of season". The seeds are fixed, so the
same snapshot always gives the same forecast.

Swing factors come from the same engine, never from real logic:
- a key game: the playoff odds conditional on winning vs losing it, read off
  the baseline samples;
- working the wire / trading: the same seeds replayed with the user's auto-GM
  switched on, compared paired against the baseline run.
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
MAX_FACTORS = 3
GAME_LOOKAHEAD = 4
MIN_BRANCH = 8  # samples needed on each side of a game before its swing is trusted
MIN_GAME_SWING = 0.05
MIN_MOVE_PLAYOFF_GAIN = 0.03
MIN_MOVE_TITLE_GAIN = 0.015

BASELINE = Strategy(trade_aggressiveness=0.0, waiver_aggressiveness=0.0, lineup_auto_set=True)
WIRE = replace(BASELINE, waiver_aggressiveness=1.0)
TRADES = replace(BASELINE, trade_aggressiveness=0.75)


def _score(outcome: SeasonOutcome) -> dict[str, Any]:
    user = outcome.user
    return {
        "wins": user["wins"] + 0.5 * user["ties"],
        "seed": int(user["seed"]),
        "playoffs": bool(user["made_playoffs"]),
        "title": user["playoff_result"] == "champion",
        "final": user["playoff_result"] in ("champion", "runner_up"),
    }


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    return sum(1 for r in rows if r[key]) / len(rows) if rows else 0.0


def _pct(values: list[float], q: float) -> float:
    return float(np.percentile(values, q))


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
        who = names.get(opponent, "your opponent")
        factors.append({
            "kind": "game", "week": week,
            "title": f"Week {week} vs {who}",
            "detail": (
                f"Win and your playoff odds are about {round(p_win * 100)}%; lose and they fall to "
                f"about {round(p_loss * 100)}%."
            ),
            "playoff_delta": round(swing, 3), "title_delta": round(t_win - t_loss, 3),
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
    if p_gain < MIN_MOVE_PLAYOFF_GAIN and t_gain < MIN_MOVE_TITLE_GAIN:
        return None
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
        "detail": detail, "playoff_delta": round(p_gain, 3), "title_delta": round(t_gain, 3),
        "players": players,
    }


def build_forecast(snapshot: LeagueSnapshot, *, samples: int = BASE_SAMPLES, scenario_samples: int = SCENARIO_SAMPLES) -> dict[str, Any]:
    user = snapshot.user_team
    outcomes = [simulate_season(snapshot, BASELINE, seed) for seed in range(1, samples + 1)]
    scores = [_score(o) for o in outcomes]
    n_teams = len(snapshot.teams)
    wins = [s["wins"] for s in scores]
    seeds = [s["seed"] for s in scores]
    games = int(outcomes[0].user["games"]) if outcomes else 0
    played = user.wins + user.losses + user.ties
    total_games = played + games
    mean_wins = float(np.mean(wins))
    seed_counts = Counter(seeds)
    median_finish = int(round(float(np.median(seeds))))

    factors = _game_factors(snapshot, outcomes, scores)
    m = min(scenario_samples, samples)
    for kind, strategy in (("waiver", WIRE), ("trade", TRADES)):
        scenario = [simulate_season(snapshot, strategy, seed) for seed in range(1, m + 1)]
        factor = _move_factor(kind, scores, scenario, user.tid)
        if factor:
            factors.append(factor)
    factors.sort(key=lambda f: -(abs(f["playoff_delta"]) + 0.5 * abs(f["title_delta"])))

    return {
        "samples": samples,
        "start_week": snapshot.settings.start_week,
        "regular_season_end": snapshot.settings.regular_season_end,
        "weeks_remaining": games,
        "team": {"team_id": user.tid, "name": user.name},
        "current": {"wins": user.wins, "losses": user.losses, "ties": user.ties},
        "odds": {
            "playoffs": round(_rate(scores, "playoffs"), 3),
            "finals": round(_rate(scores, "final"), 3),
            "title": round(_rate(scores, "title"), 3),
            "playoff_spots": snapshot.settings.playoff_teams,
        },
        "record": {
            "wins": round(mean_wins, 1),
            "losses": round(total_games - mean_wins - user.ties, 1),
            "wins_low": round(_pct(wins, 10), 1),
            "wins_high": round(_pct(wins, 90), 1),
            "projected": f"{int(round(mean_wins))}-{int(round(total_games - round(mean_wins) - user.ties))}",
            "games": total_games,
        },
        "finish": {
            "median": median_finish,
            "low": int(round(_pct(seeds, 10))),
            "high": int(round(_pct(seeds, 90))),
            "teams": n_teams,
            "distribution": [
                {"finish": f, "probability": round(seed_counts.get(f, 0) / len(seeds), 3)} for f in range(1, n_teams + 1)
            ],
        },
        "swing_factors": factors[:MAX_FACTORS],
    }
