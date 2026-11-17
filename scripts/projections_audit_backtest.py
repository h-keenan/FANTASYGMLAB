"""Point-in-time backtest of the REAL ``modules.player_projections`` pipeline on nflverse history.

Audit of 2026-11 (``docs/audits/2026-11-projections-backtest.md``). For every
(season, week) it rebuilds exactly what ``project_player_week`` would have
returned *before* kickoff, using only data published before that week:

* the player's own weekly rows from earlier weeks (and the prior season, as in
  production's prior-season seeding) - weeks >= the target week are never passed in;
* the nflverse Friday injury report for that week (the ``availability`` layer);
* a usage-derived depth order (production reads Sleeper's depth chart, which has
  no point-in-time history; the derivation is a documented proxy);
* the nflverse schedule (byes, opponent, lines).

Everything is scored against nflverse actual PPR. Nothing is written to ``data/``,
no database is touched (``rankings.load_players`` is never called). Data is read
from ``--nv`` (a throwaway cache of nflverse release files), see ``fetch``.

    python scripts/projections_audit_backtest.py fetch  --nv /tmp/nv
    python scripts/projections_audit_backtest.py build  --nv /tmp/nv --out /tmp/pa
    python scripts/projections_audit_backtest.py ros    --nv /tmp/nv --out /tmp/pa
    python scripts/projections_audit_backtest.py sleeper --nv /tmp/nv --sl /tmp/sl --out /tmp/pa

``build`` writes ``rows.parquet`` (one row per projected player-week with model
output, baselines, actuals and scenario flags). ``ros`` writes rest-of-season
totals. ``sleeper`` re-runs the usage baseline fed by Sleeper's weekly stats (the
production input) for the independence comparison.
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import nfl_schedule  # noqa: E402
from modules import player_projections as pp  # noqa: E402

POS = ("QB", "RB", "WR", "TE", "K")
_BASE = "https://github.com/nflverse/nflverse-data/releases/download/"
HALF = {"rec": 0.5, "rec_yd": 0.1, "rec_td": 6.0, "rush_yd": 0.1, "rush_td": 6.0, "pass_yd": 0.04, "pass_td": 4.0,
        "pass_int": -1.0, "fum_lost": -2.0}
# TE-premium (+0.5/rec for TE) on PPR, with 6-point passing TDs (the usual superflex-league setup).
TEP6 = {**HALF, "rec": 1.0, "bonus_rec_te": 0.5, "pass_td": 6.0}


def fetch(nv: Path, first: int = 2015, last: int = 2026) -> None:
    nv.mkdir(parents=True, exist_ok=True)
    jobs = [("https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv", "games.csv"),
            (_BASE + "players/players.csv", "players.csv")]
    for s in range(first, last + 1):
        jobs += [(_BASE + f"stats_player/stats_player_week_{s}.parquet", f"spw_{s}.parquet"),
                 (_BASE + f"injuries/injuries_{s}.csv", f"inj_{s}.csv"),
                 (_BASE + f"weekly_rosters/roster_weekly_{s}.csv", f"rw_{s}.csv")]
    for url, name in jobs:
        path = nv / name
        if path.exists() and path.stat().st_size > 100:
            continue
        for _ in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "FantasyDesk-audit/1.0"})
                path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
                break
            except Exception:
                time.sleep(2)


# ------------------------------------------------------------------ data
def load_spw(nv: Path, seasons) -> pd.DataFrame:
    frames = []
    for s in seasons:
        d = pd.read_parquet(nv / f"spw_{s}.parquet")
        d = d[(d.season_type == "REG") & d.position.isin(POS)].copy()
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d["fum_lost"] = d[["sack_fumbles_lost", "rushing_fumbles_lost", "receiving_fumbles_lost"]].fillna(0).sum(axis=1)
    # nflverse leaves kicker fantasy points at 0. Sleeper's default kicker scoring (recovered by least squares on
    # its 2024 K rows, exact to 0.98 pt): FG 3 (<40), 4 (40-49), 5 (50+), XP 1, missed FG -1, missed XP -1.
    k = d.position == "K"
    f = lambda c: d[c].fillna(0)  # noqa: E731
    kpts = (3 * (f("fg_made_0_19") + f("fg_made_20_29") + f("fg_made_30_39")) + 4 * f("fg_made_40_49")
            + 5 * (f("fg_made_50_59") + f("fg_made_60_")) + f("pat_made") - f("fg_missed") - f("pat_missed"))
    d.loc[k, "fantasy_points_ppr"] = kpts[k]
    d["fantasy_points_ppr"] = d["fantasy_points_ppr"].fillna(0.0)
    return d


def sleeper_like_row(r) -> dict:
    return {
        "week": int(r.week), "games_played": 1.0, "targets": float(r.targets or 0), "receptions": float(r.receptions or 0),
        "rush_attempts": float(r.carries or 0), "pass_attempts": float(r.attempts or 0),
        "fantasy_points_ppr": float(r.fantasy_points_ppr), "receiving_yards": float(r.receiving_yards or 0),
        "receiving_tds": float(r.receiving_tds or 0), "rushing_yards": float(r.rushing_yards or 0),
        "rushing_tds": float(r.rushing_tds or 0), "passing_yards": float(r.passing_yards or 0),
        "passing_tds": float(r.passing_tds or 0), "passing_interceptions": float(r.passing_interceptions or 0),
        "passing_completions": float(r.completions or 0), "fumbles_lost": float(r.fum_lost or 0),
    }


class LazyWeekly(dict):
    """``weekly_stats`` for the handcuff estimator: starter rows truncated to weeks < W."""

    def __init__(self, rows_by_pid, week):
        super().__init__()
        self._rows, self._week = rows_by_pid, week

    def get(self, key, default=None):
        rows = self._rows.get(str(key))
        if rows is None:
            return default
        return {"weekly": [r for r in rows if r["week"] < self._week]}


def scoring_points(row, pos: str, scoring: dict) -> float:
    """Actual points of a nflverse row (namedtuple) under a Sleeper-style scoring dict."""
    pts = float(row.fantasy_points_ppr)
    if pos not in ("QB", "RB", "WR", "TE"):
        return pts
    rec = float(row.receptions or 0)
    pts += (scoring.get("rec", 1.0) - 1.0) * rec
    pts += (scoring.get("pass_td", 4.0) - 4.0) * float(row.passing_tds or 0)
    if pos == "TE":
        pts += scoring.get("bonus_rec_te", 0.0) * rec
    return pts


def build_context(nv: Path, season: int):
    seasons = [season - 1, season]
    spw = load_spw(nv, seasons)
    games = pd.read_csv(nv / "games.csv", low_memory=False)
    nfl_schedule.load_games = lambda refresh=False: games  # type: ignore[assignment]
    nfl_schedule.clear_load_games_cache()
    return spw, games


def team_game_table(games: pd.DataFrame, season: int) -> pd.DataFrame:
    g = games[(games.season == season) & (games.game_type == "REG")]
    home = pd.DataFrame({"week": g.week, "team": g.home_team, "opp": g.away_team, "home": 1, "rest": g.home_rest,
                         "spread": g.spread_line, "total": g.total_line, "qb": g.home_qb_id, "weekday": g.weekday,
                         "roof": g.roof, "temp": g.temp, "wind": g.wind, "score": g.home_score,
                         "opp_score": g.away_score})
    away = pd.DataFrame({"week": g.week, "team": g.away_team, "opp": g.home_team, "home": 0, "rest": g.away_rest,
                         "spread": -g.spread_line, "total": g.total_line, "qb": g.away_qb_id, "weekday": g.weekday,
                         "roof": g.roof, "temp": g.temp, "wind": g.wind, "score": g.away_score,
                         "opp_score": g.home_score})
    out = pd.concat([home, away], ignore_index=True)
    out["implied"] = (out.total - out.spread) / 2.0
    return out


def _ros_rows(season, V, games, week_players, cur_rows, prev_rows, tg_idx, full, weekly_stats):
    """Rest-of-season totals as the weekly projection loop in production would produce them at week V.

    Production builds a rest-of-season view by calling ``project_player_week`` for every remaining week
    (``GET /v1/players/{id}/schedule``). Here the schedule's ``played`` flags are those of week V (scores of
    weeks >= V are hidden), so the availability layer sees future games as future games, exactly as in production.
    Totals cover weeks V..17 (fantasy regular season); actuals are the real PPR points of the same weeks.
    """
    g2 = games.copy()
    mask = (g2.season == season) & (g2.week >= V)
    g2.loc[mask, ["home_score", "away_score"]] = np.nan
    saved = nfl_schedule.load_games
    nfl_schedule.load_games = lambda refresh=False, _g=g2: _g  # type: ignore[assignment]
    nfl_schedule.clear_load_games_cache()
    out = []
    try:
        for pid, pl in week_players.items():
            team = pl["team"]
            rem = [w for w in range(V, 18) if (team, w) in tg_idx]
            if not rem:
                continue
            rows_before = [x for x in cur_rows.get(pid, []) if x["week"] < V]
            total, n_ok = 0.0, 0
            lows = highs = 0.0
            for w in rem:
                res = pp.project_player_week(pid, w, season, players=week_players, player_weekly_rows=rows_before,
                                             prior_weekly_rows=prev_rows.get(pid), defense_strength={}, team_qb_quality={},
                                             weekly_stats=weekly_stats, team_qb_pass_attempts_by_team={}, stats_through_week=V - 1)
                if res.get("status") == "ok":
                    total += res["point_estimate"]
                    n_ok += 1
            if n_ok == 0:
                continue
            hist_all = [x["fantasy_points_ppr"] for x in prev_rows.get(pid, [])] + [x["fantasy_points_ppr"] for x in rows_before]
            cur_pts = [x["fantasy_points_ppr"] for x in rows_before]
            act = [float(full[(pid, season, w)].fantasy_points_ppr) for w in rem if (pid, season, w) in full]
            out.append({"season": season, "vantage": V, "pid": pid, "pos": pl["position"], "team": team, "rem_games": len(rem),
                        "ros_est": total, "ros_actual": sum(act), "games_played": len(act),
                        "b_last3": float(np.mean(hist_all[-3:])) * len(rem) if hist_all else np.nan,
                        "b_std": (float(np.mean(cur_pts)) if cur_pts else (float(np.mean([x["fantasy_points_ppr"] for x in prev_rows.get(pid, [])])) if prev_rows.get(pid) else np.nan)) * len(rem),
                        "ppg_est": total / max(1, n_ok), "inj": pl["injury_status"], "status": pl["status"]})
    finally:
        nfl_schedule.load_games = saved  # type: ignore[assignment]
        nfl_schedule.clear_load_games_cache()
    return out


def run_season(nv: Path, season: int, last_week: int, scorings: bool = True, ros_weeks=(), ros_sink=None) -> pd.DataFrame:
    spw, games = build_context(nv, season)
    tg = team_game_table(games, season)
    tg_idx = {(r.team, int(r.week)): r for r in tg.itertuples()}
    rw = pd.read_csv(nv / f"rw_{season}.csv", low_memory=False)
    rw = rw[rw.game_type == "REG"] if "game_type" in rw else rw
    rw_prev = pd.read_csv(nv / f"rw_{season - 1}.csv", low_memory=False)
    inj = pd.read_csv(nv / f"inj_{season}.csv", low_memory=False)
    inj = inj[inj.game_type == "REG"] if "game_type" in inj else inj
    inj_status = {(r.gsis_id, int(r.week)): r.report_status for r in inj.itertuples() if isinstance(r.report_status, str)}
    rw_status = {(r.gsis_id, int(r.week)): (r.status, r.team, r.status_description_abbr) for r in rw.itertuples()}
    rw_info = rw.drop_duplicates("gsis_id").set_index("gsis_id")[["birth_date", "rookie_year", "entry_year", "years_exp", "draft_number", "sleeper_id", "full_name"]]
    for df in (rw_prev,):
        extra = df.drop_duplicates("gsis_id").set_index("gsis_id")[["birth_date", "rookie_year", "entry_year", "years_exp", "draft_number", "sleeper_id", "full_name"]]
        rw_info = pd.concat([rw_info, extra[~extra.index.isin(rw_info.index)]])

    # per-player sorted rows across seasons (prior season weeks shifted at call time via prior_weekly_rows)
    cur_rows, prev_rows, meta = defaultdict(list), defaultdict(list), {}
    full = {}
    for r in spw.sort_values(["season", "week"]).itertuples():
        row = sleeper_like_row(r)
        row["pos"] = r.position
        row["team"] = r.team
        row["_raw"] = (r.receptions, r.passing_tds)
        (cur_rows if r.season == season else prev_rows)[r.player_id].append(row)
        meta[r.player_id] = (r.position, r.team)
        full[(r.player_id, r.season, int(r.week))] = r
    cur_weeks = {pid: [x["week"] for x in rows] for pid, rows in cur_rows.items()}

    # team-position trailing usage for derived depth order (weeks < W)
    out = []
    played_set = {(pid, int(w)) for pid, rows in cur_rows.items() for w in cur_weeks[pid]}
    all_pids = set(cur_rows) | set(prev_rows)
    # who plays at each (team, week) at each position: to detect starters absent
    for W in range(1, last_week + 1):
        # roster candidates
        cands = {}
        for pid in all_pids:
            pos, tm = meta[pid]
            cands[pid] = (pos, tm)
        week_players = {}
        usage = defaultdict(list)  # (team,pos) -> [(score, pid)]
        for pid, (pos, tm) in cands.items():
            rows = [x for x in cur_rows.get(pid, []) if x["week"] < W]
            hist = rows[-3:] if rows else prev_rows.get(pid, [])[-3:]
            if not hist:
                continue
            st = rw_status.get((pid, W))
            team_now = (st[1] if st and isinstance(st[1], str) else None) or (rows[-1]["team"] if rows else hist[-1]["team"])
            if pos == "QB":
                u = np.mean([h["pass_attempts"] for h in hist])
            elif pos == "RB":
                u = np.mean([h["rush_attempts"] + h["targets"] for h in hist])
            elif pos in ("WR", "TE"):
                u = np.mean([h["targets"] for h in hist])
            else:
                u = 1.0
            usage[(team_now, pos)].append((u, pid))
        depth = {}
        for key, lst in usage.items():
            lst.sort(reverse=True)
            if key[1] == "QB":
                # A depth chart's QB1 is the announced starter: use the QB who starts that game (games.csv).
                tgq = tg_idx.get((key[0], W))
                starter = getattr(tgq, "qb", None)
                lst.sort(key=lambda item: (item[1] != starter, -item[0]))
            for i, (_u, pid) in enumerate(lst):
                depth[pid] = i + 1
        for pid, (pos, tm) in cands.items():
            rows = [x for x in cur_rows.get(pid, []) if x["week"] < W]
            hist_exists = bool(rows) or bool(prev_rows.get(pid))
            if not hist_exists:
                continue
            st = rw_status.get((pid, W))
            if (pid, W) not in played_set and not (st and st[0] in ("ACT", "RES", "INA")):
                continue  # not on an NFL active/reserve roster that week and did not play
            team_now = (st[1] if st and isinstance(st[1], str) else None) or (rows[-1]["team"] if rows else prev_rows[pid][-1]["team"])
            status_txt = "Active"
            if st and st[0] == "RES":
                status_txt = "Injured Reserve"
            elif st and st[0] in ("CUT", "RET", "EXE", "TRC"):
                status_txt = "Inactive"
            iss = inj_status.get((pid, W))
            week_players[pid] = {
                "position": pos, "team": team_now, "status": status_txt, "injury_status": iss or "",
                "depth_chart_order": depth.get(pid), "rw_abbr": st[2] if st else None, "full_name": str(rw_info.full_name.get(pid, pid)) if pid in rw_info.index else pid,
                "active": True,
            }
        weekly_stats = LazyWeekly(cur_rows, W)
        if W in ros_weeks and ros_sink is not None:
            ros_sink.extend(_ros_rows(season, W, games, week_players, cur_rows, prev_rows, tg_idx, full, weekly_stats))
        for pid, pl in week_players.items():
            team_now = pl["team"]
            tgrow = tg_idx.get((team_now, W))
            if tgrow is None:
                continue  # bye or unknown team: no game to project
            played = (pid, W) in played_set
            rows_before = [x for x in cur_rows.get(pid, []) if x["week"] < W]
            res = pp.project_player_week(
                pid, W, season, players=week_players,
                player_weekly_rows=rows_before, prior_weekly_rows=prev_rows.get(pid), defense_strength={},
                team_qb_quality={}, weekly_stats=weekly_stats, team_qb_pass_attempts_by_team={}, stats_through_week=W - 1,
            )
            status = res.get("status")
            rec = {"season": season, "week": W, "pid": pid, "pos": pl["position"], "team": team_now, "status": status,
                   "played": played, "depth": pl["depth_chart_order"], "rw_abbr": pl.get("rw_abbr"), "inj": pl["injury_status"], "rost_status": pl["status"]}
            if played:
                arow = full[(pid, season, W)]
                rec["actual"] = float(arow.fantasy_points_ppr)
                rec["actual_half"] = scoring_points(arow, pl["position"], HALF)
                rec["actual_tep6"] = scoring_points(arow, pl["position"], TEP6)
                rec["receptions"] = float(arow.receptions or 0)
            else:
                rec["actual"] = rec["actual_half"] = rec["actual_tep6"] = 0.0
                rec["receptions"] = 0.0
            # baselines: last-3 played games (current season, topped up from prior), season-to-date avg
            hist_all = [x["fantasy_points_ppr"] for x in prev_rows.get(pid, [])] + [x["fantasy_points_ppr"] for x in rows_before]
            cur_pts = [x["fantasy_points_ppr"] for x in rows_before]
            rec["b_last3"] = float(np.mean(hist_all[-3:])) if hist_all else np.nan
            rec["b_std"] = float(np.mean(cur_pts)) if cur_pts else (float(np.mean([x["fantasy_points_ppr"] for x in prev_rows.get(pid, [])])) if prev_rows.get(pid) else np.nan)
            rec["n_cur"] = len(cur_pts)
            rec["n_prev"] = len(prev_rows.get(pid, []))
            if status == "ok":
                b = res["basis"]
                rec.update(est=res["point_estimate"], low=res["low"], high=res["high"], conf=res["confidence"],
                           avail=b["availability"]["reason"], avail_mult=b["availability"]["multiplier"],
                           role=b["role"]["reason"], prior_seeded=b["prior_season_seeded"], games_used=b["season_games_played"],
                           usage_implied=b["usage_implied_ppr"], questionable_applied=b["questionable_plays"]["applied"],
                           eff_adj=b["efficiency_adjustment_ppr"], recent_avg=b["recent_weighted_avg_ppr"],
                           role_mult=b["role"]["multiplier"], plays_mult=b["questionable_plays"]["multiplier"],
                           handcuff_inherit=b["role"].get("inherited_ppr"))
                if scorings and pl["position"] in ("QB", "RB", "WR", "TE"):
                    for tag, sc in (("half", HALF), ("tep6", TEP6)):
                        r2 = pp.project_player_week(
                            pid, W, season, players=week_players, player_weekly_rows=rows_before,
                            prior_weekly_rows=prev_rows.get(pid), defense_strength={}, team_qb_quality={},
                            weekly_stats=weekly_stats, team_qb_pass_attempts_by_team={}, scoring_settings=sc, stats_through_week=W - 1)
                        rec[f"est_{tag}"], rec[f"low_{tag}"], rec[f"high_{tag}"] = r2["point_estimate"], r2["low"], r2["high"]
            # context flags
            rec.update(implied=tgrow.implied, spread=tgrow.spread, rest=tgrow.rest, weekday=tgrow.weekday, roof=tgrow.roof,
                       temp=tgrow.temp, wind=tgrow.wind, game_qb=tgrow.qb, opp=tgrow.opp)
            prevg = tg_idx.get((team_now, W - 1))
            rec["qb_prev"] = prevg.qb if prevg is not None else None
            rec["last_played_week"] = max([x["week"] for x in rows_before], default=0)
            # team games since he last played this season
            last_pw = rec["last_played_week"]
            rec["gap"] = sum(1 for w in range(last_pw + 1, W) if (team_now, w) in tg_idx) if last_pw else None
            # Participation: of the team's last 4 completed games this season (byes excluded), how many did he miss?
            # Needs only the schedule and his own played weeks, both available to production.
            window = [w for w in range(W - 1, 0, -1) if (team_now, w) in tg_idx][:4]
            pw = set(cur_weeks.get(pid, ()))
            rec["games4"] = len(window)
            rec["missed4"] = sum(1 for w in window if w not in pw)
            rec["missed_season"] = sum(1 for w in range(1, W) if (team_now, w) in tg_idx and w not in pw)
            rec["team_games_season"] = sum(1 for w in range(1, W) if (team_now, w) in tg_idx)
            rec["team_last"] = rows_before[-1]["team"] if rows_before else (prev_rows[pid][-1]["team"] if prev_rows.get(pid) else None)
            info = rw_info.loc[pid] if pid in rw_info.index else None
            if info is not None:
                bd = pd.to_datetime(info.birth_date, errors="coerce")
                rec["age"] = (pd.Timestamp(season, 9, 1) - bd).days / 365.25 if pd.notna(bd) else np.nan
                rec["rookie_year"] = info.rookie_year
                rec["years_exp"] = info.years_exp
                rec["draft_number"] = info.draft_number
                rec["sleeper_id"] = info.sleeper_id
            out.append(rec)
    # Players who played with no usable history (rookies, first-time NFL players): the pipeline returns
    # ``insufficient_player_data`` / unknown for them, so they get no projection at all. Record them so the
    # coverage gap and the actual scoring of that population are measurable.
    projected = {(r["pid"], r["week"]) for r in out}
    for r in spw[spw.season == season].itertuples():
        if r.week > last_week or (r.player_id, int(r.week)) in projected:
            continue
        info = rw_info.loc[r.player_id] if r.player_id in rw_info.index else None
        tg = tg_idx.get((r.team, int(r.week)))
        bd = pd.to_datetime(info.birth_date, errors="coerce") if info is not None else pd.NaT
        out.append({"season": season, "week": int(r.week), "pid": r.player_id, "pos": r.position, "team": r.team,
                    "status": "no_history", "played": True, "actual": float(r.fantasy_points_ppr),
                    "actual_half": scoring_points(r, r.position, HALF), "actual_tep6": scoring_points(r, r.position, TEP6),
                    "receptions": float(r.receptions or 0), "n_cur": 0, "n_prev": 0,
                    "age": (pd.Timestamp(season, 9, 1) - bd).days / 365.25 if pd.notna(bd) else np.nan,
                    "rookie_year": info.rookie_year if info is not None else np.nan,
                    "draft_number": info.draft_number if info is not None else np.nan,
                    "implied": tg.implied if tg is not None else np.nan})
    return pd.DataFrame(out)


def run_sleeper_vs_nflverse(nv: Path, sl: Path, season: int, last_week: int) -> pd.DataFrame:
    """Independence check: the same estimator fed by Sleeper's weekly stats (the production input) and by nflverse.

    Everything except the weekly stat rows is identical (same schedule, no availability / role layers, same
    candidates: nflverse player-weeks with a stat line, week >= 2, player present in both feeds). Both are scored
    against nflverse actual PPR.
    """
    import json

    spw, games = build_context(nv, season)
    rw = pd.concat([pd.read_csv(nv / f"rw_{y}.csv", low_memory=False, usecols=["gsis_id", "sleeper_id"]) for y in (season - 1, season)])
    g2s = {g: str(int(s)) for g, s in zip(rw.gsis_id, rw.sleeper_id) if pd.notna(g) and pd.notna(s)}

    def sleeper_rows(y: int):
        feed = defaultdict(list)
        for w in range(1, 19):
            f = sl / f"stats_{y}_{w}.json"
            if not f.exists():
                continue
            for r in json.loads(f.read_text()):
                st = r.get("stats") or {}
                pos = str((r.get("player") or {}).get("position") or "").upper()
                if pos not in POS or not float(st.get("gp") or 0) > 0:
                    continue
                feed[str(r["player_id"])].append({"week": w, "games_played": 1.0, "targets": st.get("rec_tgt", 0.0), "receptions": st.get("rec", 0.0),
                                                  "rush_attempts": st.get("rush_att", 0.0), "pass_attempts": st.get("pass_att", 0.0),
                                                  "fantasy_points_ppr": float(st.get("pts_ppr") or 0.0), "team": r.get("team")})
        return feed

    sl_cur, sl_prev = sleeper_rows(season), sleeper_rows(season - 1)
    nv_cur, nv_prev = defaultdict(list), defaultdict(list)
    for r in spw.sort_values(["season", "week"]).itertuples():
        (nv_cur if r.season == season else nv_prev)[r.player_id].append(sleeper_like_row(r))
    out = []
    played = spw[(spw.season == season) & (spw.week >= 2) & (spw.week <= last_week)]
    for r in played.itertuples():
        sid = g2s.get(r.player_id)
        if sid is None or sid not in sl_cur:
            continue
        W = int(r.week)
        pl = {r.player_id: {"position": r.position, "team": r.team, "status": "Active", "injury_status": "", "depth_chart_order": None, "full_name": "x"}}
        rec = {"season": season, "week": W, "pid": r.player_id, "pos": r.position, "actual": float(r.fantasy_points_ppr)}
        for tag, cur, prev, key in (("nv", nv_cur, nv_prev, r.player_id), ("sl", sl_cur, sl_prev, sid)):
            before = [x for x in cur.get(key, []) if x["week"] < W]
            res = pp.project_player_week(r.player_id, W, season, players=pl, player_weekly_rows=before, prior_weekly_rows=prev.get(key),
                                         defense_strength={}, team_qb_quality={}, weekly_stats={}, team_qb_pass_attempts_by_team={})
            rec[tag] = res.get("point_estimate") if res.get("status") == "ok" else np.nan
            rec[tag + "_low"] = res.get("low") if res.get("status") == "ok" else np.nan
            rec[tag + "_high"] = res.get("high") if res.get("status") == "ok" else np.nan
        out.append(rec)
    return pd.DataFrame(out)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("fetch", "build", "ros", "sleeper"))
    ap.add_argument("--nv", type=Path, required=True)
    ap.add_argument("--sl", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--seasons", type=int, nargs="*", default=[2023, 2024, 2025, 2026])
    a = ap.parse_args(argv)
    if a.command == "fetch":
        fetch(a.nv)
        return 0
    a.out.mkdir(parents=True, exist_ok=True)
    if a.command == "sleeper":
        frames = []
        for s in [x for x in a.seasons if x >= 2022]:
            sp = pd.read_parquet(a.nv / f"spw_{s}.parquet")
            last = int(sp[sp.season_type == "REG"].week.max())
            frames.append(run_sleeper_vs_nflverse(a.nv, a.sl, s, min(last, 18)))
            print(s, len(frames[-1]), flush=True)
        pd.concat(frames, ignore_index=True).to_parquet(a.out / "sleeper_cmp.parquet")
        return 0
    if a.command == "ros":
        sink = []
        for s in a.seasons:
            sp = pd.read_parquet(a.nv / f"spw_{s}.parquet")
            last = int(sp[sp.season_type == "REG"].week.max())
            vs = tuple(v for v in (1, 5, 9, 13) if v <= min(last, 17) - 0)
            t0 = time.time()
            n0 = len(sink)
            run_season(a.nv, s, min(vs[-1], last), scorings=False, ros_weeks=vs, ros_sink=sink)
            print(s, len(sink) - n0, f"{time.time() - t0:.0f}s", flush=True)
        pd.DataFrame(sink).to_parquet(a.out / "ros.parquet")
        return 0
    if a.command == "build":
        frames = []
        for s in a.seasons:
            sp = pd.read_parquet(a.nv / f"spw_{s}.parquet")
            last = int(sp[sp.season_type == "REG"].week.max())
            t0 = time.time()
            df = run_season(a.nv, s, min(last, 18))
            print(s, len(df), f"{time.time() - t0:.0f}s", flush=True)
            frames.append(df)
        pd.concat(frames, ignore_index=True).to_parquet(a.out / "rows.parquet")
        return 0
    raise SystemExit("not implemented here")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
