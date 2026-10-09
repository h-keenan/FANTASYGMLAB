"""Fail closed on large deterministic Founder Beta performance regressions."""

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TRACE_PREFIX = "DYNASTYGM_RUNTIME "
MAX_COLD_SERVER_MS = 2_500.0
MAX_WARM_SERVER_MS = 750.0
MAX_FIXTURE_RENDER_MS = 3_000.0
MAX_PROTOBUF_BYTES = 520_000
SURFACES = ("dashboard", "my-team", "trade", "waivers", "league")
# Canonical explicit-rerun inventory is 64 (same on main and every pytest-
# level launch-gate test — test_ui_constitution_v1.py, test_founder_beta_
# ship_pass.py, etc. all already assert <= 64). History: budget was last
# raised to 58 for Trade Analyzer chip remounts (89fb2fb), then to 62 for
# welcome/entry state-machine work (3036a53: marketing_landing +3,
# account_ui +1, premium_page +1, trade_hub_ui -1), then to 63 for the
# live-draft trade evaluator's Trade Hub navigation site (PR #828), and now
# to 64 for one new shared rerun call site behind the welcome page's
# feature-explanation slideshow Prev/Next buttons (marketing_landing.py
# render_landing_detail_slideshow). Raise only to match the already-
# authoritative launch inventory; do not raise further without also
# updating every <= 64 assertion above in lockstep.
MAX_EXPLICIT_RERUNS = 64

from scripts.apptest_support import server_only_summary_tiles, server_only_player_quick_view


def _runtime_report(output: str) -> dict:
    reports = [
        json.loads(line[len(TRACE_PREFIX) :])
        for line in output.splitlines()
        if line.startswith(TRACE_PREFIX)
    ]
    if not reports:
        raise AssertionError("production AppTest emitted no runtime report")
    return reports[-1]


@server_only_summary_tiles()
@server_only_player_quick_view()
def main() -> int:
    os.environ["DYNASTYGM_RUNTIME_TRACE"] = "1"
    from streamlit.testing.v1 import AppTest
    from scripts.audit_founder_beta_performance import inventory

    architecture = inventory()
    if architecture["explicit_rerun_count"] > MAX_EXPLICIT_RERUNS:
        raise AssertionError(
            f"explicit reruns {architecture['explicit_rerun_count']} exceeded "
            f"{MAX_EXPLICIT_RERUNS}"
        )
    if architecture["deferred_gate_count"] < 4:
        raise AssertionError("secondary-work interaction gates were removed")
    if architecture["reduced_context_call_count"] < 4:
        raise AssertionError("route-specific reduced contexts were removed")

    production = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    samples = []
    for state in ("cold", "warm"):
        captured = io.StringIO()
        with redirect_stdout(captured):
            production.run()
        if production.exception:
            raise AssertionError(f"production {state} AppTest raised an exception")
        report = _runtime_report(captured.getvalue())
        total_ms = float(report.get("total_page_ms") or 0)
        protobuf = int((report.get("streamlit") or {}).get("protobuf_bytes") or 0)
        limit = MAX_COLD_SERVER_MS if state == "cold" else MAX_WARM_SERVER_MS
        if total_ms > limit:
            raise AssertionError(f"{state} server time {total_ms:.1f}ms exceeded {limit:.1f}ms")
        if protobuf > MAX_PROTOBUF_BYTES:
            raise AssertionError(f"{state} protobuf {protobuf} exceeded {MAX_PROTOBUF_BYTES}")
        samples.append({"state": state, "server_ms": round(total_ms, 1), "protobuf_bytes": protobuf})

    fixture = []
    for surface in SURFACES:
        application = AppTest.from_file(
            str(ROOT / "scripts" / "ui_validation_harness.py"),
            default_timeout=30,
        )
        application.query_params["surface"] = surface
        started = time.perf_counter()
        application.run()
        elapsed_ms = (time.perf_counter() - started) * 1000
        if application.exception:
            raise AssertionError(f"{surface} fixture raised an exception")
        if elapsed_ms > MAX_FIXTURE_RENDER_MS:
            raise AssertionError(
                f"{surface} fixture render {elapsed_ms:.1f}ms exceeded {MAX_FIXTURE_RENDER_MS:.1f}ms"
            )
        fixture.append({"surface": surface, "wall_ms": round(elapsed_ms, 1)})

    print(
        json.dumps(
            {
                "production": samples,
                "fixture_surfaces": fixture,
                "architecture": {
                    "explicit_reruns": architecture["explicit_rerun_count"],
                    "deferred_gates": architecture["deferred_gate_count"],
                    "reduced_context_calls": architecture["reduced_context_call_count"],
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
