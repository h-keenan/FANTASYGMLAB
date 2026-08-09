"""Cold-data startup harness — report shell vs football readiness ordering.

Usage:
  python scripts/harness_cold_data_startup.py
  python scripts/harness_cold_data_startup.py --cold-data

This does not boot Streamlit. It validates the architectural contracts and
exercises persist-first player loading against the local DB when present.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _architecture_report() -> dict:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    main = app_source.index("def main():")
    dismiss = app_source.index('runtime_trace.mark("first_usable_paint")', main)
    players = app_source.index('"players_ready"', main)
    prepared = app_source.index('"prepared_frame_ready"', main)
    identity = app_source.index("def _build_identity_shell_chrome_bundle()")
    return {
        "shell_before_players": dismiss < players,
        "shell_before_prepared": dismiss < prepared,
        "identity_shell_defined": identity > 0,
        "persist_first_players": "ensure_players_for_startup" in app_source,
    }


def _persist_first_probe() -> dict:
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from modules import startup_cold_path

    db_path = str(ROOT / "data" / "players.db")
    started = time.perf_counter()
    state: dict = {}

    def _load(_path: str):
        try:
            import pandas as pd
            from modules import rankings

            return rankings.load_players(_path)
        except Exception:
            return __import__("pandas").DataFrame()

    frame = startup_cold_path.ensure_players_for_startup(
        db_path=db_path,
        load_players_fn=_load,
        build_players_table_fn=lambda *_a, **_k: __import__("pandas").DataFrame(),
        session_state=state,
        allow_network_refresh=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    empty = getattr(frame, "empty", True)
    return {
        "db_exists": Path(db_path).exists(),
        "rows": 0 if empty else len(frame),
        "elapsed_ms": round(elapsed_ms, 1),
        "refresh_pending": bool(state.get(startup_cold_path.PLAYERS_REFRESH_PENDING_KEY)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cold-data",
        action="store_true",
        help="Exercise persist-first player load against local DB (no network rebuild).",
    )
    args = parser.parse_args()
    arch = _architecture_report()
    print("Cold-data startup harness")
    print(f"  shell_before_players: {arch['shell_before_players']}")
    print(f"  shell_before_prepared: {arch['shell_before_prepared']}")
    print(f"  identity_shell_defined: {arch['identity_shell_defined']}")
    print(f"  persist_first_players: {arch['persist_first_players']}")
    if not all(
        [
            arch["shell_before_players"],
            arch["shell_before_prepared"],
            arch["identity_shell_defined"],
            arch["persist_first_players"],
        ]
    ):
        print("FAIL: architecture contracts broken")
        return 1
    if args.cold_data:
        probe = _persist_first_probe()
        print("Persist-first probe")
        print(f"  db_exists: {probe['db_exists']}")
        print(f"  rows: {probe['rows']}")
        print(f"  elapsed_ms: {probe['elapsed_ms']}")
        print(f"  refresh_pending: {probe['refresh_pending']}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
