"""A deterministic fake league: used by tests and local dev so the engine can be
exercised without any real data. Never used for a real user's world."""

from __future__ import annotations

import numpy as np

from modules.sim.types import LeagueSettings, LeagueSnapshot, SimPlayer, SimTeam

_ROSTER_SHAPE = {"QB": 3, "RB": 7, "WR": 8, "TE": 3, "K": 1}
_BASE_MEAN = {"QB": 19.0, "RB": 13.0, "WR": 12.5, "TE": 9.0, "K": 7.5}
_MARKET_PER_POINT = {"QB": 4.0, "RB": 5.0, "WR": 5.5, "TE": 6.0, "K": 2.0}
NFL_TEAMS = ["BUF", "MIA", "NE", "NYJ", "BAL", "CIN", "CLE", "PIT", "DAL", "NYG", "PHI", "WAS", "SF", "SEA", "LAR", "ARI"]


def round_robin(tids: list[str], weeks: int) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Circle-method schedule, repeated to fill ``weeks``."""

    teams = list(tids)
    if len(teams) % 2:
        teams.append("")
    n = len(teams)
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = teams[i], teams[n - 1 - i]
            if a and b:
                pairs.append((a, b) if r % 2 == 0 else (b, a))
        rounds.append(tuple(pairs))
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return tuple(rounds[w % len(rounds)] for w in range(weeks))


def build_synthetic_snapshot(
    seed: int = 7,
    *,
    teams: int = 12,
    weeks: int = 14,
    start_week: int = 1,
    slots: tuple[str, ...] = ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K"),
    playoff_teams: int = 6,
) -> LeagueSnapshot:
    rng = np.random.default_rng(seed)
    players: dict[str, SimPlayer] = {}
    pool: list[str] = []
    counter = 0

    def make(pos: str) -> str:
        nonlocal counter
        counter += 1
        pid = f"p{counter:04d}"
        mean = float(max(2.0, _BASE_MEAN[pos] + rng.normal(0, 4.5)))
        age = float(np.clip(rng.normal(26.5, 3.0), 21, 36))
        market = float(np.clip(mean * _MARKET_PER_POINT[pos] * (1.0 + (27 - age) * 0.03) + rng.normal(0, 6), 1, 100))
        players[pid] = SimPlayer(
            pid=pid, name=f"{pos} Player {counter}", pos=pos, nfl_team=NFL_TEAMS[counter % len(NFL_TEAMS)],
            age=round(age, 1), market=round(market, 1), mean=round(mean, 2),
            sd=round(max(2.0, mean * 0.42), 2),
        )
        pool.append(pid)
        return pid

    rosters: list[list[str]] = [[] for _ in range(teams)]
    for pos, per_team in _ROSTER_SHAPE.items():
        for _ in range(per_team):
            for t in range(teams):
                rosters[t].append(make(pos))
    free_agents = [make(pos) for pos in ("QB", "RB", "RB", "RB", "RB", "WR", "WR", "WR", "WR", "TE", "TE", "K") * 3]
    # free agents are, by construction, lower-end: shave their projection
    for pid in free_agents:
        p = players[pid]
        players[pid] = SimPlayer(
            pid=p.pid, name=p.name, pos=p.pos, nfl_team=p.nfl_team, age=p.age,
            market=round(p.market * 0.35, 1), mean=round(p.mean * 0.7, 2), sd=p.sd,
        )
    tids = [str(i + 1) for i in range(teams)]
    team_objs = tuple(
        SimTeam(tid=tid, name=f"Team {tid}", owner=f"owner{tid}", is_user=(i == 0), roster=tuple(r))
        for i, (tid, r) in enumerate(zip(tids, rosters))
    )
    schedule = round_robin(tids, weeks - start_week + 1)
    settings = LeagueSettings(
        slots=slots, start_week=start_week, regular_season_end=weeks, playoff_teams=playoff_teams,
        trade_deadline_week=max(start_week, int(weeks * 0.7)), league_name="Synthetic League", season="2026",
    )
    return LeagueSnapshot(
        league_id="synthetic", settings=settings, teams=team_objs, players=players,
        free_agents=tuple(free_agents), schedule=schedule, mode="full",
    )
