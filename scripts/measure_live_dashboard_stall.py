#!/usr/bin/env python3
"""Measure live Dashboard hydrate stall with a real league-bearing Sleeper user.

Uses production app.py + Streamlit AppTest against username amatl7.
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


def _state_get(app, key, default=None):
    try:
        return app.session_state[key]
    except Exception:
        return default


def _find_text_input(app, *needles: str):
    lowered = tuple(n.casefold() for n in needles)
    for widget in app.text_input:
        label = str(getattr(widget, "label", "") or "")
        key = str(getattr(widget, "key", "") or "")
        hay = f"{label} {key}".casefold()
        if any(n in hay for n in lowered):
            return widget
    return None


def _find_button(app, *needles: str):
    lowered = tuple(n.casefold() for n in needles)
    for widget in app.button:
        label = str(getattr(widget, "label", "") or "")
        if any(n in label.casefold() for n in lowered):
            return widget
    return None


def _find_selectbox(app, *needles: str):
    lowered = tuple(n.casefold() for n in needles)
    for widget in app.selectbox:
        label = str(getattr(widget, "label", "") or "")
        key = str(getattr(widget, "key", "") or "")
        hay = f"{label} {key}".casefold()
        if any(n in hay for n in lowered):
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

    print("TEXT", [getattr(w, "label", None) for w in app.text_input], flush=True)
    print("BUTTONS", [getattr(w, "label", None) for w in app.button], flush=True)
    print("SELECT", [getattr(w, "label", None) for w in app.selectbox], flush=True)

    username_widget = _find_text_input(app, "sleeper username", "username")
    if username_widget is None:
        print("NO username widget", flush=True)
        return 1

    t1 = time.perf_counter()
    username_widget.set_value(USERNAME).run(timeout=120)
    print(f"RUN username_set {(time.perf_counter() - t1) * 1000:.0f}ms", flush=True)
    if app.exception:
        print(f"EXCEPTION username: {app.exception}", flush=True)
        return 1

    load = _find_button(app, "load leagues", "continue with sleeper", "import")
    t2 = time.perf_counter()
    if load is not None:
        load.click().run(timeout=180)
        print(f"RUN load_click {(time.perf_counter() - t2) * 1000:.0f}ms label={load.label}", flush=True)
    else:
        app.run(timeout=180)
        print(f"RUN load_rerun {(time.perf_counter() - t2) * 1000:.0f}ms", flush=True)
    if app.exception:
        print(f"EXCEPTION load: {app.exception}", flush=True)
        return 1

    leagues = _state_get(app, "leagues_for_user") or []
    print(f"LEAGUES n={len(leagues)} username={_state_get(app, 'username')}", flush=True)
    for league in leagues[:8]:
        print(
            f"  {league.get('league_id')} {league.get('name')} {league.get('season')}",
            flush=True,
        )

    league_select = _find_selectbox(app, "select league", "league_select")
    t3 = time.perf_counter()
    if league_select is not None:
        league_select.set_value(LEAGUE_ID).run(timeout=240)
        print(f"RUN select_league {(time.perf_counter() - t3) * 1000:.0f}ms", flush=True)
    else:
        app.session_state["username"] = USERNAME
        app.session_state["selected_league_id"] = LEAGUE_ID
        app.session_state["selected_league_name"] = "Austin and Co."
        app.session_state["_identity_established"] = True
        app.session_state["_league_selection_established"] = True
        app.session_state["leagues_for_user"] = leagues or [
            {"league_id": LEAGUE_ID, "name": "Austin and Co.", "season": "2026"}
        ]
        app.run(timeout=240)
        print(f"RUN seeded_dashboard {(time.perf_counter() - t3) * 1000:.0f}ms", flush=True)
    if app.exception:
        print(f"EXCEPTION dashboard: {app.exception}", flush=True)
        return 1

    markdown = "\n".join(str(item.value) for item in app.markdown)
    print(
        "MARKERS",
        "hydrating=" + str("data-fgl-dashboard-hydrating" in markdown),
        "useful=" + str("data-fgl-dashboard-useful" in markdown),
        "game_plan_sig=" + str(bool(_state_get(app, "_game_plan_package_signature"))),
        "phase=" + str(_state_get(app, "_dashboard_loading_phase")),
        "selected=" + str(_state_get(app, "selected_league_id")),
        flush=True,
    )
    print(f"TOTAL_HARNESS {(time.perf_counter() - t0) * 1000:.0f}ms", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
