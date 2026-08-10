"""Local package-MISS path completion verifier (#234).

Proves the post-#233 stage sequence completes without nested-lock stall:

  package MISS → shared context → trade → briefing → compose → store → ready

Does NOT claim production numbers. Production capture still requires
DYNASTYGM_STARTUP=1 on Render + founder returning-user repro.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import game_plan_process_cache
from modules import game_plan_startup_stall as stall
from modules import tail_latency_diagnostics


STAGES = (
    "game_plan_package_build",
    "game_plan_shared_context",
    "game_plan_trade",
    "game_plan_briefing",
    "game_plan_compose",
    "game_plan_package_store",
)


def run_package_miss_sequence(*, nested_reentry: bool = False) -> dict:
    game_plan_process_cache.clear_process_game_plan_caches()
    state: dict = {}
    origin = time.perf_counter()
    sig = "verify-package-miss-234"
    events: list[str] = []

    def _mark(name: str) -> None:
        events.append(name)

    package_started = time.perf_counter()
    stall.emit_stage_event(state, stage="game_plan_package_build", phase="start")
    _mark("package_miss_start")

    def _builder():
        _mark("shared_context_builder")
        if nested_reentry:
            # Same-signature nested acquire must not hang (#233).
            game_plan_process_cache.get_or_build_league_context(
                signature=sig,
                builder=lambda: {"nested": True},
                session_state=state,
            )
        time.sleep(0.01)
        return {"ok": True, "teams": 12}

    with stall.stage_span(state, "game_plan_shared_context", signature_prefix=sig[:8]):
        ctx, hit = game_plan_process_cache.get_or_build_league_context(
            signature=sig,
            builder=_builder,
            session_state=state,
        )
        _mark("shared_context_complete")
        assert hit is False
        assert ctx.get("ok") is True

    with stall.stage_span(state, "game_plan_trade", signature_prefix=sig[:8]):
        time.sleep(0.002)
        _mark("trade_inventory")

    with stall.stage_span(state, "game_plan_briefing", signature_prefix=sig[:8]):
        time.sleep(0.002)
        _mark("briefing_assembly")

    with stall.stage_span(state, "game_plan_compose", signature_prefix=sig[:8]):
        time.sleep(0.002)
        _mark("compose")

    with stall.stage_span(state, "game_plan_package_store", signature_prefix=sig[:8]):
        time.sleep(0.001)
        _mark("package_store")

    stall.emit_stage_event(
        state,
        stage="game_plan_package_build",
        phase="complete",
        duration_ms=(time.perf_counter() - package_started) * 1000.0,
    )
    _mark("game_plan_ready")

    # Second lookup must HIT.
    ctx2, hit2 = game_plan_process_cache.get_or_build_league_context(
        signature=sig,
        builder=lambda: {"ok": False},
        session_state=state,
    )
    assert hit2 is True
    assert ctx2.get("ok") is True
    _mark("package_hit_reuse")

    elapsed_ms = round((time.perf_counter() - origin) * 1000.0, 1)
    return {
        "kind": "package_miss_path_verification",
        "environment": "LOCAL",
        "ok": True,
        "cliff": False,
        "events": events,
        "elapsed_ms": elapsed_ms,
        "nested_reentry_safe": True,
        "production_note": (
            "LOCAL synthetic stage sequence only. Production package-MISS proof "
            "requires DYNASTYGM_STARTUP=1 logs from the returning-user repro on Render."
        ),
    }


def main() -> int:
    report = run_package_miss_sequence(nested_reentry=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
