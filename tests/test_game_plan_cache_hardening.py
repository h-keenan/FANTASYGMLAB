"""Cache hardening: TradeTrust pickle safety + Game Plan fingerprint stability (#222)."""

from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
import pytest

from modules import game_plan_package
from modules import game_plan_process_cache
from modules import recommendation_lifecycle
from modules import trade_trust


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_trade_trust_context_not_defined_in_app_main():
    assert "class TradeTrustContext" not in APP
    assert "from modules.trade_trust import TradeTrustContext" in APP
    assert "serialize_trade_trust_context" in APP


def test_cached_league_context_serializes_trust_before_return():
    assert "trade_trust.serialize_trade_trust_context" in APP
    assert "assert_pickle_safe_league_context" in APP


def test_trade_trust_round_trip_pickle_and_hydrate():
    original = trade_trust.TradeTrustContext(
        ownership_by_player=(("p1", 7), ("p2", 8)),
        valid_roster_ids=frozenset({7, 8}),
        team_name_to_roster=(("alpha", 7),),
        league_context_valid=True,
    )
    payload = trade_trust.serialize_trade_trust_context(original)
    assert isinstance(payload, dict)
    trade_trust.assert_pickle_safe_league_context({"trade_trust_context": payload})
    dumped = pickle.dumps(payload)
    loaded = pickle.loads(dumped)
    hydrated = trade_trust.hydrate_trade_trust_context(loaded)
    assert hydrated == original


def test_assert_pickle_safe_rejects_runtime_trust_instance():
    ctx = trade_trust.TradeTrustContext(
        ownership_by_player=(),
        valid_roster_ids=frozenset(),
        team_name_to_roster=(),
        league_context_valid=False,
    )
    with pytest.raises(TypeError, match="serialized"):
        trade_trust.assert_pickle_safe_league_context({"trade_trust_context": ctx})


def test_package_signature_ignores_startup_mode():
    base = dict(
        account_user_id="u1",
        league_id="L1",
        roster_id="7",
        prepared_frame_signature="frame",
        score_field="value_score",
        league_settings_key="settings",
        team_strategy="contend",
        role_items=(("p1", "Core"),),
        untouchables=("A",),
        entitlement="premium",
        lifecycle_digest="fp",
        roster_state_version="rv1",
        pick_score_multiplier=1,
    )
    a = game_plan_package.build_package_signature(**base, startup_mode=True)
    b = game_plan_package.build_package_signature(**base, startup_mode=False)
    assert a == b


def test_package_signature_stable_across_auth_save_account_scope_flip():
    """Account is keyed separately; football lifecycle digest excludes account_scope."""

    fp_anon = recommendation_lifecycle.CanonicalContextFingerprint(
        account_scope="anon",
        league_id="L1",
        roster_id="7",
        season="2026",
        week="1",
        scoring_format="PPR",
        valuation_lens="value_score",
        roster_state_version="rv1",
        provider_data_version="settings",
    )
    fp_user = recommendation_lifecycle.CanonicalContextFingerprint(
        account_scope="user-123",
        league_id="L1",
        roster_id="7",
        season="2026",
        week="1",
        scoring_format="PPR",
        valuation_lens="value_score",
        roster_state_version="rv1",
        provider_data_version="settings",
    )
    assert fp_anon.digest != fp_user.digest
    assert fp_anon.football_digest == fp_user.football_digest
    sig_a = game_plan_package.build_package_signature(
        account_user_id="user-123",
        league_id="L1",
        roster_id="7",
        prepared_frame_signature="frame",
        lifecycle_digest=fp_anon.football_digest,
    )
    sig_b = game_plan_package.build_package_signature(
        account_user_id="user-123",
        league_id="L1",
        roster_id="7",
        prepared_frame_signature="frame",
        lifecycle_digest=fp_user.football_digest,
    )
    assert sig_a == sig_b


def test_league_process_signature_ignores_startup_mode():
    a = game_plan_process_cache.build_league_process_signature(
        prepared_frame_signature="f",
        league_id="L1",
        score_field="value_score",
        startup_mode=True,
        flags=(False, True, True, True),
    )
    b = game_plan_process_cache.build_league_process_signature(
        prepared_frame_signature="f",
        league_id="L1",
        score_field="value_score",
        startup_mode=False,
        flags=(False, True, True, True),
    )
    assert a == b


def test_maturity_digest_ignores_startup_complete_flip():
    a = game_plan_process_cache.maturity_context_digest(
        {"dashboard_phase": "in_season", "startup_complete": False, "evidence_level": 2}
    )
    b = game_plan_process_cache.maturity_context_digest(
        {"dashboard_phase": "in_season", "startup_complete": True, "evidence_level": 2}
    )
    assert a == b


def test_trade_signature_stable_when_only_startup_complete_changes():
    base = dict(
        prepared_frame_signature="frame",
        league_id="L1",
        roster_id="7",
        score_field="value_score",
        team_strategy="contend",
        role_items=(("p1", "Core"),),
        roster_state_version="rv1",
    )
    a = game_plan_process_cache.build_trade_process_signature(
        **base,
        maturity_digest=game_plan_process_cache.maturity_context_digest(
            {"dashboard_phase": "in_season", "startup_complete": False}
        ),
    )
    b = game_plan_process_cache.build_trade_process_signature(
        **base,
        maturity_digest=game_plan_process_cache.maturity_context_digest(
            {"dashboard_phase": "in_season", "startup_complete": True}
        ),
    )
    assert a == b


def test_package_invalidates_on_league_and_roles():
    base = dict(
        account_user_id="u1",
        league_id="L1",
        roster_id="7",
        prepared_frame_signature="frame",
        team_strategy="contend",
        role_items=(("p1", "Core"),),
    )
    a = game_plan_package.build_package_signature(**base)
    assert a != game_plan_package.build_package_signature(**{**base, "league_id": "L2"})
    assert a != game_plan_package.build_package_signature(
        **{**base, "role_items": (("p1", "Bench"),)}
    )
    assert a != game_plan_package.build_package_signature(
        **{**base, "account_user_id": "u2"}
    )


def test_app_emits_fingerprint_component_diagnostics():
    assert "game_plan_package_fingerprint_components" in APP
    assert "trade_inventory_fingerprint_components" in APP
    assert "football_digest" in APP


def test_post_auth_save_package_hit_contract():
    """Simulated: same football inputs before/after auth remount → package hit."""

    state: dict = {}
    sig = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="7",
        prepared_frame_signature="frame",
        lifecycle_digest="stable-football",
        startup_mode=True,
    )
    game_plan_package.store_package(
        state,
        signature=sig,
        package={"recommendation_ids": ["rec-1"], "briefing": {"items": []}},
    )
    after_auth = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="7",
        prepared_frame_signature="frame",
        lifecycle_digest="stable-football",
        startup_mode=False,  # flipped after usable
    )
    cached, hit = game_plan_package.lookup_package(state, signature=after_auth)
    assert hit is True
    assert cached is not None
    assert cached["recommendation_ids"] == ["rec-1"]
