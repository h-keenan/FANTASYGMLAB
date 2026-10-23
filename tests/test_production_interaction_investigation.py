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


def test_investigation_adds_no_shared_cache_worker_or_production_activation_path():
    changed_modules = [
        ROOT / "modules" / "runtime_trace.py",
        ROOT / "modules" / "performance.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in changed_modules)
    for forbidden in ("redis", "render key value", "background worker"):
        assert forbidden not in source.casefold()
