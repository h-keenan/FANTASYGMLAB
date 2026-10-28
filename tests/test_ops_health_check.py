"""Unit tests for scripts/ops_health_check.py (pure helpers and injected fetchers).

No network: every HTTP call goes through an injected ``get`` callable.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ops_health_check.py"
_spec = importlib.util.spec_from_file_location("ops_health_check", _PATH)
ohc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ohc)

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def _iso(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).isoformat()


def test_parse_ts_handles_z_dates_and_garbage():
    assert ohc.parse_ts("2026-10-28T01:00:00Z") == datetime(2026, 10, 28, 1, tzinfo=timezone.utc)
    assert ohc.parse_ts("2026-10-27") == datetime(2026, 10, 27, tzinfo=timezone.utc)
    assert ohc.parse_ts("") is None
    assert ohc.parse_ts("not a date") is None


def test_check_freshness_boundaries():
    assert ohc.check_freshness("x", _iso(2), 9, NOW)["status"] == "ok"
    assert ohc.check_freshness("x", _iso(10), 9, NOW)["status"] == "fail"
    assert ohc.check_freshness("x", None, 9, NOW)["status"] == "fail"


def test_check_drift_ok_grace_and_fail():
    sha = "61a93eda0c71" + "0" * 28
    assert ohc.check_drift("61a93eda0c71", sha, _iso(5), NOW)["status"] == "ok"
    assert ohc.check_drift("deadbeef0000", sha, _iso(0.1), NOW)["status"] == "ok"  # 6 min: deploying
    assert ohc.check_drift("deadbeef0000", sha, _iso(2), NOW)["status"] == "fail"
    assert ohc.check_drift("local", sha, _iso(2), NOW)["status"] == "skip"
    assert ohc.check_drift("", sha, _iso(2), NOW)["status"] == "skip"


def test_failing_signature_is_sorted_and_stable():
    results = [ohc.result("b", "fail"), ohc.result("a", "fail"), ohc.result("c", "ok"), ohc.result("d", "skip")]
    assert ohc.failing_signature(results) == "a, b"
    assert ohc.failing_signature([ohc.result("c", "ok")]) == ""


def test_render_markdown_never_includes_environment_values(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "super-secret-value")
    text = ohc.render_markdown([ohc.result("a", "fail", "HTTP 500")], NOW)
    assert "super-secret-value" not in text
    assert "Failing: a" in text


def test_cert_days_left_parses_ssl_format():
    days = ohc.cert_days_left("Dec 31 00:00:00 2026 GMT", NOW)
    assert days is not None and 63 < days < 65
    assert ohc.cert_days_left("garbage", NOW) is None


def test_public_checks_flag_a_down_api_and_a_stale_board():
    def get(url, headers=None):
        if url.endswith("/health"):
            return 503, "", 0.1
        if "dynasty-values" in url:
            body = json.dumps({"players": [{}] * 250, "source_updated_at": _iso(80)})
            return 200, body, 0.1
        if url.endswith("/robots.txt"):
            return 200, "User-Agent: *\nAllow: /", 0.1
        if url.endswith("/sitemap.xml"):
            return 200, "<loc>x</loc>" * 150, 0.1
        return 200, "FantasyDesk Trade Privacy Terms", 0.1

    results, build = ohc.run_public_checks(NOW, get)
    by_name = {r["name"]: r["status"] for r in results}
    assert build == ""
    assert by_name["api_health"] == "fail"
    assert by_name["public_values_fresh"] == "fail"
    assert by_name["web_home"] == "ok"
    assert by_name["robots"] == "ok"
    assert by_name["sitemap"] == "ok"


def test_supabase_checks_skip_without_secrets(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert {r["status"] for r in ohc.run_supabase_checks(NOW)} == {"skip"}


def test_github_checks_report_a_stale_workflow(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")

    def get(url, headers=None):
        if url.endswith("/commits/main"):
            return 200, json.dumps({"sha": "a" * 40, "commit": {"committer": {"date": _iso(5)}}}), 0.1
        runs = [{"name": "News Ingest", "updated_at": _iso(20)}, {"name": "Push Trigger Sweep", "updated_at": _iso(1)}]
        return 200, json.dumps({"workflow_runs": runs}), 0.1

    by_name = {r["name"]: r["status"] for r in ohc.run_github_checks(NOW, "bbbbbbbbbbbb", get)}
    assert by_name["deploy_drift"] == "fail"
    assert by_name["workflow_news_ingest"] == "fail"
    assert by_name["workflow_push_trigger_sweep"] == "ok"
    assert by_name["workflow_injury_status_sync"] == "fail"  # never ran in the sample
