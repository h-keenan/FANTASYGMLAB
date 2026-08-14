#!/usr/bin/env python3
"""League-bearing Dashboard + warm trade-modal hot-path measurement.

Uses production app.py AppTest with a seeded selected league (amatl7 default)
plus a direct football-path probe. Enable:

  DYNASTYGM_HOT_PATH=1 DYNASTYGM_DASHBOARD_WATERFALL=1 DYNASTYGM_RUNTIME_TRACE=1
"""

from __future__ import annotations

import json
import os
import sys
import time
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DYNASTYGM_HOT_PATH", "1")
os.environ.setdefault("DYNASTYGM_DASHBOARD_WATERFALL", "1")
os.environ.setdefault("DYNASTYGM_RUNTIME_TRACE", "1")
os.environ.setdefault("DYNASTYGM_STARTUP", "1")

USERNAME = os.environ.get("DYNASTYGM_STALL_USERNAME", "amatl7")
LEAGUE_ID = os.environ.get("DYNASTYGM_STALL_LEAGUE_ID", "1356507236486107136")
LEAGUE_NAME = os.environ.get("DYNASTYGM_STALL_LEAGUE_NAME", "Austin and Co.")


def _state(app, key, default=None):
    try:
        return app.session_state[key]
    except Exception:
        return default


def _hot_payloads(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        if not line.startswith("HOT_PATH "):
            continue
        try:
            rows.append(json.loads(line[len("HOT_PATH ") :]))
        except json.JSONDecodeError:
            continue
    return rows


def _seed_league(app) -> None:
    from modules import session_isolation

    app.session_state["username"] = USERNAME
    app.session_state["selected_league_id"] = LEAGUE_ID
    app.session_state["selected_league_name"] = LEAGUE_NAME
    app.session_state["_identity_established"] = True
    app.session_state["_league_selection_established"] = True
    app.session_state["platform_nav_page"] = "dashboard"
    app.session_state["current_page"] = "dashboard"
    app.query_params["page"] = "dashboard"
    app.session_state["leagues_for_user"] = [
        {"league_id": LEAGUE_ID, "name": LEAGUE_NAME, "season": "2026"}
    ]
    app.session_state["leagues_for_user_username"] = USERNAME
    session_isolation.mark_explicit_guest_league_import(app.session_state)
    roster = os.environ.get("DYNASTYGM_STALL_ROSTER_ID", "").strip()
    if roster:
        try:
            app.session_state["my_roster_id"] = int(roster)
        except ValueError:
            app.session_state["my_roster_id"] = roster


def measure_dashboard(app, *, seed: bool = True) -> dict:
    from modules import hot_path_profile

    if seed:
        _seed_league(app)
    captured = StringIO()
    started = time.perf_counter()
    with redirect_stdout(captured):
        app.run(timeout=240)
    wall = (time.perf_counter() - started) * 1000
    if app.exception:
        raise RuntimeError(f"dashboard AppTest failed: {app.exception}")
    payloads = _hot_payloads(captured.getvalue())
    markdown = "\n".join(str(item.value) for item in app.markdown)
    return {
        "wall_ms": round(wall, 1),
        "useful": "data-fgl-dashboard-useful" in markdown,
        "phase": _state(app, "_dashboard_loading_phase"),
        "game_plan_sig": bool(_state(app, "_game_plan_package_signature")),
        "selected_league_id": _state(app, "selected_league_id"),
        "script_seq": _state(app, "_hot_path_script_seq"),
        "hot_path": payloads[-1] if payloads else hot_path_profile.report(top_n=10),
        "waterfall_lines": [
            line for line in captured.getvalue().splitlines() if "DASHBOARD_WATERFALL" in line
            or line[:1].isalpha() and "ms" in line
        ][:40],
    }


def measure_trade_modal(app) -> dict:
    from modules import trade_detail_navigation
    from modules import trade_hub_first_useful
    from modules import trade_hub_ui

    app.session_state["platform_nav_page"] = "trade_hub"
    app.session_state["current_page"] = "trade_hub"
    app.query_params["page"] = "trade_hub"
    captured_hub = StringIO()
    hub_started = time.perf_counter()
    with redirect_stdout(captured_hub):
        app.run(timeout=240)
    hub_ms = (time.perf_counter() - hub_started) * 1000
    if app.exception:
        raise RuntimeError(f"trade hub AppTest failed: {app.exception}")

    store = _state(app, trade_hub_first_useful.PRESENTATION_CACHE_KEY) or {}
    board = {}
    if isinstance(store, dict):
        for payload in store.values():
            if isinstance(payload, dict) and payload.get("ranked_feed"):
                board = payload
                break
    ranked = list(board.get("ranked_feed") or [])
    if not ranked:
        return {
            "hub_wall_ms": round(hub_ms, 1),
            "modal_wall_ms": None,
            "error": "no_ranked_feed",
            "board_keys": list(store.keys()) if isinstance(store, dict) else [],
        }
    idea = ranked[0]
    summary_key = trade_hub_ui.trade_summary_key(
        idea, page_context="trade_hub_feed", instance_token=0
    )
    trade_detail_navigation.open_trade(app.session_state, summary_key)
    captured_modal = StringIO()
    modal_started = time.perf_counter()
    with redirect_stdout(captured_modal):
        app.run(timeout=240)
    modal_ms = (time.perf_counter() - modal_started) * 1000
    if app.exception:
        raise RuntimeError(f"trade modal AppTest failed: {app.exception}")
    payloads = _hot_payloads(captured_modal.getvalue())
    return {
        "hub_wall_ms": round(hub_ms, 1),
        "modal_wall_ms": round(modal_ms, 1),
        "summary_key": summary_key[:48],
        "script_seq": _state(app, "_hot_path_script_seq"),
        "active_trade": _state(app, "dg_trade_detail_active"),
        "hot_path": payloads[-1] if payloads else None,
        "board_cache_present": bool(board),
    }


def measure_direct_football() -> dict:
    from modules import dashboard_waterfall as wf
    from modules import hot_path_profile
    from modules import rankings
    from modules import sleeper
    from modules import startup_cold_path
    import app as production_app

    hot_path_profile.begin("direct_football")
    wf.begin()
    state: dict = {}
    with hot_path_profile.span("sleeper_user_lookup", kind="network"):
        user_id = sleeper.get_user_id(USERNAME)
    if not user_id:
        return {"error": "no_sleeper_user", "username": USERNAME}
    with hot_path_profile.span("sleeper_league", kind="network"):
        league = sleeper.get_league(LEAGUE_ID) or {}
    with hot_path_profile.span("sleeper_rosters", kind="network"):
        rosters = sleeper.get_rosters(LEAGUE_ID) or []
    db_path = str(ROOT / "data" / "players.db")
    with hot_path_profile.span("player_hydrate", kind="disk") as meta:
        frame = startup_cold_path.ensure_players_for_startup(
            db_path=db_path,
            load_players_fn=rankings.load_players,
            build_players_table_fn=rankings.build_players_table,
            session_state=state,
            allow_network_refresh=False,
        )
        meta["cache_status"] = "hit" if frame is not None and not frame.empty else "miss"
    score_field = (
        "dynasty_score"
        if frame is not None and "dynasty_score" in frame.columns
        else "value_score"
    )
    settings = league.get("settings") if isinstance(league, dict) else {}
    settings = settings if isinstance(settings, dict) else {}
    with hot_path_profile.span("cached_league_context", kind="cpu") as meta:
        ctx = production_app.cached_league_context(
            frame,
            LEAGUE_ID,
            score_field,
            settings,
            include_intelligence=False,
            include_roster_map=True,
            include_trust=True,
            include_maturity=True,
        )
        meta["cache_status"] = "built"
    my_roster = None
    for roster in rosters:
        if str(roster.get("owner_id")) == str(user_id):
            my_roster = roster.get("roster_id")
            break
    trade_ms = None
    if my_roster is not None:
        with hot_path_profile.span("dashboard_trade_headline", kind="cpu"):
            production_app.cached_dashboard_trade_headline(
                df_players=frame,
                league_id=LEAGUE_ID,
                df_summary=ctx.get("team_direction_summary"),
                my_roster_id=int(my_roster),
                untouchables=(),
                role_items=(),
                score_field=score_field,
                pick_score_multiplier=1.0,
                team_strategy="balanced",
                league_settings_items=(),
                roster_owner_items=tuple(
                    (
                        str(roster.get("roster_id")),
                        tuple(
                            str(pid)
                            for pid in (roster.get("players") or [])
                            if pid is not None
                        ),
                    )
                    for roster in rosters
                ),
            )
    return {
        "user_id": bool(user_id),
        "roster_id": my_roster,
        "player_rows": 0 if frame is None else len(frame),
        "hot_path": hot_path_profile.report(top_n=10),
        "trade_headline_ms": trade_ms,
    }


def main() -> int:
    from streamlit.testing.v1 import AppTest

    report: dict = {"username": USERNAME, "league_id": LEAGUE_ID}
    print("HOT_PATH_HARNESS start", flush=True)
    roster_id = None
    try:
        report["direct_football"] = measure_direct_football()
        roster_id = report["direct_football"].get("roster_id")
        print("direct_football done", json.dumps(report["direct_football"].get("hot_path", {}), default=str)[:1500], flush=True)
    except Exception as exc:
        report["direct_football"] = {"error": str(exc)}
        print("direct_football error", exc, flush=True)

    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240)
    try:
        if roster_id is not None:
            os.environ["DYNASTYGM_STALL_ROSTER_ID"] = str(roster_id)
        report["dashboard"] = measure_dashboard(app)
        print("dashboard done", report["dashboard"]["wall_ms"], "useful", report["dashboard"]["useful"], "league", report["dashboard"].get("selected_league_id"), flush=True)
        hp = report["dashboard"].get("hot_path") or {}
        print("dashboard top", json.dumps(hp.get("top"), default=str)[:2000], flush=True)
        report["dashboard_warm"] = measure_dashboard(app, seed=False)
        print("dashboard_warm done", report["dashboard_warm"]["wall_ms"], flush=True)
        hpw = report["dashboard_warm"].get("hot_path") or {}
        print("dashboard_warm top", json.dumps(hpw.get("top"), default=str)[:2000], flush=True)
    except Exception as exc:
        report["dashboard"] = report.get("dashboard") or {"error": str(exc)}
        print("dashboard error", exc, flush=True)
        print(json.dumps(report, indent=2, default=str)[:8000])
        return 1

    try:
        report["trade_modal"] = measure_trade_modal(app)
        print("trade_modal done", report["trade_modal"], flush=True)
    except Exception as exc:
        report["trade_modal"] = {"error": str(exc)}
        print("trade_modal error", exc, flush=True)

    print(json.dumps(report, indent=2, default=str)[:20000], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
