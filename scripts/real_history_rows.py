"""Extract real 2015-2025 player-seasons (weeks 1-17, PPR, QB/RB/WR/TE) from nflverse files into a small JSON for
the Sim calibration real-history report (which must stay pandas-free).

    python scripts/real_history_rows.py --nv /tmp/nv --out /tmp/real_rows.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

POS = ("QB", "RB", "WR", "TE")


def real_rows(nv: Path, first: int = 2015, last: int = 2025) -> list[dict[str, Any]]:
    import pandas as pd

    players = pd.read_csv(nv / "players.csv", usecols=["gsis_id", "birth_date"], low_memory=False)
    born = {g: pd.to_datetime(b, errors="coerce") for g, b in zip(players.gsis_id, players.birth_date)}
    out = []
    for season in range(first, last + 1):
        d = pd.read_parquet(nv / f"spw_{season}.parquet")
        d = d[(d.season_type == "REG") & (d.week <= 17) & d.position.isin(POS)]
        for pid, g in d.groupby("player_id"):
            pos = g.position.iloc[0]
            games = int(len(g))
            b = born.get(pid)
            age = (pd.Timestamp(season, 9, 1) - b).days / 365.25 if b is not None and pd.notna(b) else None
            team = g.sort_values("week").team.iloc[-1]
            out.append({"run": "real", "season": season, "pid": pid, "pos": pos, "ppg": float(g.fantasy_points_ppr.mean()), "g": games,
                        "age": age, "team": team})
    return out



def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nv", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.write_text(json.dumps(real_rows(a.nv)))


if __name__ == "__main__":
    main()
