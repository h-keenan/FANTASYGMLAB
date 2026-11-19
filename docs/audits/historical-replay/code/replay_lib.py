"""Whole-system historical replay helpers (audit 2026-11-historical-replay).

Builds a synthetic point-in-time league from a real player pool, runs the REAL Trade Hub idea generator
(modules.trade_hub_engine.generate_trade_idea_records) for each team, and scores each idea against what happened.
Nothing here writes to data/ and rankings.load_players / build_players_table are never called.
"""
from __future__ import annotations

import os

import datetime as dt
import socket
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] if (Path(__file__).resolve().parents[1] / "modules").exists() else Path(os.environ.get("REPLAY_REPO", "."))
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
warnings.filterwarnings("ignore")


def _no_net(*a, **k):
    raise OSError("network blocked (historical replay is offline)")


socket.socket.connect = _no_net  # type: ignore[assignment]

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import trade_advice_backtest as B  # noqa: E402
import trade_advice_outcomes as O  # noqa: E402
from modules import (  # noqa: E402
    league_rankings, league_value_settings as lvs, partner_context, season_clock, team_eval, trade_hub_engine as H,
    trade_ideas, trade_lineup_model, usage_roles_targets, usage_trends,
)
from modules.player_eligibility import annotate_player_eligibility  # noqa: E402

LAST_FULL = 2025
LINEUP = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}
SIMS = 240
REG_WEEKS = 14


# ------------------------------------------------------------------ clock freezing (no wall-clock leakage)
class _FrozenDate(dt.date):
    _d = dt.date(2021, 1, 1)

    @classmethod
    def today(cls):  # type: ignore[override]
        return cls._d


class _FrozenDateTime(dt.datetime):
    _d = dt.datetime(2021, 1, 1)

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return cls._d

    @classmethod
    def utcnow(cls):  # type: ignore[override]
        return cls._d


def freeze(d: pd.Timestamp) -> None:
    day = d.date()
    season_clock._today_utc = lambda: day  # calendar_year / upcoming_draft_year / nfl_week all derive from this
    _FrozenDate._d = day
    _FrozenDateTime._d = dt.datetime(day.year, day.month, day.day)
    trade_lineup_model.date = _FrozenDate
    league_rankings.datetime = _FrozenDateTime
    from modules import trust_engine
    iso = day.isoformat()
    trust_engine._now_bucket = lambda now=None: (now.astimezone(dt.timezone.utc).date().isoformat() if now else iso)


# ------------------------------------------------------------------ synthetic platform adapter
class Adapter:
    def __init__(self, rosters, season, n_teams, status):
        self.r, self.season, self.n, self.status = rosters, season, n_teams, status

    def get_rosters(self, _):
        return self.r

    def get_users(self, _):
        return [{"user_id": r["owner_id"], "display_name": f"Team {r['roster_id']}",
                 "metadata": {"team_name": f"Team {r['roster_id']}"}} for r in self.r]

    def get_league(self, _):
        return {"season": str(self.season), "status": self.status,
                "settings": {"draft_rounds": 4, "num_teams": self.n}, "roster_positions": []}

    def get_traded_picks(self, _):
        return []

    def get_league_drafts(self, _):
        return []

    def normalize_roster(self, r):
        return r


def install_adapter(ad: Adapter) -> None:
    team_eval.get_sleeper_adapter = lambda *a, **k: ad
    trade_ideas.get_sleeper_adapter = lambda *a, **k: ad


# ------------------------------------------------------------------ weekly lineup scoring (hindsight, static roster)
class Env:
    def __init__(self, nv: str, dp: str):
        self.h = B.History(Path(nv), Path(dp))
        self.sc = O.Scorer(self.h)
        self._pw = {}

    def weekly(self, pid: str, season: int, tep: bool) -> np.ndarray:
        key = (pid, season, tep)
        if key not in self._pw:
            self._pw[key] = self.sc.weekly(pid, season, tep)
        return self._pw[key]

    def team_weeks(self, roster: list[str], season: int, sf: bool, tep: bool) -> np.ndarray:
        """Optimal-lineup points per week (index 1..18), empty slots at replacement PPG."""
        repl = self.h.repl_ppg(season, sf, tep)
        by = {p: [] for p in B.POS}
        for pid in roster:
            by[self.sc.pos(pid)].append(self.weekly(pid, season, tep))
        out = np.zeros(20)
        flex_rows = []
        for pos, n in LINEUP.items():
            n_eff = n + (1 if sf and pos == "QB" else 0)
            if by[pos]:
                m = np.vstack(by[pos])
                m = np.where(np.isnan(m), -999.0, m)
                m = -np.sort(-m, axis=0)
            else:
                m = np.full((0, 20), -999.0)
            if m.shape[0] < n_eff:
                m = np.vstack([m, np.full((n_eff - m.shape[0], 20), -999.0)])
            top = np.where(m[:n_eff] < -900, repl[pos], m[:n_eff])
            out += top.sum(axis=0)
            if pos in ("RB", "WR", "TE") and m.shape[0] > n_eff:
                flex_rows.append(m[n_eff:])
        if flex_rows:
            fl = np.vstack(flex_rows).max(axis=0)
            fl = np.where(fl < -900, min(repl["RB"], repl["WR"]), fl)
        else:
            fl = np.full(20, min(repl["RB"], repl["WR"]))
        return out + fl


# ------------------------------------------------------------------ league + sim
def schedule(n: int, rng: np.random.Generator) -> np.ndarray:
    """opp[sim, week, team] random weekly pairings (common random numbers across before/after)."""
    opp = np.zeros((SIMS, REG_WEEKS, n), dtype=np.int16)
    for s in range(SIMS):
        for w in range(REG_WEEKS):
            perm = rng.permutation(n)
            for k in range(0, n - 1, 2):
                a, b = perm[k], perm[k + 1]
                opp[s, w, a], opp[s, w, b] = b, a
            if n % 2:
                opp[s, w, perm[-1]] = perm[-1]
    return opp


def simulate(W: np.ndarray, opp: np.ndarray, n_playoff: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """W[team, week 1..18]. Returns (P(playoffs), P(title), mean wins) per team."""
    n = W.shape[0]
    wk = W[:, 1:REG_WEEKS + 1]  # team x 14
    wins = np.zeros((SIMS, n))
    for w in range(REG_WEEKS):
        o = opp[:, w, :]  # SIMS x n
        mine = wk[:, w][None, :]
        theirs = wk[:, w][o]
        wins += (mine > theirs) + 0.5 * (mine == theirs)
    pf = wk.sum(axis=1)
    key = wins * 1e6 + pf[None, :]
    order = np.argsort(-key, axis=1)  # SIMS x n
    seeds = order[:, :n_playoff]
    po = np.zeros(n)
    title = np.zeros(n)
    for s in range(SIMS):
        t = seeds[s]
        po[t] += 1
        if n_playoff == 6:
            w15, w16, w17 = W[:, 15], W[:, 16], W[:, 17]
            a = t[2] if w15[t[2]] >= w15[t[5]] else t[5]
            b = t[3] if w15[t[3]] >= w15[t[4]] else t[4]
            # reseed: seed 1 plays worst remaining, seed 2 the other
            rem = sorted([a, b], key=lambda x: list(t).index(x), reverse=True)
            s1 = t[0] if w16[t[0]] >= w16[rem[0]] else rem[0]
            s2 = t[1] if w16[t[1]] >= w16[rem[1]] else rem[1]
            champ = s1 if w17[s1] >= w17[s2] else s2
        else:
            w16, w17 = W[:, 16], W[:, 17]
            s1 = t[0] if w16[t[0]] >= w16[t[3]] else t[3]
            s2 = t[1] if w16[t[1]] >= w16[t[2]] else t[2]
            champ = s1 if w17[s1] >= w17[s2] else s2
        title[champ] += 1
    return po / SIMS, title / SIMS, wins.mean(axis=0)


def pick_rookie(env: Env, cls: int, rnd: int, slot: int, n_teams: int, sf: bool):
    r = env.sc.rookies(int(cls), sf)
    i = (int(rnd) - 1) * n_teams + int(slot) - 1
    return r[i] if 0 <= i < len(r) else None


# ------------------------------------------------------------------ roles map (nflverse usage -> usage_trends flags)
def build_role_map(env: Env, season: int, completed: int, ids_pos: list[tuple[str, str]]) -> dict[str, dict[str, str]]:
    if completed < 7:
        return {}
    s = env.h.spw
    s = s[(s.season == season) & (s.week <= completed)]
    by = {k: g for k, g in s.groupby("player_id")}
    out = {}
    for pid, pos in ids_pos:
        g = by.get(pid)
        if g is None or pos not in usage_trends.COVERED_POSITIONS:
            continue
        weeks = [dict(week=int(r.week), fantasy_points_ppr=float(r.fantasy_points_ppr), rush_attempts=float(r.carries),
                      targets=float(r.targets), receptions=float(r.receptions)) for r in g.itertuples()]
        adv = {"available": True, "through_week": completed, "as_of": None,
               "weeks": {int(r.week): dict(target_share=(None if pd.isna(r.target_share) else float(r.target_share)),
                                           air_yards_share=(None if pd.isna(r.air_yards_share) else float(r.air_yards_share)),
                                           opportunity_share=None, rz_targets=0, rz_carries=0) for r in g.itertuples()}}
        prof = usage_trends.build_usage_profile(pos, weeks, adv)
        for f in prof.get("flags") or ():
            if f.get("key") in usage_roles_targets.ROLE_KEYS and f.get("explanation"):
                out[pid] = {"key": f["key"], "explanation": str(f["explanation"])}
                break
    return out
