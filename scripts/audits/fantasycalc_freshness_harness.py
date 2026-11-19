"""Before/after harness for DYNASTYGM_FRESH_PROVIDER_CACHE_V1 (data-truth audit finding 1).

Simulates the players refresh job's starting state on a THROWAWAY directory (never data/): a seed CSV that a fresh git
checkout has given a brand-new mtime. Prints what ``get_dynasty_values()`` serves with the flag off and on.

    python scripts/audits/fantasycalc_freshness_harness.py            # offline, stubbed provider
    python scripts/audits/fantasycalc_freshness_harness.py --live     # real public FantasyCalc API, 1QB dynasty

Offline output is deterministic; --live also prints how far the seed drifted from the live board.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from modules import fantasycalc  # noqa: E402

SEED = [("Seed Star", "WR", 9842), ("Seed Vet", "RB", 2650), ("Seed Rookie", "QB", 400)]
STUB = [
    {"player": {"name": "Seed Star", "position": "WR", "maybeTeam": "CIN", "sleeperId": "1"}, "value": 9076},
    {"player": {"name": "Seed Vet", "position": "RB", "maybeTeam": "BAL", "sleeperId": "2"}, "value": 2100},
    {"player": {"name": "Seed Rookie", "position": "QB", "maybeTeam": "NE", "sleeperId": "3"}, "value": 6358},
]


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def run(flag_on: bool, live: bool) -> pd.DataFrame:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "fantasycalc_values.csv")
        fantasycalc.FANTASYCALC_CACHE_PATH = path
        pd.DataFrame([{"name": n, "position": p, "team": "", "value": v} for n, p, v in SEED]).to_csv(path, index=False)  # mtime = now, like a checkout
        os.environ["DYNASTYGM_FRESH_PROVIDER_CACHE_V1"] = "1" if flag_on else "0"
        real_get = fantasycalc.requests.get
        calls = []
        if not live:
            fantasycalc.requests.get = lambda *a, **k: (calls.append(1), _Resp(STUB))[1]
        try:
            df = fantasycalc.get_dynasty_values()
        finally:
            fantasycalc.requests.get = real_get
        df.attrs["provider_calls"] = len(calls)
        return df


def main() -> None:
    live = "--live" in sys.argv
    for flag_on in (False, True):
        df = run(flag_on, live)
        age = time.time() - float(df.attrs.get("as_of") or 0)
        print(f"\nflag {'ON ' if flag_on else 'OFF'}: rows={len(df)} as_of_age_h={age / 3600:.1f} provider_calls={df.attrs.get('provider_calls', 'n/a')}")
        print(df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
