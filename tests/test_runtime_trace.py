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


def test_runtime_trace_records_sanitized_correlation_and_lifecycle_boundaries():
    completed = _run_trace_script(
        """
from modules import runtime_trace
runtime_trace.begin_rerun(sequence=3, cache_state="warm")
runtime_trace.mark("authentication_complete")
runtime_trace.mark("private-user@example.com")
runtime_trace.finish_rerun(route="dashboard", total_ms=4.2)
""",
        enabled=True,
    )
    report = _runtime_report(completed)
    assert report["schema"] == "dynastygm-runtime-trace-v3"
    assert len(report["correlation_id"]) == 16
    assert set(report["correlation_id"]) <= set("0123456789abcdef")
    assert report["sequence"] == 3
    assert report["process_uptime_ms"] >= 0
    assert report["first_traced_rerun_after_process_start"] is True
    assert "authentication_complete" in report["milestones"]
    assert set(report["milestones"]) == {
        "authentication_complete",
        "page_elements_built",
        "rerun_complete",
        "streamlit_session_run_started",
    }
    assert "page_elements_built" in report["milestones"]
    assert "rerun_complete" in report["milestones"]
    assert "private-user@example.com" not in completed.stdout


def test_runtime_trace_context_is_isolated_between_threads():
    completed = _run_trace_script(
        """
import threading
from modules import runtime_trace

def run(sequence):
    runtime_trace.begin_rerun(sequence=sequence, cache_state="warm")
    runtime_trace.mark("thread_boundary")
    runtime_trace.finish_rerun(route="dashboard", total_ms=float(sequence))

threads = [threading.Thread(target=run, args=(value,)) for value in (10, 20)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
""",
        enabled=True,
    )
    reports = [
        json.loads(line.split(" ", 1)[1])
        for line in completed.stdout.splitlines()
        if line.startswith("DYNASTYGM_RUNTIME ")
    ]
    assert {report["sequence"] for report in reports} == {10, 20}
    assert len({report["correlation_id"] for report in reports}) == 2
    assert {report["total_page_ms"] for report in reports} == {10.0, 20.0}


def test_session_correlation_is_anonymous_stable_and_separate_from_rerun_span():
    completed = _run_trace_script(
        """
from modules import runtime_trace
for sequence in (1, 2):
    runtime_trace.begin_rerun(
        sequence=sequence,
        cache_state="warm",
        session_correlation_id="0123456789abcdef",
        module_import_ms=123.45,
    )
    runtime_trace.finish_rerun(route="dashboard")
""",
        enabled=True,
    )
    reports = [
        json.loads(line.split(" ", 1)[1])
        for line in completed.stdout.splitlines()
        if line.startswith("DYNASTYGM_RUNTIME ")
    ]
    assert {report["session_correlation_id"] for report in reports} == {
        "0123456789abcdef"
    }
    assert len({report["correlation_id"] for report in reports}) == 2
    assert {report["process"]["application_import_ms"] for report in reports} == {
        123.5
    }
    assert all(
        report["process"]["initial_http_request_observable"] is False
        for report in reports
    )


def test_streamlit_message_observation_records_only_structure_and_size():
    completed = _run_trace_script(
        """
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from modules import runtime_trace

runtime_trace.begin_rerun()
message = ForwardMsg()
message.delta.new_element.markdown.body = "private-user@example.com"
runtime_trace._observe_streamlit_message(message)
runtime_trace.finish_rerun(route="dashboard")
""",
        enabled=True,
    )
    report = _runtime_report(completed)
    assert report["counters"]["streamlit_messages"] == 1
    assert report["counters"]["streamlit_elements"] == 1
    assert report["streamlit"]["protobuf_bytes"] > 0
    assert report["streamlit"]["largest_messages"][0]["type"] == "markdown"
    assert "private-user@example.com" not in completed.stdout


def test_css_message_observation_records_hash_and_sizes_without_contents():
    completed = _run_trace_script(
        """
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from modules import runtime_trace

runtime_trace.begin_rerun()
message = ForwardMsg()
message.delta.new_element.markdown.body = "<style>.private-selector{color:red}</style>"
runtime_trace._observe_streamlit_message(message)
runtime_trace.finish_rerun(route="dashboard")
""",
        enabled=True,
    )
    report = _runtime_report(completed)
    css_message = report["streamlit"]["css_messages"][0]
    assert css_message["ordinal"] == 1
    assert len(css_message["sha256"]) == 64
    assert css_message["utf8_bytes"] == 43
    assert css_message["protobuf_bytes"] > css_message["utf8_bytes"]
    assert "private-selector" not in completed.stdout
    assert "color:red" not in completed.stdout


def test_disabled_trace_does_not_observe_or_hash_css_messages():
    completed = _run_trace_script(
        """
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from modules import runtime_trace

runtime_trace.begin_rerun()
message = ForwardMsg()
message.delta.new_element.markdown.body = "<style>.private-selector{color:red}</style>"
runtime_trace._observe_streamlit_message(message)
assert runtime_trace.finish_rerun(route="dashboard") == {}
print("disabled")
""",
        enabled=False,
    )
    assert completed.stdout.strip() == "disabled"


def test_explicit_rerun_event_preserves_only_structural_correlation():
    completed = _run_trace_script(
        """
from modules import runtime_trace
runtime_trace.begin_rerun(sequence=4, cache_state="warm")
runtime_trace._emit_rerun_request()
""",
        enabled=True,
    )
    line = next(
        value
        for value in completed.stdout.splitlines()
        if value.startswith("DYNASTYGM_RUNTIME_RERUN ")
    )
    event = json.loads(line.split(" ", 1)[1])
    assert event["schema"] == "dynastygm-runtime-rerun-event-v1"
    assert event["sequence"] == 4
    assert len(event["correlation_id"]) == 16
    assert event["elapsed_ms"] >= 0


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


def test_runtime_trace_installs_hooks_once_and_preserves_exceptions():
    completed = _run_trace_script(
        """
import pandas as pd
from modules import runtime_trace

runtime_trace.begin_rerun()
copy_hook = pd.DataFrame.copy
runtime_trace.begin_rerun()
assert pd.DataFrame.copy is copy_hook

class ExpectedError(RuntimeError):
    pass

error = ExpectedError("private-user@example.com")

@runtime_trace.traced("failing_operation", phase="loading_data")
def fail():
    raise error

try:
    fail()
except ExpectedError as caught:
    assert caught is error
else:
    raise AssertionError("exception did not propagate")

report = runtime_trace.finish_rerun(route="dashboard")
assert report["functions"]["failing_operation"]["calls"] == 1
""",
        enabled=True,
    )
    report = _runtime_report(completed)
    assert report["route"] == "dashboard"
    assert "private-user@example.com" not in completed.stdout


def test_runtime_trace_nested_timings_are_inclusive_and_counted_once():
    completed = _run_trace_script(
        """
from modules import runtime_trace

@runtime_trace.traced("inner", phase="loading_data")
def inner():
    return 1

@runtime_trace.traced("outer", phase="loading_data")
def outer():
    return inner()

runtime_trace.begin_rerun()
assert outer() == 1
runtime_trace.finish_rerun(route="dashboard")
""",
        enabled=True,
    )
    report = _runtime_report(completed)
    assert report["timing_semantics"] == "inclusive"
    assert report["functions"]["outer"]["calls"] == 1
    assert report["functions"]["inner"]["calls"] == 1
    assert report["phases"]["loading_data"]["calls"] == 2


def test_runtime_trace_logs_only_structural_dataframe_and_request_metadata():
    completed = _run_trace_script(
        """
import pandas as pd
import requests
from unittest.mock import Mock, patch
from modules import runtime_trace

runtime_trace.begin_rerun()
private_value = "private-user@example.com"
frame = pd.DataFrame({"email": [private_value], "player_id": ["secret-101"]})
frame.copy()
response = Mock(status_code=200)
private_url = "https://example.test/league/private-999?email=" + private_value
with patch("requests.sessions.Session.send", return_value=response):
    requests.get(private_url, timeout=1)
runtime_trace.finish_rerun(route="player_detail")
""",
        enabled=True,
    )
    report = _runtime_report(completed)
    assert report["external"]["by_source"]["http"]["calls"] == 1
    assert report["dataframes"][0]["rows"] == 1
    assert "private-user@example.com" not in completed.stdout
    assert "private-999" not in completed.stdout
    assert "secret-101" not in completed.stdout
    assert private_url_not_logged(report)


def test_rss_hook_counts_url_retrievals_but_not_in_memory_parsing():
    completed = _run_trace_script(
        """
import feedparser
from unittest.mock import patch
from modules import runtime_trace

with patch.object(feedparser, "parse", return_value={"entries": []}):
    runtime_trace.begin_rerun()
    feedparser.parse(b"<rss><channel></channel></rss>")
    feedparser.parse("https://example.test/feed")
    runtime_trace.finish_rerun(route="player_detail")
""",
        enabled=True,
    )
    report = _runtime_report(completed)
    assert report["external"]["rss_news_calls"] == 1
    assert report["external"]["by_source"]["rss"]["calls"] == 1


def private_url_not_logged(report: dict) -> bool:
    return "url" not in json.dumps(report).casefold()


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
        "cache_state": "cold",
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
    assert page["cache_states"]["cold"]["total_page_ms"]["mean"] == 100.0
    assert page["cache_states"]["cold"]["total_page_ms"]["p50"] == 100.0
    assert page["duplicates"]["suggest_optimal_lineup"] == 2
    assert page["dataframe_operations"]["dataframe_copies"] == 7
    assert page["external_requests"]["sleeper"]["calls"] == 1
    assert output["aggregate"]["largest_dataframes"][0]["rows"] == 30
    assert output["top_optimization_opportunities"][0]["label"] == "suggest_optimal_lineup"


def test_runtime_log_summarizer_does_not_conflate_cold_and_warm_samples():
    reports = [
        {
            "schema": "dynastygm-runtime-trace-v1",
            "route": "dashboard",
            "cache_state": "cold",
            "total_page_ms": 1000.0,
        },
        {
            "schema": "dynastygm-runtime-trace-v1",
            "route": "dashboard",
            "cache_state": "warm",
            "total_page_ms": 100.0,
        },
    ]
    page = summarize(reports)["pages"]["dashboard"]
    assert page["cache_states"]["cold"]["total_page_ms"]["p50"] == 1000.0
    assert page["cache_states"]["warm"]["total_page_ms"]["p50"] == 100.0
    assert page["total_page_ms_all_cache_states"]["mean"] == 550.0


def test_runtime_log_summarizer_accepts_v2_and_reports_streamlit_payloads():
    report = {
        "schema": "dynastygm-runtime-trace-v2",
        "route": "dashboard",
        "cache_state": "warm",
        "total_page_ms": 50.0,
        "streamlit": {"protobuf_bytes": 4096},
    }
    output = summarize([report])
    page = output["pages"]["dashboard"]
    assert page["streamlit_protobuf_bytes"]["p50"] == 4096.0


def test_runtime_log_summarizer_accepts_v3_session_correlations():
    report = {
        "schema": "dynastygm-runtime-trace-v3",
        "session_correlation_id": "0123456789abcdef",
        "correlation_id": "fedcba9876543210",
        "route": "dashboard",
        "cache_state": "warm",
        "total_page_ms": 50.0,
    }
    output = summarize([report])
    assert output["pages"]["dashboard"]["samples"] == 1


def test_aggregate_stage_counters_are_not_reported_as_duplicate_functions():
    completed = _run_trace_script(
        """
from modules import runtime_trace

@runtime_trace.traced("filter_news_for_players", phase="news_retrieval", counter="news_parsing")
def filter_news():
    return []

@runtime_trace.traced("curate_player_news", phase="news_retrieval", counter="news_parsing")
def curate_news():
    return []

runtime_trace.begin_rerun()
filter_news()
curate_news()
runtime_trace.finish_rerun(route="dashboard")
""",
        enabled=True,
    )
    report = _runtime_report(completed)
    assert report["counters"]["news_parsing"] == 2
    assert "news_parsing" not in report["duplicate_computations"]
