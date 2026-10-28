"""Interesting-trade feed for the external content/ad bot.

Backs ``GET /v1/external/trades/interesting`` (docs/external-trades-interesting.md).

Every item is a concrete 2-3 player (or player + pick) trade built ONLY from
data the app already holds: the shared players table run through the app's own
valuation lens (``league_value_settings.apply_valuation_lens`` -- the same
Superflex / TE-premium math every league screen uses), ages, injury fields,
usage-trend fields and Sleeper roster/injury state in ``data/players.db``, and
the app's own pick curve (``trade_ideas``). Nothing is league- or user-specific
and nothing is invented.

Verdicts are NOT a new model. Each candidate is graded by the same engine the
signed-in Trade Analyzer uses: ``trade_analyzer_fit.evaluate_trade_analyzer_fit``
-> ``trade_offer_analyzer.decide_offer_verdict``. That engine is roster-aware,
and a public feed has no roster, so it is run against a *reference roster*: a
league-median team made of real players (see ``reference_roster``). The
response says so (``verdict_basis``).

Pure builders live here (no I/O); ``load_and_build`` is the cached front door.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

import pandas as pd

from modules import (
    league_value_settings,
    player_eligibility,
    public_dynasty_values,
    trade_analyzer_assembly,
    trade_analyzer_fit,
    trade_grade,
    trade_hub_engine,
    trade_offer_analyzer,
    trade_ideas,
)

logger = logging.getLogger(__name__)

FORMATS = ("1qb", "superflex")
LENSES = ("ppr", "tep")
VALUATION_LENS = "Dynasty"
STRATEGY = trade_hub_engine.DEFAULT_ANALYZER_STRATEGY  # the neutral strategy the Analyzer defaults to
POSITIONS = ("QB", "RB", "WR", "TE")
TEAMS = 12

TYPE_BUY_LOW = "buy_low_window"
TYPE_SELL_HIGH = "sell_high_cliff"
TYPE_ARBITRAGE = "positional_arbitrage"
TYPE_PICK = "pick_for_player"
TYPE_CONSOLIDATION = "consolidation"
TYPE_STASH = "injury_return_stash"
TYPES = (TYPE_BUY_LOW, TYPE_SELL_HIGH, TYPE_ARBITRAGE, TYPE_PICK, TYPE_CONSOLIDATION, TYPE_STASH)
TYPE_LABELS = {
    TYPE_BUY_LOW: "Buy-low window",
    TYPE_SELL_HIGH: "Sell-high before the cliff",
    TYPE_ARBITRAGE: "Positional arbitrage",
    TYPE_PICK: "Pick for player",
    TYPE_CONSOLIDATION: "2-for-1 consolidation",
    TYPE_STASH: "Injury-return stash",
}

# Verdict tones we are willing to advertise. A "counter"/"decline" is not an
# interesting trade to post.
ADVERTISABLE_TONES = ("accept", "fair")

MIN_STAR_VALUE = 2500  # ignore assets too small to be worth a post
CLIFF_AGE = {"RB": 27, "WR": 29, "TE": 30, "QB": 34}
MAX_CANDIDATES_PER_TYPE = 14
CACHE_TTL_SECONDS = 600
MAX_SINCE_DAYS = 14
SPICE_VERSION = "spice-v1"

SPICE_DEFINITION = {
    "version": SPICE_VERSION,
    "scale": "0-100 (sum of the four parts below, clamped)",
    "parts": {
        "star_power": "0-25: value of the most valuable player/pick in the deal (value / 10,000 * 25)",
        "edge": "0-30: the Trade Analyzer's own posture-adjusted value_delta for the side we recommend (value_delta / 20, capped at 30)",
        "story_signal": "0-30: how strong the type's own trigger is (size of the market-vs-model gap, years past the age cliff, usage-trend size, format value jump, ...)",
        "newsy": "0-15: 15 if a fresh Sleeper injury/news timestamp (<= 7 days) is on a player in the deal, else 5 for a usage-trend read, else 0",
    },
}

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _h(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def settings_for(fmt: str, lens: str) -> dict[str, Any]:
    settings = public_dynasty_values.settings_for_format(fmt)
    settings["te_premium"] = lens == "tep"
    return settings


def lens_label(fmt: str, lens: str) -> str:
    return f"{'Superflex' if fmt == 'superflex' else '1QB'} {'TEP' if lens == 'tep' else 'PPR'}"


def _valued(players_df: pd.DataFrame, fmt: str, lens: str) -> pd.DataFrame:
    """Eligible players valued under the app's own lens, strategy-adjusted
    exactly like the signed-in Trade Analyzer (Dynasty score field)."""

    frame = player_eligibility.filter_current_fantasy_players(players_df, surface="external_interesting_trades")
    if frame is None or frame.empty:
        return pd.DataFrame()
    frame = frame[frame["position"].isin(POSITIONS)]
    valued = league_value_settings.apply_valuation_lens(frame, VALUATION_LENS, settings_for(fmt, lens))
    score_field = league_value_settings.valuation_score_field(VALUATION_LENS)
    valued = trade_hub_engine.apply_strategy_age_curve(valued, STRATEGY, score_field)
    valued = valued.copy()
    valued["player_id"] = valued["player_id"].astype(str)
    return valued


def _lineup_counts(settings: Mapping[str, Any]) -> dict[str, int]:
    return {
        "QB": int(settings.get("qb_count") or 1) + int(settings.get("superflex_count") or 0),
        "RB": int(settings.get("rb_count") or 2),
        "WR": int(settings.get("wr_count") or 3),
        "TE": int(settings.get("te_count") or 1),
    }


def reference_roster(frame: pd.DataFrame, settings: Mapping[str, Any], score_field: str) -> pd.DataFrame:
    """A league-median team made of REAL players, for roster-aware grading.

    For each position with ``c`` starting slots, take ``c + 1`` consecutive
    players starting at that position's league-median starter rank
    (``teams * c / 2``). That is the team the Analyzer would be asked about
    if the asker were exactly average, so the verdict is not tilted to any
    one roster. Deterministic for a given players table.
    """

    counts = _lineup_counts(settings)
    teams = int(settings.get("league_size") or TEAMS)
    parts = []
    for pos, c in counts.items():
        pool = frame[frame["position"] == pos].sort_values([score_field, "player_id"], ascending=[False, True])
        mid = max(0, int(round(teams * c / 2.0)) - 1)
        parts.append(pool.iloc[mid : mid + c + 1])
    return pd.concat(parts) if parts else pd.DataFrame()


# ---------------------------------------------------------------------------
# context + evaluation
# ---------------------------------------------------------------------------


class Context:
    def __init__(self, players_df: pd.DataFrame, fmt: str, lens: str, now: datetime):
        self.fmt, self.lens, self.now = fmt, lens, now
        self.score_field = league_value_settings.valuation_score_field(VALUATION_LENS)
        self.settings = settings_for(fmt, lens)
        frame = _valued(players_df, fmt, lens)
        self.frame = frame
        sf = self.score_field
        if frame.empty:
            self.pool = frame
            self.baseline = frame
            return
        base_1qb = _valued(players_df, "1qb", "ppr").set_index("player_id")[sf]
        fmt_ppr = _valued(players_df, fmt, "ppr").set_index("player_id")[sf]
        frame["v"] = pd.to_numeric(frame[sf], errors="coerce").fillna(0.0)
        frame["v_1qb_ppr"] = frame["player_id"].map(base_1qb).fillna(frame["v"])
        frame["v_fmt_ppr"] = frame["player_id"].map(fmt_ppr).fillna(frame["v"])
        for col in ("market_score", "age", "production_score", "opportunity_score", "recency_trend", "news_updated"):
            frame[col] = pd.to_numeric(frame[col], errors="coerce") if col in frame.columns else float("nan")
        eligible = frame["valuation_trade_eligible"].fillna(True).astype(bool) if "valuation_trade_eligible" in frame.columns else True
        self.pool = frame[(frame["v"] > 0) & eligible].sort_values(["v", "player_id"], ascending=[False, True])
        self.baseline = reference_roster(self.pool, self.settings, sf)
        self.current_context_cache: dict[str, Any] = {}

    # --- assets ----------------------------------------------------------
    def asset(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return trade_analyzer_assembly.player_asset_from_mapping(row, score_field=self.score_field)

    def pick_asset(self, season: int, rnd: int, tier: str) -> dict[str, Any]:
        label = f"{season} Round {rnd} pick ({tier} projection)"
        score = trade_ideas._round_tier_base_value(rnd, tier)
        return trade_analyzer_assembly.pick_asset_from_mapping(
            {"label": label, "score": score, "season": season, "round": rnd, "original_roster_id": f"generic-{tier}"}
        )

    # --- verdict (the app's own evaluator) ----------------------------------
    def evaluate(self, send_assets: list[dict], receive_assets: list[dict]) -> dict[str, Any] | None:
        send_ids = {a["player_id"] for a in send_assets if a.get("asset_type") == "player"}
        recv_ids = {a["player_id"] for a in receive_assets if a.get("asset_type") == "player"}
        base = self.baseline[~self.baseline["player_id"].isin(send_ids | recv_ids)]
        extra = self.frame[self.frame["player_id"].isin(send_ids)]
        roster = pd.concat([base, extra]).drop_duplicates(subset=["player_id"]).reset_index(drop=True)
        fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
            my_team_df=roster,
            all_players_df=self.frame,
            send_assets=send_assets,
            receive_assets=receive_assets,
            metrics=None,
            strategy=STRATEGY,
            lineup_settings=self.settings,
            score_field=self.score_field,
        )
        if not fit or not fit.get("available"):
            return None
        verdict = trade_offer_analyzer.decide_offer_verdict(
            fit, send_assets=send_assets, receive_assets=receive_assets
        )
        return {"fit": fit, "verdict": verdict}


def _near(pool: pd.DataFrame, target: float, lo: float, hi: float, exclude: set[str], *, positions=None, min_age=None, max_age=None, limit=6):
    """Real players with value in [lo*target, hi*target], nearest to target first."""

    sub = pool[(pool["v"] >= lo * target) & (pool["v"] <= hi * target) & (~pool["player_id"].isin(exclude))]
    if positions:
        sub = sub[sub["position"].isin(positions)]
    if min_age is not None:
        sub = sub[sub["age"] >= min_age]
    if max_age is not None:
        sub = sub[sub["age"] <= max_age]
    sub = sub[sub["injury_status"].fillna("").astype(str).str.strip().isin(["", "Active"]) | (sub["injury_status"].isna())]
    if sub.empty:
        return []
    sub = sub.assign(_d=(sub["v"] - target).abs()).sort_values(["_d", "player_id"])
    return [r for _, r in sub.head(limit).iterrows()]


def _market(x: Any) -> float:
    """Market price on the app's value scale: FantasyCalc-derived
    ``market_score`` for a player, the pick curve's own value for a pick."""

    if isinstance(x, tuple):  # ("pick", season, round, tier)
        return float(trade_ideas._round_tier_base_value(x[2], x[3]))
    return _num(x.get("market_score"))


def _market_ok(send: Sequence[Any], receive: Sequence[Any], *, slack: float) -> bool:
    """Realism gate: the other side must plausibly accept. The market price of
    what we receive may not exceed ``slack`` x the market price of what we
    send (so the edge comes from the model disagreeing with the market, never
    from asking a counterparty to overpay by the market's own numbers)."""

    s, r = sum(_market(x) for x in send), sum(_market(x) for x in receive)
    return s > 0 and r > 0 and r <= slack * s


def _healthy(row: Mapping[str, Any]) -> bool:
    return _text(row.get("injury_status")) in ("", "Active", "NA") and _text(row.get("status")) in ("", "Active")


def _fmt(n: float) -> str:
    return f"{int(round(n)):,}"


def _who(row: Mapping[str, Any]) -> str:
    return f"{_text(row.get('name'))} ({_text(row.get('position'))}, {int(_num(row.get('age')))})"


# ---------------------------------------------------------------------------
# candidate generators -- each returns dicts:
#   {type, send:[rows|assets], receive:[...], signal: 0..1, facts: {...}, hook, why:[...]}
# ---------------------------------------------------------------------------


def _market_ratio(row: Mapping[str, Any]) -> float | None:
    """market_score / base (1QB PPR) model value: <1 means the market prices
    the player below the model. Both sides are format-matched (base format)."""

    market, base = _num(row.get("market_score")), _num(row.get("v_1qb_ppr"))
    if market <= 0 or base <= 0:
        return None
    return market / base


def gen_buy_low(ctx: Context) -> list[dict]:
    out = []
    for _, r in ctx.pool.iterrows():
        if r["position"] not in POSITIONS or r["v"] < MIN_STAR_VALUE or _num(r["age"]) > 28 or not _healthy(r):
            continue
        ratio = _market_ratio(r)
        trend = _num(r.get("recency_trend"))
        rising = _text(r.get("workload_trend")) == "Rising" or trend >= 0.10
        if ratio is None or ratio > 0.86 or ratio < 0.55 or r["v"] < 3500 or not rising:
            continue
        price = r["v"] * ratio  # what the market charges, on the format's scale
        exclude = {r["player_id"]}
        partners = _near(ctx.pool, price, 0.95, 1.06, exclude, min_age=_num(r["age"]) + 1, limit=3)
        for p in partners:
            if _text(p.get("workload_trend")) == "Rising":
                continue
            gap = 1.0 - ratio
            out.append(
                dict(
                    type=TYPE_BUY_LOW, send=[p], receive=[r], signal=min(1.0, gap / 0.35),
                    facts=dict(ratio=ratio, trend=trend, price=price),
                    figures=dict(market_price=price, gap_pct=int(round(gap * 100)), usage_trend=trend),
                    hook=f"{_text(r['name'])} is priced like a {_fmt(price)} asset, but the model has him at {_fmt(r['v'])} and his usage is climbing.",
                    why=[
                        f"Market price ({_fmt(price)}) sits {int(round(gap * 100))}% below our model value for {_text(r['name'])} ({_fmt(r['v'])}).",
                        f"Usage trend {trend:+.2f} vs his own baseline ({_text(r.get('workload_trend')) or 'n/a'} workload, {_text(r.get('opportunity_label')) or 'n/a'}).",
                        f"{_text(p['name'])} ({_fmt(p['v'])}) is the closest match to that {_fmt(price)} market price, at age {int(_num(p['age']))} vs {int(_num(r['age']))}.",
                    ],
                )
            )
    return out


def gen_sell_high(ctx: Context) -> list[dict]:
    out = []
    for _, s in ctx.pool.iterrows():
        pos, age = s["position"], _num(s["age"])
        cliff = CLIFF_AGE.get(pos)
        if cliff is None or age < cliff or s["v"] < 3000 or not _healthy(s):
            continue
        cooling = _text(s.get("workload_trend")) == "Cooling" or _num(s.get("recency_trend")) <= -0.10
        ratio = _market_ratio(s)
        priced_above = ratio is not None and ratio >= 1.0
        if not (cooling or priced_above):
            continue
        price = _num(s.get("market_score")) * (s["v"] / s["v_1qb_ppr"] if s["v_1qb_ppr"] > 0 else 1.0)
        price = max(price, s["v"])
        for p in _near(ctx.pool, price, 0.88, 1.04, {s["player_id"]}, max_age=min(26, age - 4), limit=6):
            if not _market_ok([s], [p], slack=1.05):
                continue
            yrs = age - cliff
            out.append(
                dict(
                    type=TYPE_SELL_HIGH, send=[s], receive=[p],
                    signal=min(1.0, (yrs + 1) / 4.0),
                    facts=dict(cliff=cliff, cooling=cooling),
                    figures=dict(market_price=price, cliff_age=cliff, years_younger=int(age - _num(p["age"])), usage_trend=_num(s.get("recency_trend"))),
                    hook=f"Sell {_text(s['name'])} ({int(age)}) while the market still pays {_fmt(price)}; {_text(p['name'])} is {int(age - _num(p['age']))} years younger.",
                    why=[
                        f"{_text(s['name'])} is {int(age)}; {pos}s typically fall off around {cliff}. Our model value is {_fmt(s['v'])} vs a market price near {_fmt(price)}.",
                        f"Usage trend {_num(s.get('recency_trend')):+.2f} ({_text(s.get('workload_trend')) or 'n/a'}).",
                        f"{_text(p['name'])} returns {_fmt(p['v'])} at age {int(_num(p['age']))}.",
                    ],
                )
            )
    return out


def gen_arbitrage(ctx: Context) -> list[dict]:
    out = []
    pool = ctx.pool
    if ctx.fmt == "superflex":  # receive the scarce QB for a skill player of the same value
        for _, q in pool[(pool["position"] == "QB") & (pool["v"] >= 4000) & (pool["age"] <= 33)].iterrows():
            if not _healthy(q):
                continue
            jump = q["v"] / q["v_1qb_ppr"] - 1 if q["v_1qb_ppr"] > 0 else 0
            for w in _near(pool, q["v"], 0.94, 1.06, {q["player_id"]}, positions=("RB", "WR", "TE"), min_age=_num(q["age"]) - 2, limit=2):
                out.append(
                    dict(
                        type=TYPE_ARBITRAGE, send=[w], receive=[q], signal=min(1.0, jump / 0.40),
                        facts=dict(kind="sf_qb", jump=jump),
                        figures=dict(value_1qb=q["v_1qb_ppr"], jump_pct=int(round(jump * 100))),
                        hook=f"In Superflex, {_text(q['name'])} and {_text(w['name'])} cost the same, but only one fills a scarce QB2 slot.",
                        why=[
                            f"{_text(q['name'])} is worth {_fmt(q['v'])} in Superflex vs {_fmt(q['v_1qb_ppr'])} in 1QB (+{int(round(jump * 100))}%).",
                            f"{_text(w['name'])} is {_fmt(w['v'])} in either format: a near-even swap on paper.",
                            "A second starting QB slot makes the QB the harder position to replace.",
                        ],
                    )
                )
    else:  # 1QB: sell the replaceable QB for a skill player at the same value
        for _, q in pool[(pool["position"] == "QB") & (pool["v"] >= 4500) & (pool["age"] >= 28)].iterrows():
            if not _healthy(q):
                continue
            for w in _near(pool, q["v"], 0.97, 1.10, {q["player_id"]}, positions=("RB", "WR"), max_age=_num(q["age"]) - 3, limit=2):
                out.append(
                    dict(
                        type=TYPE_ARBITRAGE, send=[q], receive=[w], signal=0.5,
                        facts=dict(kind="1qb_qb"),
                        figures=dict(years_younger=int(_num(q["age"]) - _num(w["age"]))),
                        hook=f"In 1QB there is one QB slot: {_text(q['name'])} and {_text(w['name'])} are priced the same, but the {w['position']} is the harder starter to replace.",
                        why=[
                            f"Only one starting QB slot: {_text(q['name'])} is worth {_fmt(q['v'])}, {_text(w['name'])} {_fmt(w['v'])}.",
                            f"{_text(w['name'])} is {int(_num(q['age']) - _num(w['age']))} years younger.",
                        ],
                    )
                )
    if ctx.lens == "tep":  # receive the TE the premium lifts, for a skill player of the same value
        for _, te in pool[(pool["position"] == "TE") & (pool["v"] >= 3000)].iterrows():
            if not _healthy(te):
                continue
            jump = te["v"] / te["v_fmt_ppr"] - 1 if te["v_fmt_ppr"] > 0 else 0
            if jump < 0.04:
                continue
            for w in _near(pool, te["v"], 0.94, 1.06, {te["player_id"]}, positions=("RB", "WR"), min_age=_num(te["age"]) - 1, limit=2):
                out.append(
                    dict(
                        type=TYPE_ARBITRAGE, send=[w], receive=[te], signal=min(1.0, jump / 0.20),
                        facts=dict(kind="tep", jump=jump),
                        figures=dict(value_without_premium=te["v_fmt_ppr"], jump_pct=int(round(jump * 100))),
                        hook=f"TE premium turns {_text(te['name'])} into a {_fmt(te['v'])} asset; {_text(w['name'])} costs the same and gets no boost.",
                        why=[
                            f"{_text(te['name'])} is worth {_fmt(te['v'])} with TE premium vs {_fmt(te['v_fmt_ppr'])} without (+{int(round(jump * 100))}%).",
                            f"{_text(w['name'])} is {_fmt(w['v'])}: a near-even swap on paper.",
                        ],
                    )
                )
    return out


def upcoming_draft_year(today: date) -> int:
    return today.year + 1 if today.month >= 5 else today.year


def gen_pick_for_player(ctx: Context) -> list[dict]:
    out = []
    year = upcoming_draft_year(ctx.now.date())
    pool = ctx.pool
    for rnd, tier in ((1, "mid"), (1, "early"), (2, "mid")):
        pv = trade_ideas._round_tier_base_value(rnd, tier)
        # A: pay the pick for a young proven producer the app values above it
        for _, p in pool[(pool["v"] >= pv * 1.04) & (pool["v"] <= pv * 1.25) & (pool["age"] <= 25)].iterrows():
            if not _healthy(p) or _num(p.get("production_score")) < 8500 or not _market_ok([("pick", year, rnd, tier)], [p], slack=1.05):
                continue
            out.append(
                dict(
                    type=TYPE_PICK, send=[("pick", year, rnd, tier)], receive=[p],
                    signal=min(1.0, (p["v"] / pv - 1) / 0.20),
                    facts=dict(pick_value=pv, direction="buy"),
                    figures=dict(production_score=_num(p.get("production_score")), opportunity_score=_num(p.get("opportunity_score"))),
                    hook=f"A {year} round {rnd} pick buys {_text(p['name'])}, who is already producing.",
                    why=[
                        f"The app prices a {year} round {rnd} ({tier}) at {_fmt(pv)}; {_text(p['name'])} is {_fmt(p['v'])} at age {int(_num(p['age']))}.",
                        f"Production score {_fmt(_num(p.get('production_score')))} (opportunity {_fmt(_num(p.get('opportunity_score')))}): proven, not projected.",
                    ],
                )
            )
        # B: cash an aging starter for the pick before the age curve takes it
        for _, s in pool[(pool["v"] >= pv * 0.97) & (pool["v"] <= pv * 1.10) & (pool["position"].isin(["RB", "WR", "TE"]))].iterrows():
            cliff = CLIFF_AGE.get(s["position"], 99)
            if not _healthy(s) or _num(s["age"]) < cliff - 1 or not _market_ok([s], [("pick", year, rnd, tier)], slack=1.05):
                continue
            out.append(
                dict(
                    type=TYPE_PICK, send=[s], receive=[("pick", year, rnd, tier)],
                    signal=min(1.0, (_num(s["age"]) - cliff + 2) / 4.0),
                    facts=dict(pick_value=pv, direction="sell"),
                    figures=dict(cliff_age=cliff),
                    hook=f"Turn {_text(s['name'])} ({int(_num(s['age']))}) into a {year} round {rnd} pick while he still carries first-round value.",
                    why=[
                        f"{_text(s['name'])} is {_fmt(s['v'])}; the app prices a {year} round {rnd} ({tier}) at {_fmt(pv)}.",
                        f"At {int(_num(s['age']))}, {s['position']}s are at or near the {cliff} cliff; the pick does not age.",
                    ],
                )
            )
    return out


def gen_consolidation(ctx: Context) -> list[dict]:
    out = []
    pool = ctx.pool
    for _, r in pool[(pool["v"] >= 5500) & (pool["age"] <= 29)].iterrows():
        if not _healthy(r):
            continue
        mids = pool[(pool["v"] >= 0.30 * r["v"]) & (pool["v"] <= 0.62 * r["v"]) & (pool["player_id"] != r["player_id"])]
        mids = mids[[_healthy(x) for _, x in mids.iterrows()]]
        rows = [x for _, x in mids.head(40).iterrows()]
        best = []
        for i, a in enumerate(rows):
            for b in rows[i + 1 :]:
                tot = a["v"] + b["v"]
                if 0.82 * r["v"] <= tot <= 1.0 * r["v"]:
                    best.append((abs(tot - 0.92 * r["v"]), a["player_id"], b["player_id"], a, b))
        best.sort(key=lambda t: t[:3])
        for _, _, _, a, b in best[:6]:
            if not _market_ok([a, b], [r], slack=1.0):
                continue
            out.append(
                dict(
                    type=TYPE_CONSOLIDATION, send=[a, b], receive=[r],
                    signal=min(1.0, r["v"] / 9000.0),
                    facts=dict(total=a["v"] + b["v"]),
                    hook=f"Two starters for one star: {_text(a['name'])} + {_text(b['name'])} for {_text(r['name'])}.",
                    why=[
                        f"{_text(a['name'])} ({_fmt(a['v'])}) + {_text(b['name'])} ({_fmt(b['v'])}) = {_fmt(a['v'] + b['v'])} for one {_fmt(r['v'])} player.",
                        "The Analyzer credits the side that ends up with the best single asset; depth is replaceable, a star is not.",
                    ],
                )
            )
    return out


def gen_injury_stash(ctx: Context) -> list[dict]:
    out = []
    pool = ctx.pool
    window = trade_grade.season_window(ctx.settings)
    for _, r in pool[(pool["v"] >= 2000) & (pool["age"] <= 27)].iterrows():
        status = _text(r.get("injury_status"))
        if status not in ("IR", "Out", "PUP"):
            continue
        absence = trade_grade.estimate_injury_absence(
            r.get("status"), status, body_part=r.get("injury_body_part"), notes=r.get("injury_notes"), window=window
        )
        if absence is None or absence.season_ending or absence.weeks < 3:
            continue
        # pay with a healthy player of equal listed value; the Analyzer's own
        # injury pricing (trade_grade) decides whether the wait is worth it
        for p in _near(pool, r["v"], 0.90, 1.15, {r["player_id"]}, min_age=_num(r["age"]) + 1, limit=4):
            out.append(
                dict(
                    type=TYPE_STASH, send=[p], receive=[r],
                    signal=min(1.0, absence.weeks / 8.0),
                    facts=dict(weeks=absence.weeks, status=status),
                    figures=dict(estimated_weeks_out=int(absence.weeks)),
                    hook=f"{_text(r['name'])} is {status} ({_text(r.get('injury_body_part')) or 'injury'}); the discount is the buying window.",
                    why=[
                        f"{status} designation, estimated {int(absence.weeks)} weeks out ({absence.basis}; no return date is on record).",
                        f"Model value {_fmt(r['v'])} at age {int(_num(r['age']))}; {_text(p['name'])} ({_fmt(p['v'])}) is an equal-value healthy player.",
                    ],
                )
            )
    return out


GENERATORS = {
    TYPE_BUY_LOW: gen_buy_low,
    TYPE_SELL_HIGH: gen_sell_high,
    TYPE_ARBITRAGE: gen_arbitrage,
    TYPE_PICK: gen_pick_for_player,
    TYPE_CONSOLIDATION: gen_consolidation,
    TYPE_STASH: gen_injury_stash,
}


# ---------------------------------------------------------------------------
# item assembly
# ---------------------------------------------------------------------------


def _player_view(row: Mapping[str, Any]) -> dict[str, Any]:
    age = _num(row.get("age"))
    return {
        "kind": "player",
        "player_id": _text(row.get("player_id")),
        "name": _text(row.get("name")),
        "team": _text(row.get("team")) or None,
        "position": _text(row.get("position")),
        "age": round(age, 1) if age > 0 else None,
        "value": int(round(_num(row.get("v", row.get("score"))))),
        "injury_status": _text(row.get("injury_status")) or None,
    }


def _pick_view(asset: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": "pick",
        "label": asset["label"],
        "season": asset.get("season"),
        "round": asset.get("round"),
        "value": int(asset.get("score") or 0),
    }


def _view(asset: Mapping[str, Any], source: Any) -> dict[str, Any]:
    if asset["asset_type"] == "pick":
        return _pick_view(asset)
    return _player_view({**source, "v": asset["score"]})


def item_id(ctype: str, fmt: str, lens: str, send_keys: Sequence[str], recv_keys: Sequence[str]) -> str:
    raw = f"{ctype}|{fmt}|{lens}|{','.join(sorted(send_keys))}>{','.join(sorted(recv_keys))}"
    return "it_" + hashlib.sha256(raw.encode()).hexdigest()[:14]


def _key(x: Any) -> str:
    return f"pick:{x['pick_id']}" if x.get("asset_type") == "pick" else str(x["player_id"])


def _spice(ctx: Context, cand: dict, assets: list[dict], rows: list[Mapping[str, Any]], value_delta: int) -> dict[str, Any]:
    top = max((int(a.get("score") or 0) for a in assets), default=0)
    star = min(25.0, top / 10000.0 * 25.0)
    edge = min(30.0, max(0.0, value_delta) / 20.0)
    story = min(30.0, 30.0 * float(cand.get("signal") or 0.0))
    now_ms = ctx.now.timestamp() * 1000
    fresh = any(_num(r.get("news_updated")) > 0 and now_ms - _num(r.get("news_updated")) <= 7 * 86400 * 1000 for r in rows)
    trendy = any(abs(_num(r.get("recency_trend"))) >= 0.10 for r in rows)
    newsy = 15.0 if fresh else (5.0 if trendy else 0.0)
    total = max(0, min(100, int(round(star + edge + story + newsy))))
    return {
        "spice_score": total,
        "spice_breakdown": {
            "star_power": round(star, 1), "edge": round(edge, 1),
            "story_signal": round(story, 1), "newsy": round(newsy, 1), "version": SPICE_VERSION,
        },
    }


SHARE_CARD_SIZE = 1600
SHARE_CARD_BRAND = "FantasyDesk"
SHARE_CARD_DESTINATION = "https://fantasydesk.app"


def share_card_descriptor(iid: str, fmt: str, lens: str) -> dict[str, Any]:
    """The `share_card` block of an item. The PNG is exactly width x height,
    all content sits inside `safe_area` (centered, 8% margins), `focus` is the
    centre of that area for centered zoom/pan."""

    from modules import share_card_renderer

    size = SHARE_CARD_SIZE
    return {
        "available": True,
        "path": f"/v1/external/trades/interesting/{iid}/share-card.png?format={fmt}&lens={lens}",
        "content_type": "image/png",
        "width": size,
        "height": size,
        "brand": SHARE_CARD_BRAND,
        "destination": SHARE_CARD_DESTINATION,
        "safe_area": share_card_renderer.square_safe_area(size),
        "focus": {"x": 0.5, "y": 0.5},
        "auth": "same static bearer API key as every /v1/external/* route",
    }


def _figure(value: Any) -> float:
    """A derived number cited in the free text, rounded the way the text prints it."""

    v = _num(value)
    return float(int(round(v))) if abs(v) >= 10 else round(v, 2)


_NUM_RE = re.compile(r"(?<![A-Za-z0-9.])[+-]?\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9])")


def structured_numbers(item: Mapping[str, Any]) -> set[float]:
    """Every number an item's free text may cite: send/receive asset values,
    ages, pick season/round, side totals, every `balance` field, and the
    documented derived `text_figures`."""

    allowed: set[float] = set()

    def add(x: Any) -> None:
        if x is None or isinstance(x, bool):
            return
        v = _num(x, float("nan"))
        if math.isnan(v):
            return
        allowed.add(round(abs(v), 2))
        allowed.add(float(int(round(abs(v)))))
        allowed.add(float(int(abs(v))))

    for side in ("send", "receive"):
        add(item[side].get("total_value"))
        for a in item[side]["assets"]:
            for k in ("value", "age", "season", "round"):
                add(a.get(k))
    for k in ("send_value", "receive_value", "raw_delta", "value_delta", "fit_total"):
        add(item["balance"].get(k))
    for v in (item.get("text_figures") or {}).values():
        add(v)
    return allowed


def unreconciled_numbers(item: Mapping[str, Any]) -> list[str]:
    """Numbers printed in `hook`/`why` that match no structured field or
    documented derived figure. Empty list == reconciled."""

    allowed = structured_numbers(item)
    bad = []
    for line in [item.get("hook") or "", *(item.get("why") or [])]:
        for tok in _NUM_RE.findall(line):
            if round(abs(float(tok.replace(",", ""))), 2) not in allowed:
                bad.append(tok)
    return bad


def build_candidates(ctx: Context, types: Sequence[str] = TYPES) -> list[dict[str, Any]]:
    """Generate, grade with the app's evaluator, and keep advertisable trades."""

    if ctx.pool is None or ctx.pool.empty:
        return []
    generated_at = ctx.now.isoformat()
    items: dict[str, dict] = {}
    for ctype in types:
        cands = GENERATORS[ctype](ctx)
        cands.sort(key=lambda c: (-float(c["signal"]), [str(x) if isinstance(x, tuple) else _text(x["player_id"]) for x in c["send"] + c["receive"]]))
        kept = 0
        for cand in cands:
            if kept >= MAX_CANDIDATES_PER_TYPE:
                break
            send_assets = [ctx.pick_asset(*x[1:]) if isinstance(x, tuple) else ctx.asset(x) for x in cand["send"]]
            recv_assets = [ctx.pick_asset(*x[1:]) if isinstance(x, tuple) else ctx.asset(x) for x in cand["receive"]]
            iid = item_id(ctype, ctx.fmt, ctx.lens, [_key(a) for a in send_assets], [_key(a) for a in recv_assets])
            if iid in items:
                continue
            graded = ctx.evaluate(send_assets, recv_assets)
            if not graded:
                continue
            verdict, fit = graded["verdict"], graded["fit"]
            if verdict.tone not in ADVERTISABLE_TONES:
                continue
            rows = [x for x in cand["send"] + cand["receive"] if not isinstance(x, tuple)]
            send_v = sum(int(a.get("score") or 0) for a in send_assets)
            recv_v = sum(int(a.get("score") or 0) for a in recv_assets)
            spice = _spice(ctx, cand, send_assets + recv_assets, rows, int(verdict.value_delta))
            send_view = [_view(a, x) for a, x in zip(send_assets, cand["send"])]
            recv_view = [_view(a, x) for a, x in zip(recv_assets, cand["receive"])]
            items[iid] = {
                "id": iid,
                "type": ctype,
                "type_label": TYPE_LABELS[ctype],
                "format": ctx.fmt,
                "lens": ctx.lens,
                "format_label": lens_label(ctx.fmt, ctx.lens),
                "send": {"assets": send_view, "total_value": send_v},
                "receive": {"assets": recv_view, "total_value": recv_v},
                "perspective": "The team that sends `send` and receives `receive` is the side we recommend.",
                "balance": {
                    "send_value": send_v,
                    "receive_value": recv_v,
                    "raw_delta": recv_v - send_v,
                    "value_delta": int(verdict.value_delta),
                    "fit_total": int(verdict.fit_total),
                    "direction": verdict.value_summary,
                },
                "verdict": {
                    "band": verdict.band,
                    "ui_verdict": verdict.ui_verdict,
                    "tone": verdict.tone,
                    "confidence": verdict.confidence,
                    "rationale": verdict.rationale,
                },
                "hook": cand["hook"],
                "why": cand["why"][:3],
                "text_figures": {k: _figure(v) for k, v in (cand.get("figures") or {}).items()},
                **spice,
                "generated_at": generated_at,
                "share_card": share_card_descriptor(iid, ctx.fmt, ctx.lens),
                "_players": [_text(r.get("player_id")) for r in rows],
            }
            bad = unreconciled_numbers(items[iid])
            if bad:  # single source of truth: never ship text that disagrees with the structure
                logger.warning("interesting trade %s dropped: text numbers not in structure: %s", iid, bad)
                del items[iid]
                continue
            kept += 1
    return list(items.values())


# ---------------------------------------------------------------------------
# selection: filters, dedupe, deterministic daily rotation
# ---------------------------------------------------------------------------


def _rotation_order(items: list[dict], day: date) -> list[dict]:
    """Deterministic order for one UTC day: best spice first with a +/-6 point
    daily shuffle, then round-robin across types in a day-seeded type order so
    one type cannot fill the whole feed. Same inputs + same day => same list."""

    by_type: dict[str, list[dict]] = {}
    for it in items:
        by_type.setdefault(it["type"], []).append(it)
    for lst in by_type.values():
        lst.sort(key=lambda i: (-(i["spice_score"] + (_h(day.isoformat(), i["id"]) % 1200) / 100.0 - 6.0), i["id"]))
    order = sorted(by_type, key=lambda t: (_h(day.isoformat(), t), t))
    ranked: list[dict] = []
    used_players: set[str] = set()
    i = 0
    while any(by_type.values()):
        t = order[i % len(order)]
        i += 1
        lst = by_type.get(t) or []
        while lst:
            cand = lst.pop(0)
            if used_players.isdisjoint(cand["_players"]):
                used_players.update(cand["_players"])
                ranked.append(cand)
                break
        if i > 10000:
            break
    return ranked


def parse_since(since: str | None, now: datetime) -> datetime | None:
    """Parse ``since``: ISO-8601, epoch seconds or epoch milliseconds (a
    numeric value >= 1e11 is read as milliseconds). Clamped to at most
    ``MAX_SINCE_DAYS`` back. Returns an aware UTC datetime (or None)."""

    if since is None or not str(since).strip():
        return None
    text = str(since).strip()
    try:
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            raw = float(text)
            moment = datetime.fromtimestamp(raw / 1000.0 if raw >= 1e11 else raw, timezone.utc)
        else:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError, OSError) as exc:
        raise ValueError("since must be an ISO-8601 timestamp, epoch seconds or epoch milliseconds.") from exc
    return max(moment.astimezone(timezone.utc), now - timedelta(days=MAX_SINCE_DAYS))


def select_items(
    candidates: list[dict],
    *,
    now: datetime,
    limit: int = 5,
    types: Sequence[str] | None = None,
    min_spice: int = 0,
    exclude_ids: Sequence[str] = (),
    since: datetime | None = None,
) -> list[dict]:
    """Filter + rotate. ``since`` keeps items whose ``generated_at`` is at or
    after it (items are generated fresh from current data on every request, so
    every item is stamped now: a past ``since`` never removes anything and a
    future one returns nothing). It is a freshness filter, not a "have I seen
    this" filter -- use ``exclude_ids`` for exact dedupe."""

    pool = [c for c in candidates if (not types or c["type"] in types) and c["spice_score"] >= min_spice]
    if since is not None:
        pool = [c for c in pool if datetime.fromisoformat(c["generated_at"]) >= since]
    skip = {str(x) for x in exclude_ids}
    today = now.astimezone(timezone.utc).date()
    ordered = [i for i in _rotation_order(list(pool), today) if i["id"] not in skip]
    return [{k: v for k, v in i.items() if not k.startswith("_")} for i in ordered[:limit]]


# ---------------------------------------------------------------------------
# front door
# ---------------------------------------------------------------------------


def build_payload_pool(players_df: pd.DataFrame, fmt: str, lens: str, now: datetime) -> list[dict]:
    return build_candidates(Context(players_df, fmt, lens, now))


def get_pool(db_path: str, fmt: str, lens: str, now: datetime | None = None) -> tuple[list[dict], float | None]:
    """Cached candidate pool + players.db mtime. Same loader the public
    dynasty-values route uses (``rankings.load_players``)."""

    from modules import rankings

    now = now or datetime.now(timezone.utc)
    try:
        mtime = os.path.getmtime(db_path)
    except OSError:
        mtime = None
    key = f"{db_path}:{fmt}:{lens}:{mtime}:{now.date().isoformat()}"
    t = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and t - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]["pool"], mtime
    players_df = rankings.load_players(db_path)
    if players_df is None or players_df.empty:
        return [], mtime
    pool = build_payload_pool(players_df, fmt, lens, now)
    with _cache_lock:
        _cache.clear() if len(_cache) > 8 else None
        _cache[key] = (t, {"pool": pool})
    return pool, mtime


def idea_for_share_card(item: Mapping[str, Any]) -> dict[str, Any]:
    """Map a feed item into the dict ``share_recommendation_cards.
    build_trade_share_card`` takes (same renderer the app's own cards use, no
    user/roster/league needed)."""

    def assets(side: Mapping[str, Any]) -> list[dict]:
        out = []
        for a in side["assets"]:
            if a["kind"] == "pick":
                out.append({"asset_type": "pick", "label": a["label"], "score": a["value"]})
            else:
                out.append(
                    {"asset_type": "player", "player_id": a["player_id"], "label": a["name"], "name": a["name"],
                     "position": a["position"], "team": a.get("team") or "", "score": a["value"]}
                )
        return out

    return {
        "send_assets": assets(item["send"]),
        "receive_assets": assets(item["receive"]),
        "trade_gain": int(item["balance"]["value_delta"]),
        "my_score": item["send"]["total_value"],
        "their_score": item["receive"]["total_value"],
        "reasoning_summary": " ".join(item["why"][:2]),
        "my_team_name": "Team A",
        "partner_team_name": "Team B",
        "tag": item["type_label"],
        "trade_confidence_label": str(item["verdict"]["confidence"]).lower().replace("confidence", "").strip().title(),
    }
