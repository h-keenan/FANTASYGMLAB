"""Injury audit on the committed real-history panel joined to nflverse weekly injury reports (read-only).

The panel (the sim calibration panel file (``calibration/data/panel.json.gz``), read as plain JSON) says only whether a player played each
week. nflverse ``injuries_<season>.csv`` (public; download into ``--inj-dir``, never committed, plus optional ids.csv from dynastyprocess/data db_playerids.csv for the sleeper_id -> gsis_id map) lists the weekly report
status (Out / Doubtful / Questionable) so a missed game can be classed as injury-listed or unexplained (bench, rest,
suspension, cut, or a long IR stay that left the weekly report). Joined through ``data/sleeper_players.json`` gsis_id.

    python scripts/sim_injury_audit.py --inj-dir DIR [--json OUT.json]

Imports nothing from the sim package and no real logic. Nothing is written under ``data/``.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "modules" / "sim" / "calibration" / "data" / "panel.json.gz"
SLEEPER = ROOT / "data" / "sleeper_players.json"
CORE = ("QB", "RB", "WR", "TE")


def age_bucket(a):
    return "?" if a is None else ("<24" if a < 24 else "24-26" if a < 27 else "27-29" if a < 30 else "30+")


def load(inj_dir: Path):
    rows = json.load(gzip.open(PANEL, "rt"))["rows"]
    sl = json.loads(SLEEPER.read_text())
    gsis = {str(pid): v.get("gsis_id") for pid, v in sl.items()}
    ids = inj_dir / "ids.csv"  # dynastyprocess db_playerids.csv: sleeper_id -> gsis_id for retired / unmatched players
    if ids.exists():
        for r in csv.DictReader(open(ids)):
            if r["sleeper_id"] and r["gsis_id"] and not gsis.get(r["sleeper_id"]):
                gsis[r["sleeper_id"]] = r["gsis_id"]
    rep = {}
    for p in sorted(inj_dir.glob("injuries_*.csv")) + sorted(inj_dir.glob("inj_*.csv")):
        for r in csv.DictReader(open(p)):
            if r["game_type"] == "REG" and r["gsis_id"]:
                rep[(int(r["season"]), r["gsis_id"], int(r["week"]))] = (r["report_status"], r["report_primary_injury"])
    return rows, gsis, rep


def episodes(row, gid, rep):
    """Runs of consecutive missed games (byes skipped). Each: length, injury-listed (any Out/Doubtful in the run)."""
    out, run = [], []
    for w, rec in enumerate(row["weeks"], 1):
        if rec is None:
            continue
        if rec[0] == 0:
            run.append(w)
        elif run:
            out.append(run)
            run = []
    if run:
        out.append(run)
    res = []
    for r in out:
        listed = [rep.get((row["season"], gid, w), ("", ""))[0] for w in r] if gid else []
        res.append(dict(start=r[0], length=len(r), injury=any(s in ("Out", "Doubtful") for s in listed), listed_weeks=sum(s in ("Out", "Doubtful") for s in listed)))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inj-dir", required=True)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    rows, gsis, rep = load(Path(args.inj_dir))
    core = [r for r in rows if r["pos"] in CORE and ((r["adp"] and r["adp"] <= 120) or r["proj_ppg"] >= 9)]
    out: dict = {}
    # 1. coverage and classification
    withid = [r for r in core if gsis.get(r["pid"])]
    out["core_player_seasons"] = len(core)
    out["with_gsis_id"] = len(withid)
    cls = defaultdict(int)
    eps_all = []
    for r in withid:
        for e in episodes(r, gsis[r["pid"]], rep):
            e.update(pos=r["pos"], age=r["age"], rookie=r["rookie"], season=r["season"], pid=r["pid"])
            eps_all.append(e)
            cls["missed_games"] += e["length"]
            cls["injury_listed_games"] += e["length"] if e["injury"] else 0
    out["missed_games"] = cls["missed_games"]
    out["missed_in_injury_listed_runs_share"] = round(cls["injury_listed_games"] / max(cls["missed_games"], 1), 3)
    out["episodes"] = len(eps_all)
    out["episodes_injury_listed_share"] = round(float(np.mean([e["injury"] for e in eps_all])), 3)
    out["unexplained_episode_length_mean"] = round(float(np.mean([e["length"] for e in eps_all if not e["injury"]])), 2)
    out["injury_episode_length_mean"] = round(float(np.mean([e["length"] for e in eps_all if e["injury"]])), 2)
    # 2. incidence and duration (injury-listed episodes), per available game
    avail = defaultdict(float)
    cnt = defaultdict(int)
    miss_inj = defaultdict(float)
    for r in withid:
        n = sum(1 for w in r["weeks"] if w is not None)
        for key in (("pos", r["pos"]), ("age", age_bucket(r["age"])), ("rookie", "rookie" if r["rookie"] else "vet"), ("all", "all")):
            avail[key] += n
    for e in eps_all:
        if e["injury"]:
            for key in (("pos", e["pos"]), ("age", age_bucket(e["age"])), ("rookie", "rookie" if e["rookie"] else "vet"), ("all", "all")):
                cnt[key] += 1
                miss_inj[key] += e["length"]
    out["incidence"] = {f"{k[0]}:{k[1]}": dict(episodes=cnt[k], per_100_games=round(100 * cnt[k] / avail[k], 2), games_missed_per_player_season=round(miss_inj[k] / (avail[k] / 16), 2)) for k in sorted(avail)}
    lens = np.array([e["length"] for e in eps_all if e["injury"]])
    out["injury_episode_pmf"] = {str(k): round(float((lens == k).mean()), 3) for k in range(1, 9)} | {"9+": round(float((lens >= 9).mean()), 3)}
    lens_u = np.array([e["length"] for e in eps_all if not e["injury"]])
    out["unexplained_episode_pmf"] = {str(k): round(float((lens_u == k).mean()), 3) for k in range(1, 9)} | {"9+": round(float((lens_u >= 9).mean()), 3)}
    # 3. persistence: prior-season injury-listed games missed vs this season's
    by = {(r["season"], r["pid"]): r for r in withid}
    def season_missed(r):
        es = episodes(r, gsis[r["pid"]], rep)
        return sum(e["length"] for e in es if e["injury"]), sum(e["length"] for e in es)
    pairs = []
    for (s, pid), r in by.items():
        p = by.get((s - 1, pid))
        if p:
            pi, pa = season_missed(p)
            ci, ca = season_missed(r)
            pairs.append(dict(season=s, prior_inj=pi, prior_all=pa, cur_inj=ci, cur_all=ca, pos=r["pos"], age=r["age"]))
    out["persistence_n"] = len(pairs)
    def bucket(v):
        return "0" if v == 0 else "1-2" if v <= 2 else "3-5" if v <= 5 else "6+"
    for tag, sel in (("2022-23 (fit)", lambda x: x["season"] in (2022, 2023)), ("2024-25 (held-out)", lambda x: x["season"] in (2024, 2025)), ("all", lambda x: True)):
        g = defaultdict(list)
        for x in pairs:
            if sel(x):
                g[bucket(x["prior_inj"])].append(x)
        out[f"persistence {tag}"] = {k: dict(n=len(v), cur_inj_missed=round(float(np.mean([x["cur_inj"] for x in v])), 2),
                                           p_ge3=round(float(np.mean([x["cur_inj"] >= 3 for x in v])), 3),
                                           cur_all_missed=round(float(np.mean([x["cur_all"] for x in v])), 2)) for k, v in sorted(g.items())}
    a = np.array([[x["prior_inj"], x["cur_inj"]] for x in pairs], float)
    out["corr_prior_cur_injury_games"] = round(float(np.corrcoef(a[:, 0], a[:, 1])[0, 1]), 3)
    a2 = np.array([[x["prior_all"], x["cur_all"]] for x in pairs], float)
    out["corr_prior_cur_all_missed"] = round(float(np.corrcoef(a2[:, 0], a2[:, 1])[0, 1]), 3)
    text = json.dumps(out, indent=1)
    if args.json:
        Path(args.json).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
