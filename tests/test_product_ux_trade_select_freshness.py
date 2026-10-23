"""Product UX polish — Trade Analyzer packages, freshness, selects, posture."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from modules import game_plan_package


ROOT = Path(__file__).resolve().parents[1]


def test_game_plan_soft_ttl_marks_stale_and_rebuilds():
    state: dict = {}
    sig = "freshness-sig-1"
    payload = {"briefing": {"items": []}, "built_at": time.time() - (6 * 60 * 60)}
    game_plan_package.store_package(state, signature=sig, package={"briefing": {"items": []}})
    # Force-age the stored package.
    state[game_plan_package.PACKAGE_KEY]["built_at"] = time.time() - (6 * 60 * 60)
    game_plan_package._PROCESS_PACKAGE_STORE[sig]["built_at"] = time.time() - (6 * 60 * 60)
    cached, hit = game_plan_package.lookup_package(state, signature=sig)
    assert hit is False
    assert cached is None
    assert state[game_plan_package.LAST_CACHE_STATUS_KEY] == "stale"
    assert state[game_plan_package.LAST_MISS_REASON_KEY] == "soft_ttl_expired"


def test_game_plan_fresh_hit_within_ttl():
    state: dict = {}
    sig = "freshness-sig-2"
    game_plan_package.store_package(state, signature=sig, package={"briefing": {"items": []}})
    cached, hit = game_plan_package.lookup_package(state, signature=sig)
    assert hit is True
    assert cached is not None
    assert state[game_plan_package.LAST_CACHE_STATUS_KEY] == "hit"
    assert game_plan_package.format_package_age_label(cached).startswith("Updated")


def test_manual_refresh_invalidates_recommendation_packages_only():
    state: dict = {"auth_session": {"user_id": "u1"}, "other": 1}
    sig = "freshness-sig-3"
    game_plan_package.store_package(state, signature=sig, package={"briefing": {"items": []}})
    assert sig in game_plan_package._PROCESS_PACKAGE_STORE
    game_plan_package.invalidate_recommendation_packages(state, signature=sig)
    assert game_plan_package.PACKAGE_KEY not in state
    assert sig not in game_plan_package._PROCESS_PACKAGE_STORE
    assert state.get("auth_session", {}).get("user_id") == "u1"
    assert state.get("other") == 1
    assert state[game_plan_package.LAST_CACHE_STATUS_KEY] == "rebuild"
