"""Build a game's frozen snapshot: the player pool with draft values, the 12
(or 8/10) teams with personas, the schedule, bye weeks.

Pure and deterministic given ``(rows, bye_weeks, settings, seed)``. The rows
come from an adapter (``inputs.player_pool`` for real data, ``synthetic`` for
tests); nothing here reads real data.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


from modules.sim.game_mode import DEFAULT_ROOKIE_ROUNDS, DEFAULT_SEASONS, DYNASTY_VERSION, PICK_YEARS
from modules.sim.game_types import (
    FLEX_SHARE,
    RESERVE_VERSION,
    POOL_CAPS,
    SINGLETON_POSITIONS,
    START_LEAGUE,
    GamePlayer,
    GameSettings,
    GameSnapshot,
    GameTeam,
    LeagueImport,
    scoring_label,
)
from modules.sim.personas import assign_personas
from modules.sim.rng import WorldRng
from modules.sim.synthetic import round_robin
from modules.sim.types import GAME_POSITIONS, SimInputsError, SimPick

TEAM_NAMES = (
    "Gridiron Ghosts", "Blitz Brigade", "Red Zone Rascals", "Hail Mary Heroes", "Pocket Aces",
    "Backfield Bandits", "Sunday Scaries", "Dynasty Dogs", "The Waiver Wolves", "Fourth & Long",
    "Bye Week Bandits", "Trade Deadline Titans", "Flex Appeal", "Touchdown Tonic", "End Zone Elite",
    "Playoff Pretenders", "The Auditors", "Sleeper Cell", "Bench Mob", "Late Round Legends",
    "Snap Count Sharks", "Target Share Tigers", "Handcuff Heroes", "Boom or Bust",
    "Waiver Wire Wizards", "Goal Line Gamblers", "Garbage Time Gods", "Draft Day Dreamers",
    "Mud Dogs", "Prime Time Pythons", "Checkdown Charlies", "Two Minute Warning",
)
# Names the player can pick for a fresh league. AI teams never reuse the one chosen.
USER_TEAM_NAME_MAX = 40


def pick_random_team_name(seed: int) -> str:
    """A preset name for "Random", stable for a game's seed."""

    return TEAM_NAMES[int(WorldRng(seed).stream(0, "gsetup", 8).integers(0, len(TEAM_NAMES)))]


def _name_key(name: str) -> str:
    return " ".join(str(name).split()).casefold()
OWNER_NAMES = (
    "Dana Whitfield", "Marcus Bell", "Priya Nair", "Tomas Ortega", "Jules Archer", "Kenji Mori",
    "Rhea Collins", "Dmitri Volkov", "Hannah Brooks", "Luis Navarro", "Ines Duarte", "Colm Brady",
    "Sade Okafor", "Wes Holloway", "Mira Lindqvist", "Odell Grant", "Tessa Vance", "Rafael Quinn",
    "Noor Haddad", "Gus Palmer", "Yuki Tanaka", "Bea Mercer", "Idris Cole", "Frankie Doyle",
)
SYNTHETIC_BYE_FIRST_WEEK = 5
SYNTHETIC_BYE_LAST_WEEK = 14


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def finalize_pool(
    rows: Iterable[Mapping[str, Any]], settings: GameSettings, keep: Iterable[str] = ()
) -> dict[str, GamePlayer]:
    """Trim the raw rows to the fantasy-relevant pool and compute each player's
    one-season draft ``value`` (value over replacement blended with market) and
    ``adp`` (rank by that value).

    Only positions this league plays exist (no kickers without a K slot, no
    defenses without a DEF slot). ``keep`` are ids that must stay even if the
    position cap would trim them (an imported league's rostered players)."""

    positions = settings.pool_positions
    keep_ids = {str(k) for k in keep}
    best: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        pid = str(row.get("pid") or "")
        pos = str(row.get("pos") or "").upper()
        if not pid or pos not in positions or _num(row.get("mean")) <= 0:
            continue
        if pid not in best:
            best[pid] = row
    by_pos: dict[str, list[Mapping[str, Any]]] = {p: [] for p in positions}
    for pid in sorted(best):
        by_pos[str(best[pid]["pos"]).upper()].append(best[pid])
    kept: list[Mapping[str, Any]] = []
    for pos, rs in by_pos.items():
        rs.sort(key=lambda r: (-_num(r.get("market")), -_num(r.get("mean")), str(r["pid"])))
        kept.extend(rs[: POOL_CAPS[pos]])
        kept.extend(r for r in rs[POOL_CAPS[pos]:] if str(r["pid"]) in keep_ids)

    return value_pool(kept, settings, by_pos)


def value_pool(
    kept: list[Mapping[str, Any]], settings: GameSettings, by_pos: Mapping[str, list[Mapping[str, Any]]] | None = None
) -> dict[str, GamePlayer]:
    """Draft ``value`` and ``adp`` for an already-trimmed set of rows. Dynasty's
    later seasons reuse this on the aged pool so a player's one-season value
    follows his new projection."""

    if by_pos is None:
        by_pos = {p: [] for p in settings.pool_positions}
        for r in kept:
            by_pos.setdefault(str(r["pos"]).upper(), []).append(r)
    repl = replacement_levels(settings, by_pos)
    vor = {str(r["pid"]): max(0.0, _num(r["mean"]) - repl[str(r["pos"]).upper()]) for r in kept}
    max_vor = max(vor.values(), default=0.0) or 1.0
    max_market = max((_num(r.get("market")) for r in kept), default=0.0) or 1.0
    weight = settings.policy.vorp_weight
    raw_value = {
        str(r["pid"]): weight * 100.0 * vor[str(r["pid"])] / max_vor
        + (1.0 - weight) * 100.0 * _num(r.get("market")) / max_market
        for r in kept
    }
    order = sorted(raw_value, key=lambda p: (-raw_value[p], p))
    adp = {pid: float(i + 1) for i, pid in enumerate(order)}
    players: dict[str, GamePlayer] = {}
    for r in kept:
        pid = str(r["pid"])
        mean = _num(r["mean"])
        sd = _num(r.get("sd"))
        players[pid] = GamePlayer(
            pid=pid, name=str(r.get("name") or pid), pos=str(r["pos"]).upper(),
            nfl_team=str(r.get("nfl_team") or "FA"), age=_num(r.get("age"), 26.0) or 26.0,
            market=round(_num(r.get("market")), 2), mean=round(mean, 2),
            sd=round(sd if sd > 0 else max(2.0, mean * 0.42), 2), adp=adp[pid],
            value=round(raw_value[pid], 2), injury_weeks=int(_num(r.get("injury_weeks"))),
            extra={str(k): float(v) for k, v in (r.get("extra") or {}).items() if isinstance(v, (int, float))},
        )
    return players


def replacement_levels(settings: GameSettings, by_pos: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, float]:
    """Weekly mean of the first player a team would not start, per position:
    league-wide starters at the position (strict slots plus each flex slot's
    expected share) plus one bench player per team (half for K and DEF)."""

    out: dict[str, float] = {}
    for pos in GAME_POSITIONS:
        strict = sum(1 for s in settings.slots if s == pos)
        flex = sum(FLEX_SHARE.get(s, {}).get(pos, 0.0) for s in settings.slots if s in FLEX_SHARE)
        starters = settings.teams * (strict + flex)
        buffer = settings.teams * (0.5 if pos in SINGLETON_POSITIONS else 1.0)
        index = int(round(starters + buffer))
        means = sorted((_num(r["mean"]) for r in by_pos.get(pos, ())), reverse=True)
        out[pos] = means[min(index, len(means) - 1)] if means else 0.0
    return out


def synthetic_byes(nfl_teams: Iterable[str], regular_weeks: int, seed: int) -> dict[str, int]:
    """Deterministic, evenly spread byes (weeks 5-14) for when the real NFL
    schedule is not on hand."""

    teams = sorted(set(nfl_teams) - {"FA", ""})
    order = WorldRng(seed).stream(0, "gsetup", 1).permutation(len(teams))
    last = min(SYNTHETIC_BYE_LAST_WEEK, regular_weeks)
    span = max(1, last - SYNTHETIC_BYE_FIRST_WEEK + 1)
    return {teams[int(j)]: SYNTHETIC_BYE_FIRST_WEEK + (i % span) for i, j in enumerate(order)}


def resolve_byes(
    players: Mapping[str, GamePlayer], real: Mapping[str, int], settings: GameSettings, seed: int
) -> tuple[dict[str, int], list[str]]:
    """Real byes where the adapter had them; otherwise synthetic. Only byes
    inside the regular season matter (the playoffs have none)."""

    nfl = {p.nfl_team for p in players.values()} - {"FA", ""}
    usable = {t: int(w) for t, w in real.items() if t in nfl and 1 <= int(w) <= settings.regular_weeks}
    if len(usable) >= max(1, int(0.8 * len(nfl))):
        return usable, []
    synthetic = synthetic_byes(nfl, settings.regular_weeks, seed)
    return {**synthetic, **usable} if usable else synthetic, ["byes_synthetic"]


def require_pool(players: Mapping[str, GamePlayer], settings: GameSettings) -> None:
    """Every team needs a kicker / defense to start if the league has the slot."""

    for pos in SINGLETON_POSITIONS:
        if pos in settings.slots and sum(1 for p in players.values() if p.pos == pos) < settings.teams:
            raise SimInputsError(f"{pos.lower()}_unavailable")


def build_snapshot(
    rows: Iterable[Mapping[str, Any]],
    bye_weeks: Mapping[str, int],
    settings: GameSettings,
    seed: int,
    *,
    user_team_name: str = "Your Team",
    scoring_model: str = "",
    notes: Iterable[str] = (),
) -> GameSnapshot:
    players = finalize_pool(rows, settings)
    require_pool(players, settings)
    if len(players) < settings.teams * settings.rounds:
        raise ValueError("player pool too small for this draft")
    byes, bye_notes = resolve_byes(players, bye_weeks, settings, seed)
    rng = WorldRng(seed)
    n = settings.teams
    ai_slots = [s for s in range(1, n + 1) if s != settings.user_slot]
    name_pick = rng.stream(0, "gsetup", 2).permutation(len(TEAM_NAMES))
    owner_pick = rng.stream(0, "gsetup", 3).permutation(len(OWNER_NAMES))
    coins = rng.stream(0, "gsetup", 4).permutation(n)

    ai_ids = [str(s) for s in ai_slots]
    strength = rng.stream(0, "gsetup", 5).random(len(ai_ids))
    personas = assign_personas(
        rng.stream(0, "persona", 1), ai_ids,
        {tid: float(strength[i]) for i, tid in enumerate(ai_ids)}, {tid: 26.0 for tid in ai_ids},
    )
    teams: list[GameTeam] = []
    ai_seen = 0
    user_key = _name_key(user_team_name)
    ai_names = [TEAM_NAMES[int(i)] for i in name_pick if _name_key(TEAM_NAMES[int(i)]) != user_key]
    for slot in range(1, n + 1):
        tid = str(slot)
        if slot == settings.user_slot:
            teams.append(GameTeam(
                tid=tid, name=user_team_name[:40] or "Your Team", owner="You", is_user=True,
                persona_id="you", draft_slot=slot, coin=int(coins[slot - 1]),
            ))
            continue
        persona = personas[tid]
        teams.append(GameTeam(
            tid=tid, name=ai_names[ai_seen % len(ai_names)],
            owner=OWNER_NAMES[int(owner_pick[ai_seen % len(OWNER_NAMES)])], is_user=False,
            persona_id=persona.pid, draft_slot=slot, coin=int(coins[slot - 1]),
            horizon=persona.params.horizon, pos_bias=dict(persona.params.pos_bias),
        ))
        ai_seen += 1
    order = [str(int(i) + 1) for i in rng.stream(0, "gsetup", 6).permutation(n)]
    schedule = round_robin(order, settings.regular_weeks)
    return GameSnapshot(
        settings=settings, teams=tuple(teams), players=players, bye_weeks=byes, schedule=schedule,
        scoring_model=scoring_model, notes=tuple(notes) + tuple(bye_notes),
        seed=seed if settings.dynasty else 0, start_picks=own_picks(settings, [t.tid for t in teams]),
    )


def own_picks(settings: GameSettings, tids: Iterable[str]) -> tuple[SimPick, ...]:
    """Every team holds its own picks for the next ``pick_years`` rookie drafts
    (the first draft is the one after season 1). Empty outside dynasty."""

    if not settings.dynasty:
        return ()
    first = settings.start_year + 1
    return tuple(
        SimPick(season=y, round=r, orig=t, owner=t)
        for y in range(first, first + settings.pick_years)
        for r in range(1, settings.rookie_rounds + 1) for t in sorted(tids)
    )


def league_settings(
    imported: LeagueImport, *, difficulty: str, auto_lineup: bool, regular_weeks: int = 14, trade_deadline_week: int = 10,
    tiebreaker: str = "points_for", dynasty: bool = False, seasons: int = DEFAULT_SEASONS, start_year: int = 0,
    ir_slots: int | None = None, taxi_slots: int | None = None,
) -> GameSettings:
    """Game settings that mirror a real league: its size, lineup, scoring and
    playoff field, over a fresh 14-week season."""

    n = len(imported.teams)
    user = next(i for i, t in enumerate(imported.teams) if t.is_user) + 1
    limit = max(len(imported.slots) + imported.bench, max(len(t.roster) for t in imported.teams))
    scoring = {str(k): float(v) for k, v in imported.scoring_settings.items()}
    ir = imported.ir_slots if ir_slots is None else ir_slots
    taxi = imported.taxi_slots if taxi_slots is None else taxi_slots
    ir = max(ir, max((len(t.ir) for t in imported.teams), default=0))
    taxi = max(taxi, max((len(t.taxi) for t in imported.teams), default=0))
    dyn = {}
    if dynasty:
        dyn = dict(
            mode="dynasty", seasons=seasons, dynasty_v=DYNASTY_VERSION, pick_years=PICK_YEARS,
            start_year=start_year or imported.start_year or imported_year(imported),
            rookie_rounds=max(2, min(5, imported.rookie_rounds or DEFAULT_ROOKIE_ROUNDS)),
        )
    return GameSettings(
        reserve_v=RESERVE_VERSION, ir_slots=min(ir, 8), taxi_slots=min(taxi, 12), taxi_years=imported.taxi_years, **dyn,
        teams=n, scoring=scoring_label(scoring), difficulty=difficulty, user_slot=user, auto_lineup=auto_lineup,
        slots=imported.slots, rounds=0, roster_limit=limit, regular_weeks=regular_weeks,
        playoff_teams=max(2, min(imported.playoff_teams, n)), trade_deadline_week=trade_deadline_week,
        te_premium=float(scoring.get("bonus_rec_te", 0.0) or 0.0),
        superflex="SUPER_FLEX" in imported.slots, include_k="K" in imported.slots,
        include_def="DEF" in imported.slots, bench=limit - len(imported.slots),
        start=START_LEAGUE, custom_scoring=scoring, tiebreaker=tiebreaker,
    )


def imported_year(imported: LeagueImport) -> int:
    try:
        return int(imported.season)
    except (TypeError, ValueError):
        return 2026


def build_league_snapshot(
    rows: Iterable[Mapping[str, Any]],
    bye_weeks: Mapping[str, int],
    imported: LeagueImport,
    settings: GameSettings,
    seed: int,
    *,
    user_team_name: str = "",
    scoring_model: str = "",
    notes: Iterable[str] = (),
) -> GameSnapshot:
    """A game that starts in week 1 with a real league's rosters (frozen copy).
    Rostered players the pool cannot project are dropped from their team and
    counted in the notes; free agents are the rest of the pool."""

    rostered = {p for t in imported.teams for p in (*t.roster, *t.ir, *t.taxi)}
    players = finalize_pool(rows, settings, keep=rostered)
    require_pool(players, settings)
    dropped = sum(1 for p in rostered if p not in players)
    picks = imported.picks if settings.dynasty and imported.picks else own_picks(settings, [t.tid for t in imported.teams])
    picks = tuple(p for p in picks if settings.start_year < p.season < settings.start_year + 1 + settings.pick_years and p.round <= settings.rookie_rounds)
    byes, bye_notes = resolve_byes(players, bye_weeks, settings, seed)
    rng = WorldRng(seed)
    ai_ids = [t.tid for t in imported.teams if not t.is_user]
    strength = rng.stream(0, "gsetup", 5).random(max(1, len(ai_ids)))
    personas = assign_personas(
        rng.stream(0, "persona", 1), ai_ids,
        {tid: float(strength[i]) for i, tid in enumerate(ai_ids)}, {tid: 26.0 for tid in ai_ids},
    )
    coins = rng.stream(0, "gsetup", 4).permutation(len(imported.teams))
    teams: list[GameTeam] = []
    start_rosters: dict[str, tuple[str, ...]] = {}
    start_ir: dict[str, tuple[str, ...]] = {}
    start_taxi: dict[str, tuple[str, ...]] = {}
    for i, t in enumerate(imported.teams):
        start_rosters[t.tid] = tuple(p for p in t.roster if p in players)
        start_ir[t.tid] = tuple(p for p in t.ir if p in players)
        start_taxi[t.tid] = tuple(p for p in t.taxi if p in players)
        if t.is_user:
            teams.append(GameTeam(
                tid=t.tid, name=(user_team_name or t.name)[:40] or "Your Team", owner="You", is_user=True,
                persona_id="you", draft_slot=i + 1, coin=int(coins[i]),
            ))
            continue
        persona = personas[t.tid]
        teams.append(GameTeam(
            tid=t.tid, name=t.name[:40] or f"Team {t.tid}", owner=t.owner[:40], is_user=False,
            persona_id=persona.pid, draft_slot=i + 1, coin=int(coins[i]),
            horizon=persona.params.horizon, pos_bias=dict(persona.params.pos_bias),
        ))
    order = [imported.teams[int(i)].tid for i in rng.stream(0, "gsetup", 6).permutation(len(imported.teams))]
    schedule = round_robin(order, settings.regular_weeks)
    extra = list(notes) + list(imported.notes) + list(bye_notes)
    if dropped:
        extra.append(f"roster_players_not_projected:{dropped}")
    return GameSnapshot(
        settings=settings, teams=tuple(teams), players=players, bye_weeks=byes, schedule=schedule,
        scoring_model=scoring_model, notes=tuple(extra), start_rosters=start_rosters,
        start_ir=start_ir if settings.reserves else {}, start_taxi=start_taxi if settings.reserves else {},
        seed=seed if settings.dynasty else 0, start_picks=picks if settings.dynasty else (),
    )


def draft_order(snapshot: GameSnapshot) -> list[str]:
    """Snake order: team id on the clock for each overall pick (0-based)."""

    s = snapshot.settings
    by_slot = {t.draft_slot: t.tid for t in snapshot.teams}
    out: list[str] = []
    for rnd in range(1, s.rounds + 1):
        slots = range(1, s.teams + 1) if rnd % 2 else range(s.teams, 0, -1)
        out.extend(by_slot[slot] for slot in slots)
    return out


def pick_round(snapshot: GameSnapshot, pick_index: int) -> int:
    return pick_index // snapshot.settings.teams + 1


__all__ = ["finalize_pool", "replacement_levels", "require_pool", "league_settings", "build_league_snapshot", "build_snapshot", "draft_order", "pick_round", "synthetic_byes", "resolve_byes"]
