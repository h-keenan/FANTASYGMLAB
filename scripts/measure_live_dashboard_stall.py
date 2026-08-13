#!/usr/bin/env python3
"""Measure live Dashboard hydrate stall with a real league-bearing Sleeper user.

Uses production app.py + Streamlit AppTest against username amatl7
(Austin and Co. / Revivalry). Enable:

  DYNASTYGM_DASHBOARD_WATERFALL=1 DYNASTYGM_STARTUP=1

This is a diagnostic harness, not a user-facing surface.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DYNASTYGM_DASHBOARD_WATERFALL", "1")
os.environ.setdefault("DYNASTYGM_STARTUP", "1")
os.environ.setdefault("DYNASTYGM_RUNTIME_TRACE", "1")

USERNAME = os.environ.get("DYNASTYGM_STALL_USERNAME", "amatl7")
LEAGUE_ID = os.environ.get("DYNASTYGM_STALL_LEAGUE_ID", "1356507236486107136")


def _button(app, label: str):
    for widget in app.button:
        if str(widget.label) == label:
            return widget
    return None


def main() -> int:
    from streamlit.testing.v1 import AppTest

    print(f"STALL_HARNESS username={USERNAME} league_id={LEAGUE_ID}", flush=True)
    t0 = time.perf_counter()
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240)
    app.run(timeout=120)
    print(f"RUN landing {(time.perf_counter() - t0) * 1000:.0f}ms", flush=True)
    if app.exception:
        print(f"EXCEPTION landing: {app.exception}", flush=True)
        return 1

    # Sidebar username + load leagues (imported-league path).
    username_widget = None
    for widget in app.text_input:
        key = str(getattr(widget, "key", "") or "")
        label = str(getattr(widget, "label", "") or "")
        if key == "username_input" or "sleeper username" in label.casefold():
            username_widget = widget
            break
    if username_widget is None:
        print("NO username_input widget", flush=True)
        print("text_inputs", [getattr(w, "label", None) for w in app.text_input], flush=True)
        print("buttons", [getattr(w, "label", None) for w in app.button], flush=True)
        return 1

    username_widget.set_value(USERNAME)
    load = _button(app, "Load leagues for user")
    t1 = time.perf_counter()
    if load is not None:
        load.click().run(timeout=120)
    else:
        app.run(timeout=120)
    print(f"RUN load_leagues {(time.perf_counter() - t1) * 1000:.0f}ms", flush=True)
    if app.exception:
        print(f"EXCEPTION load_leagues: {app.exception}", flush=True)
        return 1

    leagues = app.session_state.get("leagues_for_user") or []
    print(f"LEAGUES n={len(leagues)}", flush=True)
    for league in leagues[:8]:
        print(
            f"  {league.get('league_id')} {league.get('name')} {league.get('season')}",
            flush=True,
        )

    league_select = None
    for widget in app.selectbox:
        if str(getattr(widget, "key", "") or "") == "league_select":
            league_select = widget
            break
    if league_select is None:
        print("NO league_select; trying session seed + rerun", flush=True)
        app.session_state["username"] = USERNAME
        app.session_state["selected_league_id"] = LEAGUE_ID
        app.session_state["_identity_established"] = True
        app.session_state["_league_selection_established"] = True
        t2 = time.perf_counter()
        app.run(timeout=240)
        print(f"RUN seeded_dashboard {(time.perf_counter() - t2) * 1000:.0f}ms", flush=True)
    else:
        t2 = time.perf_counter()
        league_select.set_value(LEAGUE_ID).run(timeout=240)
        print(f"RUN select_league {(time.perf_counter() - t2) * 1000:.0f}ms", flush=True)

    if app.exception:
        print(f"EXCEPTION dashboard: {app.exception}", flush=True)
        return 1

    markdown = "\n".join(str(item.value) for item in app.markdown)
    print(
        "MARKERS",
        "hydrating=" + str("data-fgl-dashboard-hydrating" in markdown),
        "useful=" + str("data-fgl-dashboard-useful" in markdown),
        "game_plan_sig=" + str(bool(app.session_state.get("_game_plan_package_signature"))),
        "phase=" + str(app.session_state.get("_dashboard_loading_phase")),
        flush=True,
    )
    print(f"TOTAL_HARNESS {(time.perf_counter() - t0) * 1000:.0f}ms", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
