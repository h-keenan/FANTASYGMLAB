"""3-team trade ideas: find cyclic three-way deals every team can say yes to.

A 2-team idea (``trade_hub_engine``) pairs the user with ONE partner. Many real
trades need three seats: the user's surplus fits team B's need, B's surplus fits
team C's need, and C's surplus fits the user's need. This module searches for
those cycles. It has no valuation model of its own:

* **Needs / surplus** come from ``roster_value_model.league_needs`` (the same
  per-roster need table Trade Hub, Waivers and the Dashboard read): a position
  is a *need* at tier primary / secondary; a player is *surplus* when the model
  lists him in ``surplus_player_ids`` or he sits beyond the starters at a
  position that is covered.
* **Every candidate is judged by ``multi_team_trade_engine.grade_transfers``**,
  the per-team pipeline the 3-team Analyzer runs (each team's own posture,
  lineup model, age curve, roster-full check). An idea is returned only when
  EVERY team's own verdict is "Fair or better" (tone ``accept`` or ``fair``).

The search is bounded and deterministic:

1. *Partners*: the ``MAX_PARTNERS`` teams whose rosters best fit the user's (the
   user's needs filled by their surplus plus their needs filled by the user's).
2. *Edges*: for each directed pair (X to Y), at most ``EDGE_ASSETS`` sendable
   X players at a position Y needs, best need fit first.
3. *Cycles*: for each partner pair and both orientations, every combination of
   one or two assets per edge, pre-priced on the neutral league value (a cheap filter
   only; ``PROXY_TOLERANCE``), best balanced first, at most ``PAIR_VERIFY_CAP``
   per partner pair.
4. *Verify*: at most ``MAX_VERIFY`` candidates go through the real engine, in
   that fixed order, until ``MAX_IDEAS`` pass or ``time_budget`` runs out.
5. *Counter variants*: a candidate that fails only because ONE team is a notch
   short gets one repair (a single extra asset from the team sending to it);
   at most ``MAX_VARIANTS`` repairs per search.

Draft picks are pieces too (only when the context loaded the league's pick
table, ``build_context(load_picks=True)``). A pick is priced by the SAME pick
valuation the 2-team engine and the Analyzer use (``list_draft_pick_assets``,
then each team's own posture multiplier inside ``grade_transfers``), and the
search follows the same direction logic those engines apply to a team's posture:
a *contender* spends picks (it prices them at a discount), a *rebuild* team
(``rebuild`` / ``tank``) wants them most and a *retool* team wants them some;
rebuild and retool teams never send picks. A pick is therefore a "need" only for
a team whose posture wants capital, never a free filler. At most one pick per
edge and ``MAX_PICKS_PER_IDEA`` per idea keep a deal about players first.

Every passing idea is also run through the commissioner veto read
(``trade_veto.assess``): an idea one team could be asked to be vetoed over
(band lopsided / outrage) is dropped even when every verdict is "Fair".

All sorts break ties on roster / player ids, so the same league state returns
the same ideas in the same order (only the wall-clock budget can shorten the
list, never reorder it).
"""

from __future__ import annotations

import hashlib
import itertools
import logging
import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import pandas as pd

from modules import multi_team_trade as mt
from modules import multi_team_trade_engine as engine
from modules import roster_value_model, trade_veto, trade_value_bands as bands

logger = logging.getLogger("fantasygm.multi_team_trade_finder")

MAX_PARTNERS = 5
EDGE_ASSETS = 3
PROXY_TOLERANCE = 1200  # neutral-value shortfall a team may show before the real engine is asked (the DECLINE rung)
MIN_ASSET_VALUE = 300  # below this a player is a throw-in, not a trade piece
PAIR_VERIFY_CAP = 3
MAX_VERIFY = 12
MAX_IDEAS = 5
MAX_IDEAS_PER_PAIR = 2
MAX_VARIANTS = 2
DEFAULT_TIME_BUDGET_SECONDS = 12.0
PASS_TONES = frozenset({"accept", "fair"})
NEED_TIERS = ("primary", "secondary")
NEED_TIER_WEIGHT = {"primary": 2.0, "secondary": 1.0}
PICK_POSITION = "PICK"
# Posture group -> how much a team wants draft capital back (0 = never needs one).
PICK_WANT_BY_GROUP = {"rebuild": 2.0, "retool": 1.0, "contender": 0.0}
PICK_SENDER_GROUPS = frozenset({"contender"})
EDGE_PICKS = 2  # picks offered per directed edge (at most one rides in any single option)
MAX_PICKS_PER_IDEA = 2
VETO_BLOCK_BANDS = frozenset({trade_veto.BAND_LOPSIDED, trade_veto.BAND_OUTRAGE})


@dataclass(frozen=True)
class Asset:
    player_id: str
    label: str
    position: str
    value: float
    roster_id: str
    kind: str = "player"  # "player" | "pick" (a pick's player_id is its pick_id)


@dataclass(frozen=True)
class Candidate:
    transfers: tuple[mt.Transfer, ...]
    pair: tuple[str, str]
    fit: float
    min_delta: float


def _num(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if out != out else out


class _League:
    """Per-search read of the league: needs, sendable players, per-position fit."""

    def __init__(self, ctx: engine.TradeContext, user_rid: str, untouchable_ids: set[str]):
        self.ctx = ctx
        self.user_rid = user_rid
        self.untouchable_ids = untouchable_ids
        frame = ctx.valued
        pos_col = frame["position"].astype(str).str.upper() if "position" in frame.columns else None
        self.rows: dict[str, Asset] = {}
        if pos_col is not None and ctx.score_field in frame.columns:
            core = set(roster_value_model.CORE_POSITIONS)
            name_col = "name" if "name" in frame.columns else "player_id"
            for pid, pos, name, value in zip(
                frame["player_id"].astype(str), pos_col, frame[name_col].astype(str),
                pd.to_numeric(frame[ctx.score_field], errors="coerce").fillna(0.0),
            ):
                if pos in core:
                    self.rows[pid] = Asset(pid, name, pos, float(value), "")
        needs = ctx.needs()
        self.need_pos: dict[str, dict[str, float]] = {}
        self.sendable: dict[str, list[Asset]] = {}
        for rid in sorted(ctx.by_rid):
            assessed = needs.for_roster(rid)
            if not assessed:
                continue
            positions = list(assessed.get("positions") or [])
            self.need_pos[rid] = {
                str(p["position"]): NEED_TIER_WEIGHT[p["tier"]] + float(p.get("score") or 0.0)
                for p in positions if p.get("tier") in NEED_TIERS
            }
            self.sendable[rid] = self._sendable(rid, positions)
        self.pick_want: dict[str, float] = {}
        self.group: dict[str, str] = {}
        self.picks: dict[str, Asset] = {}
        if ctx.pick_by_id:
            self._load_picks()

    def _load_picks(self) -> None:
        """Pick pieces: each roster's own picks (current owner, per the pick table), and how
        much each team's posture wants draft capital back. Rebuild / retool never send one."""

        for rid in self.need_pos:
            group = str((self.ctx.posture(rid) or {}).get("group") or "retool")
            self.group[rid] = group
            self.pick_want[rid] = PICK_WANT_BY_GROUP.get(group, 0.0)
        for pick_id, pick in sorted(self.ctx.pick_by_id.items()):
            rid = str(pick.get("owner_roster_id"))
            value = _num(pick.get("score"))
            if rid not in self.need_pos or value < MIN_ASSET_VALUE:
                continue
            asset = Asset(pick_id, str(pick.get("label") or pick.get("name") or "Draft pick"), PICK_POSITION, value, rid, "pick")
            self.picks[pick_id] = asset
            if self.group[rid] in PICK_SENDER_GROUPS:
                self.sendable[rid].append(asset)
        for rid in self.sendable:
            self.sendable[rid].sort(key=lambda a: (-a.value, a.player_id))

    def want(self, rid: str, asset: Asset) -> float:
        """How much ``rid`` wants this piece: the position need, or posture-driven pick demand."""

        if asset.kind == "pick":
            return self.pick_want.get(rid, 0.0)
        return self.need_pos.get(rid, {}).get(asset.position, 0.0)

    def label(self, asset_id: str) -> str:
        found = self.rows.get(asset_id) or self.picks.get(asset_id)
        return found.label if found else asset_id

    def _sendable(self, rid: str, positions: Sequence[Mapping[str, Any]]) -> list[Asset]:
        tier_by_pos = {str(p["position"]): str(p["tier"]) for p in positions}
        starters = {str(p["position"]): int(p.get("starters") or 0) for p in positions}
        surplus = {str(pid) for p in positions for pid in (p.get("surplus_player_ids") or [])}
        owned = sorted(str(pid) for pid in (self.ctx.by_rid[rid].get("players") or []) if pid is not None)
        mine = [self.rows[pid] for pid in owned if pid in self.rows]
        by_pos: dict[str, list[Asset]] = {}
        for a in mine:
            by_pos.setdefault(a.position, []).append(a)
        out: list[Asset] = []
        for pos, group in by_pos.items():
            group.sort(key=lambda a: (-a.value, a.player_id))
            for rank, a in enumerate(group):
                if a.value < MIN_ASSET_VALUE or (rid == self.user_rid and a.player_id in self.untouchable_ids):
                    continue
                spare = a.player_id in surplus or (
                    tier_by_pos.get(pos) in ("covered", "watch") and rank >= starters.get(pos, 0) + 1
                )
                if spare:
                    out.append(Asset(a.player_id, a.label, a.position, a.value, rid))
        out.sort(key=lambda a: (-a.value, a.player_id))
        return out

    def edge(self, src: str, dst: str) -> list[Asset]:
        """Up to ``EDGE_ASSETS`` of ``src``'s sendable players at a position ``dst`` needs."""

        want = self.need_pos.get(dst, {})
        fits = [a for a in self.sendable.get(src, []) if a.kind == "player" and a.position in want]
        fits.sort(key=lambda a: (-want[a.position], -a.value, a.player_id))
        picks = [a for a in self.sendable.get(src, []) if a.kind == "pick" and self.want(dst, a) > 0]
        return fits[:EDGE_ASSETS] + picks[:EDGE_PICKS]

    def pair_fit(self, partner: str) -> float:
        """How well ``partner`` fits the user: needs each side can fill for the other."""

        score = 0.0
        for src, dst in ((partner, self.user_rid), (self.user_rid, partner)):
            score += sum(self.want(dst, a) for a in self.sendable.get(src, []))
        return score


def _options(assets: Sequence[Asset]) -> list[tuple[Asset, ...]]:
    """What one edge can carry: any single asset or any pair of the edge's assets."""

    singles = [(a,) for a in assets]
    pairs = [c for c in itertools.combinations(assets, 2) if not (c[0].kind == "pick" and c[1].kind == "pick")]
    return singles + pairs


def _candidates(league: _League, partners: Sequence[str]) -> list[Candidate]:
    user = league.user_rid
    out: list[Candidate] = []
    for p, q in itertools.combinations(sorted(partners), 2):
        for cycle in ((user, p, q), (user, q, p)):
            edges = [_options(league.edge(cycle[i], cycle[(i + 1) % 3])) for i in range(3)]
            if not all(edges):
                continue
            for combo in itertools.product(*edges):
                if sum(a.kind == "pick" for edge in combo for a in edge) > MAX_PICKS_PER_IDEA:
                    continue
                sent = {cycle[i]: sum(a.value for a in combo[i]) for i in range(3)}
                got = {cycle[(i + 1) % 3]: sum(a.value for a in combo[i]) for i in range(3)}
                deltas = [got[r] - sent[r] for r in cycle]
                if min(deltas) < -PROXY_TOLERANCE:
                    continue
                fit = sum(
                    league.want(cycle[(i + 1) % 3], a) for i in range(3) for a in combo[i]
                )
                transfers = tuple(
                    mt.Transfer(a.kind, a.player_id, cycle[i], cycle[(i + 1) % 3])
                    for i in range(3) for a in combo[i]
                )
                out.append(Candidate(transfers, (p, q), fit, min(deltas)))
    return out


def _order(cands: Sequence[Candidate]) -> list[Candidate]:
    """Best balanced first (simpler deals win ties), per-pair cap applied, ties on ids."""

    ranked = sorted(
        cands,
        key=lambda c: (
            -round(c.min_delta / 100.0), len(c.transfers), -c.fit,
            [(t.asset_id, t.from_roster) for t in c.transfers],
        ),
    )
    taken: dict[tuple[str, str], int] = {}
    out: list[Candidate] = []
    for c in ranked:
        if taken.get(c.pair, 0) >= PAIR_VERIFY_CAP:
            continue
        taken[c.pair] = taken.get(c.pair, 0) + 1
        out.append(c)
    return out


def idea_id(transfers: Sequence[mt.Transfer]) -> str:
    key = "|".join(sorted(f"{t.asset_type}:{t.asset_id}:{t.from_roster}>{t.to_roster}" for t in transfers))
    return "m3-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def _team_view(team: Mapping[str, Any], fit_text: str) -> dict[str, Any]:
    verdict = team.get("verdict") or {}
    why = list(team.get("why") or [])
    if fit_text:
        why.insert(0, {"factor": "need", "text": fit_text})
    return {
        "roster_id": team["roster_id"],
        "team_name": team["team_name"],
        "is_perspective": team["is_perspective"],
        "sends": team["sends"],
        "receives": team["receives"],
        "verdict": {k: verdict.get(k) for k in ("band", "ui_verdict", "confidence", "rationale")},
        "trade_score": team["trade_score"],
        "market_delta": team["market_delta"],
        "lineup_delta": team["lineup_delta"],
        "tone": team["tone"],
        "color_token": team["color_token"],
        "outcome": team["outcome"],
        "posture": team["posture"],
        "roster_overflow": team["roster_overflow"],
        "why": why,
    }


_GROUP_VERB = {"rebuild": "rebuilding", "retool": "retooling"}


def _fit_text(
    league: _League, rid: str, name: str, receives: Sequence[Mapping[str, Any]], sends: Sequence[Mapping[str, Any]]
) -> str:
    wanted = league.need_pos.get(rid, {})
    fills = sorted({str(r.get("position")) for r in receives if r.get("type") != "pick" and r.get("position") in wanted})
    spare = sorted({str(s.get("position")) for s in sends if s.get("type") != "pick" and s.get("position")})
    got_pick = any(r.get("type") == "pick" for r in receives) and league.pick_want.get(rid, 0.0) > 0
    sent_pick = any(s.get("type") == "pick" for s in sends)
    parts: list[str] = []
    if fills:
        parts.append(f"fills a {'/'.join(fills)} need")
    if got_pick:
        parts.append(f"adds draft capital while {_GROUP_VERB.get(league.group.get(rid, ''), 'building')}")
    sends_bits: list[str] = []
    if spare:
        sends_bits.append(f"spare {'/'.join(spare)} depth")
    if sent_pick:
        sends_bits.append("draft capital a contender can spend")
    if parts and sends_bits:
        return f"{name} {' and '.join(parts)} and sends {' plus '.join(sends_bits)}."
    if parts:
        return f"{name} {' and '.join(parts)}."
    if sends_bits:
        return f"{name} sends {' plus '.join(sends_bits)}."
    return ""


def _veto_view(graded: Mapping[str, Any]) -> dict[str, Any] | None:
    veto = graded.get("veto_summary") or None
    if not veto:
        return None
    return {k: veto.get(k) for k in ("band", "label", "outrage", "explained_by_roster", "hurt_roster_id")}


def _idea(league: _League, graded: Mapping[str, Any], transfers: Sequence[mt.Transfer], *, edits: int, note: str) -> dict[str, Any]:
    user = league.user_rid
    teams = [
        _team_view(t, _fit_text(league, t["roster_id"], t["team_name"], t["receives"], t["sends"]))
        for t in graded["teams"]
    ]
    me = next(t for t in teams if t["roster_id"] == user)
    others = [t for t in teams if t["roster_id"] != user]
    got = ", ".join(a["label"] for a in me["receives"]) or "nothing"
    gave = ", ".join(a["label"] for a in me["sends"]) or "nothing"
    summary = graded["summary"]
    return {
        "id": idea_id(transfers),
        "headline": f"{' + '.join(t['team_name'] for t in others)}: you get {got}, you send {gave}",
        "teams": teams,
        "flows": graded["flows"],
        "partners": [{"roster_id": t["roster_id"], "team_name": t["team_name"]} for t in others],
        "user": {
            "roster_id": user,
            "trade_score": me["trade_score"],
            "market_delta": me["market_delta"],
            "lineup_delta": me["lineup_delta"],
            "outcome": me["outcome"],
        },
        "summary": {k: summary.get(k) for k in ("headline", "balance", "most_hurt_roster_id", "best_off_roster_id", "market_sum")},
        "veto": _veto_view(graded),
        "variant": {"edits": edits, "note": note} if edits else None,
        "analyzer_request": {
            "transfers": [t.to_public() for t in transfers],
            "perspective_roster_id": user,
        },
    }


def _passes(graded: Mapping[str, Any]) -> bool:
    return graded.get("status") == "ok" and all(t.get("tone") in PASS_TONES for t in graded["teams"])


def _vetoed(graded: Mapping[str, Any]) -> bool:
    """True when the commissioner read (trade_veto.assess) would flag the deal for review."""

    return str((graded.get("veto_summary") or {}).get("band") or "") in VETO_BLOCK_BANDS


def _repair(league: _League, graded: Mapping[str, Any], base: Sequence[mt.Transfer]) -> tuple[mt.Transfer, ...] | None:
    """One extra asset that lifts the single failing team: sent by the team that
    sends to it, sized to the shortfall, never one that team needs itself."""

    short = [t for t in graded["teams"] if t.get("tone") not in PASS_TONES]
    if len(short) != 1 or short[0].get("tone") != "counter" or len(base) >= 4:
        return None
    hurt = short[0]["roster_id"]
    gap = max(0.0, -_num(short[0]["market_delta"]))
    giver = next(t.from_roster for t in base if t.to_roster == hurt)
    used = {t.asset_id for t in base}
    keep = league.need_pos.get(giver, {})
    pool = [
        a for a in league.sendable.get(giver, [])
        if a.player_id not in used and a.position not in keep
        and (a.kind != "pick" or league.want(hurt, a) > 0)
    ]
    if not pool:
        return None
    pick = min(pool, key=lambda a: (abs(a.value - gap), a.player_id))
    return (*base, mt.Transfer(pick.kind, pick.player_id, giver, hurt))


def find_three_team_ideas(
    ctx: engine.TradeContext,
    user_roster_id: str,
    *,
    untouchable_ids: set[str] | None = None,
    time_budget: float = DEFAULT_TIME_BUDGET_SECONDS,
    max_ideas: int = MAX_IDEAS,
    max_verify: int = MAX_VERIFY,
    max_partners: int = MAX_PARTNERS,
    clock=time.monotonic,
) -> dict[str, Any]:
    """Search for 3-team ideas for ``user_roster_id`` (see module docstring).

    Returns ``{"status": "ok", "ideas": [...], "search": {...}}``; ``search``
    reports what was bounded (partners considered, candidates priced / verified,
    whether the time budget cut the search short). Never raises for a league that
    simply has no fit: that is ``ideas == []`` with ``search.reason``."""

    deadline = clock() + max(0.0, time_budget)
    user = str(user_roster_id)
    if user not in ctx.by_rid or len(ctx.by_rid) < 3:
        return {"status": "ok", "ideas": [], "search": {"reason": "league_too_small", "partners": 0, "candidates": 0, "verified": 0, "truncated": False}}
    league = _League(ctx, user, set(untouchable_ids or ()))
    search: dict[str, Any] = {"partners": 0, "candidates": 0, "verified": 0, "variants": 0, "vetoed": 0, "picks_in_play": 0, "truncated": False, "reason": ""}
    if user not in league.need_pos:
        search["reason"] = "needs_unavailable"
        return {"status": "ok", "ideas": [], "search": search}

    scored = sorted(
        ((league.pair_fit(rid), rid) for rid in league.need_pos if rid != user),
        key=lambda x: (-x[0], x[1]),
    )
    partners = [rid for fit, rid in scored if fit > 0][:max_partners]
    search["partners"] = len(partners)
    search["picks_in_play"] = sum(a.kind == "pick" for rid in partners + [user] for a in league.sendable.get(rid, []))
    cands = _candidates(league, partners) if len(partners) >= 2 else []
    search["candidates"] = len(cands)
    queue = _order(cands)[:max_verify]
    ideas: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_pair: dict[tuple[str, str], int] = {}
    near: list[tuple[tuple[str, str], tuple[mt.Transfer, ...]]] = []

    def grade(transfers: Sequence[mt.Transfer]) -> Mapping[str, Any]:
        search["verified"] += 1
        return engine.grade_transfers(ctx, list(transfers), perspective_roster_id=user, include_veto=True)

    for cand in queue:
        if len(ideas) >= max_ideas:
            break
        if clock() >= deadline:
            search["truncated"] = True
            break
        if per_pair.get(cand.pair, 0) >= MAX_IDEAS_PER_PAIR:
            continue
        graded = grade(cand.transfers)
        if _passes(graded) and _vetoed(graded):
            search["vetoed"] += 1
        elif _passes(graded):
            iid = idea_id(cand.transfers)
            if iid not in seen:
                seen.add(iid)
                per_pair[cand.pair] = per_pair.get(cand.pair, 0) + 1
                ideas.append(_idea(league, graded, cand.transfers, edits=0, note=""))
        elif graded.get("status") == "ok" and len(near) < MAX_VARIANTS:
            repaired = _repair(league, graded, cand.transfers)
            if repaired:
                near.append((cand.pair, repaired))

    for pair, repaired in near:
        if len(ideas) >= max_ideas:
            break
        if clock() >= deadline:
            search["truncated"] = True
            break
        graded = grade(repaired)
        search["variants"] += 1
        iid = idea_id(repaired)
        if _passes(graded) and _vetoed(graded):
            search["vetoed"] += 1
        elif _passes(graded) and iid not in seen and per_pair.get(pair, 0) < MAX_IDEAS_PER_PAIR:
            seen.add(iid)
            per_pair[pair] = per_pair.get(pair, 0) + 1
            extra = repaired[-1]
            ideas.append(_idea(
                league, graded, repaired, edits=1,
                note=f"One added piece ({ctx.names.get(extra.from_roster, extra.from_roster)} also sends "
                     f"{league.label(extra.asset_id)}) brings every team to fair.",
            ))

    ideas.sort(key=lambda i: (
        -min(t["trade_score"] for t in i["teams"]), -_num(i["user"]["trade_score"]), i["id"],
    ))
    if not ideas:
        search["reason"] = "no_fit"
    # Surfacing the band cut keeps the bar honest in the UI copy.
    search["bar"] = {"tones": sorted(PASS_TONES), "min_score": bands.COUNTER}
    return {"status": "ok", "ideas": ideas[:max_ideas], "search": search}
