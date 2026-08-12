"""Launch analytics foundation contracts — privacy, envelope, retention, dedupe."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from modules import launch_analytics as la


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def analytics_path(tmp_path, monkeypatch):
    path = tmp_path / "analytics.jsonl"
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(path))
    la.clear_emitted()
    return path


def test_canonical_api_surface_exists():
    for name in (
        "track_event",
        "track_page_view",
        "track_feature_use",
        "track_error",
        "track_performance",
        "track_session_started",
        "track_route_opened",
    ):
        assert callable(getattr(la, name))


def test_event_envelope_and_environment(analytics_path, monkeypatch):
    monkeypatch.setenv("DYNASTYGM_ANALYTICS_ENV", "test")
    state = {}
    assert la.track_event("session_started", once_key="s1", state=state) is True
    row = json.loads(analytics_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["event"] == "session_started"
    assert row["event_version"] == la.EVENT_VERSION
    assert row["environment"] == "test"
    assert row["session_key"].startswith("anon_")
    assert row["anon_id"] == row["session_key"]
    assert "build" in row
    assert isinstance(row["ts"], float)


def test_league_id_hashed_and_raw_blocked(analytics_path):
    state = {"selected_league_id": "sleeper-league-123"}
    assert la.track_event(
        "dashboard_reached",
        props=la.build_context_props(state, league_id="sleeper-league-123", route="dashboard"),
        once_key="a",
        state=state,
    )
    row = json.loads(analytics_path.read_text(encoding="utf-8").splitlines()[0])
    assert "league_id" not in row["props"]
    assert row["props"]["league_key"].startswith("lg_")
    assert "sleeper-league-123" not in json.dumps(row)


def test_pii_and_secrets_stripped(analytics_path):
    assert la.track_event(
        "application_error",
        props={
            "email": "a@b.com",
            "access_token": "tok",
            "league_name": "My League",
            "username": "coach",
            "traceback": "secret stack",
            "error_class": "supabase_unavailable",
            "route": "dashboard",
        },
        once_key="e1",
    )
    row = json.loads(analytics_path.read_text(encoding="utf-8").splitlines()[0])
    props = row["props"]
    for banned in ("email", "access_token", "league_name", "username", "traceback"):
        assert banned not in props
    assert props["error_class"] == "supabase_unavailable"


def test_session_and_route_rerun_dedupe(analytics_path):
    state = {}
    assert la.track_session_started(state, reason="script_start") is True
    assert la.track_session_started(state, reason="script_start") is False
    assert la.track_page_view("dashboard", state=state, changed=True) is True
    assert la.track_page_view("dashboard", state=state, changed=True) is False
    assert la.track_page_view("dashboard", state=state, changed=False) is False
    events = [
        json.loads(line)["event"]
        for line in analytics_path.read_text(encoding="utf-8").splitlines()
    ]
    assert events.count("session_started") == 1
    assert events.count("dashboard_reached") == 1


def test_checkout_alias_once_only(analytics_path):
    state = {"auth_session": {"user_id": "user-1"}}
    assert (
        la.track_event(
            "premium_checkout_started",
            props={"interval": "monthly", "route": "premium"},
            once_key="user-1:monthly:premium",
            state=state,
        )
        is True
    )
    assert (
        la.track_event(
            "checkout_started",
            props={"interval": "monthly", "route": "premium"},
            once_key="user-1:monthly:premium",
            state=state,
        )
        is False
    )
    lines = analytics_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "checkout_started"


def test_error_fingerprint_dedupe(analytics_path):
    state = {}
    assert (
        la.track_error(
            "sleeper_unavailable",
            state=state,
            route="dashboard",
            provider="sleeper",
            kind="provider_error",
        )
        is True
    )
    assert (
        la.track_error(
            "sleeper_unavailable",
            state=state,
            route="dashboard",
            provider="sleeper",
            kind="provider_error",
        )
        is False
    )
    assert len(analytics_path.read_text(encoding="utf-8").splitlines()) == 1


def test_performance_bucketed_once(analytics_path):
    state = {}
    assert (
        la.track_performance(
            "dashboard_first_useful",
            latency_ms=1234,
            state=state,
            route="dashboard",
        )
        is True
    )
    assert (
        la.track_performance(
            "dashboard_first_useful",
            latency_ms=9999,
            state=state,
            route="dashboard",
        )
        is False
    )
    row = json.loads(analytics_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["props"]["latency_ms"] == 1234
    assert row["props"]["latency_bucket"] == "lt_2000ms"


def test_fail_soft_and_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(la, "ENABLED", False)
    monkeypatch.setattr(la, "analytics_enabled", lambda **kwargs: False)
    assert la.track_event("landing_viewed") is False
    monkeypatch.setattr(la, "ENABLED", True)
    monkeypatch.setattr(la, "ANALYTICS_PATH", str(tmp_path / "no" / "e.jsonl"))

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "mkdir", boom)
    assert la.track_event("feedback_submitted") is False


def test_retention_and_feature_summaries(analytics_path):
    now = time.time()
    day = 86400.0
    # Two users: one active today and 7 days ago; one only today.
    for idx, (identity, offset) in enumerate(
        (
            ("acct_a", 0),
            ("acct_a", 7),
            ("acct_b", 0),
        )
    ):
        row = {
            "event": "dashboard_reached" if idx != 1 else "trade_hub_opened",
            "ts": now - offset * day,
            "account_hash": identity,
            "user_key": identity,
            "session_key": f"anon_{idx}",
            "anon_id": f"anon_{idx}",
            "build": "abc",
            "props": {},
        }
        with analytics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
    retention = la.retention_summary(path=analytics_path, now=now)
    assert retention["dau"] >= 2
    assert retention["wau"] >= 2
    assert "d1_retention_pct" in retention
    assert "d7_retention_pct" in retention
    features = la.feature_adoption_summary(path=analytics_path)
    assert features["Dashboard"]["views"] >= 1
    assert features["Trade Hub"]["views"] >= 1
    health = la.health_summary(path=analytics_path)
    assert "error_rate" in health
    assert "performance" in health


def test_volume_model_documented():
    assert la.EXPECTED_EVENTS_PER_SESSION >= 8
    assert la.VOLUME_MODEL["dau_1k"]["events_day"] == 18_000
    assert "warehouse" in la.VOLUME_MODEL["dau_100k"]["notes"].casefold()


def test_no_vendor_sdk_imports_in_app_modules():
    banned = (
        "import posthog",
        "from posthog",
        "import mixpanel",
        "from mixpanel",
        "import amplitude",
        "from amplitude",
        "import sentry_sdk",
        "from sentry_sdk",
        "analytics.write_key",
        "from segment",
        "import segment",
    )
    for path in (ROOT / "modules").glob("*.py"):
        text = path.read_text(encoding="utf-8").casefold()
        for token in banned:
            assert token not in text, f"{path} imports/references {token}"


def test_contract_doc_covers_foundation():
    text = (ROOT / "docs" / "founder-beta-product-analytics-contract.md").read_text(
        encoding="utf-8"
    )
    for needle in (
        "Privacy model",
        "DYNASTYGM_LAUNCH_ANALYTICS",
        "DAU",
        "D1",
        "event_version",
        "league_key",
        "Streamlit",
        "Founder dashboard",
    ):
        assert needle in text
