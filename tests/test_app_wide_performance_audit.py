"""App-wide performance audit contracts (PR #166)."""

from __future__ import annotations

from pathlib import Path

from modules import live_draft


ROOT = Path(__file__).resolve().parents[1]


def test_live_draft_discovery_ttl_skips_warm_support_routes():
    session = {
        "_cached_live_draft_active": False,
        live_draft.LIVE_DRAFT_DISCOVERY_AT_KEY: 1_000.0,
        live_draft.LIVE_DRAFT_DISCOVERY_LEAGUE_KEY: "lg1",
    }
    assert (
        live_draft.should_refresh_live_draft_discovery(
            session=session,
            league_id="lg1",
            current_page="premium",
            now=1_010.0,
        )
        is False
    )
    assert (
        live_draft.should_refresh_live_draft_discovery(
            session=session,
            league_id="lg1",
            current_page="dashboard",
            now=1_010.0,
            ttl_seconds=60.0,
        )
        is False
    )
    assert (
        live_draft.should_refresh_live_draft_discovery(
            session=session,
            league_id="lg1",
            current_page="dashboard",
            now=1_070.0,
            ttl_seconds=60.0,
        )
        is True
    )
    assert (
        live_draft.should_refresh_live_draft_discovery(
            session=session,
            league_id="lg2",
            current_page="dashboard",
            now=1_010.0,
        )
        is True
    )
    assert (
        live_draft.should_refresh_live_draft_discovery(
            session=session,
            league_id="lg1",
            current_page="live_draft",
            now=1_010.0,
        )
        is True
    )


def test_live_draft_discovery_mark_persists_ttl_keys():
    session: dict = {}
    live_draft.mark_live_draft_discovery(
        session,
        league_id="lg9",
        active=True,
        now=42.5,
    )
    assert session["_cached_live_draft_active"] is True
    assert session[live_draft.LIVE_DRAFT_DISCOVERY_LEAGUE_KEY] == "lg9"
    assert session[live_draft.LIVE_DRAFT_DISCOVERY_AT_KEY] == 42.5


def test_app_wires_live_draft_discovery_ttl_and_premium_profile_cache():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "should_refresh_live_draft_discovery" in source
    assert "mark_live_draft_discovery" in source
    assert 'force=billing_flag == "success"' in source
    assert "LIVE_DRAFT_DISCOVERY_AT_KEY" in source


def test_app_wide_performance_harness_and_audit_doc_exist():
    harness = (ROOT / "scripts" / "measure_app_wide_performance.py").read_text(
        encoding="utf-8"
    )
    doc = (ROOT / "docs" / "app-wide-performance-audit.md").read_text(encoding="utf-8")
    assert "dynastygm-app-wide-performance-v1" in harness
    assert "DYNASTYGM_RUNTIME_TRACE" in harness
    assert "Latency map" in doc or "latency map" in doc.casefold()
    assert "Live Draft discovery" in doc or "live_draft_discovery" in doc
    assert "protobuf" in doc.casefold()
    assert "No football" in doc or "no football" in doc.casefold()
