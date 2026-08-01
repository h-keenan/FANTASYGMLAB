from pathlib import Path

from modules import runtime_trace


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_trace_allowlist_contains_no_identity_or_payload_milestones():
    forbidden = {
        "user",
        "league_id",
        "url",
        "query",
        "token",
        "cookie",
        "payload",
        "player",
        "exception",
    }
    assert not forbidden.intersection(runtime_trace.SAFE_MILESTONES)


def test_interaction_floor_harness_is_synthetic_and_covers_four_boundaries():
    harness = (ROOT / "scripts" / "interaction_latency_harness.py").read_text(
        encoding="utf-8"
    )
    measure = (
        ROOT / "scripts" / "measure_streamlit_interaction_floor.py"
    ).read_text(encoding="utf-8")
    assert "No account, league, player, or network data" in harness
    for boundary in (
        "local_disclosure_browser_ms",
        "navigation_popover_browser_ms",
        "state_control_browser_ms",
        "prepared_modal_browser_ms",
    ):
        assert boundary in measure
    assert "browser_minus_server" in measure


def test_investigation_adds_no_shared_cache_worker_or_production_activation_path():
    changed_modules = [
        ROOT / "modules" / "runtime_trace.py",
        ROOT / "modules" / "performance.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in changed_modules)
    for forbidden in ("redis", "render key value", "background worker"):
        assert forbidden not in source.casefold()
