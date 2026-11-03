"""One roster-value model for "what does MY roster need" and "who can I drop".

Waivers used to answer "team need" from ``roster_needs.classify_roster_rooms``,
a coverage-count policy whose value thresholds (18 / 20 / 24 / 55) are written
for a 0-100 scale while the valued frame is 0-11,000: every rostered player
cleared "playable cover" and every young player was a "core young asset", so a
dynasty roster could never have a need and the header said "None" (see
``docs/suggested-drops-and-needs.md``). That policy also never ranked positions
against each other, so there was nothing to surface when nothing was binary.

This module replaces it for the waiver surfaces and is shared with
``modules.drop_candidates`` so the two cannot disagree about a player's worth
to the roster. Both read the same facts, all from the lineup model the Trade
Analyzer uses (``modules.trade_lineup_model``):

* ``start_share``      share of remaining weeks a player is in the best lineup;
* ``slot ranks``       each starter slot at a position vs the same slot on every
                       other team in the league ("your WR3 is 8th of 12");
* ``upgrade gain``     lineup points over the rest of the season if the best
                       real free agent at the position were added;
* ``depth``            healthy players at the position vs starters + one cover;
* ``future``           dynasty only: aging starters (the repo age curve) with no
                       young cover behind them;
* ``injury pressure``  starters who are ruled out.

Nothing here is silent: a lookup that fails for an expected reason is reported
through ``modules.model_status`` and the caller says so; anything else is a bug
and propagates.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from modules import model_status, trade_lineup_model as tlm
from modules.frame_records import frame_records
from modules.injury_status import is_ruled_out
from modules.rankings import age_multiplier
from modules.trade_grade import FANTASY_SEASON_WEEKS, SeasonWindow, healthy_equivalent_roster

logger = logging.getLogger(__name__)

MODEL_VERSION = "roster-value-v1"
CORE_POSITIONS = ("QB", "RB", "WR", "TE")
# Positions the lineup model prices. Anything else (IDP, D/ST) is not
# evaluated by either the need model or the drop engine, and says so.
MODELED_POSITIONS = tlm.SCORED_POSITIONS

# A player is "core" when he is in the best lineup in at least this share of
# the remaining weeks.
CORE_START_SHARE = 0.5

# "High-value asset": healthy value at or above the value of the player ranked
# league_size * max(3, starters // 2) among ALL rostered players, i.e. roughly
# each team's top handful of assets, scaled by league size and lineup size
# (never a fixed number).
HIGH_VALUE_PLAYERS_PER_TEAM_MIN = 3

# Need tiers (documented judgement calls, all in one place). Slot rank is the
# league rank of a starter slot as a 0..1 percentile (0 = best team, 1 = worst).
PRIMARY_RANK_PCT = 0.60  # 8th of 12 or worse
SECONDARY_RANK_PCT = 0.45  # 6th of 12 or worse (watch-list only)
# A weak slot rank alone (no free agent upgrade, no injury) is a real need only
# when it is bottom-quarter; between PRIMARY and this it is a watch item.
RANK_ONLY_SECONDARY_PCT = 0.75
# Lineup points per week the best free agent would add before it counts as a
# real upgrade (about a typical flex's weekly spread, not noise).
MATERIAL_UPGRADE_PPW = 0.75
# Aging: a starter whose age-curve multiplier falls by this share within two
# years is "aging" (modules.rankings.age_multiplier, the curve valuation uses).
AGING_DROP_SHARE = 0.12
# A young cover is a player at or under this age at the position.
YOUNG_COVER_AGE = {"QB": 27.0, "RB": 24.0, "WR": 25.0, "TE": 25.0}

TIER_ORDER = {"primary": 3, "secondary": 2, "watch": 1, "covered": 0}


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# --- roster limits -----------------------------------------------------------

_IR_ALWAYS = {"ir", "injured reserve", "pup", "physically unable to perform", "nfi", "non football injury"}


@dataclass(frozen=True)
class RosterLimits:
    """Real roster shape for one team (Sleeper roster + league settings)."""

    active_limit: int | None  # starters + bench; IR and taxi are extra
    active_ids: tuple[str, ...]
    ir_ids: tuple[str, ...]
    taxi_ids: tuple[str, ...]
    reserve_slots: int
    taxi_slots: int

    @property
    def active_count(self) -> int:
        return len(self.active_ids)

    @property
    def is_full(self) -> bool:
        return self.active_limit is not None and self.active_count >= self.active_limit

    @property
    def open_spots(self) -> int | None:
        return None if self.active_limit is None else max(0, self.active_limit - self.active_count)

    @property
    def open_ir_slots(self) -> int:
        return max(0, self.reserve_slots - len(self.ir_ids))

    def to_public(self) -> dict[str, Any]:
        return {
            "active_limit": self.active_limit,
            "active_count": self.active_count,
            "open_spots": self.open_spots,
            "is_full": self.is_full,
            "reserve_slots": self.reserve_slots,
            "reserve_used": len(self.ir_ids),
            "taxi_slots": self.taxi_slots,
            "taxi_used": len(self.taxi_ids),
        }


def roster_limits(league: Mapping[str, Any] | None, roster: Mapping[str, Any] | None) -> RosterLimits:
    """Active-roster limit and who occupies it, from the real Sleeper payloads.

    Sleeper's ``roster.players`` lists everybody including IR (``reserve``) and
    taxi; only the remainder competes for the ``roster_positions`` slots, so
    only those players can make room for an add when dropped."""

    league = league or {}
    roster = roster or {}
    positions = [str(p or "").upper() for p in (league.get("roster_positions") or [])]
    active_slots = [p for p in positions if p not in {"IR", "TAXI"}]
    settings = league.get("settings") if isinstance(league.get("settings"), Mapping) else {}
    all_ids = [str(p) for p in (roster.get("players") or []) if p is not None]
    ir = {str(p) for p in (roster.get("reserve") or []) if p is not None}
    taxi = {str(p) for p in (roster.get("taxi") or []) if p is not None}
    active = tuple(p for p in all_ids if p not in ir and p not in taxi)
    return RosterLimits(
        active_limit=len(active_slots) or None,
        active_ids=active,
        ir_ids=tuple(p for p in all_ids if p in ir),
        taxi_ids=tuple(p for p in all_ids if p in taxi),
        reserve_slots=int(_num(settings.get("reserve_slots"), 0)),
        taxi_slots=int(_num(settings.get("taxi_slots"), 0)),
    )


def ir_eligible(status: Any, injury_status: Any, league: Mapping[str, Any] | None) -> bool:
    """Whether Sleeper would let this player sit in this league's IR slot.

    IR / PUP are always allowed; Out, Doubtful, Suspended, COVID, DNR and NA
    only when the league's ``reserve_allow_*`` setting says so (an absent
    setting is "not allowed")."""

    settings = ((league or {}).get("settings") or {}) if isinstance((league or {}).get("settings"), Mapping) else {}
    terms = {_text(status).casefold(), _text(injury_status).casefold()} - {""}
    if terms & _IR_ALWAYS:
        return True
    allow = {
        "out": "reserve_allow_out",
        "doubtful": "reserve_allow_doubtful",
        "suspended": "reserve_allow_sus",
        "covid-19": "reserve_allow_cov",
        "cov": "reserve_allow_cov",
        "dnr": "reserve_allow_dnr",
        "na": "reserve_allow_na",
    }
    return any(key in terms and bool(_num(settings.get(setting), 0)) for key, setting in allow.items())


# --- league-scaled thresholds and the league table --------------------------


def high_value_threshold(rostered_values: Sequence[float], league_size: int, starter_count: int) -> float:
    """Healthy value above which a player is a high-value asset in THIS league.

    The value of the player ranked ``league_size * max(3, starters // 2)``
    among all rostered players: about every team's top handful of assets,
    which grows with a bigger league or a bigger lineup and tracks whatever
    value scale the lens uses. 0.0 when there is nothing to rank."""

    values = sorted((float(v) for v in rostered_values if v is not None and math.isfinite(float(v))), reverse=True)
    if not values:
        return 0.0
    per_team = max(HIGH_VALUE_PLAYERS_PER_TEAM_MIN, int(starter_count) // 2)
    rank = min(len(values), max(1, int(league_size) * per_team))
    return float(values[rank - 1])


def league_position_table(
    all_players_df: pd.DataFrame,
    rosters: Iterable[Mapping[str, Any]],
    ctx: tlm.ModelContext,
) -> dict[str, dict[str, list[float]]]:
    """roster_id -> position -> expected PPG of each rostered player, best first.

    One consistent basis for every team (season average shrunk to the value
    prior, no per-player projection) so a rank compares like with like."""

    base = all_players_df
    if base is not None and "proj_ppg" in base.columns:
        base = base.drop(columns=[c for c in ("proj_ppg", "proj_sd") if c in base.columns])
    out: dict[str, dict[str, list[float]]] = {}
    by_id = None
    for roster in rosters:
        rid = str(roster.get("roster_id"))
        ids = {str(p) for p in (roster.get("players") or []) if p is not None}
        ir = {str(p) for p in (roster.get("reserve") or []) if p is not None}
        taxi = {str(p) for p in (roster.get("taxi") or []) if p is not None}
        ids -= ir | taxi
        if by_id is None:
            by_id = base
        frame = by_id[by_id["player_id"].astype(str).isin(ids)]
        table: dict[str, list[float]] = {pos: [] for pos in MODELED_POSITIONS}
        for p in tlm.profile_roster(frame, ctx):
            if p.position in table and p.ppg is not None and not p.out_all:
                table[p.position].append(float(p.ppg))
        for pos in table:
            table[pos].sort(reverse=True)
        out[rid] = table
    return out


# --- the context -------------------------------------------------------------


@dataclass
class RosterValueContext:
    frame: pd.DataFrame  # every player on the team (active + IR + taxi), valued, projections attached
    score_field: str
    settings: dict[str, Any]
    league: Mapping[str, Any]
    strategy: str
    window: SeasonWindow
    model_ctx: tlm.ModelContext
    profiles: dict[str, tlm.PlayerPoints]
    limits: RosterLimits
    healthy_value: dict[str, float]
    start_share: dict[str, float]
    high_value: float
    league_size: int
    pool: pd.DataFrame | None
    status: dict[str, Any] = field(default_factory=model_status.ok)

    @property
    def weeks(self) -> int:
        return len(self.model_ctx.weeks)

    def row(self, player_id: str) -> dict[str, Any] | None:
        match = self.frame[self.frame["player_id"].astype(str) == str(player_id)]
        return frame_records(match)[0] if not match.empty else None

    def active_profiles(self) -> list[tlm.PlayerPoints]:
        return [self.profiles[p] for p in self.limits.active_ids if p in self.profiles]

    def expected_starters(self) -> dict[str, float]:
        """Expected number of starters at each position (sum of start shares)."""

        out = {pos: 0.0 for pos in MODELED_POSITIONS}
        for pid, share in self.start_share.items():
            p = self.profiles.get(pid)
            if p is not None and p.position in out:
                out[p.position] += share
        return out


def _start_shares(profiles: Mapping[str, tlm.PlayerPoints], ctx: tlm.ModelContext, active: set[str]) -> dict[str, float]:
    weeks = ctx.weeks
    counts = {pid: 0 for pid in active}
    current = max(1, ctx.window.current_week)
    for week in weeks:
        cands = []
        for pid in active:
            p = profiles.get(pid)
            if p is None or p.ppg is None:
                continue
            # A player counts toward the best lineup when he is more likely
            # than not to be available that week.
            if p.availability(week, current) >= 0.5:
                cands.append((pid, p.position, float(p.ppg)))
        _, starters, _ = tlm.solve_lineup(cands, ctx.slots)
        for pid, *_ in starters:
            counts[pid] = counts.get(pid, 0) + 1
    n = max(1, len(weeks))
    return {pid: counts.get(pid, 0) / n for pid in active}


def build_context(
    *,
    roster_df: pd.DataFrame,
    all_players_df: pd.DataFrame,
    pool: pd.DataFrame | None,
    my_roster: Mapping[str, Any],
    league: Mapping[str, Any],
    settings: Mapping[str, Any],
    score_field: str,
    strategy: str,
    window: SeasonWindow,
    league_rostered_values: Sequence[float],
    status: Mapping[str, Any] | None = None,
) -> RosterValueContext:
    """Profile the roster once; everything else reads this."""

    settings = dict(settings)
    model_ctx = tlm.get_context(
        all_players_df, settings, score_field if score_field in all_players_df.columns else "value_score",
        window=window, strategy=strategy, waiver_df=pool,
    )
    limits = roster_limits(league, my_roster)
    profiles = {p.player_id: p for p in tlm.profile_roster(roster_df, model_ctx)}
    healthy = healthy_equivalent_roster(roster_df, score_column=score_field, window=window)
    healthy_value = {
        str(r["player_id"]): _num(r.get(score_field))
        for r in frame_records(healthy)
    }
    active = {pid for pid in limits.active_ids if pid in profiles}
    league_size = int(_num((league or {}).get("total_rosters"), 0)) or int(_num(settings.get("league_size"), 12)) or 12
    starter_count = int(_num(settings.get("starter_count"), sum(model_ctx.slots.values()) or 9))
    return RosterValueContext(
        frame=roster_df,
        score_field=score_field,
        settings=settings,
        league=league,
        strategy=strategy,
        window=window,
        model_ctx=model_ctx,
        profiles=profiles,
        limits=limits,
        healthy_value=healthy_value,
        start_share=_start_shares(profiles, model_ctx, active),
        high_value=high_value_threshold(league_rostered_values, league_size, starter_count),
        league_size=league_size,
        pool=pool,
        status=model_status.merge(status),
    )


# --- swaps: the shared "what changes if" evaluation -------------------------


def _asset(player_id: str, name: str, value: float) -> dict[str, Any]:
    return {"asset_type": "player", "player_id": player_id, "name": name, "score": value}


def evaluate_swap(
    rvc: RosterValueContext,
    drop_ids: Sequence[str],
    add_rows: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """The lineup model's verdict on dropping ``drop_ids`` and adding ``add_rows``.

    A drop-for-add is a trade with the waiver wire: the same expected-points
    model, the same posture weighting and the same value scale as the Trade
    Analyzer (``trade_lineup_model.evaluate_trade``). Values are healthy
    equivalents; the model prices an injury as missed weeks, so a stash is not
    double-penalised."""

    drop_set = {str(p) for p in drop_ids}
    before = rvc.frame
    keep = before[~before["player_id"].astype(str).isin(drop_set)]
    add_frame = pd.DataFrame(list(add_rows)) if add_rows else pd.DataFrame()
    after = pd.concat([keep, add_frame], ignore_index=True) if not add_frame.empty else keep
    send = [
        _asset(pid, rvc.profiles[pid].name if pid in rvc.profiles else pid, rvc.healthy_value.get(pid, 0.0))
        for pid in drop_ids
    ]
    add_values = healthy_equivalent_roster(add_frame, score_column=rvc.score_field, window=rvc.window) if not add_frame.empty else add_frame
    add_value_by_id = {str(r["player_id"]): _num(r.get(rvc.score_field)) for r in frame_records(add_values)}
    receive = [_asset(str(r["player_id"]), _text(r.get("name")), add_value_by_id.get(str(r["player_id"]), 0.0)) for r in add_rows]
    raw = sum(a["score"] for a in receive) - sum(a["score"] for a in send)
    result = tlm.evaluate_trade(
        before,
        after,
        rvc.model_ctx,
        send_assets=send,
        receive_assets=receive,
        raw_value_delta=raw,
        asset_value=lambda a: float(a.get("score") or 0.0),
    )
    result["raw_value_delta"] = round(raw)
    return result


# --- needs -------------------------------------------------------------------


def _pool_by_position(pool: pd.DataFrame | None, score_field: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {pos: [] for pos in MODELED_POSITIONS}
    if pool is None or pool.empty:
        return out
    for row in frame_records(pool):
        pos = _text(row.get("position")).upper()
        if pos in out:
            out[pos].append(row)
    for pos in out:
        out[pos].sort(key=lambda r: -(_num(r.get("proj_ppg"), _num(r.get(score_field)) / 1000.0)))
    return out


def best_free_agents(rvc: RosterValueContext, position: str, limit: int = 3) -> list[tlm.PlayerPoints]:
    """Best real free agents at a position by the model's expected PPG."""

    pool = [p for p in rvc.model_ctx.waiver if p.position == position and p.ppg is not None]
    pool.sort(key=lambda p: (-(p.ppg or 0.0), p.player_id))
    return pool[:limit]


def _aging(p: tlm.PlayerPoints) -> bool:
    if p.age is None:
        return False
    now = age_multiplier(p.position, p.age)
    then = age_multiplier(p.position, p.age + 2)
    return now > 0 and (now - then) / now >= AGING_DROP_SHARE


def assess_needs(
    rvc: RosterValueContext,
    league_table: Mapping[str, Mapping[str, Sequence[float]]],
    my_roster_id: str,
    *,
    dynasty: bool,
) -> dict[str, Any]:
    """Per-position need with the numbers behind it, weakest first.

    Always names the relative weakest position; says "no need" only when every
    position is covered by the model (``covered`` is a result, not a default).
    """

    status = model_status.merge(rvc.status)
    expected = rvc.expected_starters()
    mine: dict[str, list[tlm.PlayerPoints]] = {pos: [] for pos in MODELED_POSITIONS}
    for p in rvc.active_profiles():
        if p.position in mine and p.ppg is not None:
            mine[p.position].append(p)
    for pos in mine:
        mine[pos].sort(key=lambda p: -(p.ppg or 0.0))
    # League ranks use the same basis for every team.
    base_mine = league_table.get(str(my_roster_id), {})
    weeks = max(1, rvc.weeks)
    positions: list[dict[str, Any]] = []
    for pos in CORE_POSITIONS:
        starters_n = max(int(round(expected.get(pos, 0.0))), int(rvc.model_ctx.slots.get(pos, 0) or 0))
        if starters_n <= 0:
            continue
        roster_pts = base_mine.get(pos, [])
        # Rank each starter slot against the same slot on every other team.
        slot_ranks: list[dict[str, Any]] = []
        for k in range(starters_n):
            mine_k = roster_pts[k] if k < len(roster_pts) else 0.0
            better = sum(
                1
                for rid, table in league_table.items()
                if rid != str(my_roster_id) and (table.get(pos, [])[k] if k < len(table.get(pos, [])) else 0.0) > mine_k
            )
            league_n = max(1, len(league_table))
            rank = better + 1
            slot_ranks.append({
                "slot": f"{pos}{k + 1}" if starters_n > 1 or pos != "QB" else pos,
                "rank": rank,
                "of": league_n,
                "pct": 0.0 if league_n <= 1 else (rank - 1) / (league_n - 1),
                "ppg": round(mine_k, 1),
            })
        weakest = max(slot_ranks, key=lambda s: (s["pct"], s["slot"]))
        # Upgrade: the best free agent as a rostered player.
        upgrade = {"ppw": 0.0, "ros": 0.0, "name": "", "player_id": "", "ppg": None}
        fas = best_free_agents(rvc, pos, 1)
        if fas:
            fa = fas[0]
            fa_row = None
            if rvc.pool is not None and not rvc.pool.empty:
                match = rvc.pool[rvc.pool["player_id"].astype(str) == fa.player_id]
                fa_row = frame_records(match)[0] if not match.empty else None
            if fa_row is not None:
                swap = evaluate_swap(rvc, [], [fa_row])
                ros = float(swap["points"]["ros_delta"])
                upgrade = {
                    "ppw": round(ros / weeks, 2), "ros": round(ros, 1), "name": fa.name,
                    "player_id": fa.player_id, "ppg": round(float(fa.ppg or 0.0), 1),
                }
        healthy_here = [p for p in mine[pos] if not p.out_all and (p.absence is None or p.absence.weeks < 3)]
        required_depth = starters_n + (1 if pos != "K" else 0)
        depth_short = max(0, required_depth - len(healthy_here))
        # A player who would start if healthy: at least as good as the weakest
        # healthy starter (start_share ignores him while he is unavailable).
        floor_ppg = float(healthy_here[starters_n - 1].ppg or 0.0) if len(healthy_here) >= starters_n else 0.0
        injured_starters = [
            p for p in rvc.active_profiles()
            if p.position == pos and (p.out_all or (p.absence is not None and p.absence.weeks >= 3))
            and (p.ppg or 0.0) >= floor_ppg
        ]
        aging = [p for p in mine[pos][:starters_n] if _aging(p)]
        young_cover = [
            p for p in rvc.profiles.values()
            if p.position == pos and p.age is not None and p.age <= YOUNG_COVER_AGE[pos]
            and p.player_id not in {a.player_id for a in aging}
        ]
        future_gap = bool(dynasty and aging and not young_cover)

        rank_bad = weakest["pct"] >= PRIMARY_RANK_PCT
        material_upgrade = upgrade["ppw"] >= MATERIAL_UPGRADE_PPW
        reasons: list[str] = []
        if depth_short and len(healthy_here) < starters_n:
            tier = "primary"
            reasons.append(
                f"only {len(healthy_here)} healthy {pos} for {starters_n} starting spot{'s' if starters_n != 1 else ''}"
            )
        elif rank_bad and material_upgrade:
            tier = "primary"
        elif weakest["pct"] >= RANK_ONLY_SECONDARY_PCT or material_upgrade or injured_starters:
            tier = "secondary"
        elif weakest["pct"] >= SECONDARY_RANK_PCT or depth_short or future_gap:
            tier = "watch"
        else:
            tier = "covered"
        if depth_short and len(healthy_here) >= starters_n:
            reasons.append(f"thin depth: {len(healthy_here)} healthy {pos} for {starters_n} starter{'s' if starters_n != 1 else ''} plus a bye/injury cover")
        if weakest["pct"] >= SECONDARY_RANK_PCT:
            reasons.append(f"{weakest['slot']} is {_ordinal(weakest['rank'])} of {weakest['of']} in the league")
        if upgrade["ppw"] >= MATERIAL_UPGRADE_PPW and upgrade["name"]:
            reasons.append(f"{upgrade['name']} on the wire would add ~{upgrade['ppw']:.1f} pts/week")
        if injured_starters:
            reasons.append("injured: " + ", ".join(p.name for p in injured_starters[:2]))
        if future_gap:
            reasons.append("aging starter(s) " + ", ".join(p.name for p in aging[:2]) + " with no young cover")
        score = (
            weakest["pct"]
            + min(1.0, max(0.0, upgrade["ppw"]) / (MATERIAL_UPGRADE_PPW * 4))
            + 0.25 * min(2, depth_short)
            + 0.15 * (1 if future_gap else 0)
            + 0.20 * (1 if injured_starters else 0)
        )
        positions.append({
            "position": pos,
            "tier": tier,
            "score": round(score, 3),
            "starters": starters_n,
            "weakest_slot": weakest,
            "slot_ranks": slot_ranks,
            "upgrade": upgrade,
            "healthy_count": len(healthy_here),
            "required_depth": required_depth,
            "depth_short": depth_short,
            "injured_starters": [p.name for p in injured_starters],
            "aging_starters": [p.name for p in aging],
            "future_gap": future_gap,
            "reasons": reasons,
        })
    positions.sort(key=lambda d: (-TIER_ORDER[d["tier"]], -d["score"], d["position"]))
    needed = [d["position"] for d in positions if d["tier"] in ("primary", "secondary")]
    biggest = positions[0] if positions else None
    no_need = bool(biggest) and biggest["tier"] in ("watch", "covered")
    headline = ""
    if biggest:
        ws = biggest["weakest_slot"]
        if biggest["tier"] in ("primary", "secondary"):
            lead = "Biggest need" if biggest["tier"] == "primary" else "Top need"
            detail = f"your {ws['slot']} is {_ordinal(ws['rank'])} of {ws['of']}"
            if biggest["reasons"] and ws["pct"] < SECONDARY_RANK_PCT:
                detail = biggest["reasons"][0]
            headline = f"{lead}: {biggest['position']} — {detail}."
        else:
            headline = (
                f"No urgent need — your weakest spot is {ws['slot']} ({_ordinal(ws['rank'])} of {ws['of']}, "
                f"no free agent adds a meaningful {biggest['position']} upgrade)."
                if biggest["upgrade"]["ppw"] < MATERIAL_UPGRADE_PPW
                else f"No urgent need — your weakest spot is {ws['slot']} ({_ordinal(ws['rank'])} of {ws['of']})."
            )
    return {
        "model_version": MODEL_VERSION,
        "needed_positions": needed,
        "biggest_need": biggest["position"] if biggest and biggest["tier"] in ("primary", "secondary") else None,
        "weakest_position": biggest["position"] if biggest else None,
        "no_need": no_need,
        "headline": headline,
        "positions": positions,
        "league_size": len(league_table),
        "basis": "offseason" if not rvc.window.in_season else "in_season",
        "dynasty": bool(dynasty),
        "model_status": status,
    }
