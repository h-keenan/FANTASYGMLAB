from pathlib import Path
from unittest.mock import patch

from modules import performance, sleeper


def test_performance_debug_flag_is_opt_in():
    assert not performance.debug_enabled(environ={})
    assert performance.debug_enabled(environ={"DYNASTYGM_DEBUG_PERF": "true"})
    assert performance.debug_enabled(environ={"DYNASTYGM_DEBUG_PERF": "1"})


def test_performance_labels_redact_sensitive_words():
    entry = performance.record_timing("token refresh for user@example.com", 12.34, category="secret")
    assert entry["label"] == "[redacted]"
    assert entry["category"] == "[redacted]"
    assert "user@example.com" not in str(entry)
    assert "token" not in str(entry).casefold()


def test_performance_diagnostics_do_not_include_secret_values():
    with patch.object(performance, "session_timings", return_value=[{"label": "[redacted]", "elapsed_ms": 7.0}]):
        diagnostics = performance.redacted_diagnostics()
    text = str(diagnostics)
    assert "sk_test_" not in text
    assert "whsec_" not in text
    assert "SUPABASE_ANON_KEY" not in text
    assert "access_token" not in text


def test_performance_snapshot_reports_observed_cache_hit_rate():
    events = [
        {"kind": "cache", "category": "fixture", "status": "hit"},
        {"kind": "cache", "category": "fixture", "status": "hit"},
        {"kind": "cache", "category": "fixture", "status": "miss"},
    ]
    with patch.object(performance, "_session_state", return_value={
        "_perf_current_events": events,
        "_perf_last_rerun": {"route": "dashboard"},
    }):
        snapshot = performance.performance_snapshot()

    assert snapshot["cache"] == {
        "observed": 3,
        "hits": 2,
        "misses": 1,
        "hit_rate_pct": 66.7,
    }


def test_sleeper_api_calls_are_timed_without_ids_in_labels():
    source = Path("modules/sleeper.py").read_text(encoding="utf-8")
    for label in (
        "sleeper_league",
        "sleeper_league_rosters",
        "sleeper_league_users",
        "sleeper_draft_picks",
        "sleeper_players_fetch",
    ):
        assert label in source
    assert "_request_json(" in source
    assert "performance.time_block(label, category=\"sleeper\")" in source


def test_live_draft_polling_has_isolated_timing():
    source = Path("modules/live_draft.py").read_text(encoding="utf-8")
    assert "live_draft_poll_picks" in source
    assert "performance.time_block" in source
