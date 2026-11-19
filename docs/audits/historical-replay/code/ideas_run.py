"""Run the real Trade Hub idea generator on point-in-time synthetic leagues and score every idea.

python ideas_run.py --out DIR --variant base --seasons 2021,2022 [--dates 08-20,10-20,12-01] [--formats ...] [--sizes 12]
"""
from __future__ import annotations

import os

import argparse
import time
import zlib
from pathlib import Path

import replay_lib as R
import pit
from modules import playoff_context, team_profile
from replay_lib import annotate_player_eligibility
from replay_lib import (B, H, O, Env, np, pd, lvs, partner_context, trade_ideas, usage_roles_targets)

DATA = os.environ["REPLAY_DATA"]
FORMS = ["dynasty_1qb", "dynasty_sf", "dynasty_sf_tep"]


def apply_variant(name: str) -> None:
    """Patch module constants for a tuning variant (``base`` = shipped defaults, untouched)."""
    if name == "base":
        return
    kind, _, val = name.partition(":")
    if kind == "ceiling":
        trade_ideas.PARTNER_EDGE_HARD_CEILING = float(val)
    elif kind == "budget":
        x = float(val)
        partner_context.COMBINED_MAX_POINTS = x
        partner_context.CAP_PER_POINT = (partner_context.CAP_SHIFT_MAX / x) if x > 0 else 0.0
    elif kind == "age_w":
        partner_context.AGE_MAX_POINTS = 3.0 * float(val)
    elif kind == "pick_w":
        partner_context.PICK_MAX_POINTS = 3.0 * float(val)
    elif kind == "roles":
        if val == "off":
            usage_roles_targets.enabled = lambda: False
        else:
            usage_roles_targets.TARGET_POINTS = 1.5 * float(val)
            usage_roles_targets.SEND_POINTS = 1.5 * float(val)
            usage_roles_targets.MAX_POINTS = 2.0 * float(val)
    elif kind == "handshakes":
        if val == "off":
            partner_context.enabled = lambda: False
    else:
        raise SystemExit(f"unknown variant {name}")


def pick_market(env, label, year, rnd, slot, sf, frame, n=12):
    try:
        picks = env.h.dp_picks(label)
    except FileNotFoundError:
        return np.nan
    ordn = {1: "1st", 2: "2nd", 3: "3rd"}.get(int(rnd), f"{int(rnd)}th")
    third = "Early" if slot <= n / 3 else "Late" if slot > 2 * n / 3 else "Mid"
    pk = picks[picks.player == f"{year} Pick {int(rnd)}.{int(slot):02d}"]
    if pk.empty:
        pk = picks[picks.player == f"{year} {third} {ordn}"]
    if pk.empty:
        pk = picks[picks.player == f"{year} {ordn}"]
    if pk.empty:
        return np.nan
    col = "ecr_2qb" if sf else "ecr_1qb"
    mcol = "value_2qb" if sf else "value_1qb"
    cv = frame.dropna(subset=[col, mcol]).sort_values(col)
    return float(np.interp(float(pk[col].iloc[0]), cv[col].to_numpy(), cv[mcol].to_numpy()))


def run_league(env: Env, season, mmdd, lname, n, seed, max_ideas, log):
    label = f"{season}-{mmdd}"
    d = pd.Timestamp(label)
    R.freeze(d)
    league = B.LEAGUES[lname]
    sf, tep = bool(league["sf"]), bool(league["tep"])
    completed = env.h.completed_weeks(season, d)
    in_season = 0 < completed < 17
    cw = completed + 1 if in_season else 0
    lvs.DEFAULT_LEAGUE_VALUE_SETTINGS = dict(lvs.DEFAULT_LEAGUE_VALUE_SETTINGS, league_size=n, season=season)
    frame, settings = B.build_frame(env.h, label, season, d, completed, league, cw)
    frame = B.fit_weekly_baselines(frame).reset_index(drop=True)
    frame["player_id"] = frame.player_id.astype(str)
    now_ = pd.Timestamp(label, tz="UTC")
    frame["full_name"] = frame["name"]
    frame["fantasy_positions"] = frame.position.map(lambda p: [p])
    frame["sport"] = "nfl"
    frame["active"] = True
    frame["status"] = "active"
    frame["stats_season"] = season - 1 if completed == 0 else season
    frame["latest_stats_season"] = frame["stats_season"]
    frame["news_updated"] = now_.timestamp()
    frame["news_updated_at"] = now_.isoformat()
    frame["metadata_updated_at"] = now_.isoformat()
    frame["verified_signals"] = [{} for _ in range(len(frame))]
    frame = annotate_player_eligibility(frame, now=now_.to_pydatetime())
    settings = dict(settings, season=season, league_size=n, current_week=cw,
                    starter_count=10 if sf else 9, qb_count=1, rb_count=2, wr_count=3, te_count=1, flex_count=1,
                    superflex_count=1 if sf else 0, k_count=0, def_count=0, max_roster_size=24)
    rng = np.random.default_rng(zlib.crc32(f"{seed}|{season}|{mmdd}|{lname}|{n}".encode()))
    teams = B.draft_league(frame, rng, sf, n)
    rosters_ids = [[frame.at[j, "player_id"] for j in t] for t in teams]
    sched = R.schedule(n, np.random.default_rng(zlib.crc32(f"sched|{seed}|{season}|{n}".encode())))
    nplayed = min(completed, R.REG_WEEKS)
    if nplayed:
        sched[:, :nplayed, :] = sched[0:1, :nplayed, :]  # played weeks have one fixed schedule (the record the engine sees)
    Wb = np.zeros((n, 20))
    for i, r in enumerate(rosters_ids):
        Wb[i] = env.team_weeks(r, season, sf, tep)
    n_po = 6 if n >= 12 else 4
    # record to date from the same schedule (only weeks already played), sim 0
    wins0 = np.zeros(n)
    for w in range(min(completed, R.REG_WEEKS)):
        o = sched[0, w]
        wins0 += (Wb[:, w + 1] > Wb[o, w + 1]) + 0.5 * (Wb[:, w + 1] == Wb[o, w + 1])
    rosters = [{"roster_id": i + 1, "owner_id": f"O{i + 1}", "players": r,
                "settings": {"wins": int(wins0[i]), "losses": int(min(completed, R.REG_WEEKS) - wins0[i]), "ties": 0}}
               for i, r in enumerate(rosters_ids)]
    status = "pre_draft" if mmdd in ("04-15",) else "in_season"
    ad = R.Adapter(rosters, season, n, status)
    R.install_adapter(ad)
    score_field = lvs.valuation_score_field(league["lens"])
    summary = R.team_eval.build_league_summary(frame, "L", score_field=score_field, current_score_field="value_score",
                                               lineup_settings=dict(settings), adapter=ad)
    if summary.empty:
        log(f"empty summary {label} {lname} {n}")
        return [], []
    strat = {int(r.roster_id): r.strategy for r in summary.itertuples()}
    power = summary.assign(_s=summary.total_score).sort_values("_s", ascending=False).roster_id.astype(int).tolist()
    po_b, ti_b, wins_b = R.simulate(Wb, sched, n_po)
    proj = frame.set_index("player_id").proj_ppg.to_dict()
    mu = np.array([pit.lineup_mean(r, proj, env.sc.pos, sf) for r in rosters_ids])
    po_pit, ti_pit, wn_pit = pit.simulate_pit(Wb, mu, sched, completed, n_po, np.random.default_rng(5))
    cores = []
    for r in rosters_ids:
        blk = team_profile.build_age_block(frame[frame.player_id.isin(r)], score_field)
        cores.append(blk.get("core_avg"))
    lg_core = np.nanmean([c for c in cores if c is not None])
    leans = []
    for i in range(n):
        dlt = (cores[i] - lg_core) if cores[i] is not None else None
        leans.append(playoff_context.lean({"playoff_probability": po_pit[i] * 100.0}, posture_key=strat[i + 1], core_age_delta=dlt))
    all_ids = [p for r in rosters_ids for p in r]
    roles = R.build_role_map(env, season, completed, [(p, env.sc.pos(p)) for p in all_ids]) if in_season else {}
    mcol = "value_2qb" if sf else "value_1qb"
    mval = frame.set_index("player_id")[mcol].to_dict()
    snaps = {1: env.sc.snap(f"{season + 1}-{mmdd}"), 2: env.sc.snap(f"{season + 2}-{mmdd}")}
    out, team_rows = [], []
    for a in range(1, n + 1):
        t0 = time.perf_counter()
        try:
            recs = H.generate_trade_idea_records(
                league_id="L", my_roster_id=a, players_df=frame, rosters=rosters, league_settings=settings,
                score_field=score_field, team_strategy=strat[a], max_ideas=max_ideas, df_summary=summary,
                usage_roles=roles or None)
        except Exception as exc:  # noqa: BLE001
            log(f"ERR {label} {lname} {n} team {a}: {type(exc).__name__}: {exc}")
            recs = []
        hold = None
        try:
            cards = [H.project_trade_idea_card(r_, is_headline=(k_ == 0)).to_dict() for k_, r_ in enumerate(recs)]
            hold = H.build_hold_verdict(cards, strategy=strat[a], power_rank=power.index(a) + 1, team_count=n,
                                        season_progress=completed / 18.0, in_season=in_season, trade_window=None)
        except Exception as exc:  # noqa: BLE001
            log(f"hold err {exc}")
        team_rows.append(dict(po_pit=po_pit[a - 1], title_pit=ti_pit[a - 1], lean=leans[a - 1]["lean"], lean_points=leans[a - 1]["points"],
                              hold=bool(hold), hold_reason=(hold or {}).get("reason", ""), season=season, mmdd=mmdd, league=lname, n_teams=n, team=a, posture=strat[a], n_ideas=len(recs),
                              power_rank=power.index(a) + 1, po_before=po_b[a - 1], title_before=ti_b[a - 1],
                              wins_exp=wins_b[a - 1], ms=(time.perf_counter() - t0) * 1000, completed=completed))
        for k, rec in enumerate(recs):
            b = int(str(rec.get("partner_team_name", "Team 0")).split()[-1])
            sp = [x for x in rec["send_assets"] if x.get("asset_type") == "player"]
            rp = [x for x in rec["receive_assets"] if x.get("asset_type") == "player"]
            sk = [x for x in rec["send_assets"] if x.get("asset_type") == "pick"]
            rk = [x for x in rec["receive_assets"] if x.get("asset_type") == "pick"]
            sids, rids = [x["player_id"] for x in sp], [x["player_id"] for x in rp]

            def rookies(picks):
                out_ = []
                for x in picks:
                    rid = R.pick_rookie(env, x.get("season") or 0, x.get("round") or 1, x.get("projected_slot_number") or (n + 1) // 2, n, sf)
                    out_.append((int(x.get("season") or 0), rid))
                return out_

            rs, rr = rookies(sk), rookies(rk)

            def window_pts(roster_before, roster_after, extra_before, extra_after, Y, w0, w1):
                if Y > R.LAST_FULL:
                    return np.nan
                eb = [p for c, p in extra_before if p and c <= Y]
                ea = [p for c, p in extra_after if p and c <= Y]
                wb = env.team_weeks(roster_before + eb, Y, sf, tep)
                wa = env.team_weeks(roster_after + ea, Y, sf, tep)
                return float((wa[w0:w1 + 1] - wb[w0:w1 + 1]).sum())

            ub, pb = rosters_ids[a - 1], rosters_ids[b - 1]
            ua = [p for p in ub if p not in set(sids)] + rids
            pa = [p for p in pb if p not in set(rids)] + sids
            row = {k_: v for k_, v in rec.items() if isinstance(v, (str, int, float, bool, type(None)))}
            try:
                row["impact_tag"] = H._classify_impact_tag(rec, str(rec.get("trade_confidence_label") or ""))
            except Exception:  # noqa: BLE001
                row["impact_tag"] = ""
            row.update(season=season, mmdd=mmdd, date=label, league=lname, n_teams=n, team=a, partner=b, posture=strat[a],
                       partner_posture=strat[b], idea_rank=k, completed=completed, in_season=in_season, power_rank=power.index(a) + 1,
                       send_names="; ".join(x["label"] for x in rec["send_assets"]), recv_names="; ".join(x["label"] for x in rec["receive_assets"]),
                       n_send=len(rec["send_assets"]), n_recv=len(rec["receive_assets"]),
                       send_pos="|".join(x["position"] for x in sp), recv_pos="|".join(x["position"] for x in rp),
                       send_age=float(np.nanmean([x.get("age") or np.nan for x in sp])) if sp else np.nan,
                       recv_age=float(np.nanmean([x.get("age") or np.nan for x in rp])) if rp else np.nan,
                       send_pick_n=len(sk), recv_pick_n=len(rk), send_ids="|".join(sids), recv_ids="|".join(rids),
                       send_pick_score=sum(x.get("score", 0) for x in sk), recv_pick_score=sum(x.get("score", 0) for x in rk),
                       send_score=sum(x.get("score", 0) for x in rec["send_assets"]), recv_score=sum(x.get("score", 0) for x in rec["receive_assets"]),
                       pick_unresolved=int(any(p is None for _, p in rs + rr)))
            for nm, Y, w0, w1 in (("ros", season, completed + 1, 18), ("y1", season + 1, 1, 18), ("y2", season + 2, 1, 18)):
                row[f"u_{nm}"] = window_pts(ub, ua, rs, rr, Y, w0, w1)
                row[f"p_{nm}"] = window_pts(pb, pa, rr, rs, Y, w0, w1)
            # playoff odds / title (static rosters; only weeks after the trade change)
            W = Wb.copy()
            wa_u = env.team_weeks(ua + [p for c, p in rr if p and c <= season], season, sf, tep)
            wa_p = env.team_weeks(pa + [p for c, p in rs if p and c <= season], season, sf, tep)
            W[a - 1, completed + 1:] = wa_u[completed + 1:]
            W[b - 1, completed + 1:] = wa_p[completed + 1:]
            po_a, ti_a, wn_a = R.simulate(W, sched, n_po)
            row.update(u_dpo=po_a[a - 1] - po_b[a - 1], u_dti=ti_a[a - 1] - ti_b[a - 1], u_dwins=wn_a[a - 1] - wins_b[a - 1],
                       p_dpo=po_a[b - 1] - po_b[b - 1], u_lean=leans[a - 1]["lean"], u_po_pit=po_pit[a - 1], p_dti=ti_a[b - 1] - ti_b[b - 1], u_po_before=po_b[a - 1])
            # market value change (players; picks via rookie at the later snapshot)
            for yy in (1, 2):
                sn = snaps[yy]
                if sn is None:
                    row[f"u_val{yy}"] = np.nan
                    row[f"u_valchg{yy}"] = np.nan
                    continue
                if (len(sk) + len(rk)) and any(c > season + yy for c, _ in rs + rr):
                    row[f"u_val{yy}"] = np.nan
                    row[f"u_valchg{yy}"] = np.nan
                    continue
                if any(p is None for _, p in rs + rr):
                    row[f"u_val{yy}"] = np.nan
                    row[f"u_valchg{yy}"] = np.nan
                    continue
                end = lambda ids: float(sum(sn[mcol].get(p, 0.0) for p in ids))  # noqa: E731
                e_r = end(rids + [p for _, p in rr])
                e_s = end(sids + [p for _, p in rs])
                s_r = sum(mval.get(p, 0.0) for p in rids) + sum(pick_market(env, label, c, x.get("round") or 1, x.get("projected_slot_number") or (n + 1) // 2, sf, frame, n)
                                                                 for x, (c, _) in zip(rk, rr))
                s_s = sum(mval.get(p, 0.0) for p in sids) + sum(pick_market(env, label, c, x.get("round") or 1, x.get("projected_slot_number") or (n + 1) // 2, sf, frame, n)
                                                                 for x, (c, _) in zip(sk, rs))
                row[f"u_val{yy}"] = e_r - e_s
                row[f"u_valchg{yy}"] = (e_r - e_s) - (s_r - s_s)
            row["mkt_delta_start"] = (sum(mval.get(p, 0.0) for p in rids) - sum(mval.get(p, 0.0) for p in sids))
            out.append(row)
    return out, team_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--variant", default="base")
    ap.add_argument("--seasons", default="2021,2022,2023,2024,2025")
    ap.add_argument("--dates", default="08-20,10-20,12-01")
    ap.add_argument("--formats", default=",".join(FORMS))
    ap.add_argument("--sizes", default="12")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--max-ideas", type=int, default=8)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    apply_variant(a.variant)
    logf = open(out / f"run_{a.variant.replace(':', '_')}_{a.seasons.replace(',', '')}.log", "a")

    def log(m):
        logf.write(m + "\n")
        logf.flush()

    env = Env(DATA + "/nv", DATA + "/dp")
    ideas, teams = [], []
    tag = f"{a.variant.replace(':', '_')}_{a.seasons.replace(',', '')}"
    for season in [int(s) for s in a.seasons.split(",")]:
        for mmdd in a.dates.split(","):
            for lname in a.formats.split(","):
                for n in [int(x) for x in a.sizes.split(",")]:
                    t0 = time.time()
                    i, t = run_league(env, season, mmdd, lname, n, a.seed, a.max_ideas, log)
                    ideas += i
                    teams += t
                    log(f"{season} {mmdd} {lname} n={n}: {len(i)} ideas {time.time() - t0:.0f}s")
                    df_ = pd.DataFrame(ideas)
                    for c_ in df_.columns[df_.dtypes == object]:
                        df_[c_] = df_[c_].map(lambda v: v if v is None or isinstance(v, str) else str(v)) if df_[c_].map(lambda v: isinstance(v, str) or v is None).any() else pd.to_numeric(df_[c_], errors="coerce")
                    df_.to_parquet(out / f"ideas_{tag}.parquet")
                    pd.DataFrame(teams).to_parquet(out / f"teams_{tag}.parquet")


if __name__ == "__main__":
    main()
