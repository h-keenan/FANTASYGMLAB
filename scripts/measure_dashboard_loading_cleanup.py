#!/usr/bin/env python3
"""Report Dashboard loading-state + critical-path ownership contracts.

Synthetic timing of clear-then-hydrate ownership (not a substitute for prod
DYNASTYGM_STARTUP logs). Prints budgets and cache/rebuild contracts.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from modules import dashboard_loading_state as dls
    from modules import prepared_player_frame
    from modules import app_styles

    samples = []
    for _ in range(20):
        state: dict = {
            dls.LAST_USEFUL_LEAGUE_KEY: "league-a",
            "_league_switch_first_useful_guard": {"to": "b"},
        }
        t0 = time.perf_counter()
        assert dls.begin_hydrate(state, league_id="league-b", league_name="B")
        # Placeholder path is HTML-only; measure ownership decision cost.
        elapsed_ms = (time.perf_counter() - t0) * 1000
        samples.append(elapsed_ms)

    samples.sort()
    report = {
        "hydrate_decision_ms": {
            "n": len(samples),
            "p50": samples[len(samples) // 2],
            "p90": samples[int(len(samples) * 0.9)],
            "p95": samples[int(len(samples) * 0.95)],
        },
        "budgets_ms": {
            "warm_first_useful": dls.BUDGET_WARM_FIRST_USEFUL_MS,
            "warm_stable": dls.BUDGET_WARM_STABLE_MS,
            "cold_first_useful": dls.BUDGET_COLD_FIRST_USEFUL_MS,
            "cold_stable": dls.BUDGET_COLD_STABLE_MS,
            "switch_cached_first_useful": dls.BUDGET_SWITCH_CACHED_FIRST_USEFUL_MS,
        },
        "policy": "clear_then_hydrate",
        "app_css_bytes": len(app_styles.APP_CSS.encode("utf-8")),
        "prepared_frame_has_league_id_in_signature": "league_id"
        in (
            ROOT / "modules" / "prepared_player_frame.py"
        ).read_text(encoding="utf-8").split("def build_frame_signature", 1)[1][
            :800
        ].casefold(),
        "notes": [
            "Prod wall-clock still comes from DYNASTYGM_STARTUP milestones.",
            "Top blockers historically: auth restore reruns, prepared-frame MISS, Game Plan package MISS.",
            "This pass emits a stable placeholder before post-dismiss football work on context change.",
        ],
    }
    # Warm frame retain contract still holds.
    state = {}
    frame_sig = "sig-test"
    import pandas as pd

    built = {"n": 0}

    def builder():
        built["n"] += 1
        return pd.DataFrame([{"player_id": "1", "value_score": 1.0}])

    prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=frame_sig, builder=builder
    )
    prepared_player_frame.get_or_build_valued_ranked_frame(
        state, signature=frame_sig, builder=builder
    )
    report["prepared_frame_builds_for_two_lookups"] = built["n"]
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
