"""Walk-forward backtest for ``modules.news_value_events`` (docs/news-value-events-2026-10.md).

Sleeper keeps no point-in-time injury history, but its weekly stats rows carry the
player's *team that week* and games played. That gives two structured events that can
be reconstructed without guessing from headlines:

- ``availability_out`` (proxy for Sleeper Out/IR/PUP/Suspended): an established player
  (>=4 prior games, trailing PPG >= 6, played his previous team game) has no game in a
  week his team played. The proxy is NOT split by cause (injury vs suspension) because
  the cause is not in the data.
- ``team_change`` (proxy for a confirmed trade/signing): his team code that week
  differs from the team of his previous game, and he played.

Prediction target: PPR points over the next four team games. Baseline = trailing PPG
(last 8 games this season) x team games in window, i.e. a value that has not heard the
news. Adjusted = baseline x ratio fitted ONLY on earlier seasons (walk-forward).
Clean window for availability_out is the four team games AFTER the missed one, so the
known-out week does not trivially favour the adjustment.

Nothing here touches data/players.db. Usage::

    python scripts/news_value_events_backtest.py fetch CACHE_DIR
    python scripts/news_value_events_backtest.py run CACHE_DIR
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

POS = ("QB", "RB", "WR", "TE", "K")
_Q = "&".join(f"position[]={p}" for p in POS)
MIN_PRIOR_GAMES = 4
MIN_PPG = 6.0
TRAIL = 8
WINDOW = 4
FIRST_WEEK, LAST_WEEK = 5, 17


def _get(url: str, path: Path) -> None:
    if path.exists() and path.stat().st_size > 100:
        return
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FantasyDesk-nve/1.0"})
            path.write_bytes(urllib.request.urlopen(req, timeout=90).read())
            return
        except Exception:
            time.sleep(2)
    path.write_bytes(b"[]")


def fetch(cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    jobs = [
        (f"https://api.sleeper.com/stats/nfl/{s}/{w}?season_type=regular&{_Q}", cache / f"stats_{s}_{w}.json")
        for s in range(2021, 2026)
        for w in range(1, 19)
    ]
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda a: _get(*a), jobs))


def load(cache: Path) -> pd.DataFrame:
    rows = []
    for p in sorted(cache.glob("stats_*_*.json")):
        _, s, w = p.stem.split("_")
        for r in json.loads(p.read_text()):
            st = r.get("stats") or {}
            pos = str((r.get("player") or {}).get("position") or "").upper()
            if pos not in POS or not r.get("team") or not float(st.get("gp") or 0) > 0:
                continue
            rows.append(dict(season=int(s), week=int(w), pid=r["player_id"], pos=pos, team=r["team"],
                             pts=float(st.get("pts_ppr") or 0.0)))
    return pd.DataFrame(rows)


def build_samples(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (event-or-control, player-week) with baseline and realised window points."""
    out = []
    for season, sdf in df.groupby("season"):
        team_weeks = defaultdict(set)
        for t, w in zip(sdf.team, sdf.week):
            team_weeks[t].add(w)
        for pid, g in sdf.groupby("pid"):
            g = g.sort_values("week")
            weeks = g.week.tolist()
            pts = dict(zip(g.week, g.pts))
            team_of = dict(zip(g.week, g.team))
            pos = g.pos.iloc[0]
            for t in range(FIRST_WEEK, LAST_WEEK + 1):
                prior = [w for w in weeks if w < t]
                if len(prior) < MIN_PRIOR_GAMES:
                    continue
                last_team = team_of[prior[-1]]
                ppg = float(np.mean([pts[w] for w in prior[-TRAIL:]]))
                if ppg < MIN_PPG:
                    continue
                played_t = t in pts
                # previous team game: player must have played it (established, not already out)
                prev_games = [w for w in sorted(team_weeks[last_team]) if w < t]
                if not prev_games or prev_games[-1] != prior[-1]:
                    continue
                if played_t:
                    team_t = team_of[t]
                    kind = "team_change" if team_t != last_team else "control"
                    cur_team = team_t
                    win_start = t if kind == "team_change" else t + 1
                else:
                    if t not in team_weeks[last_team]:
                        continue  # bye
                    kind, cur_team, win_start = "availability_out", last_team, t + 1
                win = [w for w in sorted(team_weeks[cur_team]) if win_start <= w < win_start + 8][:WINDOW]
                if len(win) < WINDOW or win[-1] > 18:
                    continue
                y_by_game = [pts.get(w, 0.0) for w in win]
                out.append(dict(season=season, week=t, pid=pid, pos=pos, kind=kind, ppg=ppg,
                                base=ppg * WINDOW, y=sum(y_by_game),
                                **{f"y{k+1}": y_by_game[k] for k in range(WINDOW)}))
    return pd.DataFrame(out)


def spearman(a, b) -> float:
    return float(pd.Series(a).rank().corr(pd.Series(b).rank()))


def run(cache: Path) -> None:
    df = load(cache)
    s = build_samples(df)
    print(f"player-weeks with outcomes: {len(s)}")
    print(s.groupby(["season", "kind"]).size().unstack(fill_value=0).to_string())
    seasons = sorted(s.season.unique())
    rows = []
    decay = []
    for kind in ("availability_out", "team_change"):
        for test in seasons[2:]:  # fit on >=2 earlier seasons
            tr = s[(s.season < test) & (s.kind == kind)]
            te = s[(s.season == test) & (s.kind == kind)]
            ctl = s[(s.season == test) & (s.kind == "control")]
            ratio = tr.y.sum() / tr.base.sum()
            # static = what production already does for this status (rankings.injury_multiplier:
            # Out -> "moderate" 0.80). The event layer must beat this, not the raw baseline.
            static = 0.80 if kind == "availability_out" else 1.0
            te = te.assign(adj=te.base * ratio, stat=te.base * static)
            ctl = ctl.assign(adj=ctl.base, stat=ctl.base)
            pool = pd.concat([te, ctl])
            # bootstrap CI on MAE improvement
            d = (te.stat - te.y).abs().values - (te.adj - te.y).abs().values  # gain vs production's static multiplier
            rng = np.random.default_rng(0)
            bs = [rng.choice(d, len(d)).mean() for _ in range(2000)]
            rows.append(dict(kind=kind, test=test, n=len(te), ratio=round(ratio, 3),
                             mae_base=(te.base - te.y).abs().mean(), mae_static=(te.stat - te.y).abs().mean(), mae_adj=(te.adj - te.y).abs().mean(),
                             mae_gain_lo=np.percentile(bs, 2.5), mae_gain_hi=np.percentile(bs, 97.5),
                             rho_base=spearman(pool.base, pool.y), rho_static=spearman(pool.stat, pool.y), rho_adj=spearman(pool.adj, pool.y),
                             bias_base=(te.base - te.y).mean(), bias_adj=(te.adj - te.y).mean(),
                             ctl_ratio=ctl.y.sum() / ctl.base.sum()))
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(res.round(3).to_string(index=False))
    for kind in ("availability_out", "team_change"):
        g = s[s.kind == kind]
        dec = {k + 1: round(g[f"y{k+1}"].sum() / (g.ppg.sum()), 3) for k in range(WINDOW)}
        decay.append((kind, len(g), dec))
        # by position
    print("\nrealised/expected points by game index after event (all seasons):")
    c = s[s.kind == "control"]
    print("control", len(c), {k + 1: round(c[f"y{k+1}"].sum() / c.ppg.sum(), 3) for k in range(WINDOW)})
    for kind, n, dec in decay:
        print(kind, n, dec)
    print("\nby position (all seasons), realised/baseline:")
    for kind in ("availability_out", "team_change", "control"):
        g = s[s.kind == kind]
        print(kind, {p: (len(x), round(x.y.sum() / x.base.sum(), 3)) for p, x in g.groupby("pos")})
    print("\nshare of availability_out samples with zero points in all 4 following games:",
          round(float((s[s.kind == "availability_out"].y == 0).mean()), 3))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("fetch", "run"):
        raise SystemExit(__doc__)
    (fetch if sys.argv[1] == "fetch" else run)(Path(sys.argv[2]))
