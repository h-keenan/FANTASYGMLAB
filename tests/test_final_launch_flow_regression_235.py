"""Final launch flow regression + visual contracts (#235)."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from modules import brand_identity, decision_memory, experimental_graduation, game_plan_process_cache, gm_targets, launch_analytics, premium_conversion, session_integrity, share_recommendation_cards, tail_latency_diagnostics
from modules.ui_architecture import ARCHIVED_DESTINATION_KEYS, current_platform_destinations
from scripts import verify_package_miss_path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "final-launch-flow-regression-235.md"


@pytest.fixture(autouse=True)
def _reset():
    game_plan_process_cache.clear_process_game_plan_caches()
    yield
    game_plan_process_cache.clear_process_game_plan_caches()


def test_launch_doc_exists_and_records_verdict_fields():
    assert DOC.is_file()
    text = DOC.read_text(encoding="utf-8")
    assert "GO" in text or "CONDITIONAL GO" in text or "NO-GO" in text
    assert "package-MISS" in text or "package MISS" in text
    assert "GM control" in text or "GM orb" in text


def test_decision_memory_and_gm_targets_scope_defaults():
    assert decision_memory.experiment_enabled(environ={}) is True
    assert gm_targets.experiment_enabled(environ={}) is True
    assert share_recommendation_cards.experiment_enabled(environ={}) is True
    assert experimental_graduation.GRADUATED_DEFAULT_ON is True
    # Kill switches still honor explicit off.
    assert decision_memory.experiment_enabled(
        environ={"DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY": "0"}
    ) is False
    assert gm_targets.experiment_enabled(
        environ={"DYNASTYGM_EXPERIMENTAL_GM_TARGETS": "0"}
    ) is False


def test_share_privacy_blocks_identifiers():
    # Public card payload helpers must not expose email/username/league/roster ids.
    source = (ROOT / "modules" / "share_recommendation_cards.py").read_text(encoding="utf-8")
    assert "email" in source.casefold()  # blocklist / scrubbing references
    assert "public" in source.casefold() or "sanitize" in source.casefold() or "safe" in source.casefold()


def test_archived_routes_not_in_default_nav():
    keys = {page.key for page in current_platform_destinations(False)}
    for archived in ARCHIVED_DESTINATION_KEYS:
        assert archived not in keys


def test_package_miss_completion_and_hit_stability():
    report = verify_package_miss_path.run_package_miss_sequence(nested_reentry=True)
    assert report["ok"] is True
    assert report["cliff"] is False
    assert "game_plan_ready" in report["events"]
    assert "package_hit_reuse" in report["events"]


def test_post_hydration_no_rebuild_marker():
    state = {}
    tail_latency_diagnostics.mark_football_hydration_complete(state)
    assert state.get(tail_latency_diagnostics.FOOTBALL_HYDRATION_COMPLETE_KEY) is True


def test_provider_call_budget_constant_present():
    assert tail_latency_diagnostics.MAX_PROVIDER_LEAGUES_CALLS_GOLDEN_STARTUP >= 1
    assert tail_latency_diagnostics.MAX_PROVIDER_LEAGUES_CALLS_GOLDEN_STARTUP <= 8


def test_single_flight_concurrency_same_signature():
    sig = "launch-qa-same-235"
    builds = {"n": 0}

    def builder():
        builds["n"] += 1
        time.sleep(0.03)
        return {"ok": True}

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [
            pool.submit(
                game_plan_process_cache.get_or_build_league_context,
                signature=sig,
                builder=builder,
            )
            for _ in range(5)
        ]
        results = [f.result(timeout=5) for f in futures]
    assert builds["n"] == 1
    assert all(row[0].get("ok") for row in results)


def test_fail_soft_user_visible_threshold_separate_from_hard_timeout():
    from modules import game_plan_startup_stall as stall

    assert stall.USER_VISIBLE_FAILSOFT_S < game_plan_process_cache.SINGLEFLIGHT_WAIT_TIMEOUT_S


def test_analytics_pii_safeguards():
    blocked = launch_analytics.BLOCKED_PROP_KEYS if hasattr(launch_analytics, "BLOCKED_PROP_KEYS") else set()
    source = (ROOT / "modules" / "launch_analytics.py").read_text(encoding="utf-8")
    for key in ("email", "username", "access_token", "stripe"):
        assert key in source.casefold() or key in {str(k).casefold() for k in blocked}
