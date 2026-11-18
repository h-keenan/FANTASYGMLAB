"""Before/after for trade-advice audit P1-1 (starting-demand role/opportunity) and
P1-2 (no-market floor): flags off vs on over a SYNTHETIC 12-team pool.

    .venv313/bin/python scripts/audits/trade_p1_anchor_diff.py [OUT.md]

Prints, per league format, the engine score of QB1 / QB12 / QB19 / QB30 and of a
no-market depth piece, with both flags off and on, plus a 1-for-2 package sum.
Never touches data/players.db.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules import league_value_settings as lvs  # noqa: E402
from modules import valuation_anchors as va  # noqa: E402

FORMATS = {
    "1QB": {"league_size": 12, "qb_count": 1, "superflex_count": 0, "rb_count": 2, "wr_count": 2, "te_count": 1, "regular_flex_count": 1},
    "Superflex": {"league_size": 12, "qb_count": 1, "superflex_count": 1, "rb_count": 2, "wr_count": 2, "te_count": 1, "regular_flex_count": 1},
}


def pool() -> pd.DataFrame:
    rows = []
    for i in range(30):
        market = 9000 - i * 250
        rows.append({"player_id": f"QB{i + 1}", "position": "QB", "age": 27, "market_score": market, "team": "KC", "status": "Active", "search_rank": 10 + i, "role_score": 8500,
                     "opportunity_score": 8800, "production_score": 5000, "scarcity_score": 0, "risk_multiplier": 1.0,
                     "score": int(0.44 * market + 0.06 * 8500 + 0.10 * 8800 + 0.12 * 5000 + 0.28 * market)})
    for i in range(3):
        rows.append({"player_id": f"Depth{i + 1}", "position": "WR", "age": 25, "market_score": 0, "team": "KC", "status": "Active", "search_rank": 900, "role_score": 3800,
                     "opportunity_score": 2800, "production_score": 2200, "scarcity_score": 0, "risk_multiplier": 1.0,
                     "score": 900})
    df = pd.DataFrame(rows)
    df["dynasty_score"] = df["score"]
    df["value_score"] = df["score"]
    return df


def scores(fmt: str, on: bool) -> pd.Series:
    for key in (va.STARTING_DEMAND_ENV_KEY, va.NO_MARKET_FLOOR_ENV_KEY):
        os.environ[key] = "1" if on else "0"
    out = lvs.apply_valuation_lens(pool(), lvs.LENS_DYNASTY, dict(FORMATS[fmt]))
    return out.set_index("player_id")["dynasty_score"]


def main(out: str | None) -> None:
    lines = ["# Trade-advice P1-1 / P1-2: before / after (synthetic pool, flags off -> on)", ""]
    for fmt in FORMATS:
        off, on = scores(fmt, False), scores(fmt, True)
        lines.append(f"## {fmt}")
        for pid in ("QB1", "QB12", "QB19", "QB30", "Depth1"):
            lines.append(f"- {pid}: {off[pid]} -> {on[pid]} ({on[pid] - off[pid]:+d})")
        pkg_off = int(off["QB1"] + 0.85 * (off["Depth1"] + off["Depth2"]))
        pkg_on = int(on["QB1"] + 0.85 * (on["Depth1"] + on["Depth2"]))
        lines.append(f"- 1-for-3 return bundle (QB1 + two depth pieces, depth-weighted): {pkg_off} -> {pkg_on}")
        lines.append("")
    text = "\n".join(lines)
    if out:
        Path(out).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
