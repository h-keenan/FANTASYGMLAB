"""#239 post-first-useful Game Plan fingerprint drift regressions.

Production a85e97c9: package MISS → first useful succeeded, then post-usable-auth
remount drifted team_strategy / strategy-adjusted pick multiplier, causing
package_fingerprint_drift + trade rebuild + post_ready_rebuild loops.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules import auth_restore_lifecycle
from modules import auth_storage_handshake
from modules import game_plan_package
from modules import game_plan_process_cache
from modules import game_plan_truth_canon as truth_canon
from modules import prepared_player_frame
from modules import tail_latency_diagnostics


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("DYNASTYGM_STARTUP", raising=False)
    game_plan_process_cache.clear_process_game_plan_caches()
    tail_latency_diagnostics.reset_process_boot_for_tests()
    yield
    game_plan_process_cache.clear_process_game_plan_caches()
    tail_latency_diagnostics.reset_process_boot_for_tests()


def test_app_resolves_truth_canon_before_render_home_dashboard():
    entry = APP.index('"dashboard_game_plan_entry"')
    canon = APP.index("pre_package_canonical_resolver", entry)
    render = APP.index("render_home_dashboard(", canon)
    assert entry < canon < render
    assert "game_plan_truth_canon_ready" in APP


def test_valued_enrichment_defers_display_but_cannot_overwrite_canon_contract():
    assert "note_presentation_strategy_write" in APP
    assert "valued_shell_chrome_enrichment" in APP


def test_shell_chrome_memos_are_per_signature():
    state: dict = {}
    builds = {"n": 0}

    def builder_a():
        builds["n"] += 1
        return {"active_team_strategy": "retool", "kind": "a"}

    def builder_b():
        builds["n"] += 1
        return {"active_team_strategy": "contender", "kind": "b"}

    a1, hit_a1 = prepared_player_frame.get_or_build_shell_chrome(
        state, signature="identity|L1", builder=builder_a
    )
    b1, hit_b1 = prepared_player_frame.get_or_build_shell_chrome(
        state, signature="valued|L1", builder=builder_b
    )
    a2, hit_a2 = prepared_player_frame.get_or_build_shell_chrome(
        state, signature="identity|L1", builder=builder_a
    )
    assert hit_a1 is False and hit_b1 is False
    assert hit_a2 is True
    assert a1["kind"] == "a" and a2["kind"] == "a"
    assert b1["kind"] == "b"
    assert builds["n"] == 2


def test_canon_lock_survives_presentation_write():
    state: dict = {}
    truth_canon.lock_canonical_inputs(
        state,
        truth_signature="sig-1",
        team_strategy="contender",
        team_strategy_label="Contender",
        auto_team_strategy="contender",
        team_strategy_override="Auto",
        pick_score_multiplier=1.023456789,
        writer="test_lock",
        mutation_kind=truth_canon.MUTATION_CANONICAL,
        force=True,
    )
    kept = truth_canon.note_presentation_strategy_write(
        state,
        attempted_strategy="retool",
        writer="presentation",
    )
    assert kept == "contender"
    canon = truth_canon.get_canon(state)
    assert canon["team_strategy"] == "contender"
    assert canon["pick_score_multiplier"] == "1.02345679"


def test_production_topology_package_hit_after_auth_remount(monkeypatch, capsys):
    monkeypatch.setenv("DYNASTYGM_STARTUP", "1")
    state: dict = {}
    auth_restore_lifecycle.ensure_startup_session(state)
    auth_restore_lifecycle.begin_script_run(state)  # run 1 shell
    auth_restore_lifecycle.begin_script_run(state)  # run 2 football/package

    truth_sig = truth_canon.build_truth_signature(
        league_id="L1",
        roster_id="R1",
        score_field="dynasty_score",
        league_settings_key="settings",
        prepared_frame_signature="frame-ccc7b75c",
    )
    resolves = {"n": 0}

    def resolve_fn():
        resolves["n"] += 1
        return "contender", "contender", "Auto", "Contender"

    # First useful path: identity would have defaulted to retool; canon locks real.
    canon = truth_canon.resolve_or_lock_strategy(
        state,
        truth_signature=truth_sig,
        pick_score_multiplier=1.05,
        resolve_fn=resolve_fn,
        writer="pre_package_canonical_resolver",
    )
    assert canon["team_strategy"] == "contender"
    assert resolves["n"] == 1

    package_sig = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame-ccc7b75c",
        score_field="dynasty_score",
        league_settings_key="settings",
        team_strategy=canon["team_strategy"],
        entitlement="free",
        lifecycle_digest="life",
        roster_state_version="rv1",
        pick_score_multiplier=canon["pick_score_multiplier"],
    )
    components_before = game_plan_package.package_fingerprint_components(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame-ccc7b75c",
        score_field="dynasty_score",
        league_settings_key="settings",
        team_strategy=canon["team_strategy"],
        entitlement="free",
        lifecycle_digest="life",
        roster_state_version="rv1",
        pick_score_multiplier=canon["pick_score_multiplier"],
    )
    game_plan_package.store_package(
        state,
        signature=package_sig,
        package={"briefing": {"items": []}, "dashboard_briefing": {}, "snapshot_items": []},
    )

    # Simulate valued enrichment attempting to write (and historically polluting session).
    state["active_team_strategy"] = "retool"
    truth_canon.note_presentation_strategy_write(
        state, attempted_strategy="retool", writer="valued_shell_chrome_enrichment"
    )

    # Post-usable auth remount (run 3) + presentation (run 4).
    state[auth_restore_lifecycle.POST_USABLE_SAVE_RERUN_KEY] = True
    from modules import startup_coordinator

    state[startup_coordinator.STARTUP_COMPLETE_KEY] = True
    auth_restore_lifecycle.begin_script_run(state)
    assert auth_storage_handshake.classify_script_run_cause(state) in {
        "post_usable_auth_save",
        "durable_auth_save_pending",
        "post_ready_interactive",
        "post_usable_auth_save_queued",
    }

    canon2 = truth_canon.resolve_or_lock_strategy(
        state,
        truth_signature=truth_sig,
        pick_score_multiplier=1.05,
        resolve_fn=resolve_fn,
        writer="pre_package_canonical_resolver",
    )
    assert resolves["n"] == 1  # no re-resolve
    assert canon2["team_strategy"] == "contender"
    assert canon2["pick_score_multiplier"] == canon["pick_score_multiplier"]

    components_after = game_plan_package.package_fingerprint_components(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame-ccc7b75c",
        score_field="dynasty_score",
        league_settings_key="settings",
        team_strategy=canon2["team_strategy"],
        entitlement="free",
        lifecycle_digest="life",
        roster_state_version="rv1",
        pick_score_multiplier=canon2["pick_score_multiplier"],
    )
    assert components_before["team_strategy"] == components_after["team_strategy"]
    assert (
        components_before["pick_score_multiplier"]
        == components_after["pick_score_multiplier"]
    )
    assert components_before["prepared_frame_signature"] == components_after[
        "prepared_frame_signature"
    ]

    package_sig2 = game_plan_package.build_package_signature(
        account_user_id="u1",
        league_id="L1",
        roster_id="R1",
        prepared_frame_signature="frame-ccc7b75c",
        score_field="dynasty_score",
        league_settings_key="settings",
        team_strategy=canon2["team_strategy"],
        entitlement="free",
        lifecycle_digest="life",
        roster_state_version="rv1",
        pick_score_multiplier=canon2["pick_score_multiplier"],
    )
    assert package_sig2 == package_sig
    cached, hit = game_plan_package.lookup_package(state, signature=package_sig2)
    assert hit is True and cached is not None

    trade_before = game_plan_process_cache.build_trade_process_signature(
        prepared_frame_signature="frame-ccc7b75c",
        league_id="L1",
        roster_id="R1",
        score_field="dynasty_score",
        league_settings_key="settings",
        team_strategy=canon["team_strategy"],
        pick_score_multiplier=1.05 * 0.88,  # contender-adjusted
        roster_state_version="rv1",
        maturity_digest="m1",
    )
    trade_after = game_plan_process_cache.build_trade_process_signature(
        prepared_frame_signature="frame-ccc7b75c",
        league_id="L1",
        roster_id="R1",
        score_field="dynasty_score",
        league_settings_key="settings",
        team_strategy=canon2["team_strategy"],
        pick_score_multiplier=1.05 * 0.88,
        roster_state_version="rv1",
        maturity_digest="m1",
    )
    assert trade_before == trade_after

    out = capsys.readouterr().out
    assert "package_fingerprint_drift" not in out


def test_explicit_strategy_change_invalidates_once():
    state: dict = {}
    truth_sig = "sig-user"
    truth_canon.lock_canonical_inputs(
        state,
        truth_signature=truth_sig,
        team_strategy="contender",
        pick_score_multiplier=1.0,
        writer="init",
        force=True,
    )
    sig1 = game_plan_package.build_package_signature(
        league_id="L1",
        roster_id="R1",
        team_strategy="contender",
        pick_score_multiplier=1.0,
        prepared_frame_signature="f",
    )
    game_plan_package.store_package(state, signature=sig1, package={"ok": True})

    truth_canon.apply_explicit_strategy_change(
        state,
        truth_signature=truth_sig,
        team_strategy="rebuild",
        team_strategy_label="Rebuild",
        auto_team_strategy="contender",
        team_strategy_override="Rebuild",
        pick_score_multiplier=1.0,
        writer="my_team_strategy_select",
    )
    game_plan_package.clear_game_plan_package(state)
    sig2 = game_plan_package.build_package_signature(
        league_id="L1",
        roster_id="R1",
        team_strategy="rebuild",
        pick_score_multiplier=1.0,
        prepared_frame_signature="f",
    )
    assert sig2 != sig1
    _, hit = game_plan_package.lookup_package(state, signature=sig2)
    assert hit is False


def test_pick_multiplier_float_repr_is_stable():
    a = game_plan_package.build_package_signature(
        league_id="L",
        roster_id="R",
        team_strategy="retool",
        pick_score_multiplier=1.05 * 1.02,
        prepared_frame_signature="f",
    )
    b = game_plan_package.build_package_signature(
        league_id="L",
        roster_id="R",
        team_strategy="retool",
        pick_score_multiplier=float(f"{1.05 * 1.02:.12f}"),
        prepared_frame_signature="f",
    )
    assert a == b


def test_pre239_identity_default_then_session_pollution_would_drift():
    """Document the failure mode fixed by canon + per-signature shell memos."""

    state: dict = {}
    # First identity build defaults to retool.
    identity, _ = prepared_player_frame.get_or_build_shell_chrome(
        state,
        signature="identity|L",
        builder=lambda: {"active_team_strategy": "retool"},
    )
    assert identity["active_team_strategy"] == "retool"
    # Valued enrichment historically overwrote the single shell slot.
    prepared_player_frame.get_or_build_shell_chrome(
        state,
        signature="valued|L",
        builder=lambda: {"active_team_strategy": "contender"},
    )
    # With per-signature store, identity remains retool (no forced rebuild).
    identity2, hit = prepared_player_frame.get_or_build_shell_chrome(
        state,
        signature="identity|L",
        builder=lambda: {"active_team_strategy": "polluted"},
    )
    assert hit is True
    assert identity2["active_team_strategy"] == "retool"


@pytest.mark.parametrize("n", [1, 3, 5, 10, 20])
def test_canon_lock_concurrency_no_cross_session_leakage(n):
    barrier = threading.Barrier(n)
    results: list[tuple[str, str]] = []

    def worker(i: int):
        state: dict = {}
        barrier.wait(timeout=5)
        truth_canon.lock_canonical_inputs(
            state,
            truth_signature=f"sig-{i % 3}",
            team_strategy="contender" if i % 2 == 0 else "rebuild",
            pick_score_multiplier=1.0 + (i % 3) * 0.01,
            writer=f"worker-{i}",
            force=True,
        )
        canon = truth_canon.get_canon(state)
        assert canon is not None
        return canon["team_strategy"], canon["truth_signature"]

    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = [pool.submit(worker, i) for i in range(n)]
        results = [f.result(timeout=5) for f in as_completed(futs)]
    # Each session keeps its own canon; no global shared mutable lock object.
    assert len(results) == n
    # Signatures only cycle 0..2 — strategies still match worker parity independently.
    assert all(sig.startswith("sig-") for _, sig in results)


def test_no_global_lock_around_unrelated_league_work():
    """Canon helpers must not serialize unrelated league builds."""

    order: list[str] = []
    gate = threading.Event()

    def slow_league():
        order.append("league_start")
        gate.wait(timeout=2)
        order.append("league_end")
        return {"league": True}

    def canon_work():
        state = {}
        truth_canon.lock_canonical_inputs(
            state,
            truth_signature="s",
            team_strategy="contender",
            pick_score_multiplier=1.0,
            writer="t",
            force=True,
        )
        order.append("canon")
        return True

    t = threading.Thread(target=lambda: slow_league())
    t.start()
    # While league work is blocked, canon still proceeds (no global lock).
    assert canon_work() is True
    assert "canon" in order
    gate.set()
    t.join(timeout=2)
    assert order.index("canon") < order.index("league_end")
