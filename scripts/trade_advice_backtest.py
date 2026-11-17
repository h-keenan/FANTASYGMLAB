"""Point-in-time backtest of the REAL trade valuation + Analyzer verdict on nflverse history.

Audit of 2026-11 (``docs/audits/2026-11-trade-advice-backtest.md``). For each historical date D (2021-2025:
mid-April, late May, Aug 20, Oct 20, Dec 1) it rebuilds, from data published before D only:

* the market input: the DynastyProcess value snapshot committed nearest before D (FantasyPros-ECR dynasty values;
  FantasyCalc itself keeps no archive), 1QB column as the production FantasyCalc input (``get_dynasty_values`` is
  fetched with numQbs=1, Superflex is the lens's own QB uplift) and the 2QB column as the Superflex *market baseline*;
* age at D, current-season and prior-season usage and PPG from nflverse weekly stats (weeks < D only), the latest
  published injury report, a usage-derived depth order;
* the production valuation chain as written in ``modules.rankings`` / ``modules.league_value_settings``:
  age curve, scarcity, ``production_usage_frame``, ``apply_role_and_opportunity``, ``apply_injury_risk_fields``,
  ``compose_composite_score``, ``apply_valuation_lens``, ``apply_strategy_age_curve``;
* the verdict: ``modules.trade_grade.grade_trade_for_user`` (Analyzer fit + ``decide_offer_verdict``), the same entry
  point Trade Hub uses.

Random 12-team leagues are drafted from the snapshot, random 1-for-1 / 2-for-1 / 1-for-2 / pick trades are drawn from
plausible value bands, graded as of D, and scored against what nflverse says happened: PPR points over replacement
for the rest of that season and the next two, the starting-lineup (hindsight-optimal) points delta of the receiving
roster, and the market-value change. ``rankings.load_players`` / ``build_players_table`` are never called and
``data/players.db`` is never opened. Nothing is written to ``data/``.

    python scripts/trade_advice_backtest.py run --nv NV --dp DP --out OUT [--per-league 120]
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

warnings.filterwarnings("ignore")

from modules import league_value_settings as lvs  # noqa: E402
from modules import rankings  # noqa: E402
from modules import trade_grade  # noqa: E402
from modules import trade_analyzer_fit, trade_hub_engine  # noqa: E402
from modules import trade_ideas  # noqa: E402

POS = ("QB", "RB", "WR", "TE")
DATES = ("04-15", "05-20", "08-20", "10-20", "12-01")
STRATEGIES = ("contender", "fringe_contender", "retool", "rebuild", "tank")
LEAGUES = {
    # name: (valuation lens settings, score field, superflex slots, te premium)
    "dynasty_1qb": dict(lens="Dynasty", fmt="Dynasty", qb="1QB", sf=0, tep=False),
    "dynasty_sf": dict(lens="Dynasty", fmt="Dynasty", qb="Superflex", sf=1, tep=False),
    "dynasty_sf_tep": dict(lens="Dynasty", fmt="Dynasty", qb="Superflex", sf=1, tep=True),
    "redraft_1qb": dict(lens="Non-Dynasty", fmt="Redraft", qb="1QB", sf=0, tep=False),
}
# Replacement rank for points-over-replacement (12 teams, 1QB/2RB/3WR/1TE/1FLEX; SF doubles QB).
REPL_RANK = {"QB": 12, "RB": 30, "WR": 42, "TE": 14}
REPL_RANK_SF = {"QB": 24, "RB": 30, "WR": 42, "TE": 14}
LINEUP = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}


def norm(name: str) -> str:
    return rankings._normalize_name(str(name))


# ------------------------------------------------------------------ history
class History:
    def __init__(self, nv: Path, dp: Path):
        self.nv, self.dp = Path(nv), Path(dp)
        frames = []
        for s in range(2020, 2027):
            d = pd.read_parquet(self.nv / f"spw_{s}.parquet")
            d = d[(d.season_type == "REG") & d.position.isin(POS)].copy()
            frames.append(d)
        spw = pd.concat(frames, ignore_index=True)
        spw["fantasy_points_ppr"] = spw["fantasy_points_ppr"].fillna(0.0)
        for c in ("targets", "receptions", "carries", "attempts", "rushing_yards", "receiving_yards", "passing_yards",
                  "passing_tds", "receiving_tds", "rushing_tds"):
            spw[c] = spw[c].fillna(0)
        self.spw = spw
        # weekly points [gsis][season] -> array[19] (nan = did not play)
        self.wk: dict[tuple[str, int], np.ndarray] = {}
        for (pid, season), g in spw.groupby(["player_id", "season"]):
            arr = np.full(20, np.nan)
            arr[g.week.astype(int).to_numpy()] = g.fantasy_points_ppr.to_numpy()
            self.wk[(pid, int(season))] = arr
        self.te_rec = {}  # (gsis, season) -> receptions array for TE premium
        te = spw[spw.position == "TE"]
        for (pid, season), g in te.groupby(["player_id", "season"]):
            arr = np.zeros(20)
            arr[g.week.astype(int).to_numpy()] = g.receptions.to_numpy()
            self.te_rec[(pid, int(season))] = arr
        pl = pd.read_csv(self.nv / "players.csv", low_memory=False)
        pl = pl[pl.position.isin(POS) & pl.gsis_id.notna()].copy()
        pl["key"] = pl.display_name.map(norm)
        pl["birth"] = pd.to_datetime(pl.birth_date, errors="coerce")
        self.players = pl.set_index("gsis_id")
        self.by_key: dict[tuple[str, str], list[str]] = {}
        for gsis, r in self.players.iterrows():
            self.by_key.setdefault((r.key, r.position), []).append(gsis)
        games = pd.read_csv(self.nv / "games.csv")
        games = games[games.game_type == "REG"].copy()
        games["gameday"] = pd.to_datetime(games.gameday)
        self.week_end = {}
        self.week_start = {}
        for (s, w), g in games.groupby(["season", "week"]):
            self.week_end[(int(s), int(w))] = g.gameday.max()
            self.week_start[(int(s), int(w))] = g.gameday.min()
        self.inj = {}
        for s in range(2020, 2027):
            p = self.nv / f"inj_{s}.csv"
            if p.exists():
                i = pd.read_csv(p, low_memory=False)
                i = i[i.game_type == "REG"]
                self.inj[s] = i
        self.team_by_season = spw.groupby(["season", "player_id"]).team.last().to_dict()
        self._repl = {}
        self._dp_cache = {}
        fc = pd.read_csv(ROOT / "data" / "fantasycalc_values.csv")
        fc = fc[fc.position.isin(POS)].value.sort_values(ascending=False).to_numpy(dtype=float)
        self.fc_curve = np.concatenate([fc, np.zeros(2000)])

    def completed_weeks(self, season: int, d: pd.Timestamp) -> int:
        n = 0
        for w in range(1, 19):
            e = self.week_end.get((season, w))
            if e is not None and e < d:
                n = w
        return n

    def season_over(self, season: int, d: pd.Timestamp) -> bool:
        return self.completed_weeks(season, d) >= 17

    # --- DP market snapshots
    def dp_players(self, label: str) -> pd.DataFrame:
        if label not in self._dp_cache:
            f = pd.read_csv(self.dp / f"{label}_values-players.csv", na_values=["NA"])
            self._dp_cache[label] = f
        return self._dp_cache[label]

    def dp_picks(self, label: str) -> pd.DataFrame:
        return pd.read_csv(self.dp / f"{label}_values-picks.csv", na_values=["NA"])

    def match(self, snap: pd.DataFrame, d: pd.Timestamp) -> pd.DataFrame:
        rows = []
        for r in snap.itertuples():
            if r.pos not in POS or pd.isna(r.value_1qb):
                continue
            cands = self.by_key.get((norm(r.player), r.pos))
            if not cands:
                continue
            if len(cands) > 1:
                dy = r.draft_year if pd.notna(r.draft_year) else None
                cands = sorted(cands, key=lambda g: (abs((self.players.loc[g, "draft_year"] or 0) - dy) if dy and pd.notna(self.players.loc[g, "draft_year"]) else 9,
                                                     -(self.players.loc[g, "last_season"] if pd.notna(self.players.loc[g, "last_season"]) else 0)))
            gsis = cands[0]
            p = self.players.loc[gsis]
            birth = p.birth
            age = (d - birth).days / 365.25 if pd.notna(birth) else (r.age if pd.notna(r.age) else np.nan)
            rows.append(dict(player_id=gsis, name=r.player, position=r.pos, team=r.team, age=age, years_exp=np.nan,
                             draft_year=p.draft_year, rookie_season=p.rookie_season,
                             value_1qb=float(r.value_1qb), value_2qb=float(r.value_2qb) if pd.notna(r.value_2qb) else float(r.value_1qb),
                             ecr_1qb=r.ecr_1qb, ecr_2qb=r.ecr_2qb))
        df = pd.DataFrame(rows).drop_duplicates("player_id")
        # DynastyProcess values (FantasyPros-ECR derived) have a far steeper tail than FantasyCalc, the production
        # market input. Rank-match each snapshot onto FantasyCalc's own current rank->value curve (order preserved).
        for col in ("value_1qb", "value_2qb"):
            order = df[col].rank(ascending=False, method="first").astype(int) - 1
            df[col] = self.fc_curve[order.to_numpy()]
        return df

    # --- stats before D
    def usage_before(self, season: int, upto_week: int) -> pd.DataFrame:
        s = self.spw[(self.spw.season == season) & (self.spw.week <= upto_week)]
        g = s.groupby("player_id").agg(games_played=("week", "count"), targets=("targets", "sum"), receptions=("receptions", "sum"),
                                       rush_attempts=("carries", "sum"), rushing_yards=("rushing_yards", "sum"),
                                       pass_attempts=("attempts", "sum"), pts=("fantasy_points_ppr", "sum"),
                                       passing_yards=("passing_yards", "sum"), passing_tds=("passing_tds", "sum"))
        return g

    def repl_ppg(self, season: int, sf: bool, tep: bool) -> dict[str, float]:
        key = (season, sf, tep)
        if key in self._repl:
            return self._repl[key]
        s = self.spw[self.spw.season == season]
        g = s.groupby(["player_id", "position"]).agg(pts=("fantasy_points_ppr", "sum"), gp=("week", "count"), rec=("receptions", "sum")).reset_index()
        if tep:
            g.loc[g.position == "TE", "pts"] += 0.5 * g.loc[g.position == "TE", "rec"]
        g = g[g.gp >= 6]
        g["ppg"] = g.pts / g.gp
        ranks = REPL_RANK_SF if sf else REPL_RANK
        out = {}
        for pos, k in ranks.items():
            v = g[g.position == pos].ppg.sort_values(ascending=False).to_numpy()
            out[pos] = float(v[min(k, len(v)) - 1]) if len(v) else 0.0
        self._repl[key] = out
        return out


# ------------------------------------------------------------------ valuation frame
def build_frame(h: History, label: str, season: int, d: pd.Timestamp, completed: int, league: dict, current_week: int) -> pd.DataFrame:
    snap = h.match(h.dp_players(label), d)
    snap = snap[snap.value_1qb > 0].copy()
    prior = h.usage_before(season - 1, 18).add_prefix("prior_")
    cur = h.usage_before(season, completed) if completed > 0 else h.usage_before(season, 0)
    df = snap.set_index("player_id").join(cur, how="left").join(prior, how="left").reset_index()
    df["years_exp"] = (season - pd.to_numeric(df.rookie_season, errors="coerce")).clip(lower=0)
    df["ppg"] = np.where(df.games_played.fillna(0) > 0, df.pts / df.games_played.replace(0, np.nan), np.nan)
    df["prior_ppg"] = df.prior_pts / df.prior_games_played.replace(0, np.nan)
    df["status"] = "Active"
    df["injury_status"] = ""
    df["injury_body_part"] = ""
    # latest published injury report (week = last completed week; the report for the week D falls in is not out yet)
    if completed > 0 and season in h.inj:
        i = h.inj[season]
        i = i[i.week == completed]
        m = i.drop_duplicates("gsis_id").set_index("gsis_id")
        stat = df.player_id.map(m.report_status).fillna("")
        df["injury_status"] = stat.where(stat.isin(["Out", "Doubtful", "Questionable"]), "")
        df["injury_body_part"] = df.player_id.map(m.report_primary_injury).fillna("")
    df = df.sort_values("value_1qb", ascending=False).reset_index(drop=True)
    df["search_rank"] = np.arange(1, len(df) + 1)
    df["value"] = df.value_1qb
    # usage-derived depth order within team+position (production reads Sleeper's chart; no history exists)
    usage = df.ppg.fillna(df.prior_ppg).fillna(0) + df.value_1qb / 5000.0
    df["_u"] = usage
    df["depth_chart_order"] = df.groupby(["team", "position"])._u.rank(ascending=False, method="first").astype(int)
    df["depth_chart_position"] = df.position
    df = df.drop(columns=["_u"])
    # canonical market chain (rankings._apply_market_valuation_context, with market_score = the snapshot value)
    df["market_score"] = df.value_1qb.astype(float)
    repl = {}
    for pos, rank in rankings.POSITION_REPLACEMENT_RANK.items():
        v = df.loc[df.position == pos, "market_score"].sort_values(ascending=False).reset_index(drop=True)
        repl[pos] = float(v.iloc[min(rank - 1, len(v) - 1)]) if len(v) else 0.0
    df["age_multiplier"] = rankings.age_multiplier_series(df.position, df.age)
    df["age_curve_score"] = (df.market_score * df.age_multiplier).clip(0, 12000)
    df["scarcity_score"] = [max(0.0, m - repl.get(p, 0.0)) * rankings.POSITION_SCARCITY_MULTIPLIER.get(p, 1.0) for m, p in zip(df.market_score, df.position)]
    df["scarcity_score"] = df.scarcity_score.clip(0, 10000)
    df["fantasycalc_value"] = df.market_score
    work = rankings.apply_role_and_opportunity(df)
    prod = rankings.production_usage_frame(work)
    for c in prod.columns:
        work[c] = prod[c]
    work = rankings.apply_injury_risk_fields(work)
    work = rankings.compose_composite_score(work)
    settings = dict(lvs.DEFAULT_LEAGUE_VALUE_SETTINGS)
    settings.update(league_format=league["fmt"], qb_format=league["qb"], te_premium=league["tep"], superflex_count=league["sf"],
                    current_week=current_week)
    work = lvs.apply_valuation_lens(work, league["lens"], settings)
    return work, settings


def pick_score(round_num: int, season: int, next_draft_year: int, slot_pct: float, qb_format: str) -> int:
    ctx = {"slot_percentile": slot_pct, "tier_bucket": "early" if slot_pct < 0.34 else "late" if slot_pct > 0.66 else "mid"}
    comp = trade_ideas._pick_value_components(
        season, round_num, 0, pd.DataFrame(), {"league_format": "Dynasty", "qb_format": qb_format, "league_size": 12},
        team_context=ctx, next_draft_year=next_draft_year)
    return int(comp["score"])


# ------------------------------------------------------------------ league + trades
def draft_league(df: pd.DataFrame, rng: np.random.Generator, sf: bool, n_teams: int = 12) -> list[list[int]]:
    """Snake draft by (noisy) snapshot value with positional caps. Returns row indices per team."""
    value = df.value_2qb if sf else df.value_1qb
    noisy = value.to_numpy() * rng.lognormal(0, 0.10, len(df))
    order = np.argsort(-noisy)
    caps = {"QB": 4 if sf else 3, "RB": 8, "WR": 9, "TE": 3}
    teams = [[] for _ in range(n_teams)]
    counts = [dict.fromkeys(POS, 0) for _ in range(n_teams)]
    taken = set()
    rounds = 20
    for r in range(rounds):
        seq = range(n_teams) if r % 2 == 0 else range(n_teams - 1, -1, -1)
        for t in seq:
            for idx in order:
                if idx in taken:
                    continue
                pos = df.position.iat[idx]
                if counts[t][pos] >= caps[pos]:
                    continue
                taken.add(idx)
                teams[t].append(int(idx))
                counts[t][pos] += 1
                break
    return teams


def team_strength(df: pd.DataFrame, rows: list[int], score: str, sf: bool) -> float:
    sub = df.iloc[rows]
    tot = 0.0
    used = set()
    for pos, n in LINEUP.items():
        s = sub[sub.position == pos].sort_values(score, ascending=False)
        n_eff = n + (1 if (sf and pos == "QB") else 0)
        tot += s[score].head(n_eff).sum()
        used |= set(s.head(n_eff).index)
    rest = sub[~sub.index.isin(used) & sub.position.isin(["RB", "WR", "TE"])].sort_values(score, ascending=False)
    tot += rest[score].head(1).sum()
    return float(tot)


def asset_player(row: pd.Series, score_col: str) -> dict:
    return {"asset_type": "player", "player_id": str(row.player_id), "name": row["name"], "label": row["name"], "position": row.position,
            "age": row.age, "score": int(row[score_col]), "team": row.team}


def fit_weekly_baselines(df: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward weekly baseline for the in-season lineup model (it reads ``proj_ppg``/``proj_sd``)."""
    g = df.games_played.fillna(0)
    pg = df.prior_games_played.fillna(0)
    cur = df.ppg.fillna(0)
    pri = df.prior_ppg.fillna(0)
    w_cur = g / (g + 6.0)
    base = np.where(pg > 0, pri, 0.0)
    est = np.where(g > 0, w_cur * cur + (1 - w_cur) * np.where(pg > 0, pri, cur), base)
    # No history at all: value-derived estimate (the model labels its own fallback basis)
    est = np.where((g == 0) & (pg == 0), df.value_1qb / 10000.0 * 17.0, est)
    df = df.copy()
    df["proj_ppg"] = est
    df["proj_sd"] = np.maximum(3.0, est * 0.55)
    df["proj_scoring_applied"] = False
    return df


def run_league(h: History, season: int, mmdd: str, lname: str, league: dict, per_league: int, rng: np.random.Generator, log) -> list[dict]:
    label = f"{season}-{mmdd}"
    d = pd.Timestamp(label)
    completed = h.completed_weeks(season, d)
    in_season = 0 < completed < 17
    current_week = completed + 1 if in_season else 0
    if lname == "redraft_1qb" and not in_season and mmdd != "08-20":
        return []
    frame, settings = build_frame(h, label, season, d, completed, league, current_week)
    frame = fit_weekly_baselines(frame)
    sf = bool(league["sf"])
    score_field = lvs.valuation_score_field(league["lens"])
    lineup_settings = dict(settings, qb_count=1, rb_count=2, wr_count=3, te_count=1, flex_count=1, superflex_count=league["sf"],
                           k_count=0, def_count=0)
    base_pool = frame.reset_index(drop=True)
    market_col = "value_2qb" if sf else "value_1qb"
    teams = draft_league(base_pool, rng, sf)
    strength = [team_strength(base_pool, t, score_field, sf) for t in teams]
    rank_order = np.argsort(-np.array(strength))
    rank_of = {int(t): i for i, t in enumerate(rank_order)}
    posture_by_rank = ["contender"] * 3 + ["fringe_contender"] * 3 + ["retool"] * 3 + ["rebuild"] * 2 + ["tank"]
    next_draft_year = season if mmdd in ("04-15", "05-20") else season + 1
    # pick market value (DP ecr -> value mapped through this snapshot's own ecr/value curve)
    snap = base_pool  # FantasyCalc-scale market columns + ECR (for pick slot -> value)
    picks = h.dp_picks(label)
    rostered = {i for t in teams for i in t}
    pool_rows = base_pool.index.difference(list(rostered))
    out = []
    pick_year = None
    m = picks.player.str.extract(r"(\d{4}) Pick (\d+)\.(\d+)")
    if m[0].notna().any():
        pick_year = int(m[0].dropna().iloc[0])
    strategies_cache: dict[str, pd.DataFrame] = {}
    waiver_cache: dict[str, pd.DataFrame] = {}
    ctx_cache: dict = {}
    for _ in range(per_league):
        a, b = rng.choice(len(teams), 2, replace=False)
        a, b = int(a), int(b)
        strat = posture_by_rank[rank_of[a]]
        if strat not in strategies_cache:
            curved = trade_hub_engine.apply_strategy_age_curve(base_pool, strat, score_field)
            strategies_cache[strat] = curved
            waiver_cache[strat] = curved.loc[curved.index.isin(pool_rows)]
        cp = strategies_cache[strat]
        mult = trade_hub_engine.strategy_adjusted_pick_score_multiplier(1.0, strat)
        slot_pct = {i: (rank_of[i] + 0.5) / 12.0 for i in range(12)}  # strongest team = lowest percentile = LATE pick
        slot_pct = {i: 1.0 - v for i, v in slot_pct.items()}
        kind = rng.choice(["1for1", "2for1", "1for2", "pick_for_player", "player_for_pick", "handcuff"], p=[0.30, 0.18, 0.12, 0.13, 0.13, 0.14])
        A = [i for i in teams[a] if base_pool.at[i, score_field] >= 800]
        B = [i for i in teams[b] if base_pool.at[i, score_field] >= 800]
        if len(A) < 3 or len(B) < 3:
            continue
        send, recv = [], []
        sidx, ridx = [], []
        picks_s, picks_r = [], []
        try:
            if kind == "1for1":
                p = int(rng.choice(A))
                v = base_pool.at[p, market_col]
                cand = [i for i in B if 0.55 * v <= base_pool.at[i, market_col] <= 1.6 * v]
                if not cand:
                    continue
                q = int(rng.choice(cand))
                sidx, ridx = [p], [q]
            elif kind == "2for1":
                p1, p2 = [int(x) for x in rng.choice(A, 2, replace=False)]
                tot = base_pool.at[p1, market_col] + base_pool.at[p2, market_col]
                cand = [i for i in B if 0.6 * tot <= base_pool.at[i, market_col] <= 1.15 * tot and base_pool.at[i, market_col] > max(base_pool.at[p1, market_col], base_pool.at[p2, market_col])]
                if not cand:
                    continue
                sidx, ridx = [p1, p2], [int(rng.choice(cand))]
            elif kind == "1for2":
                q1, q2 = [int(x) for x in rng.choice(B, 2, replace=False)]
                tot = base_pool.at[q1, market_col] + base_pool.at[q2, market_col]
                cand = [i for i in A if 0.6 * tot <= base_pool.at[i, market_col] <= 1.15 * tot and base_pool.at[i, market_col] > max(base_pool.at[q1, market_col], base_pool.at[q2, market_col])]
                if not cand:
                    continue
                sidx, ridx = [int(rng.choice(cand))], [q1, q2]
            elif kind == "handcuff":
                # a backup RB (depth 2) behind a top-24 market RB on the partner's team, bought with a comparable asset
                rb1 = base_pool[(base_pool.position == "RB") & (base_pool.depth_chart_order == 1)].set_index("team").market_score.to_dict()
                hc = [i for i in B if base_pool.at[i, "position"] == "RB" and base_pool.at[i, "depth_chart_order"] == 2
                      and rb1.get(base_pool.at[i, "team"], 0) >= 3500 and base_pool.at[i, market_col] <= 2500]
                if not hc:
                    continue
                q = int(rng.choice(hc))
                v = base_pool.at[q, market_col]
                cand = [i for i in A if 0.6 * v <= base_pool.at[i, market_col] <= 1.6 * v and base_pool.at[i, "position"] != "RB"]
                if not cand:
                    continue
                sidx, ridx = [int(rng.choice(cand))], [q]
            else:
                if pick_year is None:
                    continue
                rnd = int(rng.choice([1, 1, 2, 2, 3]))
                owner_is_a = kind == "pick_for_player"
                owner = a if owner_is_a else b
                pick_slot_pct = slot_pct[owner]
                ps = pick_score(rnd, pick_year, next_draft_year, pick_slot_pct, league["qb"])
                slot_in_round = int(round((1 - pick_slot_pct) * 11)) + 1  # 1 = earliest pick
                # market value of the pick slot by DP ECR curve (ecr -> value); pick ecr from the snapshot
                pk = picks[picks.player == f"{pick_year} Pick {rnd}.{slot_in_round:02d}"]
                if pk.empty:
                    continue
                ecr = float(pk.ecr_2qb.iloc[0] if sf else pk.ecr_1qb.iloc[0])
                col = "ecr_2qb" if sf else "ecr_1qb"
                cv = snap.dropna(subset=[col, market_col]).sort_values(col)
                mval = float(np.interp(ecr, cv[col].to_numpy(), cv[market_col].to_numpy()))
                cand = [i for i in B if 0.55 * mval <= base_pool.at[i, market_col] <= 1.6 * mval]
                if not cand:
                    continue
                q = int(rng.choice(cand))
                pick_asset = {"asset_type": "pick", "label": f"{pick_year} {rnd}.{slot_in_round:02d}", "score": int(round(ps * mult)),
                              "position": "PICK", "age": "", "player_id": None, "round": rnd, "season": pick_year,
                              "pick_slot": (rnd - 1) * 12 + slot_in_round, "pick_year": pick_year, "market_value": mval}
                if owner_is_a:
                    picks_s, sidx, ridx = [pick_asset], [], [q]
                else:
                    # player_for_pick: A sends a player from A, receives the pick from B
                    cand_a = [i for i in A if 0.55 * mval <= base_pool.at[i, market_col] <= 1.6 * mval]
                    if not cand_a:
                        continue
                    picks_r, sidx, ridx = [pick_asset], [int(rng.choice(cand_a))], []
        except ValueError:
            continue
        if len(set(sidx) & set(ridx)):
            continue
        if not (sidx or picks_s) or not (ridx or picks_r):
            continue
        send_assets = [asset_player(cp.loc[i], score_field) for i in sidx] + picks_s
        recv_assets = [asset_player(cp.loc[i], score_field) for i in ridx] + picks_r
        key = (strat, a)
        if key not in ctx_cache:
            my_team_ = cp.loc[teams[a]]
            ctx_cache[key] = trade_analyzer_fit.prepare_current_roster_context(my_team_, None, strat, lineup_settings, score_field, None)
        my_team = ctx_cache[key]["my_team_df"] if ctx_cache[key] else cp.loc[teams[a]]
        t0 = time.perf_counter()
        try:
            fit, verdict = trade_grade.grade_trade_for_user(
                my_team_df=my_team, all_players_df=cp, send_assets=send_assets, receive_assets=recv_assets,
                strategy=strat, lineup_settings=lineup_settings, score_field=score_field, waiver_df=waiver_cache[strat],
                current_context=ctx_cache.get(key))
        except Exception as exc:  # pragma: no cover - surfaced in the log
            log(f"grade error {label} {lname} {kind}: {type(exc).__name__}: {exc}")
            continue
        if verdict is None or not fit:
            continue
        dt_ms = (time.perf_counter() - t0) * 1000
        mk = lambda ids, ps_: float(sum(base_pool.at[i, market_col] for i in ids) + sum(p["market_value"] for p in ps_))  # noqa: E731
        rec = dict(
            season=season, date=label, mmdd=mmdd, league=lname, kind=str(kind), team=a, partner=b, strategy=strat, current_week=current_week,
            in_season=in_season, completed=completed,
            send_ids="|".join(str(base_pool.at[i, "player_id"]) for i in sidx), recv_ids="|".join(str(base_pool.at[i, "player_id"]) for i in ridx),
            send_names="; ".join([base_pool.at[i, "name"] for i in sidx] + [p["label"] for p in picks_s]),
            recv_names="; ".join([base_pool.at[i, "name"] for i in ridx] + [p["label"] for p in picks_r]),
            send_pick=picks_s[0]["pick_slot"] if picks_s else 0, recv_pick=picks_r[0]["pick_slot"] if picks_r else 0,
            pick_year=pick_year or 0,
            n_send=len(send_assets), n_recv=len(recv_assets),
            roster_ids="|".join(str(base_pool.at[i, "player_id"]) for i in teams[a]),
            send_depth="|".join(str(base_pool.at[i, "depth_chart_order"]) for i in sidx), recv_depth="|".join(str(base_pool.at[i, "depth_chart_order"]) for i in ridx),
            send_mkt1="|".join(f"{base_pool.at[i, 'value_1qb']:.0f}" for i in sidx), recv_mkt1="|".join(f"{base_pool.at[i, 'value_1qb']:.0f}" for i in ridx),
            send_pos="|".join(base_pool.at[i, "position"] for i in sidx), recv_pos="|".join(base_pool.at[i, "position"] for i in ridx),
            send_age=float(np.mean([base_pool.at[i, "age"] for i in sidx])) if sidx else np.nan,
            recv_age=float(np.mean([base_pool.at[i, "age"] for i in ridx])) if ridx else np.nan,
            send_inj="|".join(str(base_pool.at[i, "injury_status"]) for i in sidx), recv_inj="|".join(str(base_pool.at[i, "injury_status"]) for i in ridx),
            send_val=float(sum(a_["score"] for a_ in send_assets)), recv_val=float(sum(a_["score"] for a_ in recv_assets)),
            raw_value_delta=fit.get("raw_value_delta"), value_delta=fit.get("value_delta"), lineup_delta=fit.get("lineup_delta"),
            trade_score=verdict.trade_score, deal_size=verdict.deal_size, band=verdict.score_band, ui_verdict=verdict.ui_verdict,
            badge=verdict.band, confidence_pct=verdict.confidence_pct, fit_total=verdict.fit_total,
            consolidation=(fit.get("value_adjustments") or {}).get("consolidation"),
            starter_strength=(fit.get("value_adjustments") or {}).get("starter_strength"),
            mkt_send=mk(sidx, picks_s), mkt_recv=mk(ridx, picks_r),
            mkt1_send=float(sum(base_pool.at[i, "value_1qb"] for i in sidx)), mkt1_recv=float(sum(base_pool.at[i, "value_1qb"] for i in ridx)),
            naive_send=float(sum(np.nan_to_num(base_pool.at[i, "prior_ppg"]) for i in sidx)),
            naive_recv=float(sum(np.nan_to_num(base_pool.at[i, "prior_ppg"]) for i in ridx)),
            grade_ms=dt_ms,
        )
        if fit.get("lineup_model") and isinstance(fit["lineup_model"], dict):
            pts = fit["lineup_model"].get("points") or {}
            rec["model_ros_delta"] = pts.get("ros_delta")
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--nv", required=True)
    ap.add_argument("--dp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-league", type=int, default=120)
    ap.add_argument("--seasons", default="2021,2022,2023,2024,2025")
    ap.add_argument("--leagues", default=",".join(LEAGUES))
    ap.add_argument("--dates", default=",".join(DATES))
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    logf = open(out / "run.log", "a")

    def log(msg):
        print(msg, flush=True)
        logf.write(msg + "\n")
        logf.flush()

    h = History(Path(a.nv), Path(a.dp))
    rows = []
    for season in [int(s) for s in a.seasons.split(",")]:
        for mmdd in a.dates.split(","):
            for lname in a.leagues.split(","):
                rng = np.random.default_rng(zlib.crc32(f'{a.seed}|{season}|{mmdd}|{lname}'.encode()))
                t0 = time.time()
                r = run_league(h, season, mmdd, lname, LEAGUES[lname], a.per_league, rng, log)
                rows += r
                log(f"{season} {mmdd} {lname}: {len(r)} trades in {time.time()-t0:.0f}s")
                pd.DataFrame(rows).to_parquet(out / "graded.parquet")


if __name__ == "__main__":
    main()
