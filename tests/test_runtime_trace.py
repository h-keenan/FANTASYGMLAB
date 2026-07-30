import json
import os
from pathlib import Path
import subprocess
import sys

from scripts.summarize_runtime_traces import parse_reports, summarize


ROOT = Path(__file__).resolve().parents[1]


def _run_trace_script(source: str, *, enabled: bool) -> subprocess.CompletedProcess:
    environ = dict(os.environ)
    if enabled:
        environ["DYNASTYGM_RUNTIME_TRACE"] = "1"
    else:
        environ.pop("DYNASTYGM_RUNTIME_TRACE", None)
    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        env=environ,
        check=True,
        capture_output=True,
        text=True,
    )


def _runtime_report(completed: subprocess.CompletedProcess) -> dict:
    line = next(
        value
        for value in completed.stdout.splitlines()
        if value.startswith("DYNASTYGM_RUNTIME ")
    )
    return json.loads(line.split(" ", 1)[1])


def test_runtime_trace_is_disabled_by_default_and_decorator_is_zero_path():
    completed = _run_trace_script(
        """
from modules import runtime_trace
def original():
    return 7
decorated = runtime_trace.traced("sample", phase="loading_data")(original)
assert decorated is original
assert decorated() == 7
assert runtime_trace.finish_rerun(route="dashboard") == {}
print("disabled")
""",
        enabled=False,
    )
    assert completed.stdout.strip() == "disabled"


def test_runtime_trace_aggregates_calls_frames_external_requests_and_duplicates():
    completed = _run_trace_script(
        """
import pandas as pd
import requests
from unittest.mock import Mock, patch
from modules import runtime_trace

@runtime_trace.traced("suggest_optimal_lineup", phase="lineup_generation")
def build(frame):
    copied = frame.copy()
    return copied.merge(frame, on="player_id", suffixes=("_left", "_right"))

runtime_trace.begin_rerun(sequence=2, cache_state="warm")
source = pd.DataFrame({"player_id": ["1", "2"], "score": [10, 20]})
with runtime_trace.external_call("rss", "global_news_feed"):
    pass
response = Mock(status_code=200)
with patch("requests.sessions.Session.send", return_value=response):
    requests.get("https://api.sleeper.app/v1/league/example", timeout=1)
first = build(source)
second = build(source)
assert first.equals(second)
runtime_trace.finish_rerun(route="dashboard", total_ms=12.3)
""",
        enabled=True,
    )
    report = _runtime_report(completed)
    assert report["route"] == "dashboard"
    assert report["total_page_ms"] == 12.3
    assert report["functions"]["suggest_optimal_lineup"]["calls"] == 2
    assert report["duplicate_computations"]["suggest_optimal_lineup"] == 2
    assert report["phases"]["lineup_generation"]["calls"] == 2
    assert report["counters"]["dataframe_copies"] >= 2
    assert report["counters"]["dataframe_merges"] >= 2
    assert report["external"]["total"] == 2
    assert report["external"]["by_source"]["rss"]["calls"] == 1
    assert report["external"]["by_source"]["sleeper"]["calls"] == 1
    assert report["external"]["sleeper_calls"] == 1
    assert report["external"]["rss_news_calls"] == 1
    assert report["dataframes"][0]["rows"] == 2
    assert report["dataframes"][0]["columns"] >= 2
    assert report["dataframes"][0]["estimated_memory_bytes"] > 0


def test_production_trace_boundaries_cover_requested_computations():
    expected = {
        "modules/team_eval.py": (
            '"suggest_optimal_lineup"',
            '"build_league_summary"',
            '"get_team_vs_league"',
        ),
        "modules/roster_needs.py": (
            '"assess_team_needs"',
            '"true_roster_needs"',
            '"classify_roster_rooms"',
        ),
        "modules/trade_ideas.py": ('"trade_board_generation"',),
        "modules/rankings.py": (
            '"player_metadata_construction"',
            '"injury_level"',
            'counter="injury_parsing"',
        ),
        "modules/my_news.py": (
            '"curate_player_news"',
            '"filter_news_for_players"',
            'counter="news_parsing"',
        ),
        "app.py": (
            '"ownership_map_construction"',
            '"player_fit_construction"',
            '"roster_normalization"',
        ),
    }
    for relative_path, labels in expected.items():
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "runtime_trace.traced(" in source
        for label in labels:
            assert label in source


def test_direct_network_paths_use_the_central_observed_boundaries():
    trace_source = (ROOT / "modules/runtime_trace.py").read_text(encoding="utf-8")
    assert "requests.sessions.Session.request = traced_request" in trace_source
    assert "feedparser.parse = traced_feed_parse" in trace_source
    assert 'external_call("rss", label)' in trace_source
    assert 'source = "sleeper"' in trace_source
    assert 'source = "supabase"' in trace_source


def test_runtime_log_summarizer_groups_pages_and_ranks_observed_duplicates():
    report = {
        "schema": "dynastygm-runtime-trace-v1",
        "route": "my_team",
        "total_page_ms": 100.0,
        "phases": {"lineup_generation": {"calls": 2, "total_ms": 40.0}},
        "functions": {
            "suggest_optimal_lineup": {
                "calls": 2,
                "total_ms": 40.0,
                "max_ms": 25.0,
            }
        },
        "duplicate_computations": {"suggest_optimal_lineup": 2},
        "counters": {"dataframe_copies": 7, "dataframe_merges": 1},
        "external": {
            "by_source": {"sleeper": {"calls": 1, "total_ms": 10.0}}
        },
        "dataframes": [
            {
                "label": "team",
                "rows": 30,
                "columns": 70,
                "estimated_memory_bytes": 16800,
            }
        ],
    }
    lines = [
        "unrelated",
        f"prefix DYNASTYGM_RUNTIME {json.dumps(report)}",
    ]
    output = summarize(parse_reports(lines))
    page = output["pages"]["my_team"]
    assert page["samples"] == 1
    assert page["total_page_ms"]["mean"] == 100.0
    assert page["duplicates"]["suggest_optimal_lineup"] == 2
    assert page["dataframe_operations"]["dataframe_copies"] == 7
    assert page["external_requests"]["sleeper"]["calls"] == 1
    assert output["aggregate"]["largest_dataframes"][0]["rows"] == 30
    assert output["top_optimization_opportunities"][0]["label"] == "suggest_optimal_lineup"
