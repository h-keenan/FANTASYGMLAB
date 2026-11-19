"""Before/after harness for DYNASTYGM_INJURY_HORIZON_V1 (flag off vs on) on an existing player frame.

Never calls rankings.load_players / build_players_table. The frame is read read-only from a SQLite file (default: the committed
data/players.db, opened with mode=ro and copied into memory) or from a pickle of an already built frame.

    python scripts/audits/injury_horizon_diff.py [--db data/players.db | --frame FRAME.pkl] [--out OUT.md]

Prints, for every IR / Out / Doubtful player with a market value >= 1000: market rank, our dynasty and redraft-lens rank with the
flag off and on, and the median rank gap to the market for injured vs healthy players.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from modules import league_value_settings as lvs  # noqa: E402
from modules import rankings  # noqa: E402


def read_frame(args: argparse.Namespace) -> pd.DataFrame:
    if args.frame:
        return pd.read_pickle(args.frame)
    con = sqlite3.connect(f"file:{Path(args.db).resolve()}?mode=ro", uri=True)
    try:
        return pd.read_sql_query("select * from players", con)
    finally:
        con.close()


def lens_ranks(frame: pd.DataFrame, flag_on: bool, curves_on: bool | None = None, feed: bool = True) -> dict[str, pd.Series]:
    """curves_on None follows flag_on (the original off/on diff); a bool pins DYNASTYGM_INJURY_RETURN_CURVES_V1 independently."""
    os.environ[rankings.INJURY_HORIZON_ENV_KEY] = "1" if flag_on else "0"
    curves = flag_on if curves_on is None else curves_on
    os.environ[rankings.injury_return_curves.ENV_KEY] = "1" if curves else "0"
    os.environ[rankings.injury_return_curves.DYNASTY_FEED_ENV_KEY] = "1" if (curves and feed) else "0"
    work = rankings.compose_composite_score(rankings.apply_injury_risk_fields(frame.copy()))
    out = {}
    for name, lens, fmt in (("dynasty", "Dynasty", "Dynasty"), ("redraft", "Non-Dynasty", "Redraft")):
        settings = dict(lvs.DEFAULT_LEAGUE_VALUE_SETTINGS)
        settings["league_format"] = fmt
        scored = lvs.apply_valuation_lens(work.copy(), lens, settings)
        out[name] = scored[lvs.valuation_score_field(lens)].rank(ascending=False, method="first").astype(int)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "players.db"))
    ap.add_argument("--frame")
    ap.add_argument("--out")
    args = ap.parse_args()
    frame = read_frame(args)
    market = pd.to_numeric(frame["fantasycalc_value"], errors="coerce").fillna(0)
    mrank = market.where(market > 0).rank(ascending=False, method="first")
    injured = frame["injury_status"].fillna("").str.lower().isin(["ir", "out", "doubtful", "pup", "nfi"]) & (market >= 1000)
    healthy = frame["injury_status"].fillna("").eq("") & (market >= 1000)
    off, on = lens_ranks(frame, False), lens_ranks(frame, True)
    table = pd.DataFrame(
        {
            "name": frame["name"], "pos": frame["position"], "age": frame["age"], "inj": frame["injury_status"], "mkt": mrank,
            "dyn_off": off["dynasty"], "dyn_on": on["dynasty"], "red_off": off["redraft"], "red_on": on["redraft"],
        }
    )[injured].sort_values("mkt")
    lines = ["| player | pos | age | injury | market rank | dynasty rank off | dynasty rank on | redraft off | redraft on |", "|---|---|---|---|---|---|---|---|---|"]
    for _, r in table.iterrows():
        lines.append(f"| {r['name']} | {r['pos']} | {r['age']:.0f} | {r['inj']} | {r['mkt']:.0f} | {r['dyn_off']} | {r['dyn_on']} | {r['red_off']} | {r['red_on']} |")
    summary = [
        f"injured n={int(injured.sum())}, healthy comparison n={int(healthy.sum())}",
        f"median dynasty rank gap to market, injured: off {(off['dynasty'][injured] - mrank[injured]).median():+.0f}, on {(on['dynasty'][injured] - mrank[injured]).median():+.0f}",
        f"median dynasty rank gap to market, healthy: off {(off['dynasty'][healthy] - mrank[healthy]).median():+.0f}, on {(on['dynasty'][healthy] - mrank[healthy]).median():+.0f}",
        f"median redraft rank gap to market, injured: off {(off['redraft'][injured] - mrank[injured]).median():+.0f}, on {(on['redraft'][injured] - mrank[injured]).median():+.0f}",
        f"healthy players whose dynasty rank changed: {int((off['dynasty'][healthy] != on['dynasty'][healthy]).sum())} of {int(healthy.sum())} (rank shifts from the injured players moving, never from a changed multiplier)",
    ]
    combos = {
        "legacy (both off)": lens_ranks(frame, False, False),
        "return curves only": lens_ranks(frame, False, True),
        "horizon only": lens_ranks(frame, True, False),
        "horizon + curves (shipped defaults)": lens_ranks(frame, True, True, feed=False),
        "horizon + curves + dynasty feed": lens_ranks(frame, True, True, feed=True),
    }
    key = ["Puka Nacua", "Jeremiyah Love", "De'Von Achane"]
    keyed = ["", "market rank " + ", ".join(f"{n} {int(mrank[frame['name'] == n].iloc[0])}" for n in key), "",
             "| flags | " + " | ".join(f"{n} dyn / red" for n in key) + " |", "|---|" + "---|" * len(key)]
    for label, ranks in combos.items():
        cells = [f"{int(ranks['dynasty'][frame['name'] == n].iloc[0])} / {int(ranks['redraft'][frame['name'] == n].iloc[0])}" for n in key]
        keyed.append(f"| {label} | " + " | ".join(cells) + " |")
    text = "\n".join(summary + keyed + [""] + lines)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
