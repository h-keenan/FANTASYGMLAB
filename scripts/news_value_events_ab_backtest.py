"""A/B backtest of DYNASTYGM_NEWS_VALUE_EVENTS (on vs off) on official nflverse injury reports.
Usage: python -I nve_ab.py DATA_DIR
Events: official final-designation 'Out' (point-in-time), established players.
Layer under test: production formula incremental=min(1,(1-red)/inj_mult_age), red=0.19*0.5**(age/28).
"""
import sys, re, unicodedata
from pathlib import Path
import numpy as np, pandas as pd
D = Path(sys.argv[1]); NV = D/"nv"; DP = D/"dp"
rng = np.random.default_rng(0)
AGE_PTS = ((24.0,.88),(28.0,.80),(32.0,.70))
def inj_mult(age):
    return float(np.interp(age,[a for a,_ in AGE_PTS],[m for _,m in AGE_PTS])) if np.isfinite(age) else .80
def layer(age, days):
    red = 0.19*0.5**(max(days,0)/28.0) if days<=28 else 0.0
    return min(1.0,(1-red)/inj_mult(age)) if red>0 else 1.0
def norm(s):
    s=unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().lower()
    s=re.sub(r"\b(jr|sr|ii|iii|iv|v)\b","",s); return re.sub(r"[^a-z]","",s)
pl = pd.read_csv(NV/"players.csv",usecols=["gsis_id","display_name","position","birth_date"])
pl["key"]=pl.display_name.map(norm)+"|"+pl.position
pl=pl.drop_duplicates("key",keep=False)
games = pd.read_csv(NV/"games.csv",usecols=["season","week","gameday","game_type","home_team","away_team"]); games=games[games.game_type=="REG"]
wk_day = games.groupby(["season","week"]).gameday.min().map(pd.Timestamp)
wk_day_max = games.groupby(["season","week"]).gameday.max().map(pd.Timestamp)
inj = pd.concat([pd.read_csv(f) for f in sorted(NV.glob("inj_20*.csv"))]); inj=inj[(inj.game_type=="REG")&inj.report_status.eq("Out")]
outs = {(r.season,r.week,r.gsis_id) for r in inj.itertuples()}
spw = pd.concat([pd.read_parquet(f,columns=["player_id","season","week","season_type","team","position","fantasy_points_ppr"]) for f in sorted(NV.glob("spw_20*.parquet"))])
spw=spw[(spw.season_type=="REG")&spw.position.isin(["QB","RB","WR","TE"])].rename(columns={"player_id":"gsis_id"})
birth = pl.set_index("gsis_id").birth_date.to_dict()
def age_at(g,day):
    b=birth.get(g)
    return (day-pd.Timestamp(b)).days/365.25 if isinstance(b,str) else np.nan
tw = {}
for r in games.itertuples():
    for t in (r.home_team,r.away_team): tw.setdefault((r.season,t),set()).add(r.week)
rows=[]
for (s,g),df in spw.groupby(["season","gsis_id"]):
    df=df.sort_values("week"); pts=dict(zip(df.week,df.fantasy_points_ppr)); team=dict(zip(df.week,df.team))
    for t in range(5,18):
        prior=[w for w in pts if w<t]
        if len(prior)<4: continue
        ppg=np.mean([pts[w] for w in prior[-8:]])
        if ppg<6: continue
        lt=team[prior[-1]]; weeks=sorted(tw.get((s,lt),[]))
        if t not in weeks: continue
        if t in pts: kind="control" if (s,t,g) not in outs else "out_played"
        else: kind="out" if (s,t,g) in outs else "other_missed"
        if kind not in("control","out"): continue
        win=[w for w in weeks if w>t][:4]
        if len(win)<4: continue
        y=sum(pts.get(w,0.0) for w in win)
        rows.append(dict(season=s,week=t,gsis=g,kind=kind,base=ppg*4,y=y,age=age_at(g,wk_day[(s,t)])))
A=pd.DataFrame(rows)
def boot(d,n=4000):
    d=np.asarray(d); b=[rng.choice(d,len(d)).mean() for _ in range(n)]; return d.mean(),np.percentile(b,2.5),np.percentile(b,97.5)
print("== Test A: next-4-game PPR points; official Out and did not play that week ==")
print(A.groupby(["season","kind"]).size().unstack(fill_value=0).to_string())
out=A[A.kind=="out"].copy(); ctl=A[A.kind=="control"].copy()
def adj_on(a): return np.mean([layer(a,7*k) for k in (1,2,3,4)])
out["off"]=out.base*out.age.map(inj_mult); out["on"]=[r.base*inj_mult(r.age)*adj_on(r.age) for r in out.itertuples()]
out["rawbase"]=out.base
for test in ("2021-22",2023,2024,2025,"2023-25"):
    te=out[out.season.isin([2023,2024,2025])] if test=="2023-25" else (out[out.season.isin([2021,2022])] if test=="2021-22" else out[out.season==test])
    e_off=(te.off-te.y).abs(); e_on=(te.on-te.y).abs()
    m,lo,hi=boot(e_off.values-e_on.values)
    pool_c=ctl[ctl.season.isin(te.season.unique())].assign(off=lambda x:x.base,on=lambda x:x.base)
    pool=pd.concat([te,pool_c]); rho=lambda c:float(pool[c].rank().corr(pool.y.rank()))
    print(f"test {test}: n={len(te)} MAE off={e_off.mean():.2f} on={e_on.mean():.2f} gain(on better>0)={m:+.2f} [{lo:+.2f},{hi:+.2f}] Spearman off={rho('off'):.3f} on={rho('on'):.3f} bias off={(te.off-te.y).mean():+.2f} on={(te.on-te.y).mean():+.2f} realised/base={te.y.sum()/te.base.sum():.3f} off-factor={te.off.sum()/te.base.sum():.3f} on-factor={te.on.sum()/te.base.sum():.3f}")
dps=[]
for f in sorted(DP.glob("*_values-players.csv")):
    d=pd.read_csv(f,usecols=["player","pos","age","value_1qb"]); d["snap"]=pd.Timestamp(f.name[:10]); d["key"]=d.player.map(norm)+"|"+d.pos; dps.append(d)
dp=pd.concat(dps); dp=dp[dp.pos.isin(["QB","RB","WR","TE"])]
snaps=sorted(dp.snap.unique())
dpi=dp.drop_duplicates(["snap","key"],keep=False).set_index(["snap","key"]).value_1qb
key2g=pl.set_index("key").gsis_id
rowsB=[]
for s0,s1 in zip(snaps[:-1],snaps[1:]):
    if s0.month not in(8,10): continue
    season=s0.year
    ws=[w for (s,w),d in wk_day.items() if s==season and d<=s0]
    if not ws: continue
    wlast=max(ws); days_since=(s0-wk_day_max[(season,wlast)]).days
    for r in dp[dp.snap==s0].itertuples():
        if r.value_1qb<1500 or r.key not in key2g.index or (s1,r.key) not in dpi.index: continue
        g=key2g[r.key]
        rowsB.append(dict(snap=s0,season=season,key=r.key,age=r.age,v0=r.value_1qb,v1=dpi[(s1,r.key)],event=(season,wlast,g) in outs,days=max(days_since,0)))
B=pd.DataFrame(rowsB); B["lr"]=np.log(B.v1/B.v0)
print("\n== Test B: DynastyProcess value (1QB) next snapshot (~6-7 wks), Out in latest pre-snapshot report ==")
print(B.groupby(["season","event"]).size().unstack(fill_value=0).to_string())
B["f"]=[layer(r.age,r.days) if r.event else 1.0 for r in B.itertuples()]
for test in ("2021-22",2023,2024,2025,"2023-25"):
    te=B[B.season.isin([2023,2024,2025])] if test=="2023-25" else (B[B.season.isin([2021,2022])] if test=="2021-22" else B[B.season==test])
    ev=te[te.event]
    if len(ev)==0: continue
    ctl_lr=te[~te.event].lr.mean()
    off=(np.log(ev.v0)-np.log(ev.v1)).abs(); on=(np.log(ev.v0*ev.f)-np.log(ev.v1)).abs()
    m,lo,hi=boot(off.values-on.values)
    ex,elo,ehi=boot(ev.lr.values-ctl_lr)
    print(f"test {test}: events={len(ev)} mean logchg event={ev.lr.mean():+.3f} control={ctl_lr:+.3f} excess={ex:+.3f} [{elo:+.3f},{ehi:+.3f}] MAE(log) off={off.mean():.3f} on={on.mean():.3f} gain={m:+.4f} [{lo:+.4f},{hi:+.4f}] mean layer factor={ev.f.mean():.3f}")
tr=B[B.season<=2022]; print("train(2021-22) market excess for event players: %.3f"%(tr[tr.event].lr.mean()-tr[~tr.event].lr.mean()))
