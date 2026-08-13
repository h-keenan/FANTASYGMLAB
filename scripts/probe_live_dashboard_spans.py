#!/usr/bin/env python3
"""Direct imported-league football path probe (amatl7) with waterfall spans.

Runs the same blocking functions Dashboard uses after hydrate, against a live
Sleeper league. Complements AppTest/browser; does not fake cache hits.
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

USERNAME = os.environ.get("DYNASTYGM_STALL_USERNAME", "amatl7")
LEAGUE_ID = os.environ.get("DYNASTYGM_STALL_LEAGUE_ID", "1356507236486107136")


def main() -> int:
    from modules import dashboard_waterfall as wf
    from modules import rankings
    from modules import sleeper
    from modules import sleeper_leagues
    from modules import startup_cold_path

    wf.begin()
    state: dict = {}

    with wf.span("sleeper_user_lookup"):
        user_id = sleeper.get_user_id(USERNAME)
    print(f"user_id={user_id}", flush=True)
    if not user_id:
        print("NO user", flush=True)
        return 1

    with wf.span("sleeper_leagues"):
        leagues = sleeper_leagues.get_user_leagues(USERNAME)
    print(f"leagues={len(leagues or [])}", flush=True)

    with wf.span("sleeper_league"):
        league = sleeper.get_league(LEAGUE_ID)
    with wf.span("sleeper_rosters"):
        rosters = sleeper.get_rosters(LEAGUE_ID)
    with wf.span("sleeper_users"):
        users = sleeper.get_users(LEAGUE_ID)
    print(
        f"league={league.get('name')} rosters={len(rosters or [])} users={len(users or [])}",
        flush=True,
    )

    db_path = str(ROOT / "data" / "players.db")
    with wf.span("player_hydrate", cache_status="disk") as meta:
        frame = startup_cold_path.ensure_players_for_startup(
            db_path=db_path,
            load_players_fn=rankings.load_players,
            build_players_table_fn=rankings.build_players_table,
            session_state=state,
            allow_network_refresh=False,
        )
        meta["cache_status"] = "hit" if frame is not None and not frame.empty else "miss"
        rows = 0 if frame is None else len(frame)
    print(f"players rows={rows} empty={frame is None or frame.empty}", flush=True)
    wf.note_cache("player_hydrate", meta["cache_status"], session_state=state)

    hash_started = time.perf_counter()
    _ = hash(tuple(frame.columns)) if frame is not None else 0
    try:
        pickled = frame.to_pickle if frame is not None else None
        _ = pickled
        import pickle

        blob = pickle.dumps(frame) if frame is not None else b""
        wf.record("player_frame_pickle_hash_proxy", (time.perf_counter() - hash_started) * 1000)
        print(f"pickle_bytes={len(blob)}", flush=True)
    except Exception as exc:
        wf.record("player_frame_pickle_hash_proxy", (time.perf_counter() - hash_started) * 1000)
        print(f"pickle_failed={exc}", flush=True)

    import app as production_app

    score_field = (
        "dynasty_score"
        if frame is not None and "dynasty_score" in frame.columns
        else "value_score"
    )
    lineup = league.get("settings") if isinstance(league, dict) else {}
    lineup = lineup if isinstance(lineup, dict) else {}

    decorated_started = time.perf_counter()
    with wf.span("cached_league_context_decorated"):
        ctx = production_app.cached_league_context(
            frame,
            LEAGUE_ID,
            score_field,
            lineup,
            include_intelligence=False,
            include_roster_map=True,
            include_trust=True,
            include_maturity=True,
        )
    summary = ctx.get("league_summary")
    print(
        f"context intel_empty={getattr(ctx.get('league_intelligence_frame'), 'empty', None)} "
        f"summary_rows={0 if summary is None else len(summary)} "
        f"decorated_ms={(time.perf_counter() - decorated_started) * 1000:.0f}",
        flush=True,
    )

    from app import cached_dashboard_trade_headline

    my_roster = None
    for roster in rosters or []:
        if str(roster.get("owner_id")) == str(user_id):
            my_roster = roster.get("roster_id")
            break
    print(f"my_roster_id={my_roster}", flush=True)
    if my_roster is not None:
        trade_started = time.perf_counter()
        with wf.span("trade_opportunity_generation"):
            ideas = cached_dashboard_trade_headline(
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
            )
        print(f"trade_ideas={len(ideas or [])} {(time.perf_counter()-trade_started)*1000:.0f}ms", flush=True)

    wf.dump(force=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
