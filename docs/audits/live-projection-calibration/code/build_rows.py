import sys, time
from pathlib import Path
sys.path.insert(0, "scripts"); sys.path.insert(0, ".")
import pandas as pd
import projections_audit_backtest as B
nv = Path("calibration_scratch/nv"); frames = []
for s in (2023, 2024, 2025):
    sp = pd.read_parquet(nv / f"spw_{s}.parquet")
    last = int(sp[sp.season_type == "REG"].week.max())
    t0 = time.time()
    df = B.run_season(nv, s, min(last, 18), scorings=False)
    print(s, len(df), f"{time.time()-t0:.0f}s", flush=True)
    frames.append(df)
pd.concat(frames, ignore_index=True).to_parquet("calibration_scratch/rows.parquet")
